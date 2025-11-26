import logging
from datetime import datetime
from typing import List, Optional
from sqlmodel import Session, select
from pydantic import BaseModel
from sqlalchemy.orm import attributes, selectinload

from app.models import Dossier, Patient, Venue, DossierType
from app.models_identifiers import IdentifierType
from app.models_structure import IdentifierNamespace, UniteFonctionnelle, Service, Pole, EntiteGeographique
from app.db import get_next_sequence

logger = logging.getLogger(__name__)

class DossierCreateSchema(BaseModel):
    """Schéma de données pour la création d'un dossier."""
    uf_responsabilite: Optional[str]
    dossier_type: DossierType
    admission_source: Optional[str]
    attending_provider: Optional[str]
    admit_time: datetime
    current_state: Optional[str] = "Pas de venue courante"

class DossierUpdateSchema(BaseModel):
    """Schéma de données pour la mise à jour d'un dossier."""
    patient_id: int
    uf_responsabilite: Optional[str]
    dossier_type: DossierType
    admission_source: Optional[str]
    attending_provider: Optional[str]
    admit_time: datetime
    dossier_seq: int

def get_uf_options(session: Session, ej_id: int) -> List[dict]:
    """Récupère les options de l'UF pour les formulaires."""
    if not ej_id:
        return []
    ufs = session.exec(
        select(UniteFonctionnelle)
        .join(Service).join(Pole).join(EntiteGeographique)
        .where(EntiteGeographique.entite_juridique_id == ej_id)
        .where(UniteFonctionnelle.status == "active")
    ).all()
    return [{"value": uf.identifier, "label": f"{uf.identifier} - {uf.name}"} for uf in ufs]

def get_dossier(session: Session, dossier_id: int) -> Optional[Dossier]:
    """Récupère un dossier par son ID."""
    return session.get(Dossier, dossier_id)

def get_dossiers(
    session: Session,
    ej_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    dossier_type: Optional[DossierType] = None,
    dossier_seq: Optional[int] = None,
) -> List[Dossier]:
    """Récupère une liste de dossiers filtrée."""
        if nda_namespace:
            dossier_seq = generate_identifier(session, nda_namespace, IdentifierType.NDA)
        else:
            logger.warning(f"Aucun namespace NDA actif trouvé pour l'EJ {ej_id}. Utilisation de l'ancienne logique de séquence.")
            from app.utils.seq_generator import generate_dossier_seq
            dossier_seq = generate_dossier_seq()

        dossier = Dossier(
            **dossier_data.dict(),
            patient_id=patient.id,
            dossier_seq=dossier_seq,
            entite_juridique_id=ej_id
        )
        session.add(dossier)
        session.flush() 

        venue_seq = get_next_sequence(session, "venue")
        venue = Venue(
            dossier_id=dossier.id,
            uf_responsabilite=dossier_data.uf_responsabilite,
            start_time=dossier_data.admit_time,
            attending_provider=dossier_data.attending_provider,
            venue_seq=venue_seq,
            code="PRE_ADMIT",
            label="Pré-admission automatique"
        )
        session.add(venue)

        session.commit()
        session.refresh(dossier)
        
        logger.info(f"Dossier {dossier.id} et Venue {venue.id} créés avec succès.")
        return dossier

    except Exception as e:
        logger.error(f"Erreur lors de la création du dossier et de la venue: {e}", exc_info=True)
        session.rollback()
        raise

def update_dossier(
    session: Session,
    dossier: Dossier,
    update_data: DossierUpdateSchema
) -> Dossier:
    """Met à jour un dossier existant."""
    try:
        dossier.patient_id = update_data.patient_id
        dossier.dossier_type = update_data.dossier_type
        dossier.admission_source = update_data.admission_source
        dossier.attending_provider = update_data.attending_provider
        dossier.admit_time = update_data.admit_time
        dossier.dossier_seq = update_data.dossier_seq

        session.refresh(dossier, attribute_names=["venues"])
        if dossier.venues:
            dossier.venues[0].uf_responsabilite = update_data.uf_responsabilite
        
        session.add(dossier)
        attributes.flag_modified(dossier, "dossier_type")
        session.commit()
        session.refresh(dossier)

        logger.info(f"Dossier {dossier.id} mis à jour avec succès.")
        return dossier
    
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du dossier {dossier.id}: {e}", exc_info=True)
        session.rollback()
        raise

def delete_dossier(session: Session, dossier: Dossier):
    """Supprime un dossier."""
    try:
        session.delete(dossier)
        session.commit()
        logger.info(f"Dossier {dossier.id} supprimé avec succès.")
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du dossier {dossier.id}: {e}", exc_info=True)
        session.rollback()
        raise
