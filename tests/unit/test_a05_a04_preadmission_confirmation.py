"""
Regression test: IHE PAM France spec (CP-2013-078, section 8.5.7.3) mandates that a
pre-admission (A05) can be confirmed either by A01 (hospitalisation) or by A04
(urgences/consultation externe) — both reusing the same dossier number (PID-18).

Before this fix, app/services/pam.py's handle_admission_message() only special-cased
A01 when a dossier with the same dossier_seq already existed; any other trigger
(including a legitimate A04 confirming an A05 pre-admission) fell through to the
"Doublon dossier_seq détecté" branch and raised, aborting the import. This was
confirmed against real production captures under data/pam/ where several genuine
A05 -> A04 sequences (same PID-18, PV1-2=O) exist for outpatient/emergency visits.
"""
import pytest

from app.services.message_router import IHEMessageRouter
from app.models import Patient, Dossier, Venue
from app.infrastructure.hl7.parsing.pid_parser import parse_pid
from app.infrastructure.hl7.parsing.pv1_parser import parse_pv1
from sqlmodel import select


def _msh(trigger, control_id):
    return f"MSH|^~\\&|SYS|FAC|SYS2|FAC2|20260704120000||ADT^{trigger}|{control_id}|P|2.5"


def _pid(identifier, account_number):
    fields = {1: "1", 3: f"{identifier}^^^HOSP^PI", 5: "DOE^JANE", 7: "19800101", 8: "F", 18: account_number}
    max_index = max(fields)
    parts = ["PID"] + [fields.get(i, "") for i in range(1, max_index + 1)]
    return "|".join(parts)


def _pv1(visit_number, admit_time=None):
    fields = {1: "1", 2: "O", 3: "W1^^^^^^^^UF01", 19: visit_number}
    if admit_time:
        fields[44] = admit_time
    max_index = max(fields)
    parts = ["PV1"] + [fields.get(i, "") for i in range(1, max_index + 1)]
    return "|".join(parts)


@pytest.mark.asyncio
async def test_a05_preadmission_confirmed_by_a04(session):
    msg_a05 = "\r".join([
        _msh("A05", "1"),
        _pid("IPPA05A04", "77001"),
        _pv1("9101^^^HOSP^VN", admit_time="20260704120000"),
    ])
    ok, err = await IHEMessageRouter.route_message(
        session, "A05", parse_pid(msg_a05), parse_pv1(msg_a05), msg_a05
    )
    assert ok, err
    session.commit()

    dossier = session.exec(select(Dossier).where(Dossier.dossier_seq == 77001)).first()
    assert dossier is not None

    msg_a04 = "\r".join([
        _msh("A04", "2"),
        _pid("IPPA05A04", "77001"),
        _pv1("9101^^^HOSP^VN"),
        "ZBE|9201^^^HOSP^MVT|20260704121000||INSERT|N||^^^^^^^^UF01|^^^^^^^^UF02|H",
    ])
    ok, err = await IHEMessageRouter.route_message(
        session, "A04", parse_pid(msg_a04), parse_pv1(msg_a04), msg_a04
    )
    assert ok, err

    # The A04 must reuse the same dossier (same dossier_seq=77001), not raise
    # "Doublon dossier_seq détecté", and not create a second Dossier row.
    dossiers = session.exec(select(Dossier).where(Dossier.dossier_seq == 77001)).all()
    assert len(dossiers) == 1

    patient = session.exec(select(Patient).where(Patient.identifier == "IPPA05A04")).first()
    assert patient is not None
    venues = session.exec(select(Venue).where(Venue.dossier_id == dossiers[0].id)).all()
    assert len(venues) == 1
