"""GHT Context CRUD routes"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.models_structure_fhir import GHTContext, IdentifierNamespace
from app.utils.flash import flash
from app.services.structure_seed import ensure_demo_structure
from .helpers import get_context_or_404, get_ej_or_404

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/ght", tags=["ght"])


@router.get("")
@router.get("/")
async def list_ght_contexts(
    request: Request,
    session: Session = Depends(get_session),
):
    """Liste tous les contextes GHT (page de sélection)."""
    contexts = session.exec(select(GHTContext)).all()
    return templates.TemplateResponse(
        "ght_contexts.html",
        {"request": request, "contexts": contexts},
    )


@router.get("/new")
async def new_ght_context_form(request: Request):
    """Affiche le formulaire de création d'un nouveau contexte GHT."""
    return templates.TemplateResponse(
        "ght_form.html",
        {
            "request": request,
            "context": None,
        },
    )


@router.post("/{context_id}/set-ej")
async def set_ej_for_ght(
    request: Request,
    context_id: int,
    ej_id: int = Form(...),
    session: Session = Depends(get_session)
):
    """Enregistre l'entité juridique sélectionnée pour le contexte GHT en session utilisateur."""
    context = get_context_or_404(session, context_id)
    if ej_id:
        ej = get_ej_or_404(session, context, ej_id)
        request.session[f"ght_{context_id}_ej_id"] = ej_id
        request.session[f"ght_{context_id}_ej_name"] = ej.name
        # Définir aussi les contextes globaux pour cohérence de l'UI et des filtres
        request.session["ej_context_id"] = ej_id
        request.session["ght_context_id"] = context_id
    else:
        request.session.pop(f"ght_{context_id}_ej_id", None)
        request.session.pop(f"ght_{context_id}_ej_name", None)
        # Si on désélectionne l'EJ, effacer le contexte global EJ mais conserver le GHT courant
        request.session.pop("ej_context_id", None)
    return RedirectResponse(f"/admin/ght/{context_id}", status_code=303)


@router.post("/new")
async def create_ght_context(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    description: Optional[str] = Form(None),
    is_active: str = Form("true"),
    session: Session = Depends(get_session),
):
    """Crée un nouveau contexte GHT et initialise des namespaces par défaut."""
    # Uniqueness check for code
    existing = session.exec(select(GHTContext).where(GHTContext.code == code)).first()
    if existing:
        flash(request, "Ce code est déjà utilisé par un autre contexte GHT.", "error")
        return templates.TemplateResponse(
            "ght_form.html",
            {
                "request": request,
                "context": None,
                "form_data": {
                    "name": name,
                    "code": code,
                    "description": description,
                    "is_active": is_active,
                },
            },
            status_code=400,
        )

    context = GHTContext(
        name=name,
        code=code,
        description=description,
        is_active=str(is_active).lower() in ("1", "true", "yes", "on"),
    )
    session.add(context)
    session.commit()
    session.refresh(context)

    # Default namespaces for the new context
    default_namespaces = [
        {
            "name": "IPP",
            "system": f"urn:oid:1.2.250.1.{context.id}.1.0",
            "type": "PI",
            "description": "Identifiant Patient Principal",
        },
        {
            "name": "NDA",
            "system": f"urn:oid:1.2.250.1.{context.id}.1.1",
            "type": "VN",
            "description": "Numéro de Dossier Administratif",
        },
        {
            "name": "FINESS EJ",
            "system": "urn:oid:1.2.250.1.71.4.2.2",
            "type": "XX",
            "description": "FINESS Entité Juridique",
        },
        {
            "name": "FINESS EG",
            "system": "urn:oid:1.2.250.1.71.4.2.1",
            "type": "XX",
            "description": "FINESS Entité Géographique",
        },
    ]

    for ns in default_namespaces:
        namespace = IdentifierNamespace(
            name=ns["name"],
            system=ns["system"],
            type=ns["type"],
            description=ns["description"],
            ght_context_id=context.id,
        )
        session.add(namespace)

    session.commit()

    flash(request, f'Contexte GHT "{context.name}" créé avec succès.', "success")

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {"ok": True, "id": context.id, "redirect": "/admin/ght"}

    return RedirectResponse("/admin/ght", status_code=303)


@router.get("/{context_id}/edit")
async def edit_ght_context_form(
    request: Request,
    context_id: int,
    session: Session = Depends(get_session)
):
    """Affiche le formulaire d'édition d'un contexte GHT."""
    context = session.get(GHTContext, context_id)
    if not context:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    
    return templates.TemplateResponse(
        "ght_form.html",
        {
            "request": request,
            "context": context
        }
    )


@router.post("/{context_id}/edit")
async def update_ght_context(
    request: Request,
    context_id: int,
    name: str = Form(...),
    code: str = Form(...),
    description: Optional[str] = Form(None),
    is_active: str = Form("true"),
    session: Session = Depends(get_session)
):
    """Met à jour un contexte GHT existant."""
    context = session.get(GHTContext, context_id)
    if not context:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    
    # Vérifier l'unicité du code si modifié
    if code != context.code:
        existing = session.exec(
            select(GHTContext).where(GHTContext.code == code)
        ).first()
        if existing:
            flash(request, "Ce code est déjà utilisé par un autre contexte GHT.", "error")
            accept = request.headers.get("accept", "")
            if "application/json" in accept:
                return {"ok": False, "message": "Ce code est déjà utilisé", "errors": {"code": "Code déjà utilisé"}}

            return templates.TemplateResponse(
                "ght_form.html",
                {
                    "request": request,
                    "context": context,
                    "form_data": {
                        "name": name,
                        "code": code,
                        "description": description,
                        "is_active": is_active,
                    },
                },
                status_code=400,
            )
    
    context.name = name
    context.code = code
    context.description = description
    context.is_active = str(is_active).lower() in ("1", "true", "yes", "on")
    context.updated_at = datetime.utcnow()
    
    session.add(context)
    session.commit()

    flash(request, f'Contexte GHT "{context.name}" mis à jour.', "success")
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {"ok": True, "id": context.id, "redirect": "/admin/ght"}

    return RedirectResponse(
        "/admin/ght",
        status_code=303
    )


@router.get("/{context_id}")
async def view_ght_context(
    request: Request,
    context_id: int,
    session: Session = Depends(get_session)
):
    """Affiche les détails d'un contexte GHT et ses entités."""
    context = session.get(GHTContext, context_id)
    if not context:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    
    # Stocker le contexte sélectionné en session
    request.session["ght_context_id"] = context_id
    
    selected_ej_id = request.session.get(f"ght_{context_id}_ej_id")
    selected_ej_name = request.session.get(f"ght_{context_id}_ej_name")
    return templates.TemplateResponse(
        "ght_detail.html",
        {
            "request": request,
            "context": context,
            "namespaces": context.namespaces,
            "entites_juridiques": context.entites_juridiques,
            "selected_ej_id": selected_ej_id,
            "selected_ej_name": selected_ej_name,
        }
    )


@router.post("/{context_id}/seed-demo")
async def seed_demo_structure(
    request: Request,
    context_id: int,
    session: Session = Depends(get_session),
):
    """Génère ou met à jour une structure hospitalière de démonstration pour ce GHT."""
    context = get_context_or_404(session, context_id)
    stats = ensure_demo_structure(session, context)

    summary_parts = []
    label_map = {
        "entite_juridique": "entité juridique",
        "entite_geographique": "site géographique",
        "pole": "pôle",
        "service": "service",
        "unite_fonctionnelle": "UF",
        "unite_hebergement": "UH",
        "chambre": "chambre",
        "lit": "lit",
    }
    for key, label in label_map.items():
        created = stats["created"].get(key, 0)
        updated = stats["updated"].get(key, 0)
        if created or updated:
            summary_parts.append(f"{label}s +{created}/~{updated}")

    message = "Structure de démonstration générée."
    if summary_parts:
        message += " " + ", ".join(summary_parts) + "."

    flash(request, message, "success")
    return RedirectResponse(f"/admin/ght/{context_id}", status_code=303)
