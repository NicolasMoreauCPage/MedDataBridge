"""Stable API contracts for clinical persistence models."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models import DossierType


class OrmReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PatientRead(OrmReadModel):
    id: int
    identifier: Optional[str] = None
    ght_context_id: Optional[int] = None
    entite_juridique_id: Optional[int] = None
    family: str
    given: Optional[str] = None
    middle: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    birth_family: Optional[str] = None
    birth_date: Optional[date] = None
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
    identity_reliability_code: Optional[str] = None
    identity_reliability_date: Optional[date] = None
    identity_reliability_source: Optional[str] = None
    identity_matrix_code: Optional[str] = None
    nir: Optional[str] = None
    ins_c: Optional[str] = None
    ins_type: Optional[str] = None
    ins_in_annuaire: Optional[bool] = None
    ins_last_query_date: Optional[date] = None
    birth_given_names: Optional[str] = None
    used_given_name: Optional[str] = None
    birth_insee_code: Optional[str] = None
    sms_consent: Optional[str] = None
    birth_date_modified_indicator: Optional[str] = None
    identity_capture_mode: Optional[str] = None
    identity_proof_type: Optional[str] = None
    identity_proof_expiry_date: Optional[date] = None
    dmp_status: Optional[str] = None
    dmp_status_date: Optional[date] = None
    dmp_closure_date: Optional[date] = None
    dmp_feed_opposition: Optional[str] = None
    dmp_consultation_consent: Optional[str] = None
    socio_professional_activity: Optional[str] = None
    socio_professional_category: Optional[str] = None
    marital_status: Optional[str] = None
    mothers_maiden_name: Optional[str] = None
    nationality: Optional[str] = None
    place_of_birth: Optional[str] = None
    primary_care_provider: Optional[str] = None


class DossierRead(OrmReadModel):
    id: int
    dossier_seq: int
    patient_id: int
    admit_time: datetime
    discharge_time: Optional[datetime] = None
    dossier_type: DossierType
    entite_juridique_id: Optional[int] = None
    uf_responsabilite: Optional[str] = None
    medecin_responsable_id: Optional[int] = None
    admission_type: Optional[str] = None
    admission_source: Optional[str] = None
    attending_provider: Optional[str] = None
    reason: Optional[str] = None
    current_state: Optional[str] = None
    has_cotations: bool = False
    cotations_count: int = 0


class DossierUpdate(BaseModel):
    patient_id: Optional[int] = None
    dossier_seq: Optional[int] = None
    admit_time: Optional[datetime] = None
    discharge_time: Optional[datetime] = None
    dossier_type: Optional[DossierType] = None
    entite_juridique_id: Optional[int] = None
    uf_responsabilite: Optional[str] = None
    medecin_responsable_id: Optional[int] = None
    admission_type: Optional[str] = None
    admission_source: Optional[str] = None
    attending_provider: Optional[str] = None
    reason: Optional[str] = None
    current_state: Optional[str] = None
    has_cotations: Optional[bool] = None
    cotations_count: Optional[int] = None


class VenueRead(OrmReadModel):
    id: int
    venue_seq: int
    code: Optional[str] = None
    label: Optional[str] = None
    assigned_location: Optional[str] = None
    dossier_id: int
    entite_juridique_id: Optional[int] = None
    chambre_id: Optional[int] = None
    lit_id: Optional[int] = None
    uf_responsabilite: Optional[str] = None
    uf_soins_code: Optional[str] = None
    uf_soins_label: Optional[str] = None
    nature: Optional[str] = None
    hospital_service: Optional[str] = None
    attending_provider: Optional[str] = None
    start_time: datetime


class MouvementRead(OrmReadModel):
    id: int
    mouvement_seq: int
    venue_id: int
    entite_juridique_id: Optional[int] = None
    medecin_responsable_id: Optional[int] = None
    type: Optional[str] = None
    when: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    reason: Optional[str] = None
    performer: Optional[str] = None
    status: Optional[str] = None
    note: Optional[str] = None
    movement_type: Optional[str] = None
    movement_reason: Optional[str] = None
    performer_role: Optional[str] = None
    trigger_event: Optional[str] = None
    cancelled_movement_seq: Optional[int] = None
    action: Optional[str] = None
    is_historic: bool = False
    original_trigger: Optional[str] = None
    nature: Optional[str] = None
    uf_responsabilite: Optional[str] = None
    uf_soins_code: Optional[str] = None
    uf_soins_label: Optional[str] = None
    origin_facility_finess: Optional[str] = None
    origin_stay_date: Optional[str] = None
    discharge_transport_mode: Optional[str] = None
    legal_care_mode_code: Optional[str] = None
    transport_care_level: Optional[str] = None
