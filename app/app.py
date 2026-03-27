# Import ght router first to avoid circular imports
import app.routers.ght as ght
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

import logging, os, secrets

# Charger les variables d'environnement depuis .env
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, APIRouter
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqladmin import Admin, ModelView
from sqlmodel import select

# Import de la configuration centralisée
from config.settings import settings

from app.middleware.flash import FlashMessageMiddleware
from app.middleware.ght_context import GHTContextMiddleware
from app.middleware.version import VersionMiddleware
from app.middleware.error_handler import ErrorHandlingMiddleware, RequestLoggingMiddleware
from app.metrics import MetricsMiddleware

from app.db import init_db, engine, get_session
from app import models_scenarios  # ensure scenario models are registered
from app.admin import register_admin_views  # SQLAdmin views
from app.db_session_factory import session_factory
from app.services.transport_inbound import on_message_inbound
from app.services.mllp_manager import MLLPManager
from app.services.entity_events import register_entity_events
from app.services.entity_events_structure import register_structure_entity_events
from app.services.scheduler import start_scheduler, stop_scheduler
import asyncio
from app import runners as runners_module


# Import ght router first to avoid circular imports
import app.routers.ght as ght

"""Application composition module.

NOTE (Fallback Router Removal): The previous temporary fallback router
`ght_ej_fallback` guaranteeing `/admin/ght/{context_id}/ej/{ej_id}` has been
removed now that the main `ght` router consistently loads all routes after the
import/reload bugfix sequence. If future partial-load regressions occur, prefer
modularizing `app/routers/ght.py` instead of reintroducing a fallback.
"""

from app.routers import (
    home, patients, dossiers, venues, mouvements, structure_hl7,
    endpoints, transport, transport_views, fhir_inbox, messages, interop,
    generate, structure, workflow, fhir_structure, vocabularies,
    health, scenarios, guide, docs, ihe, dossier_type, structure_select, validation,
    documentation, conformity, fhir_export, fhir_import, metrics, auth, doc_wrapper,
    interface_testing, test_scenario_generator, ui_test_scenarios, ccam, ucd, lpp, tasks,
    hprim_interventions, hprim_acquittements, hprim_management, ngap, cotations, cotations_saisie
)
from app.routers import menu

from app.routers.ght.ej import router as ej_router
from app.routers.ght.structure import router as structure_router
from app.routers import roundtrip_hprim
from app.routers import cotation_modern


# --- PATCH: Logging to file and console, DEBUG level ---
from app.logging_config import setup_logging
setup_logging()

# Instance unique du manager et publication via app.state
# - `session_factory` fournit des sessions DB courtes et sûres côté workers.
# - `on_message_inbound` est appelé pour chaque message entrant HL7.
mllp_manager = MLLPManager(session_factory=session_factory, on_message=on_message_inbound)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # En tests, on ne veut pas initialiser la DB de production (medbridge.db) ni démarrer
    # des serveurs MLLP en arrière-plan. Les tests surchargent l'accès DB via
    # des overrides, on saute donc init/reload quand TESTING est présent ou PYTEST_RUNNING.
    import os
    PYTEST_RUNNING = "PYTEST_CURRENT_TEST" in os.environ
    testing = settings.testing or PYTEST_RUNNING
    if not testing:
        init_db()
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
        with session_factory() as sess:
            # Initialiser les vocabulaires si demandé
            if os.getenv("INIT_VOCAB", "0") in ("1", "true", "True"):
                from app.vocabularies.init import init_vocabularies
                init_scenario = False
                try:
                    init_vocabularies(sess)
                    logging.info("Vocabulaires initialisés")
                except Exception as e:
                    logging.error(f"Erreur initialisation vocabulaires: {e}")

            # Démarrer les serveurs MLLP pour tous les endpoints configurés
            try:
                await mllp_manager.reload_all(sess)
                logging.info("Serveurs MLLP démarrés")
            except Exception as e:
                logging.error(f"Erreur lors du démarrage des serveurs MLLP: {e}")
                logging.warning("L'application continue sans les serveurs MLLP")
        
        # Démarrer le scheduler pour le polling des endpoints FILE
        # Par défaut: 60 secondes (1 minute). Configurable via FILE_POLL_INTERVAL
        poll_interval = settings.file_poll_interval
        await start_scheduler(poll_interval)
        logging.info(f"File endpoint polling started (interval: {poll_interval}s)")

    try:
        yield
    finally:
        if not testing:
            await stop_scheduler()
            await mllp_manager.stop_all()

from app.version import get_version

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        debug=settings.debug
    )

    print("\nFastAPI app initialization")

    # Filtre Jinja2 global pour masquer None ou 'None' par '—'
    def none_to_dash(value):
        if value is None or value == "None":
            return "—"
        return value
    
    # Filtre Jinja2 pour convertir les caractères de retour à la ligne en sauts de ligne visibles
    def format_hl7_payload(value):
        """Convertit les caractères \r, \n et \r\n en véritables sauts de ligne HTML"""
        if not isinstance(value, str):
            return value
        # Remplacer \r\n par \n d'abord (pour éviter double conversion)
        value = value.replace('\r\n', '\n')
        # Remplacer \r seul par \n
        value = value.replace('\r', '\n')
        # Les sauts de ligne seront préservés par whitespace-pre-wrap en CSS
        return value
    
    # Ajout des filtres au moteur de templates Jinja2
    from fastapi.templating import Jinja2Templates
    templates_dir = str(Path(__file__).parent / "templates")
    templates = Jinja2Templates(directory=templates_dir)
    templates.env.filters["none_to_dash"] = none_to_dash
    templates.env.filters["format_hl7_payload"] = format_hl7_payload
    # Stocker dans app.state pour accès dans les routes si besoin
    app.state.templates = templates
    # Store version from settings
    app.state.version = settings.app_version

    # Servir les fichiers statiques (CSS/JS)
    static_dir = str(Path(__file__).parent / "static")
    app.mount("/static", StaticFiles(directory=static_dir, html=True, check_dir=True), name="static")

    # Middlewares dans l'ordre d'exécution (dernier ajouté = premier exécuté)
    # 1. Error handling (en dernier pour capturer toutes les erreurs)
    app.add_middleware(ErrorHandlingMiddleware)

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

    session_secret = settings.secret_key
    if not session_secret or session_secret == "change-me-in-production":
        session_secret = secrets.token_urlsafe(32)
        logging.getLogger(__name__).warning(
            "SECRET_KEY non défini ou par défaut - utilisation d'un secret éphémère pour cette instance"
        )
    app.add_middleware(SessionMiddleware, secret_key=session_secret)

    # exposer le manager aux routeurs
    app.state.mllp_manager = mllp_manager

    # REMARQUE: admin interface (SQLAdmin) will be created after route
    # registration to avoid catching /admin/* routes before our own
    # admin-related pages (like /admin/ght). The Admin instance is
    # created later just before returning the app.

    # Core application routes in dependency order
    # Routes are registered in logical dependency order
    # Some routers have their own prefix defined in their router creation

    # System routes (health check, metrics)
    from fastapi import HTTPException
    from sqlalchemy import text

    @app.get("/health")
    async def health_check():
        """Health check endpoint for load balancers and monitoring"""
        from app.db import get_db_health
        from app.services.cache_service import get_cache_service
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Test database connection
            db_health = get_db_health()
            if db_health.get("status") != "healthy":
                raise Exception(f"Database unhealthy: {db_health}")

            # Test cache
            cache = get_cache_service()
            cache_stats = cache.get_stats()

            return {
                "status": "healthy",
                "version": app.state.version,
                "database": db_health,
                "cache": cache_stats,
                "timestamp": "2025-12-27T00:00:00Z"
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

    @app.get("/health/db")
    async def database_health():
        """Detailed database health check"""
        try:
            async with session_factory() as session:
                result = await session.execute(text("SELECT version()"))
                version = result.scalar()

            return {
                "status": "healthy",
                "database_type": "postgresql",
                "version": version,
                "connection_pool": "active"
            }
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database unhealthy: {str(e)}")

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
    except Exception:
        # If prometheus_client isn't installed, skip this endpoint
        pass

    # System routes - Tasks API
    app.include_router(tasks.router)
    print(" - Tasks API router mounted at /api/tasks")

    # System Health API
    from app.api import system_health
    app.include_router(system_health.router)
    print(" - System Health API router mounted at /api")

    print("\nRegistering routes:")

    # 1. Basic UI routes
    
    # 1. Basic UI routes 
    app.include_router(home.router)
    print(" - Home router mounted at /")
    
    # 2. Entity and core data routes - all have their own prefixes
    app.include_router(patients.router)
    app.include_router(dossiers.router)
    app.include_router(dossiers.public_router)
    app.include_router(dossiers.api_router)
    app.include_router(venues.router)
    app.include_router(mouvements.router)
    print(" - Core entity routers mounted with their prefixes")

    # Register AJAX endpoints for mouvements (no GHT dependency)
    app.include_router(mouvements.ajax_router)
    print(" - Mouvements AJAX router mounted at /mouvements/api")
    
    # API endpoints for dynamic form field loading
    from app.routers import api_structure
    app.include_router(api_structure.router)
    print(" - API Structure router mounted at /api/mouvements")
    
    # 2b. Timeline views
    from app.routers import timeline
    app.include_router(timeline.router)
    print(" - Timeline router mounted")
    
    # 3. Structure management
    app.include_router(structure.redirect_router)  # Redirections singulier->pluriel (AVANT le router principal)
    app.include_router(structure.api_router)  # Has prefix /api/structure
    app.include_router(structure.router)  # Main structure dashboard at /structure
    app.include_router(structure_hl7.router)  # Has prefix /structure
    app.include_router(fhir_structure.router)  # Has prefix /fhir
    app.include_router(structure_select.router)  # Has prefix /structure
    print(" - Structure routers mounted")
    
    # 3b. Analytics (Mode Gestionnaire)
    from app.routers import analytics
    app.include_router(analytics.router)
    app.include_router(analytics.ui_router)
    print(" - Analytics routers mounted at /api/analytics and /structure/analytics")
    
    # 3c. Alert Configuration (Mode Gestionnaire)
    from app.routers import alert_config
    app.include_router(alert_config.router)
    app.include_router(alert_config.ui_router)
    print(" - Alert config routers mounted at /api/alert-config and /structure/alert-config")
    
    # 3d. Export Analytics (Mode Gestionnaire)
    from app.routers import export_analytics
    app.include_router(export_analytics.router)
    print(" - Export analytics router mounted at /api/analytics/export")
    
    # 3e. Design System Demo (Phase 5.2)
    from app.routers import design_system
    app.include_router(design_system.router)
    print(" - Design System demo mounted at /design-system")
    
    # 3f. Structure Search Interface (Phase 5.3)
    from app.routers import structure_search
    app.include_router(structure_search.router)
    print(" - Structure Search interface mounted at /structure/search")
    
    # 3e. Import/Export Structure Excel
    from app.routers import structure_import_export
    app.include_router(structure_import_export.router)
    app.include_router(structure_import_export.ui_router)
    print(" - Structure import/export routers mounted at /api/structure/export and /structure/import")
    
    # 3f. Structure Interactive (Phase 5 - Édition inline & drag-drop)
    from app.routers import structure_interactive
    app.include_router(structure_interactive.router)
    app.include_router(structure_interactive.ui_router)
    print(" - Structure interactive router mounted at /api/structure (PATCH, POST /move) and /structure/interactive")
    
    # 4. Admin interfaces (mount under /admin so templates/redirects using
    # /admin/ght work as expected)
    from app.routers import admin_gateway
    app.include_router(admin_gateway.router)
    app.include_router(ght.router, prefix="/admin/ght")
    # Les sub-routers sont inclus dans ght.py, on ne les inclut pas directement ici
    print(" - Admin routers mounted under /admin/ght")
    
    # 5. Integration and transport
    app.include_router(messages.router)
    app.include_router(fhir_inbox.router)
    app.include_router(transport_views.router, prefix="/transport")
    app.include_router(transport.router)  # Has own prefix
    app.include_router(endpoints.router)  # Has own prefix
    app.include_router(ihe.router)  # Has own prefix /ihe
    
    # HPRIM CCAM integration (stub router)
    try:
        from app.routers import ccam
        app.include_router(ccam.router)
        print(" - HPRIM CCAM router mounted at /ccam")
    except Exception as e:
        logging.getLogger(__name__).warning(f"HPRIM CCAM router not available: {e}")
    
    
    # HPRIM UCD router
    try:
        from app.api import ucd
        from app.routers import ucd as ucd_router
        app.include_router(ucd.router)
        app.include_router(ucd_router.router)
        print(" - HPRIM UCD routers mounted")
    except Exception as e:
        logging.getLogger(__name__).warning(f"HPRIM UCD routers not available: {e}")
    
    # HPRIM LPP router
    try:
        from app.api import lpp
        from app.routers import lpp as lpp_router
        app.include_router(lpp.router)
        app.include_router(lpp_router.router)
        print(" - HPRIM LPP routers mounted")
    except Exception as e:
        logging.getLogger(__name__).warning(f"HPRIM LPP routers not available: {e}")
    
    # HPRIM Interventions & Cotations router
    try:
        app.include_router(hprim_interventions.router)
        print(" - HPRIM Interventions router mounted at /api/hprim/interventions")
    except Exception as e:
        logging.getLogger(__name__).warning(f"HPRIM Interventions router not available: {e}")
    
    # HPRIM Acquittements router
    try:
        app.include_router(hprim_acquittements.router)
        print(" - HPRIM Acquittements router mounted at /api/hprim/acquittements")
    except Exception as e:
        logging.getLogger(__name__).warning(f"HPRIM Acquittements router not available: {e}")
    
    # HPRIM Management router (import, dashboard, etc.)
    try:
        app.include_router(hprim_management.router)
        print(" - HPRIM Management router mounted at /hprim")
    except Exception as e:
        logging.getLogger(__name__).warning(f"HPRIM Management router not available: {e}")
    
    # NGAP router (nursing acts)
    try:
        app.include_router(ngap.router)
        print(" - NGAP router mounted at /ngap")
    except Exception as e:
        logging.getLogger(__name__).warning(f"NGAP router not available: {e}")
    
    # Cotations routers (vue liste + saisie rapide)
    try:
        app.include_router(cotations.router)
        app.include_router(cotations_saisie.router)
        print(" - Cotations routers mounted:")
        print("   • /dossiers/{id}/cotations (liste)")
        print("   • /cotations/dossier/{id}/saisie (saisie rapide)")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Cotations routers not available: {e}")
    
    # REST APIs pour gestion patients et dossiers
    try:
        from app.api import patients as patients_api
        from app.api import dossiers as dossiers_api
        app.include_router(patients_api.router)
        app.include_router(dossiers_api.router)
        print(" - REST APIs Patients & Dossiers mounted at /api/patients and /api/dossiers")
    except Exception as e:
        logging.getLogger(__name__).warning(f"REST APIs Patients/Dossiers not available: {e}")
    
    # Roundtrip HPRIM router
    app.include_router(roundtrip_hprim.router)
    print(" - Roundtrip HPRIM router mounted at /roundtrip-hprim")
    
    # HPRIM messages cotation router (visualisation et import des actes)
    try:
        from app.routers import hprim_messages
        app.include_router(hprim_messages.router)
        print(" - HPRIM messages cotation router mounted at /hprim-cotation")
    except Exception as e:
        logging.getLogger(__name__).warning(f"HPRIM messages cotation router not available: {e}")
    
    # Nouvelle IHM Cotation moderne (UX/UI pro)
    app.include_router(cotation_modern.router, prefix="/cotation-modern")
    try:
        from app.routers import cotation_selector
        app.include_router(cotation_selector.router)
        print(" - Cotation selector router mounted at /cotation-modern/select")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Cotation selector router not available: {e}")
    print(" - Cotation moderne router mounted at /cotation-modern")
    
    print(" - Integration routers mounted")
    
    # 6. Utilities and workflow
    app.include_router(workflow.router)
    app.include_router(generate.router)
    app.include_router(interop.router)
    app.include_router(vocabularies.router)
    app.include_router(validation.router)  # Validation hors contexte
    app.include_router(documentation.router)  # Documentation
    app.include_router(conformity.router)  # Conformité par EJ
    app.include_router(menu.router)  # Dynamic menu mapping page
    app.include_router(interface_testing.router)  # Tests d'interfaces GAM/GAP
    app.include_router(interface_testing.ui_router)  # UI des tests d'interfaces
    app.include_router(test_scenario_generator.router)  # API générateur de scénarios
    app.include_router(ui_test_scenarios.router)  # UI générateur de scénarios
    print(" - Validation and conformity routers mounted")
    # Context management (patient/dossier quick set/clear)
    try:
        from app.routers import context
        app.include_router(context.router, prefix="/context", tags=["context"])
        print(" - Context router mounted")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Context router not available: {e}")
    app.include_router(guide.router)
    app.include_router(docs.router)
    app.include_router(doc_wrapper.router)  # Wrapper pour docs HTML statiques
    
    # Scenario templates (contextualisables) - AVANT scenarios pour éviter conflit de routes
    try:
        from app.routers import scenario_templates
        app.include_router(scenario_templates.router)
        print(" - Scenario templates router mounted")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Scenario templates router not available: {e}")
    
    # Configuration des scénarios par EJ - AVANT scenarios pour éviter conflit de routes
    try:
        from app.routers import scenario_ej_config
        app.include_router(scenario_ej_config.router)
        print(" - Scenario EJ config router mounted")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Scenario EJ config router not available: {e}")
    
    app.include_router(scenarios.router)
    
    print(" - Utility routers mounted")
    
    # 7. Cache management
    from app.routers import cache
    app.include_router(cache.router, prefix="/api")
    print(" - Cache router mounted at /api/cache")
    
    # 7.1. Tasks API
    from app.routers import tasks as tasks_router
    app.include_router(tasks_router.router)
    print(" - Tasks API router mounted at /api/tasks")
    
    # 8. Import endpoints for test Exemple
    from app.routers import import_examples
    app.include_router(import_examples.router)
    print(" - Import examples router mounted at /import")
    
    # 7. Authentication
    app.include_router(auth.router)
    print(" - Authentication router mounted")
    
    # 7.1. Protected admin endpoints
    from app.routers import admin_protected
    app.include_router(admin_protected.router)
    print(" - Protected admin router mounted at /api/admin")
    
    # 8. FHIR API endpoints
    app.include_router(fhir_export.router)
    app.include_router(fhir_import.router)
    app.include_router(metrics.router)
    app.include_router(metrics.ui_router)
    print(" - FHIR API routers mounted")
    print(" - Metrics UI router mounted at /metrics")

    # 11. Monitoring dashboard (UI)
    try:
        from fastapi import Request
        from fastapi.responses import HTMLResponse
        from fastapi import APIRouter
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="app/templates")
        dashboard_router = APIRouter()

        @dashboard_router.get("/dashboard", response_class=HTMLResponse, tags=["Monitoring"])
        async def dashboard(request: Request):
            return templates.TemplateResponse(request, "dashboard.html")

        @dashboard_router.get("/cache-dashboard", response_class=HTMLResponse, tags=["Monitoring"])
        async def cache_dashboard(request: Request):
            return templates.TemplateResponse(request, "cache_dashboard.html")

        app.include_router(dashboard_router)
        print(" - Monitoring dashboard mounted at /dashboard")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Dashboard not available: {e}")
    
    # 9. Test helpers
    app.include_router(health.router)
    print(" - Test helpers mounted")
    
    # 10. Debug endpoints (dev only)
    try:
        from app.routers import debug_events
        app.include_router(debug_events.router)
        print(" - Debug router mounted at /debug")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Debug router not available: {e}")
    
    print("All routes registered.")
    
    return app

app = create_app()

# Initialize the admin interface (SQLAdmin) only when not running
# tests. In test runs a separate test engine/session is used and
# creating Admin against the production engine can cause Operational
# errors when the production DB file is absent or schema differs.
testing = os.getenv("TESTING", "0") in ("1", "true", "True")
if not testing:
    # We do this after route registration so SQLAdmin's mounting at
    # /admin doesn't intercept our custom /admin/ght pages.
    # Mount SQLAdmin under /sqladmin to avoid conflict with our admin pages.
    # Configure SQLAdmin with no authentication (internal use only)
    # Access via /admin gateway page which provides navigation context
    from sqladmin.authentication import AuthenticationBackend
    from starlette.requests import Request
    
    class NoAuthBackend(AuthenticationBackend):
        """Backend d'authentification désactivé pour usage interne."""
        async def login(self, request: Request) -> bool:
            return True
        
        async def logout(self, request: Request) -> bool:
            return True
        
        async def authenticate(self, request: Request) -> bool:
            return True
    
    templates_path = os.path.join(os.path.dirname(__file__), "templates")
    
    admin = Admin(
        app,
        engine,
        base_url="/sqladmin",
        title="IntegraSanté - Admin SQL",
        templates_dir=templates_path,
        authentication_backend=NoAuthBackend(secret_key="not-used-for-internal-app")
    )
    
    # Register all admin views
    register_admin_views(admin)
    
    print("SQLAdmin interface initialized at /sqladmin")

print(f"Application ready with {len(app.routes)} routes")
