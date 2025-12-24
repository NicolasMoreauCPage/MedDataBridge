#!/usr/bin/env python3
"""Test identifier OID extraction"""
import os
import sys
import asyncio

os.environ['PAM_AUTO_CREATE_UF'] = '1'
os.environ['LOG_LEVEL'] = 'DEBUG'

sys.path.insert(0, os.path.dirname(__file__))

from app.services.transport_inbound import on_message_inbound_async
from app.db import get_session
from app.models_shared import SystemEndpoint

async def test():
    with open('pam_archive/1117618884.hl7', 'r') as f:
        message = f.read()
    
    print("=== Testing identifier OID extraction ===")
    session = next(get_session())
    endpoint = session.get(SystemEndpoint, 1)
    result = await on_message_inbound_async(message, session, endpoint)
    print(f"\n=== RESULT: {result}")

if __name__ == "__main__":
    asyncio.run(test())
