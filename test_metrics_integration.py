#!/usr/bin/env python3
"""Test script to populate metrics and verify dashboard display."""
import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_hprim_validation():
    """Test HPRIM validation metrics."""
    print("\n🔵 Testing HPRIM validation inbound...")
    
    # Import the record function directly
    try:
        from app.metrics import record_hprim_validation
        
        # Simulate 3 successful validations
        for i in range(3):
            record_hprim_validation(
                succes=True,
                schema="msgEvenementsServeurActes2_4",
                direction="inbound",
                duration_seconds=0.1 + (i * 0.05)
            )
            print(f"  ✅ HPRIM inbound validation #{i+1}")
        
        # Simulate 1 XSD error
        record_hprim_validation(
            succes=False,
            schema="msgEvenementsServeurActes2_4",
            error_type="xsd",
            direction="inbound",
            duration_seconds=0.05
        )
        print("  ❌ HPRIM XSD validation error")
        
        # Simulate 2 outbound validations
        for i in range(2):
            record_hprim_validation(
                succes=True,
                schema="msgEvenementsServeurActes2_4",
                direction="outbound",
                duration_seconds=0.08
            )
            print(f"  ✅ HPRIM outbound validation #{i+1}")
        
        print("✅ HPRIM metrics recorded\n")
        return True
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return False


def test_pam_messages():
    """Test PAM (HL7 ADT) message metrics."""
    print("🔵 Testing PAM (IHE HL7 ADT) messages...")
    
    try:
        from app.metrics import record_pam_ack
        
        # Simulate PAM inbound ADT messages
        for i in range(2):
            record_pam_ack(
                direction="inbound",
                ack_code="AA",  # Application Accept
                message_type="ADT^A01",
                duration_seconds=0.05 + (i * 0.02)
            )
            print(f"  ✅ PAM ADT inbound #{i+1} (AA)")
        
        # Simulate 1 rejected ADT
        record_pam_ack(
            direction="inbound",
            ack_code="AE",  # Application Error
            message_type="ADT^A04",
            duration_seconds=0.03
        )
        print("  ⚠️  PAM ADT rejected (AE)")
        
        # Simulate PAM outbound ACK
        for i in range(3):
            record_pam_ack(
                direction="outbound",
                ack_code="CA",  # Commit Accept
                message_type="ADT^A01",
                duration_seconds=0.04
            )
            print(f"  ✅ PAM ACK outbound #{i+1} (CA)")
        
        print("✅ PAM metrics recorded\n")
        return True
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return False


def test_fhir_events():
    """Test FHIR import/export metrics."""
    print("🔵 Testing FHIR import/export events...")
    
    try:
        from app.metrics import record_fhir_event
        
        # Simulate FHIR imports
        for i, resource in enumerate(["bundle", "patient", "location"]):
            record_fhir_event(
                direction="inbound",
                resource=resource,
                action="import",
                success=True,
                status_code=200,
                duration_seconds=0.1 + (i * 0.05)
            )
            print(f"  ✅ FHIR {resource} import #{i+1}")
        
        # Simulate 1 failed FHIR import
        record_fhir_event(
            direction="inbound",
            resource="patient",
            action="import",
            success=False,
            status_code=400,
            duration_seconds=0.02
        )
        print("  ❌ FHIR patient import failed (400)")
        
        # Simulate FHIR exports
        for i, resource in enumerate(["patients", "venues", "all"]):
            record_fhir_event(
                direction="outbound",
                resource=resource,
                action="export",
                success=True,
                status_code=200,
                duration_seconds=0.08 + (i * 0.03)
            )
            print(f"  ✅ FHIR {resource} export #{i+1}")
        
        print("✅ FHIR metrics recorded\n")
        return True
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return False


def get_metrics_dashboard() -> Dict[str, Any]:
    """Fetch metrics dashboard data."""
    try:
        response = requests.get(f"{BASE_URL}/api/metrics/dashboard", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Failed to fetch dashboard: {response.status_code}")
            return {}
    except Exception as e:
        print(f"❌ Error fetching dashboard: {e}")
        return {}


def display_metrics_summary(data: Dict[str, Any]):
    """Display a summary of collected metrics."""
    if not data:
        return
    
    print("\n" + "="*70)
    print("📊 METRICS DASHBOARD SUMMARY")
    print("="*70)
    
    summary = data.get("summary", {})
    print(f"\n🔹 Overall Stats:")
    print(f"   Total Operations: {summary.get('total_operations', 0)}")
    print(f"   Success Rate: {summary.get('success_rate', 0):.1f}%")
    print(f"   Error Rate: {summary.get('error_rate', 0):.1f}%")
    print(f"   Operations Tracked: {summary.get('operations_tracked', 0)}")
    
    operations = data.get("operations", {})
    
    # HPRIM
    hprim_inbound = operations.get("hprim_validation_inbound", {})
    hprim_outbound = operations.get("hprim_validation_outbound", {})
    
    if hprim_inbound or hprim_outbound:
        print(f"\n📋 HPRIM Validation:")
        if hprim_inbound:
            print(f"   Inbound: {hprim_inbound.get('count', 0)} ops, "
                  f"{hprim_inbound.get('success_count', 0)} success, "
                  f"avg {(hprim_inbound.get('avg_duration', 0)*1000):.0f}ms")
        if hprim_outbound:
            print(f"   Outbound: {hprim_outbound.get('count', 0)} ops, "
                  f"{hprim_outbound.get('success_count', 0)} success, "
                  f"avg {(hprim_outbound.get('avg_duration', 0)*1000):.0f}ms")
    
    # PAM
    pam_inbound = operations.get("pam_message_inbound", {})
    pam_outbound = operations.get("pam_message_outbound", {})
    
    if pam_inbound or pam_outbound:
        print(f"\n📤 PAM (IHE HL7 ADT):")
        if pam_inbound:
            print(f"   Inbound: {pam_inbound.get('count', 0)} msgs, "
                  f"{pam_inbound.get('success_count', 0)} accepted, "
                  f"avg {(pam_inbound.get('avg_duration', 0)*1000):.0f}ms")
        if pam_outbound:
            print(f"   Outbound: {pam_outbound.get('count', 0)} ACKs, "
                  f"{pam_outbound.get('success_count', 0)} committed, "
                  f"avg {(pam_outbound.get('avg_duration', 0)*1000):.0f}ms")
    
    # FHIR
    fhir_import = operations.get("fhir_import", {})
    fhir_export = operations.get("fhir_export", {})
    
    if fhir_import or fhir_export:
        print(f"\n🔄 FHIR (Import/Export):")
        if fhir_import:
            print(f"   Import: {fhir_import.get('count', 0)} resources, "
                  f"{fhir_import.get('success_count', 0)} success, "
                  f"avg {(fhir_import.get('avg_duration', 0)*1000):.0f}ms")
        if fhir_export:
            print(f"   Export: {fhir_export.get('count', 0)} resources, "
                  f"{fhir_export.get('success_count', 0)} success, "
                  f"avg {(fhir_export.get('avg_duration', 0)*1000):.0f}ms")
    
    print("\n" + "="*70)
    print("✅ Visit http://localhost:8000/metrics/dashboard to see the UI")
    print("="*70 + "\n")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("🧪 METRICS INTEGRATION TEST")
    print("="*70)
    print(f"Base URL: {BASE_URL}")
    print("="*70)
    
    # Run tests
    hprim_ok = test_hprim_validation()
    pam_ok = test_pam_messages()
    fhir_ok = test_fhir_events()
    
    # Wait for async operations
    time.sleep(0.5)
    
    # Fetch and display metrics
    print("🔍 Fetching metrics dashboard...")
    data = get_metrics_dashboard()
    
    if data:
        display_metrics_summary(data)
    else:
        print("⚠️  No metrics data received")
    
    # Summary
    if all([hprim_ok, pam_ok, fhir_ok]):
        print("\n✅ All tests completed successfully!")
        print("\n📊 Metrics should now be visible on the dashboard:")
        print("   • HPRIM validation (inbound/outbound)")
        print("   • PAM messages (ADT/ACK)")
        print("   • FHIR events (import/export)")
    else:
        print("\n⚠️  Some tests failed - check output above")


if __name__ == "__main__":
    main()
