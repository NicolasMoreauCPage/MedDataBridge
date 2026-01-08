"""Dépendances de contexte (GHT, Patient, Dossier).

Objectif
- Fournir des gardes à utiliser dans les routeurs FastAPI pour imposer
    la présence d'un contexte (GHT, patient ou dossier) avant d'exécuter
    une action. Si le contexte est absent, on renvoie une redirection 307
    vers la page adéquate afin de préserver la méthode HTTP (POST/GET).

Notes
- Ces gardes lisent les objets déjà injectés par le middleware
    `GHTContextMiddleware` dans `request.state`.
- Le code de statut 307 (Temporary Redirect) est volontaire ici: il
    conserve la sémantique de la méthode en cas de ré-émission éventuelle
    et reste cohérent avec l'usage existant dans l'application.
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse


def require_ght_context(request: Request):
    """Vérifie qu'un contexte GHT est actif pour la requête courante.

    Si aucun contexte n'est présent, une redirection 307 est émise vers
    `/admin/ght` afin d'inviter l'utilisateur à sélectionner un GHT.
    """
    context = getattr(request.state, "ght_context", None)
    if context is None:
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        session_id = request.session.get("ght_context_id")
        logger.warning(f"GHT context required but not found. Session has ght_context_id={session_id}, state.ght_context={context}")
        
        # Pour les requêtes POST de formulaire, rediriger plutôt que lever une exception
        if request.method == "POST":
            from app.middleware.flash import flash
            flash(request, "Veuillez sélectionner un contexte GHT avant de continuer", "warning")
            return RedirectResponse(url="/admin/ght", status_code=303)
        
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            detail="Active GHT context required",
            headers={"Location": "/admin/ght"},
        )
    return context


def require_patient_context(request: Request):
    """Vérifie qu'un contexte Patient est actif.

    Si absent, on redirige en 307 vers `/patients` pour que l'utilisateur
    sélectionne ou crée un patient avant de poursuivre.
    """
    patient = getattr(request.state, "patient_context", None)
    if patient is None:
        # Use 307 with Location header to keep method semantics (like existing approach)
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            detail="Active Patient context required",
            headers={"Location": "/patients"},
        )
    return patient


def require_dossier_context(request: Request):
    """Vérifie qu'un contexte Dossier est actif.

    Si absent, on redirige en 307 vers `/dossiers` afin de choisir un
    dossier actif avant l'opération demandée.
    """
    dossier = getattr(request.state, "dossier_context", None)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            detail="Active Dossier context required",
            headers={"Location": "/dossiers"},
        )
    return dossier
