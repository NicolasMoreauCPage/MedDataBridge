"""Régressions normatives IHE PAM France 2.11 / CPage.

Ces tests couvrent les écarts qui ne doivent pas être masqués par les anciens
fixtures HL7 v2.5 génériques : structure MSH-9, ZBE France, caractères et A44.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine

from app.models import Dossier, Patient
from app.services.hl7_display import build_hl7_view
from app.services.mllp import build_ack, frame_hl7
from app.services.pam import handle_move_account_message
from app.services.pam_profile_fr import normalize_generated_message
from app.services.pam_validation import validate_pam
from app.services.test_scenario_generator import TestScenarioGenerator, TestScenarioType, message_to_hl7


def _pid(identifier: str = "P1", identity_status: str = "VALI") -> str:
    fields = [""] * 33
    fields[0] = "PID"
    fields[1] = "1"
    fields[3] = f"{identifier}^^^HOSP^PI"
    fields[5] = "DOE^JOHN"
    fields[7] = "19800101"
    fields[8] = "M"
    fields[32] = identity_status
    return "|".join(fields)


def _pv1() -> str:
    fields = [""] * 20
    fields[0] = "PV1"
    fields[1] = "1"
    fields[2] = "I"
    fields[3] = "WARD^101^A"
    fields[19] = "V1^^^HOSP^VN"
    return "|".join(fields)


def _xon(code: str) -> str:
    fields = [""] * 10
    fields[9] = code
    return "^".join(fields)


def _message(*, trigger: str = "A01", structure: str = "ADT_A01", zbe: str | None = None, sending_app: str = "S") -> str:
    msh = f"MSH|^~\\&|{sending_app}|F|R|F|202601010101||ADT^{trigger}^{structure}|MSG1|P|2.5^FRA^2.11|||||FRA|UNICODE UTF-8"
    evn = f"EVN|{trigger}|202601010101"
    if zbe is None:
        zbe = f"ZBE|MVT1^HOSP^1.2.3^ISO|202601010101||INSERT|N|||{_xon('UF1')}|H"
    return "\r".join([msh, evn, _pid(), _pv1(), zbe])


def _error_codes(message: str) -> set[str]:
    return {issue.code for issue in validate_pam(message, direction="in").issues if issue.severity == "error"}


def test_accepts_all_national_zbe9_values_with_required_ufs():
    for nature in ("S", "H", "M", "L", "D", "SM", "SH", "MH", "LD", "HMS"):
        zbe7 = _xon("UF-MED") if "M" in nature else ""
        zbe8 = _xon("UF-SOIN") if "S" in nature else ""
        zbe = f"ZBE|MVT1^HOSP^1.2.3^ISO|202601010101||INSERT|N||{zbe7}|{zbe8}|{nature}"
        errors = _error_codes(_message(zbe=zbe))
        assert "ZBE9_INVALID" not in errors
        assert "ZBE7_MISSING" not in errors
        assert "ZBE8_MISSING" not in errors


def test_rejects_profile_violations_previously_ignored():
    assert "MSH9_STRUCTURE_INVALID" in _error_codes(_message(structure="ADT_A39"))
    assert "ZBE3_FORBIDDEN" in _error_codes(_message(zbe=f"ZBE|MVT1^HOSP^1.2.3^ISO|202601010101|20260102000000|INSERT|N|||{_xon('UF1')}|H"))
    assert "ZBE4_TRIGGER_INCONSISTENT" in _error_codes(_message(zbe=f"ZBE|MVT1^HOSP^1.2.3^ISO|202601010101||UPDATE|N|A01|{_xon('UF1')}||H"))
    assert "PID19_FORBIDDEN" in _error_codes(_message().replace("||||||||||||||VALI", "|123-45-6789|||||||||||||VALI"))
    assert "ZBE2_TS_CALENDAR_INVALID" in _error_codes(_message(zbe=f"ZBE|MVT1^HOSP^1.2.3^ISO|20260231010101||INSERT|N|||{_xon('UF1')}|H"))
    assert "SEGMENT_UNKNOWN" in _error_codes(_message() + "\rZZZ|unexpected")


def test_z99_requires_update_action_and_c_is_strictly_scoped():
    zbe = f"ZBE|MVT1^HOSP^1.2.3^ISO|202601010101||INSERT|N|||{_xon('UF1')}|C"
    errors = _error_codes(_message(trigger="Z99", structure="ADT_A01", zbe=zbe))
    assert {"Z99_ACTION_INVALID", "ZBE9_C_INVALID"} <= errors


def test_cpage_known_zbe9_suffix_bug_is_tolerated_but_reported():
    z99 = _message(
        trigger="Z99", structure="ADT_A01", sending_app="CPAGE",
        zbe=f"ZBE|MVT1^CPAGE^1.2.3^ISO|202601010101||UPDATE|N|A01|{_xon('UF1')}||HMSC",
    )
    movement = _message(
        trigger="A03", structure="ADT_A03", sending_app="CPAGE",
        zbe=f"ZBE|MVT1^CPAGE^1.2.3^ISO|202601010101||INSERT|N||{_xon('UF1')}||MHC",
    )

    for message, expected in ((z99, "C"), (movement, "MH")):
        result = validate_pam(message, direction="in")
        issue = next(issue for issue in result.issues if issue.code == "ZBE9_CPAGE_SUFFIX_COMPAT")
        assert issue.severity == "warn"
        assert issue.expected == expected
        assert "ZBE9_INVALID" not in {issue.code for issue in result.issues}

    non_cpage = _message(
        trigger="A03", structure="ADT_A03",
        zbe=f"ZBE|MVT1^HOSP^1.2.3^ISO|202601010101||INSERT|N||{_xon('UF1')}||MHC",
    )
    assert "ZBE9_INVALID" in _error_codes(non_cpage)


def test_cpage_sample_corpus_has_no_zbe9_false_rejection():
    corpus = Path(__file__).parents[2] / "data" / "pam"
    cpage_messages = [
        path for path in corpus.glob("*.hl7")
        if path.read_text(encoding="utf-8", errors="replace").startswith("MSH|^~\\&|CPAGE|")
    ]
    assert cpage_messages

    error_codes = set()
    compatibility_warnings = 0
    for path in cpage_messages:
        result = validate_pam(path.read_text(encoding="utf-8", errors="replace"), direction="in")
        error_codes.update(issue.code for issue in result.issues if issue.severity == "error")
        compatibility_warnings += sum(
            issue.code == "ZBE9_CPAGE_SUFFIX_COMPAT" for issue in result.issues
        )

    assert "ZBE9_INVALID" not in error_codes
    assert not error_codes
    assert compatibility_warnings > 0


def test_cpage_missing_care_uf_is_warned_but_other_senders_are_rejected():
    zbe = "ZBE|MVT1^CPAGE^1.2.3^ISO|202601010101||INSERT|N||^^^^^^^^^UF1||HMS"
    cpage_result = validate_pam(_message(sending_app="CPAGE", zbe=zbe), direction="in")
    cpage_issue = next(issue for issue in cpage_result.issues if issue.code == "ZBE8_MISSING")
    assert cpage_issue.severity == "warn"

    standard_result = validate_pam(_message(zbe=zbe.replace("^CPAGE^", "^HOSP^")), direction="in")
    standard_issue = next(issue for issue in standard_result.issues if issue.code == "ZBE8_MISSING")
    assert standard_issue.severity == "error"


def test_normalizer_emits_msh_profile_and_ei_zbe_without_zbe3():
    legacy = "\r".join([
        "MSH|^~\\&|S|F|R|F|202601010101||ADT^A05^ADT_A01|MSG1|P|2.5^FRA^2.10|||||FRA|8859/1",
        "EVN|A05|202601010101",
        _pid(), _pv1(),
        "ZBE|MVT1^^^HOSP&1.2.3&ISO^MVT|202601010101|TRANSFER|INSERT|N|||^^^^^^^^^UF1|H",
    ])
    message = normalize_generated_message(legacy)
    msh, *_, zbe = message.split("\r")
    assert msh.split("|")[8] == "ADT^A05^ADT_A05"
    assert msh.split("|")[11] == "2.5^FRA^2.11"
    assert msh.split("|")[17] == "UNICODE UTF-8"
    assert zbe.split("|")[1] == "MVT1^HOSP^1.2.3^ISO"
    assert zbe.split("|")[3] == ""


def test_mllp_and_ack_follow_declared_utf8_profile():
    message = normalize_generated_message(_message())
    framed = frame_hl7(message.replace("DOE", "DUPONTÉ"))
    assert b"DUPONT\xc3\x89" in framed
    ack = build_ack(message)
    assert "ACK^A01^ADT_A01" in ack.split("\r")[0]
    assert ack.split("\r")[0].split("|")[17] == "UNICODE UTF-8"


def test_diagnostics_are_linkable_to_a_structured_hl7_view():
    result = validate_pam(_message(structure="ADT_A39"), direction="in")
    issue = next(issue for issue in result.issues if issue.code == "MSH9_STRUCTURE_INVALID")

    assert issue.layer == "hl7_base"
    assert issue.location == "MSH-9"
    msh = next(segment for segment in build_hl7_view(_message()) if segment["name"] == "MSH")
    message_type = next(field for field in msh["fields"] if field["location"] == "MSH-9")
    assert message_type["label"] == "Type de message"
    assert message_type["repetitions"][0]["components"][2]["value"] == "ADT_A01"


def test_qualification_generator_exports_a_valid_pam_fr_message():
    scenario = TestScenarioGenerator().generate_scenario(TestScenarioType.ADMISSION_COMPLETE, specialty="Urgences")
    message = message_to_hl7(scenario.messages[0])
    errors = [issue.code for issue in validate_pam(message, direction="out").issues if issue.severity == "error"]

    assert "ADT^A01^ADT_A01" in message
    assert "2.5^FRA^2.11" in message
    assert not errors


def test_a44_reassigns_only_the_identified_administrative_account():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        source = Patient(identifier="OLD", family="OLD", given="PATIENT")
        target = Patient(identifier="NEW", family="NEW", given="PATIENT")
        session.add(source)
        session.add(target)
        session.flush()
        dossier = Dossier(dossier_seq=42, patient_id=source.id, admit_time=datetime.now(timezone.utc))
        session.add(dossier)
        session.commit()

        result = asyncio.run(handle_move_account_message(
            session,
            "A44",
            {"identifiers": [("NEW^^^HOSP^PI", "PI")], "external_id": "NEW", "account_number": "42^^^HOSP^AN"},
            {},
            "MSH|^~\\&|S|F|R|F|202601010101||ADT^A44^ADT_A43|1|P|2.5^FRA^2.11\rPID|||NEW^^^HOSP^PI\rMRG|OLD^^^HOSP^PI",
        ))
        assert result == (True, None)
        assert session.get(Dossier, dossier.id).patient_id == target.id
