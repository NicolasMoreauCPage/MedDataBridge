"""Routes d'orchestration, import et cartographie de la structure."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.services.structure_tree import build_structure_tree
from app.services.structure_template_application import (
    StructureTemplateTargetNotFoundError,
    StructureTemplateValidationError,
    apply_structure_template as apply_structure_template_use_case,
)
from app.services.structure_details import (
    StructureEntityNotFoundError,
    UnknownStructureTypeError,
    get_structure_details as get_structure_details_use_case,
)
from app.services.mfn_importer import import_mfn
from app.services.vocabulary_lookup import get_vocabulary_options
from app.models_structure import (
    Chambre,
    EntiteGeographique,
    Lit,
    LocationServiceType,
    Pole,
    Service,
    StructureTemplate,
    UniteFonctionnelle,
    UniteHebergement,
)
from app.routers.structure_router_base import (
    DEFAULT_API_PAGE_SIZE as DEFAULT_API_PAGE_SIZE,
    MAX_API_PAGE_SIZE as MAX_API_PAGE_SIZE,
    api_router,
    execute_paginated as _execute_paginated,  # noqa: F401 - compatibilité historique
    get_templates_with_filters,
    redirect_router,
    router,
)
from app.routers import structure_availability as _availability_routes
from app.routers import structure_organization as _organization_routes
from app.routers import structure_rooms as _room_routes
from app.routers import structure_units as _unit_routes

logger = logging.getLogger(__name__)

# Compatibilité des imports historiques depuis ``app.routers.structure``.
create_entite_geographique = _organization_routes.create_entite_geographique
create_pole = _organization_routes.create_pole
create_service = _organization_routes.create_service
create_unite_fonctionnelle = _organization_routes.create_unite_fonctionnelle
delete_entite_geographique = _organization_routes.delete_entite_geographique
delete_pole = _organization_routes.delete_pole
delete_service = _organization_routes.delete_service
delete_unite_fonctionnelle = _organization_routes.delete_unite_fonctionnelle
edit_entite_geographique_form = _organization_routes.edit_entite_geographique_form
edit_pole_form = _organization_routes.edit_pole_form
edit_service_form = _organization_routes.edit_service_form
edit_unite_fonctionnelle_form = _organization_routes.edit_unite_fonctionnelle_form
get_pole_api = _organization_routes.get_pole_api
get_service_api = _organization_routes.get_service_api
get_unite_fonctionnelle_api = _organization_routes.get_unite_fonctionnelle_api
list_entites_geographiques = _organization_routes.list_entites_geographiques
list_entites_geographiques_api = _organization_routes.list_entites_geographiques_api
list_poles = _organization_routes.list_poles
list_poles_api = _organization_routes.list_poles_api
list_services = _organization_routes.list_services
list_services_api = _organization_routes.list_services_api
list_unites_fonctionnelles = _organization_routes.list_unites_fonctionnelles
list_unites_fonctionnelles_api = _organization_routes.list_unites_fonctionnelles_api
update_entite_geographique = _organization_routes.update_entite_geographique
update_pole = _organization_routes.update_pole
update_service = _organization_routes.update_service
update_unite_fonctionnelle = _organization_routes.update_unite_fonctionnelle
view_entite_geographique = _organization_routes.view_entite_geographique
view_pole = _organization_routes.view_pole
view_service = _organization_routes.view_service
view_unite_fonctionnelle = _organization_routes.view_unite_fonctionnelle

create_unite_hebergement = _unit_routes.create_unite_hebergement
delete_unite_hebergement = _unit_routes.delete_unite_hebergement
edit_unite_hebergement_form = _unit_routes.edit_unite_hebergement_form
list_unites_hebergement = _unit_routes.list_unites_hebergement
list_unites_hebergement_api = _unit_routes.list_unites_hebergement_api
new_unite_hebergement_form = _unit_routes.new_unite_hebergement_form
update_unite_hebergement = _unit_routes.update_unite_hebergement
view_unite_hebergement = _unit_routes.view_unite_hebergement

create_chambre = _room_routes.create_chambre
create_lit = _room_routes.create_lit
delete_chambre = _room_routes.delete_chambre
edit_chambre_form = _room_routes.edit_chambre_form
edit_lit_form = _room_routes.edit_lit_form
get_chambre_api = _room_routes.get_chambre_api
get_lit_api = _room_routes.get_lit_api
list_chambres = _room_routes.list_chambres
list_chambres_api = _room_routes.list_chambres_api
list_lits = _room_routes.list_lits
list_lits_api = _room_routes.list_lits_api
new_chambre_form = _room_routes.new_chambre_form
update_chambre = _room_routes.update_chambre
update_lit = _room_routes.update_lit
view_chambre = _room_routes.view_chambre
view_lit = _room_routes.view_lit

_fetch_available_lits = _availability_routes._fetch_available_lits
search_lits_disponibles = _availability_routes.search_lits_disponibles
structure_availability_search = _availability_routes.structure_availability_search

@api_router.get("/tree")
async def get_structure_tree(
    request: Request,
    session: Session = Depends(get_session),
    ej: Optional[int] = Query(None, description="ID de l'établissement juridique à filtrer"),
    eg_ids: Optional[str] = Query(None, description="Liste d'IDs d'entités géographiques séparés par des virgules")
):
    ej_context = ej
    # La requête est injectée par FastAPI : ne pas parcourir la pile d'appel
    # pour retrouver implicitement un contexte de session.
    if ej_context is None:
        ej_context = request.session.get("ej_context_id")
    eg_id_list = [int(id_str) for id_str in eg_ids.split(",")] if eg_ids else None
    return build_structure_tree(session, ej_context=ej_context, eg_ids=eg_id_list)


class StructureTemplateOut(BaseModel):
    """Schéma de sortie simplifié pour les templates de structure.

    On évite de renvoyer le payload JSON complet à ce stade (Phase 2.1),
    l'objectif principal étant d'alimenter la liste de choix du wizard.
    """

    id: int
    key: str
    name: str
    description: Optional[str] = None
    is_default: bool = False


@api_router.get("/templates", response_model=List[StructureTemplateOut])
def list_structure_templates(session: Session = Depends(get_session)):
    """Retourne la liste des templates de structure disponibles pour le wizard.

    Implémentation minimaliste : on lit les templates en base si présents,
    sinon on renvoie un petit set de templates par défaut (non persistés)
    pour garder le wizard pleinement fonctionnel même sans seed initial.
    """
    templates = session.exec(
        select(StructureTemplate)
        .order_by(StructureTemplate.key)
        .limit(500)
    ).all()
    items: List[StructureTemplateOut] = []

    if templates:
        for tpl in templates:
            items.append(
                StructureTemplateOut(
                    id=tpl.id,
                    key=tpl.key,
                    name=tpl.name,
                    description=tpl.description,
                    is_default=tpl.is_default,
                )
            )
        return items

    # Fallback : templates en mémoire si aucun en base (Phase 2.1)
    defaults = [
        StructureTemplateOut(id=1, key="chu", name="CHU", description="Centre Hospitalier Universitaire complexe", is_default=True),
        StructureTemplateOut(id=2, key="ch", name="Centre Hospitalier", description="Établissement général polyvalent", is_default=False),
        StructureTemplateOut(id=3, key="clinique", name="Clinique", description="Structure privée à forte composante ambulatoire", is_default=False),
    ]
    return defaults


@api_router.get("/templates/{template_id}")
def get_structure_template(template_id: int, session: Session = Depends(get_session)):
    """Retourne le détail complet d'un template, y compris son payload JSON.

    Utilisé par le wizard à l'étape 2 pour charger la structure du template choisi.
    """
    template = session.get(StructureTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template non trouvé")

    return {
        "id": template.id,
        "key": template.key,
        "name": template.name,
        "description": template.description,
        "template_type": template.template_type,
        "is_default": template.is_default,
        "payload": template.payload,
    }


# ============ APPLY TEMPLATE ============

class UfPayload(BaseModel):
    """Unité Fonctionnelle dans le payload du wizard."""
    name: str
    code_um: Optional[str] = None
    type: Optional[str] = "mco"  # mco, ssr, psy, had


class ServicePayload(BaseModel):
    """Service dans le payload du wizard."""
    name: str
    short_name: Optional[str] = None
    type: Optional[str] = "service"
    ufs: List[UfPayload] = []


class PolePayload(BaseModel):
    """Pôle dans le payload du wizard."""
    name: str
    short_name: Optional[str] = None
    type: Optional[str] = "pole"
    services: List[ServicePayload] = []


class UhPayload(BaseModel):
    """Unité d'Hébergement dans le payload du wizard."""
    name: str
    uf_ref: Optional[str] = None
    chambres: int = 0
    lits: int = 0


class ApplyTemplateRequest(BaseModel):
    """Requête pour appliquer un template modifié et créer la structure."""
    eg_id: int  # Entité Géographique cible
    payload: dict  # Contient {poles: [...]}
    uhs: List[UhPayload] = []


class ApplyTemplateResponse(BaseModel):
    """Réponse après application du template."""
    success: bool
    message: str
    created_entities: dict


@api_router.post("/apply-template", response_model=ApplyTemplateResponse)
async def apply_structure_template(
    request: ApplyTemplateRequest,
    session: Session = Depends(get_session)
):
    """Applique un template modifié et crée les entités de structure en base.

    Crée les Poles, Services, UniteFonctionnelles à partir du payload JSON
    modifié par l'utilisateur dans le wizard. Associe le tout à l'EG ciblée.
    """
    try:
        target_name, created = apply_structure_template_use_case(
            session,
            eg_id=request.eg_id,
            payload=request.payload,
            hosting_units=request.uhs,
        )
    except StructureTemplateTargetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StructureTemplateValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Erreur lors de l'application du template")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la création de la structure: {exc}",
        ) from exc

    return ApplyTemplateResponse(
        success=True,
        message=f"Structure créée avec succès pour {target_name}",
        created_entities=created,
    )

@api_router.get("/details/{type}/{id}")
def get_structure_details(
    type: str,
    id: int,
    session: Session = Depends(get_session),
):
    try:
        return get_structure_details_use_case(
            session,
            entity_type=type,
            entity_id=id,
        )
    except UnknownStructureTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StructureEntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class BulkItem(BaseModel):
    type: str
    id: int


class BulkActionRequest(BaseModel):
    action: str
    items: List[BulkItem]


@api_router.post("/bulk-action")
async def bulk_action(
    payload: BulkActionRequest,
    session: Session = Depends(get_session),
):
    """Applique une action en lot (activer/désactiver) sur des structures.

    Pour l'instant, seules les actions suivantes sont supportées :
    - "activate"   → status = "active"
    - "deactivate" → status = "inactive"
    """

    action_map = {
        "activate": "active",
        "deactivate": "inactive",
    }

    if payload.action not in action_map:
        raise HTTPException(status_code=400, detail="Action invalide")

    status_value = action_map[payload.action]

    model_map = {
        'eg': EntiteGeographique,
        'pole': Pole,
        'service': Service,
        'uf': UniteFonctionnelle,
        'uh': UniteHebergement,
        'chambre': Chambre,
        'lit': Lit,
    }

    updated = 0
    not_found: List[dict] = []
    invalid_types: List[str] = []

    for item in payload.items:
        model = model_map.get(item.type)
        if not model:
            invalid_types.append(item.type)
            continue

        entity = session.get(model, item.id)
        if not entity:
            not_found.append({"type": item.type, "id": item.id})
            continue

        if hasattr(entity, "status"):
            setattr(entity, "status", status_value)
            updated += 1

    if updated:
        session.commit()

    return {
        "action": payload.action,
        "status": status_value,
        "updated": updated,
        "not_found": not_found,
        "invalid_types": list(set(invalid_types)),
    }


@router.get("", response_class=HTMLResponse)
async def structure_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    ej: Optional[int] = Query(None, description="ID de l'établissement juridique à filtrer")
):
    structure_type_opts = get_vocabulary_options("structure-type") or [
        {"value": "pole", "label": "Pôles"},
        {"value": "service", "label": "Services"},
        {"value": "uf", "label": "Unités Fonctionnelles"},
        {"value": "uh", "label": "Unités d'Hébergement"}
    ]
    structure_status_opts = get_vocabulary_options("structure-status") or [
        {"value": "active", "label": "Actif"},
        {"value": "inactive", "label": "Inactif"}
    ]
    context = {
        "request": request,
        "service_types": [stype.value for stype in LocationServiceType],
        "structure_type_options": structure_type_opts,
        "structure_status_options": structure_status_opts,
    }
    
    # Patch: always filter by EJ context if available
    ej_context = ej
    # Try to get EJ from session if not provided
    if not ej_context:
        ej_context = request.session.get("ej_context_id")
    if ej_context:
        egs = session.exec(
            select(EntiteGeographique)
            .where(EntiteGeographique.entite_juridique_id == ej_context)
        ).all()
        context["filtered_ej_id"] = ej_context
        context["filtered_egs"] = [eg.id for eg in egs]
    else:
        # If no EJ context, show all EGs (fallback for when no EJ is selected)
        egs = session.exec(select(EntiteGeographique)).all()
        context["filtered_egs"] = [eg.id for eg in egs]
        context["no_ej_context"] = True  # Flag to show message in template
    return get_templates_with_filters(request).TemplateResponse(request, "structure_new.html", context)


@router.get("/wizard", response_class=HTMLResponse)
async def structure_wizard_page(
    request: Request,
    session: Session = Depends(get_session),
):
    """Page de wizard de saisie assistée pour créer une structure à partir de templates."""
    context = {"request": request}
    # On réutilise la même logique de filtrage EJ que pour la page principale
    ej_context = request.session.get("ej_context_id")
    if ej_context:
        egs = session.exec(
            select(EntiteGeographique)
            .where(EntiteGeographique.entite_juridique_id == ej_context)
        ).all()
        context["filtered_ej_id"] = ej_context
        context["filtered_egs"] = [eg.id for eg in egs]
    else:
        egs = session.exec(select(EntiteGeographique)).all()
        context["filtered_egs"] = [eg.id for eg in egs]
        context["no_ej_context"] = True
    # L'EG est un choix métier de l'assistant ; exposer ses libellés permet de
    # supprimer la saisie manuelle et risquée d'un identifiant à la fin.
    context["target_egs"] = egs
    context["selected_eg_id"] = request.session.get("eg_context_id")
    return get_templates_with_filters(request).TemplateResponse(request, "structure_wizard.html", context)

@router.post("/import/hl7")
async def import_structure_hl7(
    request: Request,
    session: Session = Depends(get_session),
):
    """Importe un message HL7 MFN^M05 (text/plain) dans le GHT courant.

    - Le GHT est déterminé via le middleware de contexte (request.state.ght_context).
    - Retourne un JSON de synthèse: nombre d'EJ, d'EG et de services créés/mis à jour.
    """
    # Vérifier contexte GHT
    ght = getattr(request.state, "ght_context", None)
    if not ght:
        raise HTTPException(status_code=400, detail="Contexte GHT manquant")

    try:
        body = await request.body()
        text = body.decode("utf-8", errors="ignore")
    except Exception:
        raise HTTPException(status_code=400, detail="Impossible de lire le payload text/plain")

    if not text or "MSH" not in text or "MFN^M05" not in text:
        # On reste permissif: certains extracts peuvent ne pas inclure ^M05
        if not text:
            raise HTTPException(status_code=400, detail="Payload vide")

    summary = import_mfn(text, session, ght)
    return {"status": "ok", "created": summary}

# --- Entité Géographique ---

@router.get("/{type}/{id}/map", response_class=HTMLResponse)
async def view_structure_map(
    type: str,
    id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Affiche le plan de lits de l'entité de structure, restreint à son périmètre
    (redirige vers la vue plan-lits déjà fonctionnelle, filtrée par entité).
    """
    # Mapping des types vers les modèles. Inclut les formes plurielles utilisées par les
    # entités dont l'URL singulière est redirigée par ailleurs (/pole/* -> /poles/*,
    # /service/* -> /services/*), qui atteignent donc cette route sous forme plurielle.
    model_map = {
        "eg": (EntiteGeographique, "eg"),
        "pole": (Pole, "pole"),
        "poles": (Pole, "pole"),
        "service": (Service, "service"),
        "services": (Service, "service"),
        "uf": (UniteFonctionnelle, "uf"),
        "uh": (UniteHebergement, "uh"),
        "chambre": (Chambre, "chambre"),
        "chambres": (Chambre, "chambre"),
        "lit": (Lit, "lit"),
        "lits": (Lit, "lit"),
    }

    mapping = model_map.get(type)
    if not mapping:
        raise HTTPException(status_code=404, detail=f"Type de structure '{type}' non reconnu")
    model, canonical_type = mapping

    # Récupérer l'entité
    entity = session.get(model, id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"{type.upper()} #{id} non trouvé")

    return RedirectResponse(url=f"/mouvements/plan-lits?entity_type={canonical_type}&entity_id={id}", status_code=302)


# ============================================================================
# REDIRECTIONS SINGULIER → PLURIEL (à la fin pour ne pas capturer les routes)
# Utilise redirect_router sans dépendance GHT pour permettre la redirection
# ============================================================================

@redirect_router.get("/pole/{rest:path}")
async def redirect_pole_singular_get(rest: str):
    """Redirection GET de /pole/* vers /poles/*"""
    return RedirectResponse(url=f"/structure/poles/{rest}", status_code=301)

@redirect_router.post("/pole/{rest:path}")
async def redirect_pole_singular_post(rest: str):
    """Redirection POST de /pole/* vers /poles/*"""
    return RedirectResponse(url=f"/structure/poles/{rest}", status_code=308)

@redirect_router.get("/service/{rest:path}")
async def redirect_service_singular_get(rest: str):
    """Redirection GET de /service/* vers /services/*"""
    return RedirectResponse(url=f"/structure/services/{rest}", status_code=301)

@redirect_router.post("/service/{rest:path}")
async def redirect_service_singular_post(rest: str):
    """Redirection POST de /service/* vers /services/*"""
    return RedirectResponse(url=f"/structure/services/{rest}", status_code=308)

@redirect_router.get("/uf/{id:int}")
async def redirect_uf_singular_get_detail(id: int):
    """Redirection GET de /uf/{id} vers /ufs/{id}"""
    return RedirectResponse(url=f"/structure/ufs/{id}", status_code=301)

@redirect_router.get("/uf/{id:int}/edit")
async def redirect_uf_singular_get_edit(id: int):
    """Redirection GET de /uf/{id}/edit vers /ufs/{id}/edit"""
    return RedirectResponse(url=f"/structure/ufs/{id}/edit", status_code=301)

@redirect_router.post("/uf/{id:int}")
async def redirect_uf_singular_post_update(id: int):
    """Redirection POST de /uf/{id} vers /ufs/{id}"""
    return RedirectResponse(url=f"/structure/ufs/{id}", status_code=308)

@redirect_router.post("/uf/{id:int}/delete")
async def redirect_uf_singular_post_delete(id: int):
    """Redirection POST de /uf/{id}/delete vers /ufs/{id}/delete"""
    return RedirectResponse(url=f"/structure/ufs/{id}/delete", status_code=308)

@redirect_router.get("/chambre/{rest:path}")
async def redirect_chambre_singular_get(rest: str):
    """Redirection GET de /chambre/* vers /chambres/*"""
    return RedirectResponse(url=f"/structure/chambres/{rest}", status_code=301)

@redirect_router.post("/chambre/{rest:path}")
async def redirect_chambre_singular_post(rest: str):
    """Redirection POST de /chambre/* vers /chambres/*"""
    return RedirectResponse(url=f"/structure/chambres/{rest}", status_code=308)

@redirect_router.get("/lit/{rest:path}")
async def redirect_lit_singular_get(rest: str):
    """Redirection GET de /lit/* vers /lits/*"""
    return RedirectResponse(url=f"/structure/lits/{rest}", status_code=301)

@redirect_router.post("/lit/{rest:path}")
async def redirect_lit_singular_post(rest: str):
    """Redirection POST de /lit/* vers /lits/*"""
    return RedirectResponse(url=f"/structure/lits/{rest}", status_code=308)
