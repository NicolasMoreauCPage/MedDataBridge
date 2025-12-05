#!/usr/bin/env python3
"""
Seed des scénarios IHE PAM depuis les fichiers HL7 de interfaces.integration
À intégrer dans le processus d'initialisation de la base de données
"""

import os
from pathlib import Path
from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select
from datetime import datetime


def extract_hl7_messages(hl7_content: str) -> list:
    """Extrait les messages HL7 individuels d'un fichier"""
    content = hl7_content.replace('\r\n', '\n')
    
    messages = []
    current_msg = []
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('MSH') and current_msg:
            messages.append('\\r'.join(current_msg))
            current_msg = [line]
        else:
            current_msg.append(line)
    
    if current_msg:
        messages.append('\\r'.join(current_msg))
    
    return messages


def extract_trigger_from_message(hl7_msg: str) -> str:
    """Extrait le trigger event (ex: A01, A02) d'un message HL7"""
    lines = hl7_msg.split('\\r')
    for line in lines:
        if line.startswith('MSH|'):
            fields = line.split('|')
            if len(fields) > 8:
                trigger_part = fields[8]
                if '^' in trigger_part:
                    return trigger_part.split('^')[1]
                return trigger_part
    return 'UNKNOWN'


def get_scenario_name_from_path(file_path: str) -> str:
    """Génère un nom lisible depuis le chemin du fichier"""
    basename = os.path.basename(file_path)
    name = basename.replace('.hl7', '')
    name = name.replace('_', ' ')
    name = name.replace('TestHL7', '').strip()
    name = name.title()
    return f"IHE PAM - {name}"


def seed_hl7_scenarios():
    """Importe tous les fichiers HL7 comme scénarios dans la base"""
    
    base_path = Path('/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/Doc/interfaces.integration_src/interfaces.integration/target/classes/data')
    
    if not base_path.exists():
        print(f'Répertoire de scénarios introuvable: {base_path}')
        print('Seed IHE PAM ignoré - les fichiers HL7 de test ne sont pas disponibles')
        return
    
    hl7_files = list(base_path.glob('**/*.hl7'))
    if not hl7_files:
        print('Aucun fichier HL7 trouvé')
        return
    
    print(f'\nImportation de {len(hl7_files)} scénarios IHE PAM...')
    
    with Session(engine) as session:
        # Vérifier si des scénarios IHE PAM existent déjà
        existing_count = session.exec(
            select(InteropScenario).where(InteropScenario.category == "IHE_PAM")
        ).all()
        
        if existing_count:
            print(f'  {len(existing_count)} scénarios IHE PAM déjà présents - seed ignoré')
            return
        
        created_count = 0
        skipped_count = 0
        total_messages = 0
        
        for hl7_file in sorted(hl7_files):
            try:
                with open(hl7_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                
                if not content:
                    skipped_count += 1
                    continue
                
                messages = extract_hl7_messages(content)
                if not messages:
                    skipped_count += 1
                    continue
                
                scenario_name = get_scenario_name_from_path(str(hl7_file))
                
                # Vérifier que le scénario n'existe pas
                existing = session.exec(
                    select(InteropScenario).where(InteropScenario.name == scenario_name)
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Créer le scénario
                scenario = InteropScenario(
                    key=f"ihe_pam_{created_count}_{hl7_file.stem}",
                    name=scenario_name,
                    description=f"Scénario IHE PAM importé de {hl7_file.relative_to(base_path.parent.parent.parent)}",
                    category="IHE_PAM",
                    protocol="HL7",
                    source_path=str(hl7_file),
                    tags="pam,hl7,integration",
                    is_active=True
                )
                session.add(scenario)
                session.flush()
                
                # Créer les étapes
                for order_idx, msg in enumerate(messages, 1):
                    step = InteropScenarioStep(
                        scenario_id=scenario.id,
                        order_index=order_idx,
                        name=f"Step {order_idx}: {extract_trigger_from_message(msg)}",
                        message_format="hl7",
                        message_type=extract_trigger_from_message(msg),
                        payload=msg
                    )
                    session.add(step)
                
                session.flush()
                created_count += 1
                total_messages += len(messages)
                
                if (created_count) % 20 == 0:
                    print(f'  ... {created_count}/{len(hl7_files)} scénarios')
                
            except Exception as e:
                skipped_count += 1
        
        session.commit()
        
        print(f'  ✓ Importé {created_count} scénarios avec {total_messages} messages')
        if skipped_count > 0:
            print(f'  ({skipped_count} fichiers ignorés)')


if __name__ == "__main__":
    seed_hl7_scenarios()
