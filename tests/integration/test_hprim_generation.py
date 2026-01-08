#!/usr/bin/env python3
"""
Test de la génération XML HPRIM
"""
import requests
import time
import subprocess
import signal
import os
import sys

def test_hprim_generation():
    # Lancer le serveur en arrière-plan
    print("Démarrage du serveur...")
    server = subprocess.Popen([
        '.venv/bin/python3', '-m', 'uvicorn', 'app.app:app', '--port', '8004'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge')

    # Attendre que le serveur démarre
    time.sleep(8)

    try:
        print("Test de génération CCAM...")
        # Test de génération CCAM
        cotation_ccam = {
            "type": "CCAM",
            "code": "ZZQK900",
            "libelle": "Acte CCAM de test",
            "coefficient": 1,
            "montant": 100.0
        }

        response = requests.post(
            'http://localhost:8004/roundtrip-hprim/generate',
            json=cotation_ccam,
            timeout=10
        )
        print(f"Status CCAM: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Fichier généré: {result['filename']}")
            # Vérifier que le fichier existe
            filepath = result.get('filepath', '')
            if os.path.exists(filepath):
                print(f"✓ Fichier créé: {filepath}")
                # Afficher le début du fichier
                with open(filepath, 'r', encoding='iso-8859-1') as f:
                    content = f.read()[:500]
                    print(f"Contenu (début):\n{content}...")
            else:
                print(f"✗ Fichier non trouvé: {filepath}")
        else:
            print(f"Erreur: {response.text}")

        print("\nTest de génération NGAP...")
        # Test de génération NGAP
        cotation_ngap = {
            "type": "NGAP",
            "code": "AMK",
            "libelle": "Acte NGAP de test",
            "coefficient": 2,  # Changé en int
            "quantite": 1,
            "montant": 50.0
        }

        response = requests.post(
            'http://localhost:8004/roundtrip-hprim/generate',
            json=cotation_ngap,
            timeout=10
        )
        print(f"Status NGAP: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Fichier généré: {result['filename']}")
        else:
            print(f"Erreur: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f'Erreur de connexion: {e}')
    except Exception as e:
        print(f'Erreur générale: {e}')
    finally:
        # Arrêter le serveur
        print("Arrêt du serveur...")
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()

if __name__ == '__main__':
    test_hprim_generation()