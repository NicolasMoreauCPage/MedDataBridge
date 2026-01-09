#!/usr/bin/env python3
import sys
import os
# Ajouter le répertoire racine du projet au chemin
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
"""Script principal d'initialisation complète de la base de données.

Usage:
    python init_db.py                    # Init complète (structure + vocab + namespaces + population + scénarios)
    python init_db.py --reset            # Supprime la DB existante avant init
    python init_db.py --skip-vocab       # Saute l'init des vocabulaires
    python init_db.py --skip-population  # Saute le seed de patients
    python init_db.py --skip-scenarios   # Saute l'import des scénarios HL7/HPRIM
    python init_db.py --minimal          # Seed minimal (1 patient)
    python init_db.py --rich             # Seed riche (40 patients)
    python init_db.py --demo-scenarios   # Ajoute scénarios démo complexes
    python init_db.py --with-cotations   # Ajoute cotations médicales réalistes

Ce script orchestre dans l'ordre:
1. Création du schéma (tables) via app.db.init_db()
2. Vocabulaires standards (35 systèmes, 207 valeurs)
3. Structure multi-EJ (4 EJ: CHU, hôpital, EHPAD, psy) + hiérarchie complète
4. Endpoints MLLP/FHIR (12 endpoints: 3 par EJ)
5. Namespaces d'identifiants (13: IPP/NDA/VENUE par EJ + global structure)
6. Population de patients (minimal:1, standard:120, rich:40 avec scénarios)
7. Scénarios IHE HL7 (depuis Doc/examples - partie intégrante du programme)
8. Scénarios d'intégration HL7/HPRIM (159 scénarios depuis interfaces.integration - partie intégrante du programme)
9. Scénarios HL7 PAM (124 scénarios IHE PAM - partie intégrante du programme)
10. Scénarios démo optionnels (transferts, annulations)
11. Cotations médicales réalistes optionnelles

Tous les appels sont idempotents: re-exécuter ce script est safe.
"""
import argparse
import sys
import re
import json
from pathlib import Path
from subprocess import run, CalledProcessError
from typing import List, Tuple
from datetime import datetime, timedelta
from random import choice

# Imports pour les nouvelles fonctionnalités
from sqlmodel import Session, select
from app.models import Patient, Dossier, Venue, Mouvement, DossierType, Sequence
from app.models_structure import GHTContext, EntiteJuridique, EntiteGeographique, IdentifierNamespace
from app.models_structure import Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
from app.models_structure import LocationPhysicalType, LocationServiceType
from app.db import init_db as init_db_schema, engine, get_next_sequence
from random import choice

DB_PATH = Path("medbridge.db")

DB_PATH = Path("medbridge.db")


def extract_hl7_messages(hl7_content: str) -> list:
    """
    Extrait les messages HL7 individuels d'un fichier.
    Les messages sont séparés par des newlines (\\r\\n ou \\n).
    """
    # Normaliser les séparateurs
    content = hl7_content.replace('\r\n', '\n').replace('\r', '\n')

    messages = []
    current_msg = []

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            if current_msg:
                messages.append('\\r'.join(current_msg))
                current_msg = []
        else:
            # Si la ligne commence par MSH et qu'on a déjà un message en cours,
            # c'est un nouveau message
            if line.startswith('MSH') and current_msg:
                messages.append('\\r'.join(current_msg))
                current_msg = [line]
            else:
                current_msg.append(line)

    # Ajouter le dernier message
    if current_msg:
        messages.append('\\r'.join(current_msg))

    return messages


def _ensure_sequences(session: Session) -> None:
    """S'assure que les séquences existent pour les compteurs."""
    for name in ["patient", "dossier", "venue", "mouvement"]:
        if not session.get(Sequence, name):
            session.add(Sequence(name=name, value=0))
    session.commit()


def _add_cotations_to_dossier(session: Session, dossier: Dossier, cotation_type: str = "MIXED") -> int:
    """Ajoute des cotations à un dossier. Retourne le nombre de cotations ajoutées."""
    from datetime import timedelta
    from app.models import CCAMAct, NGAPAct, UCDAct, LPPAct
    
    admit_time = dossier.admit_time
    total_count = 0
    
    if cotation_type == "CCAM":
        actes = [
            {"code_acte": "HBMD001", "code_activite": "01", "montant": 120.0},
            {"code_acte": "LFDA011", "code_activite": "04", "montant": 85.50},
        ]
        for i, acte_data in enumerate(actes):
            act = CCAMAct(
                dossier_id=dossier.id,
                code_acte=acte_data["code_acte"],
                code_activite=acte_data["code_activite"],
                execute_date=admit_time + timedelta(days=1, hours=i*2),
                montant_total=acte_data["montant"],
                facture="non"
            )
            session.add(act)
            total_count += 1
            
    elif cotation_type == "NGAP":
        actes = [
            {"lettre_cle": "A", "coefficient": 1.0, "montant": 25.00},
            {"lettre_cle": "B", "coefficient": 1.5, "montant": 37.50},
        ]
        for i, acte_data in enumerate(actes):
            act = NGAPAct(
                dossier_id=dossier.id,
                lettre_cle=acte_data["lettre_cle"],
                coefficient=acte_data["coefficient"],
                execute_date=admit_time + timedelta(days=1, hours=i),
                montant_total=acte_data["montant"],
                denombrement=1,
                facture="non"
            )
            session.add(act)
            total_count += 1
            
    elif cotation_type == "MIXED":
        # 1 CCAM
        act = CCAMAct(
            dossier_id=dossier.id,
            code_acte="HBMD001",
            code_activite="01",
            execute_date=admit_time + timedelta(days=1),
            montant_total=120.0,
            facture="non"
        )
        session.add(act)
        total_count += 1
        
        # 1 NGAP
        act = NGAPAct(
            dossier_id=dossier.id,
            lettre_cle="B",
            coefficient=1.5,
            execute_date=admit_time + timedelta(days=1, hours=2),
            montant_total=37.50,
            denombrement=1,
            facture="non"
        )
        session.add(act)
        total_count += 1
        
        # 1 UCD
        act = UCDAct(
            dossier_id=dossier.id,
            code_ucd="3400936050501",
            denomination_libelle="DOLIPRANE 1000MG",
            quantite=2,
            montant_unitaire_facture_ttc=4.50,
            execute_date=admit_time + timedelta(days=1, hours=3)
        )
        session.add(act)
        total_count += 1
        
        # 1 LPP
        act = LPPAct(
            dossier_id=dossier.id,
            code_lpp="1234567890123",
            denomination_libelle="Pansement adhésif",
            quantite=1,
            montant_unitaire_facture_ttc=25.00,
            execute_date=admit_time + timedelta(days=1, hours=4)
        )
        session.add(act)
        total_count += 1
    
    # Mettre à jour les flags
    if total_count > 0:
        dossier.has_cotations = True
        dossier.cotations_count = total_count
    
    return total_count


def _add_cotations_to_existing_dossiers() -> None:
    """Ajoute des cotations aux dossiers existants (pour seed standard) - 70% de couverture."""
    with Session(engine) as session:
        # Récupérer tous les dossiers existants
        dossiers = session.exec(select(Dossier)).all()
        
        if not dossiers:
            print("Aucun dossier trouvé, cotations non ajoutées.")
            return
        
        # Distribution réaliste des types de cotations
        # CCAM et NGAP plus fréquents (actes médicaux courants)
        # UCD et LPP moins fréquents (médicaments et dispositifs)
        # MIXED : cas complexes avec plusieurs types
        cotation_weights = {
            "CCAM": 30,    # Actes techniques courants
            "NGAP": 25,    # Actes médicaux et infirmiers
            "MIXED": 20,   # Cas complexes
            "UCD": 15,     # Médicaments onéreux
            "LPP": 10,     # Dispositifs médicaux
        }
        
        cotation_pool = []
        for cot_type, weight in cotation_weights.items():
            cotation_pool.extend([cot_type] * weight)
        
        added = 0
        
        # Ajouter des cotations à 70% des dossiers
        for i, dossier in enumerate(dossiers):
            # 70% des dossiers ont des cotations (0-69 sur 100)
            if (i * 7) % 10 < 7:
                cotation_type = choice(cotation_pool)
                count = _add_cotations_to_dossier(session, dossier, cotation_type)
                added += 1
                if added <= 3:  # Afficher les 3 premiers exemples
                    patient = session.get(Patient, dossier.patient_id)
                    print(f"  • {patient.family} {patient.given}: {count} cotations ({cotation_type})")
        
        session.commit()
        coverage = (added / len(dossiers) * 100) if len(dossiers) > 0 else 0
        print(f"✓ {added} dossiers enrichis avec des cotations ({coverage:.1f}% de couverture)")


def seed_minimal() -> None:
    """Seed minimal avec 1 patient de démo."""
    with Session(engine) as session:
        _ensure_sequences(session)
        patient = Patient(
            family="DOE",
            given="John",
            birth_date="1985-05-05",
            gender="male",
            city="Paris",
            postal_code="75000",
            country="FR",
            identity_reliability_code="VALI",
            identity_reliability_date="2024-01-01",
            identity_reliability_source="CNI",
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)

        dossier_seq = get_next_sequence(session, "dossier")
        dossier = Dossier(
            dossier_seq=dossier_seq,
            patient_id=patient.id,
            uf_responsabilite="UF-EXT-1-1-1",  # sera valide si structure étendue; sinon valeur libre
            admit_time=datetime.utcnow(),
            dossier_type=DossierType.HOSPITALISE,
            reason="Admission initiale",
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)

        venue_seq = get_next_sequence(session, "venue")
        venue = Venue(
            venue_seq=venue_seq,
            dossier_id=dossier.id,
            uf_responsabilite=dossier.uf_responsabilite,
            start_time=datetime.utcnow(),
            code="VENUE-1",
            label="Unité Initiale",
            operational_status="active",
        )
        session.add(venue)
        session.commit()
        session.refresh(venue)

        mouvement_seq = get_next_sequence(session, "mouvement")
        mouvement = Mouvement(
            mouvement_seq=mouvement_seq,
            venue_id=venue.id,
            when=datetime.utcnow(),
            location=f"{venue.uf_responsabilite}^BOX-1^CH-01",
            trigger_event="A01",
            movement_type="Admission",
        )
        session.add(mouvement)
        session.commit()
        
        # Ajouter des cotations au dossier
        _add_cotations_to_dossier(session, dossier, cotation_type="MIXED")
        session.commit()
        
        print("✓ Seed minimal inséré (avec cotations)")


def seed_rich(nb_patients: int = 200) -> None:
    """Seed riche avec scénarios de mouvements réalistes.
    
    Volumes générés (nb_patients=200):
    - 200 patients avec données variées
    - 200 dossiers (1 par patient)
    - 400-600 venues (2-3 par dossier)
    - 800-1200 mouvements (plusieurs par venue)
    - 150-250 cotations (50-75% des dossiers)
    """
    with Session(engine) as session:
        _ensure_sequences(session)

        # Collect UF codes si structure présente
        uf_codes = [uf.identifier for uf in session.exec(select(UniteFonctionnelle)).all()]
        if not uf_codes:
            uf_codes = ["UF-RICH-1", "UF-RICH-2", "UF-RICH-3", "UF-RICH-4"]
        
        # Données réalistes pour génération
        prenoms_m = ["Alexandre", "Antoine", "Arthur", "Baptiste", "Benjamin", "Charles", "Clément", "David", 
                     "Étienne", "François", "Gabriel", "Hugo", "Jean", "Julien", "Laurent", "Luc", "Lucas",
                     "Marc", "Martin", "Mathieu", "Maxime", "Nicolas", "Olivier", "Paul", "Pierre", "Raphaël",
                     "Simon", "Thomas", "Victor", "Vincent"]
        prenoms_f = ["Amélie", "Anne", "Aurélie", "Camille", "Caroline", "Catherine", "Céline", "Charlotte",
                     "Chloé", "Claire", "Émilie", "Emma", "Julie", "Juliette", "Laura", "Léa", "Louise",
                     "Lucie", "Manon", "Marie", "Marine", "Martine", "Nathalie", "Pauline", "Sarah", "Sophie",
                     "Stéphanie", "Valentine", "Valérie", "Zoé"]
        noms = ["Martin", "Bernard", "Thomas", "Petit", "Robert", "Richard", "Durand", "Dubois", "Moreau",
                "Laurent", "Simon", "Michel", "Lefebvre", "Leroy", "Roux", "David", "Bertrand", "Morel",
                "Fournier", "Girard", "Bonnet", "Dupont", "Lambert", "Fontaine", "Rousseau", "Vincent",
                "Muller", "Lefèvre", "Faure", "André", "Mercier", "Blanc", "Guerin", "Boyer", "Garnier",
                "Chevalier", "François", "Legrand", "Gauthier", "Garcia", "Perrin", "Robin", "Clément",
                "Morin", "Nicolas", "Henry", "Roussel", "Mathieu", "Gautier", "Masson"]
        villes = ["Paris", "Lyon", "Marseille", "Toulouse", "Nice", "Nantes", "Strasbourg", "Montpellier",
                  "Bordeaux", "Lille", "Rennes", "Reims", "Le Havre", "Saint-Étienne", "Toulon", "Grenoble",
                  "Dijon", "Angers", "Nîmes", "Villeurbanne", "Le Mans", "Aix-en-Provence", "Clermont-Ferrand",
                  "Brest", "Tours", "Amiens", "Limoges", "Annecy", "Perpignan", "Boulogne-Billancourt"]
        
        types_admission = ["Admission aux urgences", "Admission programmée", "Transfert autre établissement",
                          "Admission en consultation", "Admission post-opératoire"]
        
        print(f"Génération de {nb_patients} patients avec parcours réalistes...")
        
        for i in range(1, nb_patients + 1):
            # Alternance homme/femme
            is_male = i % 2 == 0
            gender = "male" if is_male else "female"
            prenom = choice(prenoms_m if is_male else prenoms_f)
            nom = choice(noms)
            
            # Âge varié : 20-90 ans
            age_years = 20 + (i % 70)
            birth_year = 2024 - age_years
            birth_month = (i % 12) + 1
            birth_day = ((i * 7) % 28) + 1
            
            patient = Patient(
                family=nom,
                given=prenom,
                birth_date=f"{birth_year}-{birth_month:02d}-{birth_day:02d}",
                gender=gender,
                city=choice(villes),
                postal_code=f"{13000 + (i % 87000):05d}",
                country="FR",
                identity_reliability_code="VALI" if i % 10 != 0 else "PROV",
                identity_reliability_date="2024-02-01",
                identity_reliability_source="CNI" if i % 3 == 0 else "PP",
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)

            dossier_seq = get_next_sequence(session, "dossier")
            uf_resp = choice(uf_codes)
            
            # Type de dossier varié
            if i % 5 == 0:
                dtype = DossierType.HOSPITALISATION_PARTIELLE
            elif i % 7 == 0:
                dtype = DossierType.EXTERNE
            elif i % 11 == 0:
                dtype = DossierType.URGENCE
            else:
                dtype = DossierType.HOSPITALISE
                
            dossier = Dossier(
                dossier_seq=dossier_seq,
                patient_id=patient.id,
                uf_responsabilite=uf_resp,
                admit_time=datetime.utcnow() - timedelta(days=i % 90),
                dossier_type=dtype,
                reason=choice(types_admission),
            )
            session.add(dossier)
            session.commit()
            session.refresh(dossier)

            # Nombre de venues varié : 2-4 selon le parcours
            nb_venues = 2 if dtype == DossierType.HOSPITALISATION_PARTIELLE else (3 if i % 3 == 0 else 2)
            venues = []
            
            for v in range(1, nb_venues + 1):
                venue_seq = get_next_sequence(session, "venue")
                venue = Venue(
                    venue_seq=venue_seq,
                    dossier_id=dossier.id,
                    uf_responsabilite=choice(uf_codes),
                    start_time=datetime.utcnow() - timedelta(days=i % 60, hours=v),
                    code=f"VENUE-{i}-{v}",
                    label=f"Séjour {v}",
                    operational_status="active" if v == nb_venues else "finished",
                )
                session.add(venue)
                session.commit()
                session.refresh(venue)
                venues.append(venue)

            # Mouvements réalistes : admission + transferts + sortie
            nb_mouvements = nb_venues + 1  # Au moins 1 mouvement par venue + sortie
            
            # Admission
            mouvement_seq = get_next_sequence(session, "mouvement")
            mouvement = Mouvement(
                mouvement_seq=mouvement_seq,
                venue_id=venues[0].id,
                when=dossier.admit_time,
                location=f"{venues[0].uf_responsabilite}^CHAMBRE-{(i % 50) + 1}^LIT-{(i % 2) + 1}",
                trigger_event="A01",
                movement_type="Admission",
            )
            session.add(mouvement)
            
            # Transferts entre venues
            for v_idx in range(len(venues) - 1):
                mouvement_seq = get_next_sequence(session, "mouvement")
                mouvement = Mouvement(
                    mouvement_seq=mouvement_seq,
                    venue_id=venues[v_idx + 1].id,
                    when=venues[v_idx + 1].start_time,
                    location=f"{venues[v_idx + 1].uf_responsabilite}^CHAMBRE-{((i + v_idx) % 50) + 1}^LIT-{((i + v_idx) % 2) + 1}",
                    trigger_event="A02",
                    movement_type="Transfert",
                    from_location=venues[v_idx].uf_responsabilite,
                    to_location=venues[v_idx + 1].uf_responsabilite,
                )
                session.add(mouvement)
            
            # Sortie (pour les dossiers terminés)
            if dtype != DossierType.EXTERNE and i % 3 != 0:
                mouvement_seq = get_next_sequence(session, "mouvement")
                mouvement = Mouvement(
                    mouvement_seq=mouvement_seq,
                    venue_id=venues[-1].id,
                    when=datetime.utcnow() - timedelta(days=(i % 30)),
                    location=f"{venues[-1].uf_responsabilite}^SORTIE",
                    trigger_event="A03",
                    movement_type="Sortie",
                )
                session.add(mouvement)
            
            session.commit()
            
            # Affichage progrès
            if i % 50 == 0:
                print(f"  → {i}/{nb_patients} patients créés...")

        print(f"✓ Seed riche inséré ({nb_patients} patients)")


def seed_demo_scenarios() -> None:
    """Insère 3 patients avec scénarios de transferts / annulations."""
    with Session(engine) as session:
        _ensure_sequences(session)
        now = datetime.utcnow()
        scenario_defs = [
            ("SCENARIO-TRANSFERTS", ["A01", "A02", "A02", "A03"]),
            ("SCENARIO-ANNULATION", ["A01", "A11", "A01", "A02", "A03"]),
            ("SCENARIO-TRANSFERT-MULTI", ["A01", "A02", "A02", "A02", "A03"]),
        ]
        uf_codes = [uf.identifier for uf in session.exec(select(UniteFonctionnelle)).all()] or ["UF-DEMO-1", "UF-DEMO-2"]
        for scen_idx, (family_name, triggers) in enumerate(scenario_defs, start=1):
            patient = Patient(
                family=family_name,
                given="Demo",
                birth_date="1980-01-01",
                gender="other",
                city="DemoVille",
                postal_code="00000",
                country="FR",
                identity_reliability_code="VALI",
                identity_reliability_date="2024-03-01",
                identity_reliability_source="CNI",
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)
            dossier_seq = get_next_sequence(session, "dossier")
            uf_resp = choice(uf_codes)
            dossier = Dossier(
                dossier_seq=dossier_seq,
                patient_id=patient.id,
                uf_responsabilite=uf_resp,
                admit_time=now,
                dossier_type=DossierType.HOSPITALISE,
                reason="Scenario démo",
            )
            session.add(dossier)
            session.commit()
            session.refresh(dossier)
            venues = []
            for v in range(1, 3):
                venue_seq = get_next_sequence(session, "venue")
                venue = Venue(
                    venue_seq=venue_seq,
                    dossier_id=dossier.id,
                    uf_responsabilite=choice(uf_codes),
                    start_time=now,
                    code=f"SC-{scen_idx}-{v}",
                    label=f"Unité Scénario {v}",
                    operational_status="active",
                )
                session.add(venue)
                session.commit()
                session.refresh(venue)
                venues.append(venue)
            current_index = 0
            for step_idx, trig in enumerate(triggers, start=1):
                if trig == "A02":
                    current_index = 1 - current_index
                venue = venues[current_index]
                mouvement_seq = get_next_sequence(session, "mouvement")
                mouvement = Mouvement(
                    mouvement_seq=mouvement_seq,
                    venue_id=venue.id,
                    when=now,
                    location=f"{venue.uf_responsabilite}^BOX-{step_idx}^CH-{step_idx:02d}",
                    trigger_event=trig,
                    movement_type="Transfert" if trig == "A02" else ("Annulation" if trig == "A11" else "Admission/Sortie"),
                    from_location=venues[1 - current_index].uf_responsabilite if trig == "A02" else None,
                    to_location=venue.uf_responsabilite if trig == "A02" else None,
                )
                session.add(mouvement)
                session.commit()
        print("✓ Scénarios démo insérés")


def extract_hl7_messages(hl7_content: str) -> list:
    """Extrait le trigger event (ex: A01, A02) d'un message HL7"""
    lines = hl7_msg.split('\\r')
    for line in lines:
        if line.startswith('MSH|'):
            fields = line.split('|')
            if len(fields) >= 9:
                return fields[8]  # MSH-9: Message Type
    return "UNKNOWN"


def extract_hprim_xml(content: str) -> str:
    """
    Extrait le contenu XML HPRIM d'un fichier.
    Le XML commence par 'MSH|<?xml version' et se termine par la balise fermante.
    """
    # Trouver le début du XML
    xml_start = content.find('MSH|<?xml version')
    if xml_start == -1:
        return ""

    # Extraire à partir du début du XML
    xml_content = content[xml_start:]

    # Trouver la fin du XML (dernière balise fermante)
    # Chercher la dernière occurrence de </ qui indique une balise fermante
    last_closing_tag = xml_content.rfind('</')
    if last_closing_tag != -1:
        # Trouver la fin de cette balise
        end_pos = xml_content.find('>', last_closing_tag)
        if end_pos != -1:
            return xml_content[:end_pos + 1]

    return xml_content


def import_hl7_scenarios():
    """Importe les scénarios HL7 IHE PAM depuis les fichiers source"""
    from app.db import engine
    from app.models_scenarios import InteropScenario, InteropScenarioStep
    from sqlmodel import Session, select

    print("🔍 Recherche des fichiers HL7...")

    # Chemin vers les fichiers HL7
    hl7_dir = Path("Doc/interfaces.integration_src/interfaces.integration/src/main/resources/data/entrant/hl7")

    if not hl7_dir.exists():
        print(f"❌ Répertoire HL7 non trouvé: {hl7_dir}")
        return 0

    hl7_files = list(hl7_dir.glob("*.hl7"))
    print(f"📁 Trouvé {len(hl7_files)} fichiers HL7 dans {hl7_dir}")

    imported_count = 0

    with Session(engine) as session:
        for hl7_file in hl7_files:
            try:
                print(f"  📄 Traitement: {hl7_file.name}")

                # Lire le contenu du fichier
                with open(hl7_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Extraire les messages HL7
                messages = extract_hl7_messages(content)

                if not messages:
                    print(f"    ⚠️ Aucun message trouvé dans {hl7_file.name}")
                    continue

                # Créer le scénario
                scenario_name = f"IHE PAM - {hl7_file.stem.replace('_', ' ')}"
                scenario_key = f"ihe_pam_{hl7_file.stem.lower()}"

                # Vérifier si le scénario existe déjà
                existing = session.exec(
                    select(InteropScenario).where(InteropScenario.key == scenario_key)
                ).first()

                if existing:
                    print(f"    ⏭️ Scénario déjà existant: {scenario_name}")
                    continue

                # Créer le scénario
                scenario = InteropScenario(
                    name=scenario_name,
                    key=scenario_key,
                    category="IHE_PAM",
                    description=f"Scénario IHE PAM importé depuis {hl7_file.name}",
                    is_active=True
                )
                session.add(scenario)
                session.flush()  # Pour obtenir l'ID

                # Ajouter les étapes
                for i, message in enumerate(messages, 1):
                    trigger = extract_trigger_from_message(message)

                    step = InteropScenarioStep(
                        scenario_id=scenario.id,
                        order_index=i,
                        name=f"Message HL7 {trigger}",
                        message_format="hl7",
                        payload=message,
                        description=f"Étape {i}: Message HL7 {trigger}"
                    )
                    session.add(step)

                session.commit()
                imported_count += 1
                print(f"    ✅ Créé: {scenario_name} ({len(messages)} messages)")

            except Exception as e:
                print(f"    ❌ Erreur traitement {hl7_file.name}: {e}")
                session.rollback()
                continue

    return imported_count


def import_hprim_scenarios():
    """Importe les scénarios HPRIM depuis les fichiers source"""
    from app.db import engine
    from app.models_scenarios import InteropScenario, InteropScenarioStep
    from sqlmodel import Session, select

    print("🔍 Recherche des fichiers HPRIM...")

    # Chemin vers les fichiers HPRIM
    hprim_dir = Path("Doc/interfaces.integration_src/interfaces.integration/src/main/resources/data/entrant/hprimxml")

    if not hprim_dir.exists():
        print(f"❌ Répertoire HPRIM non trouvé: {hprim_dir}")
        return 0

    hprim_files = list(hprim_dir.glob("*.txt"))
    print(f"📁 Trouvé {len(hprim_files)} fichiers HPRIM dans {hprim_dir}")

    imported_count = 0

    with Session(engine) as session:
        for hprim_file in hprim_files:
            try:
                print(f"  📄 Traitement: {hprim_file.name}")

                # Lire le contenu du fichier
                with open(hprim_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Extraire les messages HL7 et XML HPRIM
                hl7_messages = []
                hprim_xml = ""

                # Séparer HL7 et HPRIM
                lines = content.split('\n')
                current_hl7 = []
                in_xml = False

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith('MSH|<?xml'):
                        # Début du XML HPRIM
                        if current_hl7:
                            hl7_messages.append('\r'.join(current_hl7))
                            current_hl7 = []
                        in_xml = True
                        hprim_xml = line
                    elif in_xml:
                        hprim_xml += '\n' + line
                    elif line.startswith('MSH'):
                        # Nouveau message HL7
                        if current_hl7:
                            hl7_messages.append('\r'.join(current_hl7))
                        current_hl7 = [line]
                    else:
                        if current_hl7:
                            current_hl7.append(line)

                # Ajouter le dernier message HL7
                if current_hl7:
                    hl7_messages.append('\r'.join(current_hl7))

                if not hl7_messages and not hprim_xml:
                    print(f"    ⚠️ Aucun contenu trouvé dans {hprim_file.name}")
                    continue

                # Créer le scénario
                scenario_name = f"HPRIM - {hprim_file.stem.replace('_', ' ')}"
                scenario_key = f"hprim_{hprim_file.stem.lower()}"

                # Vérifier si le scénario existe déjà
                existing = session.exec(
                    select(InteropScenario).where(InteropScenario.key == scenario_key)
                ).first()

                if existing:
                    print(f"    ⏭️ Scénario déjà existant: {scenario_name}")
                    continue

                # Créer le scénario
                scenario = InteropScenario(
                    name=scenario_name,
                    key=scenario_key,
                    category="HPRIM_COTATION",
                    description=f"Scénario HPRIM importé depuis {hprim_file.name}",
                    is_active=True
                )
                session.add(scenario)
                session.flush()  # Pour obtenir l'ID

                # Ajouter les étapes HL7
                step_number = 1
                for message in hl7_messages:
                    trigger = extract_trigger_from_message(message)

                    step = InteropScenarioStep(
                        scenario_id=scenario.id,
                        order_index=step_number,
                        name=f"Message HL7 {trigger}",
                        message_format="hl7",
                        payload=message,
                        description=f"Étape {step_number}: Message HL7 {trigger}"
                    )
                    session.add(step)
                    step_number += 1

                # Ajouter l'étape HPRIM si présente
                if hprim_xml:
                    step = InteropScenarioStep(
                        scenario_id=scenario.id,
                        order_index=step_number,
                        name="Message HPRIM XML",
                        message_format="hprim",
                        payload=hprim_xml,
                        description=f"Étape {step_number}: Acte HPRIM XML"
                    )
                    session.add(step)

                session.commit()
                imported_count += 1
                total_steps = len(hl7_messages) + (1 if hprim_xml else 0)
                print(f"    ✅ Créé: {scenario_name} ({total_steps} étapes)")

            except Exception as e:
                print(f"    ❌ Erreur traitement {hprim_file.name}: {e}")
                session.rollback()
                continue

    return imported_count


def seed_cotations_to_dossiers(engine) -> int:
    """Ajoute des cotations réalistes à certains dossiers existants.
    
    Crée des patients/dossiers avec des cotations variées:
    - CCAM: interventions chirurgicales
    - NGAP: actes paramédicaux
    - UCD: médicaments
    - LPP: dispositifs médicaux
    """
    from sqlmodel import Session
    from datetime import datetime, timedelta
    from app.models import Patient, Dossier, DossierType, CCAMAct, NGAPAct, UCDAct, LPPAct
    
    total_cotations = 0
    
    with Session(engine) as session:
        # Créer quelques patients et dossiers avec cotations variées
        patients_data = [
            {"family": "Cotation", "given": "CCAM", "dob": datetime(1965, 5, 10).date(), "type": "CCAM"},
            {"family": "Cotation", "given": "NGAP", "dob": datetime(1972, 8, 23).date(), "type": "NGAP"},
            {"family": "Cotation", "given": "Mixed", "dob": datetime(1978, 12, 5).date(), "type": "MIXED"},
            {"family": "Cotation", "given": "UCD", "dob": datetime(1955, 3, 17).date(), "type": "UCD"},
            {"family": "Cotation", "given": "LPP", "dob": datetime(1990, 7, 22).date(), "type": "LPP"},
        ]
        
        for patient_data in patients_data:
            # Vérifier si le patient existe déjà
            existing_patient = session.exec(
                select(Patient).where(Patient.family == patient_data["family"]).where(Patient.given == patient_data["given"])
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
                session.flush()
            
            # Créer un dossier
            admit_time = datetime.now() - timedelta(days=2)
            dossier = Dossier(
                patient_id=patient.id,
                admit_time=admit_time,
                dossier_type=DossierType.HOSPITALISE
            )
            session.add(dossier)
            session.flush()
            
            # Ajouter des cotations selon le type
            cotation_type = patient_data["type"]
            if cotation_type == "CCAM":
                ccam_actes = [
                    {"code_acte": "HBMD001", "code_activite": "01", "montant": 120.0},
                    {"code_acte": "LFDA011", "code_activite": "04", "montant": 85.50},
                    {"code_acte": "NZCB001", "code_activite": "02", "montant": 95.0},
                ]
                for i, acte_data in enumerate(ccam_actes):
                    act = CCAMAct(
                        dossier_id=dossier.id,
                        code_acte=acte_data["code_acte"],
                        code_activite=acte_data["code_activite"],
                        execute_date=admit_time + timedelta(days=1, hours=i*2),
                        montant_total=acte_data["montant"],
                        facture="non"
                    )
                    session.add(act)
                    total_cotations += 1
                dossier.has_cotations = True
                dossier.cotations_count = len(ccam_actes)
                
            elif cotation_type == "NGAP":
                ngap_actes = [
                    {"lettre_cle": "A", "coefficient": 1.0, "montant": 25.00},
                    {"lettre_cle": "B", "coefficient": 1.5, "montant": 37.50},
                    {"lettre_cle": "C", "coefficient": 2.0, "montant": 50.00},
                    {"lettre_cle": "AMI", "coefficient": 2.5, "montant": 62.50},
                ]
                for i, acte_data in enumerate(ngap_actes):
                    act = NGAPAct(
                        dossier_id=dossier.id,
                        lettre_cle=acte_data["lettre_cle"],
                        coefficient=acte_data["coefficient"],
                        execute_date=admit_time + timedelta(days=1, hours=i),
                        montant_total=acte_data["montant"],
                        denombrement=1,
                        facture="non"
                    )
                    session.add(act)
                    total_cotations += 1
                dossier.has_cotations = True
                dossier.cotations_count = len(ngap_actes)
                
            elif cotation_type == "UCD":
                ucd_actes = [
                    {"code_cip": "3400936050501", "designation": "DOLIPRANE 1000MG", "quantite": 2, "prix": 4.50},
                    {"code_cip": "3400893448177", "designation": "IBUPROFEN 400MG", "quantite": 1, "prix": 3.25},
                ]
                for i, acte_data in enumerate(ucd_actes):
                    act = UCDAct(
                        dossier_id=dossier.id,
                        code_ucd=acte_data["code_cip"],
                        denomination_libelle=acte_data["designation"],
                        quantite=acte_data["quantite"],
                        montant_unitaire_facture_ttc=acte_data["prix"],
                        execute_date=admit_time + timedelta(days=1, hours=i)
                    )
                    session.add(act)
                    total_cotations += 1
                dossier.has_cotations = True
                dossier.cotations_count = len(ucd_actes)
                
            elif cotation_type == "LPP":
                lpp_actes = [
                    {"code_lpp": "1234567890123", "libelle": "Pansement adhésif", "montant": 25.00},
                    {"code_lpp": "9876543210987", "libelle": "Orthèse de genou", "montant": 150.00},
                ]
                for i, acte_data in enumerate(lpp_actes):
                    act = LPPAct(
                        dossier_id=dossier.id,
                        code_lpp=acte_data["code_lpp"],
                        denomination_libelle=acte_data["libelle"],
                        quantite=1,
                        montant_unitaire_facture_ttc=acte_data["montant"],
                        execute_date=admit_time + timedelta(days=1, hours=i)
                    )
                    session.add(act)
                    total_cotations += 1
                dossier.has_cotations = True
                dossier.cotations_count = len(lpp_actes)
                
            elif cotation_type == "MIXED":
                # Ajouter 1 CCAM
                act = CCAMAct(
                    dossier_id=dossier.id,
                    code_acte="HBMD001",
                    code_activite="01",
                    execute_date=admit_time + timedelta(days=1),
                    montant_total=120.0,
                    facture="non"
                )
                session.add(act)
                total_cotations += 1
                
                # Ajouter 1 NGAP
                act = NGAPAct(
                    dossier_id=dossier.id,
                    lettre_cle="B",
                    coefficient=1.5,
                    execute_date=admit_time + timedelta(days=1, hours=2),
                    montant_total=37.50,
                    denombrement=1,
                    facture="non"
                )
                session.add(act)
                total_cotations += 1
                
                # Ajouter 1 UCD
                act = UCDAct(
                    dossier_id=dossier.id,
                    code_ucd="3400936050501",
                    denomination_libelle="DOLIPRANE 1000MG",
                    quantite=2,
                    montant_unitaire_facture_ttc=4.50,
                    execute_date=admit_time + timedelta(days=1, hours=3)
                )
                session.add(act)
                total_cotations += 1
                
                # Ajouter 1 LPP
                act = LPPAct(
                    dossier_id=dossier.id,
                    code_lpp="1234567890123",
                    denomination_libelle="Pansement adhésif",
                    quantite=1,
                    montant_unitaire_facture_ttc=25.00,
                    execute_date=admit_time + timedelta(days=1, hours=4)
                )
                session.add(act)
                total_cotations += 1
                
                dossier.has_cotations = True
                dossier.cotations_count = 4
        
        session.commit()
    
    return total_cotations


def main():
    parser = argparse.ArgumentParser(
        description="Initialisation complète de la base de données (mode FULL par défaut)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Par défaut, lance une initialisation COMPLÈTE :
  • Structure + vocabulaires + endpoints + namespaces
  • 120 patients + dossiers + mouvements (seed standard)
  • Tous les scénarios HL7/HPRIM/IHE PAM (~400 scénarios)
  • Cotations médicales réalistes

Utilisez les options ci-dessous uniquement pour personnaliser.
        """
    )
    parser.add_argument("--reset", action="store_true", 
                       help="Supprime data/medbridge.db avant init")
    
    # Options pour réduire le seed (par défaut = FULL)
    parser.add_argument("--skip-vocab", action="store_true", 
                       help="Saute l'initialisation des vocabulaires")
    parser.add_argument("--skip-population", action="store_true", 
                       help="Saute le seed de population patients")
    parser.add_argument("--skip-scenarios", action="store_true", 
                       help="Saute l'import des scénarios HL7/HPRIM")
    parser.add_argument("--minimal", action="store_true", 
                       help="Seed minimal : 1 seul patient (au lieu de 120)")
    
    args = parser.parse_args()
    
    # PAR DÉFAUT : mode FULL (rich + cotations + demo-scenarios)
    if not args.minimal:
        args.rich = True
        args.with_cotations = True
        args.demo_scenarios = True
    else:
        args.rich = False
        args.with_cotations = False
        args.demo_scenarios = False

    if args.reset and DB_PATH.exists():
        print("→ Suppression de medbridge.db existante...")
        DB_PATH.unlink()
        print("✓ Base supprimée\n")

    # 1. Schéma (tables)
    print("=" * 60)
    print("ÉTAPE 1/4 : Création du schéma (tables)")
    print("=" * 60)
    try:
        from app.db import engine
        from app import models  # Importe tous les modèles pour SQLModel.metadata
        from app import models_scenarios
        from app import models_workflows
        from app import models_shared
        from app import models_structure
        from sqlmodel import SQLModel

        # Créer les tables manuellement sans déclencher l'import automatique des templates
        SQLModel.metadata.create_all(engine)

        # Activer WAL pour SQLite
        import sqlite3
        conn = sqlite3.connect("medbridge.db")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.close()

        print("✓ Tables créées\n")
    except Exception as e:
        print(f"✗ Échec création tables: {e}")
        sys.exit(1)

    # 2. Vocabulaires
    if not args.skip_vocab:
        print("=" * 60)
        print("ÉTAPE 2/4 : Initialisation des vocabulaires")
        print("=" * 60)
        try:
            from app.vocabulary_init import init_vocabularies
            with Session(engine) as session:
                init_vocabularies(session)
            print("✓ Vocabulaires initialisés (35 systèmes, 207 valeurs)\n")
        except Exception as e:
            print(f"✗ Échec vocabulaires: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print("→ Vocabulaires sautés (--skip-vocab)\n")

    # 3. Structure étendue + endpoints + namespaces
    print("=" * 60)
    print("ÉTAPE 3/4 : Structure multi-EJ + endpoints + namespaces")
    print("=" * 60)
    try:
        run([sys.executable, "scripts/tools/init_extended_demo.py"], check=True)
        print("✓ Structure, endpoints et namespaces créés\n")
    except (CalledProcessError, FileNotFoundError) as e:
        print(f"✗ Échec structure étendue: {e}")
        sys.exit(1)

    # 4. Population (options flexibles)
    if args.skip_population:
        print("→ Population patients sautée (--skip-population)\n")
    else:
        print("=" * 60)
        print("ÉTAPE 4/7 : Population de patients")
        print("=" * 60)

        if args.minimal:
            print("→ Seed minimal (1 patient)...")
            seed_minimal()
        elif args.rich:
            print("→ Seed riche (200 patients avec cotations)...")
            seed_rich(200)
            
            # Ajouter cotations à 70% des dossiers
            print("→ Ajout cotations réalistes (70% de couverture)...")
            _add_cotations_to_existing_dossiers()
        else:
            # Seed standard (120 patients)
            print("→ Seed standard (120 patients)...")
            seed_rich(120)  # Crée 120 patients avec cotations intégrées (25%)

        if args.demo_scenarios:
            print("→ Ajout scénarios démo...")
            seed_demo_scenarios()

        print("✓ Population configurée\n")


    # 5. Import scénarios IHE HL7 (partie intégrante du programme)
    if not args.skip_scenarios:
        print("=" * 60)
        print("ÉTAPE 5/8 : Import des scénarios IHE HL7")
        print("=" * 60)
        try:
            hl7_count = import_hl7_scenarios()
            print(f"✓ {hl7_count} scénarios IHE HL7 importés\n")
        except Exception as e:
            print(f"✗ Échec import scénarios IHE HL7: {e}")
            sys.exit(1)
    else:
        print("→ Scénarios IHE HL7 sautés (--skip-scenarios)\n")
        hl7_count = 0

    # 6. Import scénarios d'intégration HL7/HPRIM (partie intégrante du programme)
    if not args.skip_scenarios:
        print("=" * 60)
        print("ÉTAPE 6/8 : Import des scénarios d'intégration HL7/HPRIM")
        print("=" * 60)
        try:
            hprim_count = import_hprim_scenarios()
            print(f"✓ {hprim_count} scénarios HPRIM importés\n")
        except Exception as e:
            print(f"✗ Échec import scénarios HPRIM: {e}")
            sys.exit(1)
    else:
        print("→ Scénarios HPRIM sautés (--skip-scenarios)\n")
        hprim_count = 0

    # 7. Scénarios HL7 IHE PAM (partie intégrante du programme)
    if not args.skip_scenarios:
        print("=" * 60)
        print("ÉTAPE 7/8 : Import des scénarios HL7 IHE PAM (124 scénarios)")
        print("=" * 60)
        try:
            # Import du script seed_hl7_scenarios.py
            sys.path.insert(0, str(Path(__file__).parent.parent / "manual"))
            from seed_hl7_scenarios import seed_hl7_scenarios
            seed_hl7_scenarios()
            print("✓ 124 scénarios HL7 IHE PAM importés\n")
            pam_count = 124
        except Exception as e:
            print(f"✗ Échec import scénarios HL7 PAM: {e}")
            sys.exit(1)
            pam_count = 0
    else:
        print("→ Scénarios HL7 PAM sautés (--skip-scenarios)\n")
        pam_count = 0

    # 8. Cotations médicales (déjà ajoutées dans seed_rich si args.rich)
    if args.with_cotations and not args.rich:
        print("=" * 60)
        print("ÉTAPE 8/8 : Ajout des cotations médicales réalistes")
        print("=" * 60)
        try:
            from datetime import timedelta
            from app.models import CCAMAct, NGAPAct, UCDAct, LPPAct
            
            _add_cotations_to_existing_dossiers()
            print("✓ Cotations ajoutées aux dossiers\n")
        except Exception as e:
            print(f"✗ Échec ajout cotations: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        if args.rich:
            print("→ Cotations déjà ajoutées dans seed_rich\n")

    # Résumé final
    print("=" * 60)
    print("✅ INITIALISATION COMPLÈTE TERMINÉE")
    print("=" * 60)
    print("\nRésumé:")
    print("  • Tables       : créées")
    if not args.skip_vocab:
        print("  • Vocabulaires : 35 systèmes, 207 valeurs")
    print("  • Structures   : 4 EJ (CHU, hôpital, EHPAD, psy) + hiérarchie")
    print("  • Endpoints    : 12 (MLLP + FHIR par EJ)")
    print("  • Namespaces   : 13 (IPP/NDA/VENUE par EJ + global)")
    if not args.skip_population:
        if args.minimal:
            print("  • Population   : 1 patient (seed minimal)")
        elif args.rich:
            print("  • Population   : 200 patients avec parcours réalistes")
            print("  • Cotations    : 70% de couverture (140+ dossiers avec cotations)")
        else:
            print("  • Population   : 120 patients, dossiers et mouvements (standard)")
        if args.demo_scenarios:
            print("  • Scénarios démo : 3 scénarios complexes (transferts/annulations)")
    if not args.skip_scenarios:
        print(f"  • Scénarios IHE HL7 : {hl7_count} scénarios importés")
        print(f"  • Scénarios HPRIM : {hprim_count} scénarios importés")
        print(f"  • Scénarios HL7 PAM : {pam_count} scénarios IHE PAM importés")
        print(f"  • Total scénarios : {hl7_count + hprim_count + pam_count} scénarios d'intégration")
    else:
        print("  • Scénarios    : sautés (--skip-scenarios)")
    print("\nLe serveur peut être démarré avec:")
    print("  uvicorn app.app:app --reload")
    print("\nAccès admin: http://localhost:8000/admin/ght/1/ej/1")


if __name__ == "__main__":
    main()
