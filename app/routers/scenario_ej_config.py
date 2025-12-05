"""Router pour la configuration des scénarios par EJ.

Ce module fournit les endpoints pour gérer la configuration des UF et médecins
utilisés lors de l'exécution des scénarios d'interopérabilité.

Routes:
    GET /scenarios/ej-config - Liste des configurations par EJ
    GET /scenarios/ej-config/{ej_id} - Détail/formulaire de configuration
    POST /scenarios/ej-config/{ej_id} - Sauvegarder la configuration
    DELETE /scenarios/ej-config/{ej_id} - Supprimer la configuration
    GET /api/ej/{ej_id}/structure - API pour récupérer l'arbre de structure
"""

from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.models_scenario_config import ScenarioEJConfig
from app.models_structure import (
    EntiteJuridique, EntiteGeographique, Pole, Service, 
    UniteFonctionnelle, UniteHebergement
)

templates = Jinja2Templates(directory="app/templates")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config/scenario-ej", tags=["scenario-ej-config"])


@router.get("", response_class=HTMLResponse, name="scenario_ej_config_list")
async def list_ej_configs(
    request: Request,
    session: Session = Depends(get_session)
):
    """Liste des configurations EJ avec leurs UF et médecins."""
    # Récupérer toutes les EJ avec leurs configurations (si elles existent)
    ejs = session.exec(
        select(EntiteJuridique).order_by(EntiteJuridique.name)
    ).all()
    
    # Récupérer les configurations existantes
    configs = session.exec(select(ScenarioEJConfig)).all()
    configs_by_ej = {c.entite_juridique_id: c for c in configs}
    
    # Préparer les données pour l'affichage
    ej_data = []
    for ej in ejs:
        config = configs_by_ej.get(ej.id)
        ej_data.append({
            "ej": ej,
            "config": config,
            "has_config": config is not None
        })
    
    return templates.TemplateResponse(
        "scenarios/ej_config_list.html",
        {
            "request": request,
            "ej_data": ej_data,
            "total_ejs": len(ejs),
            "configured_ejs": len(configs)
        }
    )


@router.get("/{ej_id}", response_class=HTMLResponse, name="scenario_ej_config_edit")
async def edit_ej_config(
    request: Request,
    ej_id: int,
    session: Session = Depends(get_session)
):
    """Formulaire de configuration pour une EJ."""
    # Récupérer l'EJ
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Récupérer la config existante ou créer un objet vide
    config = session.exec(
        select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == ej_id)
    ).first()
    
    # Récupérer l'arbre de structure de l'EJ pour les sélecteurs d'UF
    structure = get_ej_structure(ej_id, session)
    
    # Récupérer les UF sélectionnées pour afficher leurs noms
    selected_ufs = {}
    if config:
        for field in ['uf_hospitalisation_id', 'uf_consultation_id', 'uf_urgences_id', 'uf_mutation_cible_id']:
            uf_id = getattr(config, field, None)
            if uf_id:
                uf = session.get(UniteFonctionnelle, uf_id)
                selected_ufs[field] = uf
    
    return templates.TemplateResponse(
        "scenarios/ej_config_form.html",
        {
            "request": request,
            "ej": ej,
            "config": config,
            "structure": structure,
            "selected_ufs": selected_ufs
        }
    )


@router.post("/{ej_id}", response_class=HTMLResponse, name="scenario_ej_config_save")
async def save_ej_config(
    request: Request,
    ej_id: int,
    uf_hospitalisation_id: Optional[int] = Form(None),
    medecin_hospitalisation_rpps: Optional[str] = Form(None),
    medecin_hospitalisation_nom: Optional[str] = Form(None),
    uf_consultation_id: Optional[int] = Form(None),
    medecin_consultation_rpps: Optional[str] = Form(None),
    medecin_consultation_nom: Optional[str] = Form(None),
    uf_urgences_id: Optional[int] = Form(None),
    medecin_urgences_rpps: Optional[str] = Form(None),
    medecin_urgences_nom: Optional[str] = Form(None),
    uf_mutation_cible_id: Optional[int] = Form(None),
    medecin_mutation_rpps: Optional[str] = Form(None),
    medecin_mutation_nom: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    """Sauvegarder la configuration d'une EJ."""
    # Vérifier que l'EJ existe
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Récupérer ou créer la config
    config = session.exec(
        select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == ej_id)
    ).first()
    
    if not config:
        config = ScenarioEJConfig(entite_juridique_id=ej_id)
        session.add(config)
    
    # Mettre à jour les champs
    config.uf_hospitalisation_id = uf_hospitalisation_id or None
    config.medecin_hospitalisation_rpps = medecin_hospitalisation_rpps or None
    config.medecin_hospitalisation_nom = medecin_hospitalisation_nom or None
    
    config.uf_consultation_id = uf_consultation_id or None
    config.medecin_consultation_rpps = medecin_consultation_rpps or None
    config.medecin_consultation_nom = medecin_consultation_nom or None
    
    config.uf_urgences_id = uf_urgences_id or None
    config.medecin_urgences_rpps = medecin_urgences_rpps or None
    config.medecin_urgences_nom = medecin_urgences_nom or None
    
    config.uf_mutation_cible_id = uf_mutation_cible_id or None
    config.medecin_mutation_rpps = medecin_mutation_rpps or None
    config.medecin_mutation_nom = medecin_mutation_nom or None
    
    from datetime import datetime
    config.updated_at = datetime.utcnow()
    
    session.commit()
    
    logger.info(f"Configuration EJ {ej_id} ({ej.name}) sauvegardée")
    
    # Rediriger vers la liste avec message de succès
    return RedirectResponse(
        url=f"/scenarios/ej-config?success=1&ej={ej.name}",
        status_code=303
    )


@router.delete("/{ej_id}", name="scenario_ej_config_delete")
async def delete_ej_config(
    ej_id: int,
    session: Session = Depends(get_session)
):
    """Supprimer la configuration d'une EJ."""
    config = session.exec(
        select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == ej_id)
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration non trouvée")
    
    session.delete(config)
    session.commit()
    
    return {"status": "deleted", "ej_id": ej_id}


# API pour récupérer la structure de l'EJ (pour AJAX)
@router.get("/api/structure/{ej_id}", name="scenario_ej_config_structure_api")
async def get_ej_structure_api(
    ej_id: int,
    session: Session = Depends(get_session)
):
    """Retourne l'arbre de structure d'une EJ au format JSON."""
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    return get_ej_structure(ej_id, session)


def get_ej_structure(ej_id: int, session: Session) -> dict:
    """Construit l'arbre de structure d'une EJ.
    
    Retourne un dictionnaire hiérarchique:
    {
        "ej": {...},
        "egs": [
            {
                "eg": {...},
                "poles": [
                    {
                        "pole": {...},
                        "services": [
                            {
                                "service": {...},
                                "ufs": [...]
                            }
                        ]
                    }
                ]
            }
        ],
        "all_ufs": [...]  # Liste plate de toutes les UF pour sélection rapide
    }
    """
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        return {}
    
    # Récupérer toutes les EG de cette EJ
    egs = session.exec(
        select(EntiteGeographique)
        .where(EntiteGeographique.entite_juridique_id == ej_id)
        .order_by(EntiteGeographique.name)
    ).all()
    
    all_ufs = []
    egs_data = []
    
    for eg in egs:
        # Récupérer les pôles de cette EG
        poles = session.exec(
            select(Pole)
            .where(Pole.entite_geo_id == eg.id)
            .order_by(Pole.name)
        ).all()
        
        poles_data = []
        for pole in poles:
            # Récupérer les services du pôle
            services = session.exec(
                select(Service)
                .where(Service.pole_id == pole.id)
                .order_by(Service.name)
            ).all()
            
            services_data = []
            for service in services:
                # Récupérer les UF du service
                ufs = session.exec(
                    select(UniteFonctionnelle)
                    .where(UniteFonctionnelle.service_id == service.id)
                    .order_by(UniteFonctionnelle.name)
                ).all()
                
                ufs_data = []
                for uf in ufs:
                    uf_info = {
                        "id": uf.id,
                        "name": uf.name,
                        "identifier": uf.identifier,
                        "path": f"{eg.name} > {pole.name} > {service.name} > {uf.name}"
                    }
                    ufs_data.append(uf_info)
                    all_ufs.append(uf_info)
                
                services_data.append({
                    "service": {
                        "id": service.id,
                        "name": service.name,
                        "identifier": service.identifier
                    },
                    "ufs": ufs_data
                })
            
            poles_data.append({
                "pole": {
                    "id": pole.id,
                    "name": pole.name,
                    "identifier": pole.identifier
                },
                "services": services_data
            })
        
        egs_data.append({
            "eg": {
                "id": eg.id,
                "name": eg.name,
                "identifier": eg.identifier
            },
            "poles": poles_data
        })
    
    return {
        "ej": {
            "id": ej.id,
            "name": ej.name,
            "identifier": ej.identifier
        },
        "egs": egs_data,
        "all_ufs": sorted(all_ufs, key=lambda x: x["path"])
    }
