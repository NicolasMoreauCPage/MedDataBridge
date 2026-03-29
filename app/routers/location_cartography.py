"""
Location cartography picker: Interactive UI component for selecting a location
in the hospital hierarchy (Service → UF → UH → Chambre → Lit)
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.db import get_session
from app.models_structure import (
    Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit, LocationStatus
)
from typing import List
import json

router = APIRouter(prefix="/api/location", tags=["location"])


@router.get("/services")
async def get_services(session: Session = Depends(get_session)):
    """Get all services with summary info"""
    services = session.exec(select(Service)).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "service_type": s.service_type,
            "code": s.code
        }
        for s in services
    ]


@router.get("/services/{service_id}/ufs")
async def get_service_ufs(service_id: int, session: Session = Depends(get_session)):
    """Get UFs for a specific service"""
    ufs = session.exec(
        select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service_id)
    ).all()
    return [
        {
            "id": uf.id,
            "name": uf.name,
            "code": getattr(uf, 'code', None),
            "description": getattr(uf, 'description', None)
        }
        for uf in ufs
    ]


@router.get("/ufs/{uf_id}/hebergement")
async def get_uf_hebergement(uf_id: int, session: Session = Depends(get_session)):
    """Get Unités d'Hébergement for a specific UF"""
    uhs = session.exec(
        select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == uf_id)
    ).all()
    return [
        {
            "id": uh.id,
            "name": uh.name,
            "code": getattr(uh, 'code', None)
        }
        for uh in uhs
    ]


@router.get("/hebergement/{uh_id}/chambres")
async def get_uh_chambres(uh_id: int, session: Session = Depends(get_session)):
    """Get Chambres for a specific Unité d'Hébergement"""
    # Some UHs might not have chambres directly - handle flattened structures
    chambres = session.exec(
        select(Chambre).where(Chambre.unite_hebergement_id == uh_id)
    ).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "code": getattr(c, 'code', None),
            "numbering_scheme": getattr(c, 'numbering_scheme', None)
        }
        for c in chambres
    ]


@router.get("/ufs/{uf_id}/available-lits")
async def get_uf_available_lits(uf_id: int, session: Session = Depends(get_session)):
    """Get all available beds for an UF in one call (UH/Chambre/Lit flattened)."""
    uhs = session.exec(
        select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == uf_id)
    ).all()
    if not uhs:
        return []

    uh_ids = [uh.id for uh in uhs if uh.id is not None]
    chambres = session.exec(
        select(Chambre).where(Chambre.unite_hebergement_id.in_(uh_ids))
    ).all()
    if not chambres:
        return []

    chambre_ids = [ch.id for ch in chambres if ch.id is not None]
    lits = session.exec(
        select(Lit).where(Lit.chambre_id.in_(chambre_ids))
    ).all()

    uh_by_id = {uh.id: uh for uh in uhs}
    chambre_by_id = {ch.id: ch for ch in chambres}

    result = []
    for lit in lits:
        chambre = chambre_by_id.get(lit.chambre_id)
        if not chambre:
            continue
        uh = uh_by_id.get(chambre.unite_hebergement_id)
        is_available = lit.operational_status == "active" or lit.status in ["available", "clean", None]
        if not is_available:
            continue
        result.append(
            {
                "id": lit.id,
                "name": lit.name,
                "code": getattr(lit, "code", None),
                "status": lit.status,
                "operational_status": getattr(lit, "operational_status", None),
                "bed_type": getattr(lit, "bed_type", None),
                "available": is_available,
                "chambre": {
                    "id": chambre.id,
                    "name": chambre.name,
                    "code": getattr(chambre, "code", None),
                },
                "uh": {
                    "id": uh.id,
                    "name": uh.name,
                    "code": getattr(uh, "code", None),
                }
                if uh
                else None,
            }
        )

    return result


@router.get("/chambres/{chambre_id}/lits")
async def get_chambre_lits(chambre_id: int, status: str = "free", session: Session = Depends(get_session)):
    """Get Lits for a specific Chambre with status filtering"""
    query = select(Lit).where(Lit.chambre_id == chambre_id)
    
    if status == "free":
        # Only operational and not occupied
        query = query.where(
            (Lit.operational_status.in_(["active", None])) | 
            (Lit.status.in_(["available", "clean"]))
        )
    elif status == "unavailable":
        query = query.where(Lit.operational_status != "active")
    
    lits = session.exec(query).all()
    return [
        {
            "id": lit.id,
            "name": lit.name,
            "code": getattr(lit, 'code', None),
            "status": lit.status,
            "operational_status": getattr(lit, 'operational_status', None),
            "bed_type": getattr(lit, 'bed_type', None),
            "available": lit.operational_status == "active" or lit.status in ["available", "clean"]
        }
        for lit in lits
    ]


@router.get("/lit/{lit_id}")
async def get_lit_details(lit_id: int, session: Session = Depends(get_session)):
    """Get full details about a specific lit including its location hierarchy"""
    lit = session.get(Lit, lit_id)
    if not lit:
        return {"error": "Lit not found"}
    
    chambre = session.get(Chambre, lit.chambre_id) if lit.chambre_id else None
    uh = session.get(UniteHebergement, chambre.unite_hebergement_id) if chambre else None
    uf = session.get(UniteFonctionnelle, uh.unite_fonctionnelle_id) if uh else None
    service = session.get(Service, uf.service_id) if uf else None
    
    return {
        "lit": {
            "id": lit.id,
            "name": lit.name,
            "code": getattr(lit, 'code', None),
            "status": lit.status,
            "available": lit.operational_status == "active"
        },
        "chambre": {
            "id": chambre.id,
            "name": chambre.name,
            "code": getattr(chambre, 'code', None)
        } if chambre else None,
        "uh": {
            "id": uh.id,
            "name": uh.name,
            "code": getattr(uh, 'code', None)
        } if uh else None,
        "uf": {
            "id": uf.id,
            "name": uf.name,
            "code": getattr(uf, 'code', None)
        } if uf else None,
        "service": {
            "id": service.id,
            "name": service.name,
            "code": getattr(service, 'code', None),
            "service_type": service.service_type
        } if service else None,
        "hierarchy": f"{service.name} / {uf.name} / {uh.name} / {chambre.name} / {lit.name}" if service else lit.name
    }


@router.get("/hierarchy")
async def get_hierarchy_tree(session: Session = Depends(get_session)):
    """Get the complete location hierarchy tree for cartographic display"""
    services = session.exec(select(Service)).all()

    service_ids = [s.id for s in services if s.id is not None]
    ufs = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id.in_(service_ids))).all() if service_ids else []
    uf_ids = [uf.id for uf in ufs if uf.id is not None]
    uhs = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id.in_(uf_ids))).all() if uf_ids else []
    uh_ids = [uh.id for uh in uhs if uh.id is not None]
    chambres = session.exec(select(Chambre).where(Chambre.unite_hebergement_id.in_(uh_ids))).all() if uh_ids else []
    chambre_ids = [ch.id for ch in chambres if ch.id is not None]
    lits = session.exec(select(Lit).where(Lit.chambre_id.in_(chambre_ids))).all() if chambre_ids else []

    ufs_by_service = {}
    for uf in ufs:
        ufs_by_service.setdefault(uf.service_id, []).append(uf)

    uhs_by_uf = {}
    for uh in uhs:
        uhs_by_uf.setdefault(uh.unite_fonctionnelle_id, []).append(uh)

    chambres_by_uh = {}
    for chambre in chambres:
        chambres_by_uh.setdefault(chambre.unite_hebergement_id, []).append(chambre)

    lits_by_chambre = {}
    for lit in lits:
        lits_by_chambre.setdefault(lit.chambre_id, []).append(lit)
    
    tree = {
        "services": []
    }
    
    for service in services:
        service_ufs = ufs_by_service.get(service.id, [])
        
        service_node = {
            "id": service.id,
            "name": service.name,
            "type": "service",
            "ufs": []
        }
        
        for uf in service_ufs:
            uf_uhs = uhs_by_uf.get(uf.id, [])
            
            uf_node = {
                "id": uf.id,
                "name": uf.name,
                "type": "uf",
                "uhs": []
            }
            
            for uh in uf_uhs:
                uh_chambres = chambres_by_uh.get(uh.id, [])
                
                uh_node = {
                    "id": uh.id,
                    "name": uh.name,
                    "type": "uh",
                    "chambres": []
                }
                
                for chambre in uh_chambres:
                    chambre_lits = lits_by_chambre.get(chambre.id, [])
                    
                    chambre_node = {
                        "id": chambre.id,
                        "name": chambre.name,
                        "type": "chambre",
                        "lits": [
                            {
                                "id": lit.id,
                                "name": lit.name,
                                "code": getattr(lit, 'code', None),
                                "status": lit.status,
                                "available": lit.operational_status == "active",
                                "type": "lit"
                            }
                            for lit in chambre_lits
                        ]
                    }
                    
                    uh_node["chambres"].append(chambre_node)
                
                uf_node["uhs"].append(uh_node)
            
            service_node["ufs"].append(uf_node)
        
        tree["services"].append(service_node)
    
    return tree
