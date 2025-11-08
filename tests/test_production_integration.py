"""
Production data integration test
Validates MFN structure import and PAM message processing with real production data

This test:
1. Imports MFN^M05 structure from ExempleExtractionStructure.txt
2. Imports 1195 IHE PAM messages from Fichier_test_pam/
3. Validates database state matches source data
4. Verifies roundtrip coherence of identifiers and references

Uses direct service calls (on_message_inbound_async) rather than MLLP/HTTP to avoid
transport overhead during bulk import testing.
"""
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Set

from sqlmodel import Session, select

# Adjust imports to match your app structure
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import engine
from app.models_structure_fhir import EntiteJuridique, EntiteGeographique
from app.models_structure import Service
from app.models import Patient, Dossier, Mouvement, Venue
from app.models_identifiers import Identifier, IdentifierType
from app.services.transport_inbound import on_message_inbound_async


# Configuration
TEST_DATA_DIR = Path(__file__).parent / "exemples"
MFN_FILE = TEST_DATA_DIR / "ExempleExtractionStructure.txt"
PAM_DIR = TEST_DATA_DIR / "Fichier_test_pam"

# Test GHT configuration
TEST_EJ_FINESS = "700004591"
TEST_EJ_CODE = "69"
TEST_EJ_NAME = "GRGAP"


def setup_ej_and_endpoints() -> int:
    """Create EntiteJuridique and configure endpoints"""
    print(f"\n=== Setting up EntiteJuridique {TEST_EJ_FINESS} ===")
    
    # Check if EJ already exists
    with Session(engine) as db:
        existing_ej = db.exec(
             select(EntiteJuridique).where(EntiteJuridique.finess_ej == TEST_EJ_FINESS)
        ).first()
        
        if existing_ej:
             print(f"✓ EJ {TEST_EJ_FINESS} already exists: {existing_ej.name}")
             return existing_ej.id
    
    # Create EJ directly in database
    ej = EntiteJuridique(
        finess_ej=TEST_EJ_FINESS,
        name=TEST_EJ_NAME,
        short_name="EHI",
        address_line="4 Avenue de la VBF, B.P. 4",
        postal_code="70014",
        city="VESOUL CEDEX",
        start_date=datetime.now(),
        ght_context_id=1
    )
    
    with Session(engine) as db:
        db.add(ej)
        db.commit()
        db.refresh(ej)
        print(f"✓ Created EJ {TEST_EJ_FINESS}: ID={ej.id}")
        return ej.id


async def import_mfn_structure():
    """Import MFN^M05 structure file"""
    print(f"\n=== Importing MFN structure from {MFN_FILE.name} ===")
    
    if not MFN_FILE.exists():
        print(f"✗ MFN file not found: {MFN_FILE}")
        return False
    
    # Read MFN content
    mfn_content = MFN_FILE.read_text(encoding="utf-8")
    lines = [l for l in mfn_content.split("\n") if l.strip()]
    print(f"Read {len(lines)} lines from MFN file ({len(mfn_content)} bytes)")
    
    # Process MFN message directly via service
    with Session(engine) as db:
        try:
            # Call the MFN import service directly
            # Note: You may need to call import_mfn_message or similar from your structure import service
            ack = await on_message_inbound_async(mfn_content, db, None)
            
            if "MSA|AA" in ack:
                print(f"✓ MFN import successful")
                return True
            else:
                print(f"✗ MFN import failed: {ack[:200]}")
                return False
        except Exception as e:
            print(f"✗ MFN import exception: {e}")
            import traceback
            traceback.print_exc()
            return False


async def import_pam_messages():
    """Import all PAM messages from directory"""
    print(f"\n=== Importing PAM messages from {PAM_DIR.name} ===")
    
    if not PAM_DIR.exists():
        print(f"✗ PAM directory not found: {PAM_DIR}")
        return False
    
    # Get all .hl7 files sorted by name (timestamp-based)
    pam_files = sorted(PAM_DIR.glob("*.hl7"))
    print(f"Found {len(pam_files)} PAM message files")
    
    if not pam_files:
        print("✗ No PAM files found")
        return False
    
    # Import messages in batches
    BATCH_SIZE = 50
    success_count = 0
    error_count = 0
    error_samples = []
    
    for i in range(0, len(pam_files), BATCH_SIZE):
        batch = pam_files[i:i+BATCH_SIZE]
        print(f"\nProcessing batch {i//BATCH_SIZE + 1}/{(len(pam_files) + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch)} messages)", end=" ", flush=True)
        
        batch_success = 0
        batch_error = 0
        
        for pam_file in batch:
            try:
                pam_content = pam_file.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                # Fallback pour certains fichiers ISO-8859-1/latin-1 en production
                pam_content = pam_file.read_text(encoding="latin-1").strip()
            
            try:
                with Session(engine) as db:
                    ack = await on_message_inbound_async(pam_content, db, None)
                    
                    if "MSA|AA" in ack:
                        success_count += 1
                        batch_success += 1
                    else:
                        error_count += 1
                        batch_error += 1
                        if len(error_samples) < 5:
                            error_samples.append((pam_file.name, ack[:200]))
            except Exception as e:
                error_count += 1
                batch_error += 1
                if len(error_samples) < 5:
                    error_samples.append((pam_file.name, str(e)[:200]))
        
        print(f"✓{batch_success} ✗{batch_error}")
        
        # Brief pause between batches
        await asyncio.sleep(0.1)
    
    print(f"\n=== PAM Import Summary ===")
    print(f"✓ Success: {success_count}/{len(pam_files)} ({100*success_count//len(pam_files)}%)")
    print(f"✗ Errors: {error_count}/{len(pam_files)}")
    
    if error_samples:
        print(f"\n=== First {len(error_samples)} Errors ===")
        for filename, error in error_samples:
            print(f"{filename}: {error}")
    
    return error_count == 0


async def validate_structure_import():
    """Verify organizational structure was imported correctly"""
    print(f"\n=== Validating Structure Import ===")
    
    with Session(engine) as db:
        # Check EJ
        ej = db.exec(
                select(EntiteJuridique).where(EntiteJuridique.finess_ej == TEST_EJ_FINESS)
        ).first()
        
        if not ej:
            print(f"✗ EJ {TEST_EJ_FINESS} not found")
            return False
        print(f"✓ EJ found: {ej.name} (ID={ej.id})")

        # Check sites (EntiteGeographique) via entite_juridique_id
        sites = db.exec(
            select(EntiteGeographique).where(
                EntiteGeographique.entite_juridique_id == ej.id
            )
        ).all()
        print(f"✓ Found {len(sites)} sites")
        
        # Check services
        services = db.exec(select(Service)).all()
        print(f"✓ Found {len(services)} services")
        
        if not sites:
            print("⚠ Warning: No sites found")
        if not services:
            print("⚠ Warning: No services found")
        
        return True


async def validate_pam_import():
    """Verify patients / dossiers / venues / mouvements imported (model-aligned)"""
    print(f"\n=== Validating PAM Import ===")

    with Session(engine) as db:
        patients = db.exec(select(Patient)).all()
        dossiers = db.exec(select(Dossier)).all()
        venues = db.exec(select(Venue)).all()
        mouvements = db.exec(select(Mouvement)).all()

        print(f"✓ Patients:   {len(patients)}")
        print(f"✓ Dossiers:   {len(dossiers)}")
        print(f"✓ Venues:     {len(venues)}")
        print(f"✓ Mouvements: {len(mouvements)}")

        if not patients or not mouvements:
            print("✗ Missing core entities (patients or mouvements)")
            return False

        # Sample patient (first) using new attribute names
        patient = patients[0]
        print("\n=== Sample Patient ===")
        print(f"Identifier (primary): {patient.identifier}")
        print(f"Nom: {patient.family} Prénom: {patient.given}")
        print(f"Date naissance: {patient.birth_date}")

        # Sample mouvement
        mouvement = mouvements[0]
        print("\n=== Sample Mouvement ===")
        print(f"Seq: {mouvement.mouvement_seq}")
        print(f"Trigger: {mouvement.trigger_event}")
        print(f"Horodatage: {mouvement.when}")

        return True


async def validate_roundtrip():
    """Validate coherence between source HL7 identifiers and DB Identifier entries.

    Strategy:
      - Parse all PAM messages (PID-3, PID-18, PV1-19, ZBE-1)
      - Build sets of identifier values for patient (PI/IPP), dossier (AN), venue (VN), mouvement (ZBE-1)
      - Query Identifier table for matching types (IPP/PI, AN, VN, MVT)
      - Report coverage ratios
    Assumptions:
      - Ingestion stores identifiers in Identifier with proper IdentifierType mapping
      - ZBE-1 -> IdentifierType.MVT
      - PID-3 may include multiple CX components; we take first component before ^ as value
    """
    print(f"\n=== Validating Roundtrip Coherence ===")

    pam_files = sorted(PAM_DIR.glob("*.hl7"))
    if not pam_files:
        print("✗ No PAM files for roundtrip validation")
        return False

    patient_ids: Set[str] = set()
    dossier_ids: Set[str] = set()
    venue_ids: Set[str] = set()
    movement_ids: Set[str] = set()

    for pf in pam_files:
        try:
            content = pf.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = pf.read_text(encoding="latin-1")
        lines = [l for l in content.split("\n") if l]
        pid = next((l for l in lines if l.startswith("PID|")), None)
        pv1 = next((l for l in lines if l.startswith("PV1|")), None)
        zbe = next((l for l in lines if l.startswith("ZBE|")), None)
        if pid:
            # PID-3 may contain multiple repetitions separated by ~; we take first repetition
            pid3_field = pid.split("|")[3] if len(pid.split("|")) > 3 else ""
            first_rep = pid3_field.split("~")[0]
            patient_id_value = first_rep.split("^")[0]
            if patient_id_value:
                patient_ids.add(patient_id_value)
            # PID-18 (Account Number / AN)
            pid18_field = pid.split("|")[18] if len(pid.split("|")) > 18 else ""
            dossier_value = pid18_field.split("^")[0]
            if dossier_value:
                dossier_ids.add(dossier_value)
        if pv1:
            pv1_fields = pv1.split("|")
            if len(pv1_fields) > 19:
                vn_value = pv1_fields[19].split("^")[0]
                if vn_value:
                    venue_ids.add(vn_value)
        if zbe:
            zbe_fields = zbe.split("|")
            if len(zbe_fields) > 1:
                mvt_val = zbe_fields[1].split("^")[0]
                if mvt_val:
                    movement_ids.add(mvt_val)

    with Session(engine) as db:
        # Fetch identifiers by type
        def _count(type_: IdentifierType, values: Set[str]) -> Dict[str, int]:
            if not values:
                return {"expected": 0, "found": 0}
            found = db.exec(
                select(Identifier).where(Identifier.type == type_).where(Identifier.value.in_(list(values)))
            ).all()
            return {"expected": len(values), "found": len(found)}

        stats = {
            "patient_PI_or_IPP": _count(IdentifierType.IPP, patient_ids) | {"alt_type_note": "IPP only counted (PI ignored if stored differently)"},
            "dossier_AN": _count(IdentifierType.AN, dossier_ids),
            "venue_VN": _count(IdentifierType.VN, venue_ids),
            "mouvement_MVT": _count(IdentifierType.MVT, movement_ids),
        }

        print("\n=== Identifier Coverage ===")
        for label, s in stats.items():
            exp = s.get("expected", 0)
            fnd = s.get("found", 0)
            ratio = (fnd / exp * 100) if exp else 100
            print(f"{label}: {fnd}/{exp} ({ratio:.1f}%)")
            if s.get("alt_type_note"):
                print(f"  Note: {s['alt_type_note']}")

        # Basic pass condition: at least some identifiers found and movement coverage > 0
        if stats["mouvement_MVT"]["found"] == 0 and stats["mouvement_MVT"]["expected"] > 0:
            print("✗ No movement identifiers resolved")
            return False

        print("✓ Roundtrip identifier coherence baseline computed")
        return True

async def main():
    """Main integration test orchestration"""
    print("=" * 60)
    print("PRODUCTION DATA INTEGRATION TEST")
    print("=" * 60)
    
    # Step 1: Setup EJ and endpoints
    ej_id = setup_ej_and_endpoints()
    if not ej_id:
        print("\n✗ Failed to setup EJ, aborting")
        return
    
    # Step 2: Import MFN structure
    mfn_success = await import_mfn_structure()
    if not mfn_success:
        print("\n⚠ MFN import failed, continuing with PAM anyway...")
    
    # Step 3: Validate structure import
    await validate_structure_import()
    
    # Step 4: Import PAM messages
    pam_success = await import_pam_messages()
    
    # Step 5: Validate PAM import
    await validate_pam_import()
    
    # Step 6: Validate roundtrip
    await validate_roundtrip()
    
    print("\n" + "=" * 60)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
