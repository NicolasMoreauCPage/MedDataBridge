"""
Import des scénarios HPRIM depuis les fichiers de test du projet interfaces.integration
Ces scénarios contiennent un contexte HL7 (identité/mouvements) suivi d'actes HPRIM
"""

import os
import re
from pathlib import Path
from typing import List, Tuple
from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select
from datetime import datetime


def extract_hl7_messages(content: str) -> List[str]:
    """
    Extrait les messages HL7 individuels d'un fichier HPRIM.
    Les messages sont séparés par des newlines.
    """
    # Normaliser les séparateurs
    content = content.replace('\r\n', '\n')

    messages = []
    current_msg = []

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Si la ligne commence par MSH et qu'on a déjà un message en cours,
        # c'est un nouveau message (sauf si c'est du XML HPRIM)
        if line.startswith('MSH') and current_msg and not line.startswith('MSH|<?xml'):
            messages.append('\r'.join(current_msg))
            current_msg = [line]
        else:
            current_msg.append(line)

    # Ajouter le dernier message
    if current_msg:
        messages.append('\r'.join(current_msg))

    return messages


def extract_hprim_xml(content: str) -> str:
    """
    Extrait le contenu XML HPRIM d'un fichier.
    Le XML commence par 'MSH|<?xml version' et se termine par la balise fermante.
    """
    # Trouver le début du XML HPRIM
    xml_start = content.find('MSH|<?xml version')
    if xml_start == -1:
        return ""

    # Extraire à partir du MSH XML
    xml_content = content[xml_start:]

    # Le XML se termine généralement par </evenementsServeurActes>
    # ou une balise fermante similaire
    end_patterns = ['</evenementsServeurActes>', '</evenementsServeurActes>', '</acquittement>']

    for pattern in end_patterns:
        end_pos = xml_content.find(pattern)
        if end_pos != -1:
            # Inclure la balise fermante
            return xml_content[:end_pos + len(pattern)]

    # Si pas de pattern trouvé, retourner tout le reste
    return xml_content


def extract_trigger_from_message(message: str) -> str:
    """Extrait le trigger event d'un message HL7"""
    lines = message.split('\r')
    for line in lines:
        if line.startswith('MSH|'):
            fields = line.split('|')
            if len(fields) > 8:
                trigger_part = fields[8]  # ex: ADT^A01
                if '^' in trigger_part:
                    return trigger_part.split('^')[1]  # A01
                return trigger_part
    return 'UNKNOWN'


def get_hprim_message_type(xml_content: str) -> str:
    """Détermine le type de message HPRIM depuis le XML"""
    if '<evenementsServeurActes' in xml_content:
        return 'HPRIM_ACTES'
    elif '<acquittement' in xml_content:
        return 'HPRIM_ACQUITTEMENT'
    else:
        return 'HPRIM_UNKNOWN'


def get_scenario_name_from_path(file_path: str) -> str:
    """Génère un nom lisible depuis le chemin du fichier HPRIM"""
    basename = os.path.basename(file_path)
    # Supprimer l'extension .txt
    name = basename.replace('.txt', '')
    # Remplacer les underscores par des espaces
    name = name.replace('_', ' ')
    # Capitaliser
    name = name.title()
    return f"HPRIM - {name}"


def parse_hprim_scenario_file(file_path: str) -> Tuple[List[str], str]:
    """
    Parse un fichier de scénario HPRIM et retourne:
    - Liste des messages HL7
    - Contenu XML HPRIM
    """
    with open(file_path, 'r', encoding='iso-8859-1') as f:
        content = f.read()

    hl7_messages = extract_hl7_messages(content)
    hprim_xml = extract_hprim_xml(content)

    return hl7_messages, hprim_xml


def import_hprim_scenarios():
    """Importe tous les fichiers HPRIM comme scénarios"""

    # Répertoire source des fichiers HPRIM
    base_path = Path('/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/docs/interfaces.integration_src/interfaces.integration/src/main/resources/data/entrant/hprimxml')

    # Chercher tous les fichiers .txt HPRIM
    hprim_files = list(base_path.glob('**/*.txt'))
    print(f"🔍 Trouvé {len(hprim_files)} fichiers HPRIM")

    with Session(engine) as session:
        imported_count = 0

        for hprim_file in hprim_files:
            try:
                # Générer la clé unique du scénario
                scenario_key = f"hprim_{hprim_file.name}"
                scenario_name = get_scenario_name_from_path(str(hprim_file))

                # Vérifier si le scénario existe déjà
                existing = session.exec(
                    select(InteropScenario).where(InteropScenario.key == scenario_key)
                ).first()

                if existing:
                    print(f"  ✓ {scenario_name}: déjà existant")
                    continue

                # Parser le fichier
                hl7_messages, hprim_xml = parse_hprim_scenario_file(str(hprim_file))

                if not hl7_messages and not hprim_xml:
                    print(f"  ⚠ {scenario_name}: aucun contenu trouvé")
                    continue

                # Créer le scénario
                scenario = InteropScenario(
                    key=scenario_key,
                    name=scenario_name,
                    description=f"Scénario HPRIM importé depuis {hprim_file.name}",
                    category="HPRIM_COTATION",
                    protocol="MIXED",  # HL7 + HPRIM XML
                    source_path=str(hprim_file),
                    tags="hprim,cotation,actes"
                )

                session.add(scenario)
                session.flush()  # Pour obtenir l'ID

                step_order = 0

                # Ajouter les étapes HL7
                for hl7_msg in hl7_messages:
                    if hl7_msg.strip():
                        trigger = extract_trigger_from_message(hl7_msg)

                        step = InteropScenarioStep(
                            scenario_id=scenario.id,
                            order_index=step_order,
                            name=f"HL7 {trigger}",
                            description=f"Message HL7 {trigger} - Contexte identité/mouvements",
                            message_format="hl7",
                            message_type=f"ADT^{trigger}",
                            payload=hl7_msg.strip()
                        )

                        session.add(step)
                        step_order += 1

                # Ajouter l'étape HPRIM XML
                if hprim_xml.strip():
                    msg_type = get_hprim_message_type(hprim_xml)

                    step = InteropScenarioStep(
                        scenario_id=scenario.id,
                        order_index=step_order,
                        name=f"HPRIM {msg_type}",
                        description="Message HPRIM XML - Cotation d'actes",
                        message_format="xml",
                        message_type=msg_type,
                        payload=hprim_xml.strip()
                    )

                    session.add(step)
                    step_order += 1

                session.commit()
                imported_count += 1
                print(f"  ✓ Créé: {scenario_name} ({len(hl7_messages)} HL7 + 1 HPRIM)")

            except Exception as e:
                print(f"  ❌ Erreur avec {hprim_file.name}: {e}")
                session.rollback()
                continue

        print(f"\n🎉 Import terminé: {imported_count} scénarios HPRIM créés")


if __name__ == "__main__":
    import_hprim_scenarios()