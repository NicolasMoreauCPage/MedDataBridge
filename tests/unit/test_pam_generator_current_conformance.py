"""
Verifies the CURRENT adapters.hl7_pam_fr.build_message_for_movement no longer
reproduces the historical MSH-9 doubling bug (ADT^ADT^A28 instead of ADT^A28)
that produced the stale fixtures under data/pam/ADT_*.hl7.
"""
from datetime import datetime, timezone

import pytest

from adapters.hl7_pam_fr import build_message_for_movement


class _Fake:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.mark.parametrize("trigger", ["A01", "A02", "A03", "A04", "A05", "A06", "A13", "A28", "A31"])
def test_msh9_has_exactly_two_components(trigger):
    patient = _Fake(identifier="IPP1", family="DOE", given="JOHN", birth_date="1980-01-01", gender="M")
    dossier = _Fake(uf_responsabilite="UF1")
    venue = _Fake(code="W1", uf_responsabilite="UF1")
    movement = _Fake(when=datetime.now(timezone.utc), mouvement_seq=1, location="W1", type=f"ADT^{trigger}")

    msg = build_message_for_movement(dossier=dossier, venue=venue, movement=movement, patient=patient)
    msh = msg.split("\r")[0]
    msh9 = msh.split("|")[8]
    assert msh9 == f"ADT^{trigger}", f"MSH-9 malformed for trigger {trigger}: {msh9}"
