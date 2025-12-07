#!/usr/bin/env python3
"""Script pour appliquer automatiquement des configurations temporelles réalistes à tous les scénarios."""

import requests
import json
import sys
import time
from typing import List, Dict, Any

BASE_URL = "http://localhost:8000"

def get_scenario_list() -> List[Dict[str, Any]]:
    """Récupère la liste des scénarios depuis la base de données."""
    try:
        # Comme il n'y a pas d'endpoint de liste, on va essayer les premiers IDs
        scenarios = []
        for scenario_id in range(1, 21):  # Test jusqu'à ID 20
            try:
                response = requests.post(f"{BASE_URL}/scenarios/{scenario_id}/suggest-realistic-timing")
                if response.status_code == 200:
                    data = response.json()
                    scenarios.append({
                        "id": scenario_id,
                        "name": data["scenario_name"],
                        "current_config": data["current_config"],
                        "suggested_config": data["suggested_config"],
                        "analysis": data["analysis"]
                    })
                elif response.status_code == 404:
                    # Scénario n'existe pas, on continue
                    continue
                else:
                    print(f"⚠️  Erreur {response.status_code} pour le scénario {scenario_id}")
                    
            except Exception as e:
                print(f"⚠️  Erreur pour le scénario {scenario_id}: {e}")
                continue
                
            time.sleep(0.1)  # Éviter de surcharger le serveur
            
        return scenarios
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des scénarios: {e}")
        return []


def apply_realistic_timing_bulk(scenarios: List[Dict[str, Any]], dry_run: bool = True) -> None:
    """Applique des configurations temporelles réalistes à une liste de scénarios.
    
    Args:
        scenarios: Liste des scénarios à traiter
        dry_run: Si True, affiche seulement ce qui serait fait
    """
    
    print(f"\n{'=' * 80}")
    print(f"🕐 {'SIMULATION' if dry_run else 'APPLICATION'} de configurations temporelles réalistes")
    print(f"{'=' * 80}")
    
    scenarios_to_update = []
    
    # Analyser les scénarios
    for scenario in scenarios:
        scenario_id = scenario["id"]
        name = scenario["name"]
        current = scenario["current_config"]
        suggested = scenario["suggested_config"]
        analysis = scenario["analysis"]
        
        # Vérifier si une configuration est nécessaire
        needs_update = (
            current.get("time_anchor_mode") is None or
            current.get("jitter_min_minutes") is None or
            current.get("jitter_max_minutes") is None
        )
        
        if needs_update:
            scenarios_to_update.append(scenario)
            status = "🔄 À configurer"
        else:
            status = "✅ Déjà configuré"
            
        print(f"\n--- Scénario {scenario_id}: {name} ---")
        print(f"Status: {status}")
        
        if analysis.get("event_sequence"):
            print(f"Workflow détecté: {analysis.get('detected_workflow', 'N/A')}")
            print(f"Séquence: {' → '.join(analysis['event_sequence'])}")
        else:
            print(f"Workflow: {analysis.get('detected_workflow', 'N/A')} (pas d'événements extraits)")
            
        if needs_update:
            print(f"Configuration suggérée:")
            print(f"  • Ancrage: {suggested.get('time_anchor_mode')}")
            if suggested.get('time_anchor_days_offset'):
                print(f"  • Décalage: {suggested['time_anchor_days_offset']} jours")
            print(f"  • Jitter: {suggested.get('jitter_min_minutes')}-{suggested.get('jitter_max_minutes')} minutes")
            print(f"  • Événements: {suggested.get('apply_jitter_on_events')}")
    
    print(f"\n{'=' * 80}")
    print(f"📊 RÉSUMÉ:")
    print(f"  • Total de scénarios analysés: {len(scenarios)}")
    print(f"  • Nécessitent une configuration: {len(scenarios_to_update)}")
    print(f"  • Déjà configurés: {len(scenarios) - len(scenarios_to_update)}")
    
    if not scenarios_to_update:
        print(f"\n✅ Tous les scénarios sont déjà configurés avec des timings réalistes !")
        return
        
    if dry_run:
        print(f"\n🔍 MODE SIMULATION - Aucun changement appliqué")
        print(f"Pour appliquer réellement les configurations, relancer avec --apply")
        return
    
    # Demander confirmation
    print(f"\n⚠️  ATTENTION: Cette action va modifier {len(scenarios_to_update)} scénarios")
    response = input("Continuer ? (oui/non): ").lower().strip()
    
    if response not in ["oui", "o", "yes", "y"]:
        print("❌ Annulé par l'utilisateur")
        return
    
    # Appliquer les configurations
    success_count = 0
    error_count = 0
    
    print(f"\n🚀 Application des configurations...")
    
    for scenario in scenarios_to_update:
        scenario_id = scenario["id"]
        name = scenario["name"]
        
        try:
            print(f"  • Scénario {scenario_id}: {name}... ", end="")
            
            response = requests.post(f"{BASE_URL}/scenarios/{scenario_id}/apply-realistic-timing")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ OK ({result['analysis']['detected_workflow']})")
                success_count += 1
            else:
                print(f"❌ Erreur {response.status_code}")
                error_count += 1
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            error_count += 1
            
        time.sleep(0.2)  # Éviter de surcharger le serveur
    
    print(f"\n📈 RÉSULTATS FINAUX:")
    print(f"  • ✅ Succès: {success_count}")
    print(f"  • ❌ Échecs: {error_count}")
    
    if success_count > 0:
        print(f"\n🎉 {success_count} scénario(s) configuré(s) avec des timings hospitaliers réalistes !")


def main():
    """Point d'entrée principal du script."""
    
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] in ["--apply", "-a"]:
        dry_run = False
    
    print("🏥 Configuration automatique de timings réalistes pour scénarios hospitaliers")
    print("=" * 80)
    
    print("🔍 Récupération de la liste des scénarios...")
    scenarios = get_scenario_list()
    
    if not scenarios:
        print("❌ Aucun scénario trouvé ou erreur de récupération")
        sys.exit(1)
    
    print(f"✅ {len(scenarios)} scénario(s) trouvé(s)")
    
    apply_realistic_timing_bulk(scenarios, dry_run)
    
    print(f"\n{'🔍 SIMULATION TERMINÉE' if dry_run else '🎯 APPLICATION TERMINÉE'}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Interruption par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Erreur critique: {e}")
        sys.exit(1)