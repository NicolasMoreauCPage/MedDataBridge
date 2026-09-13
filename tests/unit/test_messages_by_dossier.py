from datetime import datetime

from app.models_shared import MessageLog
from app.routers.messages import _extract_ipp_and_dossier, list_by_dossier, list_messages


class _TemplatesCapture:
    def TemplateResponse(self, request, template_name, context):
        assert template_name in {"messages_by_dossier.html", "messages.html"}
        return context


class _Request:
    class _State:
        templates = _TemplatesCapture()

    app = type("App", (), {"state": _State()})()


def _hl7_message(ipp: str, *, account_number: str = "", visit_number: str = "") -> str:
    pid_fields = ["PID", "1", "", f"{ipp}^^^^PI"] + [""] * 15
    pid_fields[18] = account_number
    pv1_fields = ["PV1"] + [""] * 19
    pv1_fields[19] = visit_number
    return "\r".join([
        "MSH|^~\\&|SOURCE|FAC|TARGET|FAC|20260912120000||ADT^A01|CTRL|P|2.5",
        "|".join(pid_fields),
        "|".join(pv1_fields),
    ])


def test_extract_dossier_uses_pid18_when_pv119_is_absent():
    ipp, dossier = _extract_ipp_and_dossier(
        _hl7_message("IPP-1", account_number="NDA-1")
    )

    assert ipp == "IPP-1"
    assert dossier == "NDA-1"


def test_by_dossier_keeps_messages_without_nda_and_filters_global_status(isolated_session):
    isolated_session.add_all([
        MessageLog(
            direction="in",
            kind="MLLP",
            status="processed",
            message_type="ADT^A28",
            payload=_hl7_message("IPP-OK"),
            created_at=datetime(2026, 9, 12, 10, 0),
        ),
        MessageLog(
            direction="in",
            kind="MLLP",
            status="error",
            message_type="ADT^A01",
            payload=_hl7_message("IPP-ERROR", visit_number="NDA-ERROR"),
            created_at=datetime(2026, 9, 12, 11, 0),
        ),
    ])
    isolated_session.commit()

    all_context = list_by_dossier(
        _Request(),
        isolated_session,
        endpoint_id=None,
        date_start=None,
        date_end=None,
        direction=None,
        dossier_status=None,
        limit=10000,
    )
    assert len(all_context["dossiers"]) == 2
    assert {item["global_status"] for item in all_context["dossiers"]} == {"ok", "error"}
    assert any(
        item["ipp"] == "IPP-OK" and not item["has_dossier_number"]
        for item in all_context["dossiers"]
    )

    error_context = list_by_dossier(
        _Request(),
        isolated_session,
        endpoint_id=None,
        date_start=None,
        date_end=None,
        direction=None,
        dossier_status="error",
        limit=10000,
    )
    assert len(error_context["dossiers"]) == 1
    assert error_context["dossiers"][0]["dossier_number"] == "NDA-ERROR"
    assert error_context["filters"]["dossier_status"] == "error"


def test_by_dossier_paginates_complete_dossiers_after_aggregation(isolated_session):
    isolated_session.add_all([
        MessageLog(
            direction="in",
            kind="MLLP",
            status="processed",
            message_type="ADT^A01",
            payload=_hl7_message(f"IPP-{index}", visit_number=f"NDA-{index}"),
            created_at=datetime(2026, 9, 12, 12, 0),
        )
        for index in range(26)
    ])
    isolated_session.commit()

    context = list_by_dossier(
        _Request(),
        isolated_session,
        endpoint_id=None,
        date_start=None,
        date_end=None,
        direction=None,
        dossier_status=None,
        limit=10000,
        page=2,
        page_size=25,
    )

    assert len(context["dossiers"]) == 1
    assert context["dossier_summary"] == {"total": 26, "ok": 26, "warning": 0, "error": 0}
    assert context["pagination"]["page"] == 2
    assert context["pagination"]["total_pages"] == 2


def test_messages_filters_an_exact_status_and_groups_negative_ack_statuses(isolated_session):
    isolated_session.add_all([
        MessageLog(direction="out", kind="MLLP", status="sent", payload="MSH|^~\\&|A|B"),
        MessageLog(direction="out", kind="MLLP", status="ack_error", payload="MSH|^~\\&|A|B"),
    ])
    isolated_session.commit()

    sent_context = list_messages(
        _Request(), isolated_session, endpoint_id=None, date_start=None,
        date_end=None, neg_ack_only=False, status="sent", kind=None,
        direction=None, limit=100,
    )
    assert [message.status for message in sent_context["messages"]] == ["sent"]
    assert sent_context["filters"]["status"] == "sent"

    errors_context = list_messages(
        _Request(), isolated_session, endpoint_id=None, date_start=None,
        date_end=None, neg_ack_only=False, status="error", kind=None,
        direction=None, limit=100,
    )
    assert [message.status for message in errors_context["messages"]] == ["ack_error"]
