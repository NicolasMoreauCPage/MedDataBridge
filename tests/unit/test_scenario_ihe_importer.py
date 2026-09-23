import logging
from pathlib import Path

from app.services.scenario_ihe_importer import _scan_hl7_files


def test_ihe_scenario_scan_logs_an_unreadable_archive(monkeypatch, tmp_path, caplog):
    source = tmp_path / "unreadable.hl7"
    source.write_text("MSH|^~\\&|A|B|C|D|20260923120000||ADT^A01^ADT_A01|1|P|2.5", encoding="utf-8")
    original_read_text = Path.read_text

    def unreadable(self, *_args, **_kwargs):
        if self == source:
            raise OSError("archive unavailable")
        return original_read_text(self, *_args, **_kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable)

    with caplog.at_level(logging.WARNING):
        assert _scan_hl7_files(tmp_path) == []

    assert "Unable to scan IHE scenario source" in caplog.text
