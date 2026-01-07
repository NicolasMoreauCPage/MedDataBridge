#!/usr/bin/env python3
"""Vérifie les endpoints FILE configurés - version standalone"""

import sqlite3
import os
from pathlib import Path

def check_file_endpoints():
    """Liste tous les endpoints FILE"""
    
    # Essayer plusieurs chemins de DB
    db_paths = [
        "/opt/meddata-bridge/data/meddata.db",
        "/opt/meddatabridge/meddatabridge.db",
        "./meddatabridge.db"
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("[ERROR] Base de données introuvable")
        print(f"Chemins testés: {db_paths}")
        return
    
    print(f"[INFO] Base de données: {db_path}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, name, kind, is_enabled, inbox_path, 
                   archive_path, error_path, file_extensions
            FROM systemendpoint 
            WHERE kind='FILE'
        """)
        
        endpoints = cursor.fetchall()
        
        if not endpoints:
            print("[WARN] Aucun endpoint FILE trouvé")
            return
        
        print(f"[INFO] {len(endpoints)} endpoint(s) FILE trouvé(s):\n")
        
        for ep in endpoints:
            ep_id, name, kind, enabled, inbox, archive, error, ext = ep
            
            print(f"ID: {ep_id}")
            print(f"  Name: {name}")
            print(f"  Enabled: {enabled}")
            print(f"  Inbox: {inbox}")
            print(f"  Archive: {archive}")
            print(f"  Error: {error}")
            print(f"  Extensions: {ext}")
            
            # Vérifier si les répertoires existent
            if inbox:
                exists = os.path.exists(inbox)
                print(f"  Inbox exists: {exists}")
                if exists:
                    try:
                        files = os.listdir(inbox)
                        print(f"  Files in inbox: {len(files)}")
                        for f in files[:5]:  # Show first 5
                            print(f"    - {f}")
                    except Exception as e:
                        print(f"  Error listing inbox: {e}")
            
            print()
    
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_file_endpoints()
