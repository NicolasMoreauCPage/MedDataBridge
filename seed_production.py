#!/usr/bin/env python3
"""Script d'initialisation de la base de données pour la production."""
import sys
sys.path.insert(0, '/opt/meddata-bridge')

from app.db import init_db
from app.vocabulary_init import init_vocabularies
from app.services.structure_seed import ensure_demo_structure
from app.models_structure import GHTContext
from sqlmodel import Session, create_engine, select

# Utiliser le chemin absolu vers la base de données
engine = create_engine('sqlite:////opt/meddata-bridge/data/medbridge.db')

print('[1/4] Initialisation du schema de base de donnees...')
init_db()

with Session(engine) as session:
    print('[2/4] Initialisation des vocabulaires (35 systemes, ~200 valeurs)...')
    init_vocabularies(session)
    
    print('[3/4] Creation du contexte GHT...')
    ght = session.exec(select(GHTContext).where(GHTContext.id == 1)).first()
    if not ght:
        ght = GHTContext(id=1, name='CHU Demo', code='DEMO01', description='Contexte de demonstration')
        session.add(ght)
        session.commit()
        session.refresh(ght)
        print(f'  - GHT cree: {ght.name} (ID={ght.id})')
    else:
        print(f'  - GHT existant: {ght.name} (ID={ght.id})')
    
    print('[4/4] Creation de la structure hospitaliere complete...')
    print('  - Entites juridiques et geographiques')
    print('  - Poles, services, unites fonctionnelles')
    print('  - Unites d\'hebergement, chambres, lits')
    ensure_demo_structure(session, context=ght)
    
    print('\n✓ Base de donnees initialisee avec succes!')
    print('  Acces: http://qualifinterop.cpage.cloud:8000')
    print('  Admin: http://qualifinterop.cpage.cloud:8000/admin/ght/1/ej/1')
