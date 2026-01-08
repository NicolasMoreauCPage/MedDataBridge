#!/usr/bin/env python3
"""
Test Phase 3 - Vérification que le seed_hl7_scenarios.py avec validateur fonctionne

This script:
1. Vérifie que le validateur peut être importé
2. Teste le seed sur un petit nombre de scénarios
3. Vérifie que les messages sont validés/corrigés
"""

import sys
from pathlib import Path

# Setup path pour imports
sys.path.insert(0, str(Path(__file__).parent))

from hl7_import_validator import HL7ImportValidator, ValidationResult


def test_validator_import():
    """Test 1: Vérifier que le validateur s'importe correctement"""
    print('\n🧪 Test 1: Import du validateur')
    try:
        validator = HL7ImportValidator(mode="LENIENT")
        print('  ✓ Validateur importé avec succès en mode LENIENT')
        return True
    except Exception as e:
        print(f'  ✗ Erreur lors de l\'import: {e}')
        return False


def test_seed_imports():
    """Test 2: Vérifier que seed_hl7_scenarios.py peut être importé"""
    print('\n🧪 Test 2: Import du seed script')
    try:
        # Ajouter les répertoires à sys.path
        sys.path.insert(0, '/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge')
        sys.path.insert(0, '/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/scripts_manual')
        
        # Vérifier que les dépendances existent
        from app.db import engine
        from app.models_scenarios import InteropScenario, InteropScenarioStep
        print('  ✓ Dépendances DB importées avec succès')
        
        # Vérifier que la fonction de seed peut être importée
        from seed_hl7_scenarios import seed_hl7_scenarios, _save_corrections_report
        print('  ✓ Seed functions importées avec succès')
        return True
    except Exception as e:
        print(f'  ✗ Erreur lors de l\'import du seed: {e}')
        import traceback
        traceback.print_exc()
        return False


def test_validator_functionality():
    """Test 3: Vérifier que le validateur fonctionne correctement"""
    print('\n🧪 Test 3: Fonctionnalité du validateur')
    
    # Test message avec MSH-3 manquant
    test_msg = "MSH|^~\\&|||||20240101000000||A01|123|P|2.5\r" \
               "PID|1||123456^^^SYSTEM||DOE^JOHN"
    
    validator = HL7ImportValidator(mode="LENIENT")
    report = validator.validate_message(test_msg)
    
    print(f'  Message de test: {test_msg[:50]}...')
    print(f'  Status: {report.status.name}')
    
    if report.status == ValidationResult.FIXABLE:
        print(f'  ✓ Message reconnu comme FIXABLE')
        if report.corrected_message:
            print(f'  ✓ Message corrigé disponible')
            # Vérifier que MSH-3 a été ajouté
            if 'MEDBRIDGEDATA' in report.corrected_message:
                print(f'  ✓ Correction MSH-3 appliquée (MEDBRIDGEDATA)')
            return True
        else:
            print(f'  ✗ Message corrigé non disponible')
            return False
    elif report.status == ValidationResult.VALID:
        print(f'  ✓ Message reconnu comme VALID')
        return True
    else:
        print(f'  ✗ Message rejeté: {report.errors}')
        return False


def test_corrections_report_function():
    """Test 4: Vérifier que la fonction de rapport fonctionne"""
    print('\n🧪 Test 4: Fonction de rapport de corrections')
    
    try:
        from seed_hl7_scenarios import _save_corrections_report
        
        # Créer des données de test
        test_log = [
            {
                'scenario': 'Test Scenario 1',
                'step': 1,
                'trigger': 'A01',
                'errors': ['MSH-3 missing', 'ZBE segment missing'],
                'corrections': ['Added MSH-3: MEDBRIDGEDATA', 'Generated ZBE segment']
            }
        ]
        
        # Appeler la fonction
        _save_corrections_report(test_log)
        
        # Vérifier que le fichier a été créé
        report_path = Path('/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/P3_IMPORT_CORRECTIONS_REPORT.md')
        if report_path.exists():
            print(f'  ✓ Rapport créé: {report_path}')
            content = report_path.read_text()
            if 'Test Scenario 1' in content and 'A01' in content:
                print(f'  ✓ Contenu du rapport correct')
                return True
        else:
            print(f'  ✗ Rapport non créé')
            return False
    except Exception as e:
        print(f'  ✗ Erreur: {e}')
        import traceback
        traceback.print_exc()
        return False


def main():
    """Lance tous les tests"""
    print('=' * 60)
    print('PHASE 3 - TEST INTEGRATION SEED AVEC VALIDATEUR')
    print('=' * 60)
    
    results = []
    
    results.append(('Import Validateur', test_validator_import()))
    results.append(('Import Seed Script', test_seed_imports()))
    results.append(('Fonctionnalité Validateur', test_validator_functionality()))
    results.append(('Fonction Rapport', test_corrections_report_function()))
    
    print('\n' + '=' * 60)
    print('RÉSUMÉ DES TESTS')
    print('=' * 60)
    
    for test_name, result in results:
        status = '✓' if result else '✗'
        print(f'{status} {test_name}')
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f'\nRésultat: {passed}/{total} tests réussis')
    
    if passed == total:
        print('\n✅ TOUS LES TESTS PASSENT - Seed integration prêt à l\'exécution!')
        return 0
    else:
        print('\n❌ CERTAINS TESTS ONT ÉCHOUÉ - Réviser les erreurs ci-dessus')
        return 1


if __name__ == '__main__':
    sys.exit(main())
