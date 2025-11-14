from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
from app.db import get_session
from app.models_structure_fhir import IdentifierNamespace, GHTContext, EntiteJuridique
from app.utils.flash import flash
router = APIRouter(prefix="/ght", tags=["admin-ght"])
templates = Jinja2Templates(directory="app/templates")
# Route GET pour afficher le formulaire de création de namespace pour une EJ
# (placé après la définition de 'router')

# ...existing code...


# Route GET pour afficher le formulaire de création de namespace pour une EJ
@router.get("/{context_id}/ej/{ej_id}/namespaces/new")
async def new_namespace_form(
    request: Request,
    context_id: int,
    ej_id: int,
    session: Session = Depends(get_session),
):
    context = _ctx(session, context_id)
    entite = _ej(session, context, ej_id)
    back_url = f"/admin/ght/{context_id}/ej/{ej_id}"
    return templates.TemplateResponse(
        request,
        "ej_namespace_form.html",
        {
            "context": context,
            "entite": entite,
            "namespace": None,
            "action_url": f"/admin/ght/{context_id}/ej/{ej_id}/namespaces/new",
            "back_url": back_url,
        },
    )

# Route POST pour enregistrer le nouveau namespace
@router.post("/{context_id}/ej/{ej_id}/namespaces/new")
async def create_namespace(
    request: Request,
    context_id: int,
    ej_id: int,
    # name: str = Form(...),
    type: str = Form(...),
    system: str = Form(...),
    oid: str = Form(None),
    description: str = Form(None),
    is_active: str = Form("true"),
    session: Session = Depends(get_session),
):
    context = _ctx(session, context_id)
    entite = _ej(session, context, ej_id)
    namespace = IdentifierNamespace(
        type=type,
        system=system,
        oid=oid,
        description=description,
        is_active=str(is_active).lower() in ("1", "true", "yes", "on"),
        ght_context_id=context.id,
        entite_juridique_id=entite.id,
    )
    session.add(namespace)
    session.commit()
    from app.utils.flash import flash
    flash(request, f"Namespace '{type}' créé avec succès.", "success")
    return RedirectResponse(f"/admin/ght/{context_id}/ej/{ej_id}", status_code=303)


def _ctx(session: Session, ctx_id: int) -> GHTContext:
    ctx = session.get(GHTContext, ctx_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    return ctx


def _ej(session: Session, context: GHTContext, ej_id: int) -> EntiteJuridique:
    ej = session.exec(
        select(EntiteJuridique)
        .where(EntiteJuridique.id == ej_id)
        .where(EntiteJuridique.ght_context_id == context.id)
    ).first()
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    return ej


@router.get("/{context_id}/ej/{ej_id}/edit")
async def edit_entite_juridique_form(
    request: Request,
    context_id: int,
    ej_id: int,
    session: Session = Depends(get_session),
):
    context = _ctx(session, context_id)
    entite = _ej(session, context, ej_id)

    return templates.TemplateResponse(
        request,
        "ej_form.html",
        {"context": context, "entite": entite},
    )


@router.post("/{context_id}/ej/{ej_id}/edit")
async def update_entite_juridique(
    request: Request,
    context_id: int,
    ej_id: int,
    name: str = Form(...),
    finess_ej: str = Form(...),
    short_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    siren: Optional[str] = Form(None),
    siret: Optional[str] = Form(None),
    address_line: Optional[str] = Form(None),
    postal_code: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    country: str = Form("FR"),
    is_active: str = Form("true"),
    session: Session = Depends(get_session),
):
    context = _ctx(session, context_id)
    entite = _ej(session, context, ej_id)

    if finess_ej != entite.finess_ej:
        exists = session.exec(
            select(EntiteJuridique)
            .where(EntiteJuridique.finess_ej == finess_ej)
            .where(EntiteJuridique.id != entite.id)
        ).first()
        if exists:
            flash(
                request,
                "Une entité juridique avec ce FINESS existe déjà.",
                "error",
            )
            return templates.TemplateResponse(
                request,
                "ej_form.html",
                {"context": context, "entite": entite},
            )

    # Update entity
    entite.name = name
    entite.finess_ej = finess_ej
    entite.short_name = short_name
    entite.description = description
    entite.siren = siren
    entite.siret = siret
    entite.address_line = address_line
    entite.postal_code = postal_code
    entite.city = city
    entite.country = country
    entite.is_active = str(is_active).lower() in ("1", "true", "yes", "on")

    session.add(entite)
    session.commit()

    flash(request, f'Entité juridique "{entite.name}" mise à jour avec succès.', "success")
    return RedirectResponse(f"/admin/ght/{context_id}/ej/{ej_id}", status_code=303)
