#!/usr/bin/env python3
"""Script d'initialisation de la base de données pour la production."""
import sys
sys.path.insert(0, '/opt/meddata-bridge')

from datetime import datetime, timedelta
from app.db import init_db
from app.vocabulary_init import init_vocabularies
from app.services.structure_seed import ensure_demo_structure
from app.models_structure import GHTContext
from app.models import Patient, Dossier, DossierType, CCAMAct, NGAPAct, UCDAct, LPPAct
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
    
    print('[5/5] Ajout de cotations et interventions de demo...')
    _seed_cotations_demo(session)
    
    print('\n✓ Base de donnees initialisee avec succes!')
    print('  Acces: http://qualifinterop.cpage.cloud:8000')
    print('  Admin: http://qualifinterop.cpage.cloud:8000/admin/ght/1/ej/1')


def _seed_cotations_demo(session: Session):
    """Ajoute des cotations et interventions demo pour certains dossiers"""
    
    # Créer quelques patients et dossiers de test
    patients_data = [
        {"family": "Martin", "given": "Alice", "dob": datetime(1965, 5, 10).date()},
        {"family": "Dupont", "given": "Bernard", "dob": datetime(1972, 8, 23).date()},
        {"family": "Bernard", "given": "Catherine", "dob": datetime(1978, 12, 5).date()},
    ]
    
    for patient_data in patients_data:
        # Vérifier si le patient existe déjà
        existing_patient = session.exec(
            select(Patient).where(Patient.family == patient_data["family"])
        ).first()
        
        if existing_patient:
            patient = existing_patient
        else:
            patient = Patient(
                family=patient_data["family"],
                given=patient_data["given"],
                birth_date=patient_data["dob"]
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)
        
        # Créer un dossier pour ce patient
        admit_time = datetime.now() - timedelta(days=2)
        dossier = Dossier(
            patient_id=patient.id,
            admit_time=admit_time,
            dossier_type=DossierType.HOSPITALISE
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)
        
        # Ajouter des cotations variées selon le patient
        if patient.family == "Martin":
            _add_ccam_cotations(session, dossier)
        elif patient.family == "Dupont":
            _add_ngap_cotations(session, dossier)
        elif patient.family == "Bernard":
            _add_mixed_cotations(session, dossier)
        
        print(f"  ✓ Patient {patient.family} {patient.given}: dossier créé avec cotations")


def _add_ccam_cotations(session: Session, dossier: Dossier):
    """Ajoute des actes CCAM au dossier"""
    base_date = dossier.admit_time + timedelta(days=1)
    
    actes = [
        {"code_acte": "HBMD001", "code_activite": "01", "quantite": 1, "montant": 120.0},
        {"code_acte": "LFDA011", "code_activite": "04", "quantite": 1, "montant": 85.50},
        {"code_acte": "NZCB001", "code_activite": "02", "quantite": 2, "montant": 95.0},
    ]
    
    for i, acte_data in enumerate(actes):
        ccam_act = CCAMAct(
            dossier_id=dossier.id,
            code_acte=acte_data["code_acte"],
            code_activite=acte_data["code_activite"],
            execute_date=base_date + timedelta(hours=i*2),
            execute_heure=f"09:{i*15:02d}",
            quantite=acte_data["quantite"],
            montant=acte_data["montant"],
            commentaire=f"Acte CCAM {i+1}",
            facturable=True
        )
        session.add(ccam_act)
    
    # Mise à jour des flags cotations
    dossier.has_cotations = True
    dossier.cotations_count = len(actes)
    session.commit()


def _add_ngap_cotations(session: Session, dossier: Dossier):
    """Ajoute des actes NGAP au dossier"""
    base_date = dossier.admit_time + timedelta(days=1)
    
    actes = [
        {"lettre_cle": "A", "coefficient": 1.0, "montant": 25.00},
        {"lettre_cle": "B", "coefficient": 1.5, "montant": 37.50},
        {"lettre_cle": "C", "coefficient": 2.0, "montant": 50.00},
        {"lettre_cle": "AMI", "coefficient": 2.5, "montant": 62.50},
    ]
    
    for i, acte_data in enumerate(actes):
        ngap_act = NGAPAct(
            dossier_id=dossier.id,
            lettre_cle=acte_data["lettre_cle"],
            coefficient=acte_data["coefficient"],
            execute_date=base_date + timedelta(hours=i),
            execute_heure=f"10:{i*15:02d}",
            denombrement=1,
            montant=acte_data["montant"],
            commentaire=f"Acte NGAP {i+1}",
            facturable=True
        )
        session.add(ngap_act)
    
    # Mise à jour des flags cotations
    dossier.has_cotations = True
    dossier.cotations_count = len(actes)
    session.commit()


def _add_mixed_cotations(session: Session, dossier: Dossier):
    """Ajoute un mix de cotations CCAM, NGAP, UCD et LPP au dossier"""
    base_date = dossier.admit_time + timedelta(days=1)
    total_count = 0
    
    # Acte CCAM
    ccam_act = CCAMAct(
        dossier_id=dossier.id,
        code_acte="HBMD001",
        code_activite="01",
        execute_date=base_date,
        execute_heure="09:00",
        quantite=1,
        montant=120.0,
        commentaire="Acte chirurgical principal"
    )
    session.add(ccam_act)
    total_count += 1
    
    # Acte NGAP
    ngap_act = NGAPAct(
        dossier_id=dossier.id,
        lettre_cle="B",
        coefficient=1.5,
        execute_date=base_date + timedelta(hours=2),
        execute_heure="11:00",
        denombrement=1,
        montant=37.50,
        commentaire="Consultation paramédicale"
    )
    session.add(ngap_act)
    total_count += 1
    
    # Acte UCD (médicament)
    ucd_act = UCDAct(
        dossier_id=dossier.id,
        code_cip="3400936050501",
        designation="DOLIPRANE 1000MG CPR SEC BT 8",
        quantite=2,
        prix_unitaire=4.50,
        montant_total=9.00,
        execute_date=base_date + timedelta(hours=3),
        commentaire="Médicament antipyrétique"
    )
    session.add(ucd_act)
    total_count += 1
    
    # Acte LPP (dispositif médical)
    lpp_act = LPPAct(
        dossier_id=dossier.id,
        code_lpp="1234567890123",
        libelle="Pansement adhésif hydrocelloïde",
        quantite=1,
        prix_unitaire=25.00,
        montant_total=25.00,
        execute_date=base_date + timedelta(hours=4),
        commentaire="Pansement pour cicatrisation"
    )
    session.add(lpp_act)
    total_count += 1
    
    # Mise à jour des flags cotations
    dossier.has_cotations = True
    dossier.cotations_count = total_count
    session.commit()
