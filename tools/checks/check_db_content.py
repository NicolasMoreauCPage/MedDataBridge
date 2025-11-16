"""
Vérification rapide du contenu de la base de données
"""
from app.db import engine, Session
from app.models import Patient, Dossier, Venue, Mouvement
from app.models_structure import GHTContext, EntiteJuridique
from app.models_structure import Service, UniteFonctionnelle
from sqlmodel import select

def check_database():
    print("\n" + "="*80)
    print("CONTENU DE LA BASE DE DONNÉES medbridge.db")
    print("="*80)
    
    session = Session(engine)
    
    try:
        # Compter les enregistrements dans les tables principales
        tables = {
            "GHTContext": GHTContext,
            "EntiteJuridique": EntiteJuridique,
            "Service": Service,
            "UniteFonctionnelle": UniteFonctionnelle,
            "Patient": Patient,
            "Dossier": Dossier,
            "Venue": Venue,
            "Mouvement": Mouvement,
        }
        
        for table_name, model in tables.items():
            count = len(session.exec(select(model)).all())
            status = "✅" if count > 0 else "⚠️ "
            print(f"{status} {table_name:30} : {count:5} enregistrements")
        
        # Afficher quelques exemples si données présentes
        print("\n" + "="*80)
        print("EXEMPLES DE DONNÉES")
        print("="*80)
        
        # GHT
        ghts = session.exec(select(GHTContext).limit(3)).all()
        if ghts:
            print(f"\n📊 GHT ({len(ghts)} affichés) :")
            for ght in ghts:
                print(f"   - ID={ght.id}, Code={ght.code}, Nom={ght.name}")
        
        # Entités Juridiques
        ejs = session.exec(select(EntiteJuridique).limit(3)).all()
        if ejs:
            print(f"\n🏥 Entités Juridiques ({len(ejs)} affichés) :")
            for ej in ejs:
                print(f"   - ID={ej.id}, FINESS={ej.finess_ej}, Nom={ej.name}")
        
        # Services
        services = session.exec(select(Service).limit(3)).all()
        if services:
            print(f"\n🏢 Services ({len(services)} affichés) :")
            for service in services:
                print(f"   - ID={service.id}, Code={service.identifier}, Nom={service.name}")
        
        # UFs
        ufs = session.exec(select(UniteFonctionnelle).limit(3)).all()
        if ufs:
            print(f"\n📋 Unités Fonctionnelles ({len(ufs)} affichés) :")
            for uf in ufs:
                print(f"   - ID={uf.id}, Code={uf.identifier}, Nom={uf.name}")
        
        # Patients
        patients = session.exec(select(Patient).limit(3)).all()
        if patients:
            print(f"\n👤 Patients ({len(patients)} affichés) :")
            for patient in patients:
                print(f"   - ID={patient.id}, Identifiant={patient.identifier}, Nom={patient.family} {patient.given}")
        
        # Mouvements
        mouvements = session.exec(select(Mouvement).limit(3)).all()
        if mouvements:
            print(f"\n🚶 Mouvements ({len(mouvements)} affichés) :")
            for mouv in mouvements:
                print(f"   - ID={mouv.id}, Seq={mouv.mouvement_seq}, Type={mouv.type}, Quand={mouv.when}")
        
        print("\n" + "="*80)
        
    finally:
        session.close()


if __name__ == "__main__":
    check_database()
