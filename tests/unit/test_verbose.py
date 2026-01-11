#!/usr/bin/env python3
"""Test avec logs détaillés"""
import os
import sys
import logging

# Configurer les logs AVANT l'import
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

os.environ['PAM_AUTO_CREATE_UF'] = '1'
os.environ['LOG_LEVEL'] = 'DEBUG'
sys.path.insert(0, '.')

import asyncio
from app.db import get_session, session_factory
from app.models_shared import SystemEndpoint
from app.services.transport_inbound import on_message_inbound_async
from sqlalchemy import text

async def test():
    with open('pam_archive/1117618884.hl7', 'r') as f:
        message = f.read()
    
    print("\n=== DÉBUT DU TEST ===\n")
    
    with session_factory() as session:
        endpoint = session.get(SystemEndpoint, 1)

        result = await on_message_inbound_async(message, session, endpoint)

        print(f"\n=== RÉSULTAT ===")
        print(f"ACK: {result[:150]}...")

        # Forcer un commit
        session.commit()
        
        # Stats finales
        patients = session.execute(text("SELECT COUNT(*) FROM patient")).scalar()
        print(f"\n✅ Patients en base: {patients}")
    
    # Stats finales
    patients = session.execute(text("SELECT COUNT(*) FROM patient")).scalar()
    print(f"\n✅ Patients en base: {patients}")

if __name__ == "__main__":
    asyncio.run(test())
