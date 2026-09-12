"""Résolution des UF et médecins pour une livraison de scénario.

La résolution est déterministe et ne modifie jamais les templates :
configuration de la cible, médecin responsable de son UF, configuration EJ
historique, puis paire UF/médecin active de la structure locale.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlmodel import Session, select

from app.models_endpoints import SystemEndpoint
from app.models_practitioners import MedecinResponsable
from app.models_scenario_config import ScenarioEJConfig, get_location_for_event, get_medecin_for_event
from app.models_scenario_target_profiles import ScenarioTargetLocation, ScenarioTargetProfile
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_structure import EntiteGeographique, Pole, Service, UniteFonctionnelle
from app.services.scenario_qualification_service import target_key


ROLE_LABELS = {
    "hospitalisation": "Hospitalisation",
    "externe": "Consultation / externe",
    "urgences": "Urgences",
    "mutation": "Mutation / transfert",
    "hopital_jour": "Hôpital de jour / séance",
    "laboratoire": "Laboratoire",
}


def scenario_role(step: InteropScenarioStep) -> str:
    """Déduit un rôle stable sans imposer un nouveau champ aux catalogues."""
    message_type = (step.message_type or "").upper()
    payload = (step.payload or "").upper()
    event = ""
    for value in (message_type, payload):
        for code in ("A01", "A02", "A04", "A05", "A06", "A07", "A10", "A12", "A38"):
            if code in value:
                event = code
                break
        if event:
            break
    if event in {"A04", "A05", "A38"}:
        return "externe"
    if event in {"A02", "A06", "A07", "A12"}:
        return "mutation"
    if event == "A10":
        return "urgences"
    if "HPRIM" in message_type or (step.message_format or "").lower() in {"xml", "hprim", "hprimxml"}:
        # Les scénarios d'actes historiques s'appuient sur l'UF externe.
        return "externe"
    return "hospitalisation"


def _practitioner_data(practitioner: Optional[MedecinResponsable]) -> dict[str, str]:
    if not practitioner:
        return {}
    rpps, adeli = practitioner.rpps or "", practitioner.adeli or ""
    identifier, kind = (rpps, "RPPS") if rpps else (adeli, "ADELI")
    oid = "1.2.250.1.71.4.2.1" if kind == "RPPS" else "1.2.250.1.71.4.2.1.1"
    family, given, prefix = practitioner.family_name or "MEDECIN", practitioner.given_name or "SCENARIO", practitioner.prefix or "Dr"
    return {
        "id": identifier,
        "rpps": rpps,
        "adeli": adeli,
        "family": family,
        "given": given,
        "prefix": prefix,
        "specialty": practitioner.specialty or "",
        "name": " ".join(part for part in (prefix, given, family) if part),
        "xcn": f"{identifier}^{family}^{given}^^^{prefix}^^{kind}^{oid}^L" if identifier else "",
    }


def _is_active_uf(uf: UniteFonctionnelle) -> bool:
    return str(uf.status or "active").lower() not in {"inactive", "suspended"}


def _find_profile(session: Session, endpoint: SystemEndpoint) -> Optional[ScenarioTargetProfile]:
    key = target_key(endpoint.target_system_key or endpoint.name)
    return session.exec(
        select(ScenarioTargetProfile)
        .where(ScenarioTargetProfile.target_system_key == key)
        .where(ScenarioTargetProfile.is_active == True)  # noqa: E712
    ).first()


def _profile_location(session: Session, profile: Optional[ScenarioTargetProfile], role: str) -> Optional[ScenarioTargetLocation]:
    if not profile:
        return None
    return session.exec(
        select(ScenarioTargetLocation)
        .where(ScenarioTargetLocation.profile_id == profile.id)
        .where(ScenarioTargetLocation.role == role)
    ).first()


def _local_ufs(session: Session, ej_id: Optional[int]) -> list[UniteFonctionnelle]:
    query = select(UniteFonctionnelle).order_by(UniteFonctionnelle.identifier, UniteFonctionnelle.id)
    if ej_id:
        query = (
            query.join(Service, UniteFonctionnelle.service_id == Service.id)
            .join(Pole, Service.pole_id == Pole.id)
            .join(EntiteGeographique, Pole.entite_geo_id == EntiteGeographique.id)
            .where(EntiteGeographique.entite_juridique_id == ej_id)
        )
    return [uf for uf in session.exec(query).all() if _is_active_uf(uf)]


def _legacy_context(session: Session, ej_id: Optional[int], role: str) -> tuple[Optional[UniteFonctionnelle], dict[str, str], Optional[str], Optional[str]]:
    if not ej_id:
        return None, {}, None, None
    config = session.exec(select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == ej_id)).first()
    if not config:
        return None, {}, None, None
    event = {"hospitalisation": "A01", "externe": "A04", "urgences": "A10", "mutation": "A02"}.get(role, "A01")
    location = get_location_for_event(config, event, session)
    uf = next((item for item in _local_ufs(session, ej_id) if item.identifier == location["uf_code"]), None)
    doctor = get_medecin_for_event(config, event) or {}
    rpps = doctor.get("rpps", "") if doctor else ""
    family, given, prefix = (doctor.get("nom", "MEDECIN"), doctor.get("prenom", ""), "Dr") if doctor else ("", "", "")
    practitioner = {
        "id": rpps, "rpps": rpps, "adeli": "", "family": family, "given": given,
        "prefix": prefix, "specialty": "", "name": " ".join(item for item in (prefix, given, family) if item),
        "xcn": f"{rpps}^{family}^{given}^^^{prefix}^^RPPS^1.2.250.1.71.4.2.1^L" if rpps else "",
    } if doctor else {}
    return uf, practitioner, location.get("room"), location.get("bed")


def resolve_target_context(
    session: Session, scenario: InteropScenario, step: InteropScenarioStep, endpoint: SystemEndpoint
) -> dict[str, Any]:
    """Retourne la projection clinique effective pour une livraison.

    Une absence de paramétrage ne rend pas le scénario inutilisable : la
    première paire UF/médecin active de la structure de destination est prise.
    Un contexte global de recette reste le dernier secours explicite pour les
    bases volontairement minimales, avec une provenance traçable.
    """
    role = scenario_role(step)
    profile = _find_profile(session, endpoint)
    ej_id = (profile.entite_juridique_id if profile and profile.entite_juridique_id else endpoint.entite_juridique_id)
    location = _profile_location(session, profile, role)
    source = "target_profile" if location else ""
    uf = session.get(UniteFonctionnelle, location.unite_fonctionnelle_id) if location and location.unite_fonctionnelle_id else None
    doctor = session.get(MedecinResponsable, location.medecin_responsable_id) if location and location.medecin_responsable_id else None
    room, bed = (location.room if location else None), (location.bed if location else None)
    if uf and not _is_active_uf(uf):
        uf = None
        source = ""
    if doctor and not doctor.active:
        doctor = None
    if uf and not doctor and uf.medecin_responsable_id:
        candidate = session.get(MedecinResponsable, uf.medecin_responsable_id)
        doctor = candidate if candidate and candidate.active else None
    if not uf:
        legacy_uf, legacy_doctor, legacy_room, legacy_bed = _legacy_context(session, ej_id, role)
        if legacy_uf:
            uf, room, bed, source = legacy_uf, legacy_room, legacy_bed, "legacy_ej_config"
            if not doctor and legacy_doctor:
                practitioner = legacy_doctor
            else:
                practitioner = _practitioner_data(doctor)
        else:
            practitioner = _practitioner_data(doctor)
    else:
        practitioner = _practitioner_data(doctor)
    if not uf:
        # Repli demandé : choisir une UF et son médecin responsable dans la
        # structure cible. Les paires associées sont prioritaires.
        candidates = _local_ufs(session, ej_id)
        paired = next(
            (
                item for item in candidates
                if item.medecin_responsable_id
                and (candidate := session.get(MedecinResponsable, item.medecin_responsable_id))
                and candidate.active
            ),
            None,
        )
        uf = paired or (candidates[0] if candidates else None)
        if uf and not doctor and uf.medecin_responsable_id:
            doctor = session.get(MedecinResponsable, uf.medecin_responsable_id)
        practitioner = _practitioner_data(doctor)
        # N'annoncer un repli structurel complet que lorsqu'une paire est bien
        # disponible. Sinon le compilateur utilisera son praticien de recette
        # explicitement signalé, sans faire croire à une association UF/médecin.
        source = "structure_fallback" if uf and doctor else "global_fallback"
    code = (uf.identifier or uf.name) if uf else ""
    facility = endpoint.receiving_facility or endpoint.sending_facility or code
    return {
        "target_system_key": target_key(endpoint.target_system_key or endpoint.name),
        "profile_id": profile.id if profile else None,
        "role": role,
        "role_label": ROLE_LABELS.get(role, role),
        "source": source,
        "location": {
            "uf_id": uf.id if uf else None, "code": code, "room": room or "", "bed": bed or "",
            "pv1_3": f"{code}^{room or ''}^{bed or ''}^{facility or ''}^ACTIVE" if code else "",
        },
        "practitioner": practitioner,
    }
