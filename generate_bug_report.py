#!/usr/bin/env python3
"""
Comprehensive Bug Report Generator
Tests all features and creates detailed bug documentation
"""

import requests
import json
import sys
from datetime import datetime
from typing import List, Dict

BASE_URL = "http://localhost:8000"
BUGS: List[Dict] = []

def report_bug(category: str, endpoint: str, method: str, title: str, 
               expected: str, actual: str, steps_to_reproduce: str, 
               severity: str = "HIGH"):
    """Record a bug"""
    bug = {
        "id": len(BUGS) + 1,
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "endpoint": endpoint,
        "method": method,
        "title": title,
        "severity": severity,
        "steps_to_reproduce": steps_to_reproduce,
        "expected": expected,
        "actual": actual
    }
    BUGS.append(bug)
    print(f"\n🐛 BUG #{bug['id']} [{severity}] {title}")
    print(f"   Category: {category}")
    print(f"   Endpoint: {method} {endpoint}")
    print(f"   Reproduction: {steps_to_reproduce}")
    print(f"   Expected: {expected}")
    print(f"   Actual: {actual}")

print("\n" + "="*70)
print("COMPREHENSIVE BUG REPORT - INTEGRASANTÉ")
print("="*70)
print(f"Testing: {BASE_URL}")
print("")

# ============================================================
# 1. PATIENT MANAGEMENT TESTS
# ============================================================

print("\n[1] PATIENT MANAGEMENT")
print("-"*70)

# Test 1.1: Create patient
response = requests.post(f"{BASE_URL}/api/patients", json={
    "ej_id": 1,
    "name": "BugTest Patient",
    "date_birth": "1990-01-01",
    "sex": "M"
})

if response.status_code != 200 and response.status_code != 201:
    report_bug(
        "Patient Management",
        "/api/patients",
        "POST",
        "Cannot create patient",
        "HTTP 200/201 with patient object",
        f"HTTP {response.status_code}: {response.text[:150]}",
        "POST /api/patients with valid patient data",
        "CRITICAL"
    )
    print(f"❌ Create patient failed: {response.status_code}")
else:
    print(f"✅ Create patient: Success")
    new_patient_id = response.json().get("id")

# Test 1.2: List patients
response = requests.get(f"{BASE_URL}/api/patients")
if response.status_code != 200:
    report_bug(
        "Patient Management",
        "/api/patients",
        "GET",
        "Cannot list patients",
        "HTTP 200 with array",
        f"HTTP {response.status_code}",
        "GET /api/patients",
        "HIGH"
    )
    print(f"❌ List patients failed: {response.status_code}")
else:
    print(f"✅ List patients: Success")

# ============================================================
# 2. DOSSIER MANAGEMENT TESTS
# ============================================================

print("\n[2] DOSSIER MANAGEMENT")
print("-"*70)

# Test 2.1: List dossiers
response = requests.get(f"{BASE_URL}/api/dossiers/")
if response.status_code != 200:
    report_bug(
        "Dossier Management",
        "/api/dossiers",
        "GET",
        "Cannot list dossiers via API",
        "HTTP 200 with list of dossiers",
        f"HTTP {response.status_code}: {response.text[:150]}",
        "GET /api/dossiers",
        "CRITICAL"
    )
    print(f"❌ List dossiers: HTTP {response.status_code}")
else:
    try:
        data = response.json()
        print(f"✅ List dossiers: Success ({len(data)} dossiers)")
    except:
        report_bug(
            "Dossier Management",
            "/api/dossiers",
            "GET",
            "Dossiers response is not valid JSON",
            "Valid JSON array",
            f"Invalid JSON: {response.text[:100]}",
            "GET /api/dossiers",
            "HIGH"
        )

# Test 2.2: Get dossier detail
response = requests.get(f"{BASE_URL}/api/dossiers/1")
if response.status_code not in [200, 404]:
    report_bug(
        "Dossier Management",
        "/api/dossiers/{id}",
        "GET",
        "Cannot get dossier detail",
        "HTTP 200 with dossier object",
        f"HTTP {response.status_code}: {response.text[:150]}",
        "GET /api/dossiers/1",
        "HIGH"
    )

# ============================================================
# 3. SCENARIOS TESTS
# ============================================================

print("\n[3] SCENARIOS & FIXTURES")
print("-"*70)

# Test 3.1: List scenarios (both HTML and API)
response = requests.get(f"{BASE_URL}/scenarios")
if response.status_code == 200:
    if "text/html" in response.headers.get("content-type", ""):
        print(f"✅ Scenarios page returns HTML")
    else:
        print(f"⚠️  Scenarios page should return HTML but got {response.headers.get('content-type')}")
else:
    report_bug(
        "Scenarios",
        "/scenarios",
        "GET",
        "Scenarios page not accessible",
        "HTTP 200",
        f"HTTP {response.status_code}",
        "GET /scenarios",
        "MEDIUM"
    )

# Test 3.2: Scenarios dashboard
response = requests.get(f"{BASE_URL}/scenarios/dashboard")
if response.status_code == 200:
    print(f"✅ Scenarios dashboard accessible")
elif response.status_code == 422:
    report_bug(
        "Scenarios",
        "/scenarios/dashboard",
        "GET",
        "Scenarios dashboard has routing issue",
        "HTTP 200",
        f"HTTP 422 - path parameter 'dashboard' being parsed as scenario_id",
        "GET /scenarios/dashboard",
        "MEDIUM"
    )
else:
    report_bug(
        "Scenarios",
        "/scenarios/dashboard",
        "GET",
        "Scenarios dashboard not accessible",
        "HTTP 200",
        f"HTTP {response.status_code}",
        "GET /scenarios/dashboard",
        "MEDIUM"
    )

# ============================================================
# 4. MESSAGE ENDPOINTS TESTS
# ============================================================

print("\n[4] MESSAGE HANDLING")
print("-"*70)

endpoints_to_test = [
    ("/hprim/import", "HPRIM Import UI"),
    ("/ihe", "IHE PAM Dashboard"),
    ("/ngap", "NGAP Interface"),
]

for endpoint, name in endpoints_to_test:
    response = requests.get(f"{BASE_URL}{endpoint}")
    if response.status_code == 404:
        report_bug(
            "Message Handling",
            endpoint,
            "GET",
            f"{name} endpoint returns 404",
            "HTTP 200 with page content",
            f"HTTP 404 - Endpoint not found",
            f"GET {endpoint}",
            "MEDIUM"
        )
        print(f"❌ {name}: 404")
    elif response.status_code == 200:
        print(f"✅ {name}: 200")
    else:
        print(f"⚠️  {name}: HTTP {response.status_code}")

# ============================================================
# 5. COTATION ENDPOINTS TESTS
# ============================================================

print("\n[5] COTATION WORKFLOWS")
print("-"*70)

cotation_endpoints = [
    ("/ccam", "CCAM Search"),
    ("/ngap", "NGAP Acts"),
    ("/ucd", "UCD Dashboard"),
    ("/lpp", "LPP Dashboard"),
]

for endpoint, name in cotation_endpoints:
    response = requests.get(f"{BASE_URL}{endpoint}")
    if response.status_code == 404:
        report_bug(
            "Cotation",
            endpoint,
            "GET",
            f"{name} endpoint returns 404",
            "HTTP 200 with cotation interface",
            f"HTTP 404",
            f"GET {endpoint}",
            "MEDIUM"
        )
        print(f"❌ {name}: 404")
    elif response.status_code == 200:
        print(f"✅ {name}: 200")
    else:
        print(f"⚠️  {name}: HTTP {response.status_code}")

# ============================================================
# 6. FHIR ENDPOINTS TESTS
# ============================================================

print("\n[6] FHIR SUPPORT")
print("-"*70)

# Test FHIR import
response = requests.post(f"{BASE_URL}/api/fhir/import/bundle", json={
    "bundle": {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": []
    },
    "ej_id": 1
})

if response.status_code in [200, 400]:
    print(f"✅ FHIR import endpoint: {response.status_code}")
elif response.status_code in [404, 500]:
    report_bug(
        "FHIR",
        "/api/fhir/import/bundle",
        "POST",
        "FHIR import endpoint error",
        "HTTP 200 with bundle processed",
        f"HTTP {response.status_code}",
        "POST /api/fhir/import/bundle with minimal bundle",
        "HIGH"
    )
    print(f"❌ FHIR import: {response.status_code}")

# ============================================================
# 7. STRUCTURE ENDPOINTS TESTS
# ============================================================

print("\n[7] ORGANIZATIONAL STRUCTURE")
print("-"*70)

struct_endpoints = [
    ("/structure", "Structure Home"),
    ("/admin/ght", "GHT List"),
    ("/structure/poles", "Poles List"),
]

for endpoint, name in struct_endpoints:
    response = requests.get(f"{BASE_URL}{endpoint}")
    if response.status_code == 200:
        print(f"✅ {name}: OK")
    else:
        print(f"⚠️  {name}: {response.status_code}")

# ============================================================
# SUMMARY & REPORT GENERATION
# ============================================================

print("\n" + "="*70)
print("BUG REPORT SUMMARY")
print("="*70)

if BUGS:
    print(f"\n🐛 Total Bugs Found: {len(BUGS)}\n")
    
    # Group by severity
    critical = [b for b in BUGS if b["severity"] == "CRITICAL"]
    high = [b for b in BUGS if b["severity"] == "HIGH"]
    medium = [b for b in BUGS if b["severity"] == "MEDIUM"]
    
    if critical:
        print(f"🔴 CRITICAL ({len(critical)}):")
        for b in critical:
            print(f"   • #{b['id']}: {b['title']} ({b['endpoint']})")
    
    if high:
        print(f"\n🟠 HIGH ({len(high)}):")
        for b in high:
            print(f"   • #{b['id']}: {b['title']} ({b['endpoint']})")
    
    if medium:
        print(f"\n🟡 MEDIUM ({len(medium)}):")
        for b in medium:
            print(f"   • #{b['id']}: {b['title']} ({b['endpoint']})")
    
    # Generate markdown report
    report_md = "# BUG REPORT - IntegraSanté\n\n"
    report_md += f"**Generated:** {datetime.now().isoformat()}\n"
    report_md += f"**Total Bugs:** {len(BUGS)}\n"
    report_md += f"**Test Environment:** {BASE_URL}\n\n"
    
    for bug in BUGS:
        report_md += f"## Bug #{bug['id']}: {bug['title']}\n\n"
        report_md += f"- **Severity:** {bug['severity']}\n"
        report_md += f"- **Category:** {bug['category']}\n"
        report_md += f"- **Endpoint:** `{bug['method']} {bug['endpoint']}`\n"
        report_md += f"- **Steps to Reproduce:**\n  ```\n  {bug['steps_to_reproduce']}\n  ```\n"
        report_md += f"- **Expected:** {bug['expected']}\n"
        report_md += f"- **Actual:** {bug['actual']}\n\n"
    
    # Save report
    with open("BUG_REPORT.md", "w") as f:
        f.write(report_md)
    
    print(f"\n✅ Bug report saved to: BUG_REPORT.md")
else:
    print("\n✅ No bugs found in testing!")

sys.exit(0 if not BUGS or len(critical) == 0 else 1)
