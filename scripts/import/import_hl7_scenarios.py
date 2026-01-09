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

    # Nettoyer et améliorer le nom
    name = name.replace('TestHL7', '').strip()
    name = name.replace('_', ' ').replace('-', ' ')

    # Dictionnaire de mappings pour des noms plus parlants
    name_mappings = {
        'Hospit Simple': 'Hospitalisation Simple',
        'Hospit Jour': 'Hospitalisation de Jour',
        'Hospit Nuit': 'Hospitalisation de Nuit',
        'Hospit Complexe': 'Hospitalisation Complexe',
        'Urgence Simple': 'Admission Urgences',
        'Urgence Cristal': 'Admission Urgences Cristal',
        'Maternite Neonat': 'Maternité Néonatalogie',
        'Entree Urgence Sortie Deces': 'Entrée Urgence → Sortie Décès',
        'Hospit Simple Ident Externe': 'Hospitalisation Identité Externe',
        'Hospit Preadmission': 'Hospitalisation Pré-admission',
        'Identite Creation': 'Création Identité Patient',
        'Mutation And Cl': 'Mutation et Changement Lit',
        'Seances Avec Cloture': 'Séances avec Clôture Administrative',
        'Sortie Retour Permission': 'Sortie en Permission',
        'Venue Confidentielle': 'Venue Confidentielle',
        'Insert Mvt Auto Sprp': 'Insertion Mouvement Auto SPRP',
        'Parcours Soins Sillage To': 'Parcours de Soins Sillage TO',
        'Placement Psy': 'Placement Psychiatrique',
        'Pread Supp Pread': 'Suppression Pré-admission',
        'Rattachement Dossier': 'Rattachement de Dossier',
        'Sortie Contre Avis Medical': 'Sortie Contre Avis Médical',
        'Sortie Fugue Sans Retour': 'Sortie en Fugue',
        'Urgence Sillage': 'Urgence Sillage',
        'Ad Externe Chang Statut Eh Fu': 'Admission Externe → Changement Statut EH → FU',
        'EHPAD Sortie Transfert Retour Transfert': 'EHPAD Sortie → Transfert → Retour → Transfert',
        'Changement Statut Ext Vers Hospit': 'Changement Statut Externe → Hospitalisation',
        'Entree Transfert Interne Avec Pread': 'Entrée → Transfert Interne avec Pré-admission',
        'Hospit Cariatides Mode Entree 8': 'Hospitalisation Cariatides Mode Entrée 8',
        'Hospit Verif Mode Entree': 'Hospitalisation Vérification Mode Entrée',
        'Hospit Annul Venue': 'Hospitalisation Annulation Venue',
        'Test Letis': 'Test LETIS',
        'Double Changement Responsabilite': 'Double Changement de Responsabilité',
        'Externe Ajout Medecin Traitant': 'Ajout Médecin Traitant Externe',
        'Hospit Admission Simple Dx Care': 'Admission Simple DxCare',
        'Hospit Entree Sous Contrainte Police': 'Entrée sous Contrainte Police',
        'Hospit Jour Medecin Traitant': 'Hospitalisation Jour Médecin Traitant',
        'Identite Display Legal Name': 'Affichage Nom Légal',
        'Identite 7 Prenoms De Naissance': '7 Prénoms de Naissance',
        'Identite Ajout Placement Psy Iti30': 'Ajout Placement Psychiatrique ITI30',
        'Identite Creation Cristal': 'Création Identité Cristal',
        'Identite Creation Homme Marie': 'Création Identité Homme Marié',
        'Identite Creation Mariee Modification Divorcee': 'Création Mariée → Modification Divorcée',
        'Identite Creation Modif': 'Création et Modification Identité',
        'Identite Creation Modif Deces': 'Création → Modification → Décès',
        'Identite Creation Modif Supp Adresse': 'Création → Modif → Supp Adresse',
        'Identite Creation Patient Etranger': 'Création Patient Étranger',
        'Identite Creation Modif Suppr Adresse': 'Création → Modif → Suppression Adresse',
        'Identite Fusion Avec Dossier Externe': 'Fusion avec Dossier Externe',
        'Identite Nom Prenom': 'Nom et Prénom',
        'Maternite Neanat Sortie Bb Apres Mama': 'Maternité Néonat Sortie BB après Maman',
        'Maternite Simple Dx Care Obx': 'Maternité Simple DxCare OBX',
        'Mut Cl Mut Modif Cl': 'Mutation CL → Mutation → Modif CL',
        'Mutation And Cl Cancel': 'Mutation et CL Annulé',
        'Mutation Corrige En Changement Loc': 'Mutation Corrigée en Changement Loc',
        'Mutation Suivi Par Changement Tarif': 'Mutation → Changement Tarif',
        'Personne A Prevenir Cristal': 'Personne à Prévenir Cristal',
        'Seances Supression Seance Intermediaire': 'Suppression Séance Intermédiaire',
        'Seances Sur Dossier Non Seance': 'Séances sur Dossier Non-Séance',
        'Sortie Retour Transfert': 'Sortie → Retour → Transfert',
        'Urgence Mise En Lit A02 Correction Inutile': 'Urgence Mise en Lit A02 Correction Inutile',
        'Urgence Mise En Lit A02 Correction Loc A02': 'Urgence Mise en Lit A02 Correction Loc',
        'Urgence Mise En Lit A02 Correction Loc Resp': 'Urgence Mise en Lit A02 Correction Loc Resp',
        'Urgence Mise En Lit A02 Correction Resp A02': 'Urgence Mise en Lit A02 Correction Resp',
        'Urgence Modification Chgt Statut': 'Urgence Modification Changement Statut',
        'Urgence Provins Modif Adm': 'Urgence Provins Modif Admission',
        'Insert Mvt Inter Non Autorise': 'Insertion Mouvement Non Autorisé',
        'Insert Supp Mvt Iteratif Auto Djfj': 'Insertion/Suppression Mouvement Itératif DJFJ',
        'Insert Supp Mvt Iteratif Auto Dsfs': 'Insertion/Suppression Mouvement Itératif DSFS',
        'Supp Mvt Inter Non Autorise': 'Suppression Mouvement Non Autorisé',
    }

    # Appliquer les mappings
    for key, value in name_mappings.items():
        if key.lower() in name.lower():
            name = value
            break

    # Capitaliser et ajouter le préfixe
    name = name.strip().title()
    return f"IHE PAM - {name}" if name else f"IHE PAM - {basename.replace('.hl7', '')}"


def import_hl7_scenarios():
    """Importe tous les fichiers HL7 comme scénarios"""
    
    # Répertoire source - CORRIGÉ
    base_path = Path('/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/docs/interfaces.integration_src/interfaces.integration/src/main/resources/data/entrant/hl7')
    
    # Chercher tous les fichiers .hl7 dans le répertoire hl7
    hl7_files = list(base_path.glob('*.hl7'))
    print(f'Trouvé {len(hl7_files)} fichiers HL7 dans {base_path}')
    
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
                
                # Générer le nom du scénario
                scenario_name = get_scenario_name_from_path(str(hl7_file))
                
                # Vérifier que le scénario n'existe pas déjà (par clé unique)
                scenario_key = f"hl7_{hl7_file.stem}"
                existing = session.exec(
                    select(InteropScenario).where(InteropScenario.key == scenario_key)
                ).first()

                if existing:
                    print(f"  ✓ {scenario_name}: déjà existant")
                    skipped_count += 1
                    continue

                # Créer le scénario
                scenario = InteropScenario(
                    key=scenario_key,
                    name=scenario_name,
                    description=f"Scénario IHE PAM importé de {hl7_file.name}",
                    category="IHE_PAM",
                    protocol="HL7",
                    source_path=str(hl7_file),
                    tags="pam,hl7,integration,adt,mouvements",
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
