"""Régressions des acquittements HPRIM 2.4."""

from datetime import datetime

import pytest

from app.hprim_models import (
    HprimAcquittement,
    HprimEnteteMessage,
    HprimMessageType,
    HprimReponse,
    HprimTypeActe,
)
from app.routers.roundtrip_hprim import _build_message
from app.services.hprim import HprimService


@pytest.mark.parametrize(
    ("act_type", "code"),
    [("LPP", "1234567890123"), ("UCD", "1234567890123")],
)
def test_hprim_acquittement_is_xsd_valid_and_roundtrips(act_type, code):
    message, _ = _build_message({"type_acte": act_type, "code": code, "prix_unitaire": 10})
    message.entete = HprimEnteteMessage(
        emetteur_id=message.entete.emetteur_id,
        emetteur_nom=message.entete.emetteur_nom,
        destinataire_id=message.entete.destinataire_id,
        destinataire_nom=message.entete.destinataire_nom,
        date_emission=datetime.utcnow(),
        message_id="ACK000000001",
        message_type=HprimMessageType.ACQUITTEMENTS_SERVEUR_ACTES,
    )
    message.acquittement = HprimAcquittement(
        statut="OK",
        message_id_original="SRC000000001",
        date_acquittement=datetime.utcnow(),
        reponses_actes=[HprimReponse("ACT00000001", HprimTypeActe(act_type), code, "OK")],
    )

    service = HprimService()
    xml = service.generer_xml(message, valider=False)
    assert service.validate_generated_xml(xml, HprimMessageType.ACQUITTEMENTS_SERVEUR_ACTES) == (True, [])

    parsed = service.xml_service.parse_xml(xml)
    assert parsed.entete.message_type == HprimMessageType.ACQUITTEMENTS_SERVEUR_ACTES
    assert parsed.acquittement.message_id_original == "SRC000000001"
