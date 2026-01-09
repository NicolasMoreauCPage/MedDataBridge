#!/usr/bin/env python3
"""
Importe tous les scénarios HL7 depuis le programme Java d'intégration
dans la base de données MedDataBridge.

Ce script importe les scénarios depuis:
Doc/interfaces.integration/src/main/resources/data/entrant/hl7/

Et les ajoute comme scénarios IHE_PAM dans MedDataBridge.
"""
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select
from datetime import datetime

def extract_hl7_messages(hl7_content: str) -> list:
    """Extrait les messages HL7 individuels d'un fichier."""
    content = hl7_content.replace('\r\n', '\n')
    messages = []
    current_msg = []
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('MSH') and current_msg:
            messages.append('\r'.join(current_msg))
            current_msg = [line]
        else:
            current_msg.append(line)
    if current_msg:
        messages.append('\r'.join(current_msg))
    return messages

def extract_trigger_from_message(hl7_msg: str) -> str:
    """Extrait le trigger event du message HL7."""
    lines = hl7_msg.split('\r')
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
    """Génère un nom de scénario à partir du chemin du fichier."""
    basename = os.path.basename(file_path)
    name = basename.replace('.hl7', '')
    name = name.replace('_', ' ')
    name = name.replace('TestHL7', '').strip()
    name = name.title()

    # Mapping des noms pour plus de clarté
    name_mapping = {
        'Hospit Simple': 'Hospitalisation Simple',
        'Hospit Jour': 'Hospitalisation de Jour',
        'Hospit Complexe': 'Hospitalisation Complexe',
        'Entree Sortie Transfert': 'Entrée-Sortie-Transfert',
        'Changement Statut': 'Changement de Statut',
        'Maternite Neonat': 'Maternité-Néonatologie',
        'Urgence': 'Urgence',
        'Externe': 'Patient Externe',
        'Preadmission': 'Pré-admission',
        'Seances': 'Séances',
        'Venue Confidentielle': 'Venue Confidentielle',
        'Sortie Contre Avis Medical': 'Sortie Contre Avis Médical',
        'Sortie Retour Fugue': 'Sortie-Retour de Fugue',
        'Sortie Retour Permission': 'Sortie-Retour de Permission',
        'Sortie Retour Transfert': 'Sortie-Retour de Transfert',
    }

    for old_name, new_name in name_mapping.items():
        if old_name.lower() in name.lower():
            name = name.replace(old_name, new_name)

    return f"IHE PAM - {name}"

def get_scenario_category_from_path(file_path: str) -> str:
    """Détermine la catégorie du scénario selon son chemin."""
    path_parts = Path(file_path).parts

    if 'maternite' in path_parts:
        return 'MATERNITE'
    elif 'urgence' in path_parts:
        return 'URGENCE'
    elif 'externe' in path_parts:
        return 'EXTERNE'
    elif 'preadmission' in path_parts or 'pread' in str(file_path).lower():
        return 'PREADMISSION'
    elif 'seance' in path_parts or 'seances' in str(file_path).lower():
        return 'SEANCES'
    elif 'changementStatut' in path_parts or 'changement_statut' in str(file_path).lower():
        return 'CHANGEMENT_STATUT'
    elif 'hospit' in str(file_path).lower():
        return 'HOSPITALISATION'
    elif 'identite' in path_parts:
        return 'IDENTITE'
    elif 'mouvement' in path_parts:
        return 'MOUVEMENT'
    else:
        return 'GENERAL'

def import_java_integration_scenarios(test_mode=False):
    """Importe tous les scénarios depuis le programme Java d'intégration."""

    # Chemin vers les scénarios du programme Java
    base_path = Path("Doc/interfaces.integration/src/main/resources/data/entrant/hl7")

    if not base_path.exists():
        print(f"❌ Chemin non trouvé: {base_path}")
        return

    hl7_files = list(base_path.glob('**/*.hl7'))
    print(f'📁 Trouvé {len(hl7_files)} fichiers HL7 dans le programme Java')

    # En mode test, traiter seulement les 5 premiers fichiers
    if test_mode:
        hl7_files = hl7_files[:5]
        print(f'🧪 Mode test: traitement des {len(hl7_files)} premiers fichiers seulement')

    with Session(engine) as session:
        created_count = 0
        skipped_count = 0
        error_count = 0

        for i, hl7_file in enumerate(sorted(hl7_files)):
            try:
                print(f"\n🔍 Traitement {i+1}/{len(hl7_files)}: {hl7_file.name}")

                with open(hl7_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()

                if not content:
                    print(f"  ⊘ {hl7_file.name}: fichier vide")
                    skipped_count += 1
                    continue

                messages = extract_hl7_messages(content)
                if not messages:
                    print(f"  ⊘ {hl7_file.name}: aucun message trouvé")
                    skipped_count += 1
                    continue

                scenario_name = get_scenario_name_from_path(str(hl7_file))
                category = get_scenario_category_from_path(str(hl7_file))

                # Vérifier si le scénario existe déjà
                existing = session.exec(
                    select(InteropScenario).where(InteropScenario.name == scenario_name)
                ).first()

                if existing:
                    print(f"  ✓ {scenario_name}: déjà existant")
                    skipped_count += 1
                    continue

                # Créer le scénario
                scenario = InteropScenario(
                    key=f"java_integration_{created_count}_{hl7_file.stem}",
                    name=scenario_name,
                    description=f"Scénario IHE PAM importé du programme Java - {hl7_file.relative_to(base_path)}",
                    category=category,
                    protocol="HL7",
                    source_path=str(hl7_file),
                    tags="pam,hl7,integration,java_import",
                    is_active=True
                )

                session.add(scenario)
                session.flush()

                # Créer les étapes du scénario
                for order_idx, msg in enumerate(messages, 1):
                    trigger = extract_trigger_from_message(msg)
                    step = InteropScenarioStep(
                        scenario_id=scenario.id,
                        order_index=order_idx,
                        name=f"Étape {order_idx}: {trigger}",
                        message_format="hl7",
                        message_type=trigger,
                        payload=msg
                    )
                    session.add(step)

                session.commit()
                print(f"  ✅ Créé: {scenario_name} ({len(messages)} messages, catégorie: {category})")
                created_count += 1

            except Exception as e:
                print(f"  ❌ Erreur avec {hl7_file.name}: {e}")
                error_count += 1
                session.rollback()

    print("\n📊 Résumé de l'import:")
    print(f"  ✅ Créés: {created_count}")
    print(f"  ⏭️  Ignorés (déjà existants): {skipped_count}")
    print(f"  ❌ Erreurs: {error_count}")
    print(f"  📁 Total traité: {len(hl7_files)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Import IHE PAM scenarios from Java integration program')
    parser.add_argument('--test', action='store_true', help='Run in test mode (only first 5 files)')
    args = parser.parse_args()

    print("🚀 Import des scénarios IHE PAM depuis le programme Java d'intégration")
    print(f"📂 Répertoire de travail: {os.getcwd()}")
    import_java_integration_scenarios(test_mode=args.test)
    print("✨ Import terminé !")