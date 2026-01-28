"""
Router pour les interactions avancées sur la structure (Phase 5)
- Édition inline de champs
- Drag & drop avec déplacement d'entités
- Mise à jour partielle optimisée
"""

from fastapi import APIRouter, Depends, HTTPException, Body, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional, Dict, Any
from datetime import datetime

from app.db import get_session
from app.models_structure import (
    EntiteGeographique,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
    Chambre,
    Lit
)

router = APIRouter(prefix="/api/structure", tags=["Structure Interactive"])
ui_router = APIRouter(prefix="/structure", tags=["Structure Interactive UI"])

# Templates
templates = Jinja2Templates(directory="app/templates")


# ========================================
# UI ROUTES
# ========================================

@ui_router.get("/interactive", response_class=HTMLResponse)
async def structure_interactive_page(
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Page de démonstration de l'édition interactive
    Affiche toute la structure avec drag & drop et édition inline
    """
    # Charger toutes les EGs avec leur hiérarchie complète
    statement = select(EntiteGeographique)
    egs = session.exec(statement).all()
    
    # Enrichir chaque EG avec ses pôles → services → UFs
    for eg in egs:
        # Pole model uses 'entite_geo_id' as foreign key to EntiteGeographique
        statement_poles = select(Pole).where(Pole.entite_geo_id == eg.id)
        eg.poles = session.exec(statement_poles).all()
        
        for pole in eg.poles:
            statement_services = select(Service).where(Service.pole_id == pole.id)
            pole.services = session.exec(statement_services).all()
            
            for service in pole.services:
                statement_ufs = select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service.id)
                service.unites_fonctionnelles = session.exec(statement_ufs).all()
    
    # Calculer stats
    total_poles = sum(len(eg.poles) for eg in egs)
    total_services = sum(len(pole.services) for pole in eg.poles for eg in egs if hasattr(eg, 'poles'))
    total_ufs = sum(
        len(service.unites_fonctionnelles) 
        for eg in egs 
        for pole in (eg.poles if hasattr(eg, 'poles') else [])
        for service in (pole.services if hasattr(pole, 'services') else [])
        if hasattr(service, 'unites_fonctionnelles')
    )
    
    return templates.TemplateResponse("structure_interactive.html", {
        "request": request,
        "egs": egs,
        "total_poles": total_poles,
        "total_services": total_services,
        "total_ufs": total_ufs
    })


# ========================================
# API ROUTES
# ========================================


# Mapping type → model
MODEL_MAP = {
    "entitegeographique": EntiteGeographique,
    "pole": Pole,
    "service": Service,
    "unitefonctionnelle": UniteFonctionnelle,
    "unitehebergement": UniteHebergement,
    "chambre": Chambre,
    "lit": Lit
}


@router.patch("/{entity_type}/{entity_id}")
async def update_field(
    entity_type: str,
    entity_id: int,
    update_data: Dict[str, Any] = Body(...),
    session: Session = Depends(get_session)
):
    """
    Mise à jour inline d'un ou plusieurs champs d'une entité
    
    Body: {
        "field": "nom",  # ou plusieurs champs
        "value": "Nouveau nom"
    }
    
    Ou pour multiple fields:
    {
        "nom": "Nouveau nom",
        "telephone": "01 02 03 04 05"
    }
    """
    # Normaliser le type
    entity_type = entity_type.lower()
    
    if entity_type not in MODEL_MAP:
        raise HTTPException(status_code=400, detail=f"Type d'entité inconnu: {entity_type}")
    
    model_class = MODEL_MAP[entity_type]
    
    # Récupérer l'entité
    statement = select(model_class).where(model_class.id == entity_id)
    entity = session.exec(statement).first()
    
    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_type} #{entity_id} non trouvée")
    
    # Si format {"field": "nom", "value": "val"}
    if "field" in update_data and "value" in update_data:
        field = update_data["field"]
        value = update_data["value"]
        
        # Vérifier que le champ existe
        if not hasattr(entity, field):
            raise HTTPException(status_code=400, detail=f"Champ '{field}' inexistant sur {entity_type}")
        
        # Mise à jour
        setattr(entity, field, value)
    else:
        # Format direct {nom: "val", telephone: "val"}
        for field, value in update_data.items():
            if hasattr(entity, field):
                setattr(entity, field, value)
            else:
                raise HTTPException(status_code=400, detail=f"Champ '{field}' inexistant")
    
    # Validation unicité code si modifié
    if hasattr(entity, 'code') and 'code' in update_data or ('field' in update_data and update_data['field'] == 'code'):
        code_to_check = entity.code
        statement_check = select(model_class).where(
            model_class.code == code_to_check,
            model_class.id != entity_id
        )
        existing = session.exec(statement_check).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Code '{code_to_check}' déjà utilisé")
    
    session.add(entity)
    session.commit()
    session.refresh(entity)
    
    return {
        "success": True,
        "updated_at": datetime.now().isoformat(),
        "entity": entity.model_dump()
    }


@router.post("/move")
async def move_entity(
    item_type: str = Body(...),
    item_id: int = Body(...),
    target_type: str = Body(...),
    target_id: int = Body(...),
    position: Optional[int] = Body(None),
    session: Session = Depends(get_session)
):
    """
    Déplace une entité dans la hiérarchie
    
    Exemples:
    - Déplacer un Service d'un Pôle à un autre
    - Déplacer une UF d'un Service à un autre
    - Déplacer un Lit d'une Chambre à une autre
    
    Body: {
        "item_type": "service",
        "item_id": 123,
        "target_type": "pole",
        "target_id": 456,
        "position": 0  # optionnel
    }
    """
    item_type = item_type.lower()
    target_type = target_type.lower()
    
    # Validation types
    if item_type not in MODEL_MAP or target_type not in MODEL_MAP:
        raise HTTPException(status_code=400, detail="Type d'entité invalide")
    
    # Récupérer l'élément à déplacer
    item_model = MODEL_MAP[item_type]
    statement = select(item_model).where(item_model.id == item_id)
    item = session.exec(statement).first()
    
    if not item:
        raise HTTPException(status_code=404, detail=f"{item_type} #{item_id} non trouvé")
    
    # Récupérer la cible
    target_model = MODEL_MAP[target_type]
    statement_target = select(target_model).where(target_model.id == target_id)
    target = session.exec(statement_target).first()
    
    if not target:
        raise HTTPException(status_code=404, detail=f"{target_type} #{target_id} non trouvé")
    
    # Validation règles métier
    valid_moves = {
        "service": ["pole"],
        "unitefonctionnelle": ["service"],
        "unitehebergement": ["service"],
        "chambre": ["unitehebergement"],
        "lit": ["chambre"]
    }
    
    if item_type not in valid_moves:
        raise HTTPException(status_code=400, detail=f"Le type '{item_type}' ne peut pas être déplacé")
    
    if target_type not in valid_moves[item_type]:
        raise HTTPException(
            status_code=400, 
            detail=f"Un {item_type} ne peut pas être déplacé vers un {target_type}. Cibles valides: {valid_moves[item_type]}"
        )
    
    # Mise à jour de la clé étrangère
    foreign_key_map = {
        ("service", "pole"): "pole_id",
        ("unitefonctionnelle", "service"): "service_id",
        ("unitehebergement", "service"): "service_id",
        ("chambre", "unitehebergement"): "uh_id",
        ("lit", "chambre"): "chambre_id"
    }
    
    fk_field = foreign_key_map.get((item_type, target_type))
    if not fk_field:
        raise HTTPException(status_code=500, detail="Mapping FK non trouvé")
    
    # Appliquer le déplacement
    setattr(item, fk_field, target_id)
    
    # TODO: Gérer le position si besoin d'ordering
    # if position is not None and hasattr(item, 'ordre'):
    #     setattr(item, 'ordre', position)
    
    session.add(item)
    session.commit()
    session.refresh(item)
    
    return {
        "success": True,
        "moved_at": datetime.now().isoformat(),
        "item": {
            "type": item_type,
            "id": item_id,
            "new_parent": {
                "type": target_type,
                "id": target_id
            }
        }
    }


@router.post("/duplicate")
async def duplicate_entity(
    entity_type: str = Body(...),
    entity_id: int = Body(...),
    new_code: str = Body(...),
    new_name: Optional[str] = Body(None),
    session: Session = Depends(get_session)
):
    """
    Duplique une entité avec un nouveau code
    
    Body: {
        "entity_type": "service",
        "entity_id": 123,
        "new_code": "CARDIO-2",
        "new_name": "Cardiologie Bis"  # optionnel
    }
    """
    entity_type = entity_type.lower()
    
    if entity_type not in MODEL_MAP:
        raise HTTPException(status_code=400, detail=f"Type inconnu: {entity_type}")
    
    model_class = MODEL_MAP[entity_type]
    
    # Récupérer l'original
    statement = select(model_class).where(model_class.id == entity_id)
    original = session.exec(statement).first()
    
    if not original:
        raise HTTPException(status_code=404, detail=f"{entity_type} #{entity_id} non trouvé")
    
    # Vérifier unicité du nouveau code
    statement_check = select(model_class).where(model_class.code == new_code)
    existing = session.exec(statement_check).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Code '{new_code}' déjà utilisé")
    
    # Créer une copie
    data = original.model_dump(exclude={"id"})
    data["code"] = new_code
    if new_name:
        data["nom"] = new_name
    else:
        data["nom"] = f"{original.nom} (copie)"
    
    duplicate = model_class(**data)
    session.add(duplicate)
    session.commit()
    session.refresh(duplicate)
    
    return {
        "success": True,
        "created_at": datetime.now().isoformat(),
        "original_id": entity_id,
        "duplicate": duplicate.model_dump()
    }


@router.post("/bulk-update")
async def bulk_update(
    entity_type: str = Body(...),
    entity_ids: list[int] = Body(...),
    updates: Dict[str, Any] = Body(...),
    session: Session = Depends(get_session)
):
    """
    Mise à jour en masse de plusieurs entités
    
    Body: {
        "entity_type": "service",
        "entity_ids": [1, 2, 3],
        "updates": {
            "pole_id": 10,
            "actif": true
        }
    }
    """
    entity_type = entity_type.lower()
    
    if entity_type not in MODEL_MAP:
        raise HTTPException(status_code=400, detail=f"Type inconnu: {entity_type}")
    
    model_class = MODEL_MAP[entity_type]
    
    updated_count = 0
    errors = []
    
    for entity_id in entity_ids:
        try:
            statement = select(model_class).where(model_class.id == entity_id)
            entity = session.exec(statement).first()
            
            if not entity:
                errors.append(f"ID {entity_id} non trouvé")
                continue
            
            for field, value in updates.items():
                if hasattr(entity, field):
                    setattr(entity, field, value)
            
            session.add(entity)
            updated_count += 1
        except Exception as e:
            errors.append(f"ID {entity_id}: {str(e)}")
    
    session.commit()
    
    return {
        "success": len(errors) == 0,
        "updated_count": updated_count,
        "total_requested": len(entity_ids),
        "errors": errors
    }
