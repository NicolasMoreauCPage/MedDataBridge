"""Tests pour le système de configuration temporelle réaliste des scénarios."""

import pytest
from app.services.scenario_realistic_timeplan import (
    extract_event_sequence,
    detect_workflow_type,
    create_realistic_timeshift_config,
    suggest_scenario_timing_update,
    HOSPITAL_WORKFLOWS
)

# Messages HL7 de test pour différents workflows
EMERGENCY_MESSAGES = [
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241206080000||ADT^A05|MSG001|P|2.5|||||||FR^France
EVN||20241206080000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR""",
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241206090000||ADT^A01|MSG002|P|2.5|||||||FR^France  
EVN||20241206090000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR""",
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241206140000||ADT^A03|MSG003|P|2.5|||||||FR^France
EVN||20241206140000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR"""
]

PLANNED_ADMISSION_MESSAGES = [
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241206080000||ADT^A01|MSG001|P|2.5|||||||FR^France
EVN||20241206080000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR""",
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241206120000||ADT^A02|MSG002|P|2.5|||||||FR^France
EVN||20241206120000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR""",
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241208100000||ADT^A03|MSG003|P|2.5|||||||FR^France
EVN||20241208100000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR"""
]

CONSULTATION_ONLY_MESSAGES = [
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241206080000||ADT^A04|MSG001|P|2.5|||||||FR^France
EVN||20241206080000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR""",
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241206090000||ADT^A05|MSG002|P|2.5|||||||FR^France
EVN||20241206090000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR""",
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241206110000||ADT^A08|MSG003|P|2.5|||||||FR^France
EVN||20241206110000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR"""
]

LONG_STAY_MESSAGES = [
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241201080000||ADT^A01|MSG001|P|2.5|||||||FR^France
EVN||20241201080000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR""",
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241202080000||ADT^A02|MSG002|P|2.5|||||||FR^France
EVN||20241202080000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR""",
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241204080000||ADT^A02|MSG003|P|2.5|||||||FR^France
EVN||20241204080000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR""",
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241206080000||ADT^A02|MSG004|P|2.5|||||||FR^France
EVN||20241206080000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR""",
    """MSH|^~\\&|PAM|GHT|PDS|PDS|20241210080000||ADT^A03|MSG005|P|2.5|||||||FR^France
EVN||20241210080000||||01234
PID|1||123456789^^^GHT&1.2.3.4&ISO^PI||DOE^JOHN||19800101|M||||||||||||||FR"""
]


class TestEventSequenceExtraction:
    """Tests pour l'extraction de séquences d'événements HL7."""
    
    def test_extract_emergency_sequence(self):
        """Test extraction séquence urgence: A05 → A01 → A03"""
        events = extract_event_sequence(EMERGENCY_MESSAGES)
        assert events == ["A05", "A01", "A03"]
    
    def test_extract_planned_admission_sequence(self):
        """Test extraction séquence admission programmée: A01 → A02 → A03"""
        events = extract_event_sequence(PLANNED_ADMISSION_MESSAGES)
        assert events == ["A01", "A02", "A03"]
    
    def test_extract_consultation_sequence(self):
        """Test extraction séquence consultation: A04 → A05 → A08"""
        events = extract_event_sequence(CONSULTATION_ONLY_MESSAGES)
        assert events == ["A04", "A05", "A08"]
    
    def test_extract_long_stay_sequence(self):
        """Test extraction séquence séjour long: A01 → A02 → A02 → A02 → A03"""
        events = extract_event_sequence(LONG_STAY_MESSAGES)
        assert events == ["A01", "A02", "A02", "A02", "A03"]
    
    def test_extract_empty_sequence(self):
        """Test extraction séquence vide"""
        events = extract_event_sequence([])
        assert events == []
    
    def test_extract_malformed_messages(self):
        """Test extraction avec messages malformés"""
        malformed = ["MSH|invalid", "PID|1||123"]
        events = extract_event_sequence(malformed)
        assert events == []


class TestWorkflowDetection:
    """Tests pour la détection automatique de workflows hospitaliers."""
    
    def test_detect_emergency_workflow(self):
        """Test détection workflow urgence"""
        events = extract_event_sequence(EMERGENCY_MESSAGES)
        workflow = detect_workflow_type(events)
        assert workflow == "emergency_admission"
    
    def test_detect_planned_admission_workflow(self):
        """Test détection workflow admission programmée"""
        events = extract_event_sequence(PLANNED_ADMISSION_MESSAGES)
        workflow = detect_workflow_type(events)
        assert workflow == "planned_admission"
    
    def test_detect_consultation_workflow(self):
        """Test détection workflow consultation seule"""
        events = extract_event_sequence(CONSULTATION_ONLY_MESSAGES)
        workflow = detect_workflow_type(events)
        assert workflow == "consultation_only"
    
    def test_detect_long_stay_workflow(self):
        """Test détection workflow séjour long"""
        events = extract_event_sequence(LONG_STAY_MESSAGES)
        workflow = detect_workflow_type(events)
        assert workflow == "long_stay"
    
    def test_detect_default_workflow(self):
        """Test détection workflow par défaut"""
        events = ["A01", "A03"]  # Simple admission-sortie
        workflow = detect_workflow_type(events)
        assert workflow == "planned_admission"
    
    def test_detect_empty_workflow(self):
        """Test détection workflow vide"""
        workflow = detect_workflow_type([])
        assert workflow == "planned_admission"


class TestTimeShiftConfigGeneration:
    """Tests pour la génération de configuration TimeShiftConfig."""
    
    def test_create_emergency_config(self):
        """Test création configuration urgence"""
        config = create_realistic_timeshift_config(EMERGENCY_MESSAGES)
        
        assert config.anchor_mode == "admission_minus_days"
        assert config.anchor_days_offset == 1  # Plus récent pour urgence
        assert config.preserve_intervals is True
        assert config.jitter_min_minutes == 2
        assert config.jitter_max_minutes == 15
        assert "A02" in config.jitter_events
        assert "A03" in config.jitter_events
    
    def test_create_planned_admission_config(self):
        """Test création configuration admission programmée"""
        config = create_realistic_timeshift_config(PLANNED_ADMISSION_MESSAGES)
        
        assert config.anchor_mode == "admission_minus_days"
        assert config.anchor_days_offset == 2
        assert config.preserve_intervals is True
        assert config.jitter_min_minutes == 10
        assert config.jitter_max_minutes == 45
    
    def test_create_consultation_config(self):
        """Test création configuration consultation"""
        config = create_realistic_timeshift_config(CONSULTATION_ONLY_MESSAGES)
        
        assert config.anchor_mode == "now"  # Consultation le jour même
        assert config.preserve_intervals is True
        assert config.jitter_min_minutes == 5
        assert config.jitter_max_minutes == 20
    
    def test_create_long_stay_config(self):
        """Test création configuration séjour long"""
        config = create_realistic_timeshift_config(LONG_STAY_MESSAGES)
        
        assert config.anchor_mode == "admission_minus_days"
        assert config.anchor_days_offset == 7  # Plus ancien pour séjour long
        assert config.preserve_intervals is True
        assert config.jitter_min_minutes == 30
        assert config.jitter_max_minutes == 120
    
    def test_create_config_with_overrides(self):
        """Test création configuration avec surcharges"""
        overrides = {
            "anchor_mode": "now",
            "jitter_min_minutes": 1,
            "jitter_max_minutes": 5
        }
        config = create_realistic_timeshift_config(EMERGENCY_MESSAGES, custom_overrides=overrides)
        
        assert config.anchor_mode == "now"  # Surchargé
        assert config.jitter_min_minutes == 1  # Surchargé
        assert config.jitter_max_minutes == 5  # Surchargé
        assert config.anchor_days_offset == 1  # Valeur originale conservée
    
    def test_create_config_forced_workflow(self):
        """Test création configuration avec workflow forcé"""
        # Forcer workflow consultation sur messages d'urgence
        config = create_realistic_timeshift_config(EMERGENCY_MESSAGES, workflow_type="consultation_only")
        
        assert config.anchor_mode == "now"  # Consultation mode
        assert config.jitter_min_minutes == 5
        assert config.jitter_max_minutes == 20
    
    def test_create_config_empty_messages(self):
        """Test création configuration avec messages vides"""
        config = create_realistic_timeshift_config([])
        
        # Configuration par défaut
        assert config.anchor_mode == "now"
        assert config.preserve_intervals is True


class TestScenarioSuggestion:
    """Tests pour les suggestions de configuration de scénario."""
    
    def test_suggest_emergency_timing(self):
        """Test suggestion timing urgence"""
        suggestion = suggest_scenario_timing_update(1, EMERGENCY_MESSAGES)
        
        assert suggestion["time_anchor_mode"] == "admission_minus_days"
        assert suggestion["time_anchor_days_offset"] == 1
        assert suggestion["preserve_intervals"] is True
        assert suggestion["jitter_min_minutes"] == 2
        assert suggestion["jitter_max_minutes"] == 15
        assert "A02,A03,A06,A07,A08,A11,A12,A13" == suggestion["apply_jitter_on_events"]
        
        # Métadonnées
        assert suggestion["_detected_workflow"] == "emergency_admission"
        assert "urgence" in suggestion["_workflow_description"].lower()
        assert suggestion["_event_sequence"] == ["A05", "A01", "A03"]
    
    def test_suggest_consultation_timing(self):
        """Test suggestion timing consultation"""
        suggestion = suggest_scenario_timing_update(2, CONSULTATION_ONLY_MESSAGES)
        
        assert suggestion["time_anchor_mode"] == "now"
        assert suggestion["_detected_workflow"] == "consultation_only"
        assert suggestion["_event_sequence"] == ["A04", "A05", "A08"]
    
    def test_suggest_empty_messages(self):
        """Test suggestion avec messages vides"""
        suggestion = suggest_scenario_timing_update(3, [])
        
        assert suggestion == {}


class TestHospitalWorkflowConfigs:
    """Tests pour les configurations prédéfinies de workflows hospitaliers."""
    
    def test_all_workflows_present(self):
        """Test que tous les workflows attendus sont présents"""
        expected_workflows = [
            "emergency_admission",
            "planned_admission", 
            "consultation_only",
            "long_stay"
        ]
        
        for workflow in expected_workflows:
            assert workflow in HOSPITAL_WORKFLOWS
            config = HOSPITAL_WORKFLOWS[workflow]
            assert config.name
            assert config.description
            assert config.jitter_events is not None
            assert config.typical_intervals is not None
    
    def test_emergency_intervals(self):
        """Test intervalles spécifiques workflow urgence"""
        config = HOSPITAL_WORKFLOWS["emergency_admission"]
        intervals = config.typical_intervals
        
        # Consultation → Admission rapide
        assert ("A05", "A01") in intervals
        assert intervals[("A05", "A01")] == (30, 120)  # 30min à 2h
        
        # Admission → Sortie urgence 
        assert ("A01", "A03") in intervals
        assert intervals[("A01", "A03")] == (60, 360)  # 1h à 6h
    
    def test_planned_admission_intervals(self):
        """Test intervalles spécifiques hospitalisation programmée"""
        config = HOSPITAL_WORKFLOWS["planned_admission"]
        intervals = config.typical_intervals
        
        # Consultation → Admission programmée (délai plus long)
        assert ("A05", "A01") in intervals
        assert intervals[("A05", "A01")] == (480, 2880)  # 8h à 2 jours
        
        # Admission → Sortie (séjour normal)
        assert ("A01", "A03") in intervals
        assert intervals[("A01", "A03")] == (1440, 7200)  # 1 à 5 jours
    
    def test_consultation_intervals(self):
        """Test intervalles spécifiques consultation"""
        config = HOSPITAL_WORKFLOWS["consultation_only"]
        intervals = config.typical_intervals
        
        # Arrivée → Consultation
        assert ("A04", "A05") in intervals
        assert intervals[("A04", "A05")] == (15, 60)  # 15min à 1h
        
        # Consultation → Départ
        assert ("A05", "A08") in intervals
        assert intervals[("A05", "A08")] == (30, 90)  # 30min à 1h30
    
    def test_long_stay_intervals(self):
        """Test intervalles spécifiques séjour long"""
        config = HOSPITAL_WORKFLOWS["long_stay"]
        intervals = config.typical_intervals
        
        # Transfert → Transfert (longs intervalles)
        assert ("A02", "A02") in intervals
        assert intervals[("A02", "A02")] == (2880, 10080)  # 2 à 7 jours
        
        # Admission → Sortie (très long séjour)
        assert ("A01", "A03") in intervals
        assert intervals[("A01", "A03")] == (10080, 43200)  # 7 à 30 jours


if __name__ == "__main__":
    pytest.main([__file__, "-v"])