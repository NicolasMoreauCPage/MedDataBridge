import pytest

from app.adapters.filesystem_transport import FileSystemWriter


def test_filesystem_writer_preserves_explicit_filename_and_extension(tmp_path):
    writer = FileSystemWriter(str(tmp_path), extension=".hl7")

    written = writer.write_message("<hprim/>", filename="acte-001.xml")

    assert written == tmp_path / "acte-001.xml"
    assert written.read_text(encoding="utf-8") == "<hprim/>"


def test_filesystem_writer_refuses_a_filename_with_a_directory(tmp_path):
    writer = FileSystemWriter(str(tmp_path))

    with pytest.raises(ValueError, match="sans répertoire"):
        writer.write_message("MSH|^~\\&", filename="../outside.hl7")
