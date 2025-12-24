#!/usr/bin/env python3
"""Import all HL7 messages from tests/exemples/pam_archive directory."""
import asyncio
from pathlib import Path
from datetime import datetime
from sqlmodel import Session, select
from app.db import engine
from app.models_shared import SystemEndpoint, MessageLog
from app.services.transport_inbound import on_message_inbound_async


ARCHIVE_DIR = Path("/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/tests/exemples/pam_archive")


async def import_archive():
    """Import all HL7 files from tests/exemples/pam_archive directory."""
    
    print(f"🔍 Scanning {ARCHIVE_DIR}")
    
    # Get all HL7 files
    hl7_files = sorted(ARCHIVE_DIR.glob("*.hl7"))
    total = len(hl7_files)
    
    print(f"📁 Found {total} HL7 files to import\n")
    
    # Get endpoint
    with Session(engine) as session:
        endpoint = session.exec(
            select(SystemEndpoint).where(SystemEndpoint.name.like("MLLP RECV%"))
        ).first()
        
        if not endpoint:
            print("❌ No MLLP RECV endpoint found")
            return
        
        print(f"🔌 Using endpoint: {endpoint.name} (ID: {endpoint.id})\n")
    
    # Statistics
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    # Process each file
    for i, file_path in enumerate(hl7_files, 1):
        correlation_id = file_path.stem  # Filename without extension
        
        # Check if already imported
        with Session(engine) as session:
            existing = session.exec(
                select(MessageLog).where(MessageLog.correlation_id == correlation_id)
            ).first()
            
            if existing:
                skipped_count += 1
                if i % 50 == 0 or skipped_count == 1:
                    print(f"[{i}/{total}] Skipped {correlation_id} (already imported)")
                continue
        
        # Read message
        try:
            message = file_path.read_text()
        except Exception as e:
            print(f"❌ [{i}/{total}] Error reading {file_path.name}: {e}")
            error_count += 1
            continue
        
        # Import message
        try:
            with Session(engine) as session:
                ack = await on_message_inbound_async(message, session, endpoint)
                # Force commit to persist the message
                session.commit()
                
                # Check if ACK indicates success (AA = Application Accept)
                if "ACK|AA" in ack or "MSA|AA" in ack:
                    success_count += 1
                    if i % 50 == 0 or (success_count == 1 and i < 10):
                        print(f"✅ [{i}/{total}] Imported {correlation_id}")
                else:
                    error_count += 1
                    # Extract error message from ACK
                    error_msg = ack.split("|")[-1] if "|" in ack else "Unknown error"
                    if error_count <= 10 or i % 50 == 0:
                        print(f"⚠️  [{i}/{total}] {correlation_id}: {error_msg[:80]}")
        
        except Exception as e:
            error_count += 1
            if error_count <= 10:
                print(f"❌ [{i}/{total}] Exception importing {correlation_id}: {str(e)[:100]}")
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"📊 IMPORT SUMMARY")
    print(f"{'='*60}")
    print(f"Total files:     {total}")
    print(f"✅ Imported:     {success_count}")
    print(f"⏭️  Skipped:      {skipped_count} (already in DB)")
    print(f"❌ Errors:       {error_count}")
    print(f"{'='*60}")
    
    # Show final count in database
    with Session(engine) as session:
        total_messages = session.exec(select(MessageLog)).all()
        print(f"\n📈 Total messages in database: {len(total_messages)}")


if __name__ == "__main__":
    start = datetime.now()
    asyncio.run(import_archive())
    duration = (datetime.now() - start).total_seconds()
    print(f"\n⏱️  Duration: {duration:.1f}s")
