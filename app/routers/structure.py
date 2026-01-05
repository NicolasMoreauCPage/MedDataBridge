import logging
from typing import List, Optional
from unittest.mock import Mock as MockType
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request as FastAPIRequest
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from app.db import get_session
from app.models_endpoints import SystemEndpoint
from app.services.fhir_structure import entity_to_fhir_location
from app.services.fhir_transport import post_fhir_bundle
from app.services.structure_schedule import (
    apply_scheduled_status,
    form_datetime_to_hl7,
    hl7_to_form_datetime,
)
from app.services.mfn_importer import import_mfn
from app.dependencies.ght import require_ght_context
from app.services.vocabulary_lookup import get_vocabulary_options

logger = logging.getLogger(__name__)
from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit,
    LocationStatus, LocationMode, LocationPhysicalType, LocationServiceType
)

# Route principale pour les pages web

def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter(
    prefix="/structure",
    tags=["structure"],
    # NOTE: GHT context dependency removed from router level
    # Individual routes that need it can add the dependency
)

# Route API pour les endpoints JSON
api_router = APIRouter(
    prefix="/api/structure",
    tags=["structure_api"],
    dependencies=[Depends(require_ght_context)],
)

# Router pour les redirections (sans dépendance GHT pour permettre la redirection)
redirect_router = APIRouter(
    prefix="/structure",
    tags=["structure_redirects"],
)



# ============================================================================
# REDIRECTIONS SINGULIER → PLURIEL
# Pour éviter les erreurs 404 quand on tape l'URL au singulier
# Ces routes doivent être définies APRÈS les routes spécifiques pour ne pas
# interférer avec la résolution des routes
# ============================================================================

# REMARQUE: Ces redirections seront ajoutées à la fin du fichier pour éviter
# de capturer les routes valides


@api_router.get("/tree")
async def get_structure_tree(
    session: Session = Depends(get_session),
    ej: Optional[int] = Query(None, description="ID de l'établissement juridique à filtrer"),
    eg_ids: Optional[str] = Query(None, description="Liste d'IDs d'entités géographiques séparés par des virgules")
):
    # Apply scheduled status updates
    changed = False
    for model in (Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit):
        entities = session.exec(select(model)).all()
        if apply_scheduled_status(entities):
            changed = True
    if changed:
        session.commit()
    
    # Strict EJ filtering: if EJ context is present, only return EGs for that EJ
    query = select(EntiteGeographique)
    ej_context = ej
    # Try to get EJ from session if not provided
    if not ej_context:
        # Get request from middleware context
        import inspect
        request = None
        for frame in inspect.stack():
            if "request" in frame.frame.f_locals:
                request = frame.frame.f_locals["request"]
                break
        if request:
            ej_context = request.session.get("ej_context_id")
    eg_id_list = None
    if eg_ids:
        eg_id_list = [int(id_str) for id_str in eg_ids.split(',')]
        query = query.where(EntiteGeographique.id.in_(eg_id_list))
    elif ej_context is not None:
        query = query.where(EntiteGeographique.entite_juridique_id == ej_context)
    # If strict EJ filtering is requested and no EGs match, Renvoie empty list
    # (prevents Solution de repli to all EGs)
    query = (query
        .options(selectinload(EntiteGeographique.poles)
            .selectinload(Pole.services)
            .selectinload(Service.unites_fonctionnelles)
            .selectinload(UniteFonctionnelle.unites_hebergement)
            .selectinload(UniteHebergement.chambres)
            .selectinload(Chambre.lits)))
    egs = session.exec(query).all()
    # If EJ context is present and no EGs match, Renvoie []
    if (ej_context is not None or eg_id_list) and not egs:
        return []
    # Build tree structure
    tree = []
    for eg in egs:
        eg_node = {
            "id": eg.id,
            "name": eg.name,
            "type": "eg",
            "poles": [],
            "services": [],
            "ufs": [],
            "unites_hebergement": [],
            "chambres": [],
            "lits": []
        }
        for pole in eg.poles:
            pole_node = {
                "id": pole.id,
                "name": pole.name,
                "type": "pole",
                "services": [],
                "ufs": [],
                "unites_hebergement": [],
                "chambres": [],
                "lits": []
            }
            for service in pole.services:
                service_node = {
                    "id": service.id,
                    "name": service.name,
                    "type": "service",
                    "ufs": [],
                    "unites_hebergement": [],
                    "chambres": [],
                    "lits": []
                }
                for uf in service.unites_fonctionnelles:
                    uf_node = {
                        "id": uf.id,
                        "name": uf.name,
                        "type": "uf",
                        "unites_hebergement": [],
                        "chambres": [],
                        "lits": []
                    }
                    for uh in uf.unites_hebergement:
                        uh_node = {
                            "id": uh.id,
                            "name": uh.name,
                            "type": "uh",
                            "chambres": [],
                            "lits": []
                        }
                        for chambre in uh.chambres:
                            chambre_node = {
                                "id": chambre.id,
                                "name": chambre.name,
                                "type": "chambre",
                                "lits": []
                            }
                            for lit in chambre.lits:
                                lit_node = {
                                    "id": lit.id,
                                    "name": lit.name,
                                    "type": "lit"
                                }
                                chambre_node["lits"].append(lit_node)
                            uh_node["chambres"].append(chambre_node)
                        uf_node["unites_hebergement"].append(uh_node)
                    service_node["ufs"].append(uf_node)
                pole_node["services"].append(service_node)
            eg_node["poles"].append(pole_node)
        tree.append(eg_node)
    return tree

@api_router.get("/details/{type}/{id}")
async def get_structure_details(
    type: str,
    id: int,
    session: Session = Depends(get_session)
):
    # Sélectionner l'entité appropriée selon le type
    model_map = {
        'eg': EntiteGeographique,
        'pole': Pole,
        'service': Service,
        'uf': UniteFonctionnelle,
        'uh': UniteHebergement,
        'chambre': Chambre,
        'lit': Lit
    }
    
    model = model_map.get(type)
    if not model:
        raise HTTPException(status_code=400, detail="Type invalide")
        
    entity = session.get(model, id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entité non trouvée")
        
    # Construire un dictionnaire avec les détails
    details = {
        "id": entity.id,
        "name": entity.name,
        "type": type,
        "identifier": getattr(entity, 'identifier', None),
        "description": getattr(entity, 'description', None),
        "status": getattr(entity, 'status', 'active')
    }
    
    # Ajouter les champs spécifiques selon le type
    if type == 'service':
        details["service_type"] = getattr(entity, 'service_type', None)
    elif type == 'uf':
        details["uf_type"] = getattr(entity, 'uf_type', None)
        
    return details


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
@router.get("/eg", response_class=HTMLResponse)
async def list_entites_geographiques(
    request: Request,
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(EntiteGeographique)
    
    # Filtrer par contexte EJ si présent
    if hasattr(request.state, 'ej_context') and request.state.ej_context:
        query = query.where(EntiteGeographique.entite_juridique_id == request.state.ej_context.id)
    
    if q:
        like = f"%{q}%"
        query = query.where(
            (EntiteGeographique.name.ilike(like))
            | (EntiteGeographique.identifier.ilike(like))
            | (EntiteGeographique.finess.ilike(like))
        )
    
    egs = session.exec(query.order_by(EntiteGeographique.name)).all()
    
    return get_templates_with_filters(request).TemplateResponse(
        "structure/eg_list.html",
        {
            "request": request,
            "entites_geographiques": egs,
            "search_term": q,
        },
    )

@router.get("/api/eg", response_model=List[EntiteGeographique])
async def list_entites_geographiques_api(
    session: Session = Depends(get_session),
    skip: int = 0,
    limit: int = 100
):
    return session.exec(select(EntiteGeographique).offset(skip).limit(limit)).all()

@router.post("/eg", response_model=EntiteGeographique)
async def create_entite_geographique(
    eg: EntiteGeographique,
    session: Session = Depends(get_session)
):
    session.add(eg)
    session.commit()
    session.refresh(eg)
    
    return eg

@router.get("/eg/{eg_id}", response_class=HTMLResponse)
async def view_entite_geographique(
    request: Request,
    eg_id: int,
    session: Session = Depends(get_session)
):
    eg = session.get(EntiteGeographique, eg_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Entité géographique non trouvée")
    
    # Charger les pôles associés
    poles = session.exec(
        select(Pole).where(Pole.entite_geo_id == eg_id).order_by(Pole.name)
    ).all()
    
    return get_templates_with_filters(request).TemplateResponse(
        "structure/eg_detail.html",
        {
            "request": request,
            "eg": eg,
            "poles": poles,
        },
    )

@router.get("/eg/{eg_id}/edit", response_class=HTMLResponse)
async def edit_entite_geographique_form(
    request: Request,
    eg_id: int,
    session: Session = Depends(get_session)
):
    eg = session.get(EntiteGeographique, eg_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Entité géographique non trouvée")
    
    return get_templates_with_filters(request).TemplateResponse(
        "structure/eg_edit.html",
        {
            "request": request,
            "eg": eg,
        },
    )

@router.post("/eg/{eg_id}")
async def update_entite_geographique(
    eg_id: int,
    name: str = Form(...),
    identifier: Optional[str] = Form(None),
    finess: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    eg = session.get(EntiteGeographique, eg_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Entité géographique non trouvée")
    
    eg.name = name
    if identifier is not None:
        eg.identifier = identifier
    if finess is not None:
        eg.finess = finess
    
    session.add(eg)
    session.commit()
    session.refresh(eg)
    return RedirectResponse(url=f"/structure/eg/{eg_id}", status_code=303)

@router.post("/eg/{eg_id}/delete")
async def delete_entite_geographique(
    eg_id: int,
    session: Session = Depends(get_session)
):
    eg = session.get(EntiteGeographique, eg_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Entité géographique non trouvée")
    
    session.delete(eg)
    session.commit()
    return RedirectResponse(url="/structure/eg", status_code=303)

# --- Pôles ---
@router.get("/poles", response_class=HTMLResponse)
async def list_poles(
    request: Request,
    session: Session = Depends(get_session),
    eg_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(Pole)
    if eg_id:
        query = query.where(Pole.entite_geo_id == eg_id)
    if q:
        like = f"%{q}%"
        query = query.where(
            (Pole.name.ilike(like))
            | (Pole.identifier.ilike(like))
        )
    
    poles = session.exec(query.order_by(Pole.name)).all()
    if apply_scheduled_status(poles):
        session.commit()
    
    egs = session.exec(select(EntiteGeographique).order_by(EntiteGeographique.name)).all()
    eg_map = {eg.id: eg.name for eg in egs}
    
    return get_templates_with_filters(request).TemplateResponse(
        "structure/poles_list.html",
        {
            "request": request,
            "poles": poles,
            "entites_geographiques": egs,
            "eg_map": eg_map,
            "selected_eg_id": eg_id,
            "search_term": q,
        },
    )

@router.get("/api/poles", response_model=List[Pole])
async def list_poles_api(
    session: Session = Depends(get_session),
    eg_id: Optional[int] = None
):
    query = select(Pole)
    if eg_id:
        query = query.where(Pole.entite_geo_id == eg_id)
    poles = session.exec(query).all()
    if apply_scheduled_status(poles):
        session.commit()
    return poles

@api_router.get("/poles/{pole_id}")
def get_pole_api(
    pole_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint retournant un pôle avec ses valeurs effectives"""
    pole = session.get(Pole, pole_id)
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")

    # Retourner les données avec valeurs effectives
    return {
        "id": pole.id,
        "identifier": pole.identifier,
        "name": pole.name,
        "short_name": pole.short_name,
        "description": pole.description,

        # Valeurs locales
        "local_operational_status": pole.operational_status,
        "local_status": pole.status,
        "local_mode": pole.mode,
        "local_physical_type": pole.physical_type,
        "local_etage": pole.etage,
        "local_aile": pole.aile,
        "local_opening_date": pole.opening_date,
        "local_activation_date": pole.activation_date,
        "local_closing_date": pole.closing_date,
        "local_deactivation_date": pole.deactivation_date,

        # Valeurs effectives (avec héritage)
        "effective_operational_status": pole.get_effective_operational_status(),
        "effective_status": pole.get_effective_status(),
        "effective_mode": pole.get_effective_mode(),
        "effective_physical_type": pole.get_effective_physical_type(),
        "effective_etage": pole.get_effective_etage(),
        "effective_aile": pole.get_effective_aile(),
        "effective_opening_date": pole.get_effective_opening_date(),
        "effective_activation_date": pole.get_effective_activation_date(),
        "effective_closing_date": pole.get_effective_closing_date(),
        "effective_deactivation_date": pole.get_effective_deactivation_date(),

        # Métadonnées d'héritage
        "inheritance_info": {
            "operational_status_inherited": pole.operational_status != pole.get_effective_operational_status() and pole.get_effective_operational_status() is not None,
            "status_inherited": pole.status != pole.get_effective_status() and pole.get_effective_status() is not None,
            "mode_inherited": pole.mode != pole.get_effective_mode() and pole.get_effective_mode() is not None,
            "physical_type_inherited": pole.physical_type != pole.get_effective_physical_type() and pole.get_effective_physical_type() is not None,
            "etage_inherited": pole.etage != pole.get_effective_etage() and pole.get_effective_etage() is not None,
            "aile_inherited": pole.aile != pole.get_effective_aile() and pole.get_effective_aile() is not None,
            "opening_date_inherited": pole.opening_date != pole.get_effective_opening_date() and pole.get_effective_opening_date() is not None,
            "activation_date_inherited": pole.activation_date != pole.get_effective_activation_date() and pole.get_effective_activation_date() is not None,
            "closing_date_inherited": pole.closing_date != pole.get_effective_closing_date() and pole.get_effective_closing_date() is not None,
            "deactivation_date_inherited": pole.deactivation_date != pole.get_effective_deactivation_date() and pole.get_effective_deactivation_date() is not None,
        },

        # Relations
        "entite_geo_id": pole.entite_geo_id,
        "entite_geographique": {
            "id": pole.entite_geographique.id,
            "name": pole.entite_geographique.name,
            "identifier": pole.entite_geographique.identifier
        } if pole.entite_geographique else None,

        # Statistiques
        "stats": {
            "services_count": len(pole.services) if hasattr(pole, 'services') else 0,
        },

        # Timestamps
        "created_at": pole.created_at,
        "updated_at": pole.updated_at,
    }

@router.post("/poles", response_model=Pole)
async def create_pole(
    pole: Pole,
    session: Session = Depends(get_session)
):
    apply_scheduled_status([pole])
    session.add(pole)
    session.commit()
    session.refresh(pole)
    return pole

@router.get("/poles/{pole_id}", response_class=HTMLResponse)
async def view_pole(
    request: Request,
    pole_id: int,
    session: Session = Depends(get_session)
):
    pole = session.get(Pole, pole_id)
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")
    services = session.exec(select(Service).where(Service.pole_id == pole_id).order_by(Service.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        "structure/pole_detail.html",
        {"request": request, "pole": pole, "services": services},
    )

@router.get("/poles/{pole_id}/edit", response_class=HTMLResponse)
async def edit_pole_form(
    request: Request,
    pole_id: int,
    session: Session = Depends(get_session)
):
    pole = session.get(Pole, pole_id)
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")
    egs = session.exec(select(EntiteGeographique).order_by(EntiteGeographique.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        "structure/pole_form.html",
        {"request": request, "pole": pole, "entites_geographiques": egs},
    )

@router.post("/poles/{pole_id}")
async def update_pole(
    pole_id: int,
    name: str = Form(...),
    identifier: Optional[str] = Form(None),
    entite_geo_id: Optional[int] = Form(None),
    session: Session = Depends(get_session),
):
    pole = session.get(Pole, pole_id)
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")
    pole.name = name
    if identifier is not None:
        pole.identifier = identifier
    if entite_geo_id:
        pole.entite_geo_id = int(entite_geo_id)
    apply_scheduled_status([pole])
    session.add(pole)
    session.commit()
    return RedirectResponse(url=f"/structure/poles/{pole_id}", status_code=303)

@router.post("/poles/{pole_id}/delete")
async def delete_pole(
    pole_id: int,
    session: Session = Depends(get_session)
):
    pole = session.get(Pole, pole_id)
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")
    session.delete(pole)
    session.commit()
    return RedirectResponse(url="/structure/poles", status_code=303)

# --- Services ---
@router.get("/services", response_class=HTMLResponse)
async def list_services(
    request: Request,
    session: Session = Depends(get_session),
    pole_id: Optional[int] = Query(None),
    service_type: Optional[LocationServiceType] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(Service)
    if pole_id:
        query = query.where(Service.pole_id == pole_id)
    if service_type:
        query = query.where(Service.service_type == service_type)
    if q:
        like = f"%{q}%"
        query = query.where(
            (Service.name.ilike(like))
            | (Service.identifier.ilike(like))
        )
    
    services = session.exec(query.order_by(Service.name)).all()
    if apply_scheduled_status(services):
        session.commit()
    
    poles = session.exec(select(Pole).order_by(Pole.name)).all()
    pole_map = {pole.id: pole.name for pole in poles}
    
    return get_templates_with_filters(request).TemplateResponse(
        "structure/services_list.html",
        {
            "request": request,
            "services": services,
            "poles": poles,
            "pole_map": pole_map,
            "service_types": LocationServiceType,
            "selected_pole_id": pole_id,
            "selected_service_type": service_type.value if service_type else None,
            "search_term": q,
        },
    )

@router.get("/api/services", response_model=List[Service])
async def list_services_api(
    session: Session = Depends(get_session),
    pole_id: Optional[int] = None,
    service_type: Optional[LocationServiceType] = None
):
    query = select(Service)
    if pole_id:
        query = query.where(Service.pole_id == pole_id)
    if service_type:
        query = query.where(Service.service_type == service_type)
    services = session.exec(query).all()
    if apply_scheduled_status(services):
        session.commit()
    return services

@api_router.get("/services/{service_id}")
def get_service_api(
    service_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint retournant un service avec ses valeurs effectives"""
    service = session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")

    # Retourner les données avec valeurs effectives
    return {
        "id": service.id,
        "identifier": service.identifier,
        "name": service.name,
        "short_name": service.short_name,
        "description": service.description,
        "service_type": service.service_type,

        # Valeurs locales
        "local_operational_status": service.operational_status,
        "local_status": service.status,
        "local_mode": service.mode,
        "local_physical_type": service.physical_type,
        "local_etage": service.etage,
        "local_aile": service.aile,
        "local_type_chambre": service.type_chambre,
        "local_opening_date": service.opening_date,
        "local_activation_date": service.activation_date,
        "local_closing_date": service.closing_date,
        "local_deactivation_date": service.deactivation_date,

        # Valeurs effectives (avec héritage)
        "effective_operational_status": service.get_effective_operational_status(),
        "effective_status": service.get_effective_status(),
        "effective_mode": service.get_effective_mode(),
        "effective_physical_type": service.get_effective_physical_type(),
        "effective_etage": service.get_effective_etage(),
        "effective_aile": service.get_effective_aile(),
        "effective_type_chambre": service.get_effective_type_chambre(),
        "effective_opening_date": service.get_effective_opening_date(),
        "effective_activation_date": service.get_effective_activation_date(),
        "effective_closing_date": service.get_effective_closing_date(),
        "effective_deactivation_date": service.get_effective_deactivation_date(),

        # Métadonnées d'héritage
        "inheritance_info": {
            "operational_status_inherited": service.operational_status != service.get_effective_operational_status() and service.get_effective_operational_status() is not None,
            "status_inherited": service.status != service.get_effective_status() and service.get_effective_status() is not None,
            "mode_inherited": service.mode != service.get_effective_mode() and service.get_effective_mode() is not None,
            "physical_type_inherited": service.physical_type != service.get_effective_physical_type() and service.get_effective_physical_type() is not None,
            "etage_inherited": service.etage != service.get_effective_etage() and service.get_effective_etage() is not None,
            "aile_inherited": service.aile != service.get_effective_aile() and service.get_effective_aile() is not None,
            "type_chambre_inherited": service.type_chambre != service.get_effective_type_chambre() and service.get_effective_type_chambre() is not None,
            "opening_date_inherited": service.opening_date != service.get_effective_opening_date() and service.get_effective_opening_date() is not None,
            "activation_date_inherited": service.activation_date != service.get_effective_activation_date() and service.get_effective_activation_date() is not None,
            "closing_date_inherited": service.closing_date != service.get_effective_closing_date() and service.get_effective_closing_date() is not None,
            "deactivation_date_inherited": service.deactivation_date != service.get_effective_deactivation_date() and service.get_effective_deactivation_date() is not None,
        },

        # Relations
        "pole_id": service.pole_id,
        "pole": {
            "id": service.pole.id,
            "name": service.pole.name,
            "identifier": service.pole.identifier
        } if service.pole else None,

        # Statistiques
        "stats": {
            "unites_fonctionnelles_count": (lambda obj: 0 if obj is None or isinstance(obj, MockType) else (len(obj) if hasattr(obj, '__len__') else (sum(1 for _ in obj) if obj is not None else 0)))(getattr(service, 'unites_fonctionnelles', None)),
        },

        # Timestamps
        "created_at": service.created_at,
        "updated_at": service.updated_at,
    }

@router.post("/services", response_model=Service)
async def create_service(
    service: Service,
    session: Session = Depends(get_session)
):
    apply_scheduled_status([service])
    session.add(service)
    session.commit()
    session.refresh(service)
    return service

@router.get("/services/{service_id}", response_class=HTMLResponse)
async def view_service(
    request: Request,
    service_id: int,
    session: Session = Depends(get_session)
):
    service = session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")
    ufs = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service_id).order_by(UniteFonctionnelle.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        "structure/service_detail.html",
        {"request": request, "service": service, "ufs": ufs, "service_types": LocationServiceType},
    )

@router.get("/services/{service_id}/edit", response_class=HTMLResponse)
async def edit_service_form(
    request: Request,
    service_id: int,
    session: Session = Depends(get_session)
):
    service = session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")
    poles = session.exec(select(Pole).order_by(Pole.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        "structure/service_form.html",
        {"request": request, "service": service, "poles": poles, "service_types": [t.value for t in LocationServiceType]},
    )

@router.post("/services/{service_id}")
async def update_service(
    service_id: int,
    name: str = Form(...),
    identifier: Optional[str] = Form(None),
    pole_id: Optional[int] = Form(None),
    service_type: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    service = session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")
    service.name = name
    if identifier is not None:
        service.identifier = identifier
    if pole_id:
        service.pole_id = int(pole_id)
    if service_type:
        service.service_type = LocationServiceType(service_type)
    apply_scheduled_status([service])
    session.add(service)
    session.commit()
    return RedirectResponse(url=f"/structure/services/{service_id}", status_code=303)

@router.post("/services/{service_id}/delete")
async def delete_service(
    service_id: int,
    session: Session = Depends(get_session)
):
    service = session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")
    session.delete(service)
    session.commit()
    return RedirectResponse(url="/structure/services", status_code=303)

# --- Unités Fonctionnelles ---
@router.get("/ufs", response_class=HTMLResponse)
async def list_unites_fonctionnelles(
    request: Request,
    session: Session = Depends(get_session),
    service_id: Optional[int] = Query(None),
    service_type: Optional[LocationServiceType] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(UniteFonctionnelle)
    if service_id:
        query = query.where(UniteFonctionnelle.service_id == service_id)
    if service_type:
        service_ids = session.exec(
            select(Service.id).where(Service.service_type == service_type)
        ).all()
        if service_ids:
            query = query.where(UniteFonctionnelle.service_id.in_(service_ids))
        else:
            query = query.where(False)  # Aucun service ne correspond
    if q:
        like = f"%{q}%"
        query = query.where(
            (UniteFonctionnelle.name.ilike(like))
            | (UniteFonctionnelle.identifier.ilike(like))
        )

    ufs = session.exec(query.order_by(UniteFonctionnelle.name)).all()
    changed = apply_scheduled_status(ufs)
    services = session.exec(select(Service).order_by(Service.name)).all()
    if apply_scheduled_status(services):
        changed = True
    if changed:
        session.commit()
    service_map = {service.id: service.name for service in services}

    return get_templates_with_filters(request).TemplateResponse(
        "structure/ufs.html",
        {
            "request": request,
            "unites_fonctionnelles": ufs,
            "services": services,
            "service_map": service_map,
            "service_type_labels": {
                st.value: st.name for st in LocationServiceType
            },
            "selected_service_id": service_id,
            "selected_service_type": service_type.value if service_type else None,
            "search_term": q,
        },
    )

@router.get("/api/ufs", response_model=List[UniteFonctionnelle])
async def list_unites_fonctionnelles_api(
    session: Session = Depends(get_session),
    service_id: Optional[int] = None,
):
    query = select(UniteFonctionnelle)
    if service_id:
        query = query.where(UniteFonctionnelle.service_id == service_id)
    ufs = session.exec(query).all()
    if apply_scheduled_status(ufs):
        session.commit()
    return ufs

@api_router.get("/ufs/{uf_id}")
def get_unite_fonctionnelle_api(
    uf_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint retournant une unité fonctionnelle avec ses valeurs effectives"""
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        raise HTTPException(status_code=404, detail="UF non trouvée")

    # Retourner les données avec valeurs effectives
    return {
        "id": uf.id,
        "identifier": uf.identifier,
        "name": uf.name,
        "short_name": uf.short_name,
        "description": uf.description,

        # Valeurs locales
        "local_operational_status": uf.operational_status,
        "local_status": uf.status,
        "local_mode": uf.mode,
        "local_physical_type": uf.physical_type,
        "local_etage": uf.etage,
        "local_aile": uf.aile,
        "local_opening_date": uf.opening_date,
        "local_activation_date": uf.activation_date,
        "local_closing_date": uf.closing_date,
        "local_deactivation_date": uf.deactivation_date,

        # Valeurs effectives (avec héritage)
        "effective_operational_status": uf.get_effective_operational_status(),
        "effective_status": uf.get_effective_status(),
        "effective_mode": uf.get_effective_mode(),
        "effective_physical_type": uf.get_effective_physical_type(),
        "effective_etage": uf.get_effective_etage(),
        "effective_aile": uf.get_effective_aile(),
        "effective_opening_date": uf.get_effective_opening_date(),
        "effective_activation_date": uf.get_effective_activation_date(),
        "effective_closing_date": uf.get_effective_closing_date(),
        "effective_deactivation_date": uf.get_effective_deactivation_date(),

        # Métadonnées d'héritage
        "inheritance_info": {
            "operational_status_inherited": uf.operational_status != uf.get_effective_operational_status() and uf.get_effective_operational_status() is not None,
            "status_inherited": uf.status != uf.get_effective_status() and uf.get_effective_status() is not None,
            "mode_inherited": uf.mode != uf.get_effective_mode() and uf.get_effective_mode() is not None,
            "physical_type_inherited": uf.physical_type != uf.get_effective_physical_type() and uf.get_effective_physical_type() is not None,
            "etage_inherited": uf.etage != uf.get_effective_etage() and uf.get_effective_etage() is not None,
            "aile_inherited": uf.aile != uf.get_effective_aile() and uf.get_effective_aile() is not None,
            "opening_date_inherited": uf.opening_date != uf.get_effective_opening_date() and uf.get_effective_opening_date() is not None,
            "activation_date_inherited": uf.activation_date != uf.get_effective_activation_date() and uf.get_effective_activation_date() is not None,
            "closing_date_inherited": uf.closing_date != uf.get_effective_closing_date() and uf.get_effective_closing_date() is not None,
            "deactivation_date_inherited": uf.deactivation_date != uf.get_effective_deactivation_date() and uf.get_effective_deactivation_date() is not None,
        },

        # Relations
        "service_id": uf.service_id,
        "service": {
            "id": uf.service.id,
            "name": uf.service.name,
            "identifier": uf.service.identifier
        } if uf.service else None,

        # Statistiques
        "stats": {
            "unites_hebergement_count": (lambda obj: 0 if obj is None or isinstance(obj, MockType) else (len(obj) if hasattr(obj, '__len__') else (sum(1 for _ in obj) if obj is not None else 0)))(getattr(uf, 'unites_hebergement', None)),
        },

        # Timestamps
        "created_at": uf.created_at,
        "updated_at": uf.updated_at,
    }

@router.post("/ufs", response_model=UniteFonctionnelle)
async def create_unite_fonctionnelle(
    uf: UniteFonctionnelle,
    session: Session = Depends(get_session)
):
    apply_scheduled_status([uf])
    session.add(uf)
    session.commit()
    session.refresh(uf)
    return uf

@router.get("/ufs/{uf_id}", response_class=HTMLResponse)
async def view_unite_fonctionnelle(
    request: Request,
    uf_id: int,
    session: Session = Depends(get_session)
):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        raise HTTPException(status_code=404, detail="UF non trouvée")
    uhs = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == uf_id).order_by(UniteHebergement.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        "structure/uf_detail.html",
        {"request": request, "uf": uf, "uhs": uhs},
    )

@router.get("/ufs/{uf_id}/edit", response_class=HTMLResponse)
async def edit_unite_fonctionnelle_form(
    request: Request,
    uf_id: int,
    session: Session = Depends(get_session)
):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        raise HTTPException(status_code=404, detail="UF non trouvée")
    services = session.exec(select(Service).order_by(Service.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        "structure/uf_form.html",
        {"request": request, "uf": uf, "services": services},
    )

@router.post("/ufs/{uf_id}")
async def update_unite_fonctionnelle(
    uf_id: int,
    name: str = Form(...),
    identifier: Optional[str] = Form(None),
    service_id: Optional[int] = Form(None),
    uf_type: Optional[str] = Form(None),
    um_code: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        raise HTTPException(status_code=404, detail="UF non trouvée")
    uf.name = name
    if identifier is not None:
        uf.identifier = identifier
    if service_id:
        uf.service_id = int(service_id)
    if uf_type is not None:
        uf.uf_type = uf_type
    if um_code is not None:
        uf.um_code = um_code
    apply_scheduled_status([uf])
    session.add(uf)
    session.commit()
    return RedirectResponse(url=f"/structure/ufs/{uf_id}", status_code=303)

@router.post("/ufs/{uf_id}/delete")
async def delete_unite_fonctionnelle(
    uf_id: int,
    session: Session = Depends(get_session)
):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        raise HTTPException(status_code=404, detail="UF non trouvée")
    session.delete(uf)
    session.commit()
    return RedirectResponse(url="/structure/ufs", status_code=303)

# --- Unités d'Hébergement ---
@router.get("/uh", response_class=HTMLResponse)
async def list_unites_hebergement(
    request: Request,
    session: Session = Depends(get_session),
    uf_id: Optional[int] = None,
    mode: Optional[str] = None,
    status: Optional[str] = None
):
    # Construction de la requête avec les filtres
    query = select(UniteHebergement)
    if uf_id:
        query = query.where(UniteHebergement.unite_fonctionnelle_id == uf_id)
    if mode:
        query = query.where(UniteHebergement.mode == mode)
    if status:
        query = query.where(UniteHebergement.status == status)
    
    uhs = session.exec(query).all()
    changed = apply_scheduled_status(uhs)

    # Récupération des UFs pour le filtre
    ufs = session.exec(select(UniteFonctionnelle)).all()
    if apply_scheduled_status(ufs):
        changed = True
    if changed:
        session.commit()
    
    return get_templates_with_filters(request).TemplateResponse(
        "structure/uh.html",
        {
            "request": request,
            "unites_hebergement": uhs,
            "unites_fonctionnelles": ufs,
            "modes": ["instance", "hospitalization", "ambulatory", "virtual"],
            "statuses": ["active", "suspended", "inactive"],
            "selected_uf_id": uf_id,
            "selected_mode": mode,
            "selected_status": status
        }
    )

@router.get("/api/uh", response_model=List[UniteHebergement])
async def list_unites_hebergement_api(
    session: Session = Depends(get_session),
    uf_id: Optional[int] = None,
):
    query = select(UniteHebergement)
    if uf_id:
        query = query.where(UniteHebergement.unite_fonctionnelle_id == uf_id)
    uhs = session.exec(query).all()
    if apply_scheduled_status(uhs):
        session.commit()
    return uhs

@router.get("/uh/new", response_class=HTMLResponse)
async def new_unite_hebergement_form(
    request: Request,
    session: Session = Depends(get_session)
):
    ufs = session.exec(select(UniteFonctionnelle)).all()
    return get_templates_with_filters(request).TemplateResponse(
        "structure/uh_form.html",
        {
            "request": request,
            "unites_fonctionnelles": ufs,
            "modes": ["instance", "hospitalization", "ambulatory", "virtual"],
            "statuses": ["active", "suspended", "inactive"],
            "activation_date_value": None,
            "deactivation_date_value": None,
        }
    )

@router.get("/uh/{uh_id}", response_class=HTMLResponse)
async def view_unite_hebergement(
    request: Request,
    uh_id: int,
    session: Session = Depends(get_session)
):
    """Vue détaillée d'une UH avec ses chambres"""
    uh = session.get(UniteHebergement, uh_id)
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    changed = apply_scheduled_status([uh])

    # Charger les chambres liées à cette UH avec leurs lits
    chambres = session.exec(select(Chambre).where(Chambre.unite_hebergement_id == uh_id)).all()
    # Eager-load lits for each chambre so template can access them
    for chambre in chambres:
        lits = session.exec(select(Lit).where(Lit.chambre_id == chambre.id)).all()
        if apply_scheduled_status(lits):
            changed = True
        # attach lits to the chambre instance for template rendering
        setattr(chambre, "lits", lits)
    if apply_scheduled_status(chambres):
        changed = True
    if changed:
        session.commit()
    
    return get_templates_with_filters(request).TemplateResponse(
        "structure/uh_detail.html",
        {
            "request": request,
            "uh": uh,
            "chambres": chambres
        }
    )

@router.get("/uh/{uh_id}/edit", response_class=HTMLResponse)
async def edit_unite_hebergement_form(
    request: Request,
    uh_id: int,
    session: Session = Depends(get_session)
):
    uh = session.get(UniteHebergement, uh_id)
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    changed = apply_scheduled_status([uh])

    ufs = session.exec(select(UniteFonctionnelle)).all()
    if apply_scheduled_status(ufs):
        changed = True
    if changed:
        session.commit()
    return get_templates_with_filters(request).TemplateResponse(
        "structure/uh_form.html",
        {
            "request": request,
            "uh": uh,
            "unites_fonctionnelles": ufs,
            "modes": ["instance", "hospitalization", "ambulatory", "virtual"],
            "statuses": ["active", "suspended", "inactive"],
            "activation_date_value": hl7_to_form_datetime(getattr(uh, "activation_date", None)),
            "deactivation_date_value": hl7_to_form_datetime(getattr(uh, "deactivation_date", None)),
        }
    )

@router.post("/uh", response_model=UniteHebergement)
async def create_unite_hebergement(
    request: Request,
    session: Session = Depends(get_session)
):
    form = await request.form()
    mode_value = form.get("mode") or LocationMode.INSTANCE
    status_value = form.get("status") or LocationStatus.ACTIVE
    physical_value = form.get("physical_type") or LocationPhysicalType.RO
    uh = UniteHebergement(
        name=form["name"],
        identifier=form["identifier"],
        unite_fonctionnelle_id=int(form["unite_fonctionnelle_id"]),
        mode=LocationMode(mode_value),
        status=LocationStatus(status_value),
        physical_type=LocationPhysicalType(physical_value),
    )
    uh.activation_date = form_datetime_to_hl7(form.get("activation_date"))
    uh.deactivation_date = form_datetime_to_hl7(form.get("deactivation_date"))
    apply_scheduled_status([uh])
    session.add(uh)
    session.commit()
    session.refresh(uh)
    return RedirectResponse(url="/structure/uh", status_code=303)

@router.post("/uh/{uh_id}", response_model=UniteHebergement)
async def update_unite_hebergement(
    request: Request,
    uh_id: int,
    session: Session = Depends(get_session)
):
    uh = session.get(UniteHebergement, uh_id)
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    
    form = await request.form()
    uh.name = form["name"]
    uh.identifier = form.get("identifier", uh.identifier)
    uh.unite_fonctionnelle_id = int(form["unite_fonctionnelle_id"])
    uh.mode = LocationMode(form.get("mode", uh.mode))
    uh.status = LocationStatus(form.get("status", uh.status))
    physical_value = form.get("physical_type") or uh.physical_type
    uh.physical_type = LocationPhysicalType(physical_value)
    uh.activation_date = form_datetime_to_hl7(form.get("activation_date"))
    uh.deactivation_date = form_datetime_to_hl7(form.get("deactivation_date"))
    apply_scheduled_status([uh])
    
    session.add(uh)
    session.commit()
    return RedirectResponse(url="/structure/uh", status_code=303)

# --- Suppression UH ---
@router.post("/uh/{uh_id}/delete")
async def delete_unite_hebergement(
    uh_id: int,
    session: Session = Depends(get_session)
):
    """Supprime une unité d'hébergement et redirige vers la liste"""
    uh = session.get(UniteHebergement, uh_id)
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    
    # On vérifie d'abord qu'il n'y a plus de chambres actives
    chambres = session.exec(
        select(Chambre)
        .where(Chambre.unite_hebergement_id == uh_id)
        .where(Chambre.status == "active")
    ).all()
    
    if chambres:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer l'UH : des chambres actives y sont rattachées"
        )

    # Delete all inactive chambres and their lits first
    inactive_chambres = session.exec(
        select(Chambre)
        .where(Chambre.unite_hebergement_id == uh_id)
        .where(Chambre.status != "active")
    ).all()

    for chambre in inactive_chambres:
        # Delete all lits in the chambre
        lits = session.exec(
            select(Lit).where(Lit.chambre_id == chambre.id)
        ).all()
        for lit in lits:
            session.delete(lit)
        # Then delete the chambre
        session.delete(chambre)

    session.commit()
    session.delete(uh)
    session.commit()
    return RedirectResponse(url="/structure/uh", status_code=303)

# --- Chambres ---
@router.get("/chambres", response_class=HTMLResponse)
async def list_chambres(
    request: Request,
    session: Session = Depends(get_session),
    uh_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(Chambre)
    if uh_id:
        query = query.where(Chambre.unite_hebergement_id == uh_id)
    if q:
        like = f"%{q}%"
        query = query.where(
            (Chambre.name.ilike(like))
            | (Chambre.identifier.ilike(like))
        )
    
    chambres = session.exec(query.order_by(Chambre.name)).all()
    if apply_scheduled_status(chambres):
        session.commit()
    
    uhs = session.exec(select(UniteHebergement).order_by(UniteHebergement.name)).all()
    uh_map = {uh.id: uh.name for uh in uhs}
    
    return get_templates_with_filters(request).TemplateResponse(
        "structure/chambres_list.html",
        {
            "request": request,
            "chambres": chambres,
            "unites_hebergement": uhs,
            "uh_map": uh_map,
            "selected_uh_id": uh_id,
            "search_term": q,
        },
    )

@router.get("/chambres/new", response_class=HTMLResponse)
async def new_chambre_form(
    request: Request,
    uh_id: int,
    session: Session = Depends(get_session)
):
    """Formulaire de création d'une chambre"""
    uh = session.get(UniteHebergement, uh_id)
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    if apply_scheduled_status([uh]):
        session.commit()

    return get_templates_with_filters(request).TemplateResponse(
        "structure/chambre_form.html",
        {
            "request": request,
            "unite_hebergement": uh,
            "physical_types": [type.value for type in LocationPhysicalType],
            "statuses": ["active", "suspended", "inactive"],
            "activation_date_value": None,
            "deactivation_date_value": None,
        }
    )

@router.get("/chambres/{chambre_id}", response_class=HTMLResponse)
async def view_chambre(
    request: Request,
    chambre_id: int,
    session: Session = Depends(get_session)
):
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")
    lits = session.exec(select(Lit).where(Lit.chambre_id == chambre_id).order_by(Lit.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        "structure/chambre_detail.html",
        {"request": request, "chambre": chambre, "lits": lits},
    )

@router.get("/chambres/{chambre_id}/edit", response_class=HTMLResponse)
async def edit_chambre_form(
    request: Request,
    chambre_id: int,
    session: Session = Depends(get_session)
):
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")
    return get_templates_with_filters(request).TemplateResponse(
        "structure/chambre_form.html",
        {
            "request": request,
            "chambre": chambre,
            "unite_hebergement": chambre.unite_hebergement,
            "physical_types": [type.value for type in LocationPhysicalType],
            "statuses": [status.value for status in LocationStatus],
            "activation_date_value": hl7_to_form_datetime(getattr(chambre, "activation_date", None)),
            "deactivation_date_value": hl7_to_form_datetime(getattr(chambre, "deactivation_date", None)),
        },
    )

@router.post("/chambres/{chambre_id}")
async def update_chambre(
    request: Request,
    chambre_id: int,
    session: Session = Depends(get_session)
):
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")
    form = await request.form()
    chambre.name = form.get("name", chambre.name)
    chambre.identifier = form.get("identifier", chambre.identifier)
    # physical_type may change, keep provided or current
    pt = form.get("physical_type")
    if pt:
        chambre.physical_type = LocationPhysicalType(pt)
    st = form.get("status")
    if st:
        chambre.status = LocationStatus(st)
    chambre.activation_date = form_datetime_to_hl7(form.get("activation_date"))
    chambre.deactivation_date = form_datetime_to_hl7(form.get("deactivation_date"))
    apply_scheduled_status([chambre])
    session.add(chambre)
    session.commit()
    return RedirectResponse(url=f"/structure/uh/{chambre.unite_hebergement_id}", status_code=303)

@router.post("/chambres/{chambre_id}/delete")
async def delete_chambre(
    chambre_id: int,
    session: Session = Depends(get_session)
):
    """Supprime une chambre et redirige vers l'UH parente"""
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")
    
    # On vérifie d'abord qu'il n'y a plus de lits actifs
    lits = session.exec(
        select(Lit)
        .where(Lit.chambre_id == chambre_id)
        .where(Lit.status == "active")
    ).all()
    
    if lits:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer la chambre : des lits actifs y sont rattachés"
        )

    # Delete all lits first (active or not)
    all_lits = session.exec(
        select(Lit).where(Lit.chambre_id == chambre_id)
    ).all()
    for lit in all_lits:
        session.delete(lit)
    session.commit()

    uh_id = chambre.unite_hebergement_id
    session.delete(chambre)
    session.commit()
    return RedirectResponse(url=f"/structure/uh/{uh_id}", status_code=303)

@router.get("/chambres", response_model=List[Chambre])
async def list_chambres(
    session: Session = Depends(get_session),
    uh_id: Optional[int] = None,
    status: Optional[LocationStatus] = None
):
    query = select(Chambre)
    if uh_id:
        query = query.where(Chambre.unite_hebergement_id == uh_id)
    if status:
        query = query.where(Chambre.status == status)
    chambres = session.exec(query).all()
    if apply_scheduled_status(chambres):
        session.commit()
    return chambres

@api_router.get("/chambres/{chambre_id}")
def get_chambre_api(
    chambre_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint retournant une chambre avec ses valeurs effectives"""
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")

    # Retourner les données avec valeurs effectives
    return {
        "id": chambre.id,
        "identifier": chambre.identifier,
        "name": chambre.name,
        "description": chambre.description,
        "type_chambre": chambre.type_chambre,
        "gender_usage": chambre.gender_usage,
        "max_occupancy": chambre.max_occupancy,

        # Valeurs locales
        "local_operational_status": chambre.operational_status,
        "local_status": chambre.status,
        "local_mode": chambre.mode,
        "local_physical_type": chambre.physical_type,
        "local_etage": chambre.etage,
        "local_aile": chambre.aile,
        "local_opening_date": chambre.opening_date,
        "local_activation_date": chambre.activation_date,
        "local_closing_date": chambre.closing_date,
        "local_deactivation_date": chambre.deactivation_date,

        # Valeurs effectives (avec héritage)
        "effective_operational_status": chambre.get_effective_operational_status(),
        "effective_status": chambre.get_effective_status(),
        "effective_mode": chambre.get_effective_mode(),
        "effective_physical_type": chambre.get_effective_physical_type(),
        "effective_etage": chambre.get_effective_etage(),
        "effective_aile": chambre.get_effective_aile(),
        "effective_opening_date": chambre.get_effective_opening_date(),
        "effective_activation_date": chambre.get_effective_activation_date(),
        "effective_closing_date": chambre.get_effective_closing_date(),
        "effective_deactivation_date": chambre.get_effective_deactivation_date(),

        # Métadonnées d'héritage
        "inheritance_info": {
            "operational_status_inherited": chambre.operational_status != chambre.get_effective_operational_status() and chambre.get_effective_operational_status() is not None,
            "status_inherited": chambre.status != chambre.get_effective_status() and chambre.get_effective_status() is not None,
            "mode_inherited": chambre.mode != chambre.get_effective_mode() and chambre.get_effective_mode() is not None,
            "physical_type_inherited": chambre.physical_type != chambre.get_effective_physical_type() and chambre.get_effective_physical_type() is not None,
            "etage_inherited": chambre.etage != chambre.get_effective_etage() and chambre.get_effective_etage() is not None,
            "aile_inherited": chambre.aile != chambre.get_effective_aile() and chambre.get_effective_aile() is not None,
            "opening_date_inherited": chambre.opening_date != chambre.get_effective_opening_date() and chambre.get_effective_opening_date() is not None,
            "activation_date_inherited": chambre.activation_date != chambre.get_effective_activation_date() and chambre.get_effective_activation_date() is not None,
            "closing_date_inherited": chambre.closing_date != chambre.get_effective_closing_date() and chambre.get_effective_closing_date() is not None,
            "deactivation_date_inherited": chambre.deactivation_date != chambre.get_effective_deactivation_date() and chambre.get_effective_deactivation_date() is not None,
        },

        # Relations
        "unite_hebergement_id": chambre.unite_hebergement_id,
        "unite_hebergement": {
            "id": chambre.unite_hebergement.id,
            "name": chambre.unite_hebergement.name,
            "identifier": chambre.unite_hebergement.identifier
        } if chambre.unite_hebergement else None,

        # Statistiques
        "stats": {
            "lits_count": len(chambre.lits) if hasattr(chambre, 'lits') else 0,
        },

        # Timestamps
        "created_at": chambre.created_at,
        "updated_at": chambre.updated_at,
    }

@router.post("/chambres", response_model=Chambre)
async def create_chambre(
    request: Request,
    session: Session = Depends(get_session)
):
    form = await request.form()
    status_value = form.get("status") or LocationStatus.ACTIVE
    chambre = Chambre(
        name=form["name"],
        identifier=form["identifier"],
        unite_hebergement_id=int(form["unite_hebergement_id"]),
        physical_type=LocationPhysicalType(form.get("physical_type", LocationPhysicalType.RO)),
        mode=LocationMode(form.get("mode", LocationMode.INSTANCE)),
        status=LocationStatus(status_value),
        type_chambre=form.get("type_chambre"),
        gender_usage=form.get("gender_usage")
    )
    chambre.activation_date = form_datetime_to_hl7(form.get("activation_date"))
    chambre.deactivation_date = form_datetime_to_hl7(form.get("deactivation_date"))
    apply_scheduled_status([chambre])
    session.add(chambre)
    session.commit()
    session.refresh(chambre)
    
    # Rediriger vers la vue de l'UH parente
    return RedirectResponse(
        url=f"/structure/uh/{chambre.unite_hebergement_id}",
        status_code=303
    )

# --- Lits ---
@router.get("/lits", response_class=HTMLResponse)
async def list_lits(
    request: Request,
    session: Session = Depends(get_session),
    chambre_id: Optional[int] = Query(None),
    status: Optional[LocationStatus] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(Lit)
    if chambre_id:
        query = query.where(Lit.chambre_id == chambre_id)
    if status:
        query = query.where(Lit.status == status)
    if q:
        like = f"%{q}%"
        query = query.where(
            (Lit.name.ilike(like))
            | (Lit.identifier.ilike(like))
        )
    
    lits = session.exec(query.order_by(Lit.name)).all()
    if apply_scheduled_status(lits):
        session.commit()
    
    chambres = session.exec(select(Chambre).order_by(Chambre.name)).all()
    chambre_map = {chambre.id: chambre.name for chambre in chambres}
    
    return get_templates_with_filters(request).TemplateResponse(
        "structure/lits_list.html",
        {
            "request": request,
            "lits": lits,
            "chambres": chambres,
            "chambre_map": chambre_map,
            "statuses": LocationStatus,
            "selected_chambre_id": chambre_id,
            "selected_status": status.value if status else None,
            "search_term": q,
        },
    )

@router.get("/api/lits", response_model=List[Lit])
async def list_lits_api(
    session: Session = Depends(get_session),
    chambre_id: Optional[int] = None,
    status: Optional[LocationStatus] = None
):
    query = select(Lit)
    if chambre_id:
        query = query.where(Lit.chambre_id == chambre_id)
    if status:
        query = query.where(Lit.status == status)
    lits = session.exec(query).all()
    if apply_scheduled_status(lits):
        session.commit()
    return lits

@api_router.get("/lits/{lit_id}")
def get_lit_api(
    lit_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint retournant un lit avec ses valeurs effectives"""
    lit = session.get(Lit, lit_id)
    if not lit:
        raise HTTPException(status_code=404, detail="Lit non trouvé")

    # Retourner les données avec valeurs effectives
    return {
        "id": lit.id,
        "identifier": lit.identifier,
        "name": lit.name,
        "description": lit.description,
        "max_occupancy": lit.max_occupancy,

        # Valeurs locales
        "local_operational_status": lit.operational_status,
        "local_status": lit.status,
        "local_mode": lit.mode,
        "local_physical_type": lit.physical_type,
        "local_etage": lit.etage,
        "local_aile": lit.aile,
        "local_opening_date": lit.opening_date,
        "local_activation_date": lit.activation_date,
        "local_closing_date": lit.closing_date,
        "local_deactivation_date": lit.deactivation_date,

        # Valeurs effectives (avec héritage)
        "effective_operational_status": lit.get_effective_operational_status(),
        "effective_status": lit.get_effective_status(),
        "effective_mode": lit.get_effective_mode(),
        "effective_physical_type": lit.get_effective_physical_type(),
        "effective_etage": lit.get_effective_etage(),
        "effective_aile": lit.get_effective_aile(),
        "effective_opening_date": lit.get_effective_opening_date(),
        "effective_activation_date": lit.get_effective_activation_date(),
        "effective_closing_date": lit.get_effective_closing_date(),
        "effective_deactivation_date": lit.get_effective_deactivation_date(),

        # Métadonnées d'héritage
        "inheritance_info": {
            "operational_status_inherited": lit.operational_status != lit.get_effective_operational_status() and lit.get_effective_operational_status() is not None,
            "status_inherited": lit.status != lit.get_effective_status() and lit.get_effective_status() is not None,
            "mode_inherited": lit.mode != lit.get_effective_mode() and lit.get_effective_mode() is not None,
            "physical_type_inherited": lit.physical_type != lit.get_effective_physical_type() and lit.get_effective_physical_type() is not None,
            "etage_inherited": lit.etage != lit.get_effective_etage() and lit.get_effective_etage() is not None,
            "aile_inherited": lit.aile != lit.get_effective_aile() and lit.get_effective_aile() is not None,
            "opening_date_inherited": lit.opening_date != lit.get_effective_opening_date() and lit.get_effective_opening_date() is not None,
            "activation_date_inherited": lit.activation_date != lit.get_effective_activation_date() and lit.get_effective_activation_date() is not None,
            "closing_date_inherited": lit.closing_date != lit.get_effective_closing_date() and lit.get_effective_closing_date() is not None,
            "deactivation_date_inherited": lit.deactivation_date != lit.get_effective_deactivation_date() and lit.get_effective_deactivation_date() is not None,
        },

        # Relations
        "chambre_id": lit.chambre_id,
        "chambre": {
            "id": lit.chambre.id,
            "name": lit.chambre.name,
            "identifier": lit.chambre.identifier
        } if lit.chambre else None,

        # Statistiques
        "stats": {},

        # Timestamps
        "created_at": lit.created_at,
        "updated_at": lit.updated_at,
    }

@router.post("/lits", response_model=Lit)
async def create_lit(
    lit: Lit,
    session: Session = Depends(get_session)
):
    apply_scheduled_status([lit])
    session.add(lit)
    session.commit()
    session.refresh(lit)
    return lit

@router.get("/lits/{lit_id}", response_class=HTMLResponse)
async def view_lit(
    request: Request,
    lit_id: int,
    session: Session = Depends(get_session)
):
    lit = session.get(Lit, lit_id)
    if not lit:
        raise HTTPException(status_code=404, detail="Lit non trouvé")
    return get_templates_with_filters(request).TemplateResponse(
        "structure/lit_detail.html",
        {"request": request, "lit": lit},
    )

@router.get("/lits/{lit_id}/edit", response_class=HTMLResponse)
async def edit_lit_form(
    request: Request,
    lit_id: int,
    session: Session = Depends(get_session)
):
    lit = session.get(Lit, lit_id)
    if not lit:
        raise HTTPException(status_code=404, detail="Lit non trouvé")
    chambres = session.exec(select(Chambre).order_by(Chambre.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        "structure/lit_form.html",
        {
            "request": request,
            "lit": lit,
            "chambres": chambres,
            "statuses": [s.value for s in LocationStatus],
        },
    )

@router.post("/lits/{lit_id}")
async def update_lit(
    lit_id: int,
    name: str = Form(...),
    identifier: Optional[str] = Form(None),
    chambre_id: Optional[int] = Form(None),
    status: Optional[str] = Form(None),
    operational_status: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    lit = session.get(Lit, lit_id)
    if not lit:
        raise HTTPException(status_code=404, detail="Lit non trouvé")
    lit.name = name
    if identifier is not None:
        lit.identifier = identifier
    if chambre_id:
        lit.chambre_id = int(chambre_id)
    if status:
        lit.status = LocationStatus(status)
    if operational_status is not None:
        lit.operational_status = operational_status
    apply_scheduled_status([lit])
    session.add(lit)
    session.commit()
    return RedirectResponse(url=f"/structure/chambres/{lit.chambre_id}", status_code=303)


@router.get("/search", response_class=HTMLResponse)
async def structure_search(
    request: Request,
    session: Session = Depends(get_session),
    service_type: Optional[LocationServiceType] = Query(None),
    uf_id: Optional[int] = Query(None),
):
    services = session.exec(select(Service).order_by(Service.name)).all()
    if apply_scheduled_status(services):
        session.commit()

    service_ids = [svc.id for svc in services if not service_type or svc.service_type == service_type]
    available_ufs_query = select(UniteFonctionnelle).order_by(UniteFonctionnelle.name)
    if service_type:
        if service_ids:
            available_ufs_query = available_ufs_query.where(UniteFonctionnelle.service_id.in_(service_ids))
        else:
            available_ufs_query = available_ufs_query.where(False)
    ufs = session.exec(available_ufs_query).all()
    if apply_scheduled_status(ufs):
        session.commit()

    results = []
    if service_type or uf_id:
        lits = _fetch_available_lits(session, service_type=service_type, uf_id=uf_id)
        for lit in lits:
            chambre = lit.chambre
            uh = chambre.unite_hebergement if chambre else None
            uf = uh.unite_fonctionnelle if uh else None
            service = uf.service if uf else None
            pole = service.pole if service else None
            eg = pole.entite_geo if pole else None
            results.append(
                {
                    "lit": lit,
                    "chambre": chambre,
                    "uh": uh,
                    "uf": uf,
                    "service": service,
                    "pole": pole,
                    "entite_geo": eg,
                }
            )

    return get_templates_with_filters(request).TemplateResponse(
        "structure/search.html",
        {
            "request": request,
            "service_types": [stype for stype in LocationServiceType],
            "services": services,
            "unites_fonctionnelles": ufs,
            "selected_service_type": service_type.value if service_type else None,
            "selected_uf_id": uf_id,
            "results": results,
        },
    )

# --- Utilitaires de recherche ---
def _fetch_available_lits(
    session: Session,
    service_type: Optional[LocationServiceType] = None,
    uf_id: Optional[int] = None,
):
    """Return lits libres en tenant compte des programmations."""
    query = (
        select(Lit)
        .options(
            selectinload(Lit.chambre)
            .selectinload(Chambre.unite_hebergement)
            .selectinload(UniteHebergement.unite_fonctionnelle)
            .selectinload(UniteFonctionnelle.service)
            .selectinload(Service.pole)
            .selectinload(Pole.entite_geo)
        )
        .join(Chambre)
        .join(UniteHebergement)
        .join(UniteFonctionnelle)
        .join(Service)
        .where(Lit.operationalStatus == "libre")
    )
    if service_type:
        query = query.where(Service.service_type == service_type)
    if uf_id:
        query = query.where(UniteFonctionnelle.id == uf_id)

    lits = session.exec(query).scalars().all()
    changed = apply_scheduled_status(lits)
    for lit in lits:
        if lit.chambre and apply_scheduled_status([lit.chambre]):
            changed = True
        uh = getattr(lit.chambre, "unite_hebergement", None)
        if uh and apply_scheduled_status([uh]):
            changed = True
        uf = getattr(uh, "unite_fonctionnelle", None) if uh else None
        if uf and apply_scheduled_status([uf]):
            changed = True
        service = getattr(uf, "service", None) if uf else None
        if service and apply_scheduled_status([service]):
            changed = True
        pole = getattr(service, "pole", None) if service else None
        if pole and apply_scheduled_status([pole]):
            changed = True
        eg = getattr(pole, "entite_geo", None) if pole else None
        if eg and apply_scheduled_status([eg]):
            changed = True
    if changed:
        session.commit()
    # Filtrer les lits actifs après application
    return [lit for lit in lits if lit.status == LocationStatus.ACTIVE]


@router.get("/search/lits-disponibles")
async def search_lits_disponibles(
    session: Session = Depends(get_session),
    service_type: Optional[LocationServiceType] = None,
    uf_id: Optional[int] = None,
):
    """Recherche les lits disponibles avec filtres (JSON)."""
    return _fetch_available_lits(session, service_type=service_type, uf_id=uf_id)


@router.get("/{type}/{id}/map", response_class=HTMLResponse)
async def view_structure_map(
    type: str,
    id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Affiche une carte/plan de l'entité de structure.
    Cette fonctionnalité est en cours de développement.
    """
    # Mapping des types vers les modèles
    model_map = {
        "eg": EntiteGeographique,
        "pole": Pole,
        "service": Service,
        "uf": UniteFonctionnelle,
        "uh": UniteHebergement,
        "chambre": Chambre,
        "lit": Lit
    }
    
    model = model_map.get(type)
    if not model:
        raise HTTPException(status_code=404, detail=f"Type de structure '{type}' non reconnu")
    
    # Récupérer l'entité
    entity = session.get(model, id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"{type.upper()} #{id} non trouvé")
    
    # Pour l'instant, retourner une page simple indiquant que cette fonctionnalité arrive bientôt
    return get_templates_with_filters(request).TemplateResponse(request, "structure_map_placeholder.html", {
        "entity": entity,
        "type": type,
        "type_label": {
            "eg": "Entité Géographique",
            "pole": "Pôle",
            "service": "Service",
            "uf": "Unité Fonctionnelle",
            "uh": "Unité d'Hébergement",
            "chambre": "Chambre",
            "lit": "Lit"
        }.get(type, type.upper())
    })


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
