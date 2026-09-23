from app.services.pam_emission import dump_outbound_pam_payload


def test_outbound_pam_payload_dump_is_atomic_and_skips_generated_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDBRIDGE_OUT_DIR", str(tmp_path))

    dump_outbound_pam_payload("MSH|^~\\&|SOURCE", 42)
    dumped = list((tmp_path / "pam").glob("mllp_42_*.hl7"))

    assert len(dumped) == 1
    assert dumped[0].read_text(encoding="utf-8") == "MSH|^~\\&|SOURCE"
    dump_outbound_pam_payload("[Emission error: missing]", 42)
    assert len(list((tmp_path / "pam").glob("*.hl7"))) == 1
