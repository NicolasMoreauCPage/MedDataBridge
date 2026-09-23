"""Contrats de sortie stables pour les listes JSON de structure."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models_structure import LocationPhysicalType


class StructureLocationRead(BaseModel):
    """Colonnes communes exposées par les niveaux de structure."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    identifier: Optional[str] = None
    global_identifier: Optional[str] = None
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    address_city: Optional[str] = None
    address_postalcode: Optional[str] = None
    address_country: Optional[str] = None
    opening_date: Optional[datetime | str] = None
    activation_date: Optional[datetime | str] = None
    closing_date: Optional[datetime | str] = None
    deactivation_date: Optional[datetime | str] = None
    status: Optional[str] = None
    mode: Optional[str] = None
    physical_type: Optional[LocationPhysicalType] = None


class ClinicalLocationRead(StructureLocationRead):
    """Champs fonctionnels partagés à partir du niveau service."""

    typology: Optional[str] = None
    uf_type: Optional[str] = None
    etage: Optional[str] = None
    aile: Optional[str] = None
    type_chambre: Optional[str] = None
    gender_usage: Optional[str] = None
    operational_status: Optional[str] = None


class EntiteGeographiqueRead(ClinicalLocationRead):
    identifier: str
    name: str
    address_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    type: Optional[str] = None
    responsible_id: Optional[str] = None
    responsible_name: Optional[str] = None
    responsible_firstname: Optional[str] = None
    responsible_email: Optional[str] = None
    responsible_phone: Optional[str] = None
    responsible_rpps: Optional[str] = None
    responsible_adeli: Optional[str] = None
    responsible_specialty: Optional[str] = None
    entite_juridique_id: Optional[int] = None
    finess: Optional[str] = None
    category_code: Optional[str] = None
    category_name: Optional[str] = None
    category_sae: Optional[str] = None
    city_insee_code: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class PoleRead(StructureLocationRead):
    entite_geo_id: Optional[int] = None
    entite_juridique_id: Optional[int] = None
    responsible_id: Optional[str] = None


class ServiceRead(ClinicalLocationRead):
    service_type: Optional[str] = None
    pole_id: Optional[int] = None
    responsible_id: Optional[str] = None
    responsible_name: Optional[str] = None
    responsible_firstname: Optional[str] = None
    responsible_rpps: Optional[str] = None
    responsible_adeli: Optional[str] = None
    responsible_specialty: Optional[str] = None


class UniteFonctionnelleRead(ClinicalLocationRead):
    um_code: Optional[str] = None
    service_id: Optional[int] = None
    medecin_responsable_id: Optional[int] = None


class UniteHebergementRead(ClinicalLocationRead):
    unite_fonctionnelle_id: Optional[int] = None


class ChambreRead(ClinicalLocationRead):
    unite_hebergement_id: Optional[int] = None
    is_generic: Optional[bool] = None
    max_occupancy: Optional[int] = None


class LitRead(ClinicalLocationRead):
    chambre_id: Optional[int] = None
    is_generic: Optional[bool] = None
    max_occupancy: Optional[int] = None
