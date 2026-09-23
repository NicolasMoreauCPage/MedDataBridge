from types import SimpleNamespace

from app.services.emission_snapshot import snapshot_entity


class _UnusedSession:
    def exec(self, statement):  # pragma: no cover - regression guard only
        raise AssertionError("Les identifiants déjà matérialisés ne doivent pas requêter la base")


def test_patient_snapshot_materializes_scalar_fields_and_identifiers():
    patient = SimpleNamespace(
        id=42,
        patient_seq=12,
        family="Durand",
        given="Alice",
        gender="female",
        birth_date="1980-01-02",
        external_id="EXT-42",
        nir=None,
        entite_juridique_id=7,
        identifiers=[
            SimpleNamespace(value="IPP-42", system="HOSP", oid="1.2.3", status="active", type="IPP")
        ],
    )

    snapshot = snapshot_entity(patient, "patient", _UnusedSession())

    assert snapshot["id"] == 42
    assert snapshot["family"] == "Durand"
    assert snapshot["identifiers"] == [
        {"value": "IPP-42", "system": "HOSP", "oid": "1.2.3", "status": "active", "type": "IPP"}
    ]


def test_mouvement_snapshot_keeps_only_generator_fields():
    mouvement = SimpleNamespace(
        id=9,
        mouvement_seq=21,
        venue_id=4,
        when="2026-09-23T10:00:00",
        type="transfer",
        trigger_event="A02",
        uf_responsabilite="UF-1",
        location="B-02",
        transient="not exported",
    )

    snapshot = snapshot_entity(mouvement, "mouvement", _UnusedSession())

    assert snapshot == {
        "id": 9,
        "mouvement_seq": 21,
        "venue_id": 4,
        "when": "2026-09-23T10:00:00",
        "type": "transfer",
        "trigger_event": "A02",
        "uf_responsabilite": "UF-1",
        "location": "B-02",
    }
