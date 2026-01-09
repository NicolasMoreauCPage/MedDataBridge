#!/usr/bin/env python3
"""
Test de diagnostic simple pour les ACKs MLLP
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_shared import SystemEndpoint
from app.services.scenario_runner import send_scenario
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload


async def test_single_scenario():
    """Test d'un seul scénario pour diagnostiquer les ACKs"""
    print("🔍 DIAGNOSTIC - Test d'un seul scénario HPRIM")
    print("=" * 50)

    with Session(engine) as session:
        # Récupérer un scénario HPRIM simple
        scenario = session.exec(
            select(InteropScenario).options(selectinload(InteropScenario.steps)).where(
                InteropScenario.category == 'HPRIM_COTATION'
            ).limit(1)
        ).first()

        if not scenario:
            print("❌ Aucun scénario HPRIM trouvé")
            return

        print(f"📋 Test du scénario: {scenario.name}")
        print(f"📊 {len(scenario.steps)} étapes")

        # Endpoint de test
        endpoint = session.exec(
            select(SystemEndpoint).where(
                SystemEndpoint.kind == 'MLLP',
                SystemEndpoint.host == 'localhost',
                SystemEndpoint.port == 2575
            )
        ).first()

        if not endpoint:
            print("❌ Aucun endpoint MLLP trouvé")
            return

        print(f"🎯 Endpoint: {endpoint.name} ({endpoint.host}:{endpoint.port})")
        print()

        try:
            # Envoyer le scénario
            print("📤 Envoi du scénario...")
            logs = await send_scenario(
                session=session,
                scenario=scenario,
                endpoint=endpoint,
                update_dates=True,
                dry_run=False
            )

            print(f"📊 {len(logs)} logs récupérés")
            print()

            # Analyser les logs
            for i, log in enumerate(logs, 1):
                print(f"Log {i}:")
                print(f"  Direction: {log.direction}")
                print(f"  Kind: {log.kind}")
                print(f"  Status: {log.status}")
                print(f"  Payload length: {len(log.payload) if log.payload else 0}")
                print(f"  ACK payload length: {len(log.ack_payload) if log.ack_payload else 0}")

                if log.ack_payload:
                    print(f"  ACK preview: {log.ack_payload[:100]}...")
                    if 'MSA|AA|' in log.ack_payload:
                        print("  ✅ ACK positif détecté!")
                    elif 'MSA|AE|' in log.ack_payload:
                        print("  ⚠️ ACK d'erreur détecté!")
                    else:
                        print("  ❓ ACK de type inconnu")

                print()

        except Exception as e:
            print(f"❌ Erreur lors du test: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_single_scenario())