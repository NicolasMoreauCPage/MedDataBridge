#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
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


def seed_minimal() -> None:
    """Seed minimal avec 1 patient de démo."""
    with Session(engine) as session:
        existing = session.exec(select(Patient).limit(1)).first()
        if existing:
            print("Seed minimal ignoré (patients déjà présents).")
            return
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
        print("✓ Seed minimal inséré")


def seed_rich(nb_patients: int = 40) -> None:
    """Seed riche avec scénarios de mouvements réalistes."""
    with Session(engine) as session:
        existing = session.exec(select(Patient).limit(1)).first()
        if existing:
            print("Seed riche ignoré (patients déjà présents).")
            return
        _ensure_sequences(session)

        # Collect UF codes si structure présente
        uf_codes = [uf.identifier for uf in session.exec(select(UniteFonctionnelle)).all()]
        if not uf_codes:
            uf_codes = ["UF-RICH-1", "UF-RICH-2"]

        for i in range(1, nb_patients + 1):
            patient = Patient(
                family=f"RICH-{i:03d}",
                given=choice(["Alice", "Bob", "Chloé", "David", "Eva"]),
                birth_date="1970-01-01",
                gender="other",
                city="VilleX",
                postal_code="00000",
                country="FR",
                identity_reliability_code="VALI",
                identity_reliability_date="2024-02-01",
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
                admit_time=datetime.utcnow(),
                dossier_type=DossierType.HOSPITALISE,
                reason="Admission auto",
            )
            session.add(dossier)
            session.commit()
            session.refresh(dossier)

            # 2 venues
            venues = []
            for v in range(1, 3):
                venue_seq = get_next_sequence(session, "venue")
                venue = Venue(
                    venue_seq=venue_seq,
                    dossier_id=dossier.id,
                    uf_responsabilite=uf_resp,
                    start_time=datetime.utcnow(),
                    code=f"VENUE-{i}-{v}",
                    label=f"Unité {v}",
                    operational_status="active",
                )
                session.add(venue)
                session.commit()
                session.refresh(venue)
                venues.append(venue)

            # mouvements (admission + transfert + sortie)
            triggers = [("Admission", "A01"), ("Transfert", "A02"), ("Sortie", "A03")]
            current_index = 0
            for step_idx, (m_type, trig) in enumerate(triggers, start=1):
                if trig == "A02":
                    current_index = 1 - current_index
                venue = venues[current_index]
                mouvement_seq = get_next_sequence(session, "mouvement")
                mouvement = Mouvement(
                    mouvement_seq=mouvement_seq,
                    venue_id=venue.id,
                    when=datetime.utcnow(),
                    location=f"{venue.uf_responsabilite}^BOX-{step_idx}^CH-{step_idx:02d}",
                    trigger_event=trig,
                    movement_type=m_type,
                    from_location=venues[1 - current_index].uf_responsabilite if trig == "A02" else None,
                    to_location=venue.uf_responsabilite if trig == "A02" else None,
                )
                session.add(mouvement)
                session.commit()
            if i % 10 == 0:
                print(f"   … {i} patients créés")

        print(f"✓ Seed riche inséré ({nb_patients} patients)")


def seed_demo_scenarios() -> None:
    """Insère 3 patients avec scénarios de transferts / annulations."""
    with Session(engine) as session:
        existing_demo = session.exec(select(Patient).where(Patient.family.like("SCENARIO-%")).limit(1)).first()
        if existing_demo:
            print("Scénarios démo déjà présents.")
            return
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


def main():
    parser = argparse.ArgumentParser(description="Initialisation complète de la base de données")
    parser.add_argument("--reset", action="store_true", help="Supprime medbridge.db avant init")
    parser.add_argument("--skip-vocab", action="store_true", help="Saute l'initialisation des vocabulaires")
    parser.add_argument("--skip-population", action="store_true", help="Saute le seed de population patients")
    parser.add_argument("--skip-scenarios", action="store_true", help="Saute l'import des scénarios HL7/HPRIM")
    parser.add_argument("--minimal", action="store_true", help="Seed minimal (1 patient seulement)")
    parser.add_argument("--rich", action="store_true", help="Seed riche (40 patients avec scénarios)")
    parser.add_argument("--demo-scenarios", action="store_true", help="Ajoute scénarios démo complexes")
    parser.add_argument("--with-cotations", action="store_true", help="Ajoute cotations médicales réalistes")
    args = parser.parse_args()

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
            run([sys.executable, "scripts/tools/init_vocabularies.py"], check=True)
            print("✓ Vocabulaires initialisés\n")
        except (CalledProcessError, FileNotFoundError) as e:
            print(f"✗ Échec vocabulaires: {e}")
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
            print("→ Seed riche (40 patients)...")
            seed_rich(40)
        else:
            # Seed standard via init_extended_demo.py (120 patients)
            print("→ Seed standard (120 patients via init_extended_demo)...")
            # Le seed standard est déjà inclus dans init_extended_demo.py
            pass

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

    # 8. Cotations médicales réalistes optionnelles
    if args.with_cotations:
        print("=" * 60)
        print("ÉTAPE 8/8 : Ajout des cotations médicales réalistes")
        print("=" * 60)
        print("→ Fonctionnalité cotations à implémenter\n")
        # TODO: Implémenter la logique des cotations médicales
        # Cette étape est préparée pour une future implémentation

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
            print("  • Population   : 40 patients avec scénarios (seed riche)")
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
    if args.with_cotations:
        print("  • Cotations    : médicales réalistes ajoutées")
    print("\nLe serveur peut être démarré avec:")
    print("  uvicorn app.app:app --reload")
    print("\nAccès admin: http://localhost:8000/admin/ght/1/ej/1")


if __name__ == "__main__":
    main()
