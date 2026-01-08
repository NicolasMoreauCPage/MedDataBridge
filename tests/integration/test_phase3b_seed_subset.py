#!/usr/bin/env python3
"""
Test Phase 3B - Exécution du seed avec validateur sur un petit subset
This script runs the seed on just the first 5 scenarios to verify integration works
"""

import sys
import os
from pathlib import Path

# Setup paths
sys.path.insert(0, '/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge')
sys.path.insert(0, '/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/scripts_manual')

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select
from datetime import datetime
from hl7_import_validator import HL7ImportValidator, ValidationResult
from seed_hl7_scenarios import extract_hl7_messages, extract_trigger_from_message, get_scenario_name_from_path, _save_corrections_report


def test_seed_with_validator_subset():
    """Test the seed script on first 5 HL7 files"""
    
    base_path = Path('/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/docs/interfaces.integration_src/interfaces.integration/target/classes/data')
    
    if not base_path.exists():
        print(f'❌ Source directory not found: {base_path}')
        return False
    
    hl7_files = list(base_path.glob('**/*.hl7'))
    if not hl7_files:
        print('❌ No HL7 files found')
        return False
    
    print('\n🧪 TEST PHASE 3B - Seed avec validateur (subset)')
    print('=' * 70)
    print(f'📂 Source directory: {base_path}')
    print(f'📄 Total HL7 files: {len(hl7_files)}')
    print(f'🔍 Testing first 3 files...\n')
    
    # Initialize validator
    validator = HL7ImportValidator(mode="LENIENT")
    
    # Clear existing test scenarios from previous runs
    with Session(engine) as session:
        # Find and delete existing test scenario
        test_scenario = session.exec(
            select(InteropScenario).where(InteropScenario.name.ilike('%test%'))
        ).first()
        if test_scenario:
            print(f'🧹 Cleanup: Deleting previous test scenario: {test_scenario.name}')
            session.delete(test_scenario)
            session.commit()
    
    # Process first 3 files
    test_files = sorted(hl7_files)[:3]
    total_messages = 0
    valid_count = 0
    fixable_count = 0
    rejected_count = 0
    corrections_log = []
    
    for file_idx, hl7_file in enumerate(test_files, 1):
        try:
            with open(hl7_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().strip()
            
            if not content:
                continue
            
            messages = extract_hl7_messages(content)
            if not messages:
                continue
            
            scenario_name = get_scenario_name_from_path(str(hl7_file))
            
            print(f'\n📄 File {file_idx}/3: {hl7_file.name}')
            print(f'   Scenario: {scenario_name}')
            print(f'   Messages: {len(messages)}')
            
            # Create scenario in database
            with Session(engine) as session:
                scenario = InteropScenario(
                    key=f"test_phase3_b_{file_idx}_{hl7_file.stem}",
                    name=f"{scenario_name} (Phase3B Test)",
                    description=f"Phase 3B test scenario from {hl7_file.name}",
                    category="IHE_PAM_TEST_PHASE3B",
                    protocol="HL7",
                    source_path=str(hl7_file),
                    tags="pam,hl7,phase3b-test",
                    is_active=True
                )
                session.add(scenario)
                session.flush()
                
                # Process each message with validation
                for order_idx, msg in enumerate(messages, 1):
                    total_messages += 1
                    trigger = extract_trigger_from_message(msg)
                    
                    # Validate and potentially correct
                    validation_report = validator.validate_message(msg)
                    
                    if validation_report.status == ValidationResult.VALID:
                        payload_to_store = msg
                        valid_count += 1
                        status_icon = '✅'
                    elif validation_report.status == ValidationResult.FIXABLE:
                        payload_to_store = validation_report.corrected_message or msg
                        fixable_count += 1
                        status_icon = '🔧'
                        
                        corrections_log.append({
                            'scenario': scenario_name,
                            'step': order_idx,
                            'trigger': trigger,
                            'errors': validation_report.errors,
                            'corrections': validation_report.corrections_applied
                        })
                    else:  # REJECTED
                        rejected_count += 1
                        status_icon = '❌'
                        continue
                    
                    step = InteropScenarioStep(
                        scenario_id=scenario.id,
                        order_index=order_idx,
                        name=f"Step {order_idx}: {trigger}",
                        message_format="hl7",
                        message_type=trigger,
                        payload=payload_to_store
                    )
                    session.add(step)
                    print(f'   {status_icon} Step {order_idx} ({trigger}): {validation_report.status.name}')
                
                session.commit()
                print(f'   ✓ Scenario saved to database')
        
        except Exception as e:
            print(f'   ✗ Error: {str(e)[:100]}')
    
    # Summary
    print('\n' + '=' * 70)
    print('RÉSUMÉ DES RÉSULTATS')
    print('=' * 70)
    print(f'📊 Total messages processed: {total_messages}')
    print(f'✅ Valid (unchanged): {valid_count} ({valid_count*100/max(1,total_messages):.1f}%)')
    print(f'🔧 Fixable (corrected): {fixable_count} ({fixable_count*100/max(1,total_messages):.1f}%)')
    print(f'❌ Rejected: {rejected_count} ({rejected_count*100/max(1,total_messages):.1f}%)')
    
    if corrections_log:
        print(f'\n📋 Corrections appliquées:')
        for i, correction in enumerate(corrections_log, 1):
            print(f'   {i}. {correction["scenario"]} - Step {correction["step"]} ({correction["trigger"]})')
            for error in correction['errors'][:1]:
                print(f'      Issue: {error}')
            for fix in correction['corrections'][:1]:
                print(f'      Fix: {fix}')
    
    # Verify scenarios were created
    with Session(engine) as session:
        created = session.exec(
            select(InteropScenario).where(InteropScenario.category == "IHE_PAM_TEST_PHASE3B")
        ).all()
        
        print(f'\n✓ Scenarios créés en base: {len(created)}')
        for scenario in created:
            steps = session.exec(
                select(InteropScenarioStep).where(InteropScenarioStep.scenario_id == scenario.id)
            ).all()
            print(f'   • {scenario.name}: {len(steps)} steps')
    
    return True


if __name__ == '__main__':
    try:
        success = test_seed_with_validator_subset()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f'\n❌ Fatal error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
