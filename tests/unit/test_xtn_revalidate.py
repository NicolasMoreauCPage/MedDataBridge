#!/usr/bin/env python3
"""Re-validate specific messages to test XTN fix."""
import asyncio
from pathlib import Path
from sqlmodel import Session, select
from app.db import engine
from app.models_shared import SystemEndpoint, MessageLog
from app.services.transport_inbound import on_message_inbound_async


async def revalidate_messages():
    """Re-import specific messages to test validation."""
    
    test_files = [
        "1117931658.hl7",  # Message with email that was failing
        "1117924595.hl7",  # First message in archive
        "1117924601.hl7",  # Second message
    ]
    
    archive_dir = Path("/home/nico/Travail/Fhir_MedBridgeData/Interfaces/Entrant/PAM/Archive")
    
    # Get endpoint
    with Session(engine) as session:
        endpoint = session.exec(
            select(SystemEndpoint).where(SystemEndpoint.name.like("MLLP RECV%"))
        ).first()
    
    print("🧪 Re-validating test messages with XTN fix\n")
    
    for filename in test_files:
        file_path = archive_dir / filename
        correlation_id = file_path.stem
        
        if not file_path.exists():
            print(f"⚠️  File not found: {filename}")
            continue
        
        # Delete old entry
        with Session(engine) as session:
            old = session.exec(
                select(MessageLog).where(MessageLog.correlation_id == correlation_id)
            ).first()
            if old:
                session.delete(old)
                session.commit()
        
        # Re-import
        message = file_path.read_text()
        
        with Session(engine) as session:
            ack = await on_message_inbound_async(message, session, endpoint)
        
        # Check validation result
        with Session(engine) as session:
            msg_log = session.exec(
                select(MessageLog).where(MessageLog.correlation_id == correlation_id)
            ).first()
            
            if msg_log:
                print(f"✅ {correlation_id}")
                print(f"   Status: {msg_log.status}")
                print(f"   PAM Validation: {msg_log.pam_validation_status}")
                if msg_log.pam_validation_issues:
                    import json
                    issues = json.loads(msg_log.pam_validation_issues)
                    xtn_issues = [i for i in issues if "XTN" in i.get("code", "")]
                    if xtn_issues:
                        print(f"   XTN Issues: {len(xtn_issues)}")
                        for issue in xtn_issues:
                            print(f"      [{issue['severity']}] {issue['code']}: {issue['message']}")
                    else:
                        print(f"   ✅ No XTN issues (total: {len(issues)} issues)")
                print()
            else:
                print(f"❌ {correlation_id}: Message not created\n")


if __name__ == "__main__":
    asyncio.run(revalidate_messages())
