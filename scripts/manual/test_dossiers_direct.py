#!/usr/bin/env python3
"""
Test dossiers error with full traceback
"""

import sys
sys.path.insert(0, '/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge')

from app.db import engine, session_factory
from app.models import Dossier
from sqlmodel import select, Session
import traceback

try:
    # Get a session
    session = session_factory()
    
    # Try the query
    print("Attempting to list dossiers...")
    query = select(Dossier)
    dossiers = session.exec(query).all()
    
    print(f"✅ Got {len(dossiers)} dossiers")
    
    # Try to access attributes
    for i, dossier in enumerate(dossiers[:3]):
        print(f"\nDossier {i}:")
        try:
            print(f"  ID: {dossier.id}")
            print(f"  Type: {dossier.dossier_type}")
            print(f"  Patient ID: {dossier.patient_id}")
            print(f"  Admit time: {dossier.admit_time}")
            print(f"  Discharge time: {dossier.discharge_time}")
        except Exception as e:
            print(f"  ❌ Error accessing attributes: {e}")
            traceback.print_exc()
    
    session.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    traceback.print_exc()
