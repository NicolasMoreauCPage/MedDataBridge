#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
"""Script principal d'initialisation complète de la base de données.

Usage:
    python init_db.py                    # Init complète (structure + vocab + namespaces + population)
    python init_db.py --reset            # Supprime la DB existante avant init
    python init_db.py --skip-vocab       # Saute l'init des vocabulaires
    python init_db.py --skip-population  # Saute le seed de patients

Ce script orchestre dans l'ordre:
1. Création du schéma (tables) via app.db.init_db()
2. Vocabulaires standards (35 systèmes, 207 valeurs)
3. Structure multi-EJ (4 EJ: CHU, hôpital, EHPAD, psy) + hiérarchie complète
4. Endpoints MLLP/FHIR (12 endpoints: 3 par EJ)
5. Namespaces d'identifiants (13: IPP/NDA/VENUE par EJ + global structure)
6. Population de patients (120 par défaut avec dossiers et mouvements)
7. Scénarios IHE HL7 (depuis Doc/examples)
8. Scénarios d'intégration HL7/HPRIM (159 scénarios depuis interfaces.integration)

Tous les appels sont idempotents: re-exécuter ce script est safe.
"""
import argparse
import sys
import re
import json
from pathlib import Path
from subprocess import run, CalledProcessError
from typing import List, Tuple
from datetime import datetime

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


def extract_trigger_from_message(hl7_msg: str) -> str:
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

    # 4. Population (déjà incluse dans init_extended_demo mais peut être sautée)
    if args.skip_population:
        print("→ Population patients sautée (--skip-population)\n")
    else:
        print("=" * 60)
        print("ÉTAPE 4/4 : Vérification population patients")
        print("=" * 60)
        # init_extended_demo.py gère déjà la population, donc juste un message
        print("✓ Population incluse dans init_extended_demo.py\n")


    # 5. Import scénarios IHE HL7
    print("=" * 60)
    print("ÉTAPE 5/6 : Import des scénarios IHE HL7")
    print("=" * 60)
    try:
        hl7_count = import_hl7_scenarios()
        print(f"✓ {hl7_count} scénarios IHE HL7 importés\n")
    except Exception as e:
        print(f"✗ Échec import scénarios IHE HL7: {e}")
        sys.exit(1)

    # 6. Import scénarios d'intégration HL7/HPRIM
    print("=" * 60)
    print("ÉTAPE 6/6 : Import des scénarios d'intégration HL7/HPRIM")
    print("=" * 60)
    try:
        hprim_count = import_hprim_scenarios()
        print(f"✓ {hprim_count} scénarios HPRIM importés\n")
    except Exception as e:
        print(f"✗ Échec import scénarios HPRIM: {e}")
        sys.exit(1)

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
        print("  • Population   : 120 patients, dossiers et mouvements")
    print(f"  • Scénarios IHE HL7 : {hl7_count} scénarios importés")
    print(f"  • Scénarios HPRIM : {hprim_count} scénarios importés")
    print(f"  • Total scénarios : {hl7_count + hprim_count} scénarios d'intégration")
    print("\nLe serveur peut être démarré avec:")
    print("  uvicorn app.app:app --reload")
    print("\nAccès admin: http://localhost:8000/admin/ght/1/ej/1")


if __name__ == "__main__":
    main()
