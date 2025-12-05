from app.services.emit_on_create import generate_pam_hl7, _snapshot_entity
from sqlmodel import Session
import re


def test_pid5_includes_name_type(session: Session):
    # Create a minimal patient object in DB via session fixture
    from app.models import Patient
    p = Patient(family="MAMAN", given="GAP", birth_family="MAMAN")
    session.add(p)
    session.commit()
    session.refresh(p)

    # Pass the model instance (snapshot doesn't include birth_family)
    hl7 = generate_pam_hl7(p, 'patient', session, operation='insert')
    assert hl7 is not None

    # Extract PID segment (HL7 uses CR '\r' as segment separator)
    segments = hl7.split('\r') if isinstance(hl7, str) else []
    pid_line = next((s for s in segments if s.startswith('PID|')), None)
    assert pid_line, f"No PID segment found in generated HL7: {hl7!r}"

    # PID fields are pipe-separated; PID-5 is 6th field index 5
    fields = pid_line.split('|')
    assert len(fields) >= 6
    pid5 = fields[5]

    # XPN components separated by ^; expect at least 7 components and last == 'L'
    comps = pid5.split('^')
    assert len(comps) >= 7, f"PID-5 has fewer than 7 components: {pid5}"
    assert comps[-1] == 'L', f"Expected name type 'L' in PID-5 last component, got: {comps[-1]}"
