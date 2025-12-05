#!/usr/bin/env python3
"""
Seed des scénarios IHE PAM depuis les fichiers HL7 de interfaces.integration
À intégrer dans le processus d'initialisation de la base de données

Phase 3 - INTEGRATION VALIDATEUR:
Valide et corrige automatiquement les messages HL7 lors de l'import
"""

import os
from pathlib import Path
from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select
from datetime import datetime
from hl7_import_validator import HL7ImportValidator, ValidationResult


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


def _save_corrections_report(corrections_log: list) -> None:
    """Sauvegarde un rapport détaillé des corrections appliquées"""
    if not corrections_log:
        return
    
    report_path = Path('/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/P3_IMPORT_CORRECTIONS_REPORT.md')
    
    with open(report_path, 'w') as f:
        f.write('# Phase 3 - Rapport des Corrections à l\'Import\n\n')
        f.write(f'**Timestamp**: {datetime.now().isoformat()}\n\n')
        f.write(f'**Messages corrigés**: {len(corrections_log)}\n\n')
        
        f.write('## Résumé par Type d\'Erreur\n\n')
        error_types = {}
        for correction in corrections_log:
            for error in correction['errors']:
                error_type = error.split(':')[0] if ':' in error else error
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            f.write(f'- **{error_type}**: {count} occurrences\n')
        
        f.write('\n## Corrections Détaillées\n\n')
        
        for i, correction in enumerate(corrections_log, 1):
            f.write(f'### {i}. {correction["scenario"]} - Step {correction["step"]} ({correction["trigger"]})\n\n')
            
            if correction['errors']:
                f.write('**Erreurs détectées**:\n')
                for error in correction['errors']:
                    f.write(f'- {error}\n')
                f.write('\n')
            
            if correction['corrections']:
                f.write('**Corrections appliquées**:\n')
                for fix in correction['corrections']:
                    f.write(f'- {fix}\n')
                f.write('\n')
    
    print(f'\n  📄 Rapport des corrections sauvegardé: {report_path}')



def seed_hl7_scenarios():
    """Importe tous les fichiers HL7 comme scénarios dans la base
    
    Phase 3 - Intégration du validateur:
    - Valide chaque message HL7 avant insertion
    - Applique automatiquement les corrections (mode LENIENT)
    - Enregistre les corrections appliquées
    - Rejette les messages invalides irréparables
    """
    
    base_path = Path('/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/Doc/interfaces.integration_src/interfaces.integration/target/classes/data')
    
    if not base_path.exists():
        print(f'Répertoire de scénarios introuvable: {base_path}')
        print('Seed IHE PAM ignoré - les fichiers HL7 de test ne sont pas disponibles')
        return
    
    hl7_files = list(base_path.glob('**/*.hl7'))
    if not hl7_files:
        print('Aucun fichier HL7 trouvé')
        return
    
    print(f'\nImportation de {len(hl7_files)} scénarios IHE PAM avec validation...')
    
    # Initialiser le validateur en mode LENIENT (auto-correction)
    validator = HL7ImportValidator(mode="LENIENT")
    
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
        valid_messages = 0
        corrected_messages = 0
        rejected_messages = 0
        corrections_log = []
        
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
                
                # Créer les étapes avec validation et correction
                for order_idx, msg in enumerate(messages, 1):
                    trigger = extract_trigger_from_message(msg)
                    total_messages += 1
                    
                    # Valider et corriger le message
                    validation_report = validator.validate_message(msg)
                    
                    if validation_report.status == ValidationResult.VALID:
                        # Message valide - utiliser tel quel
                        payload_to_store = msg
                        valid_messages += 1
                    elif validation_report.status == ValidationResult.FIXABLE:
                        # Message corrigible - utiliser la version corrigée
                        payload_to_store = validation_report.corrected_message
                        corrected_messages += 1
                        
                        # Enregistrer les corrections
                        corrections_log.append({
                            'scenario': scenario_name,
                            'step': order_idx,
                            'trigger': trigger,
                            'errors': validation_report.errors,
                            'corrections': validation_report.corrections_applied
                        })
                    else:  # REJECTED
                        # Message invalide - ignorer
                        rejected_messages += 1
                        print(f'    ⚠ Message rejeté: {scenario_name} Step {order_idx} ({trigger})')
                        continue
                    
                    # Créer l'étape avec le message (validé/corrigé ou original)
                    step = InteropScenarioStep(
                        scenario_id=scenario.id,
                        order_index=order_idx,
                        name=f"Step {order_idx}: {trigger}",
                        message_format="hl7",
                        message_type=trigger,
                        payload=payload_to_store
                    )
                    session.add(step)
                
                session.flush()
                created_count += 1
                
                if (created_count) % 20 == 0:
                    print(f'  ... {created_count}/{len(hl7_files)} scénarios')
                
            except Exception as e:
                skipped_count += 1
                print(f'    ✗ Erreur lors du traitement {hl7_file}: {str(e)[:100]}')
        
        session.commit()
        
        # Statistiques d'import
        print(f'\n  ✓ Importé {created_count} scénarios avec {total_messages} messages')
        print(f'    - {valid_messages} messages valides (sans modification)')
        print(f'    - {corrected_messages} messages corrigés (auto-fix appliqué)')
        print(f'    - {rejected_messages} messages rejetés (invalides)')
        if skipped_count > 0:
            print(f'    - ({skipped_count} fichiers ignorés)')
        
        # Enregistrer les corrections dans un rapport
        if corrections_log:
            print(f'\n  Corrections appliquées à {len(corrections_log)} messages:')
            for correction in corrections_log[:10]:  # Afficher les 10 premières
                print(f'    • {correction["scenario"]} - Step {correction["step"]} ({correction["trigger"]})')
                for error in correction['errors'][:2]:
                    print(f'      - {error}')
                for fix in correction['corrections'][:2]:
                    print(f'      ✓ {fix}')
            if len(corrections_log) > 10:
                print(f'    ... et {len(corrections_log) - 10} autres messages corrigés')
        
        # Sauvegarder un rapport détaillé
        _save_corrections_report(corrections_log)


if __name__ == "__main__":
    seed_hl7_scenarios()
