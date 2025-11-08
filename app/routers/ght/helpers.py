"""Helper functions for GHT routes: form fields, validation, entity getters"""
from typing import Dict, List, Optional
from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.models_structure_fhir import (
    EntiteJuridique,
    GHTContext,
    EntiteGeographique,
)
from app.models_structure import (
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
    Chambre,
    Lit,
    LocationStatus,
    LocationMode,
    LocationPhysicalType,
    LocationServiceType,
)
from app.services.vocabulary_lookup import get_vocabulary_options

templates = Jinja2Templates(directory="app/templates")


# Entity getters with 404 handling
def get_context_or_404(session: Session, context_id: int) -> GHTContext:
    context = session.get(GHTContext, context_id)
    if not context:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    return context


def get_ej_or_404(
    session: Session, context: GHTContext, ej_id: int
) -> EntiteJuridique:
    entite = session.exec(
        select(EntiteJuridique)
        .where(EntiteJuridique.id == ej_id)
        .where(EntiteJuridique.ght_context_id == context.id)
    ).first()
    if not entite:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    return entite


def get_entite_geo_or_404(
    session: Session, entite: EntiteJuridique, eg_id: int
) -> EntiteGeographique:
    entite_geo = session.exec(
        select(EntiteGeographique)
        .where(EntiteGeographique.id == eg_id)
        .where(EntiteGeographique.entite_juridique_id == entite.id)
    ).first()
    if not entite_geo:
        raise HTTPException(status_code=404, detail="Entité géographique non trouvée")
    return entite_geo


def get_pole_or_404(
    session: Session, entite_geo: EntiteGeographique, pole_id: int
) -> Pole:
    pole = session.exec(
        select(Pole)
        .where(Pole.id == pole_id)
        .where(Pole.entite_geo_id == entite_geo.id)
    ).first()
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")
    return pole


def get_service_or_404(
    session: Session, pole: Pole, service_id: int
) -> Service:
    service = session.exec(
        select(Service)
        .where(Service.id == service_id)
        .where(Service.pole_id == pole.id)
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")
    return service


def get_uf_or_404(
    session: Session, service: Service, uf_id: int
) -> UniteFonctionnelle:
    uf = session.exec(
        select(UniteFonctionnelle)
        .where(UniteFonctionnelle.id == uf_id)
        .where(UniteFonctionnelle.service_id == service.id)
    ).first()
    if not uf:
        raise HTTPException(status_code=404, detail="Unité fonctionnelle non trouvée")
    return uf


def get_uh_or_404(
    session: Session, uf: UniteFonctionnelle, uh_id: int
) -> UniteHebergement:
    uh = session.exec(
        select(UniteHebergement)
        .where(UniteHebergement.id == uh_id)
        .where(UniteHebergement.unite_fonctionnelle_id == uf.id)
    ).first()
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    return uh


def get_chambre_or_404(
    session: Session, uh: UniteHebergement, chambre_id: int
) -> Chambre:
    chambre = session.exec(
        select(Chambre)
        .where(Chambre.id == chambre_id)
        .where(Chambre.unite_hebergement_id == uh.id)
    ).first()
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")
    return chambre


def get_lit_or_404(
    session: Session, chambre: Chambre, lit_id: int
) -> Lit:
    lit = session.exec(
        select(Lit)
        .where(Lit.id == lit_id)
        .where(Lit.chambre_id == chambre.id)
    ).first()
    if not lit:
        raise HTTPException(status_code=404, detail="Lit non trouvé")
    return lit


# Labels for enums
STATUS_LABELS = {
    LocationStatus.ACTIVE.value: "Actif",
    LocationStatus.SUSPENDED.value: "Suspendu",
    LocationStatus.INACTIVE.value: "Inactif",
}

MODE_LABELS = {
    LocationMode.INSTANCE.value: "Instance",
    LocationMode.KIND.value: "Type",
}

PHYSICAL_TYPE_LABELS = {
    LocationPhysicalType.SI.value: "Site (si)",
    LocationPhysicalType.BU.value: "Bâtiment (bu)",
    LocationPhysicalType.WI.value: "Aile (wi)",
    LocationPhysicalType.FL.value: "Étage (fl)",
    LocationPhysicalType.RO.value: "Chambre (ro)",
    LocationPhysicalType.BD.value: "Lit (bd)",
    LocationPhysicalType.VE.value: "Véhicule (ve)",
    LocationPhysicalType.HO.value: "Domicile (ho)",
    LocationPhysicalType.CA.value: "Cabinet (ca)",
    LocationPhysicalType.RD.value: "Route (rd)",
    LocationPhysicalType.AREA.value: "Zone (area)",
    LocationPhysicalType.JDN.value: "Juridiction (jdn)",
}

SERVICE_TYPE_LABELS = {
    LocationServiceType.MCO.value: "Médecine/Chirurgie/Obstétrique (MCO)",
    LocationServiceType.SSR.value: "Soins de suite et de réadaptation (SSR)",
    LocationServiceType.PSY.value: "Psychiatrie (PSY)",
    LocationServiceType.HAD.value: "Hospitalisation à domicile (HAD)",
    LocationServiceType.EHPAD.value: "EHPAD",
    LocationServiceType.USLD.value: "Unités de soins longue durée (USLD)",
}

PHYSICAL_TYPE_DEFAULTS = {
    "entite_geographique": LocationPhysicalType.SI,
    "pole": LocationPhysicalType.AREA,
    "service": LocationPhysicalType.AREA,
    "uf": LocationPhysicalType.AREA,
    "uh": LocationPhysicalType.FL,
    "chambre": LocationPhysicalType.RO,
    "lit": LocationPhysicalType.BD,
}


# Form options builders
def status_options() -> List[dict]:
    """Options de statut depuis vocabulaires paramétrables (fallback enum)."""
    return get_vocabulary_options("location-status") or [
        {"value": status.value, "label": STATUS_LABELS.get(status.value, status.value)}
        for status in LocationStatus
    ]


def mode_options() -> List[dict]:
    """Options de mode depuis vocabulaires paramétrables (fallback enum)."""
    return get_vocabulary_options("location-mode") or [
        {"value": mode.value, "label": MODE_LABELS.get(mode.value, mode.value)}
        for mode in LocationMode
    ]


def physical_type_options() -> List[dict]:
    """Options de type physique depuis vocabulaires paramétrables (fallback enum)."""
    return get_vocabulary_options("location-physical-type") or [
        {"value": typ.value, "label": PHYSICAL_TYPE_LABELS.get(typ.value, typ.value)}
        for typ in LocationPhysicalType
    ]


def service_type_options() -> List[dict]:
    """Options de type de service depuis vocabulaires paramétrables (fallback enum)."""
    return get_vocabulary_options("location-service-type") or [
        {
            "value": service_type.value,
            "label": SERVICE_TYPE_LABELS.get(service_type.value, service_type.value),
        }
        for service_type in LocationServiceType
    ]


def resolve_physical_type(entity_name: str, current: Optional[str]) -> LocationPhysicalType:
    if current:
        try:
            return LocationPhysicalType(current)
        except ValueError:
            pass
    return PHYSICAL_TYPE_DEFAULTS[entity_name]


def maybe(value: Optional[str]) -> Optional[str]:
    """Strip whitespace and return None for empty strings"""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


# Form field builders for each entity type
def pole_form_fields(pole: Optional[Pole] = None) -> List[dict]:
    return [
        {
            "name": "identifier",
            "label": "Identifiant global",
            "type": "text",
            "required": True,
            "value": pole.identifier if pole else "",
        },
        {
            "name": "name",
            "label": "Nom",
            "type": "text",
            "required": True,
            "value": pole.name if pole else "",
        },
        {
            "name": "short_name",
            "label": "Nom court",
            "type": "text",
            "value": pole.short_name if pole else "",
        },
        {
            "name": "description",
            "label": "Description",
            "type": "text",
            "value": pole.description if pole else "",
        },
        {
            "name": "status",
            "label": "Statut",
            "type": "select",
            "options": status_options(),
            "value": (pole.status.value if isinstance(pole.status, LocationStatus) else getattr(pole, "status", LocationStatus.ACTIVE.value))
            if pole
            else LocationStatus.ACTIVE.value,
        },
        {
            "name": "mode",
            "label": "Mode",
            "type": "select",
            "options": mode_options(),
            "value": (pole.mode.value if isinstance(pole.mode, LocationMode) else getattr(pole, "mode", LocationMode.INSTANCE.value))
            if pole
            else LocationMode.INSTANCE.value,
        },
    ]


def service_form_fields(service: Optional[Service] = None) -> List[dict]:
    return [
        {
            "name": "identifier",
            "label": "Identifiant global",
            "type": "text",
            "required": True,
            "value": service.identifier if service else "",
        },
        {
            "name": "name",
            "label": "Nom du service",
            "type": "text",
            "required": True,
            "value": service.name if service else "",
        },
        {
            "name": "short_name",
            "label": "Nom court",
            "type": "text",
            "value": service.short_name if service else "",
        },
        {
            "name": "description",
            "label": "Description",
            "type": "text",
            "value": service.description if service else "",
        },
        {
            "name": "status",
            "label": "Statut",
            "type": "select",
            "options": status_options(),
            "value": (service.status.value if isinstance(service.status, LocationStatus) else getattr(service, "status", LocationStatus.ACTIVE.value))
            if service
            else LocationStatus.ACTIVE.value,
        },
        {
            "name": "mode",
            "label": "Mode",
            "type": "select",
            "options": mode_options(),
            "value": (service.mode.value if isinstance(service.mode, LocationMode) else getattr(service, "mode", LocationMode.INSTANCE.value))
            if service
            else LocationMode.INSTANCE.value,
        },
        {
            "name": "service_type",
            "label": "Type de service",
            "type": "select",
            "options": service_type_options(),
            "value": (service.service_type.value if isinstance(service.service_type, LocationServiceType) else getattr(service, "service_type", LocationServiceType.MCO.value))
            if service
            else LocationServiceType.MCO.value,
        },
        {
            "name": "typology",
            "label": "Typologie",
            "type": "text",
            "value": service.typology if service else "",
        },
    ]


def uf_form_fields(uf: Optional[UniteFonctionnelle] = None) -> List[dict]:
    return [
        {
            "name": "identifier",
            "label": "Identifiant global",
            "type": "text",
            "required": True,
            "value": uf.identifier if uf else "",
        },
        {
            "name": "name",
            "label": "Nom de l'UF",
            "type": "text",
            "required": True,
            "value": uf.name if uf else "",
        },
        {
            "name": "short_name",
            "label": "Nom court",
            "type": "text",
            "value": uf.short_name if uf else "",
        },
        {
            "name": "description",
            "label": "Description",
            "type": "text",
            "value": uf.description if uf else "",
        },
        {
            "name": "status",
            "label": "Statut",
            "type": "select",
            "options": status_options(),
            "value": (uf.status.value if isinstance(uf.status, LocationStatus) else getattr(uf, "status", LocationStatus.ACTIVE.value))
            if uf
            else LocationStatus.ACTIVE.value,
        },
        {
            "name": "mode",
            "label": "Mode",
            "type": "select",
            "options": mode_options(),
            "value": (uf.mode.value if isinstance(uf.mode, LocationMode) else getattr(uf, "mode", LocationMode.INSTANCE.value))
            if uf
            else LocationMode.INSTANCE.value,
        },
        {
            "name": "um_code",
            "label": "Code UM",
            "type": "text",
            "value": uf.um_code if uf else "",
        },
        {
            "name": "uf_type",
            "label": "Type d'UF",
            "type": "text",
            "value": uf.uf_type if uf else "",
        },
    ]


def uh_form_fields(uh: Optional[UniteHebergement] = None) -> List[dict]:
    return [
        {
            "name": "identifier",
            "label": "Identifiant global",
            "type": "text",
            "required": True,
            "value": uh.identifier if uh else "",
        },
        {
            "name": "name",
            "label": "Nom de l'UH",
            "type": "text",
            "required": True,
            "value": uh.name if uh else "",
        },
        {
            "name": "short_name",
            "label": "Nom court",
            "type": "text",
            "value": uh.short_name if uh else "",
        },
        {
            "name": "description",
            "label": "Description",
            "type": "text",
            "value": uh.description if uh else "",
        },
        {
            "name": "status",
            "label": "Statut",
            "type": "select",
            "options": status_options(),
            "value": (uh.status.value if isinstance(uh.status, LocationStatus) else getattr(uh, "status", LocationStatus.ACTIVE.value))
            if uh
            else LocationStatus.ACTIVE.value,
        },
        {
            "name": "mode",
            "label": "Mode",
            "type": "select",
            "options": mode_options(),
            "value": (uh.mode.value if isinstance(uh.mode, LocationMode) else getattr(uh, "mode", LocationMode.INSTANCE.value))
            if uh
            else LocationMode.INSTANCE.value,
        },
        {
            "name": "etage",
            "label": "Étage",
            "type": "text",
            "value": uh.etage if uh else "",
        },
        {
            "name": "aile",
            "label": "Aile",
            "type": "text",
            "value": uh.aile if uh else "",
        },
    ]


def chambre_form_fields(chambre: Optional[Chambre] = None) -> List[dict]:
    return [
        {
            "name": "identifier",
            "label": "Identifiant global",
            "type": "text",
            "required": True,
            "value": chambre.identifier if chambre else "",
        },
        {
            "name": "name",
            "label": "Nom de la chambre",
            "type": "text",
            "required": True,
            "value": chambre.name if chambre else "",
        },
        {
            "name": "short_name",
            "label": "Nom court",
            "type": "text",
            "value": chambre.short_name if chambre else "",
        },
        {
            "name": "description",
            "label": "Description",
            "type": "text",
            "value": chambre.description if chambre else "",
        },
        {
            "name": "status",
            "label": "Statut",
            "type": "select",
            "options": status_options(),
            "value": (chambre.status.value if isinstance(chambre.status, LocationStatus) else getattr(chambre, "status", LocationStatus.ACTIVE.value))
            if chambre
            else LocationStatus.ACTIVE.value,
        },
        {
            "name": "mode",
            "label": "Mode",
            "type": "select",
            "options": mode_options(),
            "value": (chambre.mode.value if isinstance(chambre.mode, LocationMode) else getattr(chambre, "mode", LocationMode.INSTANCE.value))
            if chambre
            else LocationMode.INSTANCE.value,
        },
        {
            "name": "type_chambre",
            "label": "Type de chambre",
            "type": "text",
            "value": chambre.type_chambre if chambre else "",
        },
        {
            "name": "gender_usage",
            "label": "Usage (genre)",
            "type": "text",
            "value": chambre.gender_usage if chambre else "",
        },
    ]


def lit_form_fields(lit: Optional[Lit] = None) -> List[dict]:
    return [
        {
            "name": "identifier",
            "label": "Identifiant global",
            "type": "text",
            "required": True,
            "value": lit.identifier if lit else "",
        },
        {
            "name": "name",
            "label": "Nom du lit",
            "type": "text",
            "required": True,
            "value": lit.name if lit else "",
        },
        {
            "name": "short_name",
            "label": "Nom court",
            "type": "text",
            "value": lit.short_name if lit else "",
        },
        {
            "name": "description",
            "label": "Description",
            "type": "text",
            "value": lit.description if lit else "",
        },
        {
            "name": "status",
            "label": "Statut",
            "type": "select",
            "options": status_options(),
            "value": (lit.status.value if isinstance(lit.status, LocationStatus) else getattr(lit, "status", LocationStatus.ACTIVE.value))
            if lit
            else LocationStatus.ACTIVE.value,
        },
        {
            "name": "mode",
            "label": "Mode",
            "type": "select",
            "options": mode_options(),
            "value": (lit.mode.value if isinstance(lit.mode, LocationMode) else getattr(lit, "mode", LocationMode.INSTANCE.value))
            if lit
            else LocationMode.INSTANCE.value,
        },
        {
            "name": "operational_status",
            "label": "Statut opérationnel",
            "type": "text",
            "value": lit.operational_status if lit else "",
        },
    ]


def with_form_values(fields: List[dict], data: dict) -> List[dict]:
    """Update form fields with values from submitted data"""
    filled = []
    for field in fields:
        field_copy = field.copy()
        name = field_copy.get("name")
        if name in data:
            field_copy["value"] = data[name]
        filled.append(field_copy)
    return filled


def render_form(
    request: Request,
    title: str,
    fields: List[dict],
    action_url: str,
    cancel_url: str,
    error: Optional[str] = None,
    status_code: int = 200,
):
    """Render generic form template with provided fields"""
    return templates.TemplateResponse(
        "forms.html",
        {
            "request": request,
            "title": title,
            "fields": fields,
            "action_url": action_url,
            "cancel_url": cancel_url,
            "error": error,
        },
        status_code=status_code,
    )
