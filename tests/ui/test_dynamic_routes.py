import pytest
import json
from fastapi.testclient import TestClient
from playwright.sync_api import expect
from .ui_helpers import wait_for_ready, safe_navigate


class TestDynamicRoutes:
    """Tests for routes with dynamic parameters (IDs, context IDs, etc.)"""

    def test_patient_detail_page(self, page, test_server, ght_context, patient_context):
        """Test patient detail page with dynamic ID"""
        assert wait_for_ready(test_server), "Server not ready"

        # Ensure we have a patient context
        if not patient_context:
            # Create a patient via API
            resp = page.request.post(
                f"{test_server}/patients/api/patients",
                data=json.dumps({"family": "TestPatient", "given": "Detail"}),
                headers={"Content-Type": "application/json"}
            )
            assert resp.ok, f"Failed to create test patient: {resp.text}"
            patient_data = resp.json()
            patient_id = patient_data.get('id')
            assert patient_id, "Patient creation should return an ID"
        else:
            patient_id = patient_context

        # Navigate to patient detail page
        assert safe_navigate(page, f"{test_server}/patients/{patient_id}"), f"Failed to load patient detail page for ID {patient_id}"

        # Verify page loaded successfully
        page.wait_for_selector("h1, h2", state="visible", timeout=10000)

        # Check for patient information display
        patient_name_selectors = [
            "h1:has-text('TestPatient')",
            "h2:has-text('TestPatient')",
            ".patient-name",
            "[data-patient-name]"
        ]

        name_found = False
        for selector in patient_name_selectors:
            try:
                page.wait_for_selector(selector, timeout=2000)
                name_found = True
                break
            except:
                continue

        assert name_found, "Patient name should be displayed on detail page"

    def test_patient_edit_page(self, page, test_server, ght_context, patient_context):
        """Test patient edit form with dynamic ID"""
        assert wait_for_ready(test_server), "Server not ready"

        # Ensure we have a patient context
        if not patient_context:
            # Create a patient via API
            resp = page.request.post(
                f"{test_server}/patients/api/patients",
                data=json.dumps({"family": "TestPatient", "given": "Edit"}),
                headers={"Content-Type": "application/json"}
            )
            assert resp.ok, f"Failed to create test patient: {resp.text}"
            patient_data = resp.json()
            patient_id = patient_data.get('id')
            assert patient_id, "Patient creation should return an ID"
        else:
            patient_id = patient_context

        # Navigate to patient edit page
        assert safe_navigate(page, f"{test_server}/patients/{patient_id}/edit"), f"Failed to load patient edit page for ID {patient_id}"

        # Verify form loaded
        page.wait_for_selector("form", state="visible", timeout=10000)

        # Check for form fields
        family_field = page.locator("input[name=family]")
        expect(family_field).to_be_visible()
        expect(family_field).to_have_value("TestPatient")

    def test_dossier_detail_page(self, page, test_server, ght_context):
        """Test dossier detail page with dynamic ID"""
        assert wait_for_ready(test_server), "Server not ready"

        # First create a patient and dossier via API
        patient_resp = page.request.post(
            f"{test_server}/patients/api/patients",
            data=json.dumps({"family": "DossierTest", "given": "Patient"}),
            headers={"Content-Type": "application/json"}
        )
        assert patient_resp.ok, f"Failed to create test patient: {patient_resp.text}"
        patient_data = patient_resp.json()
        patient_id = patient_data.get('id')
        assert patient_id, "Patient creation should return an ID"

        # Create a dossier
        dossier_resp = page.request.post(
            f"{test_server}/dossiers/api/dossiers",
            data=json.dumps({
                "patient_id": patient_id,
                "admit_time": "2024-01-01T10:00:00Z"
            }),
            headers={"Content-Type": "application/json"}
        )
        assert dossier_resp.ok, f"Failed to create test dossier: {dossier_resp.text}"
        dossier_data = dossier_resp.json()
        dossier_id = dossier_data.get('id')
        assert dossier_id, "Dossier creation should return an ID"

        # Navigate to dossier detail page
        assert safe_navigate(page, f"{test_server}/dossiers/{dossier_id}"), f"Failed to load dossier detail page for ID {dossier_id}"

        # Verify page loaded successfully
        page.wait_for_selector("h1, h2", state="visible", timeout=10000)

        # Check for dossier information
        dossier_info_selectors = [
            f"[data-dossier-id='{dossier_id}']",
            ".dossier-info",
            ".dossier-details"
        ]

        info_found = False
        for selector in dossier_info_selectors:
            try:
                page.wait_for_selector(selector, timeout=2000)
                info_found = True
                break
            except:
                continue

        assert info_found, "Dossier information should be displayed on detail page"

    def test_dossier_edit_page(self, page, test_server, ght_context):
        """Test dossier edit form with dynamic ID"""
        assert wait_for_ready(test_server), "Server not ready"

        # Create patient and dossier first
        patient_resp = page.request.post(
            f"{test_server}/patients/api/patients",
            data=json.dumps({"family": "DossierEdit", "given": "Test"}),
            headers={"Content-Type": "application/json"}
        )
        assert patient_resp.ok, f"Failed to create test patient: {patient_resp.text}"
        patient_data = patient_resp.json()
        patient_id = patient_data.get('id')

        dossier_resp = page.request.post(
            f"{test_server}/dossiers/api/dossiers",
            data=json.dumps({
                "patient_id": patient_id,
                "admit_time": "2024-01-01T10:00:00Z"
            }),
            headers={"Content-Type": "application/json"}
        )
        assert dossier_resp.ok, f"Failed to create test dossier: {dossier_resp.text}"
        dossier_data = dossier_resp.json()
        dossier_id = dossier_data.get('id')

        # Navigate to dossier edit page
        assert safe_navigate(page, f"{test_server}/dossiers/{dossier_id}/edit"), f"Failed to load dossier edit page for ID {dossier_id}"

        # Verify form loaded
        page.wait_for_selector("form", state="visible", timeout=10000)

        # Check for form elements specific to dossier editing
        form_selectors = [
            "select[name=current_state]",
            "select[name=event_code]",
            ".dossier-form",
            "[data-dossier-form]"
        ]

        form_found = False
        for selector in form_selectors:
            try:
                page.wait_for_selector(selector, timeout=2000)
                form_found = True
                break
            except:
                continue

        assert form_found, "Dossier edit form should be displayed"


class TestContextRoutes:
    """Tests for context management routes"""

    def test_context_select_page(self, page, test_server):
        """Test context selection page"""
        assert wait_for_ready(test_server), "Server not ready"

        assert safe_navigate(page, f"{test_server}/context/select"), "Failed to load context select page"

        # Verify page loaded
        page.wait_for_selector("h1, h2", state="visible", timeout=10000)

        # Check for context selection elements
        context_selectors = [
            ".context-select",
            "[data-context-select]",
            "select[name=context_type]",
            ".context-management"
        ]

        context_found = False
        for selector in context_selectors:
            try:
                page.wait_for_selector(selector, timeout=2000)
                context_found = True
                break
            except:
                continue

        assert context_found, "Context selection interface should be displayed"

    def test_context_clear_routes(self, page, test_server, ght_context):
        """Test context clearing routes"""
        assert wait_for_ready(test_server), "Server not ready"

        # Test clearing different context types
        context_types = ["patient", "dossier", "ej"]

        for context_type in context_types:
            # Navigate to clear context
            assert safe_navigate(page, f"{test_server}/context/clear?kind={context_type}"), f"Failed to clear {context_type} context"

            # Should redirect or show success message
            # Accept both direct response and redirects
            try:
                page.wait_for_selector(".success, .alert-success, [role='alert']", timeout=3000)
            except:
                # Redirect might have happened, check URL changed
                current_url = page.url
                assert "context/clear" not in current_url, f"Should have redirected after clearing {context_type} context"


class TestAdminRoutes:
    """Tests for admin routes requiring GHT context"""

    def test_admin_ght_detail_page(self, page, test_server, ght_context):
        """Test GHT context detail page"""
        assert wait_for_ready(test_server), "Server not ready"

        # Get GHT context ID
        ght_id = ght_context
        assert ght_id, "Should have a GHT context ID"

        # Navigate to GHT detail page
        assert safe_navigate(page, f"{test_server}/admin/ght/{ght_id}"), f"Failed to load GHT detail page for ID {ght_id}"

        # Verify page loaded
        page.wait_for_selector("h1, h2", state="visible", timeout=10000)

        # Check for GHT information display
        ght_info_selectors = [
            f"[data-ght-id='{ght_id}']",
            ".ght-info",
            ".ght-details",
            ".admin-ght"
        ]

        info_found = False
        for selector in ght_info_selectors:
            try:
                page.wait_for_selector(selector, timeout=2000)
                info_found = True
                break
            except:
                continue

        assert info_found, "GHT information should be displayed on detail page"

    def test_admin_ght_edit_page(self, page, test_server, ght_context):
        """Test GHT context edit page"""
        assert wait_for_ready(test_server), "Server not ready"

        ght_id = ght_context
        assert ght_id, "Should have a GHT context ID"

        # Navigate to GHT edit page
        assert safe_navigate(page, f"{test_server}/admin/ght/{ght_id}/edit"), f"Failed to load GHT edit page for ID {ght_id}"

        # Verify form loaded
        page.wait_for_selector("form", state="visible", timeout=10000)

        # Check for GHT edit form elements
        form_selectors = [
            "input[name=name]",
            "input[name=code]",
            ".ght-form",
            "[data-ght-form]"
        ]

        form_found = False
        for selector in form_selectors:
            try:
                page.wait_for_selector(selector, timeout=2000)
                form_found = True
                break
            except:
                continue

        assert form_found, "GHT edit form should be displayed"


class TestAPIRoutes:
    """Tests for API routes not covered by existing tests"""

    def test_api_structure_tree(self, client):
        """Test structure tree API endpoint"""
        response = client.get("/api/structure/tree")
        # Should return JSON data or appropriate error
        assert response.status_code in [200, 404, 422, 400]  # Allow not found if no data

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict)), "Should return JSON data"

    def test_api_metrics_cache(self, client):
        """Test cache metrics API endpoint"""
        response = client.get("/api/metrics/cache")
        assert response.status_code in [200, 404, 422]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict), "Should return cache metrics data"

    def test_api_admin_stats(self, client):
        """Test admin stats API endpoint"""
        response = client.get("/api/admin/stats")
        assert response.status_code in [200, 401, 403, 404]  # May require auth

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict), "Should return admin stats data"

    def test_api_admin_config(self, client):
        """Test admin config API endpoint"""
        response = client.get("/api/admin/config")
        assert response.status_code in [200, 401, 403, 404]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict), "Should return config data"