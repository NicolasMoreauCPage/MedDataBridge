#!/usr/bin/env python3
"""Test import direct avec détails"""
import os
import sys
os.environ['PAM_AUTO_CREATE_UF'] = '1'
sys.path.insert(0, '.')

import asyncio
from app.db import get_session
from app.models_shared import SystemEndpoint
from app.services.transport_inbound import on_message_inbound_async
from sqlalchemy import text

async def test():
    # Lire un message
    with open('pam_archive/1117618884.hl7', 'r') as f:
        message = f.read()
    
    print(f"Message type: {message.split('|')[8] if len(message.split('|')) > 8 else 'unknown'}")
    
    # Traiter
    session = next(get_session())
    endpoint = session.get(SystemEndpoint, 1)
    
    try:
        result = await on_message_inbound_async(message, session, endpoint)
        print(f"\nRésultat: {result[:100]}...")
        
        # Vérifier les commits
        session.commit()
        
        # Stats
        patients = session.execute(text("SELECT COUNT(*) FROM patient")).scalar()
        identifiers = session.execute(text("SELECT COUNT(*) FROM identifier WHERE patient_id IS NOT NULL")).scalar()
        
        print(f"\n✅ Patients créés: {patients}")
        print(f"✅ Identifiers patients: {identifiers}")
        
        if identifiers > 0:
            sample = session.execute(text("SELECT id, value, system, oid, type FROM identifier WHERE patient_id IS NOT NULL LIMIT 3")).fetchall()
            print("\nExemples d'identifiers:")
            for row in sample:
                print(f"  {row}")
        
    except Exception as e:
        import traceback
        print(f"\n❌ ERREUR: {e}")
        traceback.print_exc()
        session.rollback()

if __name__ == "__main__":
    asyncio.run(test())
