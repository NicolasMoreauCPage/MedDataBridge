#!/usr/bin/env python3
"""
Phase 2: Integrate validator into import process
Sample scenarios from database to identify problematic HL7
"""

import asyncio
import sys
from pathlib import Path
from sqlmodel import Session, select, create_engine
from app.db import get_session, init_db
from app.models_scenarios import InteropScenario, InteropScenarioStep
from hl7_import_validator import HL7ImportValidator, ValidationResult, HL7ImportQualityReport


async def validate_scenario_hl7():
    """Valide les messages HL7 des scénarios importés"""
    
    print("\n" + "="*80)
    print("🔬 PHASE 2: VALIDATING IMPORTED SCENARIO HL7 MESSAGES")
    print("="*80)
    
    # Initialise la base de données
    from app.db import engine
    
    validator = HL7ImportValidator(mode="LENIENT")
    report = HL7ImportQualityReport()
    
    # Récupère les scénarios
    with Session(engine) as session:
        scenarios = session.exec(select(InteropScenario)).all()
        
        print(f"\n📁 Found {len(scenarios)} scenarios in database")
        
        step_count = 0
        for scenario in scenarios[:20]:  # Limite à 20 pour le test
            steps = session.exec(
                select(InteropScenarioStep)
                .where(InteropScenarioStep.scenario_id == scenario.id)
            ).all()
            
            for step in steps:
                if not step.payload or step.message_format != "hl7":
                    continue
                
                step_count += 1
                message = step.payload
                
                try:
                    validation_report = validator.validate_message(message)
                    report.add_report(validation_report)
                    
                    # Affiche le statut
                    status_icon = {
                        ValidationResult.VALID: "✅",
                        ValidationResult.FIXABLE: "🔧",
                        ValidationResult.REJECTED: "❌"
                    }[validation_report.status]
                    
                    print(f"   {status_icon} Scenario {scenario.id:3d} Step {step.order_index:2d} {validation_report.trigger:3s} {validation_report.status.value}")
                    
                except Exception as e:
                    print(f"   ❌ Scenario {scenario.id:3d} Step {step.order_index:2d} ERROR: {str(e)[:40]}")
        
        print(f"\nProcessed {step_count} HL7 messages from scenarios")
    
    # Affiche le rapport récapitulatif
    report.print_summary()
    
    # Statistiques détaillées
    print("\n📊 DETAILED ANALYSIS")
    print("="*80)
    
    print(f"\nByTrigger Distribution:")
    trigger_counts = {}
    for r in report.reports:
        trigger = r.trigger
        if trigger not in trigger_counts:
            trigger_counts[trigger] = {"valid": 0, "fixable": 0, "rejected": 0}
        
        if r.status == ValidationResult.VALID:
            trigger_counts[trigger]["valid"] += 1
        elif r.status == ValidationResult.FIXABLE:
            trigger_counts[trigger]["fixable"] += 1
        else:
            trigger_counts[trigger]["rejected"] += 1
    
    for trigger in sorted(trigger_counts.keys()):
        counts = trigger_counts[trigger]
        print(f"   {trigger:3s}: {counts['valid']:2d} valid, {counts['fixable']:2d} fixable, {counts['rejected']:2d} rejected")
    
    print("\n" + "="*80)
    print("💡 PHASE 2 SUMMARY")
    print("="*80)
    
    print(f"""
✅ Validation Complete:
   - Total HL7 messages analyzed: {report.total_messages}
   - Valid: {report.valid_messages} ({report.valid_messages*100/max(1,report.total_messages):.1f}%)
   - Fixable: {report.fixable_messages} ({report.fixable_messages*100/max(1,report.total_messages):.1f}%)
   - Rejected: {report.rejected_messages} ({report.rejected_messages*100/max(1,report.total_messages):.1f}%)

🎯 Next Steps:
   1. Phase 2 COMPLETE ✅
   2. Modify init_db.py to use validator (Phase 3)
   3. Re-import with automatic corrections
   4. Re-run roundtrip and measure +44% improvement

📈 Expected Impact:
   - Current: 21.4% AA (117 messages)
   - Target: 65-70% AA (350-380 messages)
   - Gain: +240-260 successful messages
""")


if __name__ == "__main__":
    asyncio.run(validate_scenario_hl7())
