"""
Tests unitaires pour le service de génération d'identifiants avec préfixes.
"""

import pytest
from sqlmodel import Session, create_engine, SQLModel, select

from app.models_identifiers import Identifier, IdentifierType
from app.models_structure_fhir import IdentifierNamespace, GHTContext
from app.services.identifier_generator import (
    _parse_prefix_pattern,
    _generate_with_prefix_pattern,
    _generate_with_range,
    generate_identifier,
    generate_identifier_set,
    count_available_identifiers,
    IdentifierGenerationError
)


@pytest.fixture
def test_session():
    """Crée une session de test en mémoire."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def test_ght(test_session):
    """Crée un GHT de test."""
    ght = GHTContext(name="Test GHT", code="TEST", is_active=True)
    test_session.add(ght)
    test_session.commit()
    test_session.refresh(ght)
    return ght


@pytest.fixture
def ipp_namespace_pattern(test_session, test_ght):
    """Namespace IPP avec pattern de préfixe."""
    ns = IdentifierNamespace(
        name="IPP Test",
        system="urn:oid:1.2.3.4.5.1",
        type="IPP",
        prefix_pattern="9...",
        prefix_mode="fixed",
        ght_context_id=test_ght.id
    )
    test_session.add(ns)
    test_session.commit()
    test_session.refresh(ns)
    return ns


@pytest.fixture
def nda_namespace_range(test_session, test_ght):
    """Namespace NDA avec plage numérique."""
    ns = IdentifierNamespace(
        name="NDA Test",
        system="urn:oid:1.2.3.4.5.2",
        type="NDA",
        prefix_mode="range",
        prefix_min=501000,
        prefix_max=501999,
        ght_context_id=test_ght.id
    )
    test_session.add(ns)
    test_session.commit()
    test_session.refresh(ns)
    return ns


class TestPrefixPatternParsing:
    """Tests pour le parsing des patterns de préfixe."""
    
    def test_parse_simple_pattern(self):
        prefix, digits = _parse_prefix_pattern("9...")
        assert prefix == "9"
        assert digits == 3
    
    def test_parse_long_prefix(self):
        prefix, digits = _parse_prefix_pattern("91....")
        assert prefix == "91"
        assert digits == 4
    
    def test_parse_triple_digit_prefix(self):
        prefix, digits = _parse_prefix_pattern("501...")
        assert prefix == "501"
        assert digits == 3
    
    def test_parse_no_dots(self):
        prefix, digits = _parse_prefix_pattern("9000")
        assert prefix == "9000"
        assert digits == 0
    
    def test_parse_empty_raises(self):
        with pytest.raises(IdentifierGenerationError):
            _parse_prefix_pattern("")
    
    def test_parse_invalid_prefix_raises(self):
        with pytest.raises(IdentifierGenerationError):
            _parse_prefix_pattern("ABC...")


class TestPrefixPatternGeneration:
    """Tests pour la génération avec pattern de préfixe."""
    
    def test_generate_with_pattern(self, test_session, ipp_namespace_pattern):
        """Test génération basique avec pattern."""
        ident = _generate_with_prefix_pattern(
            session=test_session,
            pattern="9...",
            identifier_type=IdentifierType.IPP,
            namespace_system=ipp_namespace_pattern.system
        )
        
        assert ident.startswith("9")
        assert len(ident) == 4
        assert ident.isdigit()
        value = int(ident)
        assert 9000 <= value <= 9999
    
    def test_generate_avoids_collision(self, test_session, ipp_namespace_pattern):
        """Test évitement de collision."""
        # Créer un identifiant existant
        existing = Identifier(
            value="9123",
            type=IdentifierType.IPP,
            system=ipp_namespace_pattern.system,
            status="active"
        )
        test_session.add(existing)
        test_session.commit()
        
        # Générer 10 nouveaux identifiants
        generated = set()
        for _ in range(10):
            ident = _generate_with_prefix_pattern(
                session=test_session,
                pattern="9...",
                identifier_type=IdentifierType.IPP,
                namespace_system=ipp_namespace_pattern.system
            )
            generated.add(ident)
        
        # Vérifier qu'aucun n'est égal à l'existant
        assert "9123" not in generated
        # Vérifier qu'on a bien 10 identifiants différents
        assert len(generated) == 10
    
    def test_generate_no_dots_raises(self, test_session, ipp_namespace_pattern):
        """Test que pattern sans dots échoue."""
        with pytest.raises(IdentifierGenerationError):
            _generate_with_prefix_pattern(
                session=test_session,
                pattern="9000",
                identifier_type=IdentifierType.IPP,
                namespace_system=ipp_namespace_pattern.system
            )


class TestRangeGeneration:
    """Tests pour la génération avec plage numérique."""
    
    def test_generate_in_range(self, test_session, nda_namespace_range):
        """Test génération dans plage."""
        ident = _generate_with_range(
            session=test_session,
            min_val=501000,
            max_val=501999,
            identifier_type=IdentifierType.NDA,
            namespace_system=nda_namespace_range.system
        )
        
        value = int(ident)
        assert 501000 <= value <= 501999
    
    def test_generate_range_avoids_collision(self, test_session, nda_namespace_range):
        """Test évitement de collision dans plage."""
        # Créer un identifiant existant
        existing = Identifier(
            value="501500",
            type=IdentifierType.NDA,
            system=nda_namespace_range.system,
            status="active"
        )
        test_session.add(existing)
        test_session.commit()
        
        # Générer plusieurs identifiants
        generated = set()
        for _ in range(20):
            ident = _generate_with_range(
                session=test_session,
                min_val=501000,
                max_val=501999,
                identifier_type=IdentifierType.NDA,
                namespace_system=nda_namespace_range.system
            )
            generated.add(ident)
        
        # Vérifier exclusion
        assert "501500" not in generated
    
    def test_invalid_range_raises(self, test_session, nda_namespace_range):
        """Test que plage invalide échoue."""
        with pytest.raises(IdentifierGenerationError):
            _generate_with_range(
                session=test_session,
                min_val=501999,
                max_val=501000,  # min > max
                identifier_type=IdentifierType.NDA,
                namespace_system=nda_namespace_range.system
            )


class TestGenerateIdentifier:
    """Tests pour la fonction principale generate_identifier."""
    
    def test_generate_with_namespace_pattern(self, test_session, ipp_namespace_pattern):
        """Test génération avec namespace configuré pattern."""
        ident = generate_identifier(
            session=test_session,
            namespace=ipp_namespace_pattern,
            identifier_type=IdentifierType.IPP
        )
        
        assert ident.startswith("9")
        assert 4 == len(ident)
    
    def test_generate_with_namespace_range(self, test_session, nda_namespace_range):
        """Test génération avec namespace configuré range."""
        ident = generate_identifier(
            session=test_session,
            namespace=nda_namespace_range,
            identifier_type=IdentifierType.NDA
        )
        
        value = int(ident)
        assert 501000 <= value <= 501999
    
    def test_generate_with_prefix_override(self, test_session, ipp_namespace_pattern):
        """Test override de préfixe."""
        ident = generate_identifier(
            session=test_session,
            namespace=ipp_namespace_pattern,
            identifier_type=IdentifierType.IPP,
            prefix_override="91...."  # Override pattern de "9..." à "91...."
        )
        
        assert ident.startswith("91")
        assert 6 == len(ident)
    
    def test_generate_without_config_fallback(self, test_session, test_ght):
        """Test fallback si namespace sans configuration."""
        # Namespace sans prefix_pattern ni prefix_mode range
        ns = IdentifierNamespace(
            name="Simple NS",
            system="urn:oid:1.2.3.4.9",
            type="PI",
            ght_context_id=test_ght.id
        )
        test_session.add(ns)
        test_session.commit()
        
        ident = generate_identifier(
            session=test_session,
            namespace=ns,
            identifier_type=IdentifierType.PI
        )
        
        # Devrait retourner "1000" par défaut
        assert ident == "1000"


class TestGenerateIdentifierSet:
    """Tests pour la génération d'ensembles complets."""
    
    def test_generate_full_set(self, test_session, ipp_namespace_pattern, nda_namespace_range):
        """Test génération IPP + NDA."""
        ids = generate_identifier_set(
            session=test_session,
            ipp_namespace=ipp_namespace_pattern,
            nda_namespace=nda_namespace_range
        )
        
        assert 'ipp' in ids
        assert 'nda' in ids
        assert ids['ipp'].startswith("9")
        assert 501000 <= int(ids['nda']) <= 501999
    
    def test_generate_with_overrides(self, test_session, ipp_namespace_pattern, nda_namespace_range):
        """Test génération avec overrides."""
        ids = generate_identifier_set(
            session=test_session,
            ipp_namespace=ipp_namespace_pattern,
            nda_namespace=nda_namespace_range,
            ipp_prefix_override="8...",
            nda_prefix_override="502..."
        )
        
        assert ids['ipp'].startswith("8")
        assert ids['nda'].startswith("502")


class TestCountAvailableIdentifiers:
    """Tests pour le comptage d'identifiants disponibles."""
    
    def test_count_pattern(self, ipp_namespace_pattern):
        """Test comptage pour pattern."""
        count = count_available_identifiers(ipp_namespace_pattern)
        # Pattern "9..." donne 9000-9999 = 1000 possibilités
        assert count == 900  # 9999 - 9000 + 1 - 100 (car commence à 100)
    
    def test_count_range(self, nda_namespace_range):
        """Test comptage pour range."""
        count = count_available_identifiers(nda_namespace_range)
        # Range 501000-501999 = 1000 possibilités
        assert count == 1000
    
    def test_count_unlimited_returns_none(self, test_session, test_ght):
        """Test namespace sans config retourne None."""
        ns = IdentifierNamespace(
            name="Unlimited",
            system="urn:oid:1.2.3.4.10",
            type="PI",
            ght_context_id=test_ght.id
        )
        count = count_available_identifiers(ns)
        assert count is None
