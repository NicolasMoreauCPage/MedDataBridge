"""Tests des différents modes de génération d'identifiants."""
import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.models_structure_fhir import IdentifierNamespace
from app.models_identifiers import IdentifierType
from app.services.identifier_generator import (
    generate_identifier,
    generate_and_persist_identifier,
    IdentifierGenerationError,
)


def setup_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_prefix_override():
    """Test génération avec override de préfixe."""
    engine = setup_db()
    with Session(engine) as session:
        ns = IdentifierNamespace(
            name="Test IPP",
            system="urn:oid:1.2.3",
            type="IPP",
            prefix_pattern="9...",
            ght_context_id=1,
            is_active=True,
        )
        session.add(ns)
        session.commit()
        session.refresh(ns)

        # Override avec pattern différent
        val = generate_identifier(session, ns, IdentifierType.IPP, prefix_override="501....")
        assert val.startswith("501")
        assert len(val) == 7  # 501 + 4 digits


def test_range_mode():
    """Test génération en mode range."""
    engine = setup_db()
    with Session(engine) as session:
        ns = IdentifierNamespace(
            name="Test Range",
            system="urn:oid:1.2.3",
            type="NDA",
            prefix_mode="range",
            prefix_min=9000000,
            prefix_max=9000099,
            ght_context_id=1,
            is_active=True,
        )
        session.add(ns)
        session.commit()
        session.refresh(ns)

        # Générer avec persistence atomique pour éviter collisions
        values = [generate_and_persist_identifier(session, ns, IdentifierType.NDA) for _ in range(10)]
        
        # Tous dans la plage
        for val in values:
            num = int(val)
            assert 9000000 <= num <= 9000099
        
        # Tous uniques
        assert len(values) == len(set(values))


def test_sequential_fallback():
    """Test mode séquentiel (pas de pattern ni range)."""
    engine = setup_db()
    with Session(engine) as session:
        ns = IdentifierNamespace(
            name="Test Sequential",
            system="urn:oid:1.2.3",
            type="VN",
            ght_context_id=1,
            is_active=True,
        )
        session.add(ns)
        session.commit()
        session.refresh(ns)

        # Premier devrait être "1000"
        val1 = generate_and_persist_identifier(session, ns, IdentifierType.VN)
        assert val1 == "1000"

        # Suivant incrémenté
        val2 = generate_and_persist_identifier(session, ns, IdentifierType.VN)
        assert val2 == "1001"


def test_pattern_exhaustion():
    """Test détection épuisement pattern très limité."""
    engine = setup_db()
    with Session(engine) as session:
        ns = IdentifierNamespace(
            name="Test Tiny",
            system="urn:oid:1.2.3",
            type="IPP",
            prefix_pattern="9.",  # Seulement 10 valeurs possibles (90-99)
            ght_context_id=1,
            is_active=True,
        )
        session.add(ns)
        session.commit()
        session.refresh(ns)

        # Générer 10 identifiants devrait réussir
        for _ in range(10):
            generate_and_persist_identifier(session, ns, IdentifierType.IPP)
        
        # Le 11ème devrait échouer (après max_attempts)
        with pytest.raises(IdentifierGenerationError, match="Impossible de générer identifiant unique"):
            generate_and_persist_identifier(session, ns, IdentifierType.IPP)


def test_range_exhaustion():
    """Test détection épuisement plage limitée."""
    engine = setup_db()
    with Session(engine) as session:
        ns = IdentifierNamespace(
            name="Test Narrow Range",
            system="urn:oid:1.2.3",
            type="NDA",
            prefix_mode="range",
            prefix_min=100,
            prefix_max=104,  # Seulement 5 valeurs (100,101,102,103,104)
            ght_context_id=1,
            is_active=True,
        )
        session.add(ns)
        session.commit()
        session.refresh(ns)

        # 5 identifiants OK
        for _ in range(5):
            generate_and_persist_identifier(session, ns, IdentifierType.NDA)
        
        # Le 6ème échoue
        with pytest.raises(IdentifierGenerationError, match="Impossible de générer identifiant unique dans plage"):
            generate_and_persist_identifier(session, ns, IdentifierType.NDA)


def test_invalid_pattern():
    """Test rejet pattern invalide."""
    engine = setup_db()
    with Session(engine) as session:
        ns = IdentifierNamespace(
            name="Test Invalid",
            system="urn:oid:1.2.3",
            type="IPP",
            prefix_pattern="ABC...",  # Non-digit prefix
            ght_context_id=1,
            is_active=True,
        )
        session.add(ns)
        session.commit()
        session.refresh(ns)

        with pytest.raises(IdentifierGenerationError, match="doit contenir uniquement des chiffres"):
            generate_identifier(session, ns, IdentifierType.IPP)


def test_no_variability_pattern():
    """Test rejet pattern sans points (pas de génération possible)."""
    engine = setup_db()
    with Session(engine) as session:
        ns = IdentifierNamespace(
            name="Test Fixed",
            system="urn:oid:1.2.3",
            type="IPP",
            prefix_pattern="9001234",  # Pas de points
            ght_context_id=1,
            is_active=True,
        )
        session.add(ns)
        session.commit()
        session.refresh(ns)

        with pytest.raises(IdentifierGenerationError, match="ne permet pas de génération"):
            generate_identifier(session, ns, IdentifierType.IPP)
