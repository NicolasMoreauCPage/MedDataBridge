#!/usr/bin/env python3
"""
Compare: original message vs corrected message dans le roundtrip
"""

import sys
sys.path.insert(0, '/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge')

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select
from hl7_import_validator import HL7ImportValidator


def find_a_corrected_message():
    """Find and display a message that was corrected"""
    
    with Session(engine) as session:
        # Find a scenario with corrected message (step 1 of first scenario)
        scenario = session.exec(
            select(InteropScenario)
            .where(InteropScenario.name == "IHE PAM - Admission (1 msg)")
        ).first()
        
        if not scenario:
            print("Scenario not found")
            return
        
        step = session.exec(
            select(InteropScenarioStep)
            .where(InteropScenarioStep.scenario_id == scenario.id)
            .where(InteropScenarioStep.order_index == 1)
        ).first()
        
        if not step:
            print("Step not found")
            return
        
        print('=' * 70)
        print(f'Scenario: {scenario.name}')
        print(f'Step: {step.order_index} ({step.message_type})')
        print('=' * 70)
        
        payload = step.payload
        print('\n📨 Message in Database:')
        print(payload[:200] + '...' if len(payload) > 200 else payload)
        
        # Check MSH-3
        lines = payload.split('\\r')
        msh = next((l for l in lines if l.startswith('MSH')), None)
        if msh:
            fields = msh.split('|')
            print(f'\nMSH-3 value: "{fields[3] if len(fields) > 3 else "EMPTY"}"')
            
            # Check if it's the auto-generated one
            if len(fields) > 3 and fields[3] == "MEDBRIDGEDATA":
                print("✅ This message was AUTO-CORRECTED (MEDBRIDGEDATA is auto-generated)")
            else:
                print("❌ This message was NOT auto-corrected")
        
        # Now test this message with validator
        print('\n' + '=' * 70)
        print('VALIDATION CHECK')
        print('=' * 70)
        
        validator = HL7ImportValidator(mode="LENIENT")
        report = validator.validate_message(payload)
        
        print(f'Trigger: {report.trigger}')
        print(f'Status: {report.status.name}')
        if report.errors:
            print(f'Errors: {report.errors}')
        if report.corrections_applied:
            print(f'Corrections: {report.corrections_applied}')
        
        if report.status.name == "VALID":
            print('\n✅ Message is VALID - should process successfully')
        else:
            print(f'\n⚠️ Message is {report.status.name} - might fail in processing')


if __name__ == '__main__':
    find_a_corrected_message()
