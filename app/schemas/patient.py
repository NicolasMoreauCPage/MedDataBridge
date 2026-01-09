from pydantic import BaseModel
from typing import Optional
from datetime import date


class PatientFormData(BaseModel):
    """Schéma pour les données de formulaire patient"""
    external_id: Optional[str] = None
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