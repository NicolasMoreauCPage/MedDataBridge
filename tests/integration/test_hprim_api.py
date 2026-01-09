#!/usr/bin/env python3
"""
Test script pour vérifier l'API HPRIM
"""
import requests
import time
import subprocess
import signal
import os
import sys

def test_hprim_api():
    # Lancer le serveur en arrière-plan
    print("Démarrage du serveur...")
    server = subprocess.Popen([
        '.venv/bin/python3', '-m', 'uvicorn', 'app.app:app', '--port', '8003'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge')

    # Attendre que le serveur démarre
    time.sleep(8)

    try:
        print("Test de l'API HPRIM...")
        # Tester l'endpoint de listage des fichiers
        response = requests.get('http://localhost:8003/roundtrip-hprim/test-files', timeout=10)
        print(f'Status list-files: {response.status_code}')

        if response.status_code == 200:
            data = response.json()
            print(f'Fichiers trouvés: {len(data.get("files", []))}')

            # Tester le parsing d'un fichier si disponible
            if data.get('files'):
                filename = data['files'][0]['filename']
                print(f"Test parsing du fichier: {filename}")
                parse_response = requests.get(f'http://localhost:8003/roundtrip-hprim/test-files/{filename}', timeout=10)
                print(f'Status parsing: {parse_response.status_code}')

                if parse_response.status_code == 200:
                    parse_data = parse_response.json()
                    print(f'Parsing réussi: {parse_data.get("parsed", False)}')
                    if parse_data.get('parsed_data'):
                        print(f'Type message: {parse_data["parsed_data"].get("type_message")}')
                else:
                    print(f'Erreur parsing: {parse_response.text}')
        else:
            print(f'Erreur list-files: {response.text}')

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
    test_hprim_api()