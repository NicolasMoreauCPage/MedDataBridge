#!/usr/bin/env python3
"""Test single message import with full error reporting"""
import os
import sys
import asyncio
import traceback

os.environ['PAM_AUTO_CREATE_UF'] = '1'

sys.path.insert(0, os.path.dirname(__file__))

from app.services.transport_inbound import on_message_inbound_async
from app.db import get_session
from app.models_shared import SystemEndpoint

async def test():
    try:
        with open('pam_archive/1117618884.hl7', 'r') as f:
            message = f.read()
        
        print("=== Testing single message import ===")
        print(f"Message: {message[:100]}...")
        
        session = next(get_session())
        endpoint = session.get(SystemEndpoint, 1)
        print(f"Endpoint: {endpoint.name} (ID: {endpoint.id})")
        
        result = await on_message_inbound_async(message, session, endpoint)
        print(f"\n=== RESULT: {result[:200]}")
        
        # Check database
        from sqlalchemy import text
        patients = session.execute(text("SELECT COUNT(*) FROM patient")).scalar()
        identifiers = session.execute(text("SELECT COUNT(*) FROM identifier")).scalar()
        print(f"\nDatabase stats:")
        print(f"  Patients: {patients}")
        print(f"  Identifiers: {identifiers}")
        
    except Exception as e:
        print(f"\n=== ERROR ===")
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test())
