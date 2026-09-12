from sqlmodel import select

from app.models_endpoints import MessageLog, SystemEndpoint
from app.models_outbox import OutboundMessage
from app.services.hprim_delivery import queue_hprim_delivery


def test_hprim_delivery_creates_a_source_log_and_a_durable_outbox_row(session, tmp_path):
    endpoint = SystemEndpoint(
        name="Dépôt HPRIM", kind="HPRIM", role="sender", is_enabled=True,
        outbox_path=str(tmp_path), target_system_key="GAM-RECETTE",
    )
    session.add(endpoint)
    session.commit()

    delivery = queue_hprim_delivery(
        session,
        xml_content="<evenementsServeurActes/>",
        message_id="HPRIM-TEST-1",
        message_type="evenementsServeurActes",
        target_system_key="GAM-RECETTE",
    )
    session.commit()

    assert delivery is not None
    assert delivery.endpoint.id == endpoint.id
    assert delivery.outbox.protocol == "FILE"
    assert delivery.outbox.status == "pending"
    log = session.exec(select(MessageLog).where(MessageLog.correlation_id == "HPRIM-TEST-1")).one()
    queued = session.exec(select(OutboundMessage).where(OutboundMessage.id == delivery.outbox.id)).one()
    assert log.status == "pending"
    assert queued.source_message_log_id == log.id


def test_hprim_delivery_requires_an_enabled_sender_when_endpoint_is_explicit(session, tmp_path):
    endpoint = SystemEndpoint(
        name="Endpoint désactivé", kind="FILE", role="sender", is_enabled=False,
        outbox_path=str(tmp_path),
    )
    session.add(endpoint)
    session.commit()

    try:
        queue_hprim_delivery(
            session,
            xml_content="<evenementsServeurActes/>",
            message_id="HPRIM-TEST-2",
            message_type="evenementsServeurActes",
            endpoint_id=endpoint.id,
        )
    except ValueError as exc:
        assert "désactivé" in str(exc)
    else:
        raise AssertionError("Un endpoint désactivé doit être refusé")
