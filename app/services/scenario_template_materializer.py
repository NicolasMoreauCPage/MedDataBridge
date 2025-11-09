"""Matérialisation des ScenarioTemplate en InteropScenario concrets.

Ce module prend un template abstrait + un contexte (GHT/EJ, param génération identifiants)
et crée un InteropScenario avec des InteropScenarioStep payload HL7/FHIR prêts à rejouer.
"""
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from sqlmodel import Session

from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep, InteropScenario, InteropScenarioStep
from app.models_structure_fhir import EntiteJuridique  # si disponible
from app.db import get_next_sequence


@dataclass
class MaterializationOptions:
    protocol: str = "HL7v2"  # HL7v2 | FHIR | MIXED
    generate_identifiers: bool = True
    ipp_prefix: Optional[str] = None
    nda_prefix: Optional[str] = None
    namespace_oid: Optional[str] = None
    apply_time_shifting: bool = True


def _now_hl7_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _generate_identifiers(session: Session, opts: MaterializationOptions) -> dict:
    data = {}
    if not opts.generate_identifiers:
        return data
    ipp_seq = get_next_sequence(session, "scenario_ipp")
    nda_seq = get_next_sequence(session, "scenario_nda")
    ipp = f"{opts.ipp_prefix or ''}{ipp_seq:08d}".strip()
    nda = f"{opts.nda_prefix or ''}{nda_seq:07d}".strip()
    data.update({"ipp": ipp, "nda": nda})
    return data


def _build_hl7_message(event: str, semantic: str, ids: dict, ej: Optional[EntiteJuridique]) -> str:
    # Construction enrichie avec segments contextuels selon semantic_event_code
    sending_app = "MEDDATA"
    sending_fac = (ej.code_ej if ej and hasattr(ej, "code_ej") and ej.code_ej else "FAC")
    ts = _now_hl7_ts()
    ipp = ids.get("ipp", "000000000")
    nda = ids.get("nda", "0000000")
    msg_id = f"MSG{ts}{semantic[:4]}"
    
    msh = f"MSH|^~\\&|{sending_app}|{sending_fac}|RECEIVER|{sending_fac}|{ts}||{event}|{msg_id}|P|2.5"
    evn = f"EVN|{event.split('^')[-1]}|{ts}"
    pid = f"PID|1||{ipp}||TEMPLATE^{semantic}||19900101|F|||123 RUE TEST^^CITY^^38000^100||||||||||||||||||"
    
    # PV1 adapté selon type d'événement
    pv_class = "I" if "ADMISSION" in semantic or "TRANSFER" in semantic else "E"
    pv1 = f"PV1|1|{pv_class}|WARD^ROOM^BED|||DR001^MEDECIN^TEST^^^Dr.||||||||||||||{nda}||||||||||||||||||||||||||{ts}|||"
    
    segments = [msh, evn, pid, pv1]
    
    # PV2 pour informations complémentaires admission
    if "ADMISSION" in semantic:
        pv2 = f"PV2||M|{semantic}||||||{ts}|||||||||||N|||||||"
        segments.append(pv2)
    
    # DG1 pour diagnostic (discharge)
    if "DISCHARGE" in semantic or "PARCOURS_END" in semantic:
        dg1 = f"DG1|1|ICD10|I10^Hypertension essentielle^I10||{ts}|A|"
        segments.append(dg1)
    
    # AL1 allergies (optionnel sur admission)
    if "ADMISSION_CONFIRMED" in semantic:
        al1 = f"AL1|1|DA|00000001^PENICILLINE^99LCA|MO|REACTION||{ts}"
        segments.append(al1)
    
    return "\r".join(segments) + "\r"


def _build_fhir_bundle(semantic: str, ids: dict, ej: Optional[EntiteJuridique]) -> str:
    # Bundle enrichi: Patient + Encounter + Location + Organization + Practitioner
    encounter_status_map = {
        "PARCOURS_START": "planned",
        "ADMISSION_PLANNED": "planned",
        "ADMISSION_CONFIRMED": "in-progress",
        "TRANSFER_OUT": "in-progress",
        "TRANSFER_IN": "in-progress",
        "DISCHARGE": "finished",
        "PARCOURS_END": "finished",
    }
    status = encounter_status_map.get(semantic, "unknown")
    ipp = ids.get("ipp", "TEMP")
    nda = ids.get("nda", "NDA")
    org_id = f"ORG-{ej.code_ej}" if ej and hasattr(ej, "code_ej") else "ORG-DEFAULT"
    
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.utcnow().isoformat(),
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": ipp,
                    "identifier": [
                        {"system": "urn:meddata:ipp", "value": ipp}
                    ],
                    "name": [{"family": "TEMPLATE", "given": [semantic]}],
                    "gender": "female",
                    "birthDate": "1990-01-01",
                    "address": [{"line": ["123 Rue Test"], "city": "City", "postalCode": "38000"}]
                }
            },
            {
                "resource": {
                    "resourceType": "Organization",
                    "id": org_id,
                    "identifier": [{"system": "urn:meddata:ej", "value": org_id}],
                    "name": (ej.name if ej and hasattr(ej, "name") else "Organisation Template"),
                    "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov"}]}]
                }
            },
            {
                "resource": {
                    "resourceType": "Location",
                    "id": "LOC-WARD",
                    "status": "active",
                    "name": "Service Template",
                    "mode": "instance",
                    "managingOrganization": {"reference": f"Organization/{org_id}"}
                }
            },
            {
                "resource": {
                    "resourceType": "Practitioner",
                    "id": "PRACT-DR001",
                    "identifier": [{"system": "urn:meddata:rpps", "value": "10000000001"}],
                    "name": [{"family": "MEDECIN", "given": ["TEST"]}]
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": nda,
                    "identifier": [{"system": "urn:meddata:nda", "value": nda}],
                    "status": status,
                    "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP"},
                    "subject": {"reference": f"Patient/{ipp}"},
                    "participant": [{"individual": {"reference": f"Practitioner/PRACT-DR001"}}],
                    "serviceProvider": {"reference": f"Organization/{org_id}"},
                    "location": [{"location": {"reference": "Location/LOC-WARD"}}],
                    "extension": [
                        {"url": "urn:meddata:semantic", "valueCode": semantic}
                    ],
                }
            }
        ]
    }
    import json
    return json.dumps(bundle, ensure_ascii=False, indent=2)


def materialize_template(
    session: Session,
    template: ScenarioTemplate,
    ej_context: Optional[EntiteJuridique] = None,
    options: Optional[MaterializationOptions] = None,
) -> InteropScenario:
    """Crée un InteropScenario concret depuis un ScenarioTemplate.

    Génère des payloads HL7 ADT ou Bundle FHIR minimal selon le protocole choisi.
    """
    if options is None:
        options = MaterializationOptions()

    scenario = InteropScenario(
        key=f"materialized:{template.key}:{options.protocol}:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        name=f"{template.name} ({options.protocol})",
        description=f"Matérialisation du template {template.key} en protocole {options.protocol}",
        category=template.category,
        protocol="HL7" if options.protocol.startswith("HL7") else "FHIR",
        source_path=template.key,
        tags=template.tags,
    )
    session.add(scenario)
    session.flush()

    ids = _generate_identifiers(session, options)

    order_index = 1
    for t_step in template.steps:
        if scenario.protocol == "HL7":
            event = t_step.hl7_event_code or "ADT^A01"
            payload = _build_hl7_message(event, t_step.semantic_event_code, ids, ej_context)
            message_type = event
            message_format = "hl7"
        else:
            payload = _build_fhir_bundle(t_step.semantic_event_code, ids, ej_context)
            message_type = "Bundle"
            message_format = "fhir"
        step = InteropScenarioStep(
            scenario_id=scenario.id,
            order_index=order_index,
            name=t_step.narrative or t_step.semantic_event_code,
            description=f"Généré depuis template {template.key}",
            message_format=message_format,
            message_type=message_type,
            payload=payload,
            delay_seconds=None,
        )
        session.add(step)
        order_index += 1

    session.commit()
    session.refresh(scenario)
    return scenario
