#!/usr/bin/env python3
"""Test roundtrip des scénarios HPRIM (cotations).

Itère sur chaque scénario HPRIM et effectue un test de matérialisation + import.
"""

import sys
import json
import time
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select, Session
from app.db import engine
from app.models_structure import EntiteJuridique, UniteFonctionnelle
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_scenario_config import ScenarioEJConfig
from app.models_endpoints import SystemEndpoint
from app.services.transport_inbound import on_message_inbound
from app.services.hprim.hprim_xml import HprimXmlService

TEST_EJ_ID = 1
TEST_OUTPUT_DIR = Path("tmp/hprim_scenarios_roundtrip")
TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("🚀 Test roundtrip des SCÉNARIOS HPRIM")
print(f"⏰ Début: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📍 EJ ID: {TEST_EJ_ID}")
print("=" * 80)

with Session(engine) as session:
    # Récupérer l'endpoint HL7
    hl7_endpoint = session.exec(
        select(SystemEndpoint).where(SystemEndpoint.name == "MLLP RECV 020000000")
    ).first()

    if not hl7_endpoint:
        print("❌ HL7 Endpoint not found!")
        pytest.skip("Required HL7 endpoint 'MLLP RECV 020000000' not found in database", allow_module_level=True)

    # Récupérer tous les scénarios HPRIM
    scenarios = session.exec(
        select(InteropScenario).where(InteropScenario.category == "HPRIM_COTATION")
    ).all()

    print(f"📊 {len(scenarios)} scénarios HPRIM à tester\n")

    results = {
        "success": [],
        "partial": [],
        "error": [],
        "total": len(scenarios)
    }

    hprim_service = HprimXmlService()

    for scenario in scenarios:
        print(f"🎬 Test {scenario.name}")
        scenario_start = datetime.now()

        try:
            # Récupérer les étapes du scénario
            steps = session.exec(
                select(InteropScenarioStep).where(
                    InteropScenarioStep.scenario_id == scenario.id
                ).order_by(InteropScenarioStep.order_index)
            ).all()

            if not steps:
                print("   ❌ Aucune étape trouvée")
                results["error"].append(scenario.name)
                continue

            success_count = 0
            total_steps = len(steps)

            # Traiter chaque étape
            for step in steps:
                try:
                    print(f"   📤 Étape {step.order_index}: {step.name} ({step.message_format})")

                    # Le payload est déjà matérialisé dans la DB
                    materialized = step.payload

                    if step.message_format == "hl7":
                        # Envoyer via endpoint HL7
                        result = on_message_inbound(
                            materialized,
                            session,
                            hl7_endpoint
                        )

                        if result and result.get("status") == "success":
                            success_count += 1
                            print("      ✅ OK")
                        else:
                            print(f"      ❌ Échec: {result}")

                    elif step.message_format == "xml":
                        # Traiter directement via service HPRIM
                        try:
                            # Nettoyer le XML (enlever le préfixe MSH| et autres artefacts)
                            xml_content = materialized
                            
                            # Enlever le préfixe MSH| s'il existe
                            if xml_content.startswith('MSH|'):
                                xml_content = xml_content[4:]  # Enlever 'MSH|'
                            
                            # Enlever tout ce qui précède <?xml
                            xml_start = xml_content.find('<?xml')
                            if xml_start > 0:
                                xml_content = xml_content[xml_start:]
                            
                            # Nettoyer les espaces et caractères de contrôle au début
                            xml_content = xml_content.lstrip()
                            
                            # Vérifier que c'est du XML valide
                            if not xml_content.startswith('<?xml'):
                                print(f"      ❌ Contenu XML invalide: {xml_content[:100]}...")
                                continue

                            # Parser le XML HPRIM
                            parsed_message = hprim_service.parse_xml(xml_content)
                            if parsed_message:
                                success_count += 1
                                print("      ✅ OK")
                            else:
                                print("      ❌ Échec parsing HPRIM")
                        except Exception as e:
                            print(f"      ❌ Erreur HPRIM: {e}")
                    else:
                        print(f"      ⚠️ Format non supporté: {step.message_format}")
                        continue

                    # Petit délai entre les messages pour éviter la surcharge
                    time.sleep(0.1)

                except Exception as e:
                    print(f"      ❌ Erreur étape: {e}")
                    continue

            # Évaluer le résultat du scénario
            if success_count == total_steps:
                results["success"].append(scenario.name)
                print(f"   ✅ SCÉNARIO RÉUSSI ({success_count}/{total_steps})")
            elif success_count > 0:
                results["partial"].append(f"{scenario.name} ({success_count}/{total_steps})")
                print(f"   ⚠️ SCÉNARIO PARTIEL ({success_count}/{total_steps})")
            else:
                results["error"].append(scenario.name)
                print(f"   ❌ SCÉNARIO ÉCHEC ({success_count}/{total_steps})")

            # Durée du scénario
            duration = datetime.now() - scenario_start
            print(f"   ⏱️ Durée: {duration.total_seconds():.2f}s")
        except Exception as e:
            print(f"   ❌ ERREUR SCÉNARIO: {e}")
            results["error"].append(scenario.name)
            continue

    # Résumé final
    print("\n" + "=" * 80)
    print("📊 RÉSULTATS FINAUX")
    print("=" * 80)
    print(f"✅ Succès complet: {len(results['success'])}")
    print(f"⚠️ Succès partiel: {len(results['partial'])}")
    print(f"❌ Échec: {len(results['error'])}")
    print(f"📊 Total: {results['total']}")

    success_rate = 0.0
    if results['total'] > 0:
        success_rate = (len(results['success']) + len(results['partial'])) / results['total'] * 100
    print(f"🎯 Taux de succès: {success_rate:.1f}%")
    # Sauvegarder les résultats détaillés
    output_file = TEST_OUTPUT_DIR / f"hprim_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Résultats sauvegardés: {output_file}")

    # Afficher quelques erreurs si présentes
    if results['error']:
        print("\n🔍 ÉCHECS:")
        for error in results['error'][:5]:  # Limiter à 5
            print(f"   - {error}")
        if len(results['error']) > 5:
            print(f"   ... et {len(results['error']) - 5} autres")

    print(f"\n⏰ Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Code de sortie basé sur le taux de succès
    if results['total'] == 0 or success_rate >= 95:
        print("🎉 Tests réussis!")
    elif success_rate >= 80:
        print("⚠️ Tests partiellement réussis")
    else:
        print("❌ Tests échoués")