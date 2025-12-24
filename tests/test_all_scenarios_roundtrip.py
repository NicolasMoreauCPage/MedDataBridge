#!/usr/bin/env python3
"""
Test roundtrip complet sur TOUS les scénarios seedés (étapes 5 et 6 de init_db.py)

Teste les 159 scénarios d'intégration HL7/HPRIM avec validation complète :
- Structure des payloads
- Génération d'identifiants IPP/NDA/VENUE
- Communication MLLP (si serveur disponible)
- ACKs et réponses

Usage:
    python test_all_scenarios_roundtrip.py [--real-run] [--max-scenarios N]
"""

import asyncio
import sys
import argparse
from pathlib import Path
from typing import Dict, List
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_shared import SystemEndpoint
from app.services.scenario_runner import send_scenario
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload


def decode_hl7_payload(payload: str) -> str:
    """Décode un payload HL7 avec séquences d'échappement"""
    if not payload:
        return payload
    return payload.replace('\\r', '\r').replace('\\n', '\n').replace('\\t', '\t')


class CompleteRoundtripTester:
    """Testeur roundtrip complet pour tous les scénarios seedés"""

    def __init__(self, real_run: bool = False, max_scenarios: int = None):
        self.real_run = real_run
        self.max_scenarios = max_scenarios
        self.results = {
            'total_scenarios': 0,
            'by_category': {},
            'identifiers_found': {'ipp': 0, 'nda': 0, 'venue': 0, 'movement': 0},
            'validation_errors': 0,
            'network_errors': 0,
            'successful_tests': 0,
            'details': []
        }

    def get_all_seeded_scenarios(self, session: Session) -> List[InteropScenario]:
        """Récupère tous les scénarios seedés (IHE_PAM + HPRIM_COTATION)"""
        query = select(InteropScenario).options(
            selectinload(InteropScenario.steps)
        ).where(
            InteropScenario.category.in_(['IHE_PAM', 'HPRIM_COTATION'])
        ).order_by(InteropScenario.id)

        scenarios = session.exec(query).all()

        if self.max_scenarios:
            scenarios = scenarios[:self.max_scenarios]

        return scenarios

    def find_test_endpoint(self, session: Session, scenario: InteropScenario) -> SystemEndpoint:
        """Trouve un endpoint de test approprié"""
        # Chercher un endpoint MLLP de test
        endpoint = session.exec(
            select(SystemEndpoint).where(
                SystemEndpoint.kind == 'MLLP',
                SystemEndpoint.is_enabled == True
            ).limit(1)
        ).first()

        if not endpoint:
            # Créer un endpoint de test temporaire
            endpoint = SystemEndpoint(
                name="Test Roundtrip Endpoint",
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

    def validate_scenario_payloads(self, scenario: InteropScenario) -> Dict:
        """Valide les payloads d'un scénario (structure + identifiants)"""
        validation = {
            'scenario_name': scenario.name,
            'category': scenario.category,
            'total_steps': len(scenario.steps),
            'hl7_steps': 0,
            'identifiers': {'ipp': [], 'nda': [], 'venue': [], 'movement': []},
            'parsing_errors': 0,
            'status': 'unknown'
        }

        for step in scenario.steps:
            if step.message_format == 'hl7' and step.payload:
                validation['hl7_steps'] += 1

                # Décoder et analyser le payload
                decoded_payload = decode_hl7_payload(step.payload)

                # Séparer les segments
                segments = decoded_payload.split('\r')

                # Chercher PID et PV1
                pid_found = False
                pv1_found = False

                for segment in segments:
                    if segment.startswith('PID|'):
                        # Extraire IPP (PID-3) et NDA (PID-18)
                        fields = segment.split('|')
                        if len(fields) > 3 and fields[3]:
                            ipp = fields[3].split('^')[0]
                            if ipp and ipp.isdigit() and len(ipp) >= 8:
                                validation['identifiers']['ipp'].append(ipp)

                        if len(fields) > 18 and fields[18]:
                            nda = fields[18].split('^')[0]
                            if nda and nda.isdigit() and len(nda) >= 8:
                                validation['identifiers']['nda'].append(nda)

                        pid_found = True

                    elif segment.startswith('PV1|'):
                        # Extraire VENUE (PV1-3)
                        fields = segment.split('|')
                        if len(fields) > 3 and fields[3]:
                            venue = fields[3].split('^')[0]
                            if venue and len(venue) >= 3:
                                validation['identifiers']['venue'].append(venue)

                        pv1_found = True

                    elif segment.startswith('ZBE|'):
                        # Extraire identifiant de mouvement (ZBE-1) pour IHE PAM
                        fields = segment.split('|')
                        if len(fields) > 1 and fields[1]:
                            movement_id = fields[1].split('^')[0]
                            if movement_id and movement_id.isdigit():
                                validation['identifiers']['movement'].append(movement_id)

                # Validation des segments requis
                if not pid_found:
                    validation['parsing_errors'] += 1
                if not pv1_found and 'PV1' in decoded_payload:
                    validation['parsing_errors'] += 1

        # Déterminer le statut
        has_identifiers = any(validation['identifiers'].values())
        has_errors = validation['parsing_errors'] > 0

        if has_identifiers and not has_errors:
            validation['status'] = 'valid'
        elif has_identifiers and has_errors:
            validation['status'] = 'partial'
        elif has_errors:
            validation['status'] = 'invalid'
        else:
            validation['status'] = 'empty'

        return validation

    async def test_scenario_roundtrip(self, session: Session, scenario: InteropScenario, endpoint: SystemEndpoint) -> Dict:
        """Test roundtrip complet d'un scénario"""
        result = {
            'scenario_name': scenario.name,
            'category': scenario.category,
            'status': 'unknown',
            'network_success': False,
            'validation_success': False,
            'error': None
        }

        try:
            if self.real_run:
                # Test réel avec envoi de messages
                logs = await send_scenario(
                    session=session,
                    scenario=scenario,
                    endpoint=endpoint,
                    update_dates=True,
                    dry_run=False
                )

                # Analyser les logs pour valider le succès
                if logs and len(logs) > 0:
                    # Vérifier que des messages ont été envoyés et des ACKs reçus
                    sent_messages = [log for log in logs if log.direction == 'OUTBOUND']
                    received_acks = [log for log in logs if log.direction == 'INBOUND' and 'MSA|AA|' in (log.payload or '')]

                    if sent_messages and received_acks:
                        result['network_success'] = True
                        result['status'] = 'success'
                    elif sent_messages:
                        result['status'] = 'sent_no_ack'
                    else:
                        result['status'] = 'send_failed'
                else:
                    result['status'] = 'no_logs'
            else:
                # Validation dry-run
                validation = self.validate_scenario_payloads(scenario)
                result['validation_success'] = validation['status'] in ['valid', 'partial']
                result['status'] = validation['status']

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)

        return result

    async def run_complete_test(self):
        """Exécute le test complet sur tous les scénarios"""
        print("🚀 Test roundtrip complet sur TOUS les scénarios seedés")
        print("=" * 70)
        print(f"Mode: {'RÉEL (avec réseau)' if self.real_run else 'DRY-RUN (validation seulement)'}")
        if self.max_scenarios:
            print(f"Limité à: {self.max_scenarios} scénarios")
        print()

        with Session(engine) as session:
            # Récupérer tous les scénarios
            scenarios = self.get_all_seeded_scenarios(session)
            self.results['total_scenarios'] = len(scenarios)

            print(f"📊 {len(scenarios)} scénarios à tester")

            # Trouver un endpoint de test
            endpoint = self.find_test_endpoint(session, scenarios[0] if scenarios else None)
            print(f"🎯 Endpoint de test: {endpoint.name} ({endpoint.kind})")
            print()

            # Tester chaque scénario
            for i, scenario in enumerate(scenarios, 1):
                print(f"[{i:3d}/{len(scenarios)}] Testing: {scenario.name}")

                # Validation des payloads (toujours faite)
                validation = self.validate_scenario_payloads(scenario)

                # Test roundtrip
                result = await self.test_scenario_roundtrip(session, scenario, endpoint)

                # Agréger les résultats
                cat = scenario.category or 'Unknown'
                if cat not in self.results['by_category']:
                    self.results['by_category'][cat] = {'total': 0, 'success': 0, 'partial': 0, 'failed': 0}

                self.results['by_category'][cat]['total'] += 1

                # Compter les identifiants trouvés
                for id_type, ids in validation['identifiers'].items():
                    if ids:
                        self.results['identifiers_found'][id_type] += len(ids)

                # Déterminer le succès global
                if result['status'] in ['success', 'valid']:
                    self.results['successful_tests'] += 1
                    self.results['by_category'][cat]['success'] += 1
                    status_icon = "✅"
                elif result['status'] in ['partial']:
                    self.results['by_category'][cat]['partial'] += 1
                    status_icon = "⚠️ "
                else:
                    self.results['by_category'][cat]['failed'] += 1
                    status_icon = "❌"

                print(f"    {status_icon} {result['status']} - {validation['hl7_steps']} étapes HL7, {len(validation['identifiers']['ipp'])} IPP, {len(validation['identifiers']['nda'])} NDA, {len(validation['identifiers']['movement'])} MOV")

                # Stocker le détail
                self.results['details'].append({
                    'scenario': scenario.name,
                    'category': cat,
                    'status': result['status'],
                    'hl7_steps': validation['hl7_steps'],
                    'identifiers': validation['identifiers'],
                    'parsing_errors': validation['parsing_errors']
                })

        # Rapport final
        self.print_final_report()

    def print_final_report(self):
        """Affiche le rapport final des tests"""
        print("\n" + "=" * 70)
        print("📊 RAPPORT FINAL - TEST ROUNDTRIP COMPLET")
        print("=" * 70)

        print(f"📈 Statistiques générales:")
        print(f"   • Total scénarios testés: {self.results['total_scenarios']}")
        print(f"   • Tests réussis: {self.results['successful_tests']}")
        success_rate = self.results['successful_tests'] / self.results['total_scenarios'] * 100 if self.results['total_scenarios'] > 0 else 0
        print(f"   • Taux de succès: {success_rate:.1f}%")
        print(f"   • Mode: {'RÉEL' if self.real_run else 'DRY-RUN'}")

        print(f"\n📋 Par catégorie:")
        for cat, stats in self.results['by_category'].items():
            success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"   • {cat}: {stats['total']} scénarios ({success_rate:.1f}% succès)")

        print(f"\n🆔 Identifiants générés:")
        print(f"   • IPP trouvés: {self.results['identifiers_found']['ipp']}")
        print(f"   • NDA trouvés: {self.results['identifiers_found']['nda']}")
        print(f"   • VENUE trouvés: {self.results['identifiers_found']['venue']}")
        print(f"   • MOUVEMENTS trouvés: {self.results['identifiers_found']['movement']}")

        # Résumé final
        overall_success = self.results['successful_tests'] / self.results['total_scenarios'] * 100
        if overall_success >= 95:
            print(f"\n🎉 SUCCÈS EXCEPTIONNEL: {overall_success:.1f}% des scénarios validés!")
            print("   Les scénarios seedés sont parfaitement intégrés.")
        elif overall_success >= 80:
            print(f"\n✅ BON RÉSULTAT: {overall_success:.1f}% des scénarios validés.")
            print("   Intégration majoritairement réussie.")
        else:
            print(f"\n⚠️ RÉSULTATS MOYENS: {overall_success:.1f}% des scénarios validés.")
            print("   Des améliorations sont nécessaires.")

        # Sauvegarder le rapport détaillé
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"roundtrip_complete_report_{timestamp}.json"

        import json
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Rapport détaillé sauvegardé: {report_file}")


async def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description="Test roundtrip complet sur tous les scénarios seedés")
    parser.add_argument("--real-run", action="store_true", help="Exécuter les tests réels (avec réseau)")
    parser.add_argument("--max-scenarios", type=int, help="Limiter le nombre de scénarios à tester")

    args = parser.parse_args()

    tester = CompleteRoundtripTester(real_run=args.real_run, max_scenarios=args.max_scenarios)
    await tester.run_complete_test()


if __name__ == "__main__":
    asyncio.run(main())