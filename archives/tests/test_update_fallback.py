import pytest
from datetime import datetime
from sqlmodel import Session, select

from app.services.transport_inbound import on_message_inbound
from app.models import Patient, Dossier, Venue, Mouvement
from app.db import get_next_sequence


def _now():
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _build_msg(trigger: str, pid_id: str, venue_seq: int | None = None) -> str:
    now = _now()
    # ZBE-4=UPDATE, ZBE-1 intentionally empty to trigger fallback
    zbe = f"ZBE||{now}||UPDATE|N|{trigger}||||"
    pv1_visit = venue_seq if venue_seq is not None else ""
    return (
        f"MSH|^~\\&|TEST|TEST|RCV|RCV|{now}||ADT^{trigger}^ADT_{trigger}|MSGFALLBACK|P|2.5\r"
        f"EVN|{trigger}|{now}\r"
        f"PID|||{pid_id}^^^SRC^PI||Fallback^{trigger}||19800101|M\r"
        f"PV1||I|LOC-001||||||||||||||||{pv1_visit}\r"
        f"{zbe}\r"
    )


@pytest.mark.asyncio
async def test_update_missing_zbe1_treated_as_insert(session: Session):
    """An A01 with ZBE-4=UPDATE and missing ZBE-1 should create a new admission movement (AA)."""
    # No prior patient/movement
    pid_identifier = str(get_next_sequence(session, "patient"))

    msg = _build_msg("A01", pid_identifier)
    ack = await on_message_inbound(msg, session, None)

    assert "MSA|AA|" in ack, ack

    # Verify movement exists
    patient = session.exec(select(Patient).where(Patient.identifier == pid_identifier)).first()
    assert patient is not None
    dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
    assert dossier is not None
    venue = session.exec(select(Venue).where(Venue.dossier_id == dossier.id)).first()
    assert venue is not None
    mouvement = session.exec(select(Mouvement).where(Mouvement.venue_id == venue.id)).first()
    assert mouvement is not None
    assert mouvement.trigger_event == "A01"


@pytest.mark.asyncio
async def test_update_missing_zbe1_rejected_if_not_initial(session: Session):
    """An A01 UPDATE missing ZBE-1 after an existing movement should be rejected (AE)."""
    # Create prior context (existing admission movement)
    pat_seq = get_next_sequence(session, "patient")
    p = Patient(patient_seq=pat_seq, identifier=str(pat_seq), family="Prior", given="Context")
    session.add(p); session.flush()
    d = Dossier(dossier_seq=get_next_sequence(session, "dossier"), patient_id=p.id, uf_responsabilite="TEST", admit_time=datetime.utcnow())
    session.add(d); session.flush()
    v = Venue(venue_seq=get_next_sequence(session, "venue"), dossier_id=d.id, uf_responsabilite="TEST", start_time=datetime.utcnow(), assigned_location="LOC-001")
    session.add(v); session.flush()
    m = Mouvement(venue_id=v.id, mouvement_seq=get_next_sequence(session, "mouvement"), when=datetime.utcnow(), location="LOC-001", trigger_event="A01")
    session.add(m); session.commit()

    msg = _build_msg("A01", str(pat_seq), v.venue_seq)
    ack = await on_message_inbound(msg, session, None)

    assert "MSA|AE|" in ack, ack
    assert "identifiant mouvement" in ack or "ZBE-1" in ack
