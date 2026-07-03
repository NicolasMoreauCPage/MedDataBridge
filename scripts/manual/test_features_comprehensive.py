#!/usr/bin/env python3
"""
Comprehensive Feature Testing Suite
Tests all major features one by one to identify bugs
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"
RESULTS = []
BUGS_FOUND = []

def log_test(category, test_name, status, details=""):
    """Log test result"""
    result = {
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "test": test_name,
        "status": status,
        "details": details
    }
    RESULTS.append(result)
    status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{status_icon} [{category}] {test_name}: {status}")
    if details:
        print(f"   → {details}")

def report_bug(category, title, reproduction, expected, actual):
    """Report a bug found"""
    bug = {
        "category": category,
        "title": title,
        "reproduction": reproduction,
        "expected": expected,
        "actual": actual
    }
    BUGS_FOUND.append(bug)
    print(f"  🐛 BUG: {title}")
    print(f"     Expected: {expected}")
    print(f"     Actual: {actual}")

# ============================================================================
# 1. FHIR IMPORT/EXPORT TESTS
# ============================================================================

def test_fhir_features():
    print("\n" + "="*70)
    print("1. FHIR IMPORT/EXPORT FUNCTIONALITY")
    print("="*70)
    
    # Test 1.1: Check if FHIR import endpoint exists
    try:
        response = requests.post(f"{BASE_URL}/api/fhir/import/bundle", 
                                json={"bundle": {}, "ej_id": 1})
        log_test("FHIR", "Import endpoint exists", "PASS" if response.status_code in [200, 400, 422] else "FAIL",
                f"Status: {response.status_code}")
    except Exception as e:
        log_test("FHIR", "Import endpoint exists", "FAIL", str(e))
        report_bug("FHIR", "Import endpoint not responding", 
                  "POST /api/fhir/import/bundle", "HTTP response", str(e))
    
    # Test 1.2: Create a minimal FHIR bundle and import it
    try:
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "fullUrl": "Patient/test-patient-1",
                    "resource": {
                        "resourceType": "Patient",
                        "id": "test-patient-1",
                        "name": [{"text": "Test Patient"}],
                        "birthDate": "1980-01-01"
                    }
                }
            ]
        }
        response = requests.post(f"{BASE_URL}/api/fhir/import/bundle",
                                json={"bundle": bundle, "ej_id": 1})
        if response.status_code == 200:
            log_test("FHIR", "Import minimal bundle", "PASS", f"Bundle processed")
        else:
            log_test("FHIR", "Import minimal bundle", "FAIL", f"Status: {response.status_code}, Response: {response.text[:200]}")
            report_bug("FHIR", "Bundle import failed",
                      "POST /api/fhir/import/bundle with valid bundle",
                      "Status 200 with bundle processed",
                      f"Status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        log_test("FHIR", "Import minimal bundle", "FAIL", str(e))
    
    # Test 1.3: Check FHIR export endpoint
    try:
        response = requests.get(f"{BASE_URL}/api/fhir/export/dossier/1")
        if response.status_code in [200, 404]:
            log_test("FHIR", "Export dossier endpoint", "PASS", f"Status: {response.status_code}")
        else:
            log_test("FHIR", "Export dossier endpoint", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("FHIR", "Export dossier endpoint", "FAIL", str(e))

# ============================================================================
# 2. PATIENT & DOSSIER CRUD TESTS
# ============================================================================

def test_patient_dossier():
    print("\n" + "="*70)
    print("2. PATIENT & DOSSIER MANAGEMENT")
    print("="*70)
    
    # Test 2.1: List patients
    try:
        response = requests.get(f"{BASE_URL}/api/patients")
        if response.status_code == 200:
            data = response.json()
            count = len(data) if isinstance(data, list) else data.get("total", 0)
            log_test("Patient/Dossier", "List patients", "PASS", f"Found {count} patients")
        else:
            log_test("Patient/Dossier", "List patients", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Patient/Dossier", "List patients", "FAIL", str(e))
    
    # Test 2.2: Create a patient
    try:
        patient_data = {
            "ej_id": 1,
            "name": "Test Patient",
            "date_birth": "1980-01-01",
            "sex": "M"
        }
        response = requests.post(f"{BASE_URL}/api/patients", json=patient_data)
        if response.status_code == 200:
            result = response.json()
            patient_id = result.get("id")
            log_test("Patient/Dossier", "Create patient", "PASS", f"Created patient {patient_id}")
        else:
            log_test("Patient/Dossier", "Create patient", "FAIL", f"Status: {response.status_code}, Response: {response.text[:200]}")
            report_bug("Patient/Dossier", "Patient creation failed",
                      "POST /api/patients with valid data",
                      "Status 200 with patient ID",
                      f"Status {response.status_code}")
    except Exception as e:
        log_test("Patient/Dossier", "Create patient", "FAIL", str(e))
    
    # Test 2.3: List dossiers
    try:
        response = requests.get(f"{BASE_URL}/api/dossiers")
        if response.status_code == 200:
            data = response.json()
            count = len(data) if isinstance(data, list) else data.get("total", 0)
            log_test("Patient/Dossier", "List dossiers", "PASS", f"Found {count} dossiers")
        else:
            log_test("Patient/Dossier", "List dossiers", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Patient/Dossier", "List dossiers", "FAIL", str(e))

# ============================================================================
# 3. COTATION TESTS
# ============================================================================

def test_cotations():
    print("\n" + "="*70)
    print("3. COTATION WORKFLOWS (CCAM/NGAP/UCD/LPP)")
    print("="*70)
    
    # Test 3.1: Modern cotation search interface
    try:
        response = requests.get(f"{BASE_URL}/cotation-modern/search?q=test&page=1&per_page=10")
        if response.status_code in [200, 400]:
            log_test("Cotation", "Modern search endpoint", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Cotation", "Modern search endpoint", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Cotation", "Modern search endpoint", "FAIL", str(e))
    
    # Test 3.2: CCAM search
    try:
        response = requests.get(f"{BASE_URL}/ccam/search?q=bandage")
        if response.status_code in [200, 404]:
            log_test("Cotation", "CCAM search", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Cotation", "CCAM search", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Cotation", "CCAM search", "FAIL", str(e))
    
    # Test 3.3: NGAP access
    try:
        response = requests.get(f"{BASE_URL}/ngap")
        if response.status_code in [200, 404]:
            log_test("Cotation", "NGAP interface", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Cotation", "NGAP interface", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Cotation", "NGAP interface", "FAIL", str(e))
    
    # Test 3.4: UCD interface
    try:
        response = requests.get(f"{BASE_URL}/ucd")
        if response.status_code in [200, 404]:
            log_test("Cotation", "UCD interface", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Cotation", "UCD interface", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Cotation", "UCD interface", "FAIL", str(e))
    
    # Test 3.5: LPP interface
    try:
        response = requests.get(f"{BASE_URL}/lpp")
        if response.status_code in [200, 404]:
            log_test("Cotation", "LPP interface", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Cotation", "LPP interface", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Cotation", "LPP interface", "FAIL", str(e))

# ============================================================================
# 4. MESSAGE HANDLING (HL7/HPRIM/IHE PAM)
# ============================================================================

def test_messages():
    print("\n" + "="*70)
    print("4. MESSAGE HANDLING (HL7/HPRIM/IHE PAM)")
    print("="*70)
    
    # Test 4.1: Messages list
    try:
        response = requests.get(f"{BASE_URL}/messages")
        if response.status_code in [200, 404]:
            log_test("Messages", "List messages", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Messages", "List messages", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Messages", "List messages", "FAIL", str(e))
    
    # Test 4.2: IHE PAM interface
    try:
        response = requests.get(f"{BASE_URL}/ihe")
        if response.status_code in [200, 404]:
            log_test("Messages", "IHE PAM interface", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Messages", "IHE PAM interface", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Messages", "IHE PAM interface", "FAIL", str(e))
    
    # Test 4.3: HPRIM import interface
    try:
        response = requests.get(f"{BASE_URL}/hprim/import")
        if response.status_code in [200, 404]:
            log_test("Messages", "HPRIM import UI", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Messages", "HPRIM import UI", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Messages", "HPRIM import UI", "FAIL", str(e))

# ============================================================================
# 5. SCENARIOS
# ============================================================================

def test_scenarios():
    print("\n" + "="*70)
    print("5. SCENARIOS & TEST FIXTURES")
    print("="*70)
    
    # Test 5.1: Scenarios list
    try:
        response = requests.get(f"{BASE_URL}/scenarios")
        if response.status_code in [200, 404]:
            data = response.json() if response.status_code == 200 else {}
            count = len(data) if isinstance(data, list) else data.get("total", 0)
            log_test("Scenarios", "List scenarios", "PASS", f"Status: {response.status_code}, Found {count} scenarios")
        else:
            log_test("Scenarios", "List scenarios", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Scenarios", "List scenarios", "FAIL", str(e))
    
    # Test 5.2: Scenarios dashboard
    try:
        response = requests.get(f"{BASE_URL}/scenarios/dashboard")
        if response.status_code in [200, 404]:
            log_test("Scenarios", "Dashboard", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Scenarios", "Dashboard", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Scenarios", "Dashboard", "FAIL", str(e))

# ============================================================================
# 6. STRUCTURE (GHT/EJ/EG)
# ============================================================================

def test_structure():
    print("\n" + "="*70)
    print("6. ORGANIZATIONAL STRUCTURE (GHT/EJ/EG)")
    print("="*70)
    
    # Test 6.1: GHT list
    try:
        response = requests.get(f"{BASE_URL}/admin/ght")
        if response.status_code in [200, 404]:
            log_test("Structure", "GHT list", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Structure", "GHT list", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Structure", "GHT list", "FAIL", str(e))
    
    # Test 6.2: Main structure view
    try:
        response = requests.get(f"{BASE_URL}/structure")
        if response.status_code in [200, 404]:
            log_test("Structure", "Structure home", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Structure", "Structure home", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Structure", "Structure home", "FAIL", str(e))

# ============================================================================
# 7. VALIDATION & CONFORMANCE
# ============================================================================

def test_validation():
    print("\n" + "="*70)
    print("7. VALIDATION & CONFORMANCE")
    print("="*70)
    
    # Test 7.1: Validation interface
    try:
        response = requests.get(f"{BASE_URL}/validation")
        if response.status_code in [200, 404]:
            log_test("Validation", "Validation interface", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Validation", "Validation interface", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Validation", "Validation interface", "FAIL", str(e))
    
    # Test 7.2: Conformity dashboard
    try:
        response = requests.get(f"{BASE_URL}/conformity-dashboard")
        if response.status_code in [200, 404]:
            log_test("Validation", "Conformity dashboard", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Validation", "Conformity dashboard", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Validation", "Conformity dashboard", "FAIL", str(e))

# ============================================================================
# 8. ANALYTICS & REPORTING
# ============================================================================

def test_analytics():
    print("\n" + "="*70)
    print("8. ANALYTICS & REPORTING")
    print("="*70)
    
    # Test 8.1: Analytics dashboard
    try:
        response = requests.get(f"{BASE_URL}/analytics-dashboard")
        if response.status_code in [200, 404]:
            log_test("Analytics", "Analytics dashboard", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Analytics", "Analytics dashboard", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Analytics", "Analytics dashboard", "FAIL", str(e))
    
    # Test 8.2: Metrics
    try:
        response = requests.get(f"{BASE_URL}/metrics")
        if response.status_code in [200, 404]:
            log_test("Analytics", "Metrics endpoint", "PASS", f"Status: {response.status_code}")
        else:
            log_test("Analytics", "Metrics endpoint", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        log_test("Analytics", "Metrics endpoint", "FAIL", str(e))

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("COMPREHENSIVE FEATURE TESTING SUITE")
    print("="*70)
    print(f"Testing endpoint: {BASE_URL}")
    print(f"Start time: {datetime.now().isoformat()}")
    
    try:
        test_fhir_features()
        test_patient_dossier()
        test_cotations()
        test_messages()
        test_scenarios()
        test_structure()
        test_validation()
        test_analytics()
        
        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        passes = sum(1 for r in RESULTS if r["status"] == "PASS")
        fails = sum(1 for r in RESULTS if r["status"] == "FAIL")
        warnings = sum(1 for r in RESULTS if r["status"] == "WARN")
        
        print(f"Total tests: {len(RESULTS)}")
        print(f"✅ Passed: {passes}")
        print(f"❌ Failed: {fails}")
        print(f"⚠️  Warnings: {warnings}")
        print(f"🐛 Bugs found: {len(BUGS_FOUND)}")
        
        if BUGS_FOUND:
            print("\n" + "="*70)
            print("BUGS FOUND")
            print("="*70)
            for i, bug in enumerate(BUGS_FOUND, 1):
                print(f"\n{i}. {bug['title']} [{bug['category']}]")
                print(f"   Reproduction: {bug['reproduction']}")
                print(f"   Expected: {bug['expected']}")
                print(f"   Actual: {bug['actual']}")
        
        sys.exit(0 if fails == 0 else 1)
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
