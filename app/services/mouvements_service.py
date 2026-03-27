"""
Service de gestion des mouvements de patients.
"""
from typing import Optional, List
from datetime import datetime
from sqlmodel import Session, select
from app.models import Mouvement, Venue
from app.db import get_next_sequence
from pydantic import BaseModel


class MouvementCreateSchema(BaseModel):
    """Schéma pour la création d'un mouvement."""
    venue_id: int
    when: datetime
    trigger_event: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    uf_id: Optional[int] = None
    uh_id: Optional[int] = None
    nature: Optional[str] = None
    medecin_responsable_id: Optional[int] = None


def create_mouvement(session: Session, mouvement_data: MouvementCreateSchema) -> Mouvement:
    """Fonction helper pour créer un mouvement."""
    service = MouvementsService(session)
    return service.create_mouvement(
        venue_id=mouvement_data.venue_id,
        when=mouvement_data.when,
        trigger_event=mouvement_data.trigger_event,
        location=mouvement_data.location,
        status=mouvement_data.status,
        uf_id=mouvement_data.uf_id,
        uh_id=mouvement_data.uh_id,
        nature=mouvement_data.nature,
        medecin_responsable_id=mouvement_data.medecin_responsable_id
    )


class MouvementsService:
    """Service pour gérer les mouvements de patients."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_mouvement(
        self,
        venue_id: int,
        when: datetime,
        trigger_event: Optional[str] = None,
        location: Optional[str] = None,
        status: Optional[str] = None,
        uf_id: Optional[int] = None,
        uh_id: Optional[int] = None,
        nature: Optional[str] = None,
        medecin_responsable_id: Optional[int] = None,
        **kwargs
    ) -> Mouvement:
        """Crée un nouveau mouvement."""
        venue = self.session.get(Venue, venue_id)
        ej_id = venue.entite_juridique_id if venue else None
        mouvement = Mouvement(
            mouvement_seq=get_next_sequence(self.session, "mouvement"),
            venue_id=venue_id,
            when=when,
            trigger_event=trigger_event,
            location=location,
            status=status,
            uf_id=uf_id,
            uh_id=uh_id,
            nature=nature,
            medecin_responsable_id=medecin_responsable_id,
            entite_juridique_id=ej_id,
            **kwargs
        )
        self.session.add(mouvement)
        self.session.commit()
        self.session.refresh(mouvement)
        return mouvement
    
    def get_mouvement(self, mouvement_id: int) -> Optional[Mouvement]:
        """Récupère un mouvement par son ID."""
        return self.session.get(Mouvement, mouvement_id)
    
    def get_mouvements_by_venue(self, venue_id: int) -> List[Mouvement]:
        """Récupère tous les mouvements d'une venue."""
        statement = select(Mouvement).where(Mouvement.venue_id == venue_id)
        return list(self.session.exec(statement).all())
    
    def update_mouvement(
        self,
        mouvement_id: int,
        **kwargs
    ) -> Optional[Mouvement]:
        """Met à jour un mouvement."""
        mouvement = self.get_mouvement(mouvement_id)
        if not mouvement:
            return None
        
        for key, value in kwargs.items():
            if hasattr(mouvement, key):
                setattr(mouvement, key, value)
        
        self.session.add(mouvement)
        self.session.commit()
        self.session.refresh(mouvement)
        return mouvement
    
    def delete_mouvement(self, mouvement_id: int) -> bool:
        """Supprime un mouvement."""
        mouvement = self.get_mouvement(mouvement_id)
        if not mouvement:
            return False
        
        self.session.delete(mouvement)
        self.session.commit()
        return True
