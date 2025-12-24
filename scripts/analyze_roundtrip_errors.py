#!/usr/bin/env python3
"""Analyse détaillée des rejets du roundtrip.

Examine chaque scénario et détermine la cause des erreurs.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select, Session
from app.db import engine
from app.models_scenarios import InteropScenario
from app.models_scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog
from app.models_endpoints import SystemEndpoint
from app.services.transport_inbound import on_message_inbound_async

TEST_EJ_ID = 1
MLLP_ENDPOINT_NAME = "MLLP RECV 020000000"


def extract_ack_code(ack_payload: str) -> str:
    """Extrait le code d'ACK du payload HL7."""
    if not ack_payload:
        return "NONE"
    
    lines = ack_payload.split('\r')
    for line in lines:
        if line.startswith('MSA'):
            parts = line.split('|')
            if len(parts) >= 2:
                return parts[1]
    
    return "UNKNOWN"


def analyze_error_in_ack(ack_payload: str) -> str:
    """Extrait le message d'erreur du ACK."""
    if not ack_payload:
        return "Pas de payload"
    
    lines = ack_payload.split('\r')
    # Chercher segment ERR pour les détails
    for line in lines:
        if line.startswith('ERR'):
            return line
        if line.startswith('MSH'):
            # Chercher le texte d'erreur après MSA
            continue
    
    # Retourner première ligne comme contexte
    if lines:
        return lines[0][:100]
    return "Impossible de déterminer"


async def analyze_scenario_errors(scenario_id: int, endpoint_id: int):
    """Analyse les erreurs d'un scénario."""
    
    with Session(engine) as session:
        scenario = session.get(InteropScenario, scenario_id)
        endpoint = session.get(SystemEndpoint, endpoint_id)
        
        if not scenario:
            return None
        
        errors = []
        
        # Traiter chaque step
        if scenario.steps:
            for step_idx, step in enumerate(scenario.steps, 1):
                if not step.payload or not step.payload.strip():
                    continue
                
                try:
                    # Extraire info du message
                    lines = step.payload.split('\r')
                    msg_type = "?"
                    trigger = "?"
                    
                    for line in lines:
                        if line.startswith('MSH'):
                            # Format: MSH|^~\&|sending_app|sending_facility|receiving_app|receiving_facility|timestamp||type^trigger
                            parts = line.split('|')
                            if len(parts) >= 9:
                                msg_type_trigger = parts[8]  # ex: ADT^A01
                                msg_type_trigger_parts = msg_type_trigger.split('^')
                                msg_type = msg_type_trigger_parts[0]
                                trigger = msg_type_trigger_parts[1] if len(msg_type_trigger_parts) > 1 else "?"
                            break
                    
                    # Envoyer le message
                    ack_payload = await on_message_inbound_async(
                        step.payload, session, endpoint
                    )
                    ack_code = extract_ack_code(ack_payload) if ack_payload else "NONE"
                    
                    # Déterminer cause si erreur
                    if ack_code != "AA":
                        error_detail = analyze_error_in_ack(ack_payload)
                        errors.append({
                            "step": step_idx,
                            "msg_type": msg_type,
                            "trigger": trigger,
                            "ack_code": ack_code,
                            "error": error_detail,
                        })
                
                except Exception as e:
                    errors.append({
                        "step": step_idx,
                        "msg_type": "ERROR",
                        "trigger": "?",
                        "ack_code": "EXCEPTION",
                        "error": str(e)[:80],
                    })
        
        return {
            "scenario_id": scenario_id,
            "name": scenario.name,
            "errors": errors,
        }


async def main():
    print(f"🔍 Analyse Détaillée des Erreurs Roundtrip")
    print(f"⏰ Début: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    with Session(engine) as session:
        # Récupérer endpoint
        endpoint = session.exec(
            select(SystemEndpoint).where(SystemEndpoint.name == MLLP_ENDPOINT_NAME)
        ).first()
        
        if not endpoint:
            print(f"❌ Endpoint not found")
            sys.exit(1)
        
        endpoint_id = endpoint.id
        
        # Récupérer tous les scénarios
        scenarios = session.exec(select(InteropScenario)).all()
        scenario_ids = [s.id for s in scenarios]
        print(f"✅ {len(scenarios)} scénarios à analyser\n")
    
    # Analyser chaque scénario
    error_scenarios = []
    partial_scenarios = []
    
    for i, scenario_id in enumerate(scenario_ids, 1):
        result = await analyze_scenario_errors(scenario_id, endpoint_id)
        
        if result and result["errors"]:
            # Vérifier si tous les steps sont en erreur ou juste certains
            with Session(engine) as session:
                scenario = session.get(InteropScenario, scenario_id)
                step_count = len([s for s in scenario.steps if s.payload and s.payload.strip()])
            
            if len(result["errors"]) == step_count:
                error_scenarios.append(result)
            else:
                partial_scenarios.append(result)
    
    # Rapport des scénarios en ERREUR complète (100% des steps en erreur)
    print("\n" + "=" * 100)
    print("❌ SCÉNARIOS AVEC ERREURS COMPLÈTES (100% des steps en erreur)")
    print("=" * 100)
    
    for scenario in error_scenarios:
        print(f"\n[{scenario['scenario_id']:3}] {scenario['name']}")
        print(f"     Erreurs: {len(scenario['errors'])} steps")
        
        # Analyser les patterns
        error_types = {}
        trigger_types = {}
        
        for err in scenario['errors']:
            key = f"{err['ack_code']}"
            error_types[key] = error_types.get(key, 0) + 1
            
            trigger = err['trigger']
            trigger_types[trigger] = trigger_types.get(trigger, 0) + 1
        
        print(f"     ACK codes: {error_types}")
        print(f"     Triggers: {trigger_types}")
        print(f"     Détails:")
        
        for err in scenario['errors']:
            print(f"       Step {err['step']}: {err['msg_type']}^{err['trigger']} → {err['ack_code']}")
            if err['error']:
                print(f"         └─ {err['error'][:80]}")
    
    # Rapport des scénarios PARTIELS (certains steps OK, d'autres en erreur)
    print("\n" + "=" * 100)
    print("⚠️  SCÉNARIOS PARTIELS (Certains steps OK, d'autres en erreur)")
    print("=" * 100)
    
    for scenario in partial_scenarios:
        print(f"\n[{scenario['scenario_id']:3}] {scenario['name']}")
        print(f"     Erreurs: {len(scenario['errors'])} steps")
        
        # Analyser pattern
        error_pattern = []
        for err in scenario['errors']:
            error_pattern.append((err['step'], err['trigger'], err['ack_code']))
        
        print(f"     Pattern d'erreurs: {error_pattern}")
    
    # Statistiques
    print("\n" + "=" * 100)
    print("📊 STATISTIQUES")
    print("=" * 100)
    print(f"Scénarios avec erreurs 100%: {len(error_scenarios)}")
    print(f"Scénarios partiels: {len(partial_scenarios)}")
    print(f"Scénarios sans erreurs: {len(scenario_ids) - len(error_scenarios) - len(partial_scenarios)}")
    
    # Identifier patterns communs
    print("\n" + "=" * 100)
    print("🎯 PATTERNS D'ERREURS COMMUNS")
    print("=" * 100)
    
    # Compter les triggers qui posent problème
    problem_triggers = {}
    for scenario in error_scenarios + partial_scenarios:
        for err in scenario['errors']:
            trigger = err['trigger']
            problem_triggers[trigger] = problem_triggers.get(trigger, 0) + 1
    
    print("\nTriggers problématiques:")
    for trigger, count in sorted(problem_triggers.items(), key=lambda x: -x[1]):
        print(f"  {trigger}: {count} erreurs")
    
    print(f"\n⏰ Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
