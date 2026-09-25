"""Validateurs réutilisables des segments et types HL7 PAM."""
from __future__ import annotations

from typing import List, Optional, Set

from sqlmodel import select

from app.models.vocabulary import VocabularySystem
from app.services.pam_validation_models import ValidationIssue
from app.services.pam_validation_rules import (
    PID13_ALLOW_EQUIP,
    PID13_ALLOW_USES,
    PID13_STRICT,
    SEGMENT_ORDER,
)

def _split_lines(msg: str) -> List[str]:
    if not msg:
        return []
    return msg.replace("\r\n", "\r").replace("\n", "\r").split("\r")


def _get_first_segment(msg: str, prefix: str) -> Optional[str]:
    for line in _split_lines(msg):
        if line.startswith(prefix + "|"):
            return line
    return None


def _field(parts: List[str], idx: int) -> str:
    return parts[idx] if len(parts) > idx else ""


def _validate_code_with_vocab(
    code: str,
    field_name: str,
    issues: List[ValidationIssue],
    session=None,
    vocab_names: Optional[List[str]] = None,
    fallback: Optional[Set[str]] = None,
    severity: str = "error",
    required: bool = True,
    msg: Optional[str] = None,
) -> None:
    """
    Validate a codified field against dynamic vocabulary (db) or fallback set.
    """
    if not code:
        if required:
            issues.append(ValidationIssue(f"{field_name}_MISSING", f"{field_name} est requis", severity=severity))
        return
    valid_codes = None
    if session is not None and vocab_names:
        vocab = session.exec(select(VocabularySystem).where(VocabularySystem.name.in_(vocab_names))).first()
        if vocab:
            valid_codes = {v.code for v in vocab.values}
    if not valid_codes and fallback:
        valid_codes = fallback
    if valid_codes and code not in valid_codes:
        issues.append(ValidationIssue(f"{field_name}_INVALID", msg or f"{field_name} doit être dans {valid_codes}, reçu: {code}", severity=severity))


def _validate_segment_order(msg: str, trigger: str, issues: List[ValidationIssue]) -> None:
    """Valide l'ordre des segments selon les structures HAPI.
    
    Les segments doivent apparaître dans l'ordre défini par SEGMENT_ORDER.
    Les segments doivent être dans l'ordre croissant de leur position attendue.
    """
    if trigger not in SEGMENT_ORDER:
        return  # Pas d'ordre défini pour ce trigger
    
    expected_order = SEGMENT_ORDER[trigger]
    lines = _split_lines(msg)
    
    # Extraire les segments présents avec leurs positions
    present_segments = []
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        seg_name = line[:3].strip()
        if seg_name and seg_name in expected_order:
            expected_pos = expected_order.index(seg_name)
            present_segments.append((seg_name, idx, expected_pos))
    
    # Vérifier que l'ordre attendu est respecté
    # Pour chaque segment, sa position attendue doit être >= à celle du segment précédent
    for i in range(1, len(present_segments)):
        curr_seg, curr_line, curr_exp = present_segments[i]
        prev_seg, prev_line, prev_exp = present_segments[i-1]
        
        if curr_exp < prev_exp:
            # Le segment actuel a une position attendue AVANT le segment précédent
            # = il est mal placé (devrait venir avant)
            issues.append(ValidationIssue(
                f"SEGMENT_ORDER_{curr_seg}",
                f"Segment {curr_seg} at line {curr_line+1} should appear before {prev_seg} (line {prev_line+1}) according to HAPI {trigger} structure",
                severity="warn"
            ))


def _validate_cx_identifier(cx: str, field_name: str, issues: List[ValidationIssue]) -> None:
    """Valide un identifiant CX (Extended Composite ID with Check Digit).
    
    Format CX: ID^CheckDigit^CheckDigitScheme^AssigningAuthority^IdentifierTypeCode^AssigningFacility
    Composants: ID (requis), reste optionnel
    """
    if not cx or not cx.strip():
        return
    
    components = cx.split("^")
    id_value = components[0] if len(components) > 0 else ""
    
    if not id_value:
        issues.append(ValidationIssue(
            f"{field_name}_CX_ID_EMPTY",
            f"{field_name}: CX ID component (1st) must not be empty",
            severity="error"
        ))
    
    # Check digit scheme si check digit présent
    if len(components) > 1 and components[1]:
        check_scheme = components[2] if len(components) > 2 else ""
        if not check_scheme:
            issues.append(ValidationIssue(
                f"{field_name}_CX_SCHEME_MISSING",
                f"{field_name}: CX Check Digit Scheme required when Check Digit present",
                severity="warn"
            ))


def _validate_xpn_name(xpn: str, field_name: str, issues: List[ValidationIssue]) -> None:
    """Valide un nom XPN (Extended Person Name).
    
    Format XPN: FamilyName^GivenName^MiddleName^Suffix^Prefix^Degree^NameTypeCode^...
    Au minimum FamilyName OU GivenName requis.
    """
    if not xpn or not xpn.strip():
        return
    
    components = xpn.split("^")
    family = components[0] if len(components) > 0 else ""
    given = components[1] if len(components) > 1 else ""
    
    if not family and not given:
        issues.append(ValidationIssue(
            f"{field_name}_XPN_INCOMPLETE",
            f"{field_name}: XPN must have at least Family Name or Given Name",
            severity="error"
        ))
    
    # Name Type Code (7ème composant) validation si présent
    if len(components) > 6 and components[6]:
        name_type = components[6]
        valid_types = {"A", "B", "C", "D", "I", "L", "M", "N", "P", "R", "S", "T", "U"}
        if name_type not in valid_types:
            issues.append(ValidationIssue(
                f"{field_name}_XPN_TYPE_INVALID",
                f"{field_name}: XPN Name Type Code '{name_type}' not in HL7 Table 0200",
                severity="warn"
            ))


def _validate_xad_address(xad: str, field_name: str, issues: List[ValidationIssue]) -> None:
    """Valide une adresse XAD (Extended Address).
    
    Format XAD: StreetAddress^OtherDesignation^City^State^Zip^Country^AddressType^...
    Au minimum un composant d'adresse doit être présent.
    """
    if not xad or not xad.strip():
        return
    
    components = xad.split("^")
    
    # Vérifier qu'au moins un composant d'adresse est présent
    has_content = any(
        components[i].strip() if len(components) > i else ""
        for i in range(6)  # Street, Other, City, State, Zip, Country
    )
    
    if not has_content:
        issues.append(ValidationIssue(
            f"{field_name}_XAD_EMPTY",
            f"{field_name}: XAD must have at least one address component",
            severity="warn"
        ))
    
    # Address Type (7ème composant) validation si présent
    if len(components) > 6 and components[6]:
        addr_type = components[6]
        # HL7 Table 0190: B, BA, BDL, BI, BR, C, F, H, L, M, N, O, P, RH, SH
        valid_types = {"B", "BA", "BDL", "BI", "BR", "C", "F", "H", "L", "M", "N", "O", "P", "RH", "SH", "BIR"}
        if addr_type and addr_type not in valid_types:
            issues.append(ValidationIssue(
                f"{field_name}_XAD_TYPE_INVALID",
                f"{field_name}: XAD Address Type '{addr_type}' not in HL7 Table 0190 (or custom)",
                severity="info"
            ))


def _validate_xtn_telecom(xtn: str, field_name: str, issues: List[ValidationIssue]) -> None:
    """Valide un numéro de téléphone XTN (Extended Telecommunication Number).
    
    Format XTN: [CountryCode]^TelephoneNumber^TelecommunicationUseCode^TelecommunicationEquipmentType^...
    Le numéro de téléphone (2ème ou formule complète dans 1er) est requis.
    """
    if not xtn or not xtn.strip():
        return
    
    components = xtn.split("^")
    
    # XTN-1: Telephone Number (deprecated, not used - index 0)
    # XTN-2: Telecommunication Use Code (Table 0201 - index 1)
    # XTN-3: Telecommunication Equipment Type (Table 0202 - index 2)
    # XTN-4: Email Address (index 3)
    # XTN-12: Unformatted Telephone Number (index 11)
    
    # XTN peut avoir le numéro dans le 1er composant (forme simple) ou 12ème (forme étendue)
    phone = components[0] if len(components) > 0 else ""
    phone_unformatted = components[11] if len(components) > 11 else ""
    
    if not phone and not phone_unformatted:
        # Pour les emails (NET), le numéro n'est pas requis
        is_email = len(components) > 1 and components[1] == "NET"
        if not is_email:
            issues.append(ValidationIssue(
                f"{field_name}_XTN_EMPTY",
                f"{field_name}: XTN must have a telephone number or email",
                severity="warn"
            ))
    
    # XTN-2: Telecommunication Use Code validation (index 1)
    # Decide policy for strict checking on PID-13
    is_pid13 = field_name.startswith("PID13")
    pid13_should_strict = PID13_STRICT and is_pid13

    if len(components) > 1 and components[1]:
        use_code = components[1]
        # permissive set for general checks (Table 0201)
        valid_uses = {"ASN", "BPN", "EMR", "NET", "ORN", "PRN", "PRS", "VHN", "WPN"}
        # If strict mode for PID13 is enabled, enforce membership unless explicitly allowed by env
        if is_pid13 and pid13_should_strict:
            if use_code not in valid_uses and use_code not in PID13_ALLOW_USES:
                issues.append(ValidationIssue(
                    f"{field_name}_XTN_USE_INVALID",
                    f"{field_name}: XTN-2 Use Code '{use_code}' not in HL7 Table 0201",
                    severity="error"
                ))
        else:
            # Non-PID13 fields use an informational, permissive check.  This
            # helper is also called for PID-14, so it must not depend on a
            # local PV1 value from the enclosing message validator.
            if not is_pid13 and use_code not in valid_uses:
                issues.append(ValidationIssue(
                    f"{field_name}_XTN_USE_INVALID",
                    f"{field_name}: XTN-2 Use Code '{use_code}' not in HL7 Table 0201",
                    severity="info"
                ))

    # XTN-3: Equipment Type validation (index 2)
    if len(components) > 2 and components[2]:
        equip_type = components[2]
        # Table 0202
        valid_types = {"BP", "CP", "FX", "Internet", "MD", "PH", "SAT", "TDD", "TTY", "X.400"}
        if is_pid13 and pid13_should_strict:
            if equip_type not in valid_types and equip_type not in PID13_ALLOW_EQUIP:
                issues.append(ValidationIssue(
                    f"{field_name}_XTN_EQUIP_INVALID",
                    f"{field_name}: XTN-3 Equipment Type '{equip_type}' not in HL7 Table 0202",
                    severity="error"
                ))
        else:
            if not is_pid13 and equip_type not in valid_types:
                issues.append(ValidationIssue(
                    f"{field_name}_XTN_EQUIP_INVALID",
                    f"{field_name}: XTN-3 Equipment Type '{equip_type}' not in HL7 Table 0202",
                    severity="info"
                ))
    
    # XTN-4: Email Address validation (index 3)
    # Selon specs IHE France, si XTN-2 = NET, alors XTN-4 contient l'email
    if len(components) > 1 and components[1] == "NET":
        if len(components) > 3 and components[3]:
            email = components[3]
            # Validation basique d'email
            if "@" not in email or "." not in email.split("@")[-1]:
                issues.append(ValidationIssue(
                    f"{field_name}_XTN_EMAIL_INVALID",
                    f"{field_name}: XTN-4 Email '{email}' is not a valid email format",
                    severity="warn"
                ))
        else:
            issues.append(ValidationIssue(
                f"{field_name}_XTN_EMAIL_MISSING",
                f"{field_name}: XTN-4 Email Address required when XTN-2 = NET",
                severity="error"
            ))

def _validate_ts_timestamp(ts: str, field_name: str, issues: List[ValidationIssue]) -> None:
    """Valide un timestamp TS (Time Stamp).
    
    Format TS: YYYY[MM[DD[HH[MM[SS[.S[S[S[S]]]]]]]]][+/-ZZZZ]
    Minimum YYYY requis, format strict.
    """
    if not ts or not ts.strip():
        return
    
    # Enlever le timezone pour validation du core
    ts_core = ts.split("+")[0].split("-")[0] if ("+" in ts or "-" in ts[4:]) else ts
    
    # Enlever les fractions de secondes
    if "." in ts_core:
        ts_core = ts_core.split(".")[0]
    
    # Valider longueur et format
    if len(ts_core) < 4:
        issues.append(ValidationIssue(
            f"{field_name}_TS_TOO_SHORT",
            f"{field_name}: TS must be at least YYYY (4 chars), got '{ts}'",
            severity="error"
        ))
        return
    
    # Valider que c'est numérique
    if not ts_core.isdigit():
        issues.append(ValidationIssue(
            f"{field_name}_TS_FORMAT",
            f"{field_name}: TS format invalid '{ts}', expected YYYY[MM[DD[HH[MM[SS]]]]]",
            severity="error"
        ))
        return
    
    # Les précisions HL7 autorisées vont de l'année à la seconde, par paires.
    if len(ts_core) not in {4, 6, 8, 10, 12, 14}:
        issues.append(ValidationIssue(
            f"{field_name}_TS_PRECISION_INVALID",
            f"{field_name}: précision TS invalide ({len(ts_core)} chiffres)",
            severity="error",
        ))
        return

    # Valider les valeurs selon la longueur
    if len(ts_core) >= 6:
        month = ts_core[4:6]
        if not (1 <= int(month) <= 12):
            issues.append(ValidationIssue(
                f"{field_name}_TS_MONTH_INVALID",
                f"{field_name}: TS month '{month}' not in 01-12",
                severity="error"
            ))
    
    if len(ts_core) >= 8:
        day = ts_core[6:8]
        if not (1 <= int(day) <= 31):
            issues.append(ValidationIssue(
                f"{field_name}_TS_DAY_INVALID",
                f"{field_name}: TS day '{day}' not in 01-31",
                severity="error"
            ))
    
    if len(ts_core) >= 10:
        hour = ts_core[8:10]
        if not (0 <= int(hour) <= 23):
            issues.append(ValidationIssue(
                f"{field_name}_TS_HOUR_INVALID",
                f"{field_name}: TS hour '{hour}' not in 00-23",
                severity="error"
            ))
    
    if len(ts_core) >= 12:
        minute = ts_core[10:12]
        if not (0 <= int(minute) <= 59):
            issues.append(ValidationIssue(
                f"{field_name}_TS_MINUTE_INVALID",
                f"{field_name}: TS minute '{minute}' not in 00-59",
                severity="error"
            ))
    
    if len(ts_core) >= 14:
        second = ts_core[12:14]
        if not (0 <= int(second) <= 59):
            issues.append(ValidationIssue(
                f"{field_name}_TS_SECOND_INVALID",
                f"{field_name}: TS second '{second}' not in 00-59",
                severity="error"
            ))

    # Le contrôle numérique 01..31 ne suffit pas (ex. 31 février). Construire
    # la partie renseignée avec datetime donne une validation calendrier réelle.
    if len(ts_core) >= 8:
        try:
            from datetime import datetime
            padded = ts_core.ljust(14, "0")
            datetime.strptime(padded, "%Y%m%d%H%M%S")
        except ValueError:
            issues.append(ValidationIssue(
                f"{field_name}_TS_CALENDAR_INVALID",
                f"{field_name}: date/heure calendrier impossible: {ts}",
                severity="error",
            ))


def _get_all_segments(msg: str) -> Set[str]:
    """Retourne l'ensemble des types de segments présents dans le message."""
    segments = set()
    for line in _split_lines(msg):
        if not line or "|" not in line:
            continue
        seg_type = line.split("|")[0]
        if seg_type:
            segments.add(seg_type)
    return segments


def _validate_z_segments(msg: str, trigger: str, issues: List[ValidationIssue], strict_inbound: bool) -> None:
    """
    Validate French extension Z-segments beyond ZBE.
    
    Supported Z-segments:
    - ZBE: Movement tracking (validated separately)
    - ZPD: Patient demographics extension
    - ZIS: Identifier system extension
    - ZAD: Address extension
    """
    segments = _get_all_segments(msg)
    
    # Extract Z-segments (excluding ZBE which is already validated)
    z_segments = {s for s in segments if s.startswith("Z") and s != "ZBE"}
    
    for z_seg_type in z_segments:
        z_seg_line = _get_first_segment(msg, z_seg_type)
        if not z_seg_line:
            continue
            
        parts = z_seg_line.split("|")
        
        # ZPD (Patient Demographics Extension)
        if z_seg_type == "ZPD":
            # ZPD-1: Extension ID (should be present)
            ext_id = _field(parts, 1)
            if not ext_id:
                issues.append(ValidationIssue(
                    "ZPD_1_MISSING",
                    "ZPD-1 (Extension ID) is required when ZPD segment present",
                    severity="error" if strict_inbound else "warn"
                ))
        
        # ZIS (Identifier System Extension)
        elif z_seg_type == "ZIS":
            # ZIS-1: System code (required)
            sys_code = _field(parts, 1)
            if not sys_code:
                issues.append(ValidationIssue(
                    "ZIS_1_MISSING",
                    "ZIS-1 (System Code) is required when ZIS segment present",
                    severity="error" if strict_inbound else "warn"
                ))
            # ZIS-2: System OID (should match HL7 standards)
            sys_oid = _field(parts, 2)
            if sys_oid and not sys_oid.replace(".", "").isdigit():
                issues.append(ValidationIssue(
                    "ZIS_2_INVALID",
                    f"ZIS-2 (System OID) must be numeric dot format, got: {sys_oid}",
                    severity="warn"
                ))
        
        # ZAD (Address Extension)
        elif z_seg_type == "ZAD":
            # ZAD-1: Address type (should be present)
            addr_type = _field(parts, 1)
            if not addr_type:
                issues.append(ValidationIssue(
                    "ZAD_1_MISSING",
                    "ZAD-1 (Address Type) is recommended when ZAD segment present",
                    severity="info"
                ))
