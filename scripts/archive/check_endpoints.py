#!/usr/bin/env python3
"""Vérifie les endpoints FILE configurés"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session, select
from app.db import engine
from app.models_shared import SystemEndpoint

def check_file_endpoints():
    """Liste tous les endpoints FILE"""
    
    with Session(engine) as session:
        stmt = select(SystemEndpoint).where(SystemEndpoint.kind == "FILE")
        endpoints = session.exec(stmt).all()
        
        if not endpoints:
            print("[WARN] Aucun endpoint FILE trouvé")
            return
        
        print(f"[INFO] {len(endpoints)} endpoint(s) FILE trouvé(s):\n")
        
        for ep in endpoints:
            print(f"ID: {ep.id}")
            print(f"  Name: {ep.name}")
            print(f"  Enabled: {ep.is_enabled}")
            print(f"  Direction: {ep.direction}")
            print(f"  Inbox: {ep.inbox_path}")
            print(f"  Archive: {ep.archive_path}")
            print(f"  Error: {ep.error_path}")
            print(f"  Extensions: {ep.file_extensions}")
            
            # Vérifier si les répertoires existent
            if ep.inbox_path:
                inbox = Path(ep.inbox_path)
                exists = inbox.exists()
                print(f"  Inbox exists: {exists}")
                if exists:
                    files = list(inbox.glob("*"))
                    print(f"  Files in inbox: {len(files)}")
                    for f in files[:5]:  # Show first 5
                        print(f"    - {f.name}")
            
            print()

if __name__ == "__main__":
    check_file_endpoints()
