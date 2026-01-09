"""
Middleware de gestion des contextes (GHT, Patient, Dossier).

Objectif
- Exposer, pour chaque requête, le contexte courant dans `request.state` afin que
    les vues/routeurs puissent l'utiliser (affichage d'un badge, filtrage, etc.).
- Centraliser la récupération depuis la session (cookie) et éviter de répéter
    cette logique dans chaque route.

Notes d'implémentation
- Les fonctions `get_active_*_context` lisent l'identifiant en session puis
    recharge l'entité depuis la base pour disposer d'un objet complet.
- Le middleware ajoute ces objets sur `request.state` avant d'appeler la suite.
- En mode tests (env TESTING=1), aucune redirection n'est déclenchée ici pour ne
    pas perturber la navigation des tests UI. L'application peut afficher une
    bannière invitant l'utilisateur à choisir un contexte.
"""

from typing import Optional
from fastapi import Request
from sqlmodel import select
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.db import get_session
from app.models_structure import GHTContext, EntiteJuridique, EntiteGeographique
from app.models import Patient, Dossier
from app.models_endpoints import MessageLog
from sqlalchemy import select, func
import os


async def get_active_ght_context(request: Request) -> Optional[GHTContext]:
    """
    Récupère le contexte GHT actif depuis la session et renvoie l'objet complet.

    Processus
    - Lit `ght_context_id` dans la session (cookies signés Starlette).
    - Si présent, ouvre une session DB courte pour recharger `GHTContext`.
    - Renvoie l'entité ou None si rien n'est défini/accessible.
    """
    import logging
    logger = logging.getLogger(__name__)
    debug_enabled = os.getenv("DEBUG_GHT_CONTEXT", "0") in ("1", "true", "True") or os.getenv("TESTING", "0") in ("1", "true", "True")

    try:
        context_id = request.session.get("ght_context_id")
        # Emit debug messages only when explicitly enabled
        if debug_enabled:
            logger.debug("[get_active_ght_context] context_id=%s", context_id)

        if context_id:
            session = next(get_session())
            try:
                ctx = session.get(GHTContext, context_id)
                if debug_enabled:
                    logger.debug("[get_active_ght_context] Loaded context: %s", getattr(ctx, 'name', None))
                return ctx
            finally:
                session.close()
        # Solution de repli for tests: if the signed session cookie isn't parsed but
        # tests have set a simple cookie 'medbridge_test' and/or a JSON
        # 'medbridge_test_data' payload, read those and attempt to resolve
        # the context from DB. This helps headless browsers where signed
        # session cookies may not be parsed consistently.
        try:
            if not context_id:
                # First try a compact JSON payload cookie (percent-encoded or raw)
                raw = request.cookies.get("medbridge_test_data")
                if raw:
                    try:
                        import json as _json
                        from urllib.parse import unquote_plus
                        decoded = unquote_plus(raw)
                        try:
                            parsed = _json.loads(decoded)
                        except Exception:
                            parsed = _json.loads(raw)
                        plain_gid = parsed.get("ght_id")
                        if plain_gid is not None:
                            session = next(get_session())
                            try:
                                ctx = session.get(GHTContext, int(plain_gid))
                                # Best-effort populate session for the request
                                try:
                                    request.session["ght_context_id"] = int(plain_gid)
                                    ej = parsed.get("ej_id")
                                    if ej is not None:
                                        request.session[f"ght_{int(plain_gid)}_ej_id"] = int(ej)
                                        request.session["ej_context_id"] = int(ej)
                                except Exception:
                                    # ignore session set failures
                                    pass
                                return ctx
                            finally:
                                session.close()
                    except Exception:
                        # parsing failed; fall back to older cookie approach
                        pass

                if request.cookies.get("medbridge_test"):
                    plain_gid = request.cookies.get("ght_context_id")
                    if plain_gid:
                        session = next(get_session())
                        try:
                            ctx = session.get(GHTContext, int(plain_gid))
                            return ctx
                        finally:
                            session.close()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"[get_active_ght_context] Error loading context: {e}", exc_info=True)
        pass
    return None


async def get_active_patient_context(request: Request) -> Optional[Patient]:
    """Récupère le patient courant depuis la session et le charge si possible."""
    try:
        patient_id = request.session.get("patient_id")
        if patient_id:
            session = next(get_session())
            try:
                return session.get(Patient, patient_id)
            finally:
                session.close()
    except Exception:
        pass
    return None


async def get_active_ej_context(request: Request) -> Optional[EntiteJuridique]:
    """Récupère l'établissement juridique courant depuis la session et le charge si possible."""
    try:
        ej_id = request.session.get("ej_context_id")
        if ej_id:
            session = next(get_session())
            try:
                return session.get(EntiteJuridique, ej_id)
            finally:
                session.close()
    except Exception:
        pass
    return None


async def get_active_eg_context(request: Request) -> Optional[EntiteGeographique]:
    """Récupère l'entité géographique courante depuis la session et la charge si possible."""
    try:
        eg_id = request.session.get("eg_context_id")
        if eg_id:
            session = next(get_session())
            try:
                return session.get(EntiteGeographique, eg_id)
            finally:
                session.close()
    except Exception:
        pass
    return None


async def get_active_dossier_context(request: Request) -> Optional[Dossier]:
    """Récupère le dossier courant depuis la session et le charge si possible."""
    try:
        dossier_id = request.session.get("dossier_id")
        if dossier_id:
            session = next(get_session())
            try:
                return session.get(Dossier, dossier_id)
            finally:
                session.close()
    except Exception:
        pass
    return None


async def get_error_message_count(request: Request) -> int:
    """
    Compte le nombre de messages en erreur selon le contexte actif.
    
    Filtrage par contexte:
    - Si dossier actif: messages du dossier en erreur
    - Si patient actif: messages du patient en erreur
    - Si EJ actif: messages de l'EJ en erreur
    - Si GHT actif: messages du GHT en erreur
    - Sinon: tous les messages en erreur
    """
    try:
        session = next(get_session())
        try:
            query = select(func.count(MessageLog.id)).where(MessageLog.validation_status == "error")
            
            # Filtrer par contexte du plus spécifique au plus général
            dossier_id = request.session.get("dossier_id")
            if dossier_id:
                query = query.where(MessageLog.dossier_id == dossier_id)
            else:
                patient_id = request.session.get("patient_id")
                if patient_id:
                    # Filtrer par dossiers du patient
                    from app.models import Dossier
                    dossier_ids = [d.id for d in session.exec(select(Dossier).where(Dossier.patient_id == patient_id)).all()]
                    if dossier_ids:
                        query = query.where(MessageLog.dossier_id.in_(dossier_ids))
                else:
                    ej_id = request.session.get("ej_context_id")
                    if ej_id:
                        query = query.where(MessageLog.ej_emetteur_id == ej_id)
                    else:
                        ght_id = request.session.get("ght_context_id")
                        if ght_id:
                            # Filtrer par EJs du GHT
                            from app.models_structure import EntiteJuridique
                            ej_ids = [ej.id for ej in session.exec(select(EntiteJuridique).where(EntiteJuridique.ght_context_id == ght_id)).all()]
                            if ej_ids:
                                query = query.where(MessageLog.ej_emetteur_id.in_(ej_ids))
            
            result = session.execute(query).scalar_one()
            return result or 0
        finally:
            session.close()
    except Exception:
        return 0


class GHTContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour injecter les contextes (GHT, Patient, Dossier) sur `request.state`.

    - Utilise BaseHTTPMiddleware pour être installé via `app.add_middleware(...)`.
    - Ajoute systématiquement `request.state.ght_context`, `patient_context`,
      `dossier_context` pour les templates et les dépendances.
    - Ne force pas la redirection ici (comportement non intrusif) — les routes
      peuvent imposer un contexte via les dépendances (ex: `require_ght_context`).
    """

    API_PATH_PREFIXES = (
        "/structure",
        "/fhir",
        "/api",
        "/messages",
    )
    ALLOWED_PATHS = {
        "/",
        "/guide",
        "/guide/",
        "/api-docs",
        "/api-docs/",
    }
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next):
        # Ajouter le contexte GHT aux attributs de la requête
        request.state.ght_context = await get_active_ght_context(request)
        # Ajouter le contexte EJ si présent
        request.state.ej_context = await get_active_ej_context(request)
        # Ajouter le contexte EG si présent
        request.state.eg_context = await get_active_eg_context(request)
        # Si aucun GHT n'est défini mais qu'un EJ est sélectionné, déduire le GHT depuis l'EJ
        if not request.state.ght_context and request.state.ej_context and getattr(request.state.ej_context, "ght_context", None):
            request.state.ght_context = request.state.ej_context.ght_context
        # Si aucun GHT n'est défini mais qu'un EG est sélectionné, déduire le GHT depuis l'EJ de l'EG
        if not request.state.ght_context and request.state.eg_context and getattr(request.state.eg_context, "entite_juridique", None):
            ej = request.state.eg_context.entite_juridique
            if ej and getattr(ej, "ght_context", None):
                request.state.ght_context = ej.ght_context
        # Ajouter les contextes Patient/Dossier si présents
        request.state.patient_context = await get_active_patient_context(request)
        request.state.dossier_context = await get_active_dossier_context(request)
        
        # Compter les messages en erreur selon le contexte
        request.state.error_message_count = await get_error_message_count(request)
        
        # Inject version into request state for templates
        request.state.version = getattr(request.app.state, "version", "1.0.0-alpha")

        # En tests, on évite les redirections automatiques pour ne pas casser
        # les scénarios Playwright. Les pages peuvent afficher un message doux.
        if os.getenv("TESTING", "0") in ("1", "true", "True"):
            return await call_next(request)

        # Historique: une redirection globale vers /admin/ght était effectuée
        # lorsqu'aucun contexte n'était défini. Cela surprenait la navigation.
        # On préfère maintenant une approche "douce" avec bannière dans la base.html.

        return await call_next(request)
