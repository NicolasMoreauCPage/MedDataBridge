"""
Composition de l'application FastAPI (MedData Bridge)

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

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, APIRouter
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqladmin import Admin, ModelView
from sqlmodel import select

from app.middleware.flash import FlashMessageMiddleware
from app.middleware.ght_context import GHTContextMiddleware

from app.db import init_db, engine, get_session
from app import models_scenarios  # ensure scenario models are registered
from app.admin import register_admin_views  # SQLAdmin views
from app.db_session_factory import session_factory
from app.services.transport_inbound import on_message_inbound
from app.services.mllp_manager import MLLPManager
from app.services.entity_events import register_entity_events
from app.services.entity_events_structure import register_structure_entity_events
from app.services.scheduler import start_scheduler, stop_scheduler

# BUGFIX: Le module ght doit être importé AVANT le __init__.py des routers
# car il y a un problème d'import circulaire qui empêche le chargement complet
# de toutes les routes (seules 9 routes sur 45 sont chargées sinon)
import app.routers.ght as ght
import app.routers.ght_ej_min as ght_ej_min
"""Application composition module.

NOTE (Fallback Router Removal): The previous temporary fallback router
`ght_ej_fallback` guaranteeing `/admin/ght/{context_id}/ej/{ej_id}` has been
removed now that the main `ght` router consistently loads all routes after the
import/reload bugfix sequence. If future partial-load regressions occur, prefer
modularizing `app/routers/ght.py` instead of reintroducing a fallback.
"""
import app.routers.ght_ej_fallback as _deprecated_ght_ej_fallback  # Deprecated (kept only if reactivation needed)

from app.routers import (
    home, patients, dossiers, venues, mouvements, structure_hl7,
    endpoints, transport, transport_views, fhir_inbox, messages, interop,
    generate, structure, workflow, fhir_structure, vocabularies,
    health, scenarios, guide, docs, ihe, dossier_type, structure_select, validation,
    documentation, conformity, fhir_export, fhir_import, metrics, auth
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
if os.getenv("MLLP_TRACE", "0") in ("1","true","True"):
    logging.getLogger("mllp").setLevel(logging.DEBUG)

# Instance unique du manager et publication via app.state
# - `session_factory` fournit des sessions DB courtes et sûres côté workers.
# - `on_message_inbound` est appelé pour chaque message entrant HL7.
mllp_manager = MLLPManager(session_factory=session_factory, on_message=on_message_inbound)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # En tests, on ne veut pas initialiser la DB de production (medbridge.db) ni démarrer
    # des serveurs MLLP en arrière-plan. Les tests surchargent l'accès DB via
    # des overrides, on saute donc init/reload quand TESTING est présent.
    testing = os.getenv("TESTING", "0") in ("1", "true", "True")
    if not testing:
        init_db()
        # Register entity event listeners for automatic message emission
        register_entity_events()
        register_structure_entity_events()
        logging.info("Entity event listeners registered for automatic emission")
        # Démarrage idempotent
        sess = next(get_session())
        try:
            # Initialiser les vocabulaires si demandé
            if os.getenv("INIT_VOCAB", "0") in ("1", "true", "True"):
                from app.vocabulary_init import init_vocabularies
                init_vocabularies(sess)
                logging.info("Vocabulaires initialisés")
            
            await mllp_manager.reload_all(sess)
        finally:
            sess.close()
        
        # Démarrer le scheduler pour le polling des endpoints FILE
        # Par défaut: 60 secondes (1 minute). Configurable via FILE_POLL_INTERVAL
        poll_interval = int(os.getenv("FILE_POLL_INTERVAL", "60"))
        await start_scheduler(poll_interval)
        logging.info(f"File endpoint polling started (interval: {poll_interval}s)")

    try:
        yield
    finally:
        if not testing:
            await stop_scheduler()
            await mllp_manager.stop_all()

def create_app() -> FastAPI:
    app = FastAPI(
        title="MedBridge - Healthcare Interoperability Platform",
        version="1.0.0-rc1",
        lifespan=lifespan
    )

    print("\nFastAPI app initialization")

    # Filtre Jinja2 global pour masquer None ou 'None' par '—'
    def none_to_dash(value):
        if value is None or value == "None":
            return "—"
        return value
    # Ajout du filtre au moteur de templates Jinja2
    from fastapi.templating import Jinja2Templates
    templates_dir = str(Path(__file__).parent / "templates")
    templates = Jinja2Templates(directory=templates_dir)
    templates.env.filters["none_to_dash"] = none_to_dash
    # Stocker dans app.state pour accès dans les routes si besoin
    app.state.templates = templates
    # Store version from pyproject.toml
    app.state.version = "0.2.0"

    # Servir les fichiers statiques (CSS/JS)
    static_dir = str(Path(__file__).parent / "static")
    app.mount("/static", StaticFiles(directory=static_dir, html=True, check_dir=True), name="static")

    # Session et contexte GHT: IMPORTANT - dans Starlette, le dernier middleware
    # ajouté est exécuté en premier. Nous voulons que SessionMiddleware s'exécute
    # AVANT FlashMessageMiddleware et GHTContextMiddleware pour que request.session
    # soit disponible dans ces middlewares. Donc on ajoute d'abord Flash/GHT,
    # PUIS SessionMiddleware en dernier.
    app.add_middleware(FlashMessageMiddleware)
    app.add_middleware(GHTContextMiddleware)

    session_secret = (
        os.getenv("SESSION_SECRET_KEY")
        or os.getenv("SESSION_SECRET")
        or os.getenv("SECRET_KEY")
    )
    if not session_secret:
        session_secret = secrets.token_urlsafe(32)
        logging.getLogger(__name__).warning(
            "SESSION_SECRET_KEY non défini - utilisation d'un secret éphémère pour cette instance"
        )
    app.add_middleware(SessionMiddleware, secret_key=session_secret)

    # exposer le manager aux routeurs
    app.state.mllp_manager = mllp_manager

    # Note: admin interface (SQLAdmin) will be created after route
    # registration to avoid catching /admin/* routes before our own
    # admin-related pages (like /admin/ght). The Admin instance is
    # created later just before returning the app.

    # Core application routes in dependency order
    # Routes are registered in logical dependency order
    # Some routers have their own prefix defined in their router creation
    
    # Register routes in order with correct prefixes
    print("\nRegistering routes:")
    
    # 1. Basic UI routes 
    app.include_router(home.router)
    print(" - Home router mounted at /")
    
    # 2. Entity and core data routes - all have their own prefixes
    app.include_router(patients.router)
    app.include_router(dossiers.router)
    app.include_router(venues.router)
    app.include_router(mouvements.router)
    print(" - Core entity routers mounted with their prefixes")
    
    # 2b. Timeline views
    from app.routers import timeline
    app.include_router(timeline.router)
    print(" - Timeline router mounted")
    
    # 3. Structure management
    app.include_router(structure.redirect_router)  # Redirections singulier->pluriel (AVANT le router principal)
    app.include_router(structure.router)  # Has prefix /structure
    app.include_router(structure.api_router)  # Has prefix /api/structure
    app.include_router(structure_hl7.router)  # Has prefix /structure
    app.include_router(fhir_structure.router)  # Has prefix /fhir
    app.include_router(structure_select.router)  # Has prefix /structure
    print(" - Structure routers mounted")
    
    # 4. Admin interfaces (mount under /admin so templates/redirects using
    # /admin/ght work as expected)
    from app.routers import admin_gateway
    app.include_router(admin_gateway.router)
    app.include_router(ght.router, prefix="/admin")
    # Minimal EJ detail router (guarantee availability even if ght incomplete)
    app.include_router(ght_ej_min.router, prefix="/admin")
    print(" - Admin routers mounted under /admin")
    
    # 5. Integration and transport
    app.include_router(messages.router)
    app.include_router(fhir_inbox.router)
    app.include_router(transport_views.router, prefix="/transport")
    app.include_router(transport.router)  # Has own prefix
    app.include_router(endpoints.router)  # Has own prefix
    app.include_router(ihe.router)  # Has own prefix /ihe
    print(" - Integration routers mounted")
    
    # 6. Utilities and workflow
    app.include_router(workflow.router)
    app.include_router(generate.router)
    app.include_router(interop.router)
    app.include_router(vocabularies.router)
    app.include_router(validation.router)  # Validation hors contexte
    app.include_router(documentation.router)  # Documentation
    app.include_router(conformity.router)  # Conformité par EJ
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
    
    # Scenario templates (contextualisables) - AVANT scenarios pour éviter conflit de routes
    try:
        from app.routers import scenario_templates
        app.include_router(scenario_templates.router)
        print(" - Scenario templates router mounted")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Scenario templates router not available: {e}")
    
    app.include_router(scenarios.router)
    
    print(" - Utility routers mounted")
    
    # 7. Cache management
    from app.routers import cache
    app.include_router(cache.router, prefix="/api")
    print(" - Cache router mounted at /api/cache")
    
    # 8. Import endpoints for test examples
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
    print(" - FHIR API routers mounted")

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
    
    # BUGFIX TEMPORAIRE: Forcer le rechargement du module ght pour obtenir toutes les routes
    # Le module ght.py ne charge que 9 routes sur 45+ lors de l'import normal à cause
    # d'un problème d'import circulaire ou de taille de fichier (3464 lignes).
    # Cette solution force le rechargement après que toutes les dépendances soient chargées.
    try:
        import importlib
        importlib.reload(ght)
        # Remplacer le router existant par le router complet
        for route in app.routes[:]:
            if hasattr(route, 'path') and route.path.startswith('/admin/ght'):
                app.routes.remove(route)
        # Réenregistrer principal + minimal EJ route
        app.include_router(ght.router, prefix="/admin")
        app.include_router(ght_ej_min.router, prefix="/admin")
        ght_routes_count = len([r for r in app.routes if hasattr(r, 'path') and r.path.startswith('/admin/ght')])
        print(f" → BUGFIX: Module ght rechargé ({ght_routes_count} routes /admin/ght)")
    except Exception as e:
        print(f" → BUGFIX WARNING: Échec du rechargement de ght: {e}")

    # Initialize the admin interface (SQLAdmin) only when not running
    # tests. In test runs a separate test engine/session is used and
    # creating Admin against the production engine can cause Operational
    # errors when the production DB file is absent or schema differs.
    testing = os.getenv("TESTING", "0") in ("1", "true", "True")
    if not testing:
        # We do this after route registration so SQLAdmin's mounting at
        # /admin doesn't intercept our custom /admin/ght pages.
        # Mount SQLAdmin under /sqladmin to avoid conflict with our admin pages.
        # Configure SQLAdmin
        # Access via /admin gateway page which provides navigation context
        admin = Admin(
            app, 
            engine, 
            base_url="/sqladmin",
            title="MedData Bridge - Admin SQL",
            templates_dir="app/templates"
        )
        
        # Register all admin views from app.admin module
        register_admin_views(admin)

    return app

# Create module-level `app` only when not running tests. Tests call
# `create_app()` directly after preparing the test database so we avoid
# side-effects (like initializing the production DB or starting MLLP
# managers) at import time which can interfere with test setup.
app = create_app()
# reload trigger lun. 03 nov. 2025 08:00:19 CET
