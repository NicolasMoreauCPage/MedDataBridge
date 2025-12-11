#!/usr/bin/env python3
"""
Crée une archive de déploiement complète incluant les sources + migration IHE PAM.
"""
import argparse
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent  # Le répertoire où se trouve ce script (MedDataBridge-main)

def should_exclude_deployment(path, root):
    """Version modifiée pour le déploiement incluant les migrations."""
    rel = os.path.relpath(path, root)
    parts = rel.split(os.sep)

    # Exclusions critiques pour éviter les archives géantes
    critical_excludes = [
        '.git', '.venv', 'venv', '__pycache__', 'node_modules', 'dist', 'build',
        'packages', 'packages-prod', 'packages-server', 'pip_pkgs', 'reports',
        'Deploiement', 'Deploiement-PostgreSQL', '.pytest_cache', '.tmp',
        'archives', 'test_archive', 'pam_archive', 'pam_archive_dst', 'pam_export',
        'pam_export_fichier_test', 'pam_export_new', 'isolated_tests',
        'one_shot_legacy', 'program_docs', '.coverage', 'coverage.xml',
        'TESTS_COVERAGE_REPORT.html'
    ]

    for ex in critical_excludes:
        if parts and parts[0] == ex:
            return True

    # Exclure les bundles de dépendances dans Deploiement
    if rel.startswith('Deploiement' + os.sep) and 'dependencies' in rel:
        return True

    # Exclure les fichiers temporaires
    if os.path.basename(path).startswith('.tmp'):
        return True

    # Exclure les bases de données
    if any(rel.endswith(ext) for ext in ['.db', '.sqlite', '.sqlite3']):
        return True

    # EXCLUSION CRITIQUE: Tous les fichiers ZIP existants
    if path.endswith('.zip'):
        return True

    # EXCLUSION CRITIQUE: Tous les fichiers d'archive
    archive_extensions = ['.tar.gz', '.tgz', '.7z', '.rar', '.bz2', '.xz']
    if any(path.endswith(ext) for ext in archive_extensions):
        return True

    # EXCLUSION CRITIQUE: Fichiers de packages Python volumineux
    if path.endswith('.whl') or path.endswith('.egg'):
        return True

    # Patterns d'exclusion
    exclude_patterns = ['.pyc', '.pyo', '.log', '.DS_Store', 'Thumbs.db', 'medbridge.db', 'meddata.log']
    for pat in exclude_patterns:
        if path.endswith(pat):
            return True

    return False

def collect_deployment_files(root):
    """Collecte les fichiers pour le déploiement."""
    files = []

    # Parcourir tous les fichiers
    for dirpath, dirnames, filenames in os.walk(root):
        # Filtrer les répertoires
        dirnames[:] = [d for d in dirnames if not should_exclude_deployment(os.path.join(dirpath, d), root)]

        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if should_exclude_deployment(full, root):
                continue
            files.append(full)

    # Ajouter spécifiquement les fichiers de migration IHE PAM
    migration_files = [
        'alembic/versions/bdebea0e6af4_add_ihe_pam_scenarios_data.py',
        'ihe_pam_scenarios_direct_export_20251211_145215.json',
        'migration_ihe_pam_production.py',
        'test_migration_ihe_pam.py',
        'DEPLOIEMENT_PRODUCTION_README.md'
    ]

    for mf in migration_files:
        mf_path = root / mf
        if mf_path.exists():
            files.append(str(mf_path))
            print(f"✅ Inclus: {mf}")
        else:
            print(f"⚠️  Non trouvé: {mf} (chemin: {mf_path})")

    return files

def create_deployment_zip(output_path, root):
    """Crée l'archive de déploiement."""
    print("📦 Collecte des fichiers pour le déploiement...")

    files = collect_deployment_files(root)

    print(f"📊 {len(files)} fichiers à archiver")

    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arcname = os.path.relpath(f, root)
            zf.write(f, arcname)

    size = os.path.getsize(output_path)
    print(f"✅ Archive créée: {output_path} ({size:,} bytes)")

    return output_path

def main():
    parser = argparse.ArgumentParser(description="Crée une archive de déploiement MedDataBridge")
    parser.add_argument('--output', '-o', help='Chemin de sortie de l\'archive',
                       default=f'meddatabridge-deployment-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}.zip')
    args = parser.parse_args()

    output_path = args.output
    if not output_path.endswith('.zip'):
        output_path += '.zip'

    print(f"🚀 Création de l'archive de déploiement: {output_path}")

    try:
        create_deployment_zip(output_path, ROOT)
        print("\\n✅ Déploiement prêt !")
        print(f"📦 Archive: {output_path}")
        print("\\n📋 Contenu de l'archive:")
        print("  - Sources de l'application")
        print("  - Migration Alembic IHE PAM")
        print("  - Données JSON des scénarios")
        print("  - Scripts de déploiement")
        print("\\n🚀 Pour déployer:")
        print("  1. Copiez l'archive sur votre serveur")
        print("  2. Extrayez: unzip meddatabridge-deployment-*.zip")
        print("  3. Activez l'environnement virtuel de production (si applicable)")
        print("  4. Appliquez la migration: alembic upgrade head")
        print("  5. Vérifiez: alembic current  # Doit afficher bdebea0e6af4")

    except Exception as e:
        print(f"❌ Erreur: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())