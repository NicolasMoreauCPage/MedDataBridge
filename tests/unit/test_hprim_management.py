"""Régressions de pagination de l'historique HPRIM."""

from datetime import datetime, timedelta

from app.models.hprim_models import HprimMessage


def test_hprim_history_is_paginated_and_keeps_its_filters(client, session):
    created_at = datetime(2026, 9, 23, 10, 0, 0)
    session.add_all(
        [
            HprimMessage(
                message_id=f"HPRIM-PAGE-{index}",
                type_message="test",
                direction="outbound",
                status="stored",
                patient_id="HPRIM-PAGINATION",
                created_at=created_at + timedelta(minutes=index),
            )
            for index in range(3)
        ]
    )
    session.commit()

    response = client.get(
        "/hprim/messages",
        params={"patient_id": "HPRIM-PAGINATION", "offset": 1, "limit": 1},
    )

    assert response.status_code == 200
    assert "HPRIM-PAGE-1" in response.text
    assert "HPRIM-PAGE-0" not in response.text
    assert "HPRIM-PAGE-2" not in response.text
    assert "Messages 2 à 2 sur 3" in response.text
    assert "patient_id=HPRIM-PAGINATION&amp;offset=2&amp;limit=1" in response.text
