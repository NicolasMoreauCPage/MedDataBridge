"""GHT Namespaces CRUD routes"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.db import get_session
from app.models_structure_fhir import GHTContext, IdentifierNamespace
from app.utils.flash import flash
from .helpers import get_context_or_404

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/ght/{context_id}/namespaces", tags=["ght_namespaces"])

@router.get("/new")
async def new_namespace_form(
    request: Request,
    context_id: int,
    session: Session = Depends(get_session),
):
    """Affiche le formulaire de création d'un nouveau namespace."""
    context = get_context_or_404(session, context_id)
    return templates.TemplateResponse(
        "namespace_form.html",
        {
            "request": request,
            "context": context,
            "namespace": None,
        },
    )

@router.post("/new")
async def create_namespace(
    request: Request,
    context_id: int,
    name: str = Form(...),
    description: str = Form(...),
    oid: str = Form(...),
    system: str = Form(...),
    type: str = Form(...),
    session: Session = Depends(get_session),
):
    """Crée un nouveau namespace."""
    context = get_context_or_404(session, context_id)
    
    namespace = IdentifierNamespace(
        name=name,
        description=description,
        oid=oid,
        system=system,
        type=type,
        ght_context_id=context.id,
        is_active=True
    )
    session.add(namespace)
    session.commit()
    flash(request, f"Namespace {name} créé avec succès", "success")
    return RedirectResponse(url=f"/admin/ght/{context_id}", status_code=303)

@router.get("/{namespace_id}")
async def namespace_detail(
    request: Request,
    context_id: int, 
    namespace_id: int,
    session: Session = Depends(get_session),
):
    """Affiche les détails d'un namespace."""
    context = get_context_or_404(session, context_id)
    namespace = session.get(IdentifierNamespace, namespace_id)
    if not namespace or namespace.ght_context_id != context.id:
        raise HTTPException(status_code=404, detail="Namespace non trouvé")
    
    return templates.TemplateResponse(
        "namespace_detail.html",
        {
            "request": request,
            "context": context,
            "namespace": namespace
        },
    )

@router.post("/{namespace_id}/edit")
async def edit_namespace(
    request: Request,
    context_id: int,
    namespace_id: int, 
    name: str = Form(...),
    description: str = Form(...),
    oid: str = Form(...),
    system: str = Form(...),
    type: str = Form(...),
    session: Session = Depends(get_session),
):
    """Modifie un namespace existant."""
    context = get_context_or_404(session, context_id)
    namespace = session.get(IdentifierNamespace, namespace_id)
    if not namespace or namespace.ght_context_id != context.id:
        raise HTTPException(status_code=404, detail="Namespace non trouvé")
        
    namespace.name = name
    namespace.description = description 
    namespace.oid = oid
    namespace.system = system
    namespace.type = type
    
    session.add(namespace)
    session.commit()
    flash(request, f"Namespace {name} modifié avec succès", "success")
    return RedirectResponse(url=f"/admin/ght/{context_id}", status_code=303)