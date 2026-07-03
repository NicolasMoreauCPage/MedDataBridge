#!/usr/bin/env python3
"""
Test patient creation more carefully
"""

import sys
sys.path.insert(0, '/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge')

from app.db import session_factory
from app.models import Patient
from app.models_structure import EntiteJuridique
from sqlmodel import select
import traceback

session = session_factory()

try:
    # Check if we have an entité juridique to work with
    ej = session.exec(select(EntiteJuridique)).first()
    if not ej:
        print("❌ No EntiteJuridique found in database. Cannot test patient creation.")
    else:
        print(f"✅ Found EJ: {ej.id}")
        
        # Try creating a patient
        patient = Patient(
            family="TestPatient",
            given="Test",
            entite_juridique_id=ej.id
        )
        
        session.add(patient)
        session.flush()  # This will raise the error if there's a problem
        session.commit()
        
        print(f"✅ Patient created successfully: ID {patient.id}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"Type: {type(e).__name__}")
    traceback.print_exc()
finally:
    session.close()
