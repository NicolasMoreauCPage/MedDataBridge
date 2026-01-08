#!/usr/bin/env python3
"""
Script de suppression sécurisée des champs d'adresse dupliqués.
PHASE 5: Suppression des champs dupliqués après validation.
"""

import os
import re
from pathlib import Path

def create_backup_models_structure():
    """Crée une sauvegarde du fichier models_structure.py"""
    source = "app/models_structure.py"
    backup = "app/models_structure.py.backup_address_fields"

    if os.path.exists(source):
        with open(source, 'r', encoding='utf-8') as f:
            content = f.read()

        with open(backup, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Sauvegarde créée: {backup}")
        return True

    return False

def remove_address_fields_from_model(model_content, model_name):
    """Supprime les champs d'adresse d'un modèle spécifique"""

    # Pattern pour identifier le modèle
    model_pattern = rf'(class {model_name}\(SQLModel, table=True\):.*?(?=\nclass|\n#|\n@|\Z))'
    model_match = re.search(model_pattern, model_content, re.DOTALL)

    if not model_match:
        print(f"⚠️ Modèle {model_name} non trouvé")
        return model_content

    model_block = model_match.group(1)

    # Champs d'adresse à supprimer (un par ligne)
    address_fields = [
        r'\s*address_line1: Optional\[str\] = None\n',
        r'\s*address_line2: Optional\[str\] = None\n',
        r'\s*address_line3: Optional\[str\] = None\n',
        r'\s*address_city: Optional\[str\] = None\n',
        r'\s*address_postalcode: Optional\[str\] = None\n',
        r'\s*address_country: Optional\[str\] = "FR"\n',
    ]

    original_block = model_block
    fields_removed = 0

    for field_pattern in address_fields:
        if re.search(field_pattern, model_block):
            model_block = re.sub(field_pattern, '', model_block)
            fields_removed += 1
            print(f"  • Supprimé {field_pattern.strip()} de {model_name}")

    if fields_removed > 0:
        # Remplacer le bloc modèle dans le contenu
        new_content = model_content.replace(original_block, model_block)
        return new_content, fields_removed
    else:
        print(f"  • Aucun champ d'adresse trouvé dans {model_name}")
        return model_content, 0

def remove_duplicate_address_fields():
    """Supprime les champs d'adresse dupliqués de tous les modèles"""

    print("🗑️ SUPPRESSION DES CHAMPS D'ADRESSE DUPLIQUÉS")
    print("=" * 50)

    # Créer une sauvegarde
    if not create_backup_models_structure():
        print("❌ Impossible de créer la sauvegarde")
        return False

    # Lire le fichier
    with open("app/models_structure.py", 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    total_fields_removed = 0

    # Ordre de suppression: du plus bas au plus haut dans la hiérarchie
    models_to_clean = [
        "Lit",           # Hérite de Chambre
        "Chambre",       # Hérite de UniteHebergement
        "UniteHebergement", # Hérite de UniteFonctionnelle
        "UniteFonctionnelle", # Hérite de Service
        "Service",       # Hérite de Pole
        "Pole",          # Hérite d'EntiteGeographique
    ]

    for model_name in models_to_clean:
        print(f"\n📋 Nettoyage du modèle {model_name}:")
        content, fields_removed = remove_address_fields_from_model(content, model_name)
        total_fields_removed += fields_removed

    if total_fields_removed > 0:
        # Écrire le nouveau contenu
        with open("app/models_structure.py", 'w', encoding='utf-8') as f:
            f.write(content)

        print("
🎉 SUPPRESSION TERMINÉE"        print(f"📊 {total_fields_removed} champs d'adresse supprimés")
        print("📁 Sauvegarde disponible: app/models_structure.py.backup_address_fields"
        return True
    else:
        print("\n⚠️ AUCUN CHAMP SUPPRIMÉ")
        print("Vérifier que les modèles contiennent bien les champs d'adresse")
        return False

def validate_removal():
    """Valide que la suppression s'est bien passée"""

    print("\n🔍 VALIDATION DE LA SUPPRESSION")
    print("-" * 30)

    # Vérifier que les propriétés inherited_ existent toujours
    with open("app/models_structure.py", 'r', encoding='utf-8') as f:
        content = f.read()

    inherited_count = len(re.findall(r'def inherited_address_', content))
    print(f"✅ Propriétés inherited_address_*: {inherited_count} trouvées")

    # Vérifier que les champs address_ ont été supprimés (sauf dans EntiteGeographique)
    address_fields_count = len(re.findall(r'\baddress_line1: Optional\[str\]', content))
    if address_fields_count <= 1:  # Seulement dans EntiteGeographique
        print("✅ Champs address_* dupliqués supprimés")
        return True
    else:
        print(f"⚠️ {address_fields_count} champs address_* encore présents")
        return False

def main():
    """Fonction principale"""

    print("⚠️ ATTENTION: Cette opération va supprimer les champs d'adresse dupliqués")
    print("Les propriétés inherited_address_* doivent déjà être en place")
    print("Une sauvegarde sera créée automatiquement")
    print()

    # Demander confirmation
    response = input("Voulez-vous continuer ? (oui/non): ").lower().strip()
    if response not in ['oui', 'yes', 'y', 'o']:
        print("❌ Opération annulée")
        return

    # Supprimer les champs
    success = remove_duplicate_address_fields()

    if success:
        # Valider
        if validate_removal():
            print("\n🎊 SUCCÈS: Champs dupliqués supprimés avec succès!")
            print("\n📋 PROCHAINES ÉTAPES:")
            print("1. Tester que l'application fonctionne")
            print("2. Lancer les tests pour valider")
            print("3. Supprimer les sauvegardes si tout est OK")
        else:
            print("\n❌ ÉCHEC: Problème de validation")
            print("Vérifier les logs ci-dessus")
    else:
        print("\n❌ ÉCHEC: Aucun champ supprimé")

if __name__ == "__main__":
    main()