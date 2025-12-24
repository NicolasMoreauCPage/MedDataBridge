#!/usr/bin/env python3
"""
Test roundtrip RÉEL avec serveur MLLP - Validation complète end-to-end
"""

import asyncio
import sys
import subprocess
import time
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_shared import SystemEndpoint
from app.services.scenario_runner import send_scenario
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload


class RealRoundtripTester:
    """Testeur roundtrip réel avec serveur MLLP"""

    def __init__(self, max_scenarios: int = 10):
        self.max_scenarios = max_scenarios
        self.server_process = None
        self.results = {
            'total_scenarios': 0,
            'successful_sends': 0,
            'successful_acks': 0,
            'validation_errors': 0,
            'network_errors': 0,
            'details': []
        }

    def start_mllp_server(self):
        """Démarre le serveur MLLP en arrière-plan (si pas déjà démarré)"""
        print("🔍 Vérification du serveur MLLP...")

        # Vérifier si un serveur tourne déjà sur le port 2575
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 2575))
        sock.close()

        if result == 0:
            print("✅ Serveur MLLP déjà actif sur localhost:2575")
            return True

        print("🚀 Démarrage du serveur MLLP de test...")
        try:
            self.server_process = subprocess.Popen(
                [sys.executable, 'simple_mllp_server.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path(__file__).parent
            )
            # Attendre que le serveur démarre
            time.sleep(2)

            if self.server_process.poll() is None:
                print("✅ Serveur MLLP démarré (PID: {})".format(self.server_process.pid))
                return True
            else:
                stdout, stderr = self.server_process.communicate()
                print(f"❌ Échec démarrage serveur: {stderr.decode()}")
                return False

        except Exception as e:
            print(f"❌ Erreur démarrage serveur: {e}")
            return False

    def stop_mllp_server(self):
        """Arrête le serveur MLLP"""
        if self.server_process:
            print("🛑 Arrêt du serveur MLLP...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
                print("✅ Serveur MLLP arrêté")
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                print("⚠️ Serveur MLLP forcé à s'arrêter")

    def get_test_endpoint(self, session: Session) -> SystemEndpoint:
        """Récupère ou crée un endpoint de test MLLP"""
        endpoint = session.exec(
            select(SystemEndpoint).where(
                SystemEndpoint.kind == 'MLLP',
                SystemEndpoint.host == 'localhost',
                SystemEndpoint.port == 2575
            )
        ).first()

        if not endpoint:
            endpoint = SystemEndpoint(
                name="Real Test MLLP Endpoint",
                kind="MLLP",
                role="TARGET",
                is_enabled=True,
                host="localhost",
                port=2575,
                sending_app="TEST_APP",
                sending_facility="TEST_FACILITY",
                receiving_app="TARGET_APP",
                receiving_facility="TARGET_FACILITY"
            )
            session.add(endpoint)
            session.commit()
            session.refresh(endpoint)

        return endpoint

    def validate_message_structure(self, payload: str) -> dict:
        """Valide la structure d'un message HL7"""
        validation = {
            'is_valid': False,
            'has_msh': False,
            'has_pid': False,
            'has_pv1': False,
            'control_id': None,
            'message_type': None,
            'errors': []
        }

        try:
            # Décodage des séquences d'échappement
            decoded = payload.replace('\\r', '\r').replace('\\n', '\n').replace('\\t', '\t')
            segments = decoded.split('\r')

            for segment in segments:
                if segment.startswith('MSH|'):
                    validation['has_msh'] = True
                    fields = segment.split('|')
                    if len(fields) >= 9:
                        validation['message_type'] = fields[8]
                    if len(fields) >= 10:
                        validation['control_id'] = fields[9]

                elif segment.startswith('PID|'):
                    validation['has_pid'] = True

                elif segment.startswith('PV1|'):
                    validation['has_pv1'] = True

            # Validation globale - MSH est obligatoire, Control ID est optionnel pour certains messages
            validation['is_valid'] = validation['has_msh']

            if not validation['has_msh']:
                validation['errors'].append("Segment MSH manquant")

        except Exception as e:
            validation['errors'].append(f"Erreur parsing: {str(e)}")

        return validation

    async def test_real_scenario(self, session: Session, scenario: InteropScenario, endpoint: SystemEndpoint) -> dict:
        """Test roundtrip réel d'un scénario"""
        result = {
            'scenario_name': scenario.name,
            'category': scenario.category,
            'messages_sent': 0,
            'acks_received': 0,
            'validation_ok': True,
            'network_ok': False,
            'errors': []
        }

        try:
            # Envoyer le scénario
            logs = await send_scenario(
                session=session,
                scenario=scenario,
                endpoint=endpoint,
                update_dates=True,
                dry_run=False
            )

            # Analyser les logs
            outbound_messages = []
            inbound_acks = []

            for log in logs:
                if log.direction == 'out' and log.payload:
                    result['messages_sent'] += 1
                    outbound_messages.append(log.payload)

                    # Valider la structure du message
                    validation = self.validate_message_structure(log.payload)
                    if not validation['is_valid']:
                        result['validation_ok'] = False
                        result['errors'].extend(validation['errors'])

                # Les ACKs sont dans ack_payload des messages sortants
                if log.direction == 'out' and log.ack_payload:
                    # Vérifier que c'est un ACK
                    if 'MSA|AA|' in log.ack_payload or 'MSA|CA|' in log.ack_payload:
                        result['acks_received'] += 1
                        inbound_acks.append(log.ack_payload)

            # Évaluation du succès
            result['network_ok'] = result['messages_sent'] > 0 and result['acks_received'] > 0

            if result['messages_sent'] == 0:
                result['errors'].append("Aucun message envoyé")
            if result['acks_received'] == 0:
                result['errors'].append("Aucun ACK reçu")

        except Exception as e:
            result['errors'].append(f"Erreur test: {str(e)}")

        return result

    async def run_real_tests(self):
        """Exécute les tests réels"""
        print("🔬 TESTS ROUNDTRIP RÉELS - VALIDATION END-TO-END")
        print("=" * 60)

        # Démarrer le serveur MLLP
        if not self.start_mllp_server():
            print("❌ Impossible de démarrer le serveur MLLP - arrêt des tests")
            return

        try:
            with Session(engine) as session:
                # Récupérer les scénarios de test
                scenarios = session.exec(
                    select(InteropScenario).options(selectinload(InteropScenario.steps)).where(
                        InteropScenario.category.in_(['IHE_PAM', 'HPRIM_COTATION'])
                    ).limit(self.max_scenarios)
                ).all()

                self.results['total_scenarios'] = len(scenarios)
                print(f"📊 {len(scenarios)} scénarios à tester en réel")
                print()

                # Endpoint de test
                endpoint = self.get_test_endpoint(session)
                print(f"🎯 Endpoint: {endpoint.name} ({endpoint.host}:{endpoint.port})")
                print()

                # Tester chaque scénario
                for i, scenario in enumerate(scenarios, 1):
                    print(f"[{i:2d}/{len(scenarios)}] Testing: {scenario.name}")

                    result = await self.test_real_scenario(session, scenario, endpoint)

                    # Analyser les résultats
                    if result['network_ok'] and result['validation_ok']:
                        self.results['successful_sends'] += 1
                        self.results['successful_acks'] += 1
                        status_icon = "✅"
                        status_text = "SUCCÈS"
                    elif result['network_ok'] and not result['validation_ok']:
                        self.results['successful_sends'] += 1
                        self.results['validation_errors'] += 1
                        status_icon = "⚠️ "
                        status_text = "RÉSEAU OK, VALIDATION NOK"
                    elif not result['network_ok'] and result['validation_ok']:
                        self.results['network_errors'] += 1
                        status_icon = "❌"
                        status_text = "RÉSEAU NOK"
                    else:
                        self.results['network_errors'] += 1
                        self.results['validation_errors'] += 1
                        status_icon = "💥"
                        status_text = "ÉCHEC TOTAL"

                    print(f"    {status_icon} {status_text}")
                    print(f"       Messages: {result['messages_sent']} envoyés, {result['acks_received']} ACKs")
                    if result['errors']:
                        print(f"       Erreurs: {', '.join(result['errors'])}")

                    # Stocker le détail
                    self.results['details'].append(result)
                    print()

            # Rapport final
            self.print_final_report()

        finally:
            self.stop_mllp_server()

    def print_final_report(self):
        """Affiche le rapport final"""
        print("=" * 60)
        print("📊 RAPPORT FINAL - TESTS RÉELS")
        print("=" * 60)

        print("📈 Statistiques:")
        print(f"   • Scénarios testés: {self.results['total_scenarios']}")
        print(f"   • Envois réussis: {self.results['successful_sends']}")
        print(f"   • ACKs reçus: {self.results['successful_acks']}")
        print(f"   • Erreurs réseau: {self.results['network_errors']}")
        print(f"   • Erreurs validation: {self.results['validation_errors']}")

        success_rate = self.results['successful_sends'] / self.results['total_scenarios'] * 100 if self.results['total_scenarios'] > 0 else 0
        ack_rate = self.results['successful_acks'] / self.results['total_scenarios'] * 100 if self.results['total_scenarios'] > 0 else 0

        print(f"   • Taux d'envoi: {success_rate:.1f}%")
        print(f"   • Taux d'ACK: {ack_rate:.1f}%")
        print()
        print("🔍 Analyse détaillée:")
        network_ok = self.results['successful_sends']
        validation_ok = self.results['successful_sends'] - self.results['validation_errors']

        print(f"   • Communication réseau: {network_ok}/{self.results['total_scenarios']} OK")
        print(f"   • Validation messages: {validation_ok}/{self.results['total_scenarios']} OK")
        print(f"   • ACKs reçus: {self.results['successful_acks']}/{self.results['total_scenarios']} OK")

        print()
        if success_rate >= 95 and ack_rate >= 95:
            print("🎉 SUCCÈS TOTAL ! Le système fonctionne parfaitement end-to-end !")
        elif success_rate >= 80:
            print("✅ BON RÉSULTAT ! Communication fonctionnelle avec quelques détails à ajuster.")
        else:
            print("⚠️ PROBLÈMES DÉTECTÉS ! Investigation nécessaire.")


async def main():
    """Fonction principale"""
    import argparse
    parser = argparse.ArgumentParser(description="Tests roundtrip réels avec serveur MLLP")
    parser.add_argument("--max-scenarios", type=int, default=10, help="Nombre maximum de scénarios à tester")

    args = parser.parse_args()

    tester = RealRoundtripTester(max_scenarios=args.max_scenarios)
    await tester.run_real_tests()


if __name__ == "__main__":
    asyncio.run(main())