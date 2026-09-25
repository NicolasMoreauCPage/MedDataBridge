"""Regression checks for the synchronous SQL structure-import endpoints."""

from fastapi.testclient import TestClient
import pytest


def test_structure_import_reads_upload_before_sync_database_work(client: TestClient):
    from app.routers import structure_import_export

    if structure_import_export.Workbook is None:
        pytest.skip("openpyxl is not installed in this minimal test environment")

    response = client.post(
        "/api/structure/import/excel",
        data={"mode": "create"},
        files={"file": ("structure.txt", b"not an excel workbook")},
    )

    assert response.status_code == 400
    assert "Format invalide" in response.json()["detail"]
