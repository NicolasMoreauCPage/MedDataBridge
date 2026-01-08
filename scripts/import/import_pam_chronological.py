#!/usr/bin/env python3
"""Import all HL7 messages from PAM archives in chronological order with auto-create UF."""
import asyncio
import os
from pathlib import Path
from datetime import datetime
from sqlmodel import Session, select
from app.db import engine
from app.models_shared import SystemEndpoint, MessageLog
from app.services.transport_inbound import on_message_inbound_async


# Enable auto-creation of missing UF structures
os.environ["PAM_AUTO_CREATE_UF"] = "1"


ARCHIVE_DIRS = [
    Path("/home/nico/Travail/Fhir_MedBridgeData/Interfaces/Entrant/PAM/Archive"),
    Path("/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/pam_archive"),
    Path("/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/tests/exemples/pam_archive"),
]


def extract_timestamp(message: str) -> datetime:
    """Extract timestamp from HL7 message (EVN-2 or MSH-7).
    
    Priority:
    1. EVN-2 (Recorded Date/Time) - most accurate for event time
    2. MSH-7 (Date/Time of Message) - fallback
    
    Returns datetime or epoch if parsing fails.
    """
    lines = message.split('\n')
    evn_timestamp = None
    msh_timestamp = None
    
    for line in lines:
        if line.startswith('EVN|'):
            # EVN|A01|20240115083045||
            parts = line.split('|')
            if len(parts) > 2 and parts[2]:
                evn_timestamp = parts[2]
                break  # EVN-2 is preferred, stop here
        elif line.startswith('MSH|'):
            # MSH|^~\&|PAM|CHU-LYON|...|||20240115083000||
            parts = line.split('|')
            if len(parts) > 6 and parts[6]:
                msh_timestamp = parts[6]
    
    # Try EVN-2 first, then MSH-7
    timestamp_str = evn_timestamp or msh_timestamp
    
    if not timestamp_str:
        # No timestamp found, return epoch
        return datetime(1970, 1, 1)
    
    # Parse HL7 timestamp: YYYYMMDDHHMMSS or YYYYMMDDHHMM or YYYYMMDD
    timestamp_str = timestamp_str.strip()
    
    try:
        if len(timestamp_str) >= 14:
            return datetime.strptime(timestamp_str[:14], '%Y%m%d%H%M%S')
        elif len(timestamp_str) >= 12:
            return datetime.strptime(timestamp_str[:12], '%Y%m%d%H%M')
        elif len(timestamp_str) >= 8:
            return datetime.strptime(timestamp_str[:8], '%Y%m%d')
        else:
            return datetime(1970, 1, 1)
    except ValueError:
        return datetime(1970, 1, 1)


async def import_all_archives_chronologically():
    """Import all HL7 files from all archives sorted by timestamp."""
    
    print("🔍 Scanning all archive directories...\n")
    print("⚙️  PAM_AUTO_CREATE_UF=1 enabled (missing UF will be auto-created)\n")
    
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
    
    print(f"\n📊 Total files: {len(all_files)}")
    print(f"📊 Unique files: {len(unique_files)}")
    
    # Parse timestamps and sort chronologically
    print("\n⏱️  Extracting timestamps and sorting chronologically...")
    
    files_with_timestamps = []
    for file_path in unique_files.values():
        try:
            message = file_path.read_text()
            timestamp = extract_timestamp(message)
            files_with_timestamps.append((timestamp, file_path, message))
        except Exception as e:
            print(f"⚠️  Error reading {file_path.name}: {e}")
            # Add with epoch timestamp
            files_with_timestamps.append((datetime(1970, 1, 1), file_path, None))
    
    # Sort by timestamp
    files_with_timestamps.sort(key=lambda x: x[0])
    
    # Show date range
    if files_with_timestamps:
        first_ts = files_with_timestamps[0][0]
        last_ts = files_with_timestamps[-1][0]
        print(f"📅 Date range: {first_ts.strftime('%Y-%m-%d %H:%M')} → {last_ts.strftime('%Y-%m-%d %H:%M')}")
    
    total = len(files_with_timestamps)
    print(f"\n🚀 Importing {total} messages in chronological order...\n")
    
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
    uf_created_count = 0
    
    # Process each file in chronological order
    for i, (timestamp, file_path, message) in enumerate(files_with_timestamps, 1):
        correlation_id = file_path.stem
        
        # Read message if not already loaded
        if message is None:
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
                    # Check if UF was auto-created (would appear in log)
                    if "UF Responsable" in ack and "créée" in ack:
                        uf_created_count += 1
                    
                    if i % 50 == 0:
                        print(f"✅ [{i}/{total}] {timestamp.strftime('%Y-%m-%d %H:%M')} - {correlation_id}")
                else:
                    error_count += 1
                    # Extract error message from ACK
                    error_msg = ack.split("|")[-1] if "|" in ack else "Unknown error"
                    if error_count <= 20 or i % 50 == 0:
                        print(f"⚠️  [{i}/{total}] {timestamp.strftime('%Y-%m-%d %H:%M')} - {correlation_id}: {error_msg[:80]}")
        
        except Exception as e:
            error_count += 1
            if error_count <= 20:
                print(f"❌ [{i}/{total}] {timestamp.strftime('%Y-%m-%d %H:%M')} - Exception: {str(e)[:100]}")
    
    # Final summary
    print(f"\n{'='*70}")
    print(f"📊 IMPORT SUMMARY (CHRONOLOGICAL)")
    print(f"{'='*70}")
    print(f"✅ Success: {success_count}")
    print(f"⚠️  Errors:  {error_count}")
    print(f"📁 Total:   {total}")
    print(f"🏥 UF auto-created: {uf_created_count}")
    print(f"{'='*70}")
    
    # Show database statistics
    with Session(engine) as session:
        message_count = session.exec(select(MessageLog)).all()
        print(f"\n📊 Database Statistics:")
        print(f"   Messages: {len(message_count)}")
        
        from app.models import Patient, Dossier, Venue, Mouvement
        patients = session.exec(select(Patient)).all()
        dossiers = session.exec(select(Dossier)).all()
        venues = session.exec(select(Venue)).all()
        mouvements = session.exec(select(Mouvement)).all()
        
        print(f"   Patients: {len(patients)}")
        print(f"   Dossiers: {len(dossiers)}")
        print(f"   Venues: {len(venues)}")
        print(f"   Mouvements: {len(mouvements)} 🎯")
        
        # Show movement types
        if mouvements:
            print(f"\n   Mouvement breakdown:")
            from collections import Counter
            movement_types = Counter([m.status for m in mouvements])
            for status, count in movement_types.items():
                print(f"      {status}: {count}")


if __name__ == "__main__":
    asyncio.run(import_all_archives_chronologically())
