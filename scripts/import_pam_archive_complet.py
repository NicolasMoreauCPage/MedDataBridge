#!/usr/bin/env python3
"""Import all HL7 messages from all three PAM archive directories."""
import asyncio
from pathlib import Path
from datetime import datetime
from sqlmodel import Session, select
from app.db import engine
from app.models_shared import SystemEndpoint, MessageLog
from app.services.transport_inbound import on_message_inbound_async


ARCHIVE_DIRS = [
    Path("/home/nico/Travail/Fhir_MedBridgeData/Interfaces/Entrant/PAM/Archive"),
    Path("/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/pam_archive"),
    Path("/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/tests/exemples/pam_archive"),
]


async def import_all_archives():
    """Import all HL7 files from all three archive directories."""
    
    print("🔍 Scanning all archive directories...\n")
    
    # Collect all files
    all_files = []
    for archive_dir in ARCHIVE_DIRS:
        files = sorted(archive_dir.glob("*.hl7"))
        print(f"📁 {archive_dir.name}: {len(files)} files")
        all_files.extend(files)
    
    # Remove duplicates based on correlation_id (filename)
    unique_files = {}
    for file_path in all_files:
        correlation_id = file_path.stem
        if correlation_id not in unique_files:
            unique_files[correlation_id] = file_path
    
    files_to_import = sorted(unique_files.values(), key=lambda f: f.stem)
    total = len(files_to_import)
    
    print(f"\n📊 Total files: {len(all_files)}")
    print(f"📊 Unique files: {total}")
    print()
    
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
    
    # Process each file
    for i, file_path in enumerate(files_to_import, 1):
        correlation_id = file_path.stem
        
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
                    if i % 50 == 0:
                        print(f"✅ [{i}/{total}] Imported {correlation_id}")
                else:
                    error_count += 1
                    # Extract error message from ACK
                    error_msg = ack.split("|")[-1] if "|" in ack else "Unknown error"
                    if error_count <= 20 or i % 50 == 0:
                        print(f"⚠️  [{i}/{total}] {correlation_id}: {error_msg[:80]}")
        
        except Exception as e:
            error_count += 1
            if error_count <= 20:
                print(f"❌ [{i}/{total}] Exception importing {correlation_id}: {str(e)[:100]}")
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"📊 IMPORT SUMMARY")
    print(f"{'='*60}")
    print(f"Total unique files: {total}")
    print(f"✅ Imported:        {success_count} ({success_count*100.0/total:.1f}%)")
    print(f"❌ Errors:          {error_count} ({error_count*100.0/total:.1f}%)")
    print(f"{'='*60}")
    
    # Show final count in database
    with Session(engine) as session:
        total_messages = len(session.exec(select(MessageLog)).all())
        total_patients = len(session.exec(select(MessageLog)).all())
        print(f"\n📈 Total messages in database: {total_messages}")


if __name__ == "__main__":
    start = datetime.now()
    asyncio.run(import_all_archives())
    duration = (datetime.now() - start).total_seconds()
    print(f"\n⏱️  Duration: {duration:.1f}s")
