#!/usr/bin/env python3
"""
Test roundtrip simplifié pour vérifier l'intégration complète
"""

import asyncio
import sys
import socket
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_shared import SystemEndpoint
from app.services.scenario_runner import send_scenario
from sqlmodel import Session, select


def decode_hl7_payload(payload: str) -> str:
    """Décode un payload HL7 avec séquences d'échappement"""
    if not payload:
        return payload
    return payload.replace('\\r', '\r').replace('\\n', '\n').replace('\\t', '\t')


async def test_mllp_connection(host='localhost', port=2575):
    """Test si le serveur MLLP est accessible"""
    try:
        reader, writer = await asyncio.open_connection(host, port)
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False


async def send_hl7_message(message: str, host='localhost', port=2575):
    """Envoie un message HL7 et retourne la réponse"""
    try:
        # Encoder le message en MLLP
        mllp_message = b'\x0b' + message.encode('utf-8') + b'\x1c\r'

        reader, writer = await asyncio.open_connection(host, port)

        # Envoyer le message
        writer.write(mllp_message)
        await writer.drain()

        # Lire la réponse
        response_data = await reader.read(1024)
        response = response_data.decode('utf-8', errors='ignore')

        writer.close()
        await writer.wait_closed()

        return response.strip()
    except Exception as e:
        return f"ERROR: {e}"


async def test_roundtrip_scenario(scenario_name: str):
    """Test roundtrip complet pour un scénario"""
    print(f"\n🧪 Test roundtrip pour: {scenario_name}")

    try:
        # Vérifier la connexion MLLP
        if not await test_mllp_connection():
            print("❌ Serveur MLLP non accessible")
            return False

        print("✅ Serveur MLLP accessible")

        # Récupérer le scénario
        with Session(engine) as session:
            scenario = session.exec(
                select(InteropScenario).where(InteropScenario.name == scenario_name)
            ).first()

            if not scenario:
                print(f"❌ Scénario '{scenario_name}' non trouvé")
                return False

            print(f"📋 Scénario trouvé: {scenario.name} ({scenario.category})")

            # Récupérer les étapes
            steps = session.exec(
                select(InteropScenarioStep).where(InteropScenarioStep.scenario_id == scenario.id)
                .order_by(InteropScenarioStep.order_index)
            ).all()

            print(f"📝 {len(steps)} étapes à traiter")

            # Traiter chaque étape
            for i, step in enumerate(steps, 1):
                print(f"\n  Étape {i}/{len(steps)}: {step.name}")

                if step.message_format == 'hl7' and step.payload:
                    # Décoder le payload
                    decoded_payload = decode_hl7_payload(step.payload)
                    print(f"    📤 Envoi message HL7 ({len(decoded_payload)} chars)")

                    # Envoyer le message
                    response = await send_hl7_message(decoded_payload)
                    print(f"    📥 Réponse: {response[:100]}...")

                    # Valider la réponse
                    if 'MSA|AA|' in response:
                        print("    ✅ ACK positif reçu")
                    elif 'ERROR' in response:
                        print(f"    ❌ Erreur: {response}")
                        return False
                    else:
                        print(f"    ⚠️ Réponse inattendue: {response[:50]}...")
                else:
                    print(f"    ⏭️ Étape ignorée (format: {step.message_format})")

        print(f"✅ Test roundtrip réussi pour {scenario_name}")
        return True

    except Exception as e:
        print(f"❌ Erreur test roundtrip: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Fonction principale"""
    print("🚀 Test roundtrip complet - Vérification intégration")

    # Liste des scénarios à tester
    test_scenarios = [
        "IHE PAM - A31",
        "IHE PAM - 1Er Test Creationipp Et Dossier Dk"
    ]

    results = []

    for scenario_name in test_scenarios:
        success = await test_roundtrip_scenario(scenario_name)
        results.append((scenario_name, success))

    # Résumé
    print("\n" + "="*50)
    print("📊 RÉSULTATS DU TEST ROUNDTRIP")
    print("="*50)

    successful = sum(1 for _, success in results if success)
    total = len(results)

    for scenario, success in results:
        status = "✅ RÉUSSI" if success else "❌ ÉCHEC"
        print(f"{status}: {scenario}")

    print(f"\n📈 Score: {successful}/{total} scénarios réussis")

    if successful == total:
        print("🎉 Intégration complète validée !")
    else:
        print("⚠️ Problèmes d'intégration détectés")


if __name__ == "__main__":
    asyncio.run(main())