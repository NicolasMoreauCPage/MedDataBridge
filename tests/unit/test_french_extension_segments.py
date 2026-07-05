"""
Regression tests for the French national extension segments (ZFD/ZFA/ZFP/ZFV/ROL) —
parsed by app/infrastructure/hl7/parsing/french_extension_parser.py and wired into
app/services/pam.py's admission/transfer/discharge handlers. Before this change these
segments were silently ignored end-to-end even though they carry high-value data
(DMP status, INSi identity verification metadata, socio-professional classification,
RIM-P legal care mode, médecin traitant/ODRP) present in a large share of real IHE PAM
France production messages.
"""
import pytest
from datetime import datetime, timezone

from app.services.message_router import IHEMessageRouter
from app.models import Patient, Dossier, Venue, Mouvement
from app.infrastructure.hl7.parsing.pid_parser import parse_pid
from app.infrastructure.hl7.parsing.pv1_parser import parse_pv1


def _msh(trigger, control_id):
    return f"MSH|^~\\&|SYS|FAC|SYS2|FAC2|20260704120000||ADT^{trigger}|{control_id}|P|2.5"


def _segment(seg_id, fields_by_index):
    """Build a pipe-delimited HL7 segment from a {1-based field index: value} map,
    padding intermediate unset fields with empty strings (avoids fragile hand-counted
    pipes when a field far in the segment needs a value)."""
    max_index = max(fields_by_index)
    parts = [seg_id] + [fields_by_index.get(i, "") for i in range(1, max_index + 1)]
    return "|".join(parts)


def _xcn(components_by_index):
    """Build a ^-delimited XCN component string from a {0-based component index: value} map."""
    max_index = max(components_by_index)
    return "^".join(components_by_index.get(i, "") for i in range(max_index + 1))


@pytest.mark.asyncio
async def test_admission_persists_zfd_zfa_zfp_and_rol_odrp(session):
    msg_a01 = "\r".join([
        _msh("A01", "1"),
        "PID|1||IPPZFX01^^^HOSP^PI||DOE^JANE||19800101|F",
        "PV1|1|I|W1^^^^^^^^UF01||||||||||||||||9001^^^HOSP^VN",
        "ZBE|9001^^^HOSP^MVT|20260704120000||INSERT|N||^^^^^^^^UF01|^^^^^^^^UF02|H",
        _segment("ZFD", {4: "N", 5: "SM", 7: "CN", 8: "20301231"}),
        _segment("ZFA", {1: "ACTIF", 2: "20260101", 9: "NA", 11: "IC"}),
        "ZFP|1|3",
        _segment("ROL", {2: "UC", 3: "ODRP", 4: (
            _xcn({0: "10005183370", 1: "DUPONT", 2: "MARTIN", 12: "RPPS"})
            + "~" + _xcn({0: "1234567", 1: "DUPONT", 2: "MARTIN", 12: "ADELI"})
        )}),
    ])
    ok, err = await IHEMessageRouter.route_message(
        session, "A01", parse_pid(msg_a01), parse_pv1(msg_a01), msg_a01
    )
    assert ok, err

    from sqlmodel import select
    patient = session.exec(select(Patient).where(Patient.identifier == "IPPZFX01")).first()
    assert patient is not None

    # ZFD
    assert patient.birth_date_modified_indicator == "N"
    assert patient.identity_capture_mode == "SM"
    assert patient.identity_proof_type == "CN"
    # ZFA
    assert patient.dmp_status == "ACTIF"
    assert patient.dmp_feed_opposition == "NA"
    assert patient.dmp_consultation_consent == "IC"
    # ZFP
    assert patient.socio_professional_activity == "1"
    assert patient.socio_professional_category == "3"
    # ROL (ODRP) - prefers the RPPS repetition over ADELI
    assert patient.primary_care_provider == "DUPONT MARTIN"


@pytest.mark.asyncio
async def test_transfer_persists_zfv_on_mouvement(session):
    from app.db import get_next_sequence
    patient = Patient(patient_seq=get_next_sequence(session, "patient"), identifier="IPPZFV01", family="X", given="Y")
    session.add(patient)
    session.flush()
    dossier = Dossier(dossier_seq=get_next_sequence(session, "dossier"), patient_id=patient.id, admit_time=datetime.now(timezone.utc))
    session.add(dossier)
    session.flush()
    venue = Venue(venue_seq=get_next_sequence(session, "venue"), dossier_id=dossier.id, start_time=datetime.now(timezone.utc), code="W1")
    session.add(venue)
    session.commit()

    msg_a02 = "\r".join([
        _msh("A02", "2"),
        "PID|1||IPPZFV01^^^HOSP^PI||X^Y||19800101|M",
        f"PV1|1|I|W2^^^^^^^^UF01||||||||||||||||{venue.venue_seq}^^^HOSP^VN",
        "ZBE|9002^^^HOSP^MVT|20260704120500||INSERT|N||^^^^^^^^UF01|^^^^^^^^UF02|H",
        _segment("ZFV", {1: "750000001^20260701", 2: "3", 10: "PSYA", 11: "1"}),
    ])
    ok, err = await IHEMessageRouter.route_message(
        session, "A02", parse_pid(msg_a02), parse_pv1(msg_a02), msg_a02
    )
    assert ok, err

    from sqlmodel import select
    mouvement = session.exec(
        select(Mouvement).where(Mouvement.venue_id == venue.id).order_by(Mouvement.id.desc())
    ).first()
    assert mouvement is not None
    assert mouvement.origin_facility_finess == "750000001"
    assert mouvement.origin_stay_date == "20260701"
    assert mouvement.discharge_transport_mode == "3"
    assert mouvement.legal_care_mode_code == "PSYA"
    assert mouvement.transport_care_level == "1"
