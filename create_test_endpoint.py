#!/usr/bin/env python3
"""Crée un endpoint FILE de test pour HPRIM XML"""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session, select
from app.db import engine
from app.models_shared import SystemEndpoint

def create_hprim_test_endpoint():
    """Crée un endpoint de test pour HPRIM XML"""
    
    with Session(engine) as session:
        # Vérifier si l'endpoint existe déjà
        stmt = select(SystemEndpoint).where(SystemEndpoint.name == "HPRIM_TEST_LOCAL")
        existing = session.exec(stmt).first()
        
        if existing:
            print(f"[INFO] Endpoint existant trouvé: {existing.id}")
            print(f"  inbox_path: {existing.inbox_path}")
            print(f"  is_enabled: {existing.is_enabled}")
            
            # Mettre à jour si nécessaire
            existing.is_enabled = True
            existing.inbox_path = r"C:\Temp\hprim_test\inbox"
            existing.archive_path = r"C:\Temp\hprim_test\archive"
            existing.error_path = r"C:\Temp\hprim_test\error"
            session.add(existing)
            session.commit()
            print(f"[OK] Endpoint mis à jour")
            return existing.id
        
        # Créer un nouvel endpoint
        endpoint = SystemEndpoint(
            name="HPRIM_TEST_LOCAL",
            kind="FILE",
            direction="in",
            is_enabled=True,
            inbox_path=r"C:\Temp\hprim_test\inbox",
            archive_path=r"C:\Temp\hprim_test\archive",
            error_path=r"C:\Temp\hprim_test\error",
            file_extensions=".xml",
            description="Endpoint de test pour fichiers HPRIM XML",
        )
        
        session.add(endpoint)
        session.commit()
        session.refresh(endpoint)
        
        print(f"[OK] Endpoint créé: ID={endpoint.id}")
        print(f"  name: {endpoint.name}")
        print(f"  kind: {endpoint.kind}")
        print(f"  inbox_path: {endpoint.inbox_path}")
        print(f"  archive_path: {endpoint.archive_path}")
        print(f"  error_path: {endpoint.error_path}")
        print(f"  is_enabled: {endpoint.is_enabled}")
        
        return endpoint.id

if __name__ == "__main__":
    endpoint_id = create_hprim_test_endpoint()
    print(f"\n[NEXT] Copier le fichier test dans inbox:")
    print(f'  Copy-Item "C:\\Temp\\hprim_test\\test_hprim.xml" -Destination "C:\\Temp\\hprim_test\\inbox\\"')
