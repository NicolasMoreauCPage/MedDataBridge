#!/usr/bin/env python3
"""
Import des médecins depuis les messages PAM archivés pour l'EJ 5.

Ce script extrait tous les médecins responsables présents dans les champs PV1-7
des messages IHE PAM archivés et les intègre dans la base de données.
"""
import os
from pathlib import Path
from sqlmodel import select
from app.db import session_factory
from app.models_structure import EntiteJuridique
from app.models_practitioners import MedecinResponsable
from app.services.medecin_extractor import extract_and_store_medecin_from_pv1


def extract_pv1_segment(message: str) -> str | None:
    """Extrait le segment PV1 d'un message HL7."""
    lines = message.split('\n')
    for line in lines:
        if line.startswith('PV1|'):
            return line
    return None


def main():
    print("=== Import des médecins depuis les messages PAM ===\n")
    
    # Chemins vers les répertoires PAM
    base_path = Path("/home/nico/Travail/Fhir_MedBridgeData/Interfaces/Entrant/PAM")
    directories = ["Archive", "Error", "In", "Out"]
    
    # Collecter tous les fichiers HL7 de tous les répertoires
    hl7_files = []
    for dir_name in directories:
        dir_path = base_path / dir_name
        if dir_path.exists():
            files = sorted(dir_path.glob("*.hl7"))
            if files:
                print(f"📁 {dir_name}: {len(files)} fichiers HL7")
                hl7_files.extend(files)
    
    if not hl7_files:
        print("❌ Aucun fichier HL7 trouvé")
        return
    
    print(f"\n📊 Total: {len(hl7_files)} fichiers HL7 à traiter\n")
    
    session = session_factory()
    
    try:
        # Vérifier l'EJ 5
        ej = session.exec(select(EntiteJuridique).where(EntiteJuridique.id == 5)).first()
        if not ej:
            print("❌ EJ 5 non trouvée dans la base de données")
            return
        
        print(f"✓ EJ trouvée: {ej.identifier} - {ej.name}\n")
        
        # Compter les médecins avant
        medecins_avant = session.exec(select(MedecinResponsable)).all()
        print(f"📊 Médecins dans la base avant import: {len(medecins_avant)}")
        for med in medecins_avant:
            print(f"   - {med.get_full_name()} ({med.get_identifier()})")
        
        # Statistiques
        messages_traites = 0
        messages_avec_pv1 = 0
        messages_avec_medecin = 0
        medecins_crees = {}
        erreurs = []
        
        print(f"\n🔄 Traitement des messages...\n")
        
        for file_path in hl7_files:
            messages_traites += 1
            
            try:
                # Lire le message
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    message = f.read()
                
                # Extraire PV1
                pv1_segment = extract_pv1_segment(message)
                
                if not pv1_segment:
                    continue
                
                messages_avec_pv1 += 1
                
                # Extraire le médecin
                medecin = extract_and_store_medecin_from_pv1(pv1_segment, session)
                
                if medecin:
                    messages_avec_medecin += 1
                    key = (medecin.rpps or "", medecin.adeli or "", medecin.family_name or "")
                    
                    if key not in medecins_crees:
                        medecins_crees[key] = {
                            'medecin': medecin,
                            'count': 1,
                            'fichiers': [file_path.name]
                        }
                    else:
                        medecins_crees[key]['count'] += 1
                        if len(medecins_crees[key]['fichiers']) < 5:
                            medecins_crees[key]['fichiers'].append(file_path.name)
                
                # Afficher la progression tous les 50 messages
                if messages_traites % 50 == 0:
                    print(f"   Traité {messages_traites}/{len(hl7_files)} messages...")
            
            except Exception as e:
                erreurs.append(f"{file_path.name}: {str(e)}")
                continue
        
        print(f"\n✅ Traitement terminé!")
        print(f"\n📊 Statistiques:")
        print(f"   - Messages traités: {messages_traites}")
        print(f"   - Messages avec PV1: {messages_avec_pv1}")
        print(f"   - Messages avec médecin: {messages_avec_medecin}")
        print(f"   - Médecins uniques trouvés: {len(medecins_crees)}")
        
        if erreurs:
            print(f"\n⚠️  Erreurs rencontrées: {len(erreurs)}")
            for err in erreurs[:10]:
                print(f"   - {err}")
            if len(erreurs) > 10:
                print(f"   ... et {len(erreurs) - 10} autres erreurs")
        
        # Afficher les médecins trouvés
        print(f"\n👨‍⚕️ Médecins extraits des messages PAM:")
        for info in sorted(medecins_crees.values(), key=lambda x: x['count'], reverse=True):
            med = info['medecin']
            count = info['count']
            fichiers = info['fichiers']
            
            print(f"\n   {med.get_full_name()}")
            print(f"   - Identifiant: {med.get_identifier()}")
            if med.rpps:
                print(f"   - RPPS: {med.rpps}")
            if med.adeli:
                print(f"   - ADELI: {med.adeli}")
            if med.specialty:
                print(f"   - Spécialité: {med.specialty}")
            print(f"   - Occurrences: {count} message(s)")
            print(f"   - Exemples: {', '.join(fichiers[:3])}")
        
        # Compter les médecins après
        medecins_apres = session.exec(select(MedecinResponsable)).all()
        print(f"\n📊 Médecins dans la base après import: {len(medecins_apres)}")
        
        nouveaux = len(medecins_apres) - len(medecins_avant)
        if nouveaux > 0:
            print(f"\n✅ {nouveaux} nouveau(x) médecin(s) intégré(s) dans la base de données")
        else:
            print(f"\nℹ️  Aucun nouveau médecin (tous déjà présents dans la base)")
    
    finally:
        session.close()


if __name__ == "__main__":
    main()
