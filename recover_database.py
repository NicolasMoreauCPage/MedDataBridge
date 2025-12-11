#!/usr/bin/env python3
"""
Script de récupération pour base de données SQLite corrompue
Utilisation en production pour restaurer la base de données
"""

import os
import shutil
import sys
from pathlib import Path

def recover_sqlite_database(db_path: str):
    """
    Tente de récupérer une base de données SQLite corrompue
    """
    db_path = Path(db_path)

    if not db_path.exists():
        print(f"❌ Base de données introuvable: {db_path}")
        return False

    print(f"🔍 Analyse de la base de données: {db_path}")

    # Vérifier si la base est corrompue
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        conn.close()

        if result and result[0] == "ok":
            print("✅ Base de données intacte")
            return True
        else:
            print(f"❌ Base de données corrompue: {result}")
    except Exception as e:
        print(f"❌ Erreur d'accès à la base: {e}")

    # Essayer de récupérer avec sqlite3
    backup_path = db_path.with_suffix('.db.backup')
    print(f"💾 Création d'une sauvegarde: {backup_path}")
    shutil.copy2(db_path, backup_path)

    print("🔧 Tentative de récupération avec sqlite3...")
    try:
        # Tenter une récupération basique
        recovered_path = db_path.with_suffix('.db.recovered')
        os.system(f'sqlite3 "{db_path}" ".recover" > "{recovered_path}"')

        if recovered_path.exists() and recovered_path.stat().st_size > 0:
            print(f"✅ Données récupérées dans: {recovered_path}")
            return True
        else:
            print("❌ Récupération échouée")
    except Exception as e:
        print(f"❌ Erreur lors de la récupération: {e}")

    print("💡 Solutions recommandées:")
    print("1. Restaurer depuis une sauvegarde connue")
    print("2. Recréer la base de données vide")
    print("3. Réappliquer les migrations depuis le début")

    return False

def recreate_database(db_path: str):
    """
    Recrée une base de données vide et applique les migrations
    """
    db_path = Path(db_path)

    # Sauvegarder l'ancienne base
    if db_path.exists():
        backup_path = db_path.with_suffix('.db.corrupted')
        print(f"💾 Sauvegarde de la base corrompue: {backup_path}")
        shutil.move(db_path, backup_path)

    print(f"🆕 Création d'une nouvelle base de données: {db_path}")

    # La nouvelle base sera créée lors de la première migration
    print("✅ Base de données prête pour les migrations")
    print("🚀 Lancez: alembic upgrade head")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python recover_database.py <database_path>")
        print("Exemple: python recover_database.py /opt/meddata-bridge/data/meddatabridge.db")
        sys.exit(1)

    db_path = sys.argv[1]

    print("🔧 Outil de récupération de base de données SQLite")
    print("=" * 50)

    if recover_sqlite_database(db_path):
        print("✅ Récupération réussie")
    else:
        print("❌ Récupération échouée")
        print()
        response = input("Voulez-vous recréer la base de données vide ? (y/N): ")
        if response.lower() in ['y', 'yes']:
            recreate_database(db_path)
        else:
            print("Opération annulée")