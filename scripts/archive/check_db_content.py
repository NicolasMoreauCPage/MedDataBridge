#!/usr/bin/env python3
"""Vérifier le contenu de la base de données."""
import sys
sys.path.insert(0, '/opt/meddata-bridge')

from sqlmodel import Session, create_engine, select
from app.models_structure import GHTContext, EntiteJuridique, Service

# Utiliser le chemin absolu vers la base de données
engine = create_engine('sqlite:////opt/meddata-bridge/data/medbridge.db')

print('=== VERIFICATION DE LA BASE DE DONNEES ===\n')

with Session(engine) as session:
    # GHT Contexts
    ghts = session.exec(select(GHTContext)).all()
    print(f'[1] GHT Contexts: {len(ghts)}')
    for ght in ghts:
        print(f'  - {ght.name} (ID={ght.id})')
    
    # Entités juridiques
    ejs = session.exec(select(EntiteJuridique)).all()
    print(f'\n[2] Entites Juridiques: {len(ejs)}')
    for ej in ejs[:3]:  # Limiter à 3
        print(f'  - {ej.name} (ID={ej.id})')
    
    # Services
    services = session.exec(select(Service)).all()
    print(f'\n[3] Services: {len(services)}')
    for svc in services[:3]:  # Limiter à 3
        print(f'  - {svc.name} (ID={svc.id})')

print('\n=== FIN VERIFICATION ===')
