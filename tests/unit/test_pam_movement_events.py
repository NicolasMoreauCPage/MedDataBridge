from types import SimpleNamespace

from app.services.pam_movement_events import detect_nature_transition, select_movement_event


class _NoQuerySession:
    def exec(self, statement):  # pragma: no cover - guard for ineligible cases
        raise AssertionError("Aucun historique ne doit être lu hors création PAM")


def test_transition_detection_skips_updates_without_querying_history():
    mouvement = SimpleNamespace(venue_id=7, nature="H")

    assert detect_nature_transition(_NoQuerySession(), mouvement, "update") == (None, None)


def test_event_selection_prioritizes_explicit_and_cancellation_triggers():
    explicit = SimpleNamespace(trigger_event="A02", venue_id=None, nature=None)
    cancelled = SimpleNamespace(
        trigger_event=None, venue_id=None, nature=None, movement_type=None,
        action="CANCEL", original_trigger="A03",
    )

    assert select_movement_event(_NoQuerySession(), explicit, "insert") == "A02"
    assert select_movement_event(_NoQuerySession(), cancelled, "insert") == "A13"
