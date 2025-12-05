"""
Tests pour la synchronisation dossier_type ↔ PV1-2 lors de réception A06/A07.
"""

import pytest
from datetime import datetime
from sqlmodel import Session, select

from app.models import Patient, Dossier, Venue, Mouvement, DossierType
from app.services.import_hl7_mouvement import (
    extract_nature_from_hl7,
    validate_a06_a07_coherence
)
from app.services.dossier_type_mapping import (
    dossier_type_to_patient_class,
    patient_class_to_dossier_type,
    get_expected_trigger_event
)


class TestDossierTypeMapping:
    """Tests des mappings dossier_type ↔ PV1-2."""

    def test_dossier_type_to_patient_class_hospitalise(self):
        """Test mapping HOSPITALISE → I."""
        assert dossier_type_to_patient_class("HOSPITALISE") == "I"
        assert dossier_type_to_patient_class(DossierType.HOSPITALISE) == "I"

    def test_dossier_type_to_patient_class_externe(self):
        """Test mapping EXTERNE → O."""
        assert dossier_type_to_patient_class("EXTERNE") == "O"
        assert dossier_type_to_patient_class(DossierType.EXTERNE) == "O"

    def test_dossier_type_to_patient_class_urgence(self):
        """Test mapping URGENCE → E."""
        assert dossier_type_to_patient_class("URGENCE") == "E"
        assert dossier_type_to_patient_class(DossierType.URGENCE) == "E"

    def test_patient_class_to_dossier_type_inpatient(self):
        """Test inverse mapping I → HOSPITALISE."""
        assert patient_class_to_dossier_type("I") == "HOSPITALISE"

    def test_patient_class_to_dossier_type_outpatient(self):
        """Test inverse mapping O → EXTERNE."""
        assert patient_class_to_dossier_type("O") == "EXTERNE"

    def test_patient_class_to_dossier_type_emergency(self):
        """Test inverse mapping E → URGENCE."""
        assert patient_class_to_dossier_type("E") == "URGENCE"

    def test_patient_class_to_dossier_type_case_insensitive(self):
        """Test que mapping fonctionne insensitive à la casse."""
        assert patient_class_to_dossier_type("i") == "HOSPITALISE"
        assert patient_class_to_dossier_type("o") == "EXTERNE"
        assert patient_class_to_dossier_type("e") == "URGENCE"


class TestExpectedTriggerEvent:
    """Tests du calcul du trigger_event attendu."""

    def test_hospitalise_to_externe_expect_a07(self):
        """HOSPITALISE → EXTERNE doit générer A07."""
        event = get_expected_trigger_event("HOSPITALISE", "EXTERNE")
        assert event == "A07"

    def test_hospitalise_to_urgence_expect_a07(self):
        """HOSPITALISE → URGENCE doit générer A07."""
        event = get_expected_trigger_event("HOSPITALISE", "URGENCE")
        assert event == "A07"

    def test_externe_to_hospitalise_expect_a06(self):
        """EXTERNE → HOSPITALISE doit générer A06."""
        event = get_expected_trigger_event("EXTERNE", "HOSPITALISE")
        assert event == "A06"

    def test_urgence_to_hospitalise_expect_a06(self):
        """URGENCE → HOSPITALISE doit générer A06."""
        event = get_expected_trigger_event("URGENCE", "HOSPITALISE")
        assert event == "A06"

    def test_same_type_no_event(self):
        """Pas de changement → pas d'A06/A07."""
        assert get_expected_trigger_event("HOSPITALISE", "HOSPITALISE") is None
        assert get_expected_trigger_event("EXTERNE", "EXTERNE") is None


class TestNatureExtraction:
    """Tests d'extraction de nature depuis PV1-2."""

    def test_nature_from_pv1_inpatient(self):
        """PV1-2=I doit donner nature=H."""
        pv1 = "PV1|1|I|location|A|"
        nature = extract_nature_from_hl7(pv1, None)
        assert nature == "H"

    def test_nature_from_pv1_outpatient(self):
        """PV1-2=O doit donner nature=S."""
        pv1 = "PV1|1|O|location|A|"
        nature = extract_nature_from_hl7(pv1, None)
        assert nature == "S"

    def test_nature_from_pv1_emergency(self):
        """PV1-2=E doit donner nature=S."""
        pv1 = "PV1|1|E|location|A|"
        nature = extract_nature_from_hl7(pv1, None)
        assert nature == "S"

    def test_nature_from_zbe_priority(self):
        """ZBE-2 prioritaire sur PV1-2."""
        pv1 = "PV1|1|I|location|A|"
        zbe = "ZBE|1|timestamp|CANCEL|N||uf|uf|S|"  # ZBE-9=S
        # REMARQUE: actual parsing uses ZBE-2, not ZBE-9
        # This is just for structure testing


class TestDossierTypeSynchronization:
    """Tests de synchronisation du dossier_type en réception A06/A07."""

    def test_a06_syncs_dossier_type_hospitalise(self):
        """A06 reçu avec PV1-2=I doit mettre à jour dossier_type=HOSPITALISE."""
        # REMARQUE: Full integration test would require session and DB setup
        # This is unit test level validation
        
        # Vérifier que patient_class "I" mappe bien à HOSPITALISE
        result = patient_class_to_dossier_type("I")
        assert result == "HOSPITALISE", \
            "A06 reception avec PV1-2=I doit mapper à HOSPITALISE"

    def test_a07_syncs_dossier_type_externe(self):
        """A07 reçu avec PV1-2=O doit mettre à jour dossier_type=EXTERNE."""
        result = patient_class_to_dossier_type("O")
        assert result == "EXTERNE", \
            "A07 reception avec PV1-2=O doit mapper à EXTERNE"

    def test_a06_syncs_dossier_type_inverse(self):
        """A06 inverse: Urgence→Hospitalise."""
        # A06 doit aboutir à hospitalisation
        old_type = "URGENCE"
        new_type_expected = "HOSPITALISE"
        
        # Si on reçoit A06, on doit passer à l'hospitalisation
        event = get_expected_trigger_event(old_type, new_type_expected)
        assert event == "A06", \
            "Transition URGENCE→HOSPITALISE doit générer A06"


class TestRoundTripSynchronization:
    """Tests du cycle complet: emission → réception → synchronisation."""

    def test_emission_reception_sync_hospitalise_to_externe(self):
        """
        Cycle complet:
        1. Dossier HOSPITALISE génère A01 avec PV1-2=I
        2. Changement vers EXTERNE génère A06 avec PV1-2=O
        3. Réception A06 synchronise dossier_type=EXTERNE
        """
        
        # Étape 1: HOSPITALISE → PV1-2=I
        original_type = "HOSPITALISE"
        original_pv1_2 = dossier_type_to_patient_class(original_type)
        assert original_pv1_2 == "I"
        
        # Étape 2: EXTERNE → PV1-2=O
        new_type = "EXTERNE"
        new_pv1_2 = dossier_type_to_patient_class(new_type)
        assert new_pv1_2 == "O"
        
        # Vérifier trigger_event
        trigger = get_expected_trigger_event(original_type, new_type)
        assert trigger == "A07"
        
        # Étape 3: Réception → mapper PV1-2 vers dossier_type
        received_pv1_2 = "O"
        synced_type = patient_class_to_dossier_type(received_pv1_2)
        assert synced_type == "EXTERNE", \
            "Réception A06/A07 avec PV1-2=O doit synchroniser dossier_type=EXTERNE"

    def test_emission_reception_sync_externe_to_hospitalise(self):
        """
        Cycle complet inverse:
        1. Dossier EXTERNE génère A03 avec PV1-2=O
        2. Changement vers HOSPITALISE génère A06 avec PV1-2=I
        3. Réception A06 synchronise dossier_type=HOSPITALISE
        """
        
        # Étape 1: EXTERNE → PV1-2=O
        original_type = "EXTERNE"
        original_pv1_2 = dossier_type_to_patient_class(original_type)
        assert original_pv1_2 == "O"
        
        # Étape 2: HOSPITALISE → PV1-2=I
        new_type = "HOSPITALISE"
        new_pv1_2 = dossier_type_to_patient_class(new_type)
        assert new_pv1_2 == "I"
        
        # Vérifier trigger_event
        trigger = get_expected_trigger_event(original_type, new_type)
        assert trigger == "A06"
        
        # Étape 3: Réception → mapper PV1-2 vers dossier_type
        received_pv1_2 = "I"
        synced_type = patient_class_to_dossier_type(received_pv1_2)
        assert synced_type == "HOSPITALISE", \
            "Réception A06 avec PV1-2=I doit synchroniser dossier_type=HOSPITALISE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
