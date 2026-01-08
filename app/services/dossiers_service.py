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
    uf: Optional[str] = None,
    medecin: Optional[str] = None,
    admit_from: Optional[str] = None,
    admit_to: Optional[str] = None,
    current_state: Optional[str] = None,
) -> List[Dossier]:
    """Récupère une liste de dossiers filtrée."""
    from datetime import datetime, timedelta
    
    query = select(Dossier)
    if ej_id:
        query = query.where(Dossier.entite_juridique_id == ej_id)
    if patient_id:
        query = query.where(Dossier.patient_id == patient_id)
    if dossier_type:
        query = query.where(Dossier.dossier_type == dossier_type)
    if dossier_seq:
        query = query.where(Dossier.dossier_seq == dossier_seq)
    
    # Filtres avancés
    if uf:
        query = query.where(Dossier.uf_responsabilite.ilike(f"%{uf}%"))
    if medecin:
        query = query.where(Dossier.attending_provider.ilike(f"%{medecin}%"))
    if current_state:
        query = query.where(Dossier.current_state.ilike(f"%{current_state}%"))
    
    # Filtres de période (admission)
    def _parse_date(value: Optional[str]):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return None
    
    admit_from_dt = _parse_date(admit_from)
    admit_to_dt = _parse_date(admit_to)
    if admit_from_dt:
        query = query.where(Dossier.admit_time >= admit_from_dt)
    if admit_to_dt:
        query = query.where(Dossier.admit_time < admit_to_dt + timedelta(days=1))
    
    return session.exec(query).all()

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

        session.merge(dossier)
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


def create_dossier(session: Session, patient_id: int, ej_id: int, dossier_type: DossierType = DossierType.HOSPITALISE, admit_time: Optional[datetime] = None) -> Dossier:
    """Crée un dossier simple pour un patient."""
    seq = get_next_sequence(session, "dossier")
    dossier = Dossier(
        dossier_seq=seq,
        patient_id=patient_id,
        ej_id=ej_id,
        dossier_type=dossier_type,
        admit_time=admit_time or datetime.now(),
    )
    session.add(dossier)
    session.commit()
    session.refresh(dossier)
    return dossier


def create_dossier_with_pre_admit_venue(session: Session, dossier_data: DossierCreateSchema, patient: Patient) -> Dossier:
    """Crée un dossier et une venue de pré-admission associée.

    This is a thin wrapper used by the UI router: it creates the Dossier with a
    generated dossier_seq and then creates an initial Venue (code PRE_ADMIT)
    linked to the dossier so the rest of the app can operate normally.
    """
    from app.services.venues_service import VenueCreateSchema, create_venue

    try:
        # assign a dossier sequence
        seq = get_next_sequence(session, "dossier")
        dossier = Dossier(
            dossier_seq=seq,
            patient_id=patient.id,
            admit_time=dossier_data.admit_time,
            dossier_type=dossier_data.dossier_type,
            uf_responsabilite=dossier_data.uf_responsabilite,
            admission_source=dossier_data.admission_source,
            attending_provider=dossier_data.attending_provider,
            current_state=dossier_data.current_state,
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)

        # create a pre-admit venue
        venue_schema = VenueCreateSchema(
            dossier_id=dossier.id,
            uf_responsabilite=dossier.uf_responsabilite or "",
            start_time=dossier.admit_time,
            code="PRE_ADMIT",
            label="Pré-admission automatique",
        )
        create_venue(session=session, venue_data=venue_schema)

        logger.info(f"Dossier {dossier.id} et pré-admission créés pour patient {patient.id}")
        return dossier
    except Exception:
        session.rollback()
        raise
