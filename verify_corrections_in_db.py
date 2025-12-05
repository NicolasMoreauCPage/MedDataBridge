#!/usr/bin/env python3
"""
Verify that corrections were actually applied to database
"""

import sys
sys.path.insert(0, '/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge')

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select


def verify_corrections():
    """Verify that corrections are in database"""
    
    print('\n' + '=' * 70)
    print('VERIFY corrections in database')
    print('=' * 70)
    
    with Session(engine) as session:
        # Get a few scenarios to spot check
        scenarios = session.exec(
            select(InteropScenario)
            .where(InteropScenario.category.in_(["IHE_PAM", "PAM", "HL7"]))
            .limit(5)
        ).all()
        
        for scenario in scenarios:
            steps = session.exec(
                select(InteropScenarioStep)
                .where(InteropScenarioStep.scenario_id == scenario.id)
                .order_by(InteropScenarioStep.order_index)
            ).all()
            
            print(f'\n📄 {scenario.name}')
            for step in steps:
                if step.payload and step.message_format == "hl7":
                    # Check if MSH-3 is present
                    lines = step.payload.split('\\r')
                    msh_line = next((l for l in lines if l.startswith('MSH')), None)
                    
                    if msh_line:
                        fields = msh_line.split('|')
                        msh3 = fields[3] if len(fields) > 3 else "EMPTY"
                        status = '✅' if msh3 else '❌'
                        print(f'   {status} Step {step.order_index} ({step.message_type}): MSH-3 = "{msh3}"')
                        
                        # Show first line
                        first_50 = step.payload[:50]
                        print(f'      Payload start: {first_50}...')
    
    print('\n✅ Verification complete')


if __name__ == '__main__':
    verify_corrections()
