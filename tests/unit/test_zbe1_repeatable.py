import pytest
from sqlmodel import select
from app.services.message_router import IHEMessageRouter
from app.models import Patient, Mouvement
from app.models_identifiers import Identifier
from app.services.pam import _parse_zbe_segment


def test_parse_zbe_segment_splits_repetitions():
    msg = (
        "MSH|^~\\&|SYS|FAC|SYS2|FAC2|20260704120000||ADT^A02|1|P|2.5\r"
        "ZBE|MVT001^SYS_A^1.2.3^ISO~MVT002^SYS_B^4.5.6^ISO|20260704120000||INSERT|N|A01|"
        "^^^^^^^UF01|^^^^^^^UF02|M"
    )
    result = _parse_zbe_segment(msg)
    assert result["movement_id"] == "MVT001^SYS_A^1.2.3^ISO"
    assert result["movement_ids"] == ["MVT001^SYS_A^1.2.3^ISO", "MVT002^SYS_B^4.5.6^ISO"]


def _build_a01(movement_field):
    msh = "MSH|^~\\&|SYS|FAC|SYS2|FAC2|20260704120000||ADT^A01|MSGID1|P|2.5"
    evn = "EVN|A01|20260704120000"
    pid = "PID|1||IPP999^^^HOSP^PI||DOE^JOHN||19800101|M"
    pv1 = "PV1|1|I|UF01^^^^^^^^UF01||||||||||||||||999^^^HOSP^VN"
    zbe = f"ZBE|{movement_field}|20260704120000||INSERT|N||^^^^^^^^UF01|^^^^^^^^UF02|H"
    return "\r".join([msh, evn, pid, pv1, zbe])


@pytest.mark.asyncio
async def test_zbe1_repeatable_creates_one_identifier_per_repetition(session):
    from app.infrastructure.hl7.parsing.pid_parser import parse_pid
    from app.infrastructure.hl7.parsing.pv1_parser import parse_pv1

    message = _build_a01("501^^^SYS_A^PI~502^^^SYS_B^PI")
    pid_data = parse_pid(message)
    pv1_data = parse_pv1(message)

    ok, err = await IHEMessageRouter.route_message(session, "A01", pid_data, pv1_data, message)
    assert ok, err
    session.commit()

    mouvement = session.exec(select(Mouvement)).first()
    assert mouvement is not None

    values = sorted(
        i.value for i in session.exec(
            select(Identifier).where(Identifier.mouvement_id == mouvement.id)
        ).all()
    )
    assert values == ["501", "502"]

    patient = session.exec(select(Patient)).first()
    assert patient.identifier == "IPP999"


@pytest.mark.asyncio
async def test_emitted_zbe1_leads_with_our_own_mouvement_seq(session):
    """Our internal mouvement_seq must be the FIRST ZBE-1 repetition we emit — even
    when an external MVT identifier (recorded from a correspondent's own ZBE-1, e.g. on
    a message this Mouvement was originally received from) is attached to this Mouvement
    — so that a correspondent echoing back the first repetition in a later Z99 lets us
    resolve it via a direct mouvement_seq match. Our internal ID and the correspondent's
    external one are deliberately different values here, to isolate this from admission's
    (separate) choice to sometimes adopt an inbound ZBE-1 as its own mouvement_seq."""
    from app.db import get_next_sequence
    from app.models import Dossier, Patient, Venue
    from app.models_identifiers import Identifier, IdentifierType
    from app.services.emit_on_create import generate_pam_hl7

    patient = Patient(patient_seq=1, identifier="IPP999", family="DOE", given="JOHN")
    session.add(patient)
    session.flush()
    from datetime import datetime, timezone
    dossier = Dossier(
        dossier_seq=get_next_sequence(session, "dossier"), patient_id=patient.id,
        admit_time=datetime.now(timezone.utc),
    )
    session.add(dossier)
    session.flush()
    venue = Venue(
        venue_seq=get_next_sequence(session, "venue"), dossier_id=dossier.id, code="W1",
        start_time=datetime.now(timezone.utc),
    )
    session.add(venue)
    session.flush()
    mouvement = Mouvement(
        mouvement_seq=get_next_sequence(session, "mouvement"),
        venue_id=venue.id, location="W1", movement_type="admission", status="active",
        when=datetime.now(timezone.utc),
    )
    session.add(mouvement)
    session.flush()
    session.add(Identifier(
        value="EXTERNAL-999", system="SYS_A", type=IdentifierType.MVT,
        status="active", mouvement_id=mouvement.id,
    ))
    session.commit()

    hl7_out = generate_pam_hl7(mouvement, "mouvement", session)
    zbe_line = next(l for l in hl7_out.split("\r") if l.startswith("ZBE"))
    zbe_1 = zbe_line.split("|")[1]
    reps = zbe_1.split("~")

    assert reps[0].split("^")[0] == str(mouvement.mouvement_seq)
    assert any(rep.split("^")[0] == "EXTERNAL-999" for rep in reps[1:])
