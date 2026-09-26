"""
Composition de l'application FastAPI (IntegraSanté by CPage)

Rôle de ce module
- Construire l'instance FastAPI et y brancher middlewares, routeurs et admin.
- Gérer le cycle de vie (lifespan): initialisation DB, rechargement des serveurs
    MLLP, arrêt propre en extinction.
- Exposer un `MLLPManager` partagé via `app.state`.

Points clés
- En mode tests (env TESTING=1), on évite l'init DB/serveurs et on laisse les
    fixtures contrôler l'environnement pour des tests isolés.
- Les logs MLLP détaillés s'activent avec `MLLP_TRACE=1`.
"""

import logging
import os
import secrets
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware

# Import de la configuration centralisée
from config.settings import Settings, settings

from app.middleware.flash import FlashMessageMiddleware
from app.middleware.ght_context import GHTContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.version import VersionMiddleware
from app.middleware.error_handler import ErrorHandlingMiddleware, RequestLoggingMiddleware
from app.infrastructure.metrics import MetricsMiddleware

from app.db import (
    create_database_engine,
    engine,
    get_session as database_session_dependency,
    make_session_dependency,
    make_session_factory,
    migrate_database,
)
from app.models import scenarios as models_scenarios  # noqa: F401 - ORM registry
from app.admin import register_admin_views  # SQLAdmin views
from app.db_session_factory import get_session as compatibility_session_dependency
from app.db_session_factory import session_factory as default_session_factory
from app.services.transport_inbound import on_message_inbound
from app.services.mllp_manager import MLLPManager
from app.services.entity_events import register_entity_events
from app.services.entity_events_structure import register_structure_entity_events
from app.services.scheduler import BackgroundScheduler
from app.services.cache_service import create_cache_service
from app.runtime import runners as runners_module


# Import the GHT router after loading local configuration. Some of its imports
# instantiate settings, so importing it before ``load_dotenv()`` made the
# documented local startup command depend on callers manually sourcing `.env`.
import app.routers.ght as ght

from app.routers import (
    home, patients, dossiers, venues, mouvements, structure_hl7,
    endpoints, transport, transport_views, fhir_inbox, messages, interop,
    generate, structure, workflow, fhir_structure, vocabularies,
    health, scenarios, guide, docs, ihe, structure_select, validation, validation_rules,
    documentation, conformity, fhir_export, fhir_import, metrics, doc_wrapper,
    interface_testing, test_scenario_generator, ui_test_scenarios, tasks,
    hprim_interventions, hprim_acquittements, hprim_management, ngap, cotations, cotations_saisie,
    admission_wizard, location_cartography, contacts
)
from app.routers import menu

from app.routers import roundtrip_hprim
from app.routers import cotation_modern

from app.infrastructure.logging import setup_logging
from app.middleware.authentication import AuthenticationMiddleware

logger = logging.getLogger(__name__)


def _mount_sqladmin(application: FastAPI, database_engine, app_settings: Settings) -> None:
    """Monte SQLAdmin sur l'instance et le moteur qui lui appartiennent."""
    from sqladmin.authentication import AuthenticationBackend
    from app.auth import authenticate_user

    class SqlAdminAuthBackend(AuthenticationBackend):
        async def login(self, request: Request) -> bool:
            form = await request.form()
            user = authenticate_user(
                str(form.get("username", "")).strip(),
                str(form.get("password", "")),
                session_factory=application.state.session_factory,
            )
            if not user or "admin" not in user.roles:
                return False
            request.session["sqladmin_user"] = user.username
            return True

        async def logout(self, request: Request) -> bool:
            request.session.pop("sqladmin_user", None)
            return True

        async def authenticate(self, request: Request) -> bool:
            return bool(request.session.get("sqladmin_user"))

    admin = Admin(
        application,
        database_engine,
        base_url="/sqladmin",
        title="PAMélia - Admin SQL",
        templates_dir=os.path.join(os.path.dirname(__file__), "templates"),
        authentication_backend=SqlAdminAuthBackend(secret_key=app_settings.secret_key),
    )
    register_admin_views(admin)
    application.state.sqladmin = admin


def make_lifespan(
    runtime_settings: Settings,
    *,
    runtime_session_factory,
    mllp_manager: MLLPManager,
    scheduler: BackgroundScheduler,
):
    """Construit un cycle de vie lié à la configuration de cette application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # En tests, on ne veut pas initialiser la DB de production (medbridge.db) ni démarrer
        # des serveurs MLLP en arrière-plan. Les tests surchargent l'accès DB via
        # des overrides, on saute donc init/reload quand TESTING est présent ou PYTEST_RUNNING.
        import os
        PYTEST_RUNNING = "PYTEST_CURRENT_TEST" in os.environ
        testing = runtime_settings.testing or PYTEST_RUNNING
        if not testing:
            # Configure application handlers when the server actually starts.
            # Importing ``app.app`` must not replace handlers installed by a
            # caller such as Uvicorn, pytest or an embedding application.
            setup_logging()
            migrate_database(runtime_settings.database_url)
        # Provide the running asyncio loop to runners so synchronous handlers
        # can schedule coroutines safely using run_coroutine_threadsafe.
            try:
                loop = asyncio.get_running_loop()
                runners_module.set_event_loop(loop)
                logging.info("Main asyncio loop registered with runners module")
            except RuntimeError:
                logging.getLogger(__name__).warning("No running asyncio loop available to register with runners")
        # Register entity event listeners for automatic message emission
            register_entity_events()
            register_structure_entity_events()
            logging.info("Entity event listeners registered for automatic emission")
        # Démarrage idempotent
        # Use an explicit session context manager here instead of consuming
        # the dependency generator with next(get_session()). Calling
        # next(get_session()) leaves the generator open and can cause the
        # underlying context manager to never exit, producing transaction
        # state errors like 'cannot rollback - no transaction is active'.
            with runtime_session_factory() as sess:
            # Initialiser les vocabulaires si demandé
                if os.getenv("INIT_VOCAB", "0") in ("1", "true", "True"):
                    from app.vocabularies.init import init_vocabularies
                    init_vocabularies(sess)
                    logging.info("Vocabulaires initialisés")

            # Démarrer les serveurs MLLP pour tous les endpoints configurés
                await mllp_manager.reload_all(sess)
                logging.info("Serveurs MLLP démarrés")
        
        # Démarrer le scheduler pour le polling des endpoints FILE
        # Par défaut: 60 secondes (1 minute). Configurable via FILE_POLL_INTERVAL
            await scheduler.start()
            logging.info(
                "File endpoint polling started (interval: %ss)",
                runtime_settings.file_poll_interval,
            )

        try:
            yield
        finally:
            if not testing:
                await scheduler.stop()
                await mllp_manager.stop_all()
    return lifespan

def create_app(runtime_settings: Settings | None = None) -> FastAPI:
    """Crée une application indépendante à partir de réglages validés."""
    app_settings = runtime_settings or settings
    runtime_engine = engine if runtime_settings is None else create_database_engine(app_settings)
    runtime_session_factory = (
        default_session_factory
        if runtime_settings is None
        else make_session_factory(runtime_engine)
    )
    runtime_session_dependency = (
        database_session_dependency
        if runtime_settings is None
        else make_session_dependency(runtime_engine)
    )
    if app_settings.security_enabled:
        from app.auth import ensure_bootstrap_admin
        from sqlmodel import SQLModel
        SQLModel.metadata.create_all(runtime_engine)
        ensure_bootstrap_admin(runtime_session_factory, app_settings)
    mllp_manager = MLLPManager(
        session_factory=runtime_session_factory,
        on_message=on_message_inbound,
        testing=app_settings.testing,
    )
    scheduler = BackgroundScheduler(
        app_settings.file_poll_interval,
        session_factory_provider=runtime_session_factory,
        testing=app_settings.testing,
    )
    runtime_cache = create_cache_service(enabled=not app_settings.testing)
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        lifespan=make_lifespan(
            app_settings,
            runtime_session_factory=runtime_session_factory,
            mllp_manager=mllp_manager,
            scheduler=scheduler,
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        debug=app_settings.debug
    )
    # Une enveloppe JSON stable pour les erreurs HTTP, de validation et métier.
    # Elle est enregistrée avant les routes afin que tous les routeurs héritent
    # du même contrat.
    from app.utils.error_handling import register_exception_handlers
    register_exception_handlers(app)

    # Tous les routeurs existants continuent de référencer la dépendance
    # historique. Les overrides les relient au moteur propre à cette instance.
    app.dependency_overrides[database_session_dependency] = runtime_session_dependency
    app.dependency_overrides[compatibility_session_dependency] = runtime_session_dependency

    logger.info("\nFastAPI app initialization")

    # Un environnement partagé évite qu'un routeur oublie les filtres requis
    # par le layout ou les macros communes.
    from app.templates import templates
    app.state.templates = templates
    # Store version from settings
    app.state.version = app_settings.app_version
    app.state.settings = app_settings
    app.state.engine = runtime_engine
    app.state.session_factory = runtime_session_factory
    app.state.scheduler = scheduler
    app.state.cache = runtime_cache
    # Les tests utilisent un stockage éphémère de révocations car Redis y est
    # explicitement désactivé. En exécution sécurisée normale, Redis reste la
    # source durable et une indisponibilité fait refuser le token.
    app.state.token_blacklist = {} if app_settings.testing else None

    # Servir les fichiers statiques (CSS/JS)
    static_dir = str(Path(__file__).parent / "static")
    app.mount("/static", StaticFiles(directory=static_dir, html=True, check_dir=True), name="static")

    # Middlewares dans l'ordre d'exécution (dernier ajouté = premier exécuté)
    # 1. Error handling (en dernier pour capturer toutes les erreurs)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(AuthenticationMiddleware)

    # 2. Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # 3. Metrics collection (avant les autres pour capturer toutes les requêtes)
    app.add_middleware(MetricsMiddleware)

    # 4. Flash messages
    app.add_middleware(FlashMessageMiddleware)

    # 4. GHT context
    app.add_middleware(GHTContextMiddleware)

    # 5. Version middleware
    app.add_middleware(VersionMiddleware)

    session_secret = app_settings.secret_key
    if not session_secret or session_secret == "change-me-in-production":
        session_secret = secrets.token_urlsafe(32)
        logging.getLogger(__name__).warning(
            "SECRET_KEY non défini ou par défaut - utilisation d'un secret éphémère pour cette instance"
        )
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        same_site="lax",
        https_only=app_settings.security_enabled,
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        security_enabled=app_settings.security_enabled,
    )

    # exposer le manager aux routeurs
    app.state.mllp_manager = mllp_manager

    # REMARQUE: admin interface (SQLAdmin) will be created after route
    # registration to avoid catching /admin/* routes before our own
    # admin-related pages (like /admin/ght). The Admin instance is
    # created later just before returning the app.

    _register_application_routes(
        app,
        app_settings=app_settings,
        runtime_engine=runtime_engine,
        runtime_session_factory=runtime_session_factory,
        mllp_manager=mllp_manager,
        scheduler=scheduler,
    )

    return app


def _register_application_routes(
    app: FastAPI,
    *,
    app_settings: Settings,
    runtime_engine,
    runtime_session_factory,
    mllp_manager: MLLPManager,
    scheduler: BackgroundScheduler,
) -> None:
    """Monte les routes et capacités optionnelles sur une instance déjà configurée."""
    # Core application routes in dependency order
    # Routes are registered in logical dependency order
    # Some routers have their own prefix defined in their router creation

    # System routes (health check, metrics)
    from fastapi import HTTPException
    from sqlalchemy import text

    @app.get("/health")
    def health_check():
        """Health check endpoint for load balancers and monitoring"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Test database connection
            with runtime_session_factory() as health_session:
                health_session.execute(text("SELECT 1"))
            db_health = {
                "status": "healthy",
                "database_type": runtime_engine.dialect.name,
            }

            # Test cache
            cache_stats = app.state.cache.get_stats()

            return {
                "status": "healthy",
                "version": app.state.version,
                "database": db_health,
                "cache": cache_stats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

    @app.get("/health/db")
    def database_health():
        """Detailed database health check for the configured SQL backend."""
        try:
            # ``session_factory`` returns a synchronous SQLModel session.  The
            # previous async context manager made this probe fail systematically
            # (``__aenter__``) on the default SQLite deployment.
            with runtime_session_factory() as session:
                if runtime_engine.dialect.name == "sqlite":
                    result = session.execute(text("SELECT sqlite_version()"))
                    database_type = "sqlite"
                else:
                    result = session.execute(text("SELECT version()"))
                    database_type = runtime_engine.dialect.name
                version = result.scalar()

            return {
                "status": "healthy",
                "database_type": database_type,
                "version": version,
                "connection_pool": runtime_engine.pool.status(),
            }
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database unhealthy: {str(e)}")

    @app.get("/ready")
    def readiness_check():
        """Vérifie les dépendances nécessaires avant de recevoir du trafic."""
        try:
            with runtime_session_factory() as ready_session:
                ready_session.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={"status": "not_ready", "database": str(exc)},
            ) from exc

        scheduler_ready = app_settings.testing or scheduler.running
        if not scheduler_ready:
            raise HTTPException(
                status_code=503,
                detail={"status": "not_ready", "scheduler": "stopped"},
            )
        return {
            "status": "ready",
            "database": runtime_engine.dialect.name,
            "scheduler": "disabled-for-tests" if app_settings.testing else "running",
            "mllp_listeners": len(mllp_manager.running_ids()),
        }

    @app.get("/metrics")
    async def metrics_endpoint():
        """Métriques de performance et monitoring au format JSON"""
        from app.metrics import metrics
        return metrics.get_metrics()

    # Prometheus exposition format (text/plain; version=0.0.4)
    try:
        from fastapi.responses import Response
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

        @app.get("/metrics/prom")
        async def metrics_prometheus():
            """Exposition des métriques Prometheus (scrape)."""
            content = generate_latest()  # default registry
            return Response(content=content, media_type=CONTENT_TYPE_LATEST)
    except Exception as exc:
        # If prometheus_client isn't installed, skip this endpoint
        logger.debug("Prometheus endpoint not registered", exc_info=exc)

    # System routes - Tasks API
    app.include_router(tasks.router)
    logger.info(" - Tasks API router mounted at /api/tasks")

    # System Health API
    from app.api import system_health
    app.include_router(system_health.router)
    logger.info(" - System Health API router mounted at /api")

    logger.info("\nRegistering routes:")

    # 1. Basic UI routes
    
    # 1. Basic UI routes 
    app.include_router(home.router)
    logger.info(" - Home router mounted at /")
    
    # 2. Entity and core data routes - all have their own prefixes
    app.include_router(patients.router)
    app.include_router(dossiers.router)
    app.include_router(dossiers.public_router)
    app.include_router(dossiers.api_router)
    app.include_router(venues.router)
    app.include_router(mouvements.router)
    app.include_router(contacts.router)
    logger.info(" - Core entity routers mounted with their prefixes")

    # Register AJAX endpoints for mouvements (no GHT dependency)
    app.include_router(mouvements.ajax_router)
    logger.info(" - Mouvements AJAX router mounted at /mouvements/api")
    
    # API endpoints for dynamic form field loading
    from app.routers import api_structure
    app.include_router(api_structure.router)
    logger.info(" - API Structure router mounted at /api/mouvements")
    
    # 2b. Timeline views
    from app.routers import timeline
    app.include_router(timeline.router)
    logger.info(" - Timeline router mounted")
    
    # 3. Structure management
    app.include_router(structure.redirect_router)  # Redirections singulier->pluriel (AVANT le router principal)
    app.include_router(structure.api_router)  # Has prefix /api/structure
    app.include_router(structure.router)  # Main structure dashboard at /structure
    app.include_router(structure_hl7.router)  # Has prefix /structure (legacy MFN helpers)
    app.include_router(fhir_structure.router)  # Has prefix /fhir
    app.include_router(structure_select.router)  # Has prefix /structure
    logger.info(" - Structure routers mounted")
    
    # 3b. Analytics (Mode Gestionnaire)
    from app.routers import analytics
    app.include_router(analytics.router)
    app.include_router(analytics.ui_router)
    logger.info(" - Analytics routers mounted at /api/analytics and /structure/analytics")
    
    # 3c. Alert Configuration (Mode Gestionnaire)
    from app.routers import alert_config
    app.include_router(alert_config.router)
    app.include_router(alert_config.ui_router)
    logger.info(" - Alert config routers mounted at /api/alert-config and /structure/alert-config")
    
    # 3d. Export Analytics (Mode Gestionnaire)
    from app.routers import export_analytics
    app.include_router(export_analytics.router)
    logger.info(" - Export analytics router mounted at /api/analytics/export")
    
    # 3e. Design System Demo (Phase 5.2)
    from app.routers import design_system
    app.include_router(design_system.router)
    logger.info(" - Design System demo mounted at /design-system")
    
    # 3f. Structure Search Interface (Phase 5.3)
    from app.routers import structure_search
    app.include_router(structure_search.router)
    logger.info(" - Structure Search interface mounted at /structure/search")
    
    # 3e. Import/Export Structure Excel
    from app.routers import structure_import_export
    app.include_router(structure_import_export.router)
    app.include_router(structure_import_export.ui_router)
    logger.info(" - Structure import/export routers mounted at /api/structure/export and /structure/import")
    
    # 3f. Structure Interactive (Phase 5 - Édition inline & drag-drop)
    from app.routers import structure_interactive
    app.include_router(structure_interactive.router)
    app.include_router(structure_interactive.ui_router)
    logger.info(" - Structure interactive router mounted at /api/structure (PATCH, POST /move) and /structure/interactive")
    
    # 4. Admin interfaces (mount under /admin so templates/redirects using
    # /admin/ght work as expected)
    from app.routers import admin_gateway
    app.include_router(admin_gateway.router)
    app.include_router(ght.router, prefix="/admin/ght")
    # Les sub-routers sont inclus dans ght.py, on ne les inclut pas directement ici
    logger.info(" - Admin routers mounted under /admin/ght")
    
    # 5. Integration and transport
    app.include_router(messages.router)
    from app.routers import outbox
    app.include_router(outbox.router)
    app.include_router(fhir_inbox.router)
    app.include_router(transport_views.router, prefix="/transport")
    app.include_router(transport.router)  # Has own prefix
    app.include_router(endpoints.router)  # Has own prefix
    app.include_router(ihe.router)  # Has own prefix /ihe
    
    # HPRIM CCAM integration (stub router)
    try:
        from app.routers import ccam
        from app.api import ccam as ccam_api
        from app.api import hprim_ccam
        from app.api import hprim_messages as hprim_messages_api
        app.include_router(ccam.router)
        app.include_router(ccam_api.router)
        app.include_router(hprim_ccam.router)
        app.include_router(hprim_messages_api.router)
        logger.info(" - HPRIM CCAM router mounted at /ccam")
        logger.info(" - HPRIM CCAM API router mounted at /api/hprim/actes/ccam")
        logger.info(" - HPRIM Messages API router mounted at /api/hprim/messages")
    except Exception as e:
        raise RuntimeError("Required HPRIM CCAM capability failed to load") from e
    
    
    # HPRIM UCD router
    try:
        from app.api import hprim_ngap
        from app.api import ucd
        from app.routers import ucd as ucd_router
        app.include_router(hprim_ngap.router)
        app.include_router(ucd.router)
        app.include_router(ucd_router.router)
        logger.info(" - HPRIM NGAP router mounted at /api/hprim/actes/ngap")
        logger.info(" - HPRIM UCD routers mounted")
    except Exception as e:
        raise RuntimeError("Required HPRIM NGAP/UCD capability failed to load") from e
    
    # HPRIM LPP router
    try:
        from app.api import lpp
        from app.routers import lpp as lpp_router
        app.include_router(lpp.router)
        app.include_router(lpp_router.router)
        logger.info(" - HPRIM LPP routers mounted")
    except Exception as e:
        raise RuntimeError("Required HPRIM LPP capability failed to load") from e
    
    # HPRIM Interventions & Cotations router
    try:
        app.include_router(hprim_interventions.router)
        logger.info(" - HPRIM Interventions router mounted at /api/hprim/interventions")
    except Exception as e:
        raise RuntimeError("Required HPRIM interventions capability failed to load") from e
    
    # HPRIM Acquittements router
    try:
        app.include_router(hprim_acquittements.router)
        logger.info(" - HPRIM Acquittements router mounted at /api/hprim/acquittements")
    except Exception as e:
        raise RuntimeError("Required HPRIM acknowledgements capability failed to load") from e
    
    # HPRIM Management router (import, dashboard, etc.)
    try:
        app.include_router(hprim_management.router)
        logger.info(" - HPRIM Management router mounted at /hprim")
    except Exception as e:
        raise RuntimeError("Required HPRIM management capability failed to load") from e
    
    # NGAP router (nursing acts)
    try:
        from app.api import ngap as ngap_api
        app.include_router(ngap.router)
        app.include_router(ngap_api.router)
        logger.info(" - NGAP router mounted at /ngap")
    except Exception as e:
        raise RuntimeError("Required NGAP capability failed to load") from e

    # Contrats de prise en charge : API et interface partagent le même domaine.
    try:
        from app.api import contracts as contracts_api
        from app.routers import contracts as contracts_router
        app.include_router(contracts_api.router)
        app.include_router(contracts_router.router)
        logger.info(" - Contracts routers mounted at /api/contracts and /contracts")
    except Exception as e:
        raise RuntimeError("Required contracts capability failed to load") from e
    
    # Cotations routers (vue liste + saisie rapide)
    try:
        app.include_router(cotations.router)
        app.include_router(cotations_saisie.router)
        logger.info(" - Cotations routers mounted:")
        logger.info("   • /dossiers/{id}/cotations (liste)")
        logger.info("   • /cotations/dossier/{id}/saisie (saisie rapide)")
    except Exception as e:
        raise RuntimeError("Required cotations capability failed to load") from e
    
    # REST APIs pour gestion patients et dossiers
    try:
        from app.api import patients as patients_api
        from app.api import dossiers as dossiers_api
        app.include_router(patients_api.router)
        app.include_router(dossiers_api.router)
        logger.info(" - REST APIs Patients & Dossiers mounted at /api/patients and /api/dossiers")
    except Exception as e:
        raise RuntimeError("Required patients/dossiers API capability failed to load") from e
    
    # Roundtrip HPRIM router
    app.include_router(roundtrip_hprim.router)
    logger.info(" - Roundtrip HPRIM router mounted at /roundtrip-hprim")
    
    # HPRIM messages cotation router (visualisation et import des actes)
    try:
        from app.routers import hprim_messages
        app.include_router(hprim_messages.router)
        logger.info(" - HPRIM messages cotation router mounted at /hprim-cotation")
    except Exception as e:
        raise RuntimeError("Required HPRIM messages capability failed to load") from e
    
    # Nouvelle IHM Cotation moderne (UX/UI pro)
    app.include_router(cotation_modern.router, prefix="/cotation-modern")
    try:
        from app.routers import cotation_selector
        app.include_router(cotation_selector.router)
        logger.info(" - Cotation selector router mounted at /cotation-modern/select")
    except Exception as e:
        raise RuntimeError("Required cotation selector capability failed to load") from e
    logger.info(" - Cotation moderne router mounted at /cotation-modern")
    
    logger.info(" - Integration routers mounted")
    
    # 6. Utilities and workflow
    app.include_router(workflow.router)
    app.include_router(admission_wizard.router)  # Multi-step admission wizard
    app.include_router(location_cartography.router)  # Location hierarchy API
    app.include_router(generate.router)
    app.include_router(interop.router)
    app.include_router(vocabularies.router)
    app.include_router(validation.router)  # Validation hors contexte
    app.include_router(validation_rules.router)
    app.include_router(validation_rules.ui_router)
    app.include_router(documentation.router)  # Documentation
    app.include_router(conformity.router)  # Conformité par EJ
    app.include_router(menu.router)  # Dynamic menu mapping page
    app.include_router(interface_testing.router)  # Tests d'interfaces GAM/GAP
    app.include_router(interface_testing.ui_router)  # UI des tests d'interfaces
    app.include_router(test_scenario_generator.router)  # API générateur de scénarios
    app.include_router(ui_test_scenarios.router)  # UI générateur de scénarios
    logger.info(" - Validation and conformity routers mounted")
    # Context management (patient/dossier quick set/clear)
    try:
        from app.routers import context
        app.include_router(context.router, prefix="/context", tags=["context"])
        logger.info(" - Context router mounted")
    except Exception as e:
        raise RuntimeError("Required context capability failed to load") from e
    app.include_router(guide.router)
    app.include_router(docs.router)
    app.include_router(doc_wrapper.router)  # Wrapper pour docs HTML statiques
    
    # Scenario templates (contextualisables) - AVANT scenarios pour éviter conflit de routes
    try:
        from app.routers import scenario_templates
        app.include_router(scenario_templates.router)
        logger.info(" - Scenario templates router mounted")
    except Exception as e:
        raise RuntimeError("Required scenario templates capability failed to load") from e
    
    # Configuration des scénarios par EJ - AVANT scenarios pour éviter conflit de routes
    try:
        from app.routers import scenario_ej_config
        app.include_router(scenario_ej_config.router)
        logger.info(" - Scenario EJ config router mounted")
    except Exception as e:
        raise RuntimeError("Required scenario EJ capability failed to load") from e
    try:
        from app.routers import scenario_target_profiles
        app.include_router(scenario_target_profiles.router)
        logger.info(" - Scenario target profiles router mounted")
    except Exception as e:
        raise RuntimeError("Required scenario target profiles capability failed to load") from e
    
    app.include_router(scenarios.router)
    
    logger.info(" - Utility routers mounted")
    
    # 7. Cache management
    from app.routers import cache
    app.include_router(cache.router, prefix="/api")
    logger.info(" - Cache router mounted at /api/cache")
    
    # 8. Import endpoints for test Exemple
    from app.routers import import_examples
    app.include_router(import_examples.router)
    logger.info(" - Import examples router mounted at /import")
    
    if app_settings.security_enabled:
        from app.routers import auth
        app.include_router(auth.router)
        logger.info(" - Authentication router mounted")

        from app.routers import admin_protected
        app.include_router(admin_protected.router)
        logger.info(" - Protected admin router mounted at /api/admin")
    else:
        logger.info(" - Authentication disabled (local network mode)")
    
    # 8. FHIR API endpoints
    app.include_router(fhir_export.router)
    app.include_router(fhir_import.router)
    app.include_router(metrics.router)
    app.include_router(metrics.ui_router)
    logger.info(" - FHIR API routers mounted")
    logger.info(" - Metrics UI router mounted at /metrics")

    # 11. Monitoring dashboard (UI)
    try:
        from fastapi import Request
        from fastapi.responses import HTMLResponse
        from fastapi import APIRouter
        from app.templates import templates
        dashboard_router = APIRouter()

        @dashboard_router.get("/dashboard", response_class=HTMLResponse, tags=["Monitoring"])
        async def dashboard(request: Request):
            return templates.TemplateResponse(request, "dashboard.html")

        @dashboard_router.get("/cache-dashboard", response_class=HTMLResponse, tags=["Monitoring"])
        async def cache_dashboard(request: Request):
            return templates.TemplateResponse(request, "cache_dashboard.html")

        app.include_router(dashboard_router)
        logger.info(" - Monitoring dashboard mounted at /dashboard")
    except Exception as e:
        raise RuntimeError("Required monitoring dashboard capability failed to load") from e
    
    # 9. Lightweight health/version helpers
    app.include_router(health.router)
    logger.info(" - Health/version helpers mounted")
    
    # 10. Debug endpoints: available only in development and tests. They create
    # durable data and must not be exposed by a normal runtime configuration.
    if app_settings.debug or app_settings.testing:
        try:
            from app.routers import debug_events
            app.include_router(debug_events.router)
            logger.info(" - Debug router mounted at /debug")
        except Exception as e:
            logging.getLogger(__name__).warning(f"Debug router not available: {e}")
    
    logger.info("All routes registered.")

    if not app_settings.testing and app_settings.security_enabled:
        _mount_sqladmin(app, runtime_engine, app_settings)
        logger.info("SQLAdmin interface initialized at /sqladmin")
    

app = create_app()

logger.info(f"Application ready with {len(app.routes)} routes")
