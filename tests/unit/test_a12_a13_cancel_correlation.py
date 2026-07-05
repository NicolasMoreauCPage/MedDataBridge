"""
Regression tests: A12/A13/A44/A52/A53 cancellation/correction handlers used to call
int(movement_id) directly on the ZBE-1 value, which raises ValueError for any
namespaced CX/EI value (the normal, spec-compliant format, e.g. "501^^^SYS_A^PI") —
silently breaking cancellation for ~all real-world IHE PAM France messages. Fixed via
the shared _find_mouvement_by_movement_id() helper (same correlation strategy as the
Z99 fix: Identifier table first, mouvement_seq fallback).
"""
import pytest
from datetime import datetime, timezone

from app.services.message_router import IHEMessageRouter
from app.services.pam import _find_mouvement_by_movement_id
from app.models import Patient, Dossier, Venue, Mouvement
from app.models_identifiers import Identifier, IdentifierType
from app.infrastructure.hl7.parsing.pid_parser import parse_pid
from app.infrastructure.hl7.parsing.pv1_parser import parse_pv1


def _msh(trigger, control_id):
    return f"MSH|^~\\&|SYS|FAC|SYS2|FAC2|20260704120000||ADT^{trigger}|{control_id}|P|2.5"


async def _admit_and_transfer(session, movement_field="501^^^SYS_A^MVT"):
    from app.db import get_next_sequence
    patient = Patient(patient_seq=get_next_sequence(session, "patient"), identifier="IPP001", family="DOE", given="JOHN")
    session.add(patient)
    session.flush()
    dossier = Dossier(dossier_seq=get_next_sequence(session, "dossier"), patient_id=patient.id, admit_time=datetime.now(timezone.utc))
    session.add(dossier)
    session.flush()
    venue = Venue(venue_seq=get_next_sequence(session, "venue"), dossier_id=dossier.id, start_time=datetime.now(timezone.utc), code="W1")
    session.add(venue)
    session.commit()

    msg_a02 = "\r".join([
        _msh("A02", "1"),
        "PID|1||IPP001^^^HOSP^PI||DOE^JOHN||19800101|M",
        f"PV1|1|I|W2^^^^^^^^UF01||||||||||||||||{venue.venue_seq}^^^HOSP^VN",
        f"ZBE|{movement_field}|20260704120000||INSERT|N||^^^^^^^^UF01|^^^^^^^^UF02|H",
    ])
    ok, err = await IHEMessageRouter.route_message(
        session, "A02", parse_pid(msg_a02), parse_pv1(msg_a02), msg_a02
    )
    assert ok, err
    session.commit()
    return venue


@pytest.mark.asyncio
async def test_a12_cancel_with_namespaced_zbe1(session):
    venue = await _admit_and_transfer(session)

    msg_a12 = "\r".join([
        _msh("A12", "2"),
        "PID|1||IPP001^^^HOSP^PI||DOE^JOHN||19800101|M",
        f"PV1|1|I|W2^^^^^^^^UF01||||||||||||||||{venue.venue_seq}^^^HOSP^VN",
        "ZBE|501^^^SYS_A^MVT|20260704120500||CANCEL|N|A02",
    ])
    ok, err = await IHEMessageRouter.route_message(
        session, "A12", parse_pid(msg_a12), parse_pv1(msg_a12), msg_a12
    )
    assert ok, err


def _bare_venue(session):
    from app.db import get_next_sequence
    patient = Patient(patient_seq=get_next_sequence(session, "patient"), identifier=f"IPP{get_next_sequence(session, 'patient')}", family="X", given="Y")
    session.add(patient)
    session.flush()
    dossier = Dossier(dossier_seq=get_next_sequence(session, "dossier"), patient_id=patient.id, admit_time=datetime.now(timezone.utc))
    session.add(dossier)
    session.flush()
    venue = Venue(venue_seq=get_next_sequence(session, "venue"), dossier_id=dossier.id, start_time=datetime.now(timezone.utc), code="W1")
    session.add(venue)
    session.flush()
    return venue


def test_find_mouvement_by_movement_id_resolves_bare_seq(session):
    venue = _bare_venue(session)
    mouvement = Mouvement(
        mouvement_seq=999, venue_id=venue.id, location="W1",
        movement_type="admission", status="active", when=datetime.now(timezone.utc),
    )
    session.add(mouvement)
    session.commit()

    found = _find_mouvement_by_movement_id(session, "999^^^SYS_A^PI")
    assert found is not None
    assert found.id == mouvement.id


def test_find_mouvement_by_movement_id_resolves_external_identifier(session):
    venue = _bare_venue(session)
    mouvement = Mouvement(
        mouvement_seq=1234, venue_id=venue.id, location="W1",
        movement_type="admission", status="active", when=datetime.now(timezone.utc),
    )
    session.add(mouvement)
    session.flush()
    session.add(Identifier(
        value="EXTERNAL-42", system="SYS_A", type=IdentifierType.MVT,
        status="active", mouvement_id=mouvement.id,
    ))
    session.commit()

    # External ID doesn't match our internal mouvement_seq (1234) at all — only
    # resolvable via the Identifier table.
    found = _find_mouvement_by_movement_id(session, "EXTERNAL-42^^^SYS_A^MVT")
    assert found is not None
    assert found.id == mouvement.id


def test_find_mouvement_by_movement_id_returns_none_when_not_found(session):
    assert _find_mouvement_by_movement_id(session, "999999999^^^SYS_A^PI") is None
    assert _find_mouvement_by_movement_id(session, None) is None
