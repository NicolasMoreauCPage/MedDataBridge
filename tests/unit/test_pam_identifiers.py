from app.services.pam_identifiers import build_pid3_identifiers


class _NoQuerySession:
    def exec(self, statement):  # pragma: no cover - snapshot path must not query
        raise AssertionError("Les identifiants déjà matérialisés ne doivent pas être rechargés")


def test_pid3_snapshot_keeps_internal_identifier_before_other_active_identifiers():
    pid3 = build_pid3_identifiers(
        {
            "id": None,
            "patient_seq": 42,
            "identifiers": [
                {"value": "EXT-7", "system": "PARTNER", "oid": "1.2.3", "status": "active", "type": "PI"}
            ],
        },
        _NoQuerySession(),
        forced_system="LOCAL",
        forced_oid="9.8.7",
    )

    assert pid3.split("~") == [
        "42^^^LOCAL&9.8.7&ISO^PI",
        "EXT-7^^^PARTNER&1.2.3&ISO^PI",
    ]
