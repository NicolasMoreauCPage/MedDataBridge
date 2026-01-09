#!/usr/bin/env python3
"""
Audit script pour analyser l'utilisation des champs ajoutés récemment
dans les modèles de structure.
"""

import os
import re
from pathlib import Path

# Liste des champs ajoutés récemment
FIELDS_TO_AUDIT = [
    'address_country', 'address_line', 'postal_code', 'city', 'country',
    'responsible_id', 'responsible_name', 'responsible_firstname',
    'responsible_rpps', 'responsible_adeli', 'responsible_specialty',
    'opening_date', 'activation_date', 'closing_date', 'deactivation_date',
    'physical_type', 'status', 'mode',
    'category_code', 'category_name', 'category_sae', 'city_insee_code', 'is_active'
]

def search_field_usage(field_name):
    """Recherche l'utilisation d'un champ dans tout le projet"""
    results = {}

    # Recherche dans les fichiers Python
    python_files = []
    for root, dirs, files in os.walk('.'):
        if 'node_modules' in root or '__pycache__' in root or '.git' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))

    # Recherche dans les templates
    template_files = []
    for root, dirs, files in os.walk('app/templates'):
        for file in files:
            if file.endswith('.html'):
                template_files.append(os.path.join(root, file))

    # Recherche dans les fichiers Python
    python_usage = []
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if field_name in content:
                    # Compter les occurrences
                    count = content.count(field_name)
                    python_usage.append(f"{file_path}: {count} occurrence(s)")
        except Exception as e:
            pass

    # Recherche dans les templates
    template_usage = []
    for file_path in template_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if field_name in content:
                    # Compter les occurrences
                    count = content.count(field_name)
                    template_usage.append(f"{file_path}: {count} occurrence(s)")
        except Exception as e:
            pass

    results['python'] = python_usage
    results['templates'] = template_usage
    results['total_occurrences'] = len(python_usage) + len(template_usage)

    return results

def main():
    print("=== AUDIT DES CHAMPS AJOUTÉS ===\n")

    for field in FIELDS_TO_AUDIT:
        print(f"🔍 Analyse du champ: {field}")
        usage = search_field_usage(field)

        if usage['total_occurrences'] == 0:
            print(f"   ❌ NON UTILISÉ")
        else:
            print(f"   ✅ UTILISÉ ({usage['total_occurrences']} fichier(s))")

            if usage['python']:
                print("   📄 Fichiers Python:")
                for file in usage['python'][:3]:  # Limiter à 3 résultats
                    print(f"      {file}")
                if len(usage['python']) > 3:
                    print(f"      ... et {len(usage['python']) - 3} autres")

            if usage['templates']:
                print("   🎨 Templates:")
                for file in usage['templates'][:3]:  # Limiter à 3 résultats
                    print(f"      {file}")
                if len(usage['templates']) > 3:
                    print(f"      ... et {len(usage['templates']) - 3} autres")

        print()

if __name__ == "__main__":
    main()