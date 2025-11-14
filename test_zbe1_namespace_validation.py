#!/usr/bin/env python3
"""
Test ZBE-1 namespace validation in PAM messages.

This test:
1. Creates a test database with minimal entities (Patient, Dossier, Venue, Mouvement)
2. Creates an Identifier of type MVT linked to the Mouvement
3. Creates an IdentifierNamespace in the database
4. Emits an HL7 message using the standard emit pipeline
5. Validates the message using pam_validation
6. Displays the ZBE-1 segment content and validation result
"""

import os
import sys
from datetime import datetime, timedelta
from sqlmodel import Session, SQLModel, create_engine, select

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import Patient, Dossier, Venue, Mouvement
from app.models_identifiers import Identifier, IdentifierType
from app.models_structure_fhir import GHTContext, IdentifierNamespace
from app.services.emit_on_create import generate_pam_hl7
from app.services.pam_validation import validate_pam


def test_zbe1_namespace_validation():
    """Test that ZBE-1 with namespace is validated correctly."""
    
    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Create GHT context
        ght = GHTContext(
            name="GHT Test",
            code="GHT001",
            is_active=True
        )
        session.add(ght)
        session.flush()
        
        # Create IdentifierNamespace for MOUVEMENT
        namespace = IdentifierNamespace(
            name="MVT_HOSP",
            system="urn:oid:1.2.250.1.71.1.2.5",
            oid="1.2.250.1.71.1.2.5",
            type="MVT",
            ght_context_id=ght.id,
            is_active=True
        )
        session.add(namespace)
        session.flush()
        
        # Create Patient
        patient = Patient(
            patient_seq=1001,
            family="Dupont",
            given="Jean",
            birth_date="1965-01-15",
            gender="M"
        )
        session.add(patient)
        session.flush()
        
        # Create Dossier
        dossier = Dossier(
            patient_id=patient.id,
            dossier_seq=2001,
            dossier_type="hospitalise",
            admit_time=datetime.utcnow(),
            uf_responsabilite="URG"
        )
        session.add(dossier)
        session.flush()
        
        # Create Venue
        venue = Venue(
            dossier_id=dossier.id,
            venue_seq=3001,
            start_time=datetime.utcnow(),
            uf_responsabilite="URG"
        )
        session.add(venue)
        session.flush()
        
        # Create Mouvement
        mouvement = Mouvement(
            venue_id=venue.id,
            mouvement_seq=4001,
            when=datetime.utcnow(),
            trigger_event="A05",
            action="INSERT",
            nature="H",
            uf_responsabilite="URG"
        )
        session.add(mouvement)
        session.flush()
        
        # Create Identifier for Mouvement (type MVT with namespace)
        mvt_identifier = Identifier(
            value="MVT4001",
            type=IdentifierType.MVT,
            system="urn:oid:1.2.250.1.71.1.2.5",
            oid="1.2.250.1.71.1.2.5",
            mouvement_id=mouvement.id,
            status="active"
        )
        session.add(mvt_identifier)
        session.commit()
        
        # Generate HL7 message using the emit pipeline
        print("=" * 80)
        print("TEST: ZBE-1 Namespace Validation")
        print("=" * 80)
        print()
        
        hl7_message = generate_pam_hl7(
            entity=mouvement,
            entity_type="mouvement",
            session=session,
            operation="insert"
        )
        
        print("Generated HL7 Message:")
        print("-" * 80)
        for idx, segment in enumerate(hl7_message.split("\r"), 1):
            print(f"  {idx:2d}. {segment}")
        print("-" * 80)
        print()
        
        # Extract ZBE segment for detailed inspection
        zbe_segment = None
        for segment in hl7_message.split("\r"):
            if segment.startswith("ZBE|"):
                zbe_segment = segment
                break
        
        if zbe_segment:
            print("ZBE Segment Details:")
            print(f"  Full segment: {zbe_segment}")
            parts = zbe_segment.split("|")
            print(f"  ZBE-1 (Movement ID): {parts[1] if len(parts) > 1 else '(empty)'}")
            if len(parts) > 1:
                zbe1_comps = parts[1].split("^")
                print(f"    - Component 1 (ID):          {zbe1_comps[0] if len(zbe1_comps) > 0 else '(empty)'}")
                print(f"    - Component 2 (Namespace):   {zbe1_comps[1] if len(zbe1_comps) > 1 else '(empty)'}")
                print(f"    - Component 3 (OID):         {zbe1_comps[2] if len(zbe1_comps) > 2 else '(empty)'}")
                print(f"    - Component 4 (System):      {zbe1_comps[3] if len(zbe1_comps) > 3 else '(empty)'}")
            print()
        
        # Validate the message
        print("PAM Validation Results:")
        print("-" * 80)
        validation_result = validate_pam(hl7_message, direction="out")
        
        print(f"  Is Valid:      {validation_result.is_valid}")
        print(f"  Level:         {validation_result.level}")
        print(f"  Event:         {validation_result.event}")
        print(f"  Message Type:  {validation_result.message_type}")
        print()
        
        if validation_result.issues:
            print(f"  Issues ({len(validation_result.issues)}):")
            for issue in validation_result.issues:
                severity_marker = {
                    "error": "❌",
                    "warn": "⚠️ ",
                    "info": "ℹ️ "
                }.get(issue.severity, "  ")
                print(f"    {severity_marker} [{issue.severity.upper()}] {issue.code}")
                print(f"       {issue.message}")
        else:
            print("  Issues: None")
        
        print()
        print("=" * 80)
        print("Test Result:")
        if validation_result.is_valid:
            print("✓ Message validates successfully with ZBE-1 namespace!")
        else:
            print("✗ Message validation failed (see issues above)")
        print("=" * 80)
        
        return validation_result.is_valid


if __name__ == "__main__":
    try:
        success = test_zbe1_namespace_validation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
