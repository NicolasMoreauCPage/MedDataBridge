#!/usr/bin/env python3
"""
Script de récupération pour base de données SQLite corrompue
Utilisation en production pour restaurer la base de données
Version améliorée avec gestion forcée des processus et fichiers verrouillés
"""

import os
import shutil
import sys
import time
from pathlib import Path

def force_remove_file(file_path: Path, max_attempts: int = 5):
    """
    Force la suppression d'un fichier, même s'il est verrouillé
    """
    for attempt in range(max_attempts):
        try:
            if file_path.exists():
                # Essayer de changer les permissions
                os.chmod(file_path, 0o666)
                file_path.unlink()
                print(f"✅ Fichier supprimé: {file_path}")
                return True
            else:
                print(f"ℹ️  Fichier déjà absent: {file_path}")
                return True
        except Exception as e:
            print(f"⚠️  Tentative {attempt + 1}/{max_attempts} échouée: {e}")
            if attempt < max_attempts - 1:
                time.sleep(1)
    return False

def kill_sqlite_processes(db_path: str):
    """
    Tente de tuer les processus qui pourraient verrouiller la base SQLite
    """
    try:
        import psutil
        db_name = Path(db_path).name

        killed = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any(db_name in str(arg) for arg in proc.info['cmdline']):
                    proc.kill()
                    killed += 1
                    print(f"🛑 Processus tué: {proc.info['name']} (PID: {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if killed > 0:
            print(f"✅ {killed} processus SQLite tués")
            time.sleep(2)  # Attendre que les processus se terminent

    except ImportError:
        print("ℹ️  psutil non disponible, vérifiez manuellement les processus")
    except Exception as e:
        print(f"⚠️  Erreur lors de la recherche de processus: {e}")

def recreate_database_force(db_path: str):
    """
    Recrée complètement la base de données SQLite
    """
    db_path = Path(db_path)

    print(f"🔧 Recréation forcée de la base de données: {db_path}")

    # Tuer les processus potentiels
    kill_sqlite_processes(str(db_path))

    # Supprimer le fichier de manière forcée
    if not force_remove_file(db_path):
        print("❌ Impossible de supprimer l'ancienne base de données")
        return False

    # Supprimer aussi les fichiers associés SQLite
    for ext in ['-shm', '-wal']:
        wal_file = db_path.with_suffix(f'.db{ext}')
        force_remove_file(wal_file)

    # Créer une nouvelle base vide
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("VACUUM;")  # Optimiser la nouvelle base
        conn.close()
        print(f"✅ Nouvelle base de données créée: {db_path}")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création: {e}")
        return False

def check_database_integrity(db_path: str) -> bool:
    """
    Vérifie l'intégrité d'une base de données SQLite
    """
    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()

        # Test de base
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        # Vérification d'intégrité
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()

        conn.close()

        if result and result[0] == "ok":
            print(f"✅ Base de données intacte ({len(tables)} tables)")
            return True
        else:
            print(f"❌ Base de données corrompue: {result}")
            return False

    except Exception as e:
        print(f"❌ Erreur d'accès: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python recover_database.py <database_path>")
        print("Exemple: python recover_database.py /opt/meddatabridge/data/meddatabridge.db")
        sys.exit(1)

    db_path = sys.argv[1]
    db_file = Path(db_path)

    print("🔧 Outil de récupération de base de données SQLite")
    print("=" * 60)

    # Vérifier l'état actuel
    if db_file.exists():
        print(f"📁 Base de données trouvée: {db_file} ({db_file.stat().st_size} bytes)")

        if check_database_integrity(db_path):
            print("✅ La base de données est intacte, pas de récupération nécessaire")
            return 0
        else:
            print("❌ Base de données corrompue détectée")
    else:
        print(f"ℹ️  Aucune base de données trouvée à: {db_file}")

    # Demander confirmation pour la recréation
    response = input("Voulez-vous recréer complètement la base de données ? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("Opération annulée")
        return 1

    # Recréer la base
    if recreate_database_force(db_path):
        print("✅ Base de données recréée avec succès")
        print("🚀 Vous pouvez maintenant lancer: alembic upgrade head")
        return 0
    else:
        print("❌ Échec de la recréation")
        return 1

if __name__ == "__main__":
    sys.exit(main())