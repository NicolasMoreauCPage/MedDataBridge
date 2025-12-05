#!/usr/bin/env python3
"""Vrai roundtrip - approche simplifiée et direct.

Envoie les messages via on_message_inbound_async et récupère les ACK codes réels.
"""

import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select, Session
from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
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


async def process_scenario(scenario_id: int, endpoint_id: int):
    """Traite un scénario complet."""
    
    with Session(engine) as session:
        # Charger scenario avec steps
        scenario = session.get(InteropScenario, scenario_id)
        endpoint = session.get(SystemEndpoint, endpoint_id)
        
        if not scenario:
            return {"status": "not_found", "ack_codes": [], "name": "?"}
        
        # Créer le run
        run = ScenarioExecutionRun(
            scenario_id=scenario_id,
            entite_juridique_id=TEST_EJ_ID,
            status="running",
        )
        session.add(run)
        session.flush()
        run_id = run.id
        
        ack_codes = []
        step_count = 0
        
        # Traiter chaque step
        if scenario.steps:
            for step_idx, step in enumerate(scenario.steps, 1):
                if not step.payload or not step.payload.strip():
                    continue
                
                step_count += 1
                ack_code = "EMPTY"
                ack_payload = ""
                
                try:
                    # Envoyer via on_message_inbound_async
                    ack_payload = await on_message_inbound_async(
                        step.payload, session, endpoint
                    )
                    ack_code = extract_ack_code(ack_payload) if ack_payload else "NONE"
                except Exception as e:
                    ack_code = "ERROR"
                    ack_payload = f"Exception: {str(e)[:200]}"
                
                ack_codes.append(ack_code)
                
                # Créer le step log
                step_log = ScenarioExecutionStepLog(
                    run_id=run_id,
                    order_index=step_idx,
                    ack_code=ack_code,
                    error_message=ack_payload if ack_code != "AA" else None,
                    status="sent" if ack_code == "AA" else "error",
                )
                session.add(step_log)
        
        # Déterminer le statut
        if not ack_codes:
            status = "no_steps"
        elif all(c == "AA" for c in ack_codes):
            status = "all_aa"
        elif any(c == "AA" for c in ack_codes):
            status = "partial"
        else:
            status = "error"
        
        # Finaliser le run
        run.status = status
        session.add(run)
        session.commit()
        
        return {
            "scenario_id": scenario_id,
            "name": scenario.name,
            "status": status,
            "ack_codes": ack_codes,
            "step_count": step_count,
        }


async def main():
    print(f"🚀 VRAI Roundtrip (v2)")
    print(f"⏰ Début: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 EJ ID: {TEST_EJ_ID}")
    print("=" * 80)
    
    with Session(engine) as session:
        # Vérifier l'endpoint
        endpoint = session.exec(
            select(SystemEndpoint).where(SystemEndpoint.name == MLLP_ENDPOINT_NAME)
        ).first()
        
        if not endpoint:
            print(f"❌ Endpoint '{MLLP_ENDPOINT_NAME}' not found!")
            sys.exit(1)
        
        print(f"✅ Endpoint: {endpoint.name} ({endpoint.host}:{endpoint.port})")
        endpoint_id = endpoint.id
        
        # Récupérer tous les IDs de scénarios
        scenarios = session.exec(select(InteropScenario)).all()
        scenario_ids = [s.id for s in scenarios]
        scenario_names = {s.id: s.name for s in scenarios}
        print(f"Total: {len(scenario_ids)} scénarios\n")
    
    # Résultats
    results = {
        "all_aa": [],
        "partial": [],
        "error": [],
        "no_steps": [],
        "aa_count": 0,
        "ae_count": 0,
        "ar_count": 0,
        "total_msg": 0,
    }
    
    # Traiter chaque scénario
    for i, scenario_id in enumerate(scenario_ids, 1):
        try:
            result = await process_scenario(scenario_id, endpoint_id)
            
            name = result["name"]
            status = result["status"]
            ack_codes = result["ack_codes"]
            
            print(f"[{i:3}/{len(scenario_ids)}] {name}...", end=" ", flush=True)
            
            # Compter
            for code in ack_codes:
                results["total_msg"] += 1
                if code == "AA":
                    results["aa_count"] += 1
                elif code == "AE":
                    results["ae_count"] += 1
                elif code == "AR":
                    results["ar_count"] += 1
            
            # Classer
            if status == "all_aa":
                results["all_aa"].append(name)
                print(f"✅ ALL_AA ({len(ack_codes)} msg)")
            elif status == "partial":
                results["partial"].append((name, ack_codes))
                print(f"⚠️  PARTIAL ({ack_codes})")
            elif status == "error":
                results["error"].append((name, ack_codes))
                print(f"❌ ERROR ({ack_codes})")
            elif status == "no_steps":
                results["no_steps"].append(name)
                print(f"⏹️  NO_STEPS")
            else:
                print(f"❓ {status}")
        
        except Exception as e:
            print(f"❌ EXCEPTION: {str(e)[:50]}")
            results["error"].append((scenario_id, str(e)))
    
    # Résumé
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ")
    print("=" * 80)
    print(f"✅ Succès:         {len(results['all_aa']):3}")
    print(f"⚠️  Partiels:      {len(results['partial']):3}")
    print(f"❌ Erreurs:       {len(results['error']):3}")
    print(f"⏹️  Pas d'étapes: {len(results['no_steps']):3}")
    print()
    print(f"📨 Messages:       {results['total_msg']}")
    print(f"   ✅ AA:         {results['aa_count']}")
    print(f"   ⚠️  AE:           {results['ae_count']}")
    print(f"   ⚠️  AR:           {results['ar_count']}")
    
    if results['total_msg'] > 0:
        rate = 100 * results['aa_count'] / results['total_msg']
        print(f"\n📈 Taux AA: {rate:.1f}%")
    
    print(f"\n⏰ Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
