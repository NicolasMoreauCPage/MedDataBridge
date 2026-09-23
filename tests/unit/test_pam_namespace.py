from app.services.pam_namespace import resolve_namespace_authority


class _NoQuerySession:
    def exec(self, statement):  # pragma: no cover - the fallback must not query
        raise AssertionError("Aucun namespace ne doit être recherché sans EJ")


def test_namespace_authority_uses_forced_endpoint_values_as_fallback():
    authority, namespace_type = resolve_namespace_authority(
        _NoQuerySession(),
        entite_juridique_id=None,
        namespace_type="VN",
        forced_system="PARTNER",
        forced_oid="1.2.250.1",
    )

    assert authority == "PARTNER&1.2.250.1&ISO"
    assert namespace_type == "VN"


def test_namespace_authority_defaults_to_hospital_when_no_value_is_forced():
    authority, namespace_type = resolve_namespace_authority(
        _NoQuerySession(), entite_juridique_id=None, namespace_type="MVT"
    )

    assert authority == "HOSP"
    assert namespace_type == "MVT"
