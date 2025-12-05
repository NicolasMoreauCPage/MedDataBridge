"""
Import des scénarios HL7 IHE PAM depuis les fichiers de test du projet interfaces.integration
"""

import os
import re
from pathlib import Path
from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select
from datetime import datetime


def extract_hl7_messages(hl7_content: str) -> list:
    """
    Extrait les messages HL7 individuels d'un fichier.
    Les messages sont séparés par des newlines (\\r\\n ou \\n).
    """
    # Normaliser les séparateurs
    content = hl7_content.replace('\r\n', '\n')
    
    messages = []
    current_msg = []
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Si la ligne commence par MSH, c'est un nouveau message
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
            if len(fields) > 8:
                # Format: ADT^A01 ou ADT^A02
                trigger_part = fields[8]  # ex: ADT^A01
                if '^' in trigger_part:
                    return trigger_part.split('^')[1]  # A01
                return trigger_part
    return 'UNKNOWN'


def get_scenario_name_from_path(file_path: str) -> str:
    """Génère un nom lisible depuis le chemin du fichier"""
    basename = os.path.basename(file_path)
    # Supprimer l'extension .hl7
    name = basename.replace('.hl7', '')
    # Remplacer les underscores par des espaces
    name = name.replace('_', ' ')
    # Remplacer TestHL7 par ''
    name = name.replace('TestHL7', '').strip()
    # Capitaliser
    name = name.title()
    return f"IHE PAM - {name}"


def import_hl7_scenarios():
    """Importe tous les fichiers HL7 comme scénarios"""
    
    # Répertoire source
    base_path = Path('/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/Doc/interfaces.integration_src/interfaces.integration/target/classes/data')
    
    # Chercher tous les fichiers .hl7
    hl7_files = list(base_path.glob('**/*.hl7'))
    print(f'Trouvé {len(hl7_files)} fichiers HL7')
    
    with Session(engine) as session:
        created_count = 0
        skipped_count = 0
        
        for i, hl7_file in enumerate(sorted(hl7_files)):
            try:
                # Lire le fichier
                with open(hl7_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                
                if not content:
                    print(f"  ⊘ {hl7_file.name}: fichier vide")
                    skipped_count += 1
                    continue
                
                # Extraire les messages HL7
                messages = extract_hl7_messages(content)
                if not messages:
                    print(f"  ⊘ {hl7_file.name}: aucun message trouvé")
                    skipped_count += 1
                    continue
                
                # Créer le scénario
                scenario_name = get_scenario_name_from_path(str(hl7_file))
                
                # Vérifier que le scénario n'existe pas déjà
                existing = session.exec(
                    select(InteropScenario).where(InteropScenario.name == scenario_name)
                ).first()
                
                if existing:
                    print(f"  ✓ {scenario_name}: déjà existant")
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
                print(f"  ✓ Créé: {scenario_name} ({len(messages)} messages)")
                created_count += 1
                
                # Progress indicator
                if (i + 1) % 20 == 0:
                    print(f"    ... {i + 1}/{len(hl7_files)} fichiers traités")
                
            except Exception as e:
                print(f"  ✗ {hl7_file.name}: {type(e).__name__}: {str(e)[:80]}")
                skipped_count += 1
        
        session.commit()
        
        print(f'\n' + '='*60)
        print(f'RÉSUMÉ: {created_count} scénarios créés, {skipped_count} ignorés')
        print(f'Total: {created_count + skipped_count}/{len(hl7_files)} fichiers traités')


if __name__ == "__main__":
    import_hl7_scenarios()
