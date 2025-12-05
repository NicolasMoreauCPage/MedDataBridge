"""Matérialisation des ScenarioTemplate en InteropScenario concrets.

Ce module prend un template abstrait + un contexte (GHT/EJ, param génération identifiants)
et crée un InteropScenario avec des InteropScenarioStep payload HL7/FHIR prêts à rejouer.

Conformité IHE PAM France:
- Messages avec segment ZBE obligatoire (sauf A28, A31, A40, A47)
- PV1-3 format complet: UF^Chambre^Lit^Facility^Status
- PV1-7: Médecin responsable (XCN avec RPPS)
- PV1-8: Médecin traitant/adressant (XCN avec RPPS)
- PV1-17: Médecin admetteur (XCN avec RPPS)
- PV1-19: Numéro de venue (NDA)
- Contexte patient cohérent entre tous les messages d'un scénario
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from sqlmodel import Session, select

from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep, InteropScenario, InteropScenarioStep
from app.models_structure import EntiteJuridique, UniteFonctionnelle
from app.utils.seq_generator import generate_patient_seq, generate_dossier_seq, generate_venue_seq
from app.models_scenario_config import (
    ScenarioEJConfig, 
    get_location_for_event, 
    get_medecin_for_event,
    get_medecin_traitant,
    build_xcn_field,
    OID_RPPS
)


@dataclass
class MaterializationOptions:
    protocol: str = "HL7v2"  # HL7v2 | FHIR | MIXED
    generate_identifiers: bool = True
    ipp_prefix: Optional[str] = None
    nda_prefix: Optional[str] = None
    namespace_oid: Optional[str] = None
    apply_time_shifting: bool = True


@dataclass
class ScenarioContext:
    """Contexte partagé entre tous les messages d'un scénario.
    
    Assure la cohérence des identifiants et du contexte patient
    tout au long du parcours (même IPP, NDA, séjour).
    
    Identifiants:
    - ipp: Identifiant Patient Permanent (PID-3)
    - nda: Numéro de Dossier Administratif (PID-18)
    - venue_seq: Numéro de venue/visite (PV1-19)
    """
    ipp: str = ""
    nda: str = ""
    venue_seq: str = ""  # Numéro de venue pour PV1-19
    ipp_oid: str = ""
    nda_oid: str = ""
    movement_seq: int = 0
    patient_family: str = "TEMPLATE"
    patient_given: str = "Patient"
    patient_dob: str = "19900101"
    patient_gender: str = "F"
    admit_datetime: Optional[str] = None
    facility_code: str = "FAC"
    
    def next_movement(self) -> int:
        """Incrémente et retourne le prochain numéro de mouvement."""
        self.movement_seq += 1
        return self.movement_seq


def _now_hl7_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _ts_offset(base_ts: str, minutes: int) -> str:
    """Ajoute un décalage en minutes à un timestamp HL7."""
    try:
        dt = datetime.strptime(base_ts, "%Y%m%d%H%M%S")
        dt += timedelta(minutes=minutes)
        return dt.strftime("%Y%m%d%H%M%S")
    except Exception:
        return base_ts


def _generate_identifiers(session: Session, opts: MaterializationOptions) -> dict:
    """Génère les identifiants uniques pour un scénario.
    
    Utilise les générateurs basés sur timestamp pour garantir l'unicité:
    - IPP: 12 chiffres, préfixe '9' + timestamp (generate_patient_seq)
    - NDA: 9 chiffres, préfixe '9' + timestamp (generate_dossier_seq)
    - venue_seq: 10 chiffres, préfixe '8' + timestamp (generate_venue_seq)
    
    Returns:
        Dict avec:
        - ipp: Identifiant Patient Permanent (PID-3)
        - nda: Numéro de Dossier Administratif (PID-18)
        - venue_seq: Numéro de venue/visite (PV1-19)
    """
    data = {}
    if not opts.generate_identifiers:
        return data
    
    # Génération basée sur timestamp pour unicité garantie
    ipp = str(generate_patient_seq())
    nda = str(generate_dossier_seq())
    # Le venue_seq est généré indépendamment pour garantir son unicité
    venue_seq = str(generate_venue_seq())
    
    data.update({"ipp": ipp, "nda": nda, "venue_seq": venue_seq})
    return data


def _get_ej_config(session: Session, ej_id: int) -> Optional[ScenarioEJConfig]:
    """Charge la configuration de scénario pour une EJ."""
    return session.exec(
        select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == ej_id)
    ).first()


# Messages d'identité (sans ZBE selon IHE PAM France)
IDENTITY_TRIGGERS = {"A28", "A31", "A40", "A47"}

# Mapping trigger -> action ZBE-4
ZBE_ACTION_MAP = {
    "A01": "INSERT", "A04": "INSERT", "A05": "INSERT",
    "A02": "INSERT", "A03": "INSERT",
    "A06": "INSERT", "A07": "INSERT",
    "A21": "INSERT", "A22": "INSERT",
    "A11": "CANCEL", "A12": "CANCEL", "A13": "CANCEL",
    "A23": "CANCEL", "A38": "CANCEL",
    "A52": "CANCEL", "A53": "CANCEL", "A55": "CANCEL",
    "Z99": "UPDATE",
}

# Mapping trigger annulation -> trigger original (ZBE-6)
ZBE_ORIGIN_MAP = {
    "A11": "A01", "A12": "A02", "A13": "A03",
    "A23": "A01", "A38": "A05",
    "A52": "A21", "A53": "A22", "A55": "A54",
}

# Nature du mouvement ZBE-9
ZBE_NATURE_MAP = {
    "A01": "M",  # Médical (admission)
    "A02": "H",  # Hébergement (mutation)
    "A03": "S",  # Sortie
    "A04": "M",  # Médical (externe)
    "A05": "M",  # Médical (préadmission)
    "A21": "L",  # Leave (permission sortie)
    "A22": "L",  # Leave (retour permission)
}


def _build_zbe_segment(
    event_code: str,
    movement_id: str,
    movement_datetime: str,
    uf_code: str,
    namespace_oid: Optional[str] = None,
    namespace_name: str = "MEDDATA"
) -> str:
    """Construit le segment ZBE conforme IHE PAM France.
    
    Structure ZBE:
    - ZBE-1: Identifiant du mouvement (EI: ID^Namespace^OID^ISO)
    - ZBE-2: Date/heure du mouvement (TS)
    - ZBE-3: Date de fin (vide sauf sortie)
    - ZBE-4: Action (INSERT/UPDATE/CANCEL)
    - ZBE-5: Indicateur historique (Y/N)
    - ZBE-6: Trigger original (pour UPDATE/CANCEL)
    - ZBE-7: UF responsabilité médicale (XON: ^^^^^^UF^^^CODE)
    - ZBE-8: UF de soins (vide si même que ZBE-7)
    - ZBE-9: Nature du mouvement (M/H/S/L/D)
    """
    # ZBE-1: Identifiant mouvement (format court: séquence numérique)
    oid = namespace_oid or "1.2.250.1.213.1.1.9"
    zbe_1 = f"{movement_id}^{namespace_name}^{oid}^ISO"
    
    # ZBE-2: Datetime mouvement
    zbe_2 = movement_datetime
    
    # ZBE-3: Date fin (vide sauf sortie)
    zbe_3 = movement_datetime if event_code == "A03" else ""
    
    # ZBE-4: Action
    zbe_4 = ZBE_ACTION_MAP.get(event_code, "INSERT")
    
    # ZBE-5: Indicateur historique (N = mouvement courant)
    zbe_5 = "N"
    
    # ZBE-6: Trigger original (pour annulations)
    zbe_6 = ZBE_ORIGIN_MAP.get(event_code, "")
    
    # ZBE-7: UF responsabilité médicale (format XON simplifié)
    # Format: ^^^^^^UF^^^CODE_UF (code en position 10)
    zbe_7 = f"^^^^^^UF^^^{uf_code}" if uf_code else ""
    
    # ZBE-8: UF de soins (vide si même que médicale)
    zbe_8 = ""
    
    # ZBE-9: Nature du mouvement
    zbe_9 = ZBE_NATURE_MAP.get(event_code, "M")
    
    return f"ZBE|{zbe_1}|{zbe_2}|{zbe_3}|{zbe_4}|{zbe_5}|{zbe_6}|{zbe_7}|{zbe_8}|{zbe_9}"


def _build_hl7_message(
    event: str, 
    semantic: str, 
    context: ScenarioContext,
    ej: Optional[EntiteJuridique], 
    ej_config: Optional[ScenarioEJConfig] = None,
    session: Optional[Session] = None,
    step_index: int = 1
) -> str:
    """Construit un message HL7 conforme IHE PAM France.
    
    Args:
        event: Code événement (ex: "ADT^A01")
        semantic: Code sémantique de l'étape
        context: Contexte partagé du scénario
        ej: Entité Juridique
        ej_config: Configuration EJ pour UF/médecins
        session: Session DB
        step_index: Index de l'étape pour décalage temporel
        
    Returns:
        Message HL7 complet avec segments MSH, EVN, PID, PV1, ZBE
    """
    # Configuration de base
    sending_app = "MEDDATA"
    sending_fac = context.facility_code
    
    # Timestamp avec décalage pour chaque étape
    base_ts = context.admit_datetime or _now_hl7_ts()
    ts = _ts_offset(base_ts, (step_index - 1) * 60)  # +1h par étape
    
    # Extraire le code événement HL7 (ex: A01 de ADT^A01)
    event_code = event.split("^")[-1] if "^" in event else event
    
    # Générer identifiant message unique (basé sur timestamp + séquence)
    # Format: MSG_YYYYMMDDHHMMSS_XXXX où XXXX est le numéro de séquence
    msg_id = f"MSG_{ts}_{step_index:04d}"
    
    # === Localisation (PV1-3) ===
    location_info = {"pv1_3": "^^^", "uf_code": ""}
    if ej_config and session:
        location_info = get_location_for_event(ej_config, event_code, session, sending_fac)
    pv1_3 = location_info.get("pv1_3", "^^^")
    uf_code = location_info.get("uf_code", "")
    
    # === Médecins ===
    # PV1-7: Médecin responsable
    pv1_7 = ""
    if ej_config:
        medecin_resp = get_medecin_for_event(ej_config, event_code)
        pv1_7 = build_xcn_field(medecin_resp)
    
    # PV1-8: Médecin traitant/adressant
    pv1_8 = ""
    if ej_config:
        medecin_trait = get_medecin_traitant(ej_config)
        pv1_8 = build_xcn_field(medecin_trait)
    
    # PV1-17: Médecin admetteur (même que responsable pour simplifier)
    pv1_17 = pv1_7
    
    # === Identifiants patient formatés ===
    # PID-3: IPP (Identifiant Patient Permanent)
    # PID-18: NDA (Numéro de Dossier Administratif)
    # PV1-19: Venue/Visit Number
    if context.ipp_oid:
        ipp_field = f"{context.ipp}^^^{context.ipp_oid}^PI"
        nda_field = f"{context.nda}^^^{context.nda_oid}^AN"  # AN = Account Number (dossier)
        venue_field = f"{context.venue_seq}^^^{context.nda_oid}^VN"  # VN = Visit Number
    else:
        ipp_field = context.ipp
        nda_field = context.nda
        venue_field = context.venue_seq
    
    # === Construction des segments ===
    
    # MSH - En-tête message
    msh = (
        f"MSH|^~\\&|{sending_app}|{sending_fac}|RECEIVER|{sending_fac}|{ts}||"
        f"{event}|{msg_id}|P|2.5^FRA^2.11|||AL|NE|FRA||UNICODE UTF-8"
    )
    
    # EVN - Événement
    evn = f"EVN|{event_code}|{ts}"
    
    # PID - Patient
    # PID-3: IPP, PID-18: NDA (numéro de dossier)
    # Format: PID|1||IPP||NOM^PRENOM||DOB|SEX|||ADDR|||||||NDA|||||...
    pid_fields = ["PID", "1", "", ipp_field, "", f"{context.patient_family}^{context.patient_given}"]
    pid_fields.extend(["", context.patient_dob, context.patient_gender])  # PID-7, 8
    pid_fields.extend(["", "", "123 RUE TEST^^CITY^^38000^FRA"])  # PID-9, 10, 11 (adresse)
    pid_fields.extend(["", "", "", "", "", ""])  # PID-12 à 17
    pid_fields.append(nda_field)  # PID-18: Numéro de dossier (NDA)
    pid = "|".join(pid_fields)
    
    # PV1 - Visite
    # Déterminer la classe patient
    if event_code in ("A04", "A05", "A38"):
        pv_class = "O"  # Outpatient
    elif event_code == "A10":
        pv_class = "E"  # Emergency
    else:
        pv_class = "I"  # Inpatient
    
    # Construction PV1 avec tous les champs positionnés correctement
    pv1_fields = ["PV1", "1", pv_class, pv1_3, "", "", ""]  # 0-6
    pv1_fields.append(pv1_7)  # PV1-7 Attending Doctor
    pv1_fields.append(pv1_8)  # PV1-8 Referring Doctor (médecin traitant)
    pv1_fields.extend(["", uf_code, "", "", "", "", "", ""])  # 9-16
    pv1_fields.append(pv1_17)  # PV1-17 Admitting Doctor
    pv1_fields.append("")  # PV1-18 Patient Type
    pv1_fields.append(venue_field)  # PV1-19 Visit Number (numéro de venue)
    # Padding jusqu'à PV1-44 (date admission)
    while len(pv1_fields) < 44:
        pv1_fields.append("")
    pv1_fields.append(context.admit_datetime or ts)  # PV1-44 Admit Date/Time
    
    pv1 = "|".join(pv1_fields)
    
    segments = [msh, evn, pid, pv1]
    
    # PV2 pour admissions
    if "ADMISSION" in semantic or event_code in ("A01", "A04", "A05"):
        pv2 = f"PV2||M|{semantic}||||||{ts}|||||||||||N|||||||"
        segments.append(pv2)
    
    # ZBE - Mouvement (obligatoire sauf messages identité)
    if event_code not in IDENTITY_TRIGGERS:
        movement_seq = context.next_movement()
        namespace_name = sending_fac
        namespace_oid = context.nda_oid or "1.2.250.1.213.1.1.9"
        
        # Identifiant mouvement: numéro séquentiel simple basé sur venue + séquence
        # Format court: VENUE_MVTSEQ (ex: 123_001)
        movement_id = f"{context.venue_seq}_{movement_seq:03d}"
        
        zbe = _build_zbe_segment(
            event_code=event_code,
            movement_id=movement_id,
            movement_datetime=ts,
            uf_code=uf_code,
            namespace_oid=namespace_oid,
            namespace_name=namespace_name
        )
        segments.append(zbe)
    
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

    Génère des payloads HL7 ADT conformes IHE PAM France ou Bundle FHIR.
    
    Le contexte patient (IPP, NDA, séjour) est partagé entre tous les messages
    pour assurer la cohérence du parcours patient.
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

    # Créer le contexte partagé pour tout le scénario
    # OID pour les identifiants - utilise l'OID fourni ou construit à partir du FINESS
    finess_ej = getattr(ej_obj, "finess_ej", None) if ej_obj else None
    default_oid = f"1.2.250.1.71.4.2.2.{finess_ej}" if finess_ej else "1.2.250.1.213.1.1.9"
    namespace_oid = options.namespace_oid or default_oid
    
    facility_code = (
        getattr(ej_obj, "code_ej", None) or 
        getattr(ej_obj, "finess_ej", None) if ej_obj else None
    ) or "FAC"
    
    context = ScenarioContext(
        ipp=ids.get("ipp", "00000000"),
        nda=ids.get("nda", "0000000"),
        venue_seq=ids.get("venue_seq", "1"),  # Numéro de venue pour PV1-19
        ipp_oid=namespace_oid,
        nda_oid=namespace_oid,
        movement_seq=0,
        patient_family="SCENARIO",
        patient_given=template.name[:20] if template.name else "Test",
        patient_dob="19900115",
        patient_gender="F",
        admit_datetime=_now_hl7_ts(),
        facility_code=facility_code,
    )

    order_index = 1
    for t_step in template.steps:
        # Ignorer les étapes lifecycle sans événement HL7 (PARCOURS_START, PARCOURS_END)
        if scenario.protocol == "HL7":
            if not t_step.hl7_event_code:
                # Pas d'événement HL7 pour cette étape (lifecycle marker)
                continue
            event = t_step.hl7_event_code
            payload = _build_hl7_message(
                event=event, 
                semantic=t_step.semantic_event_code, 
                context=context,
                ej=ej_obj, 
                ej_config=ej_config,
                session=session,
                step_index=order_index
            )
            message_type = event
            message_format = "hl7"
        else:
            # Pour FHIR, on génère tous les événements (y compris lifecycle)
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
