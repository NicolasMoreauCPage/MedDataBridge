#!/usr/bin/env python3
"""
Analyse spécifique des champs d'adresse dans les modèles de structure
pour identifier les duplications inutiles.
"""

import re
from pathlib import Path

def analyze_address_fields():
    """Analyse l'utilisation des champs d'adresse dans models_structure.py"""

    models_file = Path("app/models_structure.py")

    if not models_file.exists():
        print("Fichier models_structure.py non trouvé")
        return

    with open(models_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Identifier tous les modèles qui ont des champs d'adresse
    address_fields = ['address_line1', 'address_line2', 'address_line3', 'address_city', 'address_postalcode', 'address_country']

    models_with_address = []

    # Trouver tous les modèles (classes)
    model_pattern = r'class (\w+)\(SQLModel, table=True\):'
    models = re.findall(model_pattern, content)

    print("=== MODÈLES AVEC CHAMPS D'ADRESSE ===\n")

    for model in models:
        model_section = re.search(rf'class {model}\(SQLModel, table=True\):(.*?)(?=\nclass|\n@|\n#|\Z)', content, re.DOTALL)
        if model_section:
            model_content = model_section.group(1)

            address_fields_in_model = []
            for field in address_fields:
                if field in model_content:
                    address_fields_in_model.append(field)

            if address_fields_in_model:
                models_with_address.append((model, address_fields_in_model))
                print(f"🏥 {model}: {len(address_fields_in_model)} champs d'adresse")
                for field in address_fields_in_model:
                    print(f"   - {field}")
                print()

    print(f"📊 TOTAL: {len(models_with_address)} modèles ont des champs d'adresse dupliqués")
    print("\n💡 RECOMMANDATION: Seuls EntiteJuridique et EntiteGeographique devraient avoir des adresses.")
    print("   Les autres niveaux devraient hériter via des propriétés ou relations.")

if __name__ == "__main__":
    analyze_address_fields()