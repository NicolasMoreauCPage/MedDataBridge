#!/usr/bin/env python3
"""
Analyse des champs d'adresse utilisés dans les templates
"""

import os
import re
from pathlib import Path

def analyze_address_in_templates():
    """Analyse l'utilisation des champs d'adresse dans les templates"""

    address_fields = [
        'address_line1', 'address_line2', 'address_line3', 'address_line',
        'address_city', 'address_postalcode', 'postal_code', 'city', 'country'
    ]

    template_dir = Path("app/templates")
    usage = {}

    if not template_dir.exists():
        print("Dossier templates non trouvé")
        return

    for template_file in template_dir.rglob("*.html"):
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()

            for field in address_fields:
                if field in content:
                    if field not in usage:
                        usage[field] = []
                    usage[field].append(str(template_file.relative_to(template_dir)))

        except Exception as e:
            print(f"Erreur lors de la lecture de {template_file}: {e}")

    print("=== CHAMPS D'ADRESSE UTILISÉS DANS LES TEMPLATES ===\n")

    for field in address_fields:
        if field in usage:
            print(f"✅ {field}: utilisé dans {len(usage[field])} template(s)")
            for template in usage[field][:3]:  # Montrer max 3 templates
                print(f"   - {template}")
            if len(usage[field]) > 3:
                print(f"   ... et {len(usage[field]) - 3} autres")
        else:
            print(f"❌ {field}: non utilisé dans les templates")
        print()

    print("📊 CONCLUSION:")
    critical_fields = [f for f in address_fields if f in usage]
    unused_fields = [f for f in address_fields if f not in usage]

    print(f"   • {len(critical_fields)} champs critiques (utilisés dans templates)")
    print(f"   • {len(unused_fields)} champs inutiles (pas dans templates)")

if __name__ == "__main__":
    analyze_address_in_templates()