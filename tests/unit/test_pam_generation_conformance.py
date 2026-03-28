"""
PAM Generation Conformance Tests - Audit des messages IHE PAM générés.

Valide que les messages générés par `generate_pam_messages_for_dossier` 
sont conformes à la spécification IHE PAM France et HL7 v2.5.
"""
import pytest
from datetime import datetime, timezone
from sqlmodel import SQLModel, create_engine, Session

from app.db import get_next_sequence
from app.models import Patient, Dossier, Venue, Mouvement, DossierType
from app.services.pam import generate_pam_messages_for_dossier


def _create_memory_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


class TestPAMGenerationConformance:
    """Conformance tests for PAM message generation."""
    
    @staticmethod
    def _parse_message(msg: str):
        """Parse HL7 message into segments."""
        segments = {}
        for line in msg.split('\r'):
            if not line:
                continue
            parts = line.split('|')
            seg_type = parts[0]
            segments[seg_type] = parts
        return segments
    
    def test_pam_a01_admission_basic_structure(self):
        """Test that generated A01 message has required MSH/EVN/PID/PV1/ZBE segments."""
        engine = _create_memory_db()
        with Session(engine) as session:
            patient = Patient(
                family="DUPONT", given="ALICE", birth_date="1980-01-15", gender="F",
                identifier="PAT-TEST-001"
            )
            session.add(patient)
            session.flush()
            
            dossier = Dossier(
                dossier_seq=get_next_sequence(session, "dossier"),
                patient_id=patient.id,
                admit_time=datetime(2026, 3, 28, 10, 0, 0, tzinfo=timezone.utc),
                dossier_type=DossierType.HOSPITALISE
            )
            session.add(dossier)
            session.flush()
            
            venue = Venue(
                venue_seq=get_next_sequence(session, "venue"),
                dossier_id=dossier.id,
                start_time=datetime(2026, 3, 28, 10, 0, 0, tzinfo=timezone.utc),
                code="WARD-A", label="Ward A"
            )
            session.add(venue)
            session.flush()
            
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                when=datetime(2026, 3, 28, 10, 30, 0, tzinfo=timezone.utc),
                trigger_event="A01", type="ADT^A01",
                location="WARD-A^ROOM1", movement_type="admission", status="active"
            )
            session.add(mouvement)
            session.commit()
            
            messages = generate_pam_messages_for_dossier(dossier)
            assert messages, "No messages generated"
            
            msg = messages[0]
            segments = self._parse_message(msg)
            
            # Check required segments for A01
            assert "MSH" in segments, "MSH segment missing"
            assert "EVN" in segments, "EVN segment missing"
            assert "PID" in segments, "PID segment missing"
            assert "PV1" in segments, "PV1 segment missing"
            assert "ZBE" in segments, "ZBE segment missing"
    
    def test_msh_header_format(self):
        """Test MSH segment format and required fields."""
        engine = _create_memory_db()
        with Session(engine) as session:
            patient = Patient(family="DOE", given="JOHN", identifier="PAT-MSH-001")
            session.add(patient)
            session.flush()
            
            dossier = Dossier(
                dossier_seq=get_next_sequence(session, "dossier"),
                patient_id=patient.id,
                admit_time=datetime(2026, 3, 28, 10, 0, 0, tzinfo=timezone.utc),
                dossier_type=DossierType.HOSPITALISE
            )
            session.add(dossier)
            session.flush()
            
            venue = Venue(
                venue_seq=get_next_sequence(session, "venue"),
                dossier_id=dossier.id,
                start_time=datetime(2026, 3, 28, 10, 0, 0, tzinfo=timezone.utc),
                code="W1", label="W1"
            )
            session.add(venue)
            session.flush()
            
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                when=datetime.now(timezone.utc),
                trigger_event="A01", type="ADT^A01",
                location="W1", movement_type="admission", status="active"
            )
            session.add(mouvement)
            session.commit()
            
            messages = generate_pam_messages_for_dossier(dossier)
            msg = messages[0]
            segments = self._parse_message(msg)
            
            msh = segments["MSH"]
            # MSH-1: Field separator (should be |, but MSH has special format)
            assert msh[0] == "MSH", "Wrong segment type"
            # MSH-2: Encoding characters
            assert msh[1] == "^~\\&", f"Wrong encoding chars: {msh[1]}"
            # MSH-9: Message type (ADT^A01)
            assert "ADT^A01" in msh[8], f"Wrong message type: {msh[8]}"
            # MSH-10: Message control ID (should be non-empty)
            assert msh[9], "Message control ID is empty"
            # MSH-11: Processing ID (should be P)
            assert msh[10] == "P", f"Wrong processing ID: {msh[10]}"
            # MSH-12: Version (should be 2.5 or 2.5^FRA...)
            assert "2.5" in msh[11], f"Wrong version: {msh[11]}"
    
    def test_evt_event_segment_consistency(self):
        """Test EVN segment is consistent with MSH trigger."""
        engine = _create_memory_db()
        with Session(engine) as session:
            patient = Patient(family="SMITH", given="JANE", identifier="PAT-EVN-001")
            session.add(patient)
            session.flush()
            
            dossier = Dossier(
                dossier_seq=get_next_sequence(session, "dossier"),
                patient_id=patient.id,
                admit_time=datetime.now(timezone.utc),
                dossier_type=DossierType.HOSPITALISE
            )
            session.add(dossier)
            session.flush()
            
            venue = Venue(
                venue_seq=get_next_sequence(session, "venue"),
                dossier_id=dossier.id,
                start_time=datetime.now(timezone.utc),
                code="W2", label="W2"
            )
            session.add(venue)
            session.flush()
            
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                when=datetime.now(timezone.utc),
                trigger_event="A02", type="ADT^A02",
                location="W2", movement_type="transfer", status="active"
            )
            session.add(mouvement)
            session.commit()
            
            messages = generate_pam_messages_for_dossier(dossier)
            msg = messages[0]
            segments = self._parse_message(msg)
            
            msh = segments["MSH"]
            evn = segments["EVN"]
            
            # Extract trigger from MSH-9 and EVN-1
            msh_trigger = msh[8].split('^')[1] if '^' in msh[8] else ''
            evn_trigger = evn[1]
            
            assert msh_trigger == evn_trigger, \
                f"Trigger mismatch: MSH-9={msh_trigger}, EVN-1={evn_trigger}"
    
    def test_pid_patient_identifier_format(self):
        """Test PID-3 has correct CX format with patient identifier."""
        engine = _create_memory_db()
        with Session(engine) as session:
            patient = Patient(family="MARTIN", given="PAUL", identifier="PAT-PID-001")
            session.add(patient)
            session.flush()
            
            dossier = Dossier(
                dossier_seq=get_next_sequence(session, "dossier"),
                patient_id=patient.id,
                admit_time=datetime.now(timezone.utc),
                dossier_type=DossierType.HOSPITALISE
            )
            session.add(dossier)
            session.flush()
            
            venue = Venue(
                venue_seq=get_next_sequence(session, "venue"),
                dossier_id=dossier.id,
                start_time=datetime.now(timezone.utc),
                code="W3", label="W3"
            )
            session.add(venue)
            session.flush()
            
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                when=datetime.now(timezone.utc),
                trigger_event="A01", type="ADT^A01",
                location="W3", movement_type="admission", status="active"
            )
            session.add(mouvement)
            session.commit()
            
            messages = generate_pam_messages_for_dossier(dossier)
            msg = messages[0]
            segments = self._parse_message(msg)
            
            pid = segments["PID"]
            pid_3 = pid[3]  # PID-3: Patient identifier
            
            assert pid_3, "PID-3 (patient identifier) is empty"
            # Should contain patient identifier value
            assert "PAT-PID-001" in pid_3, \
                f"Patient identifier not found in PID-3: {pid_3}"
    
    def test_pid_demographic_fields(self):
        """Test PID segment includes demographic fields (name, DOB, gender)."""
        engine = _create_memory_db()
        with Session(engine) as session:
            patient = Patient(
                family="LEBLANC", given="MARIE",
                birth_date="1995-06-22", gender="F",
                identifier="PAT-DEMO-001"
            )
            session.add(patient)
            session.flush()
            
            dossier = Dossier(
                dossier_seq=get_next_sequence(session, "dossier"),
                patient_id=patient.id,
                admit_time=datetime.now(timezone.utc),
                dossier_type=DossierType.HOSPITALISE
            )
            session.add(dossier)
            session.flush()
            
            venue = Venue(
                venue_seq=get_next_sequence(session, "venue"),
                dossier_id=dossier.id,
                start_time=datetime.now(timezone.utc),
                code="W4", label="W4"
            )
            session.add(venue)
            session.flush()
            
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                when=datetime.now(timezone.utc),
                trigger_event="A01", type="ADT^A01",
                location="W4", movement_type="admission", status="active"
            )
            session.add(mouvement)
            session.commit()
            
            messages = generate_pam_messages_for_dossier(dossier)
            msg = messages[0]
            segments = self._parse_message(msg)
            
            pid = segments["PID"]
            pid_5 = pid[5]  # PID-5: Name
            pid_7 = pid[7]  # PID-7: Date of birth
            pid_8 = pid[8]  # PID-8: Gender
            
            # Check name format (Family^Given)
            assert "LEBLANC" in pid_5, f"Family name missing in PID-5: {pid_5}"
            assert "MARIE" in pid_5, f"Given name missing in PID-5: {pid_5}"
            
            # Check date of birth (YYYYMMDD format)
            assert "19950622" == pid_7, f"DOB format wrong in PID-7: {pid_7}"
            
            # Check gender
            assert pid_8 == "F", f"Gender wrong in PID-8: {pid_8}"
    
    def test_pv1_venue_location(self):
        """Test PV1-3 contains venue location."""
        engine = _create_memory_db()
        with Session(engine) as session:
            patient = Patient(family="TEST", given="VENUE", identifier="PAT-VEN-001")
            session.add(patient)
            session.flush()
            
            dossier = Dossier(
                dossier_seq=get_next_sequence(session, "dossier"),
                patient_id=patient.id,
                admit_time=datetime.now(timezone.utc),
                dossier_type=DossierType.HOSPITALISE
            )
            session.add(dossier)
            session.flush()
            
            venue = Venue(
                venue_seq=get_next_sequence(session, "venue"),
                dossier_id=dossier.id,
                start_time=datetime.now(timezone.utc),
                code="CARD-01", label="Cardiology Room 1"
            )
            session.add(venue)
            session.flush()
            
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                when=datetime.now(timezone.utc),
                trigger_event="A01", type="ADT^A01",
                location="CARD-01^ROOM1^BED1", movement_type="admission", status="active"
            )
            session.add(mouvement)
            session.commit()
            
            messages = generate_pam_messages_for_dossier(dossier)
            msg = messages[0]
            segments = self._parse_message(msg)
            
            pv1 = segments["PV1"]
            pv1_3 = pv1[3]  # PV1-3: Assigned patient location
            
            assert pv1_3, "PV1-3 (location) is empty"
            assert "CARD-01" in pv1_3, f"Location code missing in PV1-3: {pv1_3}"
    
    def test_zbe_movement_segment(self):
        """Test ZBE segment contains movement identifier and metadata."""
        engine = _create_memory_db()
        with Session(engine) as session:
            patient = Patient(family="ZBE", given="TEST", identifier="PAT-ZBE-001")
            session.add(patient)
            session.flush()
            
            dossier = Dossier(
                dossier_seq=get_next_sequence(session, "dossier"),
                patient_id=patient.id,
                admit_time=datetime.now(timezone.utc),
                dossier_type=DossierType.HOSPITALISE
            )
            session.add(dossier)
            session.flush()
            
            venue = Venue(
                venue_seq=get_next_sequence(session, "venue"),
                dossier_id=dossier.id,
                start_time=datetime.now(timezone.utc),
                code="ZBE-W", label="ZBE Ward"
            )
            session.add(venue)
            session.flush()
            
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                when=datetime.now(timezone.utc),
                trigger_event="A01", type="ADT^A01",
                location="ZBE-W", movement_type="admission", status="active"
            )
            session.add(mouvement)
            session.commit()
            
            messages = generate_pam_messages_for_dossier(dossier)
            msg = messages[0]
            segments = self._parse_message(msg)
            
            zbe = segments["ZBE"]
            zbe_1 = zbe[1]  # ZBE-1: Movement identifier
            zbe_2 = zbe[2]  # ZBE-2: Movement datetime
            zbe_4 = zbe[4]  # ZBE-4: Action
            zbe_5 = zbe[5]  # ZBE-5: Historic indicator
            
            assert zbe_1, "ZBE-1 (movement ID) is empty"
            assert zbe_2, "ZBE-2 (datetime) is empty"
            assert zbe_4 == "INSERT", f"ZBE-4 action should be INSERT, got: {zbe_4}"
            assert zbe_5 == "N", f"ZBE-5 historic indicator should be N, got: {zbe_5}"
    
    def test_no_none_strings_in_message(self):
        """Test that generated message does not contain literal 'None' strings."""
        engine = _create_memory_db()
        with Session(engine) as session:
            patient = Patient(family="NONEE", given="CHECK", identifier="PAT-NONE-001")
            session.add(patient)
            session.flush()
            
            dossier = Dossier(
                dossier_seq=get_next_sequence(session, "dossier"),
                patient_id=patient.id,
                admit_time=datetime.now(timezone.utc),
                dossier_type=DossierType.HOSPITALISE
            )
            session.add(dossier)
            session.flush()
            
            venue = Venue(
                venue_seq=get_next_sequence(session, "venue"),
                dossier_id=dossier.id,
                start_time=datetime.now(timezone.utc),
                code="NONE", label="None Test"
            )
            session.add(venue)
            session.flush()
            
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                when=datetime.now(timezone.utc),
                trigger_event="A01", type="ADT^A01",
                location="NONE", movement_type="admission", status="active"
            )
            session.add(mouvement)
            session.commit()
            
            messages = generate_pam_messages_for_dossier(dossier)
            msg = messages[0]
            
            # Check for literal "None" strings
            assert "|None|" not in msg, "Found |None| in message"
            assert msg.count("None") == 0, f"Found 'None' strings in message: {msg}"
    
    def test_message_uses_carriage_return_delimiter(self):
        """Test that segments are properly delimited with carriage return."""
        engine = _create_memory_db()
        with Session(engine) as session:
            patient = Patient(family="DELIM", given="TEST", identifier="PAT-DELIM-001")
            session.add(patient)
            session.flush()
            
            dossier = Dossier(
                dossier_seq=get_next_sequence(session, "dossier"),
                patient_id=patient.id,
                admit_time=datetime.now(timezone.utc),
                dossier_type=DossierType.HOSPITALISE
            )
            session.add(dossier)
            session.flush()
            
            venue = Venue(
                venue_seq=get_next_sequence(session, "venue"),
                dossier_id=dossier.id,
                start_time=datetime.now(timezone.utc),
                code="D", label="D"
            )
            session.add(venue)
            session.flush()
            
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                when=datetime.now(timezone.utc),
                trigger_event="A01", type="ADT^A01",
                location="D", movement_type="admission", status="active"
            )
            session.add(mouvement)
            session.commit()
            
            messages = generate_pam_messages_for_dossier(dossier)
            msg = messages[0]
            
            # Should contain \r separators
            assert '\r' in msg, "Message should use \\r as segment delimiter"
            
            # Should have multiple segments
            segments = msg.split('\r')
            assert len(segments) >= 5, f"Expected at least 5 segments, got {len(segments)}"
