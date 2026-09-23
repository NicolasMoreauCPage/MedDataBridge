from types import SimpleNamespace

from app.services.pam_movement_context import load_movement_context


class _NoQuerySession:
    def exec(self, statement):  # pragma: no cover - relations are already materialized
        raise AssertionError("Le contexte préchargé ne doit pas requêter la base")


def test_movement_context_reuses_materialized_relationships():
    patient = SimpleNamespace(id=3)
    dossier = SimpleNamespace(id=2, patient=patient)
    venue = SimpleNamespace(id=1, dossier=dossier)
    mouvement = SimpleNamespace(venue=venue)

    assert load_movement_context(_NoQuerySession(), mouvement) == (venue, dossier, patient)
