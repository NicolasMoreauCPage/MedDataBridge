"""Script de seed complet pour initialiser la base de données avec des données de test."""
import sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from sqlmodel import Session, create_engine
from app.models_structure_fhir import GHTContext, EntiteJuridique, EntiteGeographique
from app.models_structure import (
    Pole, Service, UniteFonctionnelle, UniteHebergement, 
    Chambre, Lit, LocationPhysicalType, LocationServiceType
)
from app.models import Patient, Venue, Mouvement, Dossier, Identifier, IdentifierType
from app.models_identifiers import IdentifierSystem

# Configuration
DATABASE_URL = "sqlite:///./medbridge.db"

def create_db_and_tables(engine):
    """Crée la base de données et les tables."""
    from app.models import SQLModel
    SQLModel.metadata.create_all(engine)

def seed_structure(session: Session):
    """Crée la structure organisationnelle complète."""
    # GHT
    ght = GHTContext(
        name="GHT Test Complet",
        code="GHT-TEST",
        oid_racine="1.2.3.4.5.6",
        fhir_server_url="http://test-fhir.hopital.fr/fhir",
        is_active=True
    )
    session.add(ght)
    session.commit()
    
    # EJ
    ej = EntiteJuridique(
        name="Centre Hospitalier Test",
        finess_ej="123456789",
        ght_context_id=ght.id,
        is_active=True
    )
    session.add(ej)
    session.commit()
    
    # EGs
    egs = []
    for i in range(2):
        eg = EntiteGeographique(
            identifier=f"EG{i+1}",
            name=f"Site {i+1}",
            entite_juridique_id=ej.id,
            finess=f"987654{i+1}",
            is_active=True
        )
        session.add(eg)
        egs.append(eg)
    session.commit()
    
    # Pôles
    poles = []
    pole_names = ["Médecine", "Chirurgie", "Urgences", "Mère-Enfant"]
    for i, name in enumerate(pole_names):
        eg = egs[i % len(egs)]
        pole = Pole(
            identifier=f"P{i+1}",
            name=f"Pôle {name}",
            entite_geo_id=eg.id,
            physical_type=LocationPhysicalType.SI
        )
        session.add(pole)
        poles.append(pole)
    session.commit()
    
    # Services
    services = []
    service_configs = [
        ("Cardiologie", LocationServiceType.MCO),
        ("Neurologie", LocationServiceType.MCO),
        ("Pneumologie", LocationServiceType.MCO),
        ("Orthopédie", LocationServiceType.MCO),
        ("Digestif", LocationServiceType.MCO),
        ("Urgences", LocationServiceType.URG),
        ("Maternité", LocationServiceType.MCO),
        ("Pédiatrie", LocationServiceType.MCO)
    ]
    for i, (name, stype) in enumerate(service_configs):
        pole = poles[i % len(poles)]
        service = Service(
            identifier=f"S{i+1}",
            name=name,
            pole_id=pole.id,
            physical_type=LocationPhysicalType.SI,
            service_type=stype
        )
        session.add(service)
        services.append(service)
    session.commit()
    
    # UFs
    ufs = []
    for i, service in enumerate(services):
        for j in range(2):  # 2 UFs par service
            uf = UniteFonctionnelle(
                identifier=f"UF{i+1}{j+1}",
                name=f"UF {service.name} {j+1}",
                service_id=service.id,
                physical_type=LocationPhysicalType.SI
            )
            session.add(uf)
            ufs.append(uf)
    session.commit()
    
    # UHs
    uhs = []
    for i, uf in enumerate(ufs):
        uh = UniteHebergement(
            identifier=f"UH{i+1}",
            name=f"UH {uf.name}",
            unite_fonctionnelle_id=uf.id,
            physical_type=LocationPhysicalType.WI
        )
        session.add(uh)
        uhs.append(uh)
    session.commit()
    
    # Chambres
    chambres = []
    for i, uh in enumerate(uhs):
        for j in range(5):  # 5 chambres par UH
            chambre = Chambre(
                identifier=f"CH{i+1}{j+1}",
                name=f"Chambre {j+1}",
                unite_hebergement_id=uh.id,
                physical_type=LocationPhysicalType.RO
            )
            session.add(chambre)
            chambres.append(chambre)
    session.commit()
    
    # Lits
    for i, chambre in enumerate(chambres):
        for j in range(2):  # 2 lits par chambre
            lit = Lit(
                identifier=f"L{i+1}{j+1}",
                name=f"Lit {j+1}",
                chambre_id=chambre.id,
                physical_type=LocationPhysicalType.BD
            )
            session.add(lit)
    session.commit()
    
    return ej, ufs

def seed_patients(session: Session, ej: EntiteJuridique, nb_patients: int = 50):
    """Crée un ensemble de patients avec leurs dossiers."""
    patients = []
    for i in range(nb_patients):
        # Création du patient
        patient = Patient(
            name=f"Prénom{i+1}",
            surname=f"NOM{i+1}",
            birth_date=datetime.now() - timedelta(days=365*30 + i*100)  # Ages variés
        )
        session.add(patient)
        session.commit()
        
        # Création du dossier associé
        dossier = Dossier(
            patient_id=patient.id,
            entite_juridique_id=ej.id,
            status="active"
        )
        session.add(dossier)
        session.commit()
        
        # Création des identifiants
        ipp = Identifier(
            value=f"IPP{i+1:06d}",
            type=IdentifierType.IPP,
            system=IdentifierSystem.IPP.value,
            entity_id=patient.id,
            entity_type="patient"
        )
        session.add(ipp)
        
        patients.append(patient)
    
    session.commit()
    return patients

def seed_venues(session: Session, patients: list[Patient], ufs: list[UniteFonctionnelle], nb_venues_per_patient: int = 2):
    """Crée des venues pour les patients."""
    for patient in patients:
        for i in range(nb_venues_per_patient):
            # Récupération du dossier du patient
            dossier = session.query(Dossier).filter(Dossier.patient_id == patient.id).first()
            
            # Création de la venue
            venue = Venue(
                dossier_id=dossier.id,
                uf_responsabilite=ufs[i % len(ufs)].id,
                start_time=datetime.now() - timedelta(days=i*30),
                venue_seq=f"VEN{patient.id}{i+1}"
            )
            session.add(venue)
            session.commit()
            
            # Identifiant de venue
            venue_id = Identifier(
                value=f"NDA{venue.id:06d}",
                type=IdentifierType.NDA,
                system=IdentifierSystem.NDA.value,
                entity_id=venue.id,
                entity_type="venue"
            )
            session.add(venue_id)
            
            # Création des mouvements
            mvt_in = Mouvement(
                venue_id=venue.id,
                when=venue.start_time,
                action="ADMIT",
                mouvement_seq=f"MVT{venue.id}1"
            )
            session.add(mvt_in)
            
            # Si la venue n'est pas la dernière, on ajoute une sortie
            if i < nb_venues_per_patient - 1:
                mvt_out = Mouvement(
                    venue_id=venue.id,
                    when=venue.start_time + timedelta(days=5),
                    action="DISCHARGE",
                    mouvement_seq=f"MVT{venue.id}2"
                )
                session.add(mvt_out)
    
    session.commit()

def main():
    """Point d'entrée principal."""
    engine = create_engine(DATABASE_URL)
    create_db_and_tables(engine)
    
    with Session(engine) as session:
        print("Création de la structure...")
        ej, ufs = seed_structure(session)
        
        print("Création des patients...")
        patients = seed_patients(session, ej)
        
        print("Création des venues...")
        seed_venues(session, patients, ufs)
        
        print("Seed terminé avec succès!")

if __name__ == "__main__":
    main()