"""
API endpoints pour charger dynamiquement les options de structure
dans les formulaires avec champs dépendants
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
from typing import List, Dict
from app.db import get_session
from app.models_structure import UniteFonctionnelle, UniteHebergement, Chambre, Lit

router = APIRouter(prefix="/api/mouvements", tags=["api", "structure"])


@router.get("/uh-options")
def get_uh_options(
    uf_id: str = Query(..., description="Identifiant de l'UF"),
    session: Session = Depends(get_session)
) -> List[Dict[str, str]]:
    """
    Retourne les options d'UH pour une UF donnée
    """
    # Chercher l'UF par son identifier
    uf = session.exec(
        select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == uf_id)
    ).first()
    
    if not uf:
        return []
    
    # Charger les UH de cette UF
    uhs = session.exec(
        select(UniteHebergement)
        .where(UniteHebergement.unite_fonctionnelle_id == uf.id)
        .order_by(UniteHebergement.name)
    ).all()
    
    return [
        {
            "value": str(uh.id),
            "label": f"{uh.identifier} — {uh.name}"
        }
        for uh in uhs
    ]


@router.get("/chambre-options")
def get_chambre_options(
    uh_id: int = Query(..., description="ID de l'UH"),
    session: Session = Depends(get_session)
) -> List[Dict[str, str]]:
    """
    Retourne les options de chambres pour une UH donnée
    """
    chambres = session.exec(
        select(Chambre)
        .where(Chambre.unite_hebergement_id == uh_id)
        .order_by(Chambre.name)
    ).all()
    
    return [
        {
            "value": str(chambre.id),
            "label": f"{chambre.identifier} — {chambre.name}" if chambre.name else chambre.identifier
        }
        for chambre in chambres
    ]


@router.get("/lit-options")
def get_lit_options(
    chambre_id: int = Query(..., description="ID de la chambre"),
    session: Session = Depends(get_session)
) -> List[Dict[str, str]]:
    """
    Retourne les options de lits pour une chambre donnée
    """
    lits = session.exec(
        select(Lit)
        .where(Lit.chambre_id == chambre_id)
        .order_by(Lit.name)
    ).all()
    
    return [
        {
            "value": str(lit.id),
            "label": f"{lit.identifier} — {lit.name}"
        }
        for lit in lits
    ]
