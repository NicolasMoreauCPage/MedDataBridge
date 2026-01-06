"""GHT Namespaces CRUD routes"""
import logging
import re
from typing import Tuple, Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.db import get_session
from app.models_structure import GHTContext, IdentifierNamespace
from app.utils.flash import flash
from .helpers import get_context_or_404

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/{context_id}/namespaces", tags=["ght_namespaces"])


def validate_and_extract_oid(system: str, oid: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valide la cohérence entre system et oid, et extrait automatiquement l'OID si nécessaire.
    
    Args:
        system: URI FHIR (ex: "urn:oid:1.2.250.1.71.1.2.2")
        oid: OID HL7v2 (ex: "1.2.250.1.71.1.2.2") ou None
    
    Returns:
        (is_valid, error_message, extracted_oid)
    """
    if not system:
        return False, "L'URI FHIR (system) est obligatoire", None
    
    # Si system est un urn:oid, extraire l'OID
    if system.startswith("urn:oid:"):
        extracted_oid = system[8:]  # Enlever "urn:oid:"
        
        # Vérifier que l'OID est au bon format
        if not re.match(r'^\d+(\.\d+)+$', extracted_oid):
            return False, f"L'OID extrait '{extracted_oid}' n'est pas au format valide (ex: 1.2.250.1.71)", None
        
        # Si l'utilisateur a fourni un OID, vérifier qu'il correspond
        if oid and oid.strip() and oid != extracted_oid:
            return False, f"Incohérence : l'OID '{oid}' ne correspond pas à l'URI '{system}' (attendu: '{extracted_oid}')", None
        
        # Utiliser l'OID extrait
        return True, None, extracted_oid
    
    # Si system n'est pas un urn:oid (rare), l'OID est facultatif mais doit être valide
    if oid and oid.strip():
        if not re.match(r'^\d+(\.\d+)+$', oid):
            return False, f"L'OID '{oid}' n'est pas au format valide (ex: 1.2.250.1.71)", None
        return True, None, oid
    
    # Pas d'OID fourni et system n'est pas un urn:oid : acceptable
    return True, None, None


def generate_namespace_name(type: str, oid: Optional[str], existing_name: Optional[str]) -> str:
    """
    Génère un nom de namespace descriptif pour les messages HL7v2/IHE PAM.
    
    Args:
        type: Type d'identifiant (IPP, NDA, MVT, VN, PC)
        oid: OID du namespace
        existing_name: Nom existant fourni par l'utilisateur (prioritaire)
    
    Returns:
        Nom du namespace (ex: "IPP_1_2_250_1_71" ou nom fourni)
    """
    if existing_name and existing_name.strip():
        return existing_name.strip()
    
    # Générer un nom basé sur le type et l'OID
    if oid:
        # Remplacer les points par des underscores pour créer un nom valide
        oid_safe = oid.replace(".", "_")
        return f"{type}_{oid_safe}"
    
    # Fallback : juste le type
    return type

@router.get("/new")
async def new_namespace_form(
    request: Request,
    context_id: int,
    session: Session = Depends(get_session),
):
    """Affiche le formulaire de création d'un nouveau namespace."""
    context = get_context_or_404(session, context_id)
    return templates.TemplateResponse(
        request,
        "namespace_form.html",
        {
            "context": context,
            "namespace": None},
    )

@router.post("/new")
async def create_namespace(
    request: Request,
    context_id: int,
    name: str = Form(default=""),
    description: str = Form(default=""),
    oid: str = Form(default=""),
    system: str = Form(...),
    type: str = Form(...),
    session: Session = Depends(get_session),
):
    """Crée un nouveau namespace avec validation et auto-extraction de l'OID."""
    context = get_context_or_404(session, context_id)
    
    logger.info(f"Tentative de création namespace: type={type}, system={system}, ght_context_id={context.id}")
    
    # Validation et extraction automatique de l'OID
    is_valid, error_msg, extracted_oid = validate_and_extract_oid(system, oid)
    if not is_valid:
        logger.warning(f"Validation échouée: {error_msg}")
        flash(request, f"Erreur de validation : {error_msg}", "error")
        return RedirectResponse(url=f"/admin/ght/{context_id}/namespaces/new", status_code=303)
    
    # Utiliser l'OID extrait
    final_oid = extracted_oid
    
    # Générer le nom si non fourni (pour messages HL7v2/IHE PAM)
    final_name = generate_namespace_name(type, final_oid, name)
    
    logger.info(f"Namespace validé: name={final_name}, oid={final_oid}")
    
    # Vérifier si un namespace avec ce system ET ce type existe déjà pour ce GHT
    from sqlmodel import select
    existing = session.exec(
        select(IdentifierNamespace)
        .where(IdentifierNamespace.system == system)
        .where(IdentifierNamespace.type == type)
        .where(IdentifierNamespace.ght_context_id == context.id)
    ).first()
    
    if existing:
        logger.warning(f"Namespace déjà existant avec system={system} et type={type} pour GHT {context.id}: ID={existing.id}")
        flash(request, f"Un namespace de type '{type}' avec l'URI '{system}' existe déjà (ID: {existing.id}). Plusieurs types peuvent partager le même URI, mais pas le même type+URI.", "warning")
        return RedirectResponse(url=f"/admin/ght/{context_id}/namespaces/new", status_code=303)
    
    try:
        namespace = IdentifierNamespace(
            name=final_name,
            description=description if description else None,
            oid=final_oid,
            system=system,
            type=type,
            ght_context_id=context.id,
            is_active=True
        )
        session.add(namespace)
        session.commit()
        session.refresh(namespace)
        logger.info(f"Namespace créé avec succès: ID={namespace.id}, name={final_name}, type={type}, oid={final_oid}")
        flash(request, f"Namespace '{final_name}' créé avec succès (ID: {namespace.id}, Type: {type}, OID: {final_oid or 'N/A'})", "success")
        return RedirectResponse(url=f"/admin/ght/{context_id}", status_code=303)
    except Exception as e:
        logger.error(f"Erreur création namespace: {type(e).__name__}: {str(e)}", exc_info=True)
        session.rollback()
        flash(request, f"Erreur lors de la création du namespace: {str(e)}", "error")
        return RedirectResponse(url=f"/admin/ght/{context_id}/namespaces/new", status_code=303)

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
        request,
        "namespace_detail.html",
        {
            "context": context,
            "namespace": namespace
        },
    )

@router.post("/{namespace_id}/edit")
async def edit_namespace(
    request: Request,
    context_id: int,
    namespace_id: int, 
    name: str = Form(default=""),
    description: str = Form(default=""),
    oid: str = Form(default=""),
    system: str = Form(...),
    type: str = Form(...),
    is_active: str = Form("true"),
    session: Session = Depends(get_session),
):
    """Modifie un namespace existant avec validation et auto-extraction de l'OID."""
    context = get_context_or_404(session, context_id)
    namespace = session.get(IdentifierNamespace, namespace_id)
    if not namespace or namespace.ght_context_id != context.id:
        raise HTTPException(status_code=404, detail="Namespace non trouvé")
    
    logger.info(f"Tentative de modification namespace ID={namespace_id}: type={type}, system={system}")
    
    # Validation et extraction automatique de l'OID
    is_valid, error_msg, extracted_oid = validate_and_extract_oid(system, oid)
    if not is_valid:
        logger.warning(f"Validation échouée: {error_msg}")
        flash(request, f"Erreur de validation : {error_msg}", "error")
        return RedirectResponse(url=f"/admin/ght/{context_id}/namespaces/{namespace_id}", status_code=303)
    
    # Utiliser l'OID extrait
    final_oid = extracted_oid
    
    # Générer le nom si non fourni (pour messages HL7v2/IHE PAM)
    final_name = generate_namespace_name(type, final_oid, name)
    
    logger.info(f"Namespace validé: name={final_name}, oid={final_oid}")
    
    namespace.name = final_name
    namespace.description = description if description else None
    namespace.oid = final_oid
    namespace.system = system
    namespace.type = type
    namespace.is_active = is_active.lower() in ('true', '1', 'yes', 'on')
    
    session.add(namespace)
    session.commit()
    session.refresh(namespace)
    logger.info(f"Namespace modifié avec succès: ID={namespace.id}, name={final_name}, oid={final_oid}")
    flash(request, f"Namespace '{final_name}' modifié avec succès (OID: {final_oid or 'N/A'})", "success")
    return RedirectResponse(url=f"/admin/ght/{context_id}/namespaces/{namespace.id}", status_code=303)