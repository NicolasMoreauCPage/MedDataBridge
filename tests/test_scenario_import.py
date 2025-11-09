"""
Tests pour le service d'import de scénarios.
Vérifie la validation, gestion d'erreurs, et cas limites.
"""
import pytest
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_structure_fhir import GHTContext
from app.services.scenario_import import (
    import_scenario_from_json,
    validate_scenario_json,
    ScenarioImportError,
)


@pytest.fixture
def session():
    """Session de test avec base SQLite en mémoire."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Créer un contexte GHT pour les tests
        ctx = GHTContext(
            id=1,
            key="test-ght",
            name="GHT Test",
            organization_id="ORG-TEST",
            software_id="MDB-TEST"
        )
        session.add(ctx)
        session.commit()
        yield session


def test_validate_json_missing_required_fields():
    """Validation doit échouer si des champs requis manquent."""
    # Manque "name"
    json_data = {
        "key": "test-key",
        "protocol": "HL7v2",
        "steps": []
    }
    is_valid, error = validate_scenario_json(json_data)
    assert not is_valid
    assert "name" in error.lower()
    
    # Manque "key"
    json_data = {
        "name": "Test Scenario",
        "protocol": "HL7v2",
        "steps": []
    }
    is_valid, error = validate_scenario_json(json_data)
    assert not is_valid
    assert "key" in error.lower()
    
    # Manque "steps"
    json_data = {
        "key": "test-key",
        "name": "Test Scenario",
        "protocol": "HL7v2"
    }
    is_valid, error = validate_scenario_json(json_data)
    assert not is_valid
    assert "steps" in error.lower()


def test_validate_json_invalid_types():
    """Validation doit échouer si les types sont incorrects."""
    # steps doit être une liste
    json_data = {
        "key": "test-key",
        "name": "Test Scenario",
        "protocol": "HL7v2",
        "steps": "not a list"
    }
    is_valid, error = validate_scenario_json(json_data)
    assert not is_valid
    assert "steps" in error.lower() and "list" in error.lower()
    
    # time_config doit être un dict si présent (avec au moins un step)
    json_data = {
        "key": "test-key",
        "name": "Test Scenario",
        "protocol": "HL7v2",
        "steps": [
            {
                "order_index": 0,
                "message_type": "ADT^A01",
                "format": "HL7v2",
                "delay_seconds": 0,
                "payload": "MSH|..."
            }
        ],
        "time_config": "not a dict"
    }
    is_valid, error = validate_scenario_json(json_data)
    assert not is_valid
    assert "time_config" in error.lower()


def test_validate_json_invalid_step_structure():
    """Validation doit échouer si un step est mal formé."""
    json_data = {
        "key": "test-key",
        "name": "Test Scenario",
        "protocol": "HL7v2",
        "steps": [
            {
                # Manque order_index et payload
                "message_type": "ADT^A01",
                "format": "HL7v2"
            }
        ]
    }
    is_valid, error = validate_scenario_json(json_data)
    assert not is_valid
    assert "step" in error.lower()


def test_validate_json_valid_minimal():
    """Validation doit réussir avec structure minimale valide."""
    json_data = {
        "key": "test-key",
        "name": "Test Scenario",
        "protocol": "HL7v2",
        "steps": [
            {
                "order_index": 0,
                "message_type": "ADT^A01",
                "format": "HL7v2",
                "delay_seconds": 0,
                "payload": "MSH|^~\\&|..."
            }
        ]
    }
    is_valid, error = validate_scenario_json(json_data)
    assert is_valid
    assert error is None


def test_validate_json_valid_complete():
    """Validation doit réussir avec structure complète."""
    json_data = {
        "key": "test-key",
        "name": "Test Scenario",
        "description": "Test description",
        "protocol": "HL7v2",
        "tags": "test,import",
        "time_config": {
            "anchor_mode": "fixed",
            "anchor_days_offset": 0,
            "fixed_start_iso": "2025-01-01T10:00:00",
            "preserve_intervals": True,
            "jitter_min": 0,
            "jitter_max": 5,
            "jitter_events": True
        },
        "steps": [
            {
                "order_index": 0,
                "message_type": "ADT^A01",
                "format": "HL7v2",
                "delay_seconds": 0,
                "payload": "MSH|^~\\&|..."
            }
        ]
    }
    is_valid, error = validate_scenario_json(json_data)
    assert is_valid
    assert error is None


def test_import_scenario_basic(session: Session):
    """Import doit créer le scénario et ses steps."""
    json_data = {
        "key": "import-test",
        "name": "Imported Scenario",
        "description": "Test import",
        "protocol": "HL7v2",
        "tags": "import,test",
        "steps": [
            {
                "order_index": 0,
                "message_type": "ADT^A01",
                "format": "HL7v2",
                "delay_seconds": 0,
                "payload": "MSH|^~\\&|SENDING|SENDER||RECEIVER|20250109120000||ADT^A01|MSG001|P|2.5"
            },
            {
                "order_index": 1,
                "message_type": "ADT^A08",
                "format": "HL7v2",
                "delay_seconds": 3600,
                "payload": "MSH|^~\\&|SENDING|SENDER||RECEIVER|20250109130000||ADT^A08|MSG002|P|2.5"
            }
        ]
    }
    
    scenario = import_scenario_from_json(session, json_data, ght_context_id=1)
    
    assert scenario.id is not None
    assert scenario.key == "import-test"
    assert scenario.name == "Imported Scenario"
    assert scenario.description == "Test import"
    assert scenario.protocol == "HL7v2"
    assert scenario.tags == "import,test"
    assert scenario.ght_context_id == 1
    assert len(scenario.steps) == 2
    
    # Vérifier les steps
    steps = sorted(scenario.steps, key=lambda s: s.order_index)
    assert steps[0].order_index == 0
    assert steps[0].message_type == "ADT^A01"
    assert steps[0].delay_seconds == 0
    assert "MSG001" in steps[0].payload
    
    assert steps[1].order_index == 1
    assert steps[1].message_type == "ADT^A08"
    assert steps[1].delay_seconds == 3600
    assert "MSG002" in steps[1].payload


def test_import_scenario_with_time_config(session: Session):
    """Import doit préserver la configuration temporelle."""
    json_data = {
        "key": "import-timeconfig",
        "name": "Scenario with Time Config",
        "protocol": "HL7v2",
        "time_config": {
            "anchor_mode": "sliding",
            "anchor_days_offset": -7,
            "fixed_start_iso": None,
            "preserve_intervals": True,
            "jitter_min": 1,
            "jitter_max": 5,
            "jitter_events": False
        },
        "steps": [
            {
                "order_index": 0,
                "message_type": "ADT^A01",
                "format": "HL7v2",
                "delay_seconds": 0,
                "payload": "MSH|..."
            }
        ]
    }
    
    scenario = import_scenario_from_json(session, json_data, ght_context_id=1)
    
    assert scenario.time_anchor_mode == "sliding"
    assert scenario.time_anchor_days_offset == -7
    assert scenario.time_fixed_start_iso is None
    assert scenario.preserve_intervals is True
    assert scenario.jitter_min_minutes == 1
    assert scenario.jitter_max_minutes == 5
    # Note: apply_jitter_on_events est stocké comme string dans la DB
    assert scenario.apply_jitter_on_events == "0"


def test_import_scenario_override_key(session: Session):
    """Override key doit remplacer la clé du JSON."""
    json_data = {
        "key": "original-key",
        "name": "Test Scenario",
        "protocol": "HL7v2",
        "steps": [
            {
                "order_index": 0,
                "message_type": "ADT^A01",
                "format": "HL7v2",
                "delay_seconds": 0,
                "payload": "MSH|..."
            }
        ]
    }
    
    scenario = import_scenario_from_json(
        session, 
        json_data, 
        ght_context_id=1,
        override_key="new-key"
    )
    
    assert scenario.key == "new-key"
    assert scenario.name == "Test Scenario"


def test_import_scenario_override_name(session: Session):
    """Override name doit remplacer le nom du JSON."""
    json_data = {
        "key": "test-key",
        "name": "Original Name",
        "protocol": "HL7v2",
        "steps": [
            {
                "order_index": 0,
                "message_type": "ADT^A01",
                "format": "HL7v2",
                "delay_seconds": 0,
                "payload": "MSH|..."
            }
        ]
    }
    
    scenario = import_scenario_from_json(
        session, 
        json_data, 
        ght_context_id=1,
        override_name="New Name"
    )
    
    assert scenario.key == "test-key"
    assert scenario.name == "New Name"


def test_import_scenario_duplicate_key_error(session: Session):
    """Import doit échouer si la clé existe déjà."""
    # Créer un scénario existant
    existing = InteropScenario(
        key="duplicate-key",
        name="Existing Scenario",
        protocol="HL7v2",
        ght_context_id=1
    )
    session.add(existing)
    session.commit()
    
    # Tenter d'importer avec la même clé
    json_data = {
        "key": "duplicate-key",
        "name": "New Scenario",
        "protocol": "HL7v2",
        "steps": []
    }
    
    with pytest.raises(ScenarioImportError) as exc_info:
        import_scenario_from_json(session, json_data, ght_context_id=1)
    
    assert "existe déjà" in str(exc_info.value).lower() or "already exists" in str(exc_info.value).lower()


def test_import_scenario_invalid_context_id(session: Session):
    """Import doit échouer si le contexte n'existe pas."""
    json_data = {
        "key": "test-key",
        "name": "Test Scenario",
        "protocol": "HL7v2",
        "steps": []
    }
    
    with pytest.raises(ScenarioImportError) as exc_info:
        import_scenario_from_json(session, json_data, ght_context_id=999)
    
    assert "contexte" in str(exc_info.value).lower()


def test_import_scenario_empty_steps(session: Session):
    """Import doit accepter un scénario sans steps."""
    json_data = {
        "key": "empty-scenario",
        "name": "Empty Scenario",
        "protocol": "HL7v2",
        "steps": []
    }
    
    scenario = import_scenario_from_json(session, json_data, ght_context_id=1)
    
    assert scenario.id is not None
    assert scenario.key == "empty-scenario"
    assert len(scenario.steps) == 0


def test_import_scenario_special_characters_in_payload(session: Session):
    """Import doit préserver les caractères spéciaux dans les payloads."""
    special_payload = "MSH|^~\\&|SEND^APP|FACILITY||RECEIVER|20250109||ADT^A01|123|P|2.5\rPID|||12345^^^HOSPA^PI||Doe^John^A||19800101|M"
    
    json_data = {
        "key": "special-chars",
        "name": "Special Characters",
        "protocol": "HL7v2",
        "steps": [
            {
                "order_index": 0,
                "message_type": "ADT^A01",
                "format": "HL7v2",
                "delay_seconds": 0,
                "payload": special_payload
            }
        ]
    }
    
    scenario = import_scenario_from_json(session, json_data, ght_context_id=1)
    
    assert len(scenario.steps) == 1
    assert scenario.steps[0].payload == special_payload
    assert "^~\\&" in scenario.steps[0].payload
    assert "^^^" in scenario.steps[0].payload


def test_import_scenario_large_delay(session: Session):
    """Import doit accepter de grands délais."""
    json_data = {
        "key": "large-delay",
        "name": "Large Delay Scenario",
        "protocol": "HL7v2",
        "steps": [
            {
                "order_index": 0,
                "message_type": "ADT^A01",
                "format": "HL7v2",
                "delay_seconds": 0,
                "payload": "MSH|..."
            },
            {
                "order_index": 1,
                "message_type": "ADT^A08",
                "format": "HL7v2",
                "delay_seconds": 86400 * 7,  # 7 jours
                "payload": "MSH|..."
            }
        ]
    }
    
    scenario = import_scenario_from_json(session, json_data, ght_context_id=1)
    
    steps = sorted(scenario.steps, key=lambda s: s.order_index)
    assert steps[1].delay_seconds == 86400 * 7


def test_import_scenario_preserves_all_optional_fields(session: Session):
    """Import doit préserver tous les champs optionnels."""
    json_data = {
        "key": "full-scenario",
        "name": "Full Scenario",
        "description": "Complete description",
        "protocol": "HL7v2",
        "tags": "tag1,tag2,tag3",
        "time_config": {
            "anchor_mode": "fixed",
            "anchor_days_offset": 0,
            "fixed_start_iso": "2025-01-01T10:00:00",
            "preserve_intervals": False,
            "jitter_min": 2,
            "jitter_max": 10,
            "jitter_events": True
        },
        "steps": [
            {
                "order_index": 0,
                "message_type": "ADT^A01",
                "format": "HL7v2",
                "delay_seconds": 0,
                "payload": "MSH|..."
            }
        ]
    }
    
    scenario = import_scenario_from_json(session, json_data, ght_context_id=1)
    
    # Vérifier tous les champs
    assert scenario.description == "Complete description"
    assert scenario.tags == "tag1,tag2,tag3"
    assert scenario.time_anchor_mode == "fixed"
    assert scenario.time_anchor_days_offset == 0
    assert scenario.time_fixed_start_iso == "2025-01-01T10:00:00"
    assert scenario.preserve_intervals is False
    assert scenario.jitter_min_minutes == 2
    assert scenario.jitter_max_minutes == 10
    # Note: apply_jitter_on_events est stocké comme string dans la DB
    assert scenario.apply_jitter_on_events == "1"
