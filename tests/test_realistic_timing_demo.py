#!/usr/bin/env python3
"""Script de test des configurations temporelles automatiques pour tous les scénarios."""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_scenario_timing_detection():
    """Test la détection automatique de timing pour les premiers scénarios."""
    
    print("=== Test de détection automatique de timing pour scénarios ===\n")
    
    # Récupérer la liste des premiers scénarios
    for scenario_id in range(1, 6):
        try:
            print(f"--- Scénario {scenario_id} ---")
            
            # Suggérer la configuration
            response = requests.post(f"{BASE_URL}/scenarios/{scenario_id}/suggest-realistic-timing")
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"Nom: {data['scenario_name']}")
                print(f"Workflow détecté: {data['analysis']['detected_workflow']}")
                print(f"Description: {data['analysis']['workflow_description']}")
                print(f"Séquence d'événements: {data['analysis']['event_sequence']}")
                
                suggested = data['suggested_config']
                print(f"Configuration suggérée:")
                print(f"  - Ancrage: {suggested['time_anchor_mode']}")
                if suggested.get('time_anchor_days_offset'):
                    print(f"  - Décalage jours: {suggested['time_anchor_days_offset']}")
                print(f"  - Jitter: {suggested['jitter_min_minutes']}-{suggested['jitter_max_minutes']} minutes")
                print(f"  - Événements avec jitter: {suggested['apply_jitter_on_events']}")
                
            elif response.status_code == 404:
                print(f"Scénario {scenario_id} non trouvé")
                break
            else:
                print(f"Erreur {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"Erreur lors du test du scénario {scenario_id}: {e}")
        
        print()
        time.sleep(0.5)  # Éviter de surcharger le serveur


def apply_realistic_timing_to_scenario(scenario_id: int):
    """Applique une configuration temporelle réaliste à un scénario."""
    
    try:
        print(f"Application de configuration réaliste au scénario {scenario_id}...")
        
        response = requests.post(f"{BASE_URL}/scenarios/{scenario_id}/apply-realistic-timing")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Succès: {data['message']}")
            print(f"Workflow: {data['analysis']['detected_workflow']}")
            return True
        else:
            print(f"❌ Erreur {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def test_scenario_execution_with_realistic_timing():
    """Test d'exécution d'un scénario avec timing réaliste."""
    
    scenario_id = 1
    print(f"=== Test d'exécution avec timing réaliste (Scénario {scenario_id}) ===\n")
    
    # D'abord s'assurer qu'il a une configuration réaliste
    if apply_realistic_timing_to_scenario(scenario_id):
        print()
        
        # Essayer d'exécuter en mode dry_run pour voir les timestamps générés
        try:
            # Note: Ceci nécessiterait un endpoint adapté ou d'utiliser l'interface web
            print("Pour tester l'exécution complète, utilisez l'interface web:")
            print(f"{BASE_URL}/scenarios/{scenario_id}")
            print("avec les options 'Update dates' et 'Advanced timeplan' activées")
            
        except Exception as e:
            print(f"Erreur lors de l'exécution: {e}")


if __name__ == "__main__":
    try:
        # Test de détection pour plusieurs scénarios
        test_scenario_timing_detection()
        
        print("\n" + "="*60 + "\n")
        
        # Test d'exécution avec timing réaliste  
        test_scenario_execution_with_realistic_timing()
        
    except KeyboardInterrupt:
        print("\nTest interrompu par l'utilisateur")
    except Exception as e:
        print(f"Erreur générale: {e}")