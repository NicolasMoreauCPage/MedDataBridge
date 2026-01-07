#!/usr/bin/env python3
"""
Script de déploiement rapide pour MedDataBridge.
Crée une archive ZIP avec les fichiers essentiels de l'application.
"""
import zipfile
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def create_deployment_package():
    """Crée un package de déploiement avec les fichiers essentiels."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_name = f"meddatabridge-deployment-{timestamp}.zip"
    
    # Fichiers et dossiers à inclure (PRODUCTION UNIQUEMENT)
    include_patterns = [
        "app/**/*.py",
        "app/**/*.html",
        "app/**/*.css",
        "app/**/*.js",
        "alembic/**/*.py",
        "alembic/**/*.mako",
        "config/**/*.py",
        "docs/**/*.md",
        "docs/**/*.html",
        "alembic.ini",
        "requirements.txt",
        "requirements-production.txt",
        "README.md",
    ]
    
    # Dossiers et fichiers à exclure
    exclude_patterns = [
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
        ".venv",
        "venv",
        ".git",
        "*.db",
        "*.db-shm",
        "*.db-wal",
        "tests",
        "temp_extract",
        "Doc",
        "archives",
        "deployment",
        "Deploiement",
        "isolated_tests",
        "one_shot_legacy",
        "program_docs",
        "scripts_manual",
        "tmp",
        ".backup",
    ]
    
    print(f"Création de {zip_name}...")
    
    # Collecter tous les fichiers uniques d'abord
    files_to_add = set()
    
    # Ajouter les fichiers des dossiers app/, alembic/, config/ et docs/
    for base_dir in ["app", "alembic", "config", "docs"]:
        if os.path.exists(base_dir):
            for root, dirs, files in os.walk(base_dir):
                # Exclure les dossiers indésirables
                dirs[:] = [d for d in dirs if d not in exclude_patterns]
                
                for file in files:
                    # Vérifier les exclusions
                    if any(excl in file for excl in exclude_patterns if not excl.startswith(".")):
                        continue
                    
                    file_path = os.path.join(root, file)
                    files_to_add.add(file_path)
    
    # Ajouter les fichiers racine
    for file in ["alembic.ini", "requirements.txt", "requirements-production.txt", "README.md"]:
        if os.path.exists(file):
            files_to_add.add(file)
    
    # Créer l'archive avec les fichiers uniques
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in sorted(files_to_add):
            zipf.write(file_path, file_path)
            print(f"  Ajouté: {file_path}")
    
    file_size = os.path.getsize(zip_name) / (1024 * 1024)
    print(f"\n[OK] Package cree: {zip_name} ({file_size:.2f} MB)")
    return zip_name

def deploy_to_server(package_name):
    """Déploie le package sur le serveur de qualif."""
    ssh_key = r"C:\Users\nmoreau\.ssh\id_rsa.ppk"
    server = "cpage@qualifinterop.cpage.cloud"
    
    print(f"\n[DEPLOIEMENT] Upload du package sur le serveur...")
    
    # 1. Upload du package
    cmd_upload = f'pscp -i "{ssh_key}" "{package_name}" {server}:/tmp/'
    result = subprocess.run(cmd_upload, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERREUR] Upload echoue: {result.stderr}")
        return False
    print(f"[OK] Package uploade")
    
    # 2. Extraction sur le serveur
    print(f"[DEPLOIEMENT] Extraction...")
    cmd_extract = f'plink -i "{ssh_key}" -batch {server} "cd /tmp && unzip -qo {package_name} -d meddatabridge-deployment"'
    result = subprocess.run(cmd_extract, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERREUR] Extraction echouee: {result.stderr}")
        return False
    print(f"[OK] Package extrait")
    
    # 3. Synchronisation et redémarrage
    print(f"[DEPLOIEMENT] Synchronisation et redemarrage du service...")
    cmd_sync = f'plink -i "{ssh_key}" -batch {server} "sudo rsync -a --delete /tmp/meddatabridge-deployment/ /opt/meddata-bridge/ && sudo systemctl restart meddata-bridge && echo OK"'
    result = subprocess.run(cmd_sync, shell=True, capture_output=True, text=True)
    if result.returncode != 0 or "OK" not in result.stdout:
        print(f"[ERREUR] Synchronisation echouee: {result.stderr}")
        return False
    print(f"[OK] Service redémarre")
    
    # 4. Vérification du statut
    print(f"[DEPLOIEMENT] Verification du statut...")
    cmd_status = f'plink -i "{ssh_key}" -batch {server} "sudo systemctl is-active meddata-bridge"'
    result = subprocess.run(cmd_status, shell=True, capture_output=True, text=True)
    if "active" in result.stdout:
        print(f"[OK] Service actif")
        return True
    else:
        print(f"[AVERTISSEMENT] Service status: {result.stdout.strip()}")
        return False

if __name__ == "__main__":
    auto_deploy = "--deploy" in sys.argv or "-d" in sys.argv
    
    package_name = create_deployment_package()
    
    if auto_deploy:
        print("\n" + "="*60)
        print("DEPLOIEMENT AUTOMATIQUE")
        print("="*60)
        if deploy_to_server(package_name):
            print("\n[SUCCES] Deploiement termine avec succes!")
        else:
            print("\n[ECHEC] Le deploiement a echoue")
            sys.exit(1)
    else:
        print(f"\nPour deployer automatiquement:")
        print(f"  python deploy_now.py --deploy")
        print(f"\nOu manuellement:")
        print(f"  1. pscp -i \"C:\\Users\\nmoreau\\.ssh\\id_rsa.ppk\" \"{package_name}\" cpage@qualifinterop.cpage.cloud:/tmp/")
        print(f"  2. plink -i \"C:\\Users\\nmoreau\\.ssh\\id_rsa.ppk\" -batch cpage@qualifinterop.cpage.cloud \"cd /tmp && unzip -qo {package_name} -d meddatabridge-deployment\"")
        print(f"  3. plink -i \"C:\\Users\\nmoreau\\.ssh\\id_rsa.ppk\" -batch cpage@qualifinterop.cpage.cloud \"sudo rsync -a --delete /tmp/meddatabridge-deployment/ /opt/meddata-bridge/ && sudo systemctl restart meddata-bridge\"")
