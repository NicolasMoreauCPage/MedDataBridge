#!/usr/bin/env python3
"""Script pour ajouter des cotations et interventions de demo à la base de données locale."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter le répertoire courant au chemin
sys.path.insert(0, str(Path(__file__).parent))

from app.db import init_db
from app.models import Patient, Dossier, DossierType, CCAMAct, NGAPAct, UCDAct, LPPAct
from sqlmodel import Session, create_engine, select

# Utiliser la base de données locale
DATABASE_URL = "sqlite:///./data/medbridge.db"
engine = create_engine(DATABASE_URL, echo=False)


def seed_cotations():
    """Ajoute des cotations et interventions de demo"""
    
    print('🌱 Initialisation des cotations de demo...\n')
    
    with Session(engine) as session:
        # Créer quelques patients et dossiers de test
        patients_data = [
            {"family": "Martin", "given": "Alice", "dob": datetime(1965, 5, 10).date(), "type": "CCAM"},
            {"family": "Dupont", "given": "Bernard", "dob": datetime(1972, 8, 23).date(), "type": "NGAP"},
            {"family": "Bernard", "given": "Catherine", "dob": datetime(1978, 12, 5).date(), "type": "MIXED"},
            {"family": "Lefevre", "given": "Daniel", "dob": datetime(1955, 3, 17).date(), "type": "UCD"},
            {"family": "Petit", "given": "Élise", "dob": datetime(1990, 7, 22).date(), "type": "LPP"},
        ]
        
        for patient_data in patients_data:
            # Vérifier si le patient existe déjà
            existing_patient = session.exec(
                select(Patient).where(Patient.family == patient_data["family"])
            ).first()
            
            if existing_patient:
                patient = existing_patient
                print(f"  ℹ Patient existant: {patient.family} {patient.given}")
            else:
                patient = Patient(
                    family=patient_data["family"],
                    given=patient_data["given"],
                    birth_date=patient_data["dob"]
                )
                session.add(patient)
                session.commit()
                session.refresh(patient)
                print(f"  ✓ Patient créé: {patient.family} {patient.given}")
            
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
            cotation_type = patient_data["type"]
            if cotation_type == "CCAM":
                _add_ccam_cotations(session, dossier)
                print(f"    → Cotations CCAM ajoutées (3 actes)")
            elif cotation_type == "NGAP":
                _add_ngap_cotations(session, dossier)
                print(f"    → Cotations NGAP ajoutées (4 actes)")
            elif cotation_type == "UCD":
                _add_ucd_cotations(session, dossier)
                print(f"    → Cotations UCD ajoutées (2 actes)")
            elif cotation_type == "LPP":
                _add_lpp_cotations(session, dossier)
                print(f"    → Cotations LPP ajoutées (2 actes)")
            elif cotation_type == "MIXED":
                _add_mixed_cotations(session, dossier)
                print(f"    → Mix de cotations ajoutées (CCAM, NGAP, UCD, LPP)")
    
    print('\n✅ Cotations de demo ajoutées avec succès!')


def _add_ccam_cotations(session: Session, dossier: Dossier):
    """Ajoute des actes CCAM au dossier"""
    base_date = dossier.admit_time + timedelta(days=1)
    
    actes = [
        {"code_acte": "HBMD001", "code_activite": "01", "quantite": 1, "montant": 120.0, "label": "Intervention chirurgicale majeure"},
        {"code_acte": "LFDA011", "code_activite": "04", "quantite": 1, "montant": 85.50, "label": "Radiologie thoracique"},
        {"code_acte": "NZCB001", "code_activite": "02", "quantite": 2, "montant": 95.0, "label": "Acte de rééducation"},
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
            commentaire=acte_data["label"],
            facturable=True,
            valide=True
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
        {"lettre_cle": "A", "coefficient": 1.0, "montant": 25.00, "label": "Acte simple"},
        {"lettre_cle": "B", "coefficient": 1.5, "montant": 37.50, "label": "Consultation intermédiaire"},
        {"lettre_cle": "C", "coefficient": 2.0, "montant": 50.00, "label": "Acte complexe"},
        {"lettre_cle": "AMI", "coefficient": 2.5, "montant": 62.50, "label": "Acte très complexe"},
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
            commentaire=acte_data["label"],
            facturable=True,
            valide=True
        )
        session.add(ngap_act)
    
    # Mise à jour des flags cotations
    dossier.has_cotations = True
    dossier.cotations_count = len(actes)
    session.commit()


def _add_ucd_cotations(session: Session, dossier: Dossier):
    """Ajoute des actes UCD au dossier"""
    base_date = dossier.admit_time + timedelta(days=1)
    
    actes = [
        {
            "code_cip": "3400936050501",
            "designation": "DOLIPRANE 1000MG CPR SEC BT 8",
            "quantite": 2,
            "prix_unitaire": 4.50,
            "montant_total": 9.00
        },
        {
            "code_cip": "3400893448177",
            "designation": "IBUPROFEN 400MG CPR BT 30",
            "quantite": 1,
            "prix_unitaire": 3.25,
            "montant_total": 3.25
        },
    ]
    
    for i, acte_data in enumerate(actes):
        ucd_act = UCDAct(
            dossier_id=dossier.id,
            code_cip=acte_data["code_cip"],
            designation=acte_data["designation"],
            quantite=acte_data["quantite"],
            prix_unitaire=acte_data["prix_unitaire"],
            montant_total=acte_data["montant_total"],
            execute_date=base_date + timedelta(hours=i),
            commentaire=f"Dispensation UCD {i+1}",
            facturable=True,
            valide=True
        )
        session.add(ucd_act)
    
    # Mise à jour des flags cotations
    dossier.has_cotations = True
    dossier.cotations_count = len(actes)
    session.commit()


def _add_lpp_cotations(session: Session, dossier: Dossier):
    """Ajoute des actes LPP au dossier"""
    base_date = dossier.admit_time + timedelta(days=1)
    
    actes = [
        {
            "code_lpp": "1234567890123",
            "libelle": "Pansement adhésif hydrocelloïde",
            "quantite": 1,
            "prix_unitaire": 25.00,
            "montant_total": 25.00
        },
        {
            "code_lpp": "9876543210987",
            "libelle": "Orthèse de genou thermoformable",
            "quantite": 1,
            "prix_unitaire": 150.00,
            "montant_total": 150.00
        },
    ]
    
    for i, acte_data in enumerate(actes):
        lpp_act = LPPAct(
            dossier_id=dossier.id,
            code_lpp=acte_data["code_lpp"],
            libelle=acte_data["libelle"],
            quantite=acte_data["quantite"],
            prix_unitaire=acte_data["prix_unitaire"],
            montant_total=acte_data["montant_total"],
            execute_date=base_date + timedelta(hours=i),
            commentaire=f"Dispositif LPP {i+1}",
            facturable=True,
            valide=True
        )
        session.add(lpp_act)
    
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
        commentaire="Intervention chirurgicale principale",
        facturable=True,
        valide=True
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
        commentaire="Consultation paramédicale",
        facturable=True,
        valide=True
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
        commentaire="Médicament antipyrétique",
        facturable=True,
        valide=True
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
        commentaire="Pansement pour cicatrisation",
        facturable=True,
        valide=True
    )
    session.add(lpp_act)
    total_count += 1
    
    # Mise à jour des flags cotations
    dossier.has_cotations = True
    dossier.cotations_count = total_count
    session.commit()


if __name__ == "__main__":
    seed_cotations()
