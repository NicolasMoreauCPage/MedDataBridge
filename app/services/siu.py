"""Validation et intégration des rendez-vous HL7 v2 SIU.

Le périmètre est volontairement distinct d'IHE PAM : les segments SCH, RGS,
AIS, AIL et AIP portent des informations de planification, pas des mouvements
administratifs de séjour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.models import Patient
from app.models_appointments import Appointment
from app.services.mllp import parse_msh_fields
from app.services.pam_validation import ValidationIssue, ValidationResult


_SIU_ACTIONS = {
    "S12": "booked",      # nouveau rendez-vous
    "S13": "booked",      # modification de rendez-vous
    "S14": "completed",   # modification de statut / réalisation
    "S15": "cancelled",   # annulation
    "S26": "cancelled",   # suppression
}


@dataclass(frozen=True)
class SIUAppointmentData:
    external_id: str
    assigning_authority: str
    patient_identifier: Optional[str]
    start_at: Optional[datetime]
    end_at: Optional[datetime]
    service_code: Optional[str]
    location_code: Optional[str]
    practitioner_identifier: Optional[str]
    status: str
    trigger: str


def _segments(message: str) -> list[str]:
    return [line for line in message.replace("\\r\\n", "\r").replace("\\n", "\r").replace("\\r", "\r").replace("\n", "\r").split("\r") if line]


def _segment(message: str, name: str) -> list[str]:
    line = next((item for item in _segments(message) if item.startswith(f"{name}|")), "")
    return line.split("|") if line else []


def _cx(value: str) -> tuple[str, str]:
    parts = (value or "").split("^")
    return (parts[0].strip() if parts else "", parts[3].strip() if len(parts) > 3 else "")


def _date_values(fields: list[str]) -> list[datetime]:
    values: list[datetime] = []
    for value in fields:
        for raw in re.findall(r"(?<!\d)(\d{8}(?:\d{4}(?:\d{2})?)?)(?!\d)", value or ""):
            for pattern in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"):
                try:
                    values.append(datetime.strptime(raw, pattern))
                    break
                except ValueError:
                    continue
    return values


def parse_siu(message: str) -> SIUAppointmentData:
    """Extrait les données utilisables des segments HL7 Scheduling."""
    msh = parse_msh_fields(message)
    sch = _segment(message, "SCH")
    pid = _segment(message, "PID")
    ais = _segment(message, "AIS")
    ail = _segment(message, "AIL")
    aip = _segment(message, "AIP")
    placer = sch[1] if len(sch) > 1 else ""
    filler = sch[2] if len(sch) > 2 else ""
    external_id, authority = _cx(placer or filler)
    dates = _date_values(sch)
    patient_identifier, _ = _cx(pid[3] if len(pid) > 3 else "")
    service_code, _ = _cx(ais[3] if len(ais) > 3 else "")
    location_code, _ = _cx(ail[3] if len(ail) > 3 else "")
    practitioner_identifier, _ = _cx(aip[3] if len(aip) > 3 else "")
    trigger = msh.get("trigger") or ""
    return SIUAppointmentData(
        external_id=external_id,
        assigning_authority=authority,
        patient_identifier=patient_identifier or None,
        start_at=dates[0] if dates else None,
        end_at=dates[1] if len(dates) > 1 else None,
        service_code=service_code or None,
        location_code=location_code or None,
        practitioner_identifier=practitioner_identifier or None,
        status=_SIU_ACTIONS.get(trigger, "booked"),
        trigger=trigger,
    )


def validate_siu(message: str, direction: str = "in") -> ValidationResult:
    """Contrôle structurel léger des flux SIU sans appliquer le profil PAM."""
    msh = parse_msh_fields(message)
    issues: list[ValidationIssue] = []
    if msh.get("type") != "SIU":
        issues.append(ValidationIssue("SIU_MSH9", "MSH-9 doit désigner un message SIU^Sxx.", severity="error"))
    if not msh.get("trigger"):
        issues.append(ValidationIssue("SIU_TRIGGER", "Le déclencheur SIU (MSH-9.2) est requis.", severity="error"))
    if not _segment(message, "SCH"):
        issues.append(ValidationIssue("SIU_SCH_MISSING", "Le segment SCH est requis pour un rendez-vous SIU.", severity="error"))
    else:
        data = parse_siu(message)
        if not data.external_id:
            issues.append(ValidationIssue("SIU_ID_MISSING", "SCH-1 ou SCH-2 doit contenir l'identifiant du rendez-vous.", severity="error"))
        if not data.patient_identifier:
            issues.append(ValidationIssue("SIU_PID_MISSING", "PID-3 est absent : rendez-vous non rattaché à un patient.", severity="warn"))
        if not data.start_at:
            issues.append(ValidationIssue("SIU_START_MISSING", "Date/heure de rendez-vous absente de SCH.", severity="warn"))
    level = "fail" if any(item.severity == "error" for item in issues) else "warn" if issues else "ok"
    return ValidationResult(
        is_valid=level != "fail", level=level, event=msh.get("trigger") or "", message_type=msh.get("msg_type") or "SIU", issues=issues,
    )


def integrate_siu(message: str, session: Session, *, endpoint_id: Optional[int] = None) -> Appointment:
    """Crée ou met à jour le rendez-vous représenté par un SIU entrant."""
    data = parse_siu(message)
    if not data.external_id:
        raise ValueError("Identifiant de rendez-vous SCH-1/SCH-2 absent")
    appointment = session.exec(
        select(Appointment)
        .where(Appointment.external_id == data.external_id)
        .where(Appointment.assigning_authority == data.assigning_authority)
    ).first()
    patient = None
    if data.patient_identifier:
        patient = session.exec(select(Patient).where(Patient.identifier == data.patient_identifier)).first()
    if not appointment:
        appointment = Appointment(external_id=data.external_id, assigning_authority=data.assigning_authority)
    appointment.patient_identifier = data.patient_identifier
    appointment.patient_id = patient.id if patient else None
    appointment.status, appointment.start_at, appointment.end_at = data.status, data.start_at, data.end_at
    appointment.service_code, appointment.location_code = data.service_code, data.location_code
    appointment.practitioner_identifier, appointment.last_trigger = data.practitioner_identifier, data.trigger
    appointment.source_endpoint_id, appointment.source_payload, appointment.updated_at = endpoint_id, message, datetime.utcnow()
    session.add(appointment)
    session.flush()
    return appointment
