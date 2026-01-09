#!/usr/bin/env python3
"""Test rapide du générateur de scénarios de test."""

from app.services.test_scenario_generator import TestScenarioGenerator, TestScenarioType

def test_scenario_generation():
    """Test de génération de scénarios."""
    print("=== Test du Générateur de Scénarios de Test ===\n")

    generator = TestScenarioGenerator()

    # Test génération admission complète
    print("1. Test génération admission complète...")
    scenario = generator.generate_scenario(
        TestScenarioType.ADMISSION_COMPLETE,
        specialty='Médecine interne'
    )

    print(f"   ✓ Scénario généré: {scenario.name}")
    print(f"   ✓ ID: {scenario.id}")
    print(f"   ✓ Type: {scenario.scenario_type.value}")
    print(f"   ✓ Messages: {len(scenario.messages)}")
    print(f"   ✓ Erreurs attendues: {len(scenario.expected_errors)}")

    # Test génération avec erreurs injectées
    print("\n2. Test génération avec erreurs injectées...")
    from app.services.test_scenario_generator import ErrorInjection, ErrorType

    error_injection = ErrorInjection(
        error_type=ErrorType.MISSING_SEGMENT,
        probability=1.0  # Erreur garantie
    )

    scenario_with_errors = generator.generate_scenario(
        TestScenarioType.ADMISSION_COMPLETE,
        specialty='Chirurgie',
        error_injections=[error_injection]
    )

    print(f"   ✓ Scénario avec erreurs: {scenario_with_errors.name}")
    print(f"   ✓ Erreurs injectées: {len(scenario_with_errors.expected_errors)}")

    # Test génération bulk
    print("\n3. Test génération admission en masse...")
    bulk_scenario = generator.generate_scenario(
        TestScenarioType.BULK_ADMISSION,
        specialty='Urgences',
        patient_count=5
    )

    print(f"   ✓ Scénario bulk: {bulk_scenario.name}")
    print(f"   ✓ Patients: {bulk_scenario.metadata['patient_count']}")
    print(f"   ✓ Messages: {len(bulk_scenario.messages)}")

    print("\n=== Tous les tests passés avec succès! ===")

if __name__ == "__main__":
    test_scenario_generation()