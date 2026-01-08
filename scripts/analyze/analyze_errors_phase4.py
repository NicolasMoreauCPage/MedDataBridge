#!/usr/bin/env python3
"""
Phase 4 - Deep Error Analysis
Analyze AE and AR errors to identify business-logic patterns
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, '/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge')

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog
from sqlmodel import Session, select
from datetime import datetime, timedelta


def analyze_error_patterns():
    """Analyze recent roundtrip errors to find patterns"""
    
    print('\n' + '=' * 80)
    print('PHASE 4 - DEEP ERROR ANALYSIS')
    print('=' * 80)
    
    with Session(engine) as session:
        # Get the most recent step logs
        recent_logs = session.exec(
            select(ScenarioExecutionStepLog)
            .order_by(ScenarioExecutionStepLog.created_at.desc())
            .limit(554)  # From latest roundtrip
        ).all()
        
        if not recent_logs:
            print('❌ No recent roundtrip logs found')
            return False
        
        print(f'\n📊 Analyzing {len(recent_logs)} recent step logs')
        
        # Group by status
        by_status = defaultdict(list)
        by_trigger = defaultdict(lambda: defaultdict(int))
        error_messages = defaultdict(int)
        
        for log in recent_logs:
            ack_code = log.ack_code or 'UNKNOWN'
            
            # Get scenario and step info
            step = session.get(InteropScenarioStep, log.step_id) if log.step_id else None
            run = session.get(ScenarioExecutionRun, log.run_id) if log.run_id else None
            scenario = session.get(InteropScenario, run.scenario_id) if run else None
            
            trigger = step.message_type if step else 'UNKNOWN'
            scenario_name = scenario.name if scenario else 'UNKNOWN'
            
            by_status[ack_code].append({
                'scenario': scenario_name,
                'trigger': trigger,
                'error': log.error_message or 'N/A'
            })
            
            by_trigger[trigger][ack_code] += 1
            
            if log.error_message:
                error_messages[log.error_message] += 1
        
        # Print Summary
        print(f'\n📈 Summary by Status:')
        for status in ['AA', 'AE', 'AR']:
            count = len(by_status.get(status, []))
            pct = count * 100 / len(recent_logs) if recent_logs else 0
            icon = '✅' if status == 'AA' else '⚠️' if status == 'AE' else '❌'
            print(f'   {icon} {status}: {count} ({pct:.1f}%)')
        
        # Errors by Trigger
        print(f'\n🔤 Error Breakdown by Message Type:')
        for trigger in sorted(by_trigger.keys()):
            stats = by_trigger[trigger]
            aa = stats.get('AA', 0)
            ae = stats.get('AE', 0)
            ar = stats.get('AR', 0)
            total = aa + ae + ar
            aa_rate = aa * 100 / total if total > 0 else 0
            
            status_icon = '✅' if aa_rate > 50 else '⚠️' if aa_rate > 0 else '❌'
            print(f'   {status_icon} {trigger:4s}: AA={aa:2d} AE={ae:2d} AR={ar:2d} ({aa_rate:5.1f}% success)')
        
        # Top Error Messages
        print(f'\n⚠️  Top Error Reasons (AE + AR):')
        if error_messages:
            for msg, count in sorted(error_messages.items(), key=lambda x: -x[1])[:15]:
                # Truncate long messages
                display_msg = msg[:70] + '...' if len(msg) > 70 else msg
                print(f'   • {display_msg}: {count}x')
        
        # Pattern Analysis
        print(f'\n🔍 Pattern Analysis:')
        
        # Check if certain transitions fail
        ae_by_scenario = defaultdict(int)
        ar_by_scenario = defaultdict(int)
        
        for log in recent_logs:
            ack_code = log.ack_code or 'UNKNOWN'
            run = session.get(ScenarioExecutionRun, log.run_id) if log.run_id else None
            scenario = session.get(InteropScenario, run.scenario_id) if run else None
            
            if not scenario:
                continue
            
            scenario_name = scenario.name
            
            if ack_code == 'AE':
                ae_by_scenario[scenario_name] += 1
            elif ack_code == 'AR':
                ar_by_scenario[scenario_name] += 1
        
        # Scenarios with ALL errors
        print(f'\n   ❌ Scenarios with ONLY errors (no AA):')
        for scenario_name in sorted(set(list(ae_by_scenario.keys()) + list(ar_by_scenario.keys()))):
            ae_count = ae_by_scenario.get(scenario_name, 0)
            ar_count = ar_by_scenario.get(scenario_name, 0)
            
            # Check if this scenario has ANY AA
            has_aa = any(
                s['scenario'] == scenario_name and s in by_status.get('AA', [])
                for s in by_status.get('AA', [])
            )
            
            if not has_aa and (ae_count > 0 or ar_count > 0):
                total_errors = ae_count + ar_count
                print(f'      • {scenario_name}: {ae_count} AE, {ar_count} AR')
        
        # Save detailed report
        _save_error_analysis_report(
            by_status, by_trigger, error_messages, ae_by_scenario, ar_by_scenario
        )
        
        return True


def _save_error_analysis_report(by_status, by_trigger, error_msgs, ae_scenarios, ar_scenarios):
    """Save detailed error analysis report"""
    
    report_path = Path('/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/P4_ERROR_ANALYSIS.md')
    
    with open(report_path, 'w') as f:
        f.write('# Phase 4 - Error Pattern Analysis\n\n')
        f.write(f'**Generated**: {datetime.now().isoformat()}\n\n')
        
        f.write('## Error Summary\n\n')
        total = sum(len(v) for v in by_status.values())
        f.write(f'| Status | Count | Percentage |\n')
        f.write(f'|--------|-------|------------|\n')
        for status in ['AA', 'AE', 'AR']:
            count = len(by_status.get(status, []))
            pct = count * 100 / total if total > 0 else 0
            f.write(f'| {status} | {count} | {pct:.1f}% |\n')
        
        f.write('\n## Error Breakdown by Message Type\n\n')
        for trigger in sorted(by_trigger.keys()):
            stats = by_trigger[trigger]
            aa = stats.get('AA', 0)
            ae = stats.get('AE', 0)
            ar = stats.get('AR', 0)
            f.write(f'### {trigger}\n\n')
            f.write(f'- AA (Success): {aa}\n')
            f.write(f'- AE (Error): {ae}\n')
            f.write(f'- AR (Reject): {ar}\n\n')
        
        f.write('\n## Top Error Reasons\n\n')
        for msg, count in sorted(error_msgs.items(), key=lambda x: -x[1])[:20]:
            f.write(f'- **{msg}**: {count} occurrences\n')
    
    print(f'\n📄 Detailed report: {report_path}')


if __name__ == '__main__':
    try:
        success = analyze_error_patterns()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f'\n❌ Error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
