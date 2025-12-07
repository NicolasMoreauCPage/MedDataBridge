#!/usr/bin/env python3
"""
Script d'importation des scénarios legacy depuis les fichiers .hl7

Les fichiers .hl7 du projet interfaces.integration contiennent plusieurs
messages HL7 séparés par des lignes vides, constituant des scénarios complets.

Ce script les importe dans la base de données comme InteropScenario avec
plusieurs InteropScenarioStep.

Usage: python -c "from import_legacy_scenarios import main; main()"
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime


def extract_message_type(hl7_message: str) -> str:
    """Extrait le type de message du segment MSH."""
    lines = hl7_message.strip().split('\n')
    for line in lines:
        if line.startswith('MSH|'):
            parts = line.split('|')
            if len(parts) > 8:
                # MSH-9 contient le type de message (ex: ADT^A28^ADT_A05)
                msg_type = parts[8]
                # On prend juste le code principal (ADT^A28)
                return msg_type.split('^')[0] + '^' + msg_type.split('^')[1] if '^' in msg_type else msg_type
    return "UNKNOWN"


def parse_hl7_scenario_file(file_path: str) -> list[str]:
    """Parse un fichier .hl7 et retourne la liste des messages individuels.
    
    Les messages sont séparés par des lignes vides dans le fichier.
    """
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Séparer par double saut de ligne (ou plus)
    messages = re.split(r'\n\s*\n', content)
    
    # Filtrer les messages vides et nettoyer
    messages = [msg.strip() for msg in messages if msg.strip()]
    
    return messages


def main():
    """Importe tous les scénarios legacy."""
    
    # Import models at runtime to avoid circular dependencies
    from sqlmodel import Session, select
    from app.db import engine
    from app.models_scenarios import InteropScenario, InteropScenarioStep
    from app.models_structure import GHTContext
    # Import ALL model modules to ensure SQLAlchemy knows all relationships
    from app import models, models_structure, models_scenarios, models_identifiers, models_practitioners, models_endpoints
    
    # Make functions available
    global import_scenario_from_hl7_file
    
    def _import_scenario_from_hl7_file(
        session: Session,
        file_path: str,
        ght_context_id: int,
        category: str = None
    ) -> InteropScenario:
        """Importe un scénario depuis un fichier .hl7 legacy."""
        
        path_obj = Path(file_path)
        file_name = path_obj.stem
        
        # Créer une clé unique basée sur le chemin relatif
        rel_path = path_obj.relative_to(path_obj.parents[5]) if len(path_obj.parents) > 5 else path_obj
        scenario_key = f"legacy/{rel_path.as_posix()}"
        
        # Vérifier si le scénario existe déjà
        existing = session.exec(
            select(InteropScenario).where(InteropScenario.key == scenario_key)
        ).first()
        
        if existing:
            print(f"⚠️  Scénario {file_name} déjà importé (key={scenario_key})")
            return existing
        
        # Parser les messages
        messages = parse_hl7_scenario_file(file_path)
        
        if not messages:
            print(f"❌ Aucun message trouvé dans {file_name}")
            return None
        
        # Créer le scénario
        scenario = InteropScenario(
            key=scenario_key,
            name=file_name.replace('_', ' ').replace('TestHL7', 'Test '),
            description=f"Scénario importé depuis {path_obj.name} ({len(messages)} messages)",
            category=category or "legacy",
            protocol="HL7",
            source_path=str(path_obj),
            ght_context_id=ght_context_id,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        session.add(scenario)
        session.commit()
        session.refresh(scenario)
        
        # Créer les étapes
        for idx, message in enumerate(messages):
            msg_type = extract_message_type(message)
            
            step = InteropScenarioStep(
                scenario_id=scenario.id,
                order_index=idx,
                name=f"Étape {idx+1}: {msg_type}",
                message_format="hl7",
                message_type=msg_type,
                payload=message,
                delay_seconds=1 if idx > 0 else 0,  # 1 seconde entre chaque message
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(step)
        
        session.commit()
        
        print(f"✅ Importé: {file_name} ({len(messages)} messages)")
        return scenario
    
    # Chemin vers les scénarios legacy
    base_path = Path("/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/Doc/interfaces.integration_src/interfaces.integration/target/classes/data/entrant/hl7")
    
    if not base_path.exists():
        print(f"❌ Chemin introuvable: {base_path}")
        return
    
    # Créer ou récupérer le contexte GHT
    with Session(engine) as session:
        context = session.exec(select(GHTContext).where(GHTContext.name == "Demo")).first()
        if not context:
            context = GHTContext(
                name="Demo",
                description="Contexte de démonstration pour scénarios legacy",
                is_active=True
            )
            session.add(context)
            session.commit()
            session.refresh(context)
            print(f"✅ Contexte GHT créé: {context.name} (id={context.id})")
        
        # Parcourir récursivement tous les fichiers .hl7
        hl7_files = list(base_path.rglob("*.hl7"))
        
        print(f"\n📂 Trouvé {len(hl7_files)} fichiers .hl7\n")
        
        imported_count = 0
        skipped_count = 0
        error_count = 0
        
        for hl7_file in sorted(hl7_files):
            try:
                # Déterminer la catégorie depuis le sous-dossier
                rel_path = hl7_file.relative_to(base_path)
                category = str(rel_path.parent) if rel_path.parent != Path('.') else "general"
                
                scenario = _import_scenario_from_hl7_file(
                    session,
                    str(hl7_file),
                    context.id,
                    category=category
                )
                
                if scenario:
                    imported_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                print(f"❌ Erreur lors de l'import de {hl7_file.name}: {e}")
                import traceback
                traceback.print_exc()
                error_count += 1
        
        print(f"\n📊 Résumé:")
        print(f"  ✅ Importés: {imported_count}")
        print(f"  ⚠️  Ignorés: {skipped_count}")
        print(f"  ❌ Erreurs: {error_count}")
        print(f"\n🎉 Import terminé!")


if __name__ == "__main__":
    main()
