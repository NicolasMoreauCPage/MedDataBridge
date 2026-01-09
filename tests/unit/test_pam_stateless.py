import pytest

from app.services.pam_validation import validate_pam


def _base_msh(trigger: str = "A01") -> str:
    return f"MSH|^~\\&|SENDER|FAC|REC|FAC|202501010101||ADT^{trigger}|MSG001|P|2.5\rEVN|{trigger}|202501010101"


def test_pv1_19_missing_for_stay_event():
    # A01 (admission) requires PV1 and PV1-19 (visit number) per BP6
    msh = _base_msh("A01")
    # Minimal PID with PID-3 and PID-5
    pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
    # PV1 present but PV1-19 (field 19) omitted
    pv1 = "PV1|1|I|WARD^101^^HOSP|3||||||||||||||||||||"  # missing visit number component at position 19

    msg = "\r".join([msh, pid, pv1]) + "\r"
    res = validate_pam(msg)
    codes = {i.code for i in res.issues}
    assert "PV1_19_MISSING" in codes
    assert not res.is_valid


def test_a02_requires_room_and_bed():
    # A02 transfer must include PV1-3.2 and PV1-3.3 per BP6
    msh = _base_msh("A02")
    pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
    # PV1 with only PointOfCare present (no room, no bed)
    pv1 = "PV1|1|I|WARD^^^^|3||||||||||||||||||||"
    msg = "\r".join([msh, pid, pv1]) + "\r"
    res = validate_pam(msg)
    codes = {i.code for i in res.issues}
    assert "PV1_3_2_MISSING_A02" in codes
    assert "PV1_3_3_MISSING_A02" in codes
    assert not res.is_valid


def test_no_ins_c_check_present():
    # Ensure that absence of INS-C does NOT trigger an error (policy change)
    msh = _base_msh("A01")
    # PID-3 contains only a local ID (no INS-C token)
    pid = "PID|1|LOCALID123^^^LOCAL|DOE^JOHN||19700101||||||||+33123456789"
    pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||"
    msg = "\r".join([msh, pid, pv1]) + "\r"
    res = validate_pam(msg)
    codes = {i.code for i in res.issues}
    assert "PID3_INS_C_MISSING" not in codes
