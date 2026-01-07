#!/usr/bin/env python3
"""
Script de déploiement rapide pour MedDataBridge.
Crée une archive ZIP avec les fichiers essentiels de l'application.
"""
import zipfile
import os
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

if __name__ == "__main__":
    package_name = create_deployment_package()
    print(f"\nPour déployer sur le serveur:")
    print(f"  1. pscp \"{package_name}\" cpage@qualifinterop.cpage.cloud:/tmp/")
    print(f"  2. plink cpage@qualifinterop.cpage.cloud -pw cpage \"cd /tmp && unzip -o {package_name} -d meddatabridge-deployment\"")
    print(f"  3. plink cpage@qualifinterop.cpage.cloud -pw cpage \"sudo rsync -av --delete /tmp/meddatabridge-deployment/ /opt/meddatabridge/ && sudo systemctl restart meddata-bridge\"")
