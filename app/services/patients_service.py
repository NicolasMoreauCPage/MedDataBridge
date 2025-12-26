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

class PatientUpdateSchema(BaseModel):
    """Schéma de données pour la mise à jour d'un patient."""
    identifier: Optional[str] = None
    family: Optional[str] = None
    given: Optional[str] = None
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
    # Sanitize string values to avoid encoding errors (lone surrogates etc.)
    import unicodedata
    def _sanitize(val):
        if isinstance(val, str):
            try:
                # Normalize to NFC and replace any surrogate codepoints (which
                # SQLite/DB drivers cannot encode) with the Unicode replacement
                # character. This avoids PendingRollbackError during commit.
                normalized = unicodedata.normalize('NFC', val)
                # Replace surrogate range U+D800..U+DFFF
                cleaned = ''.join(
                    (ch if not (0xD800 <= ord(ch) <= 0xDFFF) else '\uFFFD')
                    for ch in normalized
                )
                return cleaned
            except Exception:
                return val
        return val

    for k, v in list(data.items()):
        data[k] = _sanitize(v)
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
    # Remove identifier from data to avoid duplicate parameter
    data.pop("identifier", None)
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
    # Vérifier que le patient existe en base
    if patient.id is None or session.get(Patient, patient.id) is None:
        raise ValueError(f"Patient with id {patient.id} not found")
    
    update_data = patient_data.model_dump(exclude_unset=True)
    # Sanitize string values to prevent encoding issues on commit
    import unicodedata
    def _sanitize(val):
        if isinstance(val, str):
            try:
                normalized = unicodedata.normalize('NFC', val)
                cleaned = ''.join(
                    (ch if not (0xD800 <= ord(ch) <= 0xDFFF) else '\uFFFD')
                    for ch in normalized
                )
                return cleaned
            except Exception:
                return val
        return val

    for key, value in list(update_data.items()):
        update_data[key] = _sanitize(value)
    for key, value in update_data.items():
        if value is not None:  # Only update non-None values
            setattr(patient, key, value)
    
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient
