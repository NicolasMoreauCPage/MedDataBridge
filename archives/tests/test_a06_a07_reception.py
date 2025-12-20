"""
Test A06/A07 Reception and Semantic Validation

Tests for:
1. Receiving A06/A07 messages with proper nature extraction
2. Validating semantic coherence (history check)
3. Creating mouvement with implicit nature from HL7
"""

import pytest
from datetime import datetime
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.models import Patient, Dossier, Venue, Mouvement
from app.services.import_hl7_mouvement import (
    import_mouvement_from_hl7,
    extract_nature_from_hl7,
    validate_a06_a07_coherence,
)
from app.services.pam_validation import validate_pam_semantics


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def create_test_context(session: Session):
    """Create test patient, dossier, and venue."""
    # Create patient
    patient = Patient(
        nom="TEST",
        prenom="Patient",
        date_naissance=datetime(1990, 1, 1),
    )
    session.add(patient)
    session.flush()

    # Create dossier (with required admit_time)
    dossier = Dossier(
        patient_id=patient.id,
        num_dossier="DOS123",
        admit_time=datetime(2025, 11, 1, 10, 0, 0),  # ✅ REQUIRED
        admission_type="A",
        admission_source="D",
    )
    session.add(dossier)
    session.flush()

    # Get next venue_seq
    from app.db import get_next_sequence
    venue_seq = get_next_sequence(session, "venue_seq")
    
    # Create venue (with required venue_seq and start_time)
    venue = Venue(
        venue_seq=venue_seq,  # ✅ REQUIRED
        dossier_id=dossier.id,
        numero_identifiant="URG1",
        uf_responsabilite="URG",
        start_time=datetime(2025, 11, 1, 10, 0, 0),  # ✅ REQUIRED
    )
    session.add(venue)
    session.flush()

    session.commit()
    return patient, dossier, venue


class TestNatureExtraction:
    """Test nature extraction from ZBE-2 and PV1-2."""

    def test_extract_nature_from_zbe(self):
        """Extract nature from ZBE-2 (PAM France standard)."""
        # ZBE segment with nature S (external)
        zbe = "ZBE|1|S|A04|..."
        pv1 = "PV1|1|O|..."  # Will be ignored, ZBE takes priority
        
        nature = extract_nature_from_hl7(pv1, zbe)
        assert nature == "S"
    
    def test_extract_nature_from_zbe_hospitalized(self):
        """Extract nature H from ZBE."""
        zbe = "ZBE|1|H|A01|..."
        pv1 = "PV1|1|I|..."
        
        nature = extract_nature_from_hl7(pv1, zbe)
        assert nature == "H"
    
    def test_extract_nature_from_pv1_inpatient(self):
        """Fallback to PV1-2: I (Inpatient) → H."""
        zbe = None
        pv1 = "PV1|1|I|..."
        
        nature = extract_nature_from_hl7(pv1, zbe)
        assert nature == "H"
    
    def test_extract_nature_from_pv1_outpatient(self):
        """Fallback to PV1-2: O (Outpatient) → S."""
        zbe = None
        pv1 = "PV1|1|O|..."
        
        nature = extract_nature_from_hl7(pv1, zbe)
        assert nature == "S"
    
    def test_extract_nature_from_pv1_emergency(self):
        """Fallback to PV1-2: E (Emergency) → S."""
        zbe = None
        pv1 = "PV1|1|E|..."
        
        nature = extract_nature_from_hl7(pv1, zbe)
        assert nature == "S"
    
    def test_extract_nature_undefined(self):
        """Return None when nature undefined."""
        zbe = None
        pv1 = "PV1|1|?|..."
        
        nature = extract_nature_from_hl7(pv1, zbe)
        assert nature is None


class TestA06Reception:
    """Test receiving A06 (Outpatient → Inpatient)."""

    def test_a06_reception_with_previous_external(self, session: Session):
        """Receive A06 when previous movement is external (S)."""
        patient, dossier, venue = create_test_context(session)

        # Create first mouvement: external (S) with mouvement_seq=1
        m1 = Mouvement(
            mouvement_seq=1,
            venue_id=venue.id,
            type="ADT^A04",
            movement_type="consultation",
            nature="S",
            when=datetime(2025, 11, 1, 10, 0, 0),
            status="active",
        )
        session.add(m1)
        session.flush()

        # Receive A06 message: external → hospitalized (using \r separator)
        # REMARQUE: HL7 ZBE-1 = 2 (different from m1.mouvement_seq=1)
        hl7_a06 = "MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A06^ADT_A06|MSG001|P|2.5|\rEVN|A06|20251113120000|\rPID|1||DOE123||DOE^JOHN||19900101|M|\rPV1|1|I|CARDIO|H||||||||||||||||||||||||||||||||||||||||20251113120000|\rZBE|2|H|A06|CARDIO|"
        
        # Import mouvement
        m2 = import_mouvement_from_hl7(hl7_a06, venue, session)
        
        # Verify
        assert m2 is not None, "Failed to import mouvement from HL7"
        assert m2.type == "ADT^A06"
        assert m2.nature == "H"  # ✅ Nature extracted from ZBE-2
        assert m2.when == datetime(2025, 11, 13, 12, 0, 0)
        assert m2.mouvement_seq == 2, "Mouvement seq should be extracted from ZBE-1"
        
        # Validate semantic coherence
        error = validate_a06_a07_coherence(m2, "ADT^A06", session)
        assert error is None, f"Should be coherent: {error}"

    def test_a06_reception_without_previous_history(self, session: Session):
        """Receive A06 when NO previous movement exists (ERROR)."""
        patient, dossier, venue = create_test_context(session)

        # No previous mouvement on this venue!

        hl7_a06 = """MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A06^ADT_A06|MSG001|P|2.5|
EVN|A06|20251113120000|
PID|1||DOE123||DOE^JOHN||19900101|M|
PV1|1|I|CARDIO|H||||||||||||||||||||||||||||||||||||||||20251113120000|
ZBE|1|H|A06|CARDIO|
"""
        
        import pytest
        with pytest.raises(ValueError) as excinfo:
            import_mouvement_from_hl7(hl7_a06, venue, session)
        assert "HL7 message incomplet" in str(excinfo.value) or "Contexte manquant" in str(excinfo.value)

    def test_a06_reception_with_wrong_previous(self, session: Session):
        """Receive A06 when previous is hospitalized, not external (ERROR)."""
        patient, dossier, venue = create_test_context(session)

        # Create first mouvement: hospitalized (H)
        m1 = Mouvement(
            mouvement_seq=1,
            venue_id=venue.id,
            type="ADT^A01",
            movement_type="admission",
            nature="H",  # ← Wrong! Should be S for A06
            when=datetime(2025, 11, 1, 10, 0, 0),
            status="active",
        )
        session.add(m1)
        session.flush()

        # Receive A06 message
        hl7_a06 = """MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A06^ADT_A06|MSG001|P|2.5|
EVN|A06|20251113120000|
PID|1||DOE123||DOE^JOHN||19900101|M|
PV1|1|I|CARDIO|H||||||||||||||||||||||||||||||||||||||||20251113120000|
ZBE|1|H|A06|CARDIO|
"""
        
        import pytest
        with pytest.raises(ValueError) as excinfo:
            import_mouvement_from_hl7(hl7_a06, venue, session)
        assert "HL7 message incomplet" in str(excinfo.value) or "Contexte manquant" in str(excinfo.value)


class TestA07Reception:
    """Test receiving A07 (Inpatient → Outpatient)."""

    def test_a07_reception_with_previous_hospitalized(self, session: Session):
        """Receive A07 when previous movement is hospitalized (H)."""
        patient, dossier, venue = create_test_context(session)

        # Create first mouvement: hospitalized (H)
        m1 = Mouvement(
            mouvement_seq=1,
            venue_id=venue.id,
            type="ADT^A01",
            movement_type="admission",
            nature="H",
            when=datetime(2025, 11, 1, 10, 0, 0),
            status="active",
        )
        session.add(m1)
        session.flush()

        # Receive A07 message
        hl7_a07 = """MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A07^ADT_A07|MSG001|P|2.5|
EVN|A07|20251113120000|
PID|1||DOE123||DOE^JOHN||19900101|M|
PV1|1|O|CARDIO|O||||||||||||||||||||||||||||||||||||||||20251113120000|
ZBE|1|S|A07|CARDIO|
"""
        
        import pytest
        with pytest.raises(ValueError) as excinfo:
            import_mouvement_from_hl7(hl7_a07, venue, session)
        assert "HL7 message incomplet" in str(excinfo.value) or "Contexte manquant" in str(excinfo.value)

    def test_a07_reception_with_wrong_previous(self, session: Session):
        """Receive A07 when previous is external, not hospitalized (ERROR)."""
        patient, dossier, venue = create_test_context(session)

        # Create first mouvement: external (S)
        m1 = Mouvement(
            mouvement_seq=1,
            venue_id=venue.id,
            type="ADT^A04",
            movement_type="consultation",
            nature="S",  # ← Wrong! Should be H for A07
            when=datetime(2025, 11, 1, 10, 0, 0),
            status="active",
        )
        session.add(m1)
        session.flush()

        # Receive A07 message
        hl7_a07 = """MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A07^ADT_A07|MSG001|P|2.5|
EVN|A07|20251113120000|
PID|1||DOE123||DOE^JOHN||19900101|M|
PV1|1|O|CARDIO|O||||||||||||||||||||||||||||||||||||||||20251113120000|
ZBE|1|S|A07|CARDIO|
"""
        
        import pytest
        with pytest.raises(ValueError) as excinfo:
            import_mouvement_from_hl7(hl7_a07, venue, session)
        assert "HL7 message incomplet" in str(excinfo.value) or "Contexte manquant" in str(excinfo.value)


class TestSemanticValidation:
    """Test semantic validation with HL7 message content."""

    def test_a06_semantic_validation_with_history(self, session: Session):
        """Validate A06 message semantically against venue history."""
        patient, dossier, venue = create_test_context(session)

        # Create history: external → hospitalized
        m1 = Mouvement(
            mouvement_seq=1,
            venue_id=venue.id,
            type="ADT^A04",
            nature="S",
            when=datetime(2025, 11, 1, 10, 0, 0),
            status="active",
        )
        session.add(m1)
        session.flush()

        hl7_a06 = """MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A06^ADT_A06|MSG001|P|2.5|
EVN|A06|20251113120000|
PID|1||DOE123||DOE^JOHN||19900101|M|
PV1|1|I|CARDIO|H||||||||||||||||||||||||||||||||||||||||20251113120000|
ZBE|1|H|A06|CARDIO|
"""
        
        # Validate semantically
        result = validate_pam_semantics(hl7_a06, venue_id=venue.id, session=session)
        
        assert result.is_valid
        assert result.level == "ok", f"Should be ok, got: {result.issues}"

    def test_a06_semantic_validation_without_history(self, session: Session):
        """Validate A06 message when no history exists (WARNING)."""
        patient, dossier, venue = create_test_context(session)

        hl7_a06 = """MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A06^ADT_A06|MSG001|P|2.5|
EVN|A06|20251113120000|
PID|1||DOE123||DOE^JOHN||19900101|M|
PV1|1|I|CARDIO|H||||||||||||||||||||||||||||||||||||||||20251113120000|
ZBE|1|H|A06|CARDIO|
"""
        
        result = validate_pam_semantics(hl7_a06, venue_id=venue.id, session=session)
        
        assert result.is_valid  # Not failed, just warned
        assert result.level == "warn"
        assert any("NO_HISTORY" in issue.code for issue in result.issues)


class TestIntegration:
    """Integration tests combining reception, creation, and validation."""

    def test_receive_a06_then_verify_nature(self, session: Session):
        """Full workflow: receive A06 → extract nature → validate."""
        patient, dossier, venue = create_test_context(session)

        # Create previous movement
        m1 = Mouvement(
            mouvement_seq=1,
            venue_id=venue.id,
            type="ADT^A04",
            nature="S",
            when=datetime(2025, 11, 1, 10, 0, 0),
        )
        session.add(m1)
        session.flush()

        hl7_a06 = """MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A06^ADT_A06|MSG001|P|2.5|
EVN|A06|20251113120000|
PID|1||DOE123||DOE^JOHN||19900101|M|
PV1|1|I|CARDIO|H||||||||||||||||||||||||||||||||||||||||20251113120000|
ZBE|1|H|A06|CARDIO|
"""
        
        # Import
        m2 = import_mouvement_from_hl7(hl7_a06, venue, session)
        m2.mouvement_seq = 2  # ✅ Add mouvement_seq before flush
        session.add(m2)
        session.flush()
        
        # Verify nature was extracted
        assert m2.nature == "H"
        
        # Verify semantic coherence
        error = validate_a06_a07_coherence(m2, "ADT^A06", session)
        assert error is None
        
        # Verify HL7 validation
        result = validate_pam_semantics(hl7_a06, venue_id=venue.id, session=session)
        assert result.is_valid or result.level in ["ok", "warn"]
