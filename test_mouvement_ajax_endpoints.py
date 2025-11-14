#!/usr/bin/env python3
"""
Quick test for mouvement form AJAX endpoints
Tests the new GET endpoints for dynamic select updates
"""

import requests
import json
from pprint import pprint

BASE_URL = "http://127.0.0.1:8000"

def test_chambres_endpoint():
    """Test GET /api/mouvements/chambres/{uh_id}"""
    print("\n" + "="*60)
    print("Testing: GET /api/mouvements/chambres/{uh_id}")
    print("="*60)
    
    # Assuming UH ID 1 exists in your database
    uh_id = 1
    url = f"{BASE_URL}/api/mouvements/chambres/{uh_id}"
    
    try:
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if data.get('success'):
                print(f"✓ Found {len(data.get('options', []))} chambres")
            else:
                print(f"✗ Error: {data.get('error')}")
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Exception: {e}")


def test_lits_endpoint():
    """Test GET /api/mouvements/lits/{chambre_id}"""
    print("\n" + "="*60)
    print("Testing: GET /api/mouvements/lits/{chambre_id}")
    print("="*60)
    
    # Assuming Chambre ID 1 exists in your database
    chambre_id = 1
    url = f"{BASE_URL}/api/mouvements/lits/{chambre_id}"
    
    try:
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if data.get('success'):
                print(f"✓ Found {len(data.get('options', []))} lits")
            else:
                print(f"✗ Error: {data.get('error')}")
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Exception: {e}")


def test_reasons_endpoint():
    """Test GET /api/mouvements/reasons/{movement_type}"""
    print("\n" + "="*60)
    print("Testing: GET /api/mouvements/reasons/{movement_type}")
    print("="*60)
    
    movement_type = "A01"  # Admission
    url = f"{BASE_URL}/api/mouvements/reasons/{movement_type}"
    
    try:
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            if data.get('success'):
                print(f"✓ Found {len(data.get('options', []))} reasons")
            else:
                print(f"✗ Error: {data.get('error')}")
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Exception: {e}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("MOUVEMENT FORM AJAX ENDPOINTS TEST")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/mouvements")
        if response.status_code in [200, 302, 403]:
            print(f"✓ Server is running at {BASE_URL}")
        else:
            print(f"✗ Server responded with {response.status_code}")
    except Exception as e:
        print(f"✗ Cannot connect to server: {e}")
        print(f"  Make sure the server is running at {BASE_URL}")
        exit(1)
    
    test_chambres_endpoint()
    test_lits_endpoint()
    test_reasons_endpoint()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")
