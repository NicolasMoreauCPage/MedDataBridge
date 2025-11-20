#!/usr/bin/env python3
"""Test script to verify Service entity FHIR conversion fix."""

from sqlmodel import Session, select
from app.db import engine
from app.models_structure import Service
from app.services.fhir_structure import entity_to_fhir_location

def test_service_conversion():
    """Test that Service entity can be converted to FHIR without AttributeError."""
    print("Testing Service entity FHIR conversion...")

    with Session(engine) as session:
        # Get a Service entity
        service = session.exec(select(Service)).first()
        if not service:
            print("❌ No Service entity found in database")
            return False

        print(f"Found Service: {service.name} (id={service.id})")

        try:
            # This should not raise AttributeError anymore
            fhir_loc = entity_to_fhir_location(service, session)
            print("✅ Service conversion successful!")
            print(f"FHIR Location keys: {list(fhir_loc.keys())}")

            # Check that status and mode are not set (since Service doesn't have them)
            if 'status' in fhir_loc:
                print(f"⚠️  Warning: status found in FHIR output: {fhir_loc['status']}")
            else:
                print("✅ Status correctly not set (Service has no status attribute)")

            if 'mode' in fhir_loc:
                print(f"⚠️  Warning: mode found in FHIR output: {fhir_loc['mode']}")
            else:
                print("✅ Mode correctly not set (Service has no mode attribute)")

            return True

        except AttributeError as e:
            print(f"❌ AttributeError still occurs: {e}")
            return False
        except Exception as e:
            print(f"❌ Other error: {e}")
            return False

if __name__ == "__main__":
    success = test_service_conversion()
    if success:
        print("\n🎉 Test PASSED: Service FHIR conversion works!")
    else:
        print("\n💥 Test FAILED: Service FHIR conversion still broken")