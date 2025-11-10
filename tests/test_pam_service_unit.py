import pytest
from datetime import datetime
from sqlmodel import Session

from app.services import pam
from app.models import Patient, Dossier, Venue, Mouvement


def test_process_pam_message_basic():
    msg = "MSH|^~\\&|A|B|C|D|20230101000000||ADT^A01|MSG|P|2.5\rPID|1||123456^^^HOSP^PI||DOE^JOHN||19800101|M\rPV1|1|I|WARD^ROOM^BED||"
    res = pam.process_pam_message(None, msg)
    assert res["trigger"].startswith("ADT^A01")
    assert res["patient_identifier"] == "123456"
    assert res["patient_name"]["family"] == "DOE"
    assert res["segments"]["MSH"]
    assert res["segments"]["PID"]
    assert res["segments"]["PV1"]


def test_parse_zbe_segment_integration_format():
    zbe = "ZBE|MVT001|20230101120000||INSERT|N|A01|^^^^^^TYPE^UF01^^^^^^^|^^^^^^TYPE^UF02^^^^^^^|M"
    parsed = pam._parse_zbe_segment(zbe)
    assert parsed is not None
    assert parsed["movement_id"] == "MVT001"
    assert parsed["movement_datetime"] == "20230101120000"
    assert parsed["action_type"] == "INSERT"
    assert parsed["origin_event"] == "A01"


def make_minimal_dossier(session: Session):
    p = Patient(family="Test", given="User", identifier="P123", patient_seq=1, birth_date="19900101", gender="F")
    session.add(p)
    session.flush()
    d = Dossier(patient_id=p.id, dossier_seq=1, admit_time=datetime.utcnow())
    session.add(d)
    session.flush()
    v = Venue(dossier_id=d.id, venue_seq=1, start_time=datetime.utcnow())
    session.add(v)
    session.flush()
    m = Mouvement(venue_id=v.id, mouvement_seq=1, when=datetime.utcnow(), movement_type="admission", type="ADT^A01")
    session.add(m)
    session.commit()
    session.refresh(d)
    return p, d, v, m


def test_generate_pam_messages_for_dossier(tmp_path):
    # use a temporary SQLite in-memory DB via Session factory from app.db
    from app.db import session_factory
    s = session_factory()
    try:
        p, d, v, m = make_minimal_dossier(s)
        # attach created patient/dossier to objects
        s.add(p)
        s.add(d)
        s.commit()
        msgs = pam.generate_pam_messages_for_dossier(d)
        assert isinstance(msgs, list)
        assert len(msgs) >= 1
        first = msgs[0]
        assert "MSH|" in first
        assert "PID|||" in first
    finally:
        s.close()
