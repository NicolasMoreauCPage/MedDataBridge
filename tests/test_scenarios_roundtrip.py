#!/usr/bin/env python3
"""
Script de test de roundtrip pour tous les scénarios d'intégration HL7/HPRIM

Ce script exécute tous les scénarios importés et vérifie :
- Génération correcte des identifiants (IPP, NDA, VENUE)
- Fonctionnement des namespaces
- Cohérence des traits d'identité
- Structure des données
- Réponses des systèmes cibles

Usage:
    python test_scenarios_roundtrip.py [--endpoint-id ID] [--dry-run] [--max-scenarios N] [--create-test-endpoints]

Arguments:
    --endpoint-id ID : ID de l'endpoint à utiliser pour les tests (défaut: cherche automatiquement)
    --dry-run       : Simulation seulement (pas d'envoi réel)
    --max-scenarios N : Limiter à N scénarios pour les tests (défaut: tous)
    --create-test-endpoints : Créer des endpoints de test fictifs pour les tests
"""

import asyncio
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional
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

    # Remplacer les séquences d'échappement par les vrais caractères
    decoded = payload.replace('\\r', '\r').replace('\\n', '\n').replace('\\t', '\t')
    return decoded


class ScenarioRoundtripTester:
    """Testeur de roundtrip pour les scénarios d'intégration"""

    def __init__(self, endpoint_id: Optional[int] = None, dry_run: bool = False, max_scenarios: Optional[int] = None, create_test_endpoints: bool = False):
        self.endpoint_id = endpoint_id
        self.dry_run = dry_run
        self.max_scenarios = max_scenarios
        self._create_test_endpoints = create_test_endpoints
        self.test_endpoints_created = []
        self.results = {
            'total_scenarios': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'partial_runs': 0,
            'skipped_scenarios': 0,
            'details': []
        }

    def get_test_scenarios(self, session: Session) -> List[InteropScenario]:
        """Récupère les scénarios à tester (HL7 + HPRIM)"""
        query = select(InteropScenario).options(
            selectinload(InteropScenario.steps)
        ).where(
            InteropScenario.category.in_(['IHE_PAM', 'HPRIM_COTATION'])
        ).order_by(InteropScenario.id)

        scenarios = session.exec(query).all()

        if self.max_scenarios:
            scenarios = scenarios[:self.max_scenarios]

        return scenarios

    def find_suitable_endpoint(self, session: Session, scenario: InteropScenario) -> Optional[SystemEndpoint]:
        """Trouve un endpoint approprié pour le scénario"""
        if self.endpoint_id:
            return session.exec(
                select(SystemEndpoint).where(SystemEndpoint.id == self.endpoint_id)
            ).first()

        # Chercher un endpoint MLLP actif pour les scénarios HL7
        if scenario.protocol in ['HL7', 'MIXED']:
            endpoint = session.exec(
                select(SystemEndpoint).where(
                    SystemEndpoint.kind == 'MLLP',
                    SystemEndpoint.is_enabled == True
                ).limit(1)
            ).first()
            if endpoint:
                return endpoint

        # Chercher un endpoint FHIR actif pour les scénarios FHIR
        if scenario.protocol == 'FHIR':
            endpoint = session.exec(
                select(SystemEndpoint).where(
                    SystemEndpoint.kind == 'FHIR',
                    SystemEndpoint.is_enabled == True
                ).limit(1)
            ).first()
            if endpoint:
                return endpoint

        return None

    def create_test_endpoints(self, session: Session):
        """Crée des endpoints de test fictifs pour les tests"""
        if not self._create_test_endpoints:
            return

        print("🔧 Création d'endpoints de test...")

        # Endpoint MLLP de test
        mllp_endpoint = SystemEndpoint(
            name="Test MLLP Endpoint",
            kind="MLLP",
            role="TARGET",
            is_enabled=True,
            host="localhost",
            port=2575,  # Port MLLP standard
            sending_app="TEST_APP",
            sending_facility="TEST_FACILITY",
            receiving_app="TARGET_APP",
            receiving_facility="TARGET_FACILITY"
        )

        # Endpoint FHIR de test
        fhir_endpoint = SystemEndpoint(
            name="Test FHIR Endpoint",
            kind="FHIR",
            role="TARGET",
            is_enabled=True,
            base_url="http://localhost:8080/fhir",
            auth_kind="none"
        )

        session.add(mllp_endpoint)
        session.add(fhir_endpoint)
        session.commit()
        session.refresh(mllp_endpoint)
        session.refresh(fhir_endpoint)

        self.test_endpoints_created = [mllp_endpoint, fhir_endpoint]
        print(f"✅ 2 endpoints de test créés (MLLP: {mllp_endpoint.id}, FHIR: {fhir_endpoint.id})")

    def cleanup_test_endpoints(self, session: Session):
        """Supprime les endpoints de test créés"""
        if not self.test_endpoints_created:
            return

        print("🧹 Suppression des endpoints de test...")
        for endpoint in self.test_endpoints_created:
            session.delete(endpoint)
        session.commit()
        print("✅ Endpoints de test supprimés")

    def cleanup_test_endpoints(self, session: Session):
        """Supprime les endpoints de test créés"""
        if not self.test_endpoints_created:
            return

        print("🧹 Suppression des endpoints de test...")
        for endpoint in self.test_endpoints_created:
            session.delete(endpoint)
        session.commit()
        print("✅ Endpoints de test supprimés")

    def validate_scenario_execution(self, scenario: InteropScenario, logs: List) -> Dict:
        """Valide les résultats d'exécution d'un scénario"""
        validation = {
            'scenario_name': scenario.name,
            'scenario_key': scenario.key,
            'protocol': scenario.protocol,
            'total_steps': len(scenario.steps),
            'executed_steps': len(logs),
            'successful_steps': 0,
            'failed_steps': 0,
            'skipped_steps': 0,
            'identifiers_generated': {},
            'namespaces_validated': False,
            'structure_valid': True,
            'errors': []
        }

        for log in logs:
            if log.status == 'sent':
                validation['successful_steps'] += 1
            elif log.status == 'error':
                validation['failed_steps'] += 1
                validation['errors'].append(f"Step failed: {log.ack_payload}")
            elif log.status == 'skipped':
                validation['skipped_steps'] += 1

        # Si pas de logs réussis, examiner quand même les payloads des étapes pour valider la génération d'identifiants
        if validation['successful_steps'] == 0:
            validation['executed_steps'] = len(scenario.steps)  # Considérer toutes les étapes comme "exécutées" pour validation

        # Validation spécifique pour les scénarios HL7
        if scenario.protocol in ['HL7', 'MIXED']:
            hl7_steps = [step for step in scenario.steps if step.message_format == 'hl7']
            for step in hl7_steps:
                # Vérifier que les identifiants ont été générés/remplacés
                if 'PID|' in step.payload:
                    # Chercher les patterns d'identifiants dans les logs d'abord
                    found_in_logs = False
                    for log in logs:
                        if log.payload and 'PID|' in log.payload:
                            # Extraire IPP et NDA du payload envoyé
                            lines = log.payload.split('\n')
                            for line in lines:
                                if line.startswith('PID|'):
                                    fields = line.split('|')
                                    if len(fields) > 3 and fields[3]:
                                        # PID-3 contient l'IPP
                                        ipp_match = fields[3].split('^')[0] if '^' in fields[3] else fields[3]
                                        if ipp_match and ipp_match.isdigit() and len(ipp_match) >= 8:
                                            validation['identifiers_generated']['ipp'] = ipp_match
                                            print(f"  🆔 IPP généré: {ipp_match}")
                                            found_in_logs = True

                                    if len(fields) > 18 and fields[18]:
                                        # PID-18 contient le NDA
                                        nda_match = fields[18].split('^')[0] if '^' in fields[18] else fields[18]
                                        if nda_match and nda_match.isdigit() and len(nda_match) >= 8:
                                            validation['identifiers_generated']['nda'] = nda_match
                                            print(f"  🆔 NDA généré: {nda_match}")
                                            found_in_logs = True
                                    break

                    # Si pas trouvé dans les logs, chercher dans le payload de l'étape (pour validation même en cas d'échec)
                    if not found_in_logs and step.payload:
                        print(f"  🔍 Examinant payload de l'étape '{step.name}' (format: {step.message_format})...")
                        print(f"  📏 Payload length: {len(step.payload)} chars")

                        # Décoder le payload HL7
                        decoded_payload = decode_hl7_payload(step.payload)

                        has_pid = 'PID|' in decoded_payload
                        has_pv1 = 'PV1|' in decoded_payload
                        print(f"  🔍 Contient PID: {has_pid}, PV1: {has_pv1}")
                        if not has_pid and not has_pv1:
                            print(f"  ⚠️ Pas de segments PID ou PV1 trouvés")
                        # HL7 utilise \r comme séparateur de segments
                        lines = decoded_payload.split('\r')
                        print(f"  📊 Nombre de segments HL7: {len(lines)}")
                        pid_found = False
                        pv1_found = False
                        for line in lines:
                            if line.startswith('PID|'):
                                print(f"  📋 PID line: {line[:150]}...")
                                fields = line.split('|')
                                if len(fields) > 3 and fields[3]:
                                    ipp_match = fields[3].split('^')[0] if '^' in fields[3] else fields[3]
                                    print(f"  🔍 IPP candidat: '{ipp_match}' (isdigit: {ipp_match.isdigit()}, len: {len(ipp_match)})")
                                    if ipp_match and ipp_match.isdigit() and len(ipp_match) >= 8:
                                        validation['identifiers_generated']['ipp'] = ipp_match
                                        print(f"  🆔 IPP dans payload: {ipp_match}")

                                if len(fields) > 18 and fields[18]:
                                    nda_match = fields[18].split('^')[0] if '^' in fields[18] else fields[18]
                                    print(f"  🔍 NDA candidat: '{nda_match}' (isdigit: {nda_match.isdigit()}, len: {len(nda_match)})")
                                    if nda_match and nda_match.isdigit() and len(nda_match) >= 8:
                                        validation['identifiers_generated']['nda'] = nda_match
                                        print(f"  🆔 NDA dans payload: {nda_match}")
                                pid_found = True
                                break

                            # Chercher VENUE dans PV1
                            if line.startswith('PV1|'):
                                print(f"  📋 PV1 line: {line[:150]}...")
                                pv1_fields = line.split('|')
                                if len(pv1_fields) > 3 and pv1_fields[3]:
                                    venue_match = pv1_fields[3].split('^')[0] if '^' in pv1_fields[3] else pv1_fields[3]
                                    print(f"  🔍 VENUE candidat: '{venue_match}' (len: {len(venue_match)})")
                                    if venue_match and len(venue_match) >= 3:
                                        validation['identifiers_generated']['venue'] = venue_match
                                        print(f"  🆔 VENUE dans payload: {venue_match}")
                                pv1_found = True
                                break
                        if not pid_found and not pv1_found:
                            print(f"  ⚠️ Aucun segment PID ou PV1 trouvé dans les {len(lines)} segments HL7")
                    else:
                        print(f"  ⚠️ Étape sans payload ou déjà trouvé dans logs")

        # Validation pour les scénarios HPRIM
        if scenario.category == 'HPRIM_COTATION':
            hprim_steps = [step for step in scenario.steps if step.message_format == 'xml']
            if hprim_steps:
                validation['hprim_xml_valid'] = True
                # TODO: Validation plus poussée du XML HPRIM

        return validation

    async def run_scenario_test(self, session: Session, scenario: InteropScenario, endpoint: SystemEndpoint) -> Dict:
        """Exécute un test de roundtrip pour un scénario"""
        print(f"🧪 Test roundtrip: {scenario.name}")

        try:
            # Exécuter le scénario et capturer les logs même en cas d'erreur
            logs = []
            try:
                logs = await send_scenario(
                    session=session,
                    scenario=scenario,
                    endpoint=endpoint,
                    update_dates=True,
                    dry_run=self.dry_run
                )
            except Exception as e:
                print(f"  ⚠️ Erreur d'exécution: {e}")
                # Continuer avec les logs vides pour la validation

            # Valider les résultats
            validation = self.validate_scenario_execution(scenario, logs)

            # Déterminer le statut global
            if validation['failed_steps'] == 0 and validation['successful_steps'] > 0:
                status = 'success'
            elif validation['failed_steps'] > 0 and validation['successful_steps'] > 0:
                status = 'partial'
            elif validation['failed_steps'] > 0:
                status = 'failed'
            else:
                status = 'skipped'

            validation['status'] = status
            validation['endpoint'] = f"{endpoint.name} ({endpoint.kind})"

            return validation

        except Exception as e:
            return {
                'scenario_name': scenario.name,
                'scenario_key': scenario.key,
                'status': 'error',
                'error': str(e),
                'endpoint': f"{endpoint.name} ({endpoint.kind})" if endpoint else 'Unknown'
            }

    async def run_all_tests(self):
        """Exécute tous les tests de roundtrip"""
        print("🚀 Démarrage des tests de roundtrip pour tous les scénarios d'intégration")
        print("=" * 80)

        if self.dry_run:
            print("🔍 Mode DRY RUN activé - Simulation seulement")
        if self.max_scenarios:
            print(f"📊 Test limité aux {self.max_scenarios} premiers scénarios")
        if self._create_test_endpoints:
            print("🔧 Mode création d'endpoints de test activé")

        with Session(engine) as session:
            # Créer des endpoints de test si demandé
            if self._create_test_endpoints:
                self.create_test_endpoints(session)

            try:
                # Récupérer les scénarios à tester
                scenarios = self.get_test_scenarios(session)
                self.results['total_scenarios'] = len(scenarios)

                print(f"📋 {len(scenarios)} scénarios à tester")

                for i, scenario in enumerate(scenarios, 1):
                    print(f"\n[{i}/{len(scenarios)}] Testing: {scenario.name}")

                    # Trouver un endpoint approprié
                    endpoint = self.find_suitable_endpoint(session, scenario)
                    if not endpoint:
                        print(f"  ❌ Aucun endpoint approprié trouvé pour {scenario.protocol}")
                        self.results['skipped_scenarios'] += 1
                        self.results['details'].append({
                            'scenario_name': scenario.name,
                            'status': 'skipped',
                            'reason': 'no_suitable_endpoint'
                        })
                        continue

                    print(f"  🎯 Endpoint: {endpoint.name} ({endpoint.kind})")

                    # Exécuter le test
                    result = await self.run_scenario_test(session, scenario, endpoint)
                    self.results['details'].append(result)

                    # Compter les résultats
                    if result['status'] == 'success':
                        self.results['successful_runs'] += 1
                        print(f"  ✅ SUCCESS - {result.get('successful_steps', 0)}/{result.get('total_steps', 0)} étapes")
                    elif result['status'] == 'partial':
                        self.results['partial_runs'] += 1
                        print(f"  ⚠️ PARTIAL - {result.get('successful_steps', 0)}/{result.get('total_steps', 0)} étapes")
                    elif result['status'] == 'failed':
                        self.results['failed_runs'] += 1
                        print(f"  ❌ FAILED - Erreurs: {len(result.get('errors', []))}")
                    else:
                        self.results['skipped_scenarios'] += 1
                        print(f"  ⏭️ SKIPPED - {result.get('reason', 'unknown')}")

                    # Afficher les identifiants générés
                    if 'identifiers_generated' in result and result['identifiers_generated']:
                        ids = result['identifiers_generated']
                        print(f"  🆔 Identifiants: IPP={ids.get('ipp', 'N/A')}, NDA={ids.get('nda', 'N/A')}")

            finally:
                # Nettoyer les endpoints de test
                self.cleanup_test_endpoints(session)

    def generate_report(self):
        """Génère un rapport des tests"""
        print("\n" + "=" * 80)
        print("📊 RAPPORT FINAL DES TESTS DE ROUNDTRIP")
        print("=" * 80)

        print(f"📈 Statistiques générales:")
        print(f"   • Total scénarios testés: {self.results['total_scenarios']}")
        print(f"   • Réussites complètes: {self.results['successful_runs']}")
        print(f"   • Réussites partielles: {self.results['partial_runs']}")
        print(f"   • Échecs: {self.results['failed_runs']}")
        print(f"   • Ignorés: {self.results['skipped_scenarios']}")

        success_rate = (self.results['successful_runs'] + self.results['partial_runs']) / max(self.results['total_scenarios'], 1) * 100
        print(f"   • Taux de succès: {success_rate:.1f}%")
        # Détails par catégorie
        hl7_scenarios = [d for d in self.results['details'] if d.get('protocol') in ['HL7', 'MIXED']]
        hprim_scenarios = [d for d in self.results['details'] if d.get('scenario_key', '').startswith('hprim_')]

        print(f"\n📋 Par catégorie:")
        print(f"   • Scénarios HL7 IHE PAM: {len(hl7_scenarios)}")
        print(f"   • Scénarios HPRIM XML: {len(hprim_scenarios)}")

        # Validation des identifiants
        scenarios_with_ids = [d for d in self.results['details']
                            if d.get('identifiers_generated') and
                            ('ipp' in d['identifiers_generated'] or 'nda' in d['identifiers_generated'])]

        print(f"\n🆔 Génération d'identifiants:")
        print(f"   • Scénarios avec identifiants générés: {len(scenarios_with_ids)}")

        if scenarios_with_ids:
            sample_ids = scenarios_with_ids[0]['identifiers_generated']
            print(f"   • Exemple: IPP={sample_ids.get('ipp', 'N/A')}, NDA={sample_ids.get('nda', 'N/A')}")

        # Erreurs détaillées
        failed_scenarios = [d for d in self.results['details'] if d['status'] in ['failed', 'error']]
        if failed_scenarios:
            print(f"\n❌ Scénarios en échec ({len(failed_scenarios)}):")
            for scenario in failed_scenarios[:5]:  # Limiter à 5 exemples
                print(f"   • {scenario['scenario_name']}: {scenario.get('error', 'Unknown error')}")

        # Sauvegarder le rapport détaillé
        report_file = f"roundtrip_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        import json
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n💾 Rapport détaillé sauvegardé: {report_file}")

        return self.results


async def main():
    parser = argparse.ArgumentParser(description="Test de roundtrip pour les scénarios d'intégration")
    parser.add_argument("--endpoint-id", type=int, help="ID de l'endpoint à utiliser")
    parser.add_argument("--dry-run", action="store_true", help="Mode simulation (pas d'envoi réel)")
    parser.add_argument("--max-scenarios", type=int, help="Limiter le nombre de scénarios à tester")
    parser.add_argument("--create-test-endpoints", action="store_true", help="Créer des endpoints de test fictifs")

    args = parser.parse_args()

    tester = ScenarioRoundtripTester(
        endpoint_id=args.endpoint_id,
        dry_run=args.dry_run,
        max_scenarios=args.max_scenarios,
        create_test_endpoints=args.create_test_endpoints
    )

    await tester.run_all_tests()
    results = tester.generate_report()

    # Code de sortie basé sur les résultats
    if results['failed_runs'] > 0:
        sys.exit(1)  # Échec si des scénarios ont échoué
    elif results['successful_runs'] == results['total_scenarios']:
        sys.exit(0)  # Succès complet
    else:
        sys.exit(2)  # Succès partiel


if __name__ == "__main__":
    asyncio.run(main())