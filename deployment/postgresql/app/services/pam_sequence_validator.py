"""Stateful PAM sequence validator.

This module implements sequence-dependent checks required by BP6/IHE-PAM-FR
that cannot be evaluated purely from a single HL7 message. It relies on
database access (SQLModel session) to query previously persisted movements
and venue state.

API:
- find_mouvement_by_zbe_id(session, zbe_id) -> Optional[Mouvement]
- validate_pam_sequence(msg: str, session) -> ValidationResult

Current minimal implementation:
- For ZBE action UPDATE/CANCEL: ensure referenced mouvement exists (by numeric id in ZBE-1)
- Validate that an UPDATE/CANCEL references a mouvement with the same venue/patient when possible.

Further enhancements: allowed transition checks, bed reservation/occupation checks.
"""
from typing import Optional, List
from sqlmodel import select
from dataclasses import asdict
import os

from app.services.pam_validation import ValidationIssue, ValidationResult
from app.services.mllp import parse_msh_fields
from app.state_transitions import is_valid_transition
from app.services.identifier_manager import parse_hl7_cx_identifier
from app.models_identifiers import IdentifierType

# STRICT_PAM_SEQUENCE is enforced by default (comportement demandé)
STRICT_PAM_SEQUENCE = True
from app.services.pam_i18n import translate_issues_to_fr


def _field(parts: list, idx: int) -> str:
    return parts[idx] if len(parts) > idx else ""


def _get_first_segment(msg: str, prefix: str) -> Optional[str]:
    for line in msg.replace("\r\n", "\r").replace("\n", "\r").split("\r"):
        if line.startswith(prefix + "|"):
            return line
    return None


def find_mouvement_by_zbe_id(session, zbe_1: str):
    """Try to resolve a ZBE-1 identifier to a Mouvement.

    Strategy (best-effort):
    - ZBE-1 is composite: id^namespace^oid. Try to parse first component as integer
      and match `Mouvement.mouvement_seq` or `Mouvement.id`.
    - If not numeric, return None (caller may decide to log/warn).
    """
    if not zbe_1:
        return None

    # Try parse as CX identifier (value, system, oid, type_code)
    try:
        value, system, authority_oid, type_code = parse_hl7_cx_identifier(zbe_1)
    except Exception:
        value, system, authority_oid, type_code = (zbe_1, "", None, None)

    # First attempt: if value is integer, try mouvement_seq or id
    try:
        as_int = int(value)
    except Exception:
        as_int = None

    from app.models import Mouvement
    # Try integer-based lookup
    if as_int is not None:
        res = session.exec(select(Mouvement).where(Mouvement.mouvement_seq == as_int)).first()
        if res:
            return res
        res2 = session.exec(select(Mouvement).where(Mouvement.id == as_int)).first()
        if res2:
            return res2

    # Second attempt: lookup via Identifier table (Identifier.type == MVT)
    try:
        from app.models_identifiers import Identifier
        # Match on value and optionally system/oid; prefer Identifier.type == MVT
        q = select(Identifier).where(Identifier.value == value)
        if system:
            q = q.where(Identifier.system == system)
        if authority_oid:
            q = q.where(Identifier.oid == authority_oid)
        # Prefer movement identifiers
        idents = session.exec(q).all()
        ident = None
        for it in idents:
            try:
                if getattr(it, "type", None) == IdentifierType.MVT:
                    ident = it
                    break
            except Exception:
                continue
        if not ident and idents:
            ident = idents[0]
        if ident and getattr(ident, "mouvement_id", None):
            return session.exec(select(Mouvement).where(Mouvement.id == ident.mouvement_id)).first()
    except Exception:
        pass

    # Not found
    return None


def validate_pam_sequence(msg: str, session) -> ValidationResult:
    """Run sequence-dependent validations using DB context.

    Minimal implementation:
    - For ZBE with action in UPDATE/CANCEL: ensure referenced movement (ZBE-1 id)
      exists in DB. If not, return an error issue.
    """
    issues: List[ValidationIssue] = []

    zbe_line = _get_first_segment(msg, "ZBE")
    msh = parse_msh_fields(msg)
    trigger = msh.get("trigger") if msh else ""

    if not zbe_line:
        # Nothing stateful to check
        return ValidationResult(is_valid=True, level="ok", event=trigger or "", message_type="", issues=[])

    parts = zbe_line.split("|")
    zbe_1 = parts[1] if len(parts) > 1 else None
    zbe_4 = parts[4].upper() if len(parts) > 4 and parts[4] else ""
    # PID patient identifier (first CX component) to help occupancy checks
    pid_line = _get_first_segment(msg, "PID")
    incoming_patient_id = None
    if pid_line:
        try:
            pid_parts = pid_line.split("|")
            pid_3 = _field(pid_parts, 3)
            if pid_3:
                incoming_patient_id = pid_3.split("^")[0]
        except Exception:
            incoming_patient_id = None

    if zbe_4 in {"UPDATE", "CANCEL"}:
        # Ensure referenced mouvement exists
        mov = find_mouvement_by_zbe_id(session, zbe_1)
        if not mov:
            issues.append(ValidationIssue(
                "ZBE_REF_NOT_FOUND",
                f"ZBE action {zbe_4} references movement {zbe_1} which was not found in DB",
                severity="error"
            ))
        else:
            # If the referenced movement is already cancelled, reject UPDATE (and warn on CANCEL)
            try:
                if getattr(mov, "status", None) == "cancelled":
                    if zbe_4 == "UPDATE":
                        issues.append(ValidationIssue(
                            "ZBE_REF_ALREADY_CANCELLED",
                            f"Referenced movement {getattr(mov, 'mouvement_seq', getattr(mov, 'id', 'unknown'))} is already cancelled",
                            severity="error"
                        ))
                    else:
                        issues.append(ValidationIssue(
                            "ZBE_REF_ALREADY_CANCELLED",
                            f"Referenced movement {getattr(mov, 'mouvement_seq', getattr(mov, 'id', 'unknown'))} is already cancelled",
                            severity="warn"
                        ))
            except Exception:
                pass
            # Basic consistency: compare trigger_event if present
            try:
                if mov.trigger_event and trigger and mov.trigger_event != trigger:
                    issues.append(ValidationIssue(
                        "ZBE_REF_TRIGGER_MISMATCH",
                        f"Referenced movement trigger '{mov.trigger_event}' differs from incoming '{trigger}'",
                        severity="warn"
                    ))
            except Exception:
                pass
            
            # ZBE-6 (original trigger) consistency: if provided, compare with referenced movement
            try:
                zbe_6 = parts[6] if len(parts) > 6 and parts[6] else None
                if zbe_6:
                    # Distinguish two common uses of ZBE-6: a trigger name (e.g. A01) or an identifier
                    zbe6_first = zbe_6.split("^")[0]
                    is_probable_id = False
                    try:
                        _ = int(zbe6_first)
                        is_probable_id = True
                    except Exception:
                        # not an integer — but could be a composite CX; detect '^' as heuristic
                        if "^" in zbe_6:
                            # if the first component contains digits, treat as id
                            is_probable_id = any(c.isdigit() for c in zbe6_first)

                    if is_probable_id:
                        # Try to resolve ZBE-6 to an existing movement (chain existence check)
                        ref6 = find_mouvement_by_zbe_id(session, zbe_6)
                        if not ref6:
                            sev = "warn"
                            if STRICT_PAM_SEQUENCE:
                                sev = "error"
                            issues.append(ValidationIssue(
                                "ZBE6_REF_NOT_FOUND",
                                f"ZBE-6 original reference '{zbe_6}' cannot be resolved to a persisted movement",
                                severity=sev
                            ))
                        else:
                            # If the referenced movement exists, compare its trigger with the referenced movement trigger
                            try:
                                if mov and getattr(mov, "trigger_event", None) and getattr(ref6, "trigger_event", None) and mov.trigger_event != ref6.trigger_event:
                                    issues.append(ValidationIssue(
                                        "ZBE6_CHAIN_MISMATCH",
                                        f"ZBE-6 chain: referenced movement trigger '{mov.trigger_event}' differs from ZBE-6 movement trigger '{ref6.trigger_event}'",
                                        severity="warn"
                                    ))
                            except Exception:
                                pass
                    else:
                        # Treat ZBE-6 as a trigger label (Axx) and compare to referenced movement trigger
                        try:
                            if mov and getattr(mov, "trigger_event", None) and mov.trigger_event != zbe_6:
                                sev = "warn"
                                if STRICT_PAM_SEQUENCE:
                                    sev = "warn"
                                issues.append(ValidationIssue(
                                    "ZBE6_TRIGGER_MISMATCH",
                                    f"ZBE-6 original trigger '{zbe_6}' does not match referenced movement trigger '{mov.trigger_event}'",
                                    severity=sev
                                ))
                        except Exception:
                            pass
                    # Additional BP6 checks: chain loop detection and chronology
                    try:
                        # Chain loop detection: walk up through ZBE-6 references up to depth 6
                        seen = set()
                        cur_zbe = zbe_6
                        depth = 0
                        while cur_zbe and depth < 6:
                            if cur_zbe in seen:
                                sev = "error" if STRICT_PAM_SEQUENCE else "warn"
                                issues.append(ValidationIssue(
                                    "ZBE_CHAIN_LOOP",
                                    f"ZBE reference chain contains a loop at '{cur_zbe}'",
                                    severity=sev
                                ))
                                break
                            seen.add(cur_zbe)
                            depth += 1
                            try:
                                nxt = find_mouvement_by_zbe_id(session, cur_zbe)
                                if not nxt:
                                    break
                                # attempt to read a stored ZBE-6-like identifier on the resolved movement
                                from app.models_identifiers import Identifier
                                idents = session.exec(select(Identifier).where(Identifier.mouvement_id == nxt.id)).all()
                                cur_zbe = None
                                for it in idents:
                                    # heuristic: if an identifier value looks like a composite with '^' or digits, follow it
                                    if it.value:
                                        cur_zbe = it.value
                                        break
                            except Exception:
                                break
                    except Exception:
                        pass

                    # Chronology: ensure referenced ZBE-6 movement happened before the referenced movement
                    try:
                        if ref6 and mov and getattr(ref6, "when", None) and getattr(mov, "when", None):
                            try:
                                if ref6.when > mov.when:
                                    sev = "warn"
                                    if STRICT_PAM_SEQUENCE:
                                        sev = "error"
                                    issues.append(ValidationIssue(
                                        "ZBE6_TIME_INCONSISTENT",
                                        f"ZBE-6 referenced movement time {ref6.when} is after the referenced movement time {mov.when}",
                                        severity=sev
                                    ))
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # Child-dependency check: if other movements reference this movement, cancelling it may be problematic
                    try:
                        from app.models_identifiers import Identifier
                        from app.models import Mouvement as Mov
                        if mov:
                            # identifiers referencing this mouvement_seq as value
                            val = str(getattr(mov, 'mouvement_seq', getattr(mov, 'id', None)))
                            if val:
                                deps = session.exec(select(Identifier).where(Identifier.value == val, Identifier.mouvement_id != mov.id)).all()
                                for d in deps:
                                    try:
                                        child = session.exec(select(Mov).where(Mov.id == d.mouvement_id)).first()
                                        if child and getattr(child, 'when', None) and getattr(mov, 'when', None) and child.when > mov.when:
                                            sev = "warn"
                                            if STRICT_PAM_SEQUENCE:
                                                sev = "error"
                                            issues.append(ValidationIssue(
                                                "ZBE_REF_HAS_CHILDREN",
                                                f"Referenced movement {val} has dependent movement {getattr(child,'mouvement_seq', getattr(child,'id','?'))} recorded after it",
                                                severity=sev
                                            ))
                                            break
                                    except Exception:
                                        continue
                    except Exception:
                        pass
                else:
                    # no zbe_6 provided — nothing to check here
                    pass
            except Exception:
                pass
            # If referenced movement exists, ensure venue/patient consistency
            try:
                if mov and ref6:
                    # If venues differ, report possible chain inconsistency
                    mv_venue = getattr(mov, "venue_id", None)
                    r6_venue = getattr(ref6, "venue_id", None)
                    if mv_venue and r6_venue and mv_venue != r6_venue:
                        sev = "warn"
                        if STRICT_PAM_SEQUENCE:
                            sev = "warn"
                        issues.append(ValidationIssue(
                            "ZBE6_CHAIN_VENUE_MISMATCH",
                            f"ZBE-6 chain: referenced movement venue {r6_venue} differs from referenced movement's venue {mv_venue}",
                            severity=sev
                        ))
            except Exception:
                pass

    # If PV1-19 present, check allowed transitions using last persisted movement for the venue
    pv1_line = _get_first_segment(msg, "PV1")
    if pv1_line:
        pv1_parts = pv1_line.split("|")
        pv1_19 = _field(pv1_parts, 19)
        venue_seq = None
        if pv1_19:
            # PV1-19 may be CX: id^namespace... take first component
            venue_id_str = pv1_19.split("^")[0] if "^" in pv1_19 else pv1_19
            try:
                venue_seq = int(venue_id_str)
            except Exception:
                venue_seq = None

        if venue_seq:
            try:
                from app.models import Mouvement

                last_mov = session.exec(
                    select(Mouvement).where(Mouvement.venue_id == venue_seq).order_by(Mouvement.when.desc())
                ).first()
                previous_event = last_mov.trigger_event if last_mov and getattr(last_mov, "trigger_event", None) else None
                # If previous_event exists, validate transition
                if previous_event and trigger and not is_valid_transition(previous_event, trigger):
                    sev = "error" if STRICT_PAM_SEQUENCE else "warn"
                    issues.append(ValidationIssue(
                        "TRANSITION_NOT_ALLOWED",
                        f"Transition not allowed: {previous_event} -> {trigger} according to ALLOWED_TRANSITIONS",
                        severity=sev
                    ))
                # If the incoming message references the same referenced movement, ensure the venues align
                try:
                    if previous_event and trigger and mov:
                        # If the movement exists but venue differs from PV1-19, flag
                        if venue_seq and getattr(mov, "venue_id", None) and getattr(mov, "venue_id", None) != venue_seq:
                            sev = "warn"
                            if STRICT_PAM_SEQUENCE:
                                sev = "error"
                            issues.append(ValidationIssue(
                                "ZBE_REF_VENUE_MISMATCH",
                                f"Referenced movement venue {getattr(mov, 'venue_id', None)} does not match PV1-19 venue {venue_seq}",
                                severity=sev
                            ))
                except Exception:
                    pass
            except Exception:
                # DB lookup failure should not block processing, but warn
                issues.append(ValidationIssue(
                    "SEQ_VALIDATION_DB_ERROR",
                    "Unable to query DB to validate sequence transitions",
                    severity="warn"
                ))

    # Basic bed occupancy check for incoming transfers (A02) when PV1-3 contains room+bed
    if trigger == "A02":
        try:
            pv1_parts = pv1_line.split("|")
            pv1_3 = _field(pv1_parts, 3)
            room = bed = None
            if pv1_3:
                pl_comps = pv1_3.split("^")
                room = pl_comps[1] if len(pl_comps) > 1 else ""
                bed = pl_comps[2] if len(pl_comps) > 2 else ""
            # For A02, destination UH+room+bed are mandatory
            if not room or not bed:
                issues.append(ValidationIssue(
                    "A02_DEST_MISSING",
                    "Transfert/Mutation (A02) requires destination UH + Chambre + Lit (PV1-3)",
                    severity="error"
                ))
            if room and bed:
                    # Find any mouvement currently assigned to same room/bed
                    from app.models import Mouvement
                    # Narrow candidate search: non-historic, not discharge events, same room/bed
                    q = select(Mouvement).where(Mouvement.to_location.contains(f"^{room}^{bed}"))
                    try:
                        q = q.where(Mouvement.is_historic == False)
                    except Exception:
                        pass
                    candidates = session.exec(q).all()
                    for candidate in candidates:
                        # Skip if candidate refers to the same patient as incoming (moving within patient's own history)
                        cand_patient = getattr(candidate, "patient_seq", None) or getattr(candidate, "patient_id", None) or getattr(candidate, "dossier_id", None)
                        same_patient = False
                        if incoming_patient_id and cand_patient:
                            try:
                                same_patient = str(incoming_patient_id) == str(cand_patient)
                            except Exception:
                                same_patient = False
                        if same_patient:
                            continue

                        is_active = not getattr(candidate, "is_historic", False) and getattr(candidate, "trigger_event", None) not in ("A03", "A11")
                        if not is_active:
                            continue

                        sev = "error" if STRICT_PAM_SEQUENCE else "warn"
                        issues.append(ValidationIssue(
                            "BED_OCCUPIED",
                            f"Requested bed {room}/{bed} appears already assigned by movement {getattr(candidate, 'mouvement_seq', getattr(candidate, 'id', 'unknown'))} (patient {cand_patient})",
                            severity=sev
                        ))
                        # one occupant is enough to report
                        break
                    
        except Exception:
            # non-blocking
            pass

    # Translate messages to French for output
    issues = translate_issues_to_fr(issues)

    # Return aggregated result
    has_error = any(i.severity == "error" for i in issues)
    has_warn = any(i.severity == "warn" for i in issues)
    level = "fail" if has_error else ("warn" if has_warn else "ok")
    is_valid = not has_error

    return ValidationResult(is_valid=is_valid, level=level, event=trigger or "", message_type="", issues=issues)


__all__ = ["find_mouvement_by_zbe_id", "validate_pam_sequence"]
