"""Matérialisation des ScenarioTemplate en InteropScenario concrets.

Ce module prend un template abstrait + un contexte (GHT/EJ, param génération identifiants)
et crée un InteropScenario avec des InteropScenarioStep payload HL7/FHIR prêts à rejouer.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime
from sqlmodel import Session, select

from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep, InteropScenario, InteropScenarioStep
from app.models_structure import EntiteJuridique, UniteFonctionnelle  # si disponible
from app.db import get_next_sequence
from app.models_scenario_config import ScenarioEJConfig, get_uf_code_for_event, get_medecin_for_event


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


def _get_ej_config(session: Session, ej_id: int) -> Optional[ScenarioEJConfig]:
    """Charge la configuration de scénario pour une EJ."""
    return session.exec(
        select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == ej_id)
    ).first()


def _build_location_from_uf(session: Session, uf_id: Optional[int]) -> str:
    """Construit la chaîne de localisation PV1-3 depuis une UF."""
    if not uf_id:
        return "WARD^ROOM^BED"
    
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        return "WARD^ROOM^BED"
    
    # Format HL7: Point of Care ^ Room ^ Bed ^ Facility ^ Location Status ^ ...
    # On utilise l'identifiant UF comme point of care principal
    uf_code = uf.identifier or uf.name or "UF"
    return f"{uf_code}^^^{uf_code}^ACTIVE"


def _build_doctor_xcn(medecin_info: Optional[Dict[str, str]]) -> str:
    """Construit le champ XCN HL7 pour un médecin.
    
    Format XCN: ID^Family^Given^Middle^Suffix^Prefix^Degree^Source Table^Assigning Authority^Name Type^ID Check Digit
    """
    if not medecin_info or not medecin_info.get("rpps"):
        return "DR001^MEDECIN^TEST^^^Dr."
    
    rpps = medecin_info.get("rpps", "")
    nom = medecin_info.get("nom", "MEDECIN RPPS")
    
    # Essayer de parser le nom (format attendu: "Dr DUPONT Jean" ou "DUPONT Jean")
    nom_parts = nom.replace("Dr ", "").replace("Dr. ", "").strip().split()
    if len(nom_parts) >= 2:
        family = nom_parts[0]
        given = " ".join(nom_parts[1:])
    else:
        family = nom
        given = ""
    
    # Format: RPPS^Family^Given^Middle^Suffix^Prefix (Dr)^Degree^Source (RPPS)^AssigningAuth^NameType (L=Legal)
    return f"{rpps}^{family}^{given}^^^Dr.^^RPPS^1.2.250.1.71.4.2.1^L"


def _build_hl7_message(
    event: str, 
    semantic: str, 
    ids: dict, 
    ej: Optional[EntiteJuridique], 
    namespace_oid: Optional[str] = None,
    ej_config: Optional[ScenarioEJConfig] = None,
    session: Optional[Session] = None
) -> str:
    # Construction enrichie avec segments contextuels selon semantic_event_code
    sending_app = "MEDDATA"
    sending_fac = (ej.code_ej if ej and hasattr(ej, "code_ej") and ej.code_ej else "FAC")
    ts = _now_hl7_ts()
    ipp = ids.get("ipp", "000000000")
    nda = ids.get("nda", "0000000")
    # If a namespace OID is provided (via options or EJ), include it in identifier components
    assigning_authority = namespace_oid or (ej.namespace_oid if ej and hasattr(ej, "namespace_oid") else None)
    if assigning_authority:
        ipp_field = f"{ipp}^^^{assigning_authority}^PI"
        nda_field = f"{nda}^^^{assigning_authority}^VN"
    else:
        ipp_field = ipp
        nda_field = nda
    msg_id = f"MSG{ts}{semantic[:4]}"
    
    # Extraire le code événement HL7 (ex: A01 de ADT^A01)
    event_code = event.split("^")[-1] if "^" in event else event
    
    # === Utilisation de la configuration EJ pour UF et médecin ===
    # Déterminer l'UF à utiliser selon le type d'événement
    location_str = "WARD^ROOM^BED"  # Valeur par défaut
    if ej_config and session:
        uf_code = get_uf_code_for_event(ej_config, event_code, session)
        if uf_code:
            location_str = f"{uf_code}^^^{uf_code}^ACTIVE"
    
    # Déterminer le médecin à utiliser selon le type d'événement  
    doctor_xcn = "DR001^MEDECIN^TEST^^^Dr."  # Valeur par défaut
    if ej_config:
        medecin_info = get_medecin_for_event(ej_config, event_code)
        if medecin_info:
            doctor_xcn = _build_doctor_xcn(medecin_info)
    
    msh = f"MSH|^~\\&|{sending_app}|{sending_fac}|RECEIVER|{sending_fac}|{ts}||{event}|{msg_id}|P|2.5"
    evn = f"EVN|{event_code}|{ts}"
    pid = f"PID|1||{ipp_field}||TEMPLATE^{semantic}||19900101|F|||123 RUE TEST^^CITY^^38000^100||||||||||||||||||"
    
    # PV1 adapté selon type d'événement
    pv_class = "I" if "ADMISSION" in semantic or "TRANSFER" in semantic else "E"
    # Build PV1 fields as a list to place the Visit Number (NDA) exactly in PV1-19
    # HL7 fields are 1-indexed; when splitting the line by '|' the index in the
    # Python list corresponds: fields[0] == 'PV1', fields[19] == PV1-19.
    pv1_fields = [
        "PV1",             # fields[0] placeholder for the segment name
        "1",               # PV1-1 Set ID
        pv_class,          # PV1-2 Patient Class
        location_str,      # PV1-3 Assigned Patient Location (from EJ config if available)
        "",                # PV1-4
        "",                # PV1-5 Preadmit Number (vide)
        "",                # PV1-6 Prior Patient Location (vide)
        doctor_xcn,        # PV1-7 Attending Doctor (from EJ config if available)
    ]
    # PV1-8 à PV1-16 vides
    while len(pv1_fields) < 17:
        pv1_fields.append("")
    # PV1-17: Admitting Doctor (same as attending for simplicity)
    pv1_fields.append(doctor_xcn)
    # PV1-18 vide
    pv1_fields.append("")
    # Set PV1-19 to the nda_field (Visit Number)
    pv1_fields.append(nda_field)
    # Append a few common trailing fields (we include the timestamp near the end)
    pv1_fields.extend(["", "", "", "", "", "", ts, "", ""])  # tail fillers
    pv1 = "|".join(pv1_fields)
    
    segments = [msh, evn, pid, pv1]
    
    # PV2 pour informations complémentaires admission
    if "ADMISSION" in semantic:
        pv2 = f"PV2||M|{semantic}||||||{ts}|||||||||||N|||||||"
        segments.append(pv2)
    
    # DG1 (diagnostic) est volontairement exclu: non autorisé dans le flux IHE PAM FR basique
    # Si besoin futur (extension locale), ajouter génération conditionnelle hors profil standard.
    # Exemple (désactivé): DG1|1|ICD10|I10^Hypertension essentielle^I10||{ts}|A|
    
    # AL1 (allergies) exclu du profil IHE PAM minimal (clinique hors périmètre)
    # Pour extension future, réactiver sous drapeau ENABLE_AL1.
    
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
    namespace = None
    try:
        namespace = getattr(ej, "namespace_oid", None) if ej is not None else None
    except Exception:
        namespace = None
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
                        {
                            "system": (namespace if namespace else "urn:meddata:ipp"),
                            "value": ipp,
                            "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR"}]}
                        }
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
                    "identifier": [
                        {"system": "urn:meddata:ej", "value": org_id},
                        {"system": "urn:oid:1.2.250.1.71.4.2.2", "value": (ej.finess_ej if ej and hasattr(ej, "finess_ej") else org_id)}
                    ],
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

    # ej_context may be an EntiteJuridique object or an id (int) provided by tests.
    ej_obj: Optional[EntiteJuridique]
    if ej_context is None:
        ej_obj = None
    elif isinstance(ej_context, (int, str)):
        try:
            ej_obj = session.get(EntiteJuridique, int(ej_context))
        except Exception:
            ej_obj = None
        if ej_obj is None:
            raise ValueError(f"EJ {ej_context} introuvable pour matérialisation")
    else:
        ej_obj = ej_context

    # Charger la configuration EJ pour les UF et médecins
    ej_config: Optional[ScenarioEJConfig] = None
    if ej_obj and ej_obj.id:
        ej_config = _get_ej_config(session, ej_obj.id)

    order_index = 1
    for t_step in template.steps:
        if scenario.protocol == "HL7":
            event = t_step.hl7_event_code or "ADT^A01"
            payload = _build_hl7_message(
                event, 
                t_step.semantic_event_code, 
                ids, 
                ej_obj, 
                namespace_oid=options.namespace_oid,
                ej_config=ej_config,
                session=session
            )
            message_type = event
            message_format = "hl7"
        else:
            payload = _build_fhir_bundle(t_step.semantic_event_code, ids, ej_obj)
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
