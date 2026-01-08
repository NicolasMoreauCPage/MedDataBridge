#!/usr/bin/env python3
"""
Script de vérification de la structure du projet après réorganisation
Utilise: python scripts/utils/verify_structure.py
"""

import os
import sys
from pathlib import Path

def check_directory_structure():
    """Vérifie que la structure des répertoires est correcte"""
    required_dirs = [
        'data',
        'data/archives',
        'data/pam',
        'data/tmp',
        'deployment',
        'deployment/general',
        'deployment/postgresql',
        'deployment/packages',
        'docs',
        'scripts',
        'scripts/tools',
        'tests'
    ]

    print("🔍 Vérification de la structure des répertoires...")
    all_good = True

    for dir_path in required_dirs:
        if os.path.isdir(dir_path):
            print(f"✅ {dir_path}")
        else:
            print(f"❌ {dir_path} - MANQUANT")
            all_good = False

    return all_good

def check_readme_files():
    """Vérifie que les README.md existent"""
    required_readmes = [
        'data/README.md',
        'deployment/README.md',
        'docs/README.md',
        'scripts/README.md',
        'tests/README.md'
    ]

    print("\n📖 Vérification des fichiers README.md...")
    all_good = True

    for readme in required_readmes:
        if os.path.isfile(readme):
            print(f"✅ {readme}")
        else:
            print(f"❌ {readme} - MANQUANT")
            all_good = False

    return all_good

def check_old_paths():
    """Cherche les références aux anciens chemins"""
    print("\n🔍 Recherche de références aux anciens chemins...")

    old_paths = ['Deploiement', 'Doc', 'program_docs', 'isolated_tests']
    found_issues = []

    # Fichiers à exclure de la vérification (documentation sur la migration)
    excluded_files = [
        'docs/guides/code_review_guide.md',
        'docs/README.md',
        'scripts/README.md'
    ]

    # Chercher dans les fichiers .md, .py, .yml
    for ext in ['*.md', '*.py', '*.yml', '*.yaml']:
        for pattern in Path('.').rglob(ext):
            if '.git' in str(pattern) or '__pycache__' in str(pattern) or '.venv' in str(pattern):
                continue

            # Exclure les fichiers de documentation sur la migration
            if str(pattern) in excluded_files:
                continue

            try:
                with open(pattern, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    for old_path in old_paths:
                        if f'/{old_path}/' in content or f'{old_path}/' in content[:50]:  # Éviter les faux positifs
                            found_issues.append(f"{pattern}: référence à {old_path}")
            except:
                pass

    if found_issues:
        print("⚠️  Références aux anciens chemins trouvées:")
        for issue in found_issues[:10]:  # Limiter l'affichage
            print(f"   {issue}")
        if len(found_issues) > 10:
            print(f"   ... et {len(found_issues) - 10} autres")
        return False
    else:
        print("✅ Aucune référence aux anciens chemins trouvée")
        return True

def check_imports():
    """Vérifie que les imports principaux fonctionnent"""
    print("\n🐍 Vérification des imports Python...")

    try:
        import app
        print("✅ Import app: OK")
    except ImportError as e:
        print(f"❌ Import app: ÉCHEC - {e}")
        return False

    try:
        # Tester l'import d'un module de script
        import sys
        import importlib
        sys.path.append('scripts/import')
        importlib.import_module('import_hl7_scenarios')
        print("✅ Import script: OK")
    except ImportError as e:
        print(f"❌ Import script: ÉCHEC - {e}")
        return False

    return True

def main():
    """Fonction principale"""
    print("🚀 Vérification de la structure du projet MedData Bridge\n")

    results = []
    results.append(("Structure des répertoires", check_directory_structure()))
    results.append(("Fichiers README", check_readme_files()))
    results.append(("Anciens chemins", check_old_paths()))
    results.append(("Imports Python", check_imports()))

    print("\n" + "="*50)
    print("📊 RÉSULTATS DE LA VÉRIFICATION")

    all_good = True
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{check_name}: {status}")
        if not result:
            all_good = False

    print("\n" + "="*50)
    if all_good:
        print("🎉 Toutes les vérifications sont passées !")
        print("La structure du projet est correcte.")
        return 0
    else:
        print("⚠️  Certaines vérifications ont échoué.")
        print("Vérifiez les détails ci-dessus et corrigez les problèmes.")
        return 1

if __name__ == "__main__":
    sys.exit(main())