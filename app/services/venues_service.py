import logging
from datetime import datetime
from typing import Optional
from sqlmodel import Session
from pydantic import BaseModel
from sqlalchemy.orm import attributes

from app.models import Venue, Dossier
from app.db import get_next_sequence

logger = logging.getLogger(__name__)

class VenueCreateSchema(BaseModel):
    """Schéma de données pour la création d'une venue."""
    dossier_id: int
    uf_responsabilite: str
    start_time: datetime
    venue_seq: Optional[int] = None
    hospital_service: Optional[str] = None
    assigned_location: Optional[str] = None
    attending_provider: Optional[str] = None
    code: Optional[str] = None
    label: Optional[str] = None

class VenueUpdateSchema(BaseModel):
    """Schéma de données pour la mise à jour d'une venue."""
    dossier_id: int
    uf_responsabilite: str
    start_time: datetime
    venue_seq: int

def create_venue(session: Session, venue_data: VenueCreateSchema) -> Venue:
    """Crée une nouvelle venue en base de données."""
    try:
        dossier = session.get(Dossier, venue_data.dossier_id)
        if not dossier:
            raise ValueError(f"Le dossier avec l'ID {venue_data.dossier_id} n'existe pas.")
        seq = venue_data.venue_seq or get_next_sequence(session, "venue")
        data = venue_data.dict()
        # avoid passing venue_seq twice if provided by the schema
        data.pop("venue_seq", None)
        # Assigne l'EJ du dossier parent si non fourni
        if not data.get("entite_juridique_id"):
            data["entite_juridique_id"] = dossier.entite_juridique_id
        venue = Venue(**data, venue_seq=seq)
        session.add(venue)
        session.commit()
        session.refresh(venue)
        logger.info(f"Venue {venue.id} créée avec succès pour le dossier {venue.dossier_id}.")
        return venue
    except Exception as e:
        logger.error(f"Erreur lors de la création de la venue: {e}", exc_info=True)
        session.rollback()
        raise

def update_venue(session: Session, venue: Venue, update_data: VenueUpdateSchema) -> Venue:
    """Met à jour une venue existante."""
    try:
        venue.dossier_id = update_data.dossier_id
        venue.uf_responsabilite = update_data.uf_responsabilite
        venue.start_time = update_data.start_time
        venue.venue_seq = update_data.venue_seq
        
        session.add(venue)
        attributes.flag_modified(venue, "uf_responsabilite")
        session.commit()
        session.refresh(venue)
        
        logger.info(f"Venue {venue.id} mise à jour avec succès.")
        return venue
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la venue {venue.id}: {e}", exc_info=True)
        session.rollback()
        raise
