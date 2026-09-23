"""Façade et orchestration du validateur IHE PAM HL7v2."""
from __future__ import annotations

from typing import List

from app.services.mllp import parse_msh_fields
from app.services.pam_profile_fr import (
    ALLOWED_SEGMENTS,
    EVN_OPTIONAL_EVENTS,
    MESSAGE_STRUCTURES,
    MERGE_EVENTS,
    PID32_CODES,
    ZBE9_C_ORIGINAL_EVENTS,
    ZBE9_NATURES,
    expected_structure,
)
from app.services.pam_validation_fields import (
    _field,
    _get_all_segments,
    _get_first_segment,
    _split_lines,
    _validate_code_with_vocab,
    _validate_cx_identifier,
    _validate_segment_order,
    _validate_ts_timestamp,
    _validate_xad_address,
    _validate_xpn_name,
    _validate_xtn_telecom,
    _validate_z_segments,
)
from app.services.pam_validation_models import (
    ValidationAuditEntry,
    ValidationIssue,
    ValidationResult,
)
from app.services.pam_validation_rules import (
    FORBIDDEN_PAM_SEGMENTS,
    IDENTITY_ONLY,
    MOVEMENT_EVENTS,
    REQUIRE_PV1,
    SEGMENT_RULES,
    _normalize_cpage_zbe9,
    load_custom_segment_rules,
)
from app.services.pam_semantic_validation import validate_pam_semantics

def validate_pam(
    msg: str,
    direction: str = "in",
    profile: str = "IHE_PAM_FR",
    strict_semantic: bool = False,
    include_audit: bool = False,
    session=None,
) -> ValidationResult:
    """
    Validate HL7 ADT message against IHE PAM FR profile.
    
    Args:
        msg: HL7 message string (CR-delimited)
        direction: "in"/"inbound" (strict) or "out"/"outbound" (tolerant)
        profile: Profile name (default: "IHE_PAM_FR")
        strict_semantic: If True, A06/A07 semantic violations are error-level (default False for backward compat)
        include_audit: If True, add audit trail entry to result (default False)
        session: Session SQLModel optionnelle pour les vocabulaires configurés
    
    Returns:
        ValidationResult with is_valid, level, issues, and optional audit trail
    """
    from datetime import datetime
    
    issues: List[ValidationIssue] = []
    strict_inbound = (direction or "in").lower() in {"in", "inbound", "incoming"}
    validation_start = datetime.utcnow().isoformat() if include_audit else None

    if not msg or not msg.startswith("MSH|"):
        issues.append(ValidationIssue("STRUCTURE", "Message must start with MSH"))
        return ValidationResult(False, "fail", event="", message_type="", issues=issues)

    msh = parse_msh_fields(msg)
    if not msh:
        issues.append(ValidationIssue("MSH_PARSE", "Unable to parse MSH segment"))
        return ValidationResult(False, "fail", event="", message_type="", issues=issues)

    msg_type = f"{msh.get('type','')}^{msh.get('trigger','')}".strip("^")
    trigger = msh.get("trigger") or ""
    sending_app = (msh.get("sending_app") or "").strip().upper()

    if (msh.get("type") or "").upper() == "ADT" and trigger not in MESSAGE_STRUCTURES:
        issues.append(ValidationIssue(
            "TRIGGER_UNSUPPORTED",
            f"Trigger ADT^{trigger} non supporte par le profil IHE PAM FR",
            severity="error"
        ))

    # HL7 v2.5 base rules: MSH validation
    msh_line = _get_first_segment(msg, "MSH")
    if msh_line:
        # MSH-1 (Field Separator) should be |
        if len(msh_line) < 4 or msh_line[3] != "|":
            issues.append(ValidationIssue("MSH1_INVALID", "MSH-1 (Field Separator) must be '|'", severity="error"))
        
        # MSH-2 (Encoding Characters) should be ^~\& (standard HL7)
        msh_parts = msh_line.split("|")
        if len(msh_parts) > 1:
            encoding = msh_parts[1]
            if encoding not in ("^~\\&", "^~\\&"):  # Accept both with/without escape
                issues.append(ValidationIssue("MSH2_NONSTANDARD", f"MSH-2 (Encoding Characters) is '{encoding}', standard is '^~\\&'", severity="warn"))
        
        # MSH-9 (Message Type) format
        msg_type_field = _field(msh_parts, 8) if len(msh_parts) > 8 else ""
        if not msg_type_field or "^" not in msg_type_field:
            issues.append(ValidationIssue("MSH9_FORMAT", "MSH-9 (Message Type) must be in format type^trigger[^structure]", severity="error"))
        else:
            components = msg_type_field.split("^")
            if components[0].upper() != "ADT":
                issues.append(ValidationIssue("MSH9_TYPE_INVALID", f"MSH-9.1 doit être ADT, reçu: {components[0]}", severity="error"))
            expected = expected_structure(trigger)
            structure = components[2] if len(components) > 2 else ""
            if expected and structure != expected:
                issues.append(ValidationIssue(
                    "MSH9_STRUCTURE_INVALID",
                    f"MSH-9.3 doit être {expected} pour ADT^{trigger}, reçu: {structure or '(absent)'}",
                    severity="error",
                ))
        
        # MSH-10 (Message Control ID) non vide
        control_id = _field(msh_parts, 9) if len(msh_parts) > 9 else ""
        if not control_id:
            issues.append(ValidationIssue("MSH10_EMPTY", "MSH-10 (Message Control ID) is required", severity="error"))
        
        # MSH-11 (Processing ID) valide
        proc_id = _field(msh_parts, 10) if len(msh_parts) > 10 else ""
        if proc_id and proc_id not in ("P", "D", "T"):
            issues.append(ValidationIssue("MSH11_INVALID", f"MSH-11 (Processing ID) '{proc_id}' not in (P, D, T)", severity="warn"))
        
        # MSH-12 : HL7 2.5 et annexe française. CPage 2.10 reste accepté
        # avec avertissement pour permettre une migration sans faux rejet.
        version = _field(msh_parts, 11) if len(msh_parts) > 11 else ""
        if not version:
            issues.append(ValidationIssue("MSH12_MISSING", "MSH-12 (Version ID) est requis", severity="error"))
        elif not version.startswith("2.5^FRA"):
            issues.append(ValidationIssue("MSH12_INVALID", f"MSH-12 doit annoncer HL7 2.5 France, reçu: {version}", severity="error"))
        elif version not in {"2.5^FRA^2.11", "2.5^FRA^2.11.1"}:
            issues.append(ValidationIssue("MSH12_PROFILE_LEGACY", f"Profil PAM France historique reçu: {version}", severity="warn"))

        charset = _field(msh_parts, 17) if len(msh_parts) > 17 else ""
        if charset and charset.upper() not in {
            "8859/1", "ISO-8859-1", "ISO 8859/1",
            "UNICODE UTF-8", "8859/15", "ISO-8859-15",
        }:
            issues.append(ValidationIssue("MSH18_INVALID", f"MSH-18 non supporté par le profil France: {charset}", severity="error"))

    # EVN presence and consistency
    evn = _get_first_segment(msg, "EVN")
    if not evn:
        if trigger not in EVN_OPTIONAL_EVENTS:
            issues.append(ValidationIssue("EVN_MISSING", "EVN segment is required"))
    else:
        evn_parts = evn.split("|")
        evn_code = _field(evn_parts, 1)
        if trigger and evn_code and evn_code != trigger:
            issues.append(ValidationIssue("EVN_MISMATCH", f"EVN-1 ({evn_code}) differs from MSH-9 trigger ({trigger})", severity="warn"))
        
        # EVN-2 (Recorded Date/Time) - TS type validation
        evn2 = _field(evn_parts, 2)
        if evn2:
            _validate_ts_timestamp(evn2, "EVN2", issues)
        
        # EVN-6 (Event Occurred) - TS type validation
        evn6 = _field(evn_parts, 6)
        if evn6:
            _validate_ts_timestamp(evn6, "EVN6", issues)

    # PID presence and HL7 v2.5 base rules
    pid = _get_first_segment(msg, "PID")
    if not pid:
        issues.append(ValidationIssue("PID_MISSING", "PID segment is required"))
    else:
        pid_parts = pid.split("|")
        # PID-3 (Patient Identifier List) - CX type validation
        pid3 = _field(pid_parts, 3)
        if not pid3:
            issues.append(ValidationIssue("PID3_EMPTY", "PID-3 (Patient Identifier List) must not be empty"))
        else:
            for idx, cx_id in enumerate(pid3.split("~")):
                if cx_id:
                    _validate_cx_identifier(cx_id, f"PID3[{idx}]", issues)
        # PID-5 (Patient Name) - XPN type validation
        pid5 = _field(pid_parts, 5)
        if not pid5:
            issues.append(ValidationIssue("PID5_MISSING", "PID-5 (Patient Name) is strongly recommended", severity="warn"))
        else:
            for idx, xpn_name in enumerate(pid5.split("~")):
                if xpn_name:
                    _validate_xpn_name(xpn_name, f"PID5[{idx}]", issues)
        # PID-7 (Date of Birth) - TS type validation
        pid7 = _field(pid_parts, 7)
        if pid7:
            _validate_ts_timestamp(pid7, "PID7", issues)
        # PID-11 (Patient Address) - XAD type validation
        pid11 = _field(pid_parts, 11)
        if pid11:
            for idx, xad_addr in enumerate(pid11.split("~")):
                if xad_addr:
                    _validate_xad_address(xad_addr, f"PID11[{idx}]", issues)
        # PID-13 (Phone Number - Home) - XTN type validation
        pid13 = _field(pid_parts, 13)
        if pid13:
            for idx, xtn_phone in enumerate(pid13.split("~")):
                if xtn_phone:
                    _validate_xtn_telecom(xtn_phone, f"PID13[{idx}]", issues)
        # PID-14 (Phone Number - Business) - XTN type validation
        pid14 = _field(pid_parts, 14)
        if pid14:
            for idx, xtn_phone in enumerate(pid14.split("~")):
                if xtn_phone:
                    _validate_xtn_telecom(xtn_phone, f"PID14[{idx}]", issues)
        # PID-6 (Nom de la mère, XPN, optionnel mais conseillé)
        pid6 = _field(pid_parts, 6)
        if pid6:
            _validate_xpn_name(pid6, "PID6", issues)
        # PID-8 (Sexe, IS, obligatoire)
        pid8 = _field(pid_parts, 8)
        _validate_code_with_vocab(
            pid8,
            "PID8",
            issues,
            session=session,
            vocab_names=["semantic-administrative-gender"],
            fallback={"M", "F", "O", "U"},
            severity="error",
            required=strict_inbound,
            msg=f"PID-8 (Sexe) doit être une valeur du vocabulaire sémantique, reçu: {pid8}"
        )
        # PID-15 (Langue principale, CE, optionnel)
        pid15 = _field(pid_parts, 15)
        if pid15 and len(pid15) < 2:
            issues.append(ValidationIssue("PID15_FORMAT", "PID-15 (Langue principale) doit être un code de langue valide", severity="warn"))
        # PID-16 (Situation famille, CE, optionnel)
        # PID-18 (Numéro dossier administratif, CX, optionnel mais conseillé)
        pid18 = _field(pid_parts, 18)
        if pid18:
            _validate_cx_identifier(pid18, "PID18", issues)
        # PID-19 est interdit par l'extension nationale PAM France.
        if _field(pid_parts, 19):
            issues.append(ValidationIssue("PID19_FORBIDDEN", "PID-19 est interdit par le profil IHE PAM France", severity="error"))
        # PID-32 (Statut identité, RNIV) est répétable.
        pid32 = _field(pid_parts, 32)
        if not pid32:
            if strict_inbound:
                issues.append(ValidationIssue("PID32_MISSING", "PID-32 (statut identité) est requis", severity="error"))
        else:
            for idx, value in enumerate(pid32.split("~")):
                code = value.split("^")[0].strip().upper()
                if code not in PID32_CODES:
                    issues.append(ValidationIssue("PID32_INVALID", f"PID-32[{idx}] invalide: {value}", severity="error"))

    # PV1 validation (champs principaux)
    pv1 = _get_first_segment(msg, "PV1")
    if pv1:
        pv1_parts = pv1.split("|")
        pv1_2 = _field(pv1_parts, 2)
        _validate_code_with_vocab(
            pv1_2, "PV1_2", issues,
            session=session,
            vocab_names=["semantic-patient-class"],
            fallback={"E", "I", "O", "P", "R", "B", "C", "N", "U"},
            severity="error", required=trigger in REQUIRE_PV1,
            msg=f"PV1-2 (Classe patient) doit être une valeur du vocabulaire sémantique, reçu: {pv1_2}",
        )
        pv1_3 = _field(pv1_parts, 3)
        if trigger in REQUIRE_PV1 and not pv1_3:
            issues.append(ValidationIssue(
                "PV1_3_MISSING",
                "PV1-3 (Hébergement) est requis",
                severity="error" if strict_inbound else "warn"
            ))
        pv1_19 = _field(pv1_parts, 19)
        if trigger in REQUIRE_PV1 and not pv1_19:
            issues.append(ValidationIssue("PV1_19_MISSING", "PV1-19 (Identifiant venue) est requis", severity="warn"))

    # ZBE validation (tous champs principaux)
    zbe = _get_first_segment(msg, "ZBE")
    if zbe:
        zbe_parts = zbe.split("|")
        zbe_2 = _field(zbe_parts, 2)
        if not zbe_2:
            issues.append(ValidationIssue("ZBE2_MISSING", "ZBE-2 (Date/heure mouvement) requise", severity="error"))
        zbe_3 = _field(zbe_parts, 3)
        zbe_4 = _field(zbe_parts, 4)
        _validate_code_with_vocab(
            zbe_4,
            "ZBE4",
            issues,
            session=session,
            vocab_names=["semantic-movement-type"],
            fallback={"INSERT", "UPDATE", "CANCEL"},
            severity="error",
            required=True,
            msg=f"ZBE-4 (Type mouvement) doit être une valeur du vocabulaire sémantique, reçu: {zbe_4}"
        )
        zbe_5 = _field(zbe_parts, 5)
        zbe_6 = _field(zbe_parts, 6)
        zbe_7 = _field(zbe_parts, 7)
        zbe_8 = _field(zbe_parts, 8)
        received_zbe_9 = _field(zbe_parts, 9)
        zbe_9 = _normalize_cpage_zbe9(received_zbe_9, sending_app=sending_app, trigger=trigger)
        if zbe_9 != (received_zbe_9 or "").strip().upper():
            issues.append(ValidationIssue(
                "ZBE9_CPAGE_SUFFIX_COMPAT",
                f"ZBE-9={received_zbe_9} est une variante CPage connue ; interprété comme {zbe_9}",
                severity="warn",
                actual=received_zbe_9,
                expected=zbe_9,
            ))
        _validate_code_with_vocab(
            zbe_9,
            "ZBE9",
            issues,
            session=session,
            vocab_names=["semantic-movement-nature"],
            fallback=set(ZBE9_NATURES),
            severity="info",
            required=False,
            msg=f"ZBE-9 (Nature mouvement) doit être une valeur du vocabulaire sémantique, reçu: {zbe_9}"
        )

    # MRG (fusion, obligatoire pour A40/A47)
    mrg = _get_first_segment(msg, "MRG")
    if trigger in MERGE_EVENTS and not mrg:
        issues.append(ValidationIssue("MRG_MISSING", f"Segment MRG obligatoire pour ADT^{trigger}", severity="error"))
    if mrg:
        mrg_parts = mrg.split("|")
        mrg_1 = _field(mrg_parts, 1)
        if not mrg_1:
            issues.append(ValidationIssue("MRG1_MISSING", "MRG-1 (Identifiants à fusionner) est requis pour fusion", severity="error"))

    # NK1 (contact, optionnel)
    nk1 = _get_first_segment(msg, "NK1")
    if nk1:
        nk1_parts = nk1.split("|")
        nk1_2 = _field(nk1_parts, 2)
        nk1_3 = _field(nk1_parts, 3)
        if not nk1_2:
            issues.append(ValidationIssue("NK1_2_MISSING", "NK1-2 (Relation contact) est recommandé", severity="info"))
        if not nk1_3:
            issues.append(ValidationIssue("NK1_3_MISSING", "NK1-3 (Adresse contact) est recommandé", severity="info"))

    # PD1 (compléments patient, optionnel)
    pd1 = _get_first_segment(msg, "PD1")
    if pd1:
        pd1_parts = pd1.split("|")
        pd1_2 = _field(pd1_parts, 2)
        if not pd1_2:
            issues.append(ValidationIssue("PD1_2_MISSING", "PD1-2 (Mode de vie) est recommandé", severity="info"))

    # Validation structure HAPI détaillée (si trigger connu)
    if trigger in SEGMENT_RULES:
        rules = SEGMENT_RULES[trigger]
        present = _get_all_segments(msg)
        
        # Vérifier segments requis
        for seg in rules.get("required", []):
            if seg not in present:
                issues.append(ValidationIssue(
                    f"{seg}_MISSING",
                    f"Segment {seg} requis pour {trigger} (structure HAPI)",
                    severity="error"
                ))
        
        # Vérifier segments interdits
        for seg in rules.get("forbidden", []):
            if seg in present:
                issues.append(ValidationIssue(
                    f"{seg}_FORBIDDEN",
                    f"Segment {seg} interdit pour {trigger} (structure HAPI)",
                    severity="error"
                ))
        
        # Valider l'ordre des segments selon HAPI
        _validate_segment_order(msg, trigger, issues)
        
        # Info: segments optionnels présents (pour traçabilité détaillée)
        optional = rules.get("optional", [])
        present_optional = [s for s in optional if s in present]
        if present_optional:
            issues.append(ValidationIssue(
                "OPTIONAL_SEGMENTS",
                f"Segments optionnels présents: {', '.join(sorted(present_optional))}",
                severity="info"
            ))
    else:
        # Trigger inconnu: validation générique (legacy)
        pv1 = _get_first_segment(msg, "PV1")
        if trigger in REQUIRE_PV1 and not pv1:
            issues.append(ValidationIssue("PV1_MISSING", f"PV1 segment is required for event {trigger}"))
        if trigger in IDENTITY_ONLY and pv1:
            issues.append(ValidationIssue("PV1_UNEXPECTED", f"PV1 is generally not expected for identity-only event {trigger}", severity="info"))

    # Segments interdits par le profil IHE PAM FR
    present_segments = _get_all_segments(msg)
    forbidden_present = sorted(s for s in present_segments if s in FORBIDDEN_PAM_SEGMENTS)
    for seg in forbidden_present:
        issues.append(ValidationIssue(
            f"{seg}_FORBIDDEN",
            f"Segment {seg} interdit par le profil IHE PAM FR",
            severity="error"
        ))

    for line in _split_lines(msg):
        if not line or "|" not in line:
            continue
        segment = line.split("|", 1)[0]
        if segment and segment not in ALLOWED_SEGMENTS:
            issues.append(ValidationIssue("SEGMENT_UNKNOWN", f"Segment {segment} non prévu par le profil IHE PAM France", severity="error"))
    for singleton in {"MSH", "EVN", "PID", "PV1", "PV2", "MRG", "ZBE"}:
        count = sum(1 for line in _split_lines(msg) if line.startswith(singleton + "|"))
        if count > 1:
            issues.append(ValidationIssue(f"{singleton}_REPEATED", f"{singleton} ne doit pas être répété dans un message ADT PAM", severity="error"))
    
    # Validation ZBE (IHE PAM FR étendue)
    zbe = _get_first_segment(msg, "ZBE")
    if strict_inbound and trigger in MOVEMENT_EVENTS and not zbe:
        issues.append(ValidationIssue("ZBE_MISSING", f"Segment ZBE obligatoire pour ADT^{trigger}", severity="error"))
    if zbe:
        zbe_parts = zbe.split("|")
        zbe_1 = _field(zbe_parts, 1)
        zbe_2 = _field(zbe_parts, 2)
        zbe_3 = _field(zbe_parts, 3)
        zbe_4 = _field(zbe_parts, 4).upper() if _field(zbe_parts, 4) else ""
        zbe_5 = _field(zbe_parts, 5).upper() if _field(zbe_parts, 5) else ""
        zbe_6 = _field(zbe_parts, 6).upper() if _field(zbe_parts, 6) else ""
        zbe_7 = _field(zbe_parts, 7)
        zbe_8 = _field(zbe_parts, 8)
        zbe_9 = _normalize_cpage_zbe9(
            _field(zbe_parts, 9), sending_app=sending_app, trigger=trigger,
        )

        # ZBE-1 identifiant mouvement
        if not zbe_1:
            issues.append(ValidationIssue("ZBE1_MISSING", "ZBE-1 identifiant mouvement requis", severity="error"))
        else:
            for idx, identifier in enumerate(zbe_1.split("~")):
                comps1 = identifier.split("^")
                entity_id = comps1[0].strip() if comps1 else ""
                namespace = comps1[1].strip() if len(comps1) > 1 else ""
                universal_id = comps1[2].strip() if len(comps1) > 2 else ""
                universal_type = comps1[3].strip() if len(comps1) > 3 else ""
                if not entity_id:
                    issues.append(ValidationIssue("ZBE1_ID_EMPTY", f"ZBE-1[{idx}] identifiant vide", severity="error"))
                if not namespace and not universal_id:
                    issues.append(ValidationIssue(
                        "ZBE1_NAMESPACE_MISSING",
                        f"ZBE-1[{idx}] doit contenir EI-2 (namespace) ou EI-3 (OID)",
                        severity="error" if strict_inbound else "warn",
                    ))
                if universal_id and universal_type and universal_type != "ISO":
                    issues.append(ValidationIssue("ZBE1_UNIVERSAL_ID_TYPE_INVALID", f"ZBE-1[{idx}].EI-4 doit être ISO", severity="error"))

        if zbe_3:
            issues.append(ValidationIssue("ZBE3_FORBIDDEN", "ZBE-3 est interdit par le profil IHE PAM France", severity="error"))

        # ZBE-2 date/heure
        if not zbe_2:
            issues.append(ValidationIssue("ZBE2_MISSING", "ZBE-2 date/heure mouvement requise", severity="error"))
        else:
            _validate_ts_timestamp(zbe_2, "ZBE2", issues)

        # ZBE-4 action
        if zbe_4 and zbe_4 not in {"INSERT", "UPDATE", "CANCEL"}:
            issues.append(ValidationIssue("ZBE4_INVALID", f"ZBE-4 action inconnue: {zbe_4}", severity="error"))
        if not zbe_4:
            issues.append(ValidationIssue("ZBE4_MISSING", "ZBE-4 action requise (INSERT|UPDATE|CANCEL)", severity="error"))

        # ZBE-5 historic flag
        if zbe_5 and zbe_5 not in {"Y", "N"}:
            issues.append(ValidationIssue("ZBE5_INVALID", f"ZBE-5 doit être Y ou N, reçu: {zbe_5}", severity="error"))
        if not zbe_5:
            issues.append(ValidationIssue("ZBE5_MISSING", "ZBE-5 historique (Y/N) requis", severity="error"))

        # ZBE-6 original trigger requirement if UPDATE/CANCEL
        if zbe_4 in {"UPDATE", "CANCEL"} and not zbe_6:
            issues.append(ValidationIssue("ZBE6_REQUIRED", f"ZBE-6 trigger original requis avec action {zbe_4}", severity="error"))
        if zbe_6 and zbe_4 == "INSERT":
            issues.append(ValidationIssue("ZBE6_UNEXPECTED", "ZBE-6 ne doit pas être présent avec action INSERT", severity="error"))
        if zbe_4 == "UPDATE" and trigger != "Z99":
            issues.append(ValidationIssue("ZBE4_TRIGGER_INCONSISTENT", "UPDATE est réservé à l'événement Z99", severity="error"))
        if trigger == "Z99" and zbe_4 != "UPDATE":
            issues.append(ValidationIssue("Z99_ACTION_INVALID", "Z99 doit porter ZBE-4=UPDATE", severity="error"))

        # ZBE-7 UF médicale (XON) code composant 10
        requires_medical_uf = bool(set(zbe_9) & {"M"})
        if requires_medical_uf and not zbe_7:
            issues.append(ValidationIssue("ZBE7_MISSING", "ZBE-7 UF médicale requise", severity="error"))
        else:
            comps7 = zbe_7.split("^")
            if len(comps7) < 10 or not comps7[9].strip():
                issues.append(ValidationIssue("ZBE7_CODE_MISSING", "ZBE-7 composant 10 code UF médicale manquant", severity="error"))

        # ZBE-8 UF soins (XON) code composant 10. Cette UF est rarement
        # renseignée dans les échanges de terrain, y compris pour certaines
        # natures contenant S. Le signaler sans bloquer l'intégration ni la
        # réémission d'un message PAM autrement exploitable.
        requires_care_uf = bool(set(zbe_9) & {"S"})
        if zbe_8:
            comps8 = zbe_8.split("^")
            if len(comps8) < 10 or not comps8[9].strip():
                issues.append(ValidationIssue(
                    "ZBE8_CODE_MISSING",
                    "ZBE-8 composant 10 code UF soins manquant",
                    severity="warn" if requires_care_uf else "info",
                ))
        elif requires_care_uf:
            issues.append(ValidationIssue(
                "ZBE8_MISSING",
                "ZBE-8 UF soins absente (avertissement d'interopérabilité)",
                severity="warn",
            ))

        if not zbe_9:
            issues.append(ValidationIssue("ZBE9_MISSING", "ZBE-9 nature requise", severity="error"))
        elif zbe_9 not in ZBE9_NATURES:
            issues.append(ValidationIssue("ZBE9_INVALID", f"ZBE-9 nature inconnue: {zbe_9}", severity="error"))
        elif zbe_9 == "C" and (trigger != "Z99" or zbe_6 not in ZBE9_C_ORIGINAL_EVENTS):
            issues.append(ValidationIssue("ZBE9_C_INVALID", "ZBE-9=C est réservé à Z99 corrigeant A01, A04 ou A05", severity="error"))
    
    # Validation des champs PV1 (types de données complexes) si présent
    pv1 = _get_first_segment(msg, "PV1")
    if pv1:
        pv1_parts = pv1.split("|")
        
        # PV1-2 est obligatoire uniquement dans le contexte d'une venue/mouvement.
        pv1_2 = _field(pv1_parts, 2)
        if trigger in REQUIRE_PV1 and not pv1_2:
            issues.append(ValidationIssue("PV1_2_MISSING", "PV1-2 (Patient Class) is required", severity="error"))
        elif pv1_2:
            # HL7 Table 0004: E, I, O, P, R, B, C, N, U
            valid_classes = {"E", "I", "O", "P", "R", "B", "C", "N", "U"}
            if pv1_2 not in valid_classes:
                issues.append(ValidationIssue("PV1_2_INVALID", f"PV1-2 (Patient Class) '{pv1_2}' not in HL7 Table 0004", severity="warn"))
        
        # PV1-3 (Assigned Patient Location) - PL type (recommandé)
        pv1_3 = _field(pv1_parts, 3)
        if pv1_3:
            # Format PL: PointOfCare^Room^Bed^Facility^LocationStatus^PersonLocationType^Building^Floor
            pl_comps = pv1_3.split("^")
            if not any(pl_comps[:4]):  # Au moins un des 4 premiers composants
                issues.append(ValidationIssue("PV1_3_EMPTY", "PV1-3 (Assigned Patient Location) should have at least PointOfCare, Room, Bed or Facility", severity="warn"))
        
        # PV1-7 (Attending Doctor) - XCN type
        pv1_7 = _field(pv1_parts, 7)
        if pv1_7:
            # Format XCN: ID^FamilyName^GivenName^MiddleName^Suffix^Prefix^Degree^SourceTable^AssigningAuthority^NameTypeCode^...
            for idx, xcn in enumerate(pv1_7.split("~")):
                if xcn:
                    xcn_comps = xcn.split("^")
                    xcn_id = xcn_comps[0] if len(xcn_comps) > 0 else ""
                    xcn_family = xcn_comps[1] if len(xcn_comps) > 1 else ""
                    if not xcn_id and not xcn_family:
                        issues.append(ValidationIssue(f"PV1_7_XCN_{idx}_INCOMPLETE", f"PV1-7[{idx}] (Attending Doctor) must have ID or Family Name", severity="warn"))
        
        # PV1-19 (Visit Number) - CX type (recommandé)
        pv1_19 = _field(pv1_parts, 19)
        if pv1_19:
            _validate_cx_identifier(pv1_19, "PV1_19", issues)
        else:
            # For events that require PV1 (stay/admission related), PV1-19 (visit number) is important
            if trigger in REQUIRE_PV1:
                issues.append(ValidationIssue("PV1_19_MISSING", f"PV1-19 (Visit Number) is recommended/required for event {trigger}", severity="error"))
        
        # PV1-44 (Admit Date/Time) - TS type
        pv1_44 = _field(pv1_parts, 44)
        if pv1_44:
            _validate_ts_timestamp(pv1_44, "PV1_44", issues)
        
        # PV1-45 (Discharge Date/Time) - TS type
        pv1_45 = _field(pv1_parts, 45)
        if pv1_45:
            _validate_ts_timestamp(pv1_45, "PV1_45", issues)

        # PV1-3 detailed checks (Assigned Patient Location: PL format)
        # Components: PointOfCare^Room^Bed^Facility^LocationStatus^PersonLocationType^Building^Floor
        if pv1_3:
            pl_comps = pv1_3.split("^")
            pov = pl_comps[0] if len(pl_comps) > 0 else ""
            room = pl_comps[1] if len(pl_comps) > 1 else ""
            bed = pl_comps[2] if len(pl_comps) > 2 else ""
            loc_status = pl_comps[4] if len(pl_comps) > 4 else ""

            # For stay/admission related events, the UF (PointOfCare) should be present
            if trigger in REQUIRE_PV1 and not pov:
                issues.append(ValidationIssue(
                    "PV1_3_1_MISSING",
                    f"PV1-3.1 (UF / PointOfCare) is expected for event {trigger}",
                    severity="error" if strict_inbound else "warn"
                ))

            # A02 transfers in BP6: destination must include UF + Chambre + Lit
            if trigger == "A02":
                if not pov:
                    issues.append(ValidationIssue("PV1_3_1_MISSING_A02", "PV1-3.1 (UF) is required for transfer (A02)", severity="error"))
                if not room:
                    issues.append(ValidationIssue("PV1_3_2_MISSING_A02", "PV1-3.2 (Room/Chambre) is required for transfer (A02)", severity="error"))
                if not bed:
                    issues.append(ValidationIssue("PV1_3_3_MISSING_A02", "PV1-3.3 (Bed/Lit) is required for transfer (A02)", severity="error"))

            # PV1-3.5 (LocationStatus): expected values often 'O' (occupied) or 'U' (unoccupied)
            if loc_status and loc_status not in {"O", "U", "R", "P"}:
                issues.append(ValidationIssue("PV1_3_5_INVALID", f"PV1-3.5 (LocationStatus) has unexpected value '{loc_status}'", severity="info"))

    # Validate extended Z-segments (beyond ZBE)
    _validate_z_segments(msg, trigger, issues, strict_inbound)

    # Determine overall level
    has_error = any(i.severity == "error" for i in issues)
    has_warn = any(i.severity == "warn" for i in issues)
    level = "fail" if has_error else ("warn" if has_warn else "ok")
    is_valid = not has_error

    # Translate issues to French for output
    try:
        from app.services.pam_i18n import translate_issues_to_fr
        issues = translate_issues_to_fr(issues)
    except Exception:
        pass

    # Build audit trail if requested
    audit_entry = None
    if include_audit:
        error_count = sum(1 for i in issues if i.severity == "error")
        warn_count = sum(1 for i in issues if i.severity == "warn")
        audit_entry = ValidationAuditEntry(
            timestamp=validation_start or datetime.utcnow().isoformat(),
            trigger=trigger,
            direction=direction,
            is_valid=is_valid,
            issues_count=len(issues),
            errors_count=error_count,
            warnings_count=warn_count,
            profile=profile,
            strict_semantic=strict_semantic
        )

    return ValidationResult(
        is_valid=is_valid,
        level=level,
        event=trigger,
        message_type=msg_type,
        issues=issues,
        audit=audit_entry
    )



__all__ = [
    "SEGMENT_RULES",
    "ValidationAuditEntry",
    "ValidationIssue",
    "ValidationResult",
    "load_custom_segment_rules",
    "validate_pam",
    "validate_pam_semantics",
]
