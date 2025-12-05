from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select, func, SQLModel
import logging

from app.db import get_session
from app.utils.flash import flash
from app.models_structure import GHTContext, EntiteJuridique, EntiteGeographique, IdentifierNamespace
from app.models_structure import Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
from app.models_scenario_config import ScenarioEJConfig
from app.models_shared import SystemEndpoint
from app.models_endpoints import MLLPConfig, FHIRConfig
from .helpers import get_context_or_404, get_ej_or_404, templates

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/{context_id}/ej/new")
async def new_entite_juridique_form(
    request: Request,
    context_id: int,
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    request.state.ght_context = context
    request.session["ght_context_id"] = context.id
    return templates.TemplateResponse(
        request,
        "ej_form.html",
        {"context": context, "entite": None},
    )

@router.post("/{context_id}/ej/new")
async def create_entite_juridique(
    request: Request,
    context_id: int,
    name: str = Form(...),
    finess_ej: str = Form(...),
    short_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    siren: Optional[str] = Form(None),
    siret: Optional[str] = Form(None),
    address_line: Optional[str] = Form(None),
    postal_code: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    country: Optional[str] = Form("FR"),
    is_active: str = Form("true"),
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    existing = session.exec(select(EntiteJuridique).where(EntiteJuridique.finess_ej == finess_ej)).first()
    if existing:
        flash(request, "Une entité juridique avec ce FINESS existe déjà.", "error")
        return templates.TemplateResponse(
            request, "ej_form.html",
            {"context": context, "entite": None, "form_data": await request.form()},
            status_code=400,
        )

    entite = EntiteJuridique(
        name=name, finess_ej=finess_ej, short_name=short_name, description=description,
        siren=siren, siret=siret, address_line=address_line, postal_code=postal_code,
        city=city, country=country or "FR",
        is_active=str(is_active).lower() in ("1", "true", "yes", "on"),
        ght_context_id=context.id,
    )
    session.add(entite)
    session.commit()
    flash(request, f'Entité juridique "{entite.name}" créée avec succès.', "success")
    return RedirectResponse(f"/admin/ght/{context.id}", status_code=303)

@router.get("/{context_id}/ej/{ej_id}")
async def view_entite_juridique(
    request: Request,
    context_id: int,
    ej_id: int,
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)
    request.session["ght_context_id"] = context_id
    request.session["ej_context_id"] = ej_id
    request.state.ght_context = context
    request.state.ej_context = entite

    geo_ids = [geo.id for geo in entite.entites_geographiques]
    pole_ids = list(session.exec(select(Pole.id).where(Pole.entite_geo_id.in_(geo_ids)))) if geo_ids else []
    service_ids = list(session.exec(select(Service.id).where(Service.pole_id.in_(pole_ids)))) if pole_ids else []
    uf_ids = list(session.exec(select(UniteFonctionnelle.id).where(UniteFonctionnelle.service_id.in_(service_ids)))) if service_ids else []
    uh_ids = list(session.exec(select(UniteHebergement.id).where(UniteHebergement.unite_fonctionnelle_id.in_(uf_ids)))) if uf_ids else []
    chambre_ids = list(session.exec(select(Chambre.id).where(Chambre.unite_hebergement_id.in_(uh_ids)))) if uh_ids else []
    lit_count = session.exec(select(func.count(Lit.id)).where(Lit.chambre_id.in_(chambre_ids))).one() if chambre_ids else 0

    counts = {
        "entites_geo": len(geo_ids),
        "entites_geo_actives": sum(1 for geo in entite.entites_geographiques if getattr(geo, "is_active", True)),
        "poles": len(pole_ids), "services": len(service_ids), "ufs": len(uf_ids),
        "uhs": len(uh_ids), "chambres": len(chambre_ids), "lits": lit_count,
    }
    namespaces = session.exec(select(IdentifierNamespace).where(IdentifierNamespace.entite_juridique_id == ej_id).order_by(IdentifierNamespace.type, IdentifierNamespace.name)).all()

    return templates.TemplateResponse(
        request, "ej_detail.html",
        {"context": context, "entite": entite, "entites_geographiques": entite.entites_geographiques, "namespaces": namespaces, "counts": counts},
    )

@router.get("/{context_id}/ej/{ej_id}/edit")
async def edit_entite_juridique_form(
    request: Request,
    context_id: int,
    ej_id: int,
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)
    return templates.TemplateResponse(
        request, "ej_form.html",
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
    country: Optional[str] = Form("FR"),
    is_active: str = Form("true"),
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)

    if finess_ej != entite.finess_ej:
        exists = session.exec(select(EntiteJuridique).where(EntiteJuridique.finess_ej == finess_ej).where(EntiteJuridique.id != entite.id)).first()
        if exists:
            flash(request, "Une entité juridique avec ce FINESS existe déjà.", "error")
            return templates.TemplateResponse(
                request, "ej_form.html",
                {"context": context, "entite": entite, "form_data": await request.form()},
                status_code=400,
            )

    entite.name, entite.finess_ej, entite.short_name, entite.description = name, finess_ej, short_name, description
    entite.siren, entite.siret = siren, siret
    entite.address_line, entite.postal_code, entite.city, entite.country = address_line, postal_code, city, country or "FR"
    entite.is_active = str(is_active).lower() in ("1", "true", "yes", "on")
    
    session.add(entite)
    session.commit()
    flash(request, f'Entité juridique "{entite.name}" mise à jour.', "success")
    return RedirectResponse(f"/admin/ght/{context.id}/ej/{entite.id}", status_code=303)


def _clone_model_fields(source: Any, exclude_fields: set = None) -> Dict[str, Any]:
    """Extrait les champs d'un modèle SQLModel pour le clonage.
    
    Exclut automatiquement id, les relations et les champs spécifiés.
    """
    if exclude_fields is None:
        exclude_fields = set()
    
    # Champs à toujours exclure
    base_exclude = {'id', 'identifier', 'global_identifier', 'created_at', 'updated_at'}
    exclude_fields = exclude_fields.union(base_exclude)
    
    result = {}
    for key, value in source.__dict__.items():
        # Ignorer les attributs SQLAlchemy internes
        if key.startswith('_'):
            continue
        # Ignorer les champs exclus
        if key in exclude_fields:
            continue
        # Ignorer les relations (objets complexes ou listes)
        if isinstance(value, (list, SQLModel)) or (value is not None and hasattr(value, '__table__')):
            continue
        result[key] = value
    
    return result


def _clone_namespace(session: Session, ns: IdentifierNamespace, new_parent_id: int, parent_field: str) -> IdentifierNamespace:
    """Clone un namespace avec un nouveau parent."""
    data = _clone_model_fields(ns, exclude_fields={
        'ght_context_id', 'entite_juridique_id', 'entite_geographique_id',
        'pole_id', 'service_id', 'unite_fonctionnelle_id', 'unite_hebergement_id',
        'chambre_id', 'lit_id'
    })
    data[parent_field] = new_parent_id
    new_ns = IdentifierNamespace(**data)
    session.add(new_ns)
    return new_ns


@router.post("/{context_id}/ej/{ej_id}/clone")
async def clone_entite_juridique(
    request: Request,
    context_id: int,
    ej_id: int,
    new_name: str = Form(...),
    new_finess_ej: str = Form(...),
    session: Session = Depends(get_session),
):
    """Clone une entité juridique avec toute sa structure, namespaces et configuration de scénarios.
    
    La fonction clone:
    - L'EntiteJuridique avec un nouveau nom et FINESS
    - Tous les IdentifierNamespace liés à l'EJ
    - Le ScenarioEJConfig s'il existe
    - La structure complète (EG, Pole, Service, UF, UH, Chambre, Lit)
    - Les namespaces de chaque niveau de structure
    """
    context = get_context_or_404(session, context_id)
    source_ej = get_ej_or_404(session, context, ej_id)
    
    # Vérifier que le nouveau FINESS n'existe pas
    existing = session.exec(select(EntiteJuridique).where(EntiteJuridique.finess_ej == new_finess_ej)).first()
    if existing:
        flash(request, f"Une entité juridique avec le FINESS '{new_finess_ej}' existe déjà.", "error")
        return RedirectResponse(f"/admin/ght/{context_id}", status_code=303)
    
    try:
        # Générer un nouvel identifiant unique
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        new_identifier = f"ej-clone-{timestamp}"
        
        # 1. Cloner l'EJ
        ej_data = _clone_model_fields(source_ej, exclude_fields={
            'entites_geographiques', 'poles', 'namespaces', 'endpoints', 'ght_context'
        })
        ej_data['name'] = new_name
        ej_data['finess_ej'] = new_finess_ej
        ej_data['identifier'] = new_identifier
        ej_data['ght_context_id'] = context_id
        
        new_ej = EntiteJuridique(**ej_data)
        session.add(new_ej)
        session.flush()  # Pour obtenir l'ID
        
        logger.info(f"Clonage EJ: {source_ej.name} -> {new_ej.name} (ID: {new_ej.id})")
        
        # 2. Cloner les namespaces de l'EJ
        ej_namespaces = session.exec(
            select(IdentifierNamespace).where(IdentifierNamespace.entite_juridique_id == ej_id)
        ).all()
        for ns in ej_namespaces:
            _clone_namespace(session, ns, new_ej.id, 'entite_juridique_id')
        logger.info(f"Cloné {len(ej_namespaces)} namespaces EJ")
        
        # 3. Cloner le ScenarioEJConfig s'il existe
        source_config = session.exec(
            select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == ej_id)
        ).first()
        if source_config:
            config_data = _clone_model_fields(source_config, exclude_fields={
                'entite_juridique', 'uf_hospitalisation', 'uf_consultation', 
                'uf_urgences', 'uf_mutation_cible'
            })
            config_data['entite_juridique_id'] = new_ej.id
            # Note: les foreign keys vers les UF seront nulles car les nouvelles UF n'existent pas encore
            # On les met à None et on laisse l'utilisateur reconfigurer
            config_data['uf_hospitalisation_id'] = None
            config_data['uf_consultation_id'] = None
            config_data['uf_urgences_id'] = None
            config_data['uf_mutation_cible_id'] = None
            new_config = ScenarioEJConfig(**config_data)
            session.add(new_config)
            logger.info(f"Cloné ScenarioEJConfig (UF à reconfigurer)")
        
        # 4. Cloner la structure complète avec mapping des IDs
        # Maps old_id -> new_id pour chaque niveau
        eg_map: Dict[int, int] = {}
        pole_map: Dict[int, int] = {}
        service_map: Dict[int, int] = {}
        uf_map: Dict[int, int] = {}
        uh_map: Dict[int, int] = {}
        chambre_map: Dict[int, int] = {}
        
        # 4.1 Cloner les EntiteGeographique
        for eg in source_ej.entites_geographiques:
            eg_data = _clone_model_fields(eg, exclude_fields={
                'entite_juridique', 'poles', 'namespaces'
            })
            eg_data['entite_juridique_id'] = new_ej.id
            eg_data['identifier'] = f"eg-clone-{timestamp}-{eg.id}"
            new_eg = EntiteGeographique(**eg_data)
            session.add(new_eg)
            session.flush()
            eg_map[eg.id] = new_eg.id
            
            # Cloner les namespaces de l'EG
            eg_namespaces = session.exec(
                select(IdentifierNamespace).where(IdentifierNamespace.entite_geographique_id == eg.id)
            ).all()
            for ns in eg_namespaces:
                _clone_namespace(session, ns, new_eg.id, 'entite_geographique_id')
        
        logger.info(f"Cloné {len(eg_map)} EntiteGeographique")
        
        # 4.2 Cloner les Poles
        for old_eg_id, new_eg_id in eg_map.items():
            poles = session.exec(select(Pole).where(Pole.entite_geo_id == old_eg_id)).all()
            for pole in poles:
                pole_data = _clone_model_fields(pole, exclude_fields={
                    'entite_geo', 'entite_juridique', 'services', 'namespaces'
                })
                pole_data['entite_geo_id'] = new_eg_id
                pole_data['entite_juridique_id'] = new_ej.id
                pole_data['identifier'] = f"pole-clone-{timestamp}-{pole.id}"
                new_pole = Pole(**pole_data)
                session.add(new_pole)
                session.flush()
                pole_map[pole.id] = new_pole.id
                
                # Cloner les namespaces du pole
                pole_namespaces = session.exec(
                    select(IdentifierNamespace).where(IdentifierNamespace.pole_id == pole.id)
                ).all()
                for ns in pole_namespaces:
                    _clone_namespace(session, ns, new_pole.id, 'pole_id')
        
        logger.info(f"Cloné {len(pole_map)} Poles")
        
        # 4.3 Cloner les Services
        for old_pole_id, new_pole_id in pole_map.items():
            services = session.exec(select(Service).where(Service.pole_id == old_pole_id)).all()
            for service in services:
                service_data = _clone_model_fields(service, exclude_fields={
                    'pole', 'unites_fonctionnelles', 'namespaces'
                })
                service_data['pole_id'] = new_pole_id
                service_data['identifier'] = f"service-clone-{timestamp}-{service.id}"
                new_service = Service(**service_data)
                session.add(new_service)
                session.flush()
                service_map[service.id] = new_service.id
                
                # Cloner les namespaces du service
                service_namespaces = session.exec(
                    select(IdentifierNamespace).where(IdentifierNamespace.service_id == service.id)
                ).all()
                for ns in service_namespaces:
                    _clone_namespace(session, ns, new_service.id, 'service_id')
        
        logger.info(f"Cloné {len(service_map)} Services")
        
        # 4.4 Cloner les UniteFonctionnelle
        for old_service_id, new_service_id in service_map.items():
            ufs = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == old_service_id)).all()
            for uf in ufs:
                uf_data = _clone_model_fields(uf, exclude_fields={
                    'service', 'unites_hebergement', 'activities', 'namespaces'
                })
                uf_data['service_id'] = new_service_id
                uf_data['identifier'] = f"uf-clone-{timestamp}-{uf.id}"
                new_uf = UniteFonctionnelle(**uf_data)
                session.add(new_uf)
                session.flush()
                uf_map[uf.id] = new_uf.id
                
                # Cloner les namespaces de l'UF
                uf_namespaces = session.exec(
                    select(IdentifierNamespace).where(IdentifierNamespace.unite_fonctionnelle_id == uf.id)
                ).all()
                for ns in uf_namespaces:
                    _clone_namespace(session, ns, new_uf.id, 'unite_fonctionnelle_id')
        
        logger.info(f"Cloné {len(uf_map)} UniteFonctionnelle")
        
        # 4.5 Cloner les UniteHebergement
        for old_uf_id, new_uf_id in uf_map.items():
            uhs = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == old_uf_id)).all()
            for uh in uhs:
                uh_data = _clone_model_fields(uh, exclude_fields={
                    'unite_fonctionnelle', 'chambres', 'namespaces'
                })
                uh_data['unite_fonctionnelle_id'] = new_uf_id
                uh_data['identifier'] = f"uh-clone-{timestamp}-{uh.id}"
                new_uh = UniteHebergement(**uh_data)
                session.add(new_uh)
                session.flush()
                uh_map[uh.id] = new_uh.id
                
                # Cloner les namespaces de l'UH
                uh_namespaces = session.exec(
                    select(IdentifierNamespace).where(IdentifierNamespace.unite_hebergement_id == uh.id)
                ).all()
                for ns in uh_namespaces:
                    _clone_namespace(session, ns, new_uh.id, 'unite_hebergement_id')
        
        logger.info(f"Cloné {len(uh_map)} UniteHebergement")
        
        # 4.6 Cloner les Chambres
        for old_uh_id, new_uh_id in uh_map.items():
            chambres = session.exec(select(Chambre).where(Chambre.unite_hebergement_id == old_uh_id)).all()
            for chambre in chambres:
                chambre_data = _clone_model_fields(chambre, exclude_fields={
                    'unite_hebergement', 'lits', 'namespaces'
                })
                chambre_data['unite_hebergement_id'] = new_uh_id
                chambre_data['identifier'] = f"chambre-clone-{timestamp}-{chambre.id}"
                new_chambre = Chambre(**chambre_data)
                session.add(new_chambre)
                session.flush()
                chambre_map[chambre.id] = new_chambre.id
                
                # Cloner les namespaces de la chambre
                chambre_namespaces = session.exec(
                    select(IdentifierNamespace).where(IdentifierNamespace.chambre_id == chambre.id)
                ).all()
                for ns in chambre_namespaces:
                    _clone_namespace(session, ns, new_chambre.id, 'chambre_id')
        
        logger.info(f"Cloné {len(chambre_map)} Chambres")
        
        # 4.7 Cloner les Lits
        lit_count = 0
        for old_chambre_id, new_chambre_id in chambre_map.items():
            lits = session.exec(select(Lit).where(Lit.chambre_id == old_chambre_id)).all()
            for lit in lits:
                lit_data = _clone_model_fields(lit, exclude_fields={
                    'chambre', 'namespaces'
                })
                lit_data['chambre_id'] = new_chambre_id
                lit_data['identifier'] = f"lit-clone-{timestamp}-{lit.id}"
                new_lit = Lit(**lit_data)
                session.add(new_lit)
                session.flush()
                lit_count += 1
                
                # Cloner les namespaces du lit
                lit_namespaces = session.exec(
                    select(IdentifierNamespace).where(IdentifierNamespace.lit_id == lit.id)
                ).all()
                for ns in lit_namespaces:
                    _clone_namespace(session, ns, new_lit.id, 'lit_id')
        
        logger.info(f"Cloné {lit_count} Lits")
        
        # 5. Cloner les Endpoints et leurs configurations
        source_endpoints = session.exec(
            select(SystemEndpoint).where(SystemEndpoint.entite_juridique_id == ej_id)
        ).all()
        
        endpoint_count = 0
        for endpoint in source_endpoints:
            endpoint_data = _clone_model_fields(endpoint, exclude_fields={
                'ght_context', 'entite_juridique', 'mllp_configs', 'fhir_configs'
            })
            endpoint_data['entite_juridique_id'] = new_ej.id
            endpoint_data['ght_context_id'] = context_id
            # Modifier le nom pour indiquer que c'est un clone
            endpoint_data['name'] = f"{endpoint.name} (Clone)"
            # Modifier le port pour éviter les conflits (si MLLP)
            if endpoint_data.get('port'):
                endpoint_data['port'] = None  # L'utilisateur devra reconfigurer
            
            new_endpoint = SystemEndpoint(**endpoint_data)
            session.add(new_endpoint)
            session.flush()
            endpoint_count += 1
            
            # Cloner les MLLPConfig associés
            mllp_configs = session.exec(
                select(MLLPConfig).where(MLLPConfig.endpoint_id == endpoint.id)
            ).all()
            for mllp in mllp_configs:
                mllp_data = _clone_model_fields(mllp, exclude_fields={'endpoint'})
                mllp_data['endpoint_id'] = new_endpoint.id
                mllp_data['name'] = f"{mllp.name} (Clone)"
                # Modifier le port pour éviter les conflits
                mllp_data['port'] = mllp.port + 1000  # Décaler de 1000 pour éviter les conflits
                new_mllp = MLLPConfig(**mllp_data)
                session.add(new_mllp)
            
            # Cloner les FHIRConfig associés
            fhir_configs = session.exec(
                select(FHIRConfig).where(FHIRConfig.endpoint_id == endpoint.id)
            ).all()
            for fhir in fhir_configs:
                fhir_data = _clone_model_fields(fhir, exclude_fields={'endpoint'})
                fhir_data['endpoint_id'] = new_endpoint.id
                fhir_data['name'] = f"{fhir.name} (Clone)"
                new_fhir = FHIRConfig(**fhir_data)
                session.add(new_fhir)
        
        logger.info(f"Cloné {endpoint_count} Endpoints avec leurs configurations")
        
        session.commit()
        
        flash(request, f'Entité juridique "{new_name}" clonée avec succès (structure, namespaces, config et endpoints).', "success")
        return RedirectResponse(f"/admin/ght/{context_id}", status_code=303)
        
    except Exception as e:
        session.rollback()
        logger.exception(f"Erreur lors du clonage de l'EJ {ej_id}")
        flash(request, f"Erreur lors du clonage: {str(e)}", "error")
        return RedirectResponse(f"/admin/ght/{context_id}", status_code=303)