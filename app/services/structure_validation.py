# app/services/structure_validation.py

"""
Validation des contraintes de structure hospitalière
Gestion des chambres et lits génériques (ZGEN) pour environnements de test
"""

from typing import Optional, List
from sqlmodel import Session, select
from app.models_structure import Chambre, Lit
from app.models import Venue


def is_generic_resource(identifier: str) -> bool:
    """
    Détermine si une ressource (chambre/lit) est générique basée sur son identifiant.
    Les ressources génériques (ZGEN) permettent l'occupation multiple en environnement de test.
    """
    if not identifier:
        return False
    return identifier.upper().startswith("ZGEN")


def get_room_occupancy(session: Session, chambre_id: int) -> int:
    """
    Calcule l'occupation actuelle d'une chambre
    """
    count = session.exec(
        select(Venue).where(
            Venue.chambre_id == chambre_id
        )
    ).all()
    return len(count)


def get_bed_occupancy(session: Session, lit_id: int) -> int:
    """
    Calcule l'occupation actuelle d'un lit
    """
    count = session.exec(
        select(Venue).where(
            Venue.lit_id == lit_id
        )
    ).all()
    return len(count)


def validate_room_occupancy(session: Session, chambre_id: int, patient_id: int) -> bool:
    """
    Valide si une chambre peut accepter un nouveau patient
    Retourne True si l'occupation est autorisée
    """
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        return False

    # Chambres génériques : occupation multiple autorisée
    if chambre.is_generic or is_generic_resource(chambre.identifier):
        return True

    # Chambres normales : vérifier l'occupation maximale
    current_occupancy = get_room_occupancy(session, chambre_id)
    max_occupancy = chambre.max_occupancy or 1

    return current_occupancy < max_occupancy


def validate_bed_occupancy(session: Session, lit_id: int, patient_id: int) -> bool:
    """
    Valide si un lit peut accepter un nouveau patient
    Retourne True si l'occupation est autorisée
    """
    lit = session.get(Lit, lit_id)
    if not lit:
        return False

    # Lits génériques : occupation multiple autorisée
    if lit.is_generic or is_generic_resource(lit.identifier):
        return True

    # Lits normaux : vérifier l'occupation maximale
    current_occupancy = get_bed_occupancy(session, lit_id)
    max_occupancy = lit.max_occupancy or 1

    return current_occupancy < max_occupancy


def auto_detect_generic_resources(session: Session) -> None:
    """
    Détecte automatiquement et marque les ressources génériques (ZGEN)
    Utile lors de l'import de données depuis la plateforme de développement
    """
    # Détecter chambres génériques
    chambres = session.exec(select(Chambre)).all()
    for chambre in chambres:
        if is_generic_resource(chambre.identifier) and not chambre.is_generic:
            chambre.is_generic = True
            chambre.max_occupancy = 999  # Occupation illimitée pour tests
            session.add(chambre)

    # Détecter lits génériques
    lits = session.exec(select(Lit)).all()
    for lit in lits:
        if is_generic_resource(lit.identifier) and not lit.is_generic:
            lit.is_generic = True
            lit.max_occupancy = 999  # Occupation illimitée pour tests
            session.add(lit)

    session.commit()


def get_available_rooms(session: Session, unite_hebergement_id: Optional[int] = None) -> List[Chambre]:
    """
    Retourne les chambres disponibles (avec places libres ou génériques)
    """
    query = select(Chambre).where(
        (Chambre.operational_status == "active") | (Chambre.operational_status.is_(None))
    )

    if unite_hebergement_id:
        query = query.where(Chambre.unite_hebergement_id == unite_hebergement_id)

    chambres = session.exec(query).all()
    available = []

    for chambre in chambres:
        if chambre.is_generic or is_generic_resource(chambre.identifier):
            # Chambres génériques : toujours disponibles
            available.append(chambre)
        else:
            # Chambres normales : vérifier occupation
            current_occupancy = get_room_occupancy(session, chambre.id)
            max_occupancy = chambre.max_occupancy or 1
            if current_occupancy < max_occupancy:
                available.append(chambre)

    return available


def get_available_beds(session: Session, chambre_id: Optional[int] = None) -> List[Lit]:
    """
    Retourne les lits disponibles (avec places libres ou génériques)
    """
    query = select(Lit).where(
        (Lit.operational_status == "active") | (Lit.operational_status.is_(None))
    )

    if chambre_id:
        query = query.where(Lit.chambre_id == chambre_id)

    lits = session.exec(query).all()
    available = []

    for lit in lits:
        if lit.is_generic or is_generic_resource(lit.identifier):
            # Lits génériques : toujours disponibles
            available.append(lit)
        else:
            # Lits normaux : vérifier occupation
            current_occupancy = get_bed_occupancy(session, lit.id)
            max_occupancy = lit.max_occupancy or 1
            if current_occupancy < max_occupancy:
                available.append(lit)

    return available
