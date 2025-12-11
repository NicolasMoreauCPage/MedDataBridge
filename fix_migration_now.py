#!/usr/bin/env python3
"""
Script de correction automatique de la migration IHE PAM
À exécuter en production pour corriger l'erreur 'now is not defined'
"""

import os
import shutil
from datetime import datetime
from pathlib import Path

def fix_migration_file(migration_path: str) -> bool:
    """
    Corrige le fichier de migration en ajoutant la définition de 'now'
    """
    migration_file = Path(migration_path)

    if not migration_file.exists():
        print(f"❌ Fichier introuvable: {migration_file}")
        return False

    # Créer une sauvegarde
    backup_file = migration_file.with_suffix(f"{migration_file.suffix}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(migration_file, backup_file)
    print(f"💾 Sauvegarde créée: {backup_file}")

    # Lire le contenu
    with open(migration_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Vérifier si la correction est déjà appliquée
    if 'now = datetime.utcnow()' in content:
        print("✅ Le fichier est déjà corrigé")
        return True

    # Appliquer la correction
    # Trouver la ligne "bind = op.get_bind()" et ajouter la définition de 'now' après
    lines = content.split('\n')
    corrected = False

    for i, line in enumerate(lines):
        if 'bind = op.get_bind()' in line:
            # Insérer la définition de 'now' après cette ligne
            lines.insert(i + 1, '')
            lines.insert(i + 2, '    # Current timestamp for created_at/updated_at')
            lines.insert(i + 3, '    now = datetime.utcnow()')
            corrected = True
            break

    if not corrected:
        print("❌ Impossible de trouver l'emplacement pour appliquer la correction")
        return False

    # Écrire le contenu corrigé
    corrected_content = '\n'.join(lines)
    with open(migration_file, 'w', encoding='utf-8') as f:
        f.write(corrected_content)

    print("✅ Correction appliquée avec succès")
    return True

def main():
    migration_file = "alembic/versions/bdebea0e6af4_add_ihe_pam_scenarios_data.py"

    print("🔧 Correction automatique de la migration IHE PAM")
    print("=" * 55)

    if fix_migration_file(migration_file):
        print("")
        print("🚀 Vous pouvez maintenant exécuter:")
        print("   alembic upgrade head")
        print("")
        print("📋 Pour vérifier la correction:")
        print(f"   grep 'now = datetime.utcnow()' {migration_file}")
        return 0
    else:
        print("❌ Échec de la correction")
        return 1

if __name__ == "__main__":
    exit(main())