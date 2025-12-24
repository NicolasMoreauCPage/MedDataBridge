#!/usr/bin/env python3
"""Test script to verify MessageLog duplicate fix."""
import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path

from app.services.transport_inbound import on_message_inbound_async
from app.models_shared import MessageLog, SystemEndpoint
from sqlmodel import Session, select
from app.db import engine


# Sample ADT^A01 message
TEST_MESSAGE = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20250606103000||ADT^A01|TEST123456|P|2.5|||AL|AL|FRA
EVN|A01|20250606103000
PID|1||PAT12345^^^EJ5^PI||DOE^JOHN||19800101|M
PV1|1|I|SERVICE1^CHAMBRE1^LIT1||||||DOC123||||||||||12345678"""


async def test_no_duplicates():
    """Send a test message and verify only one MessageLog is created."""
    
    # Enable debug logging
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    print("🧪 Test de correction des doublons MessageLog\n")
    
    # Get test endpoint
    with Session(engine) as session:
        endpoint = session.exec(
            select(SystemEndpoint).where(SystemEndpoint.name.like("MLLP RECV%"))
        ).first()
        
        if not endpoint:
            print("❌ Aucun endpoint MLLP RECV trouvé")
            return False
        
        print(f"🔌 Utilisation de l'endpoint: {endpoint.name}")
    
    # Count messages before
    with Session(engine) as session:
        count_before = session.exec(select(MessageLog)).all()
        print(f"📊 Messages avant test: {len(count_before)}")
    
    # Send message
    print(f"\n📤 Envoi du message test (correlation_id: TEST123456)...")
    
    with Session(engine) as session:
        ack = await on_message_inbound_async(TEST_MESSAGE, session, endpoint)
        print(f"📥 ACK reçu: {ack[:80] if ack else 'None'}...")
    
    # Wait a bit for commit to flush
    await asyncio.sleep(0.1)
    
    # Count messages after with NEW session
    with Session(engine) as session:
        messages = session.exec(
            select(MessageLog)
            .where(MessageLog.correlation_id == "TEST123456")
            .order_by(MessageLog.created_at.desc())
        ).all()
        
        count = len(messages)
        print(f"\n📊 Messages avec correlation_id 'TEST123456': {count}")
        
        if count == 0:
            print("❌ Aucun message créé!")
            return False
        elif count == 1:
            msg = messages[0]
            print(f"\n✅ UN SEUL message créé (comme attendu)")
            print(f"   ID: {msg.id}")
            print(f"   Status: {msg.status}")
            print(f"   Type: {msg.message_type}")
            print(f"   Created: {msg.created_at}")
            print(f"   PAM validation: {msg.pam_validation_status}")
            return True
        else:
            print(f"\n❌ ERREUR: {count} messages créés (doublons détectés)")
            for i, msg in enumerate(messages, 1):
                print(f"\n   Message {i}:")
                print(f"     ID: {msg.id}")
                print(f"     Status: {msg.status}")
                print(f"     Created: {msg.created_at}")
                print(f"     PAM validation: {msg.pam_validation_status}")
            return False


if __name__ == "__main__":
    result = asyncio.run(test_no_duplicates())
    exit(0 if result else 1)
