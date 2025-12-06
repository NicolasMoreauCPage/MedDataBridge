from typing import Optional
from uuid import uuid4
from sqlmodel import Session
from pydantic import BaseModel
from app.models import Patient
from sqlalchemy.orm import attributes

class PatientCreateSchema(BaseModel):
    """Schéma de données pour la création d'un patient."""
    identifier: Optional[str] = None
    family: str
    given: str
    middle: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    birth_family: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    work_phone: Optional[str] = None
    email: Optional[str] = None
    birth_address: Optional[str] = None
    birth_city: Optional[str] = None
    birth_state: Optional[str] = None
    birth_postal_code: Optional[str] = None
    birth_country: Optional[str] = None
    nir: Optional[str] = None
    marital_status: Optional[str] = None
    nationality: Optional[str] = None
    identity_reliability_code: Optional[str] = None
    mothers_maiden_name: Optional[str] = None
    primary_care_provider: Optional[str] = None

class PatientUpdateSchema(PatientCreateSchema):
    """Schéma de données pour la mise à jour d'un patient."""
    pass

def create_patient(
    session: Session, 
    patient_data: PatientCreateSchema, 
    ght_context_id: Optional[int] = None
) -> Patient:
    """
    Crée un nouveau patient en base de données.
    Gère la logique de génération d'identifiant et la transaction.
    """
    identifier_val = patient_data.identifier or str(uuid4())
    data = patient_data.dict()
    birth_date_raw = data.get("birth_date")
    birth_date_obj = None
    if birth_date_raw:
        from datetime import datetime, date
        if isinstance(birth_date_raw, str):
            try:
                # Gère les formats YYYY-MM-DD et YYYYMMDD
                if len(birth_date_raw) == 8 and birth_date_raw.isdigit():
                    birth_date_obj = datetime.strptime(birth_date_raw, "%Y%m%d").date()
                else:
                    birth_date_obj = datetime.strptime(birth_date_raw, "%Y-%m-%d").date()
            except Exception:
                birth_date_obj = None
        elif isinstance(birth_date_raw, date):
            birth_date_obj = birth_date_raw
    data["birth_date"] = birth_date_obj
    patient = Patient(
        **data,
        identifier=identifier_val,
        ght_context_id=ght_context_id
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient

def update_patient(
    session: Session, 
    patient: Patient, 
    patient_data: PatientUpdateSchema
) -> Patient:
    """
    Met à jour un patient existant en base de données.
    """
    update_data = patient_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(patient, key, value)
    
    session.add(patient)
    # Force la détection de modification pour les événements SQLAlchemy
    attributes.flag_modified(patient, "family")
    session.flush()
    session.commit()
    session.refresh(patient)
    return patient
