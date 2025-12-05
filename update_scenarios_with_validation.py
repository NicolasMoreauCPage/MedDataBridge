#!/usr/bin/env python3
"""
Phase 3 - UPDATE existing scenarios with validation and correction

This script:
1. Iterates through all existing HL7 messages in database scenarios
2. Validates each message using the HL7ImportValidator
3. Applies corrections in LENIENT mode
4. Updates the database with corrected payloads
5. Logs all corrections applied
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge')

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select
from hl7_import_validator import HL7ImportValidator, ValidationResult


def update_scenarios_with_validation():
    """Update all existing scenarios with validation and corrections"""
    
    print('\n' + '=' * 70)
    print('PHASE 3 - UPDATE scenarios with HL7 validation & correction')
    print('=' * 70)
    
    validator = HL7ImportValidator(mode="LENIENT")
    
    with Session(engine) as session:
        # Get all scenarios (except test ones)
        scenarios = session.exec(
            select(InteropScenario).where(
                (InteropScenario.category == "IHE_PAM") |
                (InteropScenario.category == "PAM") |
                (InteropScenario.category == "HL7")
            )
        ).all()
        
        if not scenarios:
            print('❌ No scenarios found')
            return False
        
        print(f'\n📊 Found {len(scenarios)} scenarios to process')
        
        total_messages = 0
        valid_count = 0
        fixable_count = 0
        rejected_count = 0
        corrections_log = []
        
        for scenario_idx, scenario in enumerate(scenarios, 1):
            # Get all steps for this scenario
            steps = session.exec(
                select(InteropScenarioStep)
                .where(InteropScenarioStep.scenario_id == scenario.id)
                .order_by(InteropScenarioStep.order_index)
            ).all()
            
            if not steps:
                continue
            
            if scenario_idx % 25 == 0 or scenario_idx == 1:
                print(f'\n  Processing {scenario_idx}/{len(scenarios)}: {scenario.name}')
            
            # Process each step's message
            for step in steps:
                if not step.payload or step.message_format != "hl7":
                    continue
                
                total_messages += 1
                trigger = step.message_type
                
                # Validate message
                validation_report = validator.validate_message(step.payload)
                
                if validation_report.status == ValidationResult.VALID:
                    valid_count += 1
                    # No update needed
                
                elif validation_report.status == ValidationResult.FIXABLE:
                    fixable_count += 1
                    
                    # Update step with corrected message
                    if validation_report.corrected_message:
                        step.payload = validation_report.corrected_message
                        session.add(step)
                    
                    corrections_log.append({
                        'scenario': scenario.name,
                        'step': step.order_index,
                        'trigger': trigger,
                        'errors': validation_report.errors,
                        'corrections': validation_report.corrections_applied
                    })
                
                else:  # REJECTED
                    rejected_count += 1
                    print(f'    ⚠ Message rejeté: {scenario.name} Step {step.order_index} ({trigger})')
        
        # Commit all updates
        print(f'\n💾 Committing updates to database...')
        session.commit()
        
        # Summary
        print('\n' + '=' * 70)
        print('RÉSUMÉ DES MISES À JOUR')
        print('=' * 70)
        print(f'📊 Total messages: {total_messages}')
        print(f'✅ Valid (unchanged): {valid_count} ({valid_count*100/max(1,total_messages):.1f}%)')
        print(f'🔧 Fixed (corrected): {fixable_count} ({fixable_count*100/max(1,total_messages):.1f}%)')
        print(f'❌ Rejected: {rejected_count} ({rejected_count*100/max(1,total_messages):.1f}%)')
        
        if corrections_log:
            print(f'\n📋 Corrections appliquées: {len(corrections_log)} messages')
            
            # Group by error type
            error_types = {}
            for correction in corrections_log:
                for error in correction['errors']:
                    error_type = error.split(':')[0] if ':' in error else error
                    error_types[error_type] = error_types.get(error_type, 0) + 1
            
            print('\n  Résumé par type d\'erreur:')
            for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
                print(f'    - {error_type}: {count} messages')
            
            # Show first 10 corrections
            print(f'\n  Premiers corrections:')
            for i, correction in enumerate(corrections_log[:10], 1):
                print(f'    {i}. {correction["scenario"]} Step {correction["step"]} ({correction["trigger"]})')
                if correction['errors']:
                    print(f'       Issue: {correction["errors"][0]}')
                if correction['corrections']:
                    print(f'       Fix: {correction["corrections"][0]}')
            
            if len(corrections_log) > 10:
                print(f'    ... et {len(corrections_log) - 10} autres messages')
        
        # Save detailed report
        _save_update_report(corrections_log, total_messages, valid_count, fixable_count, rejected_count)
        
        return True


def _save_update_report(corrections_log, total, valid, fixable, rejected):
    """Save detailed update report"""
    
    report_path = Path('/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/P3_UPDATE_SCENARIOS_REPORT.md')
    
    with open(report_path, 'w') as f:
        f.write('# Phase 3 - Rapport de Mise à Jour des Scénarios\n\n')
        f.write(f'**Timestamp**: {datetime.now().isoformat()}\n')
        f.write(f'**Status**: ✅ Mise à jour complétée\n\n')
        
        f.write('## Statistiques Globales\n\n')
        f.write(f'| Métrique | Valeur | Pourcentage |\n')
        f.write(f'|----------|--------|------------|\n')
        f.write(f'| Total | {total} | 100% |\n')
        f.write(f'| Valides | {valid} | {valid*100/max(1,total):.1f}% |\n')
        f.write(f'| Corrigés | {fixable} | {fixable*100/max(1,total):.1f}% |\n')
        f.write(f'| Rejetés | {rejected} | {rejected*100/max(1,total):.1f}% |\n\n')
        
        if corrections_log:
            f.write(f'## Détail des Corrections ({len(corrections_log)} messages)\n\n')
            
            # Error type summary
            error_types = {}
            for correction in corrections_log:
                for error in correction['errors']:
                    error_type = error.split(':')[0] if ':' in error else error
                    error_types[error_type] = error_types.get(error_type, 0) + 1
            
            f.write('### Résumé par Type d\'Erreur\n\n')
            for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
                f.write(f'- **{error_type}**: {count} messages\n')
            
            f.write('\n### Corrections Détaillées\n\n')
            for i, correction in enumerate(corrections_log, 1):
                f.write(f'#### {i}. {correction["scenario"]} - Step {correction["step"]} ({correction["trigger"]})\n\n')
                
                if correction['errors']:
                    f.write('**Erreurs**:\n')
                    for error in correction['errors']:
                        f.write(f'- {error}\n')
                    f.write('\n')
                
                if correction['corrections']:
                    f.write('**Corrections**:\n')
                    for fix in correction['corrections']:
                        f.write(f'- {fix}\n')
                    f.write('\n')
        
        f.write('\n## Prochaines Étapes\n\n')
        f.write('1. Vérifier les messages rejetés (s\'il y en a)\n')
        f.write('2. Re-exécuter le roundtrip avec les messages corrigés\n')
        f.write('3. Mesurer l\'amélioration du taux de succès (AA)\n')
    
    print(f'\n📄 Rapport détaillé: {report_path}')


if __name__ == '__main__':
    try:
        success = update_scenarios_with_validation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f'\n❌ Fatal error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
