#!/usr/bin/env python3
"""
Script pour extraire les médecins responsables depuis les messages PAM archivés.

Lit les 298 messages HL7 dans pam_archive, extrait les informations PV1-7,
et construit le référentiel initial des médecins responsables.
"""
import sys
import os
from pathlib import Path
from typing import List, Dict
import logging

# Ajouter le chemin racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session, select, func
from app.db import engine
from app.models_practitioners import MedecinResponsable
from app.services.medecin_extractor import extract_medecin_from_pv1_7, get_or_create_medecin

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_archived_messages():
    """Analyse les messages archivés pour extraire les médecins."""
    
    archive_dir = Path("tests/exemples/pam_archive")
    
    if not archive_dir.exists():
        logger.error(f"Archive directory not found: {archive_dir}")
        return
    
    # Trouver tous les fichiers .hl7
    hl7_files = list(archive_dir.glob("*.hl7"))
    
    logger.info(f"Trouvé {len(hl7_files)} fichiers HL7 dans {archive_dir}")
    
    if not hl7_files:
        logger.warning("Aucun fichier .hl7 trouvé dans l'archive")
        return
    
    medecins_extraits = []
    messages_avec_medecin = 0
    messages_sans_medecin = 0
    erreurs = 0
    
    with Session(engine) as session:
        for idx, hl7_file in enumerate(hl7_files, 1):
            try:
                # Lire le message
                with open(hl7_file, 'r', encoding='utf-8') as f:
                    hl7_content = f.read()
                
                # Trouver le segment PV1
                pv1_segment = None
                for line in hl7_content.split('\n'):
                    if line.startswith('PV1|'):
                        pv1_segment = line.strip()
                        break
                
                if not pv1_segment:
                    messages_sans_medecin += 1
                    continue
                
                # Extraire médecin depuis PV1
                medecin_data = extract_medecin_from_pv1_7(pv1_segment)
                
                if medecin_data:
                    # Stocker dans la DB
                    medecin = get_or_create_medecin(session, medecin_data)
                    if medecin:
                        medecins_extraits.append(medecin)
                        messages_avec_medecin += 1
                        
                        # Afficher progression tous les 50 messages
                        if idx % 50 == 0:
                            logger.info(f"Progression: {idx}/{len(hl7_files)} messages traités...")
                    else:
                        messages_sans_medecin += 1
                else:
                    messages_sans_medecin += 1
                    
            except Exception as e:
                logger.error(f"[{idx}/{len(hl7_files)}] Erreur traitement {hl7_file.name}: {e}")
                erreurs += 1
    
    # Statistiques finales
    print("\n" + "=" * 70)
    print("RÉSULTATS DE L'EXTRACTION DES MÉDECINS RESPONSABLES")
    print("=" * 70)
    print(f"\n📁 Messages analysés:")
    print(f"   Total:                    {len(hl7_files)}")
    print(f"   Avec médecin (PV1-7):     {messages_avec_medecin}")
    print(f"   Sans médecin:             {messages_sans_medecin}")
    print(f"   Erreurs de parsing:       {erreurs}")
    
    # Compter les médecins uniques dans la DB
    with Session(engine) as session:
        total_medecins = session.exec(select(func.count(MedecinResponsable.id))).one()
        medecins_with_rpps = session.exec(
            select(func.count(MedecinResponsable.id)).where(MedecinResponsable.rpps.isnot(None))
        ).one()
        medecins_with_adeli = session.exec(
            select(func.count(MedecinResponsable.id)).where(MedecinResponsable.adeli.isnot(None))
        ).one()
        
        print(f"\n👨‍⚕️ Médecins dans le référentiel:")
        print(f"   Total:                    {total_medecins}")
        print(f"   Avec RPPS:                {medecins_with_rpps}")
        print(f"   Avec ADELI:               {medecins_with_adeli}")
        
        # Afficher quelques exemples
        print(f"\n📋 Exemples de médecins extraits (5 premiers):")
        print("   " + "-" * 66)
        medecins_sample = session.exec(select(MedecinResponsable).limit(5)).all()
        for m in medecins_sample:
            ids = []
            if m.rpps:
                ids.append(f"RPPS:{m.rpps}")
            if m.adeli:
                ids.append(f"ADELI:{m.adeli}")
            id_str = ", ".join(ids) if ids else "Pas d'ID"
            print(f"   • {m.get_full_name():<40} ({id_str})")
    
    print("\n" + "=" * 70)
    print("✅ Extraction terminée")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    analyze_archived_messages()
