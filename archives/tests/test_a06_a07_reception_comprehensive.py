"""
Test A06/A07 Reception - Comprehensive Suite

Tests complets pour:
1. Réception de messages A06/A07
2. Extraction de la nature depuis HL7
3. Validation sémantique de cohérence
"""

import pytest
import uuid
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
from app.db import get_next_sequence


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
    patient = Patient(
        nom="TEST",
        prenom="Patient",
        date_naissance=datetime(1990, 1, 1),
    )
    session.add(patient)
    session.flush()

    dossier = Dossier(
        patient_id=patient.id,
        num_dossier="DOS123",
        admit_time=datetime(2025, 11, 1, 10, 0, 0),
        admission_type="A",
        admission_source="D",
    )
    session.add(dossier)
    session.flush()

    venue_seq = get_next_sequence(session, "venue_seq")
    venue = Venue(
        venue_seq=venue_seq,
        dossier_id=dossier.id,
        uf_responsabilite="URG",
        start_time=datetime(2025, 11, 1, 10, 0, 0),
    )
    session.add(venue)
    session.flush()

    session.commit()
    return patient, dossier, venue


class TestA06Reception:
    """Test receiving A06 messages."""

    def test_a06_with_correct_history(self, session: Session):
        """A06 reçu avec historique correct (S avant)."""
        patient, dossier, venue = create_test_context(session)

        # Historique: mouvement externe (S)
        m1 = Mouvement(
            mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            venue_id=venue.id,
            type="ADT^A04",
            nature="S",
            when=datetime(2025, 11, 1, 10, 0, 0),
        )
        session.add(m1)
        session.flush()

        # Recevoir A06: externe → hospitalisé
        hl7_a06 = "MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A06^ADT_A06|MSG001|P|2.5|\rEVN|A06|20251113120000|\rPID|1||DOE123||DOE^JOHN||19900101|M|\rPV1|1|I|CARDIO|H||||||||||||||||||||||||||||||||||||||||20251113120000|\rZBE|2|H|A06|CARDIO|"
        
        m2 = import_mouvement_from_hl7(hl7_a06, venue, session)
        
        # Vérifications
        assert m2 is not None
        assert m2.type == "ADT^A06"
        assert m2.nature == "H"  # ✅ Nature extraite
        
        # Valider cohérence
        error = validate_a06_a07_coherence(m2, "ADT^A06", session)
        assert error is None, f"Erreur: {error}"

    def test_a06_without_history(self, session: Session):
        """A06 reçu SANS historique → ERREUR."""
        patient, dossier, venue = create_test_context(session)

        # PAS d'historique !
        hl7_a06 = "MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A06^ADT_A06|MSG001|P|2.5|\rEVN|A06|20251113120000|\rPID|1||DOE123||DOE^JOHN||19900101|M|\rPV1|1|I|CARDIO|H||||||||||||||||||||||||||||||||||||||||20251113120000|\rZBE|1|H|A06|CARDIO|"
        
        m = import_mouvement_from_hl7(hl7_a06, venue, session)
        assert m is not None
        
        # Validation doit échouer (pas d'historique)
        error = validate_a06_a07_coherence(m, "ADT^A06", session)
        assert error is not None
        assert "pas de mouvement antérieur" in error.lower()


class TestA07Reception:
    """Test receiving A07 messages."""

    def test_a07_with_correct_history(self, session: Session):
        """A07 reçu avec historique correct (H avant)."""
        patient, dossier, venue = create_test_context(session)

        # Historique: mouvement hospitalisé (H)
        m1 = Mouvement(
            mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            venue_id=venue.id,
            type="ADT^A01",
            nature="H",
            when=datetime(2025, 11, 1, 10, 0, 0),
        )
        session.add(m1)
        session.flush()

        # Recevoir A07: hospitalisé → externe
        hl7_a07 = "MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A07^ADT_A07|MSG001|P|2.5|\rEVN|A07|20251113120000|\rPID|1||DOE123||DOE^JOHN||19900101|M|\rPV1|1|O|CARDIO|O||||||||||||||||||||||||||||||||||||||||20251113120000|\rZBE|2|S|A07|CARDIO|"
        
        m2 = import_mouvement_from_hl7(hl7_a07, venue, session)
        
        # Vérifications
        assert m2 is not None
        assert m2.type == "ADT^A07"
        assert m2.nature == "S"  # ✅ Nature extraite
        
        # Valider cohérence
        error = validate_a06_a07_coherence(m2, "ADT^A07", session)
        assert error is None, f"Erreur: {error}"


class TestNatureExtraction:
    """Test nature extraction."""

    def test_extract_from_zbe(self):
        """ZBE-2 prend priorité."""
        zbe = "ZBE|1|H|A06|..."
        pv1 = "PV1|1|O|..."
        
        nature = extract_nature_from_hl7(pv1, zbe)
        assert nature == "H"

    def test_extract_from_pv1_fallback(self):
        """PV1-2 en fallback."""
        zbe = None
        pv1 = "PV1|1|I|..."
        
        nature = extract_nature_from_hl7(pv1, zbe)
        assert nature == "H"  # I → H


class TestSemanticValidation:
    """Test semantic validation."""

    def test_a06_validation_ok(self, session: Session):
        """A06 valide sémantiquement."""
        patient, dossier, venue = create_test_context(session)

        # Historique
        m1 = Mouvement(
            mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            venue_id=venue.id,
            nature="S",
            when=datetime(2025, 11, 1, 10, 0, 0),
        )
        session.add(m1)
        session.flush()

        hl7_a06 = "MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A06^ADT_A06|MSG001|P|2.5|\rEVN|A06|20251113120000|\rPID|1||DOE123||DOE^JOHN||19900101|M|\rPV1|1|I|CARDIO|H||||||||||||||||||||||||||||||||||||||||20251113120000|\rZBE|2|H|A06|CARDIO|"
        
        result = validate_pam_semantics(hl7_a06, venue_id=venue.id, session=session)
        
        assert result.is_valid
        assert result.level in ["ok", "warn"]


class TestWorkflowIntegration:
    """Integration workflow tests."""

    def test_full_a06_workflow(self, session: Session):
        """Workflow complet: import → validation."""
        patient, dossier, venue = create_test_context(session)

        # Historique
        m1 = Mouvement(
            mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            venue_id=venue.id,
            type="ADT^A04",
            nature="S",
            when=datetime(2025, 11, 1, 10, 0, 0),
        )
        session.add(m1)
        session.flush()

        # Recevoir A06
        hl7_a06 = "MSH|^~\\&|POC|HOSP|EXT|HOSP|20251113120000||ADT^A06^ADT_A06|MSG001|P|2.5|\rEVN|A06|20251113120000|\rPID|1||DOE123||DOE^JOHN||19900101|M|\rPV1|1|I|CARDIO|H||||||||||||||||||||||||||||||||||||||||20251113120000|\rZBE|2|H|A06|CARDIO|"
        
        # Import
        m2 = import_mouvement_from_hl7(hl7_a06, venue, session)
        assert m2 is not None
        assert m2.nature == "H"
        
        # Valider cohérence
        error = validate_a06_a07_coherence(m2, "ADT^A06", session)
        assert error is None
        
        # Valider sémantiquement
        result = validate_pam_semantics(hl7_a06, venue_id=venue.id, session=session)
        assert result.is_valid
