#!/usr/bin/env python3
"""
Detailed bug investigation
"""

import requests
import json
import traceback

BASE_URL = "http://localhost:8000"

print("="*70)
print("BUG INVESTIGATION: Detailed Testing")
print("="*70)

# Bug 1: Dossiers list
print("\n1. Testing GET /api/dossiers")
print("-"*70)
try:
    r = requests.get(f"{BASE_URL}/api/dossiers")
    print(f"Status: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    print(f"Response text: {r.text[:500]}")
    if r.status_code != 200:
        print(f"Full response: {r.text}")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()

# Bug 2: Patient creation
print("\n2. Testing POST /api/patients")
print("-"*70)
try:
    data = {
        "ej_id": 1,
        "name": "Test Patient 2",
        "date_birth": "1980-01-01",
        "sex": "M"
    }
    print(f"Request data: {json.dumps(data, indent=2)}")
    r = requests.post(f"{BASE_URL}/api/patients", json=data)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()

# Bug 3: Scenarios list
print("\n3. Testing GET /scenarios")
print("-"*70)
try:
    r = requests.get(f"{BASE_URL}/scenarios")
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type')}")
    print(f"Response text: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()

# Bug 4: Scenarios dashboard
print("\n4. Testing GET /scenarios/dashboard")
print("-"*70)
try:
    r = requests.get(f"{BASE_URL}/scenarios/dashboard")
    print(f"Status: {r.status_code}")
    print(f"Response text: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()

# Check other endpoints that showed issues
print("\n5. Testing GET /hprim/import")
print("-"*70)
try:
    r = requests.get(f"{BASE_URL}/hprim/import")
    print(f"Status: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")

print("\n6. Testing GET /ihe")
print("-"*70)
try:
    r = requests.get(f"{BASE_URL}/ihe")
    print(f"Status: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")

print("\n7. Testing GET /ngap")
print("-"*70)
try:
    r = requests.get(f"{BASE_URL}/ngap")
    print(f"Status: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
