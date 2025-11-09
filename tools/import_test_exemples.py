#!/usr/bin/env python3
"""Import des fichiers de test depuis tests/exemples.

Crée un GHT TEST dédié et importe:
1. Les messages MFN de structure (ExempleExtractionStructure.txt)
2. Les messages PAM HL7 (Fichier_test_pam/*.hl7)

Usage:
    python3 tools/import_test_exemples.py [--ght-code GHT-TEST]
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime
import glob

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.db import engine, init_db
from app.models_structure_fhir import (
    GHTContext, EntiteJuridique, IdentifierNamespace, EntiteGeographique
)
from app.models import Patient, Dossier, Venue, Mouvement
from app.models_structure import (
    Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
)

def init_namespaces(session: Session, ght: GHTContext) -> dict[str, IdentifierNamespace]:
    """Initialise les namespaces requis pour l'exemple."""
    namespaces = {}
    
    ns_configs = {
        "IPP": ("IPP", "Identifiant Permanent Patient"),
        "NDA": ("NDA", "Numéro de Dossier Administratif"),
        "IEL": ("IEL", "Identifiant Episode Local"),
        "FINESSEJ": ("FINESS EJ", "Identifiant FINESS Entité Juridique"),
        "FINESSEG": ("FINESS EG", "Identifiant FINESS Entité Géographique"), 
    }
    
    for ns_type, (name, desc) in ns_configs.items():
        ns = session.exec(
            select(IdentifierNamespace)
            .where(IdentifierNamespace.ght_context_id == ght.id)
            .where(IdentifierNamespace.type == ns_type)
        ).first()
        
        if not ns:
            ns = IdentifierNamespace(
                type=ns_type,
                name=name,
                description=desc,
                ght_context_id=ght.id,
                is_active=True
            )
            session.add(ns)
            print(f"✅ Namespace {ns_type} créé")
        else:
            print(f"✓ Namespace {ns_type} existant")
        
        namespaces[ns_type] = ns
    
    session.commit()
    return namespaces

def create_ght_test(session: Session, ght_code: str = "GHT-TEST") -> GHTContext:
    """Crée ou récupère le GHT TEST."""
    ght = session.exec(select(GHTContext).where(GHTContext.code == ght_code)).first()
    if ght:
        print(f"✓ GHT {ght_code} existant (id={ght.id})")
        return ght
    
    ght = GHTContext(
        name=f"GHT Test Exemples",
        code=ght_code,
        description="GHT pour import des fichiers de test depuis tests/exemples",
        oid_racine="1.2.250.1.211.10.200",
        fhir_server_url="http://localhost:8000/fhir",
        is_active=True
    )
    session.add(ght)
    session.commit()
    session.refresh(ght)
    print(f"✅ GHT {ght_code} créé (id={ght.id})")
    return ght

def create_ej_test(session: Session, ght: GHTContext) -> EntiteJuridique:
    """Crée ou récupère l'entité juridique de test."""
    ej = session.exec(
        select(EntiteJuridique)
        .where(EntiteJuridique.ght_context_id == ght.id)
        .where(EntiteJuridique.finess_ej == "700004591")
    ).first()
    
    if ej:
        print(f"✓ Entité Juridique existante (FINESS={ej.finess_ej})")
        return ej
    
    ej = EntiteJuridique(
        name="Etablissement Hospitalier Test",
        finess_ej="700004591",
        ght_context_id=ght.id,
        address_line="4 Avenue de la VBF, B.P. 4",
        postal_code="70014",
        city="VESOUL CEDEX",
        is_active=True
    )
    session.add(ej)
    session.commit()
    session.refresh(ej)
    print(f"✅ Entité Juridique créée (FINESS={ej.finess_ej})")
    return ej

def create_namespaces(session: Session, ej: EntiteJuridique, ght: GHTContext) -> dict:
    """Crée les namespaces pour l'EJ."""
    namespaces = {}
    
    for ns_type, ns_name, oid in [
        ("IPP", "IPP Test", "1.2.250.1.211.10.200.2"),
        ("NDA", "NDA Test", "1.2.250.1.211.12.1.2"),
        ("VENUE", "Venue Number Test", "1.2.250.1.211.12.1.2"),
    ]:
        ns = session.exec(
            select(IdentifierNamespace)
            .where(IdentifierNamespace.entite_juridique_id == ej.id)
            .where(IdentifierNamespace.type == ns_type)
        ).first()
        
        if not ns:
            ns = IdentifierNamespace(
                name=ns_name,
                system=f"urn:oid:{oid}",
                oid=oid,
                type=ns_type,
                ght_context_id=ght.id,
                entite_juridique_id=ej.id,
                is_active=True
            )
            session.add(ns)
            session.flush()
            print(f"  ✅ Namespace {ns_type} créé")
        else:
            print(f"  ✓ Namespace {ns_type} existant")
        
        namespaces[ns_type] = ns
    
    session.commit()
    return namespaces

from app.validators.hl7_validators import MFNValidator, PAMValidator, ValidationError, ValidationResult

def import_structure_mfn(session: Session, ej: EntiteJuridique, structure_file: Path):
    """Importe la structure depuis le fichier MFN."""
    if not structure_file.exists():
        print(f"⚠️  Fichier structure non trouvé: {structure_file}")
        return
    
    print(f"📥 Import structure MFN depuis {structure_file.name}...")
    
    try:
        # Parser et valider le fichier MFN
        with open(structure_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        validator = MFNValidator()
        result = validator.validate_message(content)
        
        if not result.is_valid:
            print("\n❌ Erreurs de validation dans le fichier MFN:")
            for error in result.errors:
                line_info = f" (ligne {error.line_number})" if error.line_number else ""
                field_info = f" - champ {error.field}" if error.field else ""
                print(f"  • {error.message} [{error.segment}{field_info}]{line_info}")
            if result.warnings:
                print("\n⚠️  Avertissements:")
                for warning in result.warnings:
                    line_info = f" (ligne {warning.line_number})" if warning.line_number else ""
                    field_info = f" - champ {warning.field}" if warning.field else ""
                    print(f"  • {warning.message} [{warning.segment}{field_info}]{line_info}")
            return

        # Les messages HL7 utilisent \r comme séparateur de segment
        segments = content.replace('\r\n', '\r').replace('\n', '\r').split('\r')
        
        last_entities = {
            'eg': None, 'pole': None, 'service': None,
            'uf': None, 'uh': None, 'chambre': None
        }
        
        for segment in segments:
            fields = segment.split('|')
            
            # MFE segment resets the context
            if segment.startswith('MFE|'):
                last_entities = {k: None for k in last_entities}
                continue
            
            # LOC segment creates new entities
            if segment.startswith('LOC|'):
                loc_id = fields[1]
                loc_type = fields[3] if len(fields) > 3 else None
                name = fields[4] if len(fields) > 4 else None
                
                entity_configs = {
                    'ETBL_GRPQ': ('eg', EntiteGeographique, {'entite_juridique_id': ej.id, 'finess': ej.finess_ej}),
                    'PL': ('pole', Pole, {'entite_geo_id': last_entities['eg'].id if last_entities['eg'] else None}),
                    'D': ('service', Service, {'pole_id': last_entities['pole'].id if last_entities['pole'] else None, 'service_type': 'MCO'}),
                    'UF': ('uf', UniteFonctionnelle, {'service_id': last_entities['service'].id if last_entities['service'] else None}),
                    'UH': ('uh', UniteHebergement, {'unite_fonctionnelle_id': last_entities['uf'].id if last_entities['uf'] else None}),
                    'CH': ('chambre', Chambre, {'unite_hebergement_id': last_entities['uh'].id if last_entities['uh'] else None, 'physical_type': 'RO'}),
                    'LIT': (None, Lit, {'chambre_id': last_entities['chambre'].id if last_entities['chambre'] else None, 'physical_type': 'BD'})
                }
                
                if loc_type in entity_configs:
                    key, entity_class, extra_params = entity_configs[loc_type]
                    
                    # Check if entity exists
                    entity = session.exec(select(entity_class).where(entity_class.identifier == loc_id)).first()
                    
                    if not entity:
                        # Create new entity with default 'SI' physical_type (except for Chambre and Lit)
                        params = {
                            'identifier': loc_id,
                            'name': name or f'{entity_class.__name__} importé',
                            'physical_type': 'SI',
                            **extra_params
                        }
                        entity = entity_class(**params)
                        session.add(entity)
                        session.flush()
                    
                    # Update last entity reference if it's not a Lit
                    if key:
                        last_entities[key] = entity

            # LCH segment updates entity attributes
            elif segment.startswith('LCH|'):
                lch_fields = fields[3].split('^') if len(fields) > 3 else []
                attr_code = lch_fields[0] if lch_fields else None
                attr_value = fields[4][1:] if len(fields) > 4 and fields[4].startswith('^') else (fields[4] if len(fields) > 4 else None)
                
                # Update name if attr_code is LBL
                if attr_code == 'LBL' and attr_value:
                    for entity in last_entities.values():
                        if entity:
                            entity.name = attr_value
                            break

        session.commit()
        print("  ✅ Import MFN structure complet : EG, pôles, services, UF, UH, chambres, lits liés hiérarchiquement.")
    
    except Exception as e:
        print(f"❌ Erreur lors de l'import structure: {str(e)}")
        session.rollback()
        raise

def import_pam_messages(session: Session, ej: EntiteJuridique, directory: Path, max_files: int = 20):
    """Importe les messages PAM HL7 depuis le répertoire."""
    if not directory.exists():
        print(f"⚠️  Répertoire PAM non trouvé: {directory}")
        return
    
    hl7_files = sorted(directory.glob("*.hl7"))
    if not hl7_files:
        print(f"⚠️  Aucun fichier .hl7 trouvé dans {directory}")
        return
    
    print(f"📥 Import de {min(max_files, len(hl7_files))}/{len(hl7_files)} messages PAM HL7...")
    
    stats = {
        'imported': 0,
        'errors': 0,
        'patients_created': 0,
        'validation_errors': 0,
        'venues_created': 0,
        'mouvements_created': 0,
        'skipped': 0
    }
    
    try:
        for hl7_file in hl7_files[:max_files]:
            try:
                # Lecture et validation du fichier HL7
                with open(hl7_file, 'r', encoding='utf-8', errors='ignore') as f:
                    hl7_content = f.read()

                validator = PAMValidator()
                result = validator.validate_message(hl7_content)
                
                if not result.is_valid:
                    print(f"\n❌ Erreurs de validation dans {hl7_file.name}:")
                    for error in result.errors:
                        line_info = f" (ligne {error.line_number})" if error.line_number else ""
                        field_info = f" - champ {error.field}" if error.field else ""
                        print(f"  • {error.message} [{error.segment}{field_info}]{line_info}")
                    if result.warnings:
                        print("\n⚠️  Avertissements:")
                        for warning in result.warnings:
                            line_info = f" (ligne {warning.line_number})" if warning.line_number else ""
                            field_info = f" - champ {warning.field}" if warning.field else ""
                            print(f"  • {warning.message} [{warning.segment}{field_info}]{line_info}")
                    stats['validation_errors'] += 1
                    stats['skipped'] += 1
                    continue
                
                # Les messages HL7 utilisent \r comme séparateur de segment
                content = hl7_content.replace('\r\n', '\r').replace('\n', '\r')
                segments = content.split('\r')
                
                # État pour le message en cours
                current_patient = None
                current_venue = None
                
                # Traiter les segments
                for segment in segments:
                    fields = segment.split('|')
                    
                    if segment.startswith('PID|'):
                        # Identifiants patient
                        pid_id = fields[3].split('^')[0] if len(fields) > 3 else None
                        pid_name = fields[5].split('^') if len(fields) > 5 else []
                        name = pid_name[0] if pid_name else 'Inconnu'
                        surname = pid_name[1] if len(pid_name) > 1 else ''
                        
                        # Chercher le patient existant ou en créer un nouveau
                        current_patient = session.exec(
                            select(Patient).where(Patient.identifier == pid_id)
                        ).first()
                        
                        if not current_patient:
                            current_patient = Patient(
                                identifier=pid_id,
                                name=name,
                                surname=surname,
                                entite_juridique_id=ej.id
                            )
                            session.add(current_patient)
                            session.flush()
                            patients_created += 1
                    
                    elif segment.startswith('PV1|') and current_patient:
                        # Informations de venue
                        pv1_id = fields[19] if len(fields) > 19 else None
                        pv1_uh = fields[3].split('^')[0] if len(fields) > 3 else None
                        
                        # Chercher l'UH correspondante
                        uh = None
                        if pv1_uh:
                            uh = session.exec(
                                select(UniteHebergement)
                                .where(UniteHebergement.identifier == pv1_uh)
                            ).first()
                        
                        # Chercher la venue existante ou en créer une nouvelle
                        current_venue = session.exec(
                            select(Venue)
                            .where(Venue.identifier == pv1_id)
                            .where(Venue.patient_id == current_patient.id)
                        ).first()
                        
                        if not current_venue:
                            current_venue = Venue(
                                identifier=pv1_id,
                                patient_id=current_patient.id,
                                unite_hebergement_id=uh.id if uh else None,
                                entite_juridique_id=ej.id
                            )
                            session.add(current_venue)
                            session.flush()
                    
                    elif segment.startswith('ZBE|') and current_venue:
                        # Informations de mouvement
                        zbe_datetime = fields[6] if len(fields) > 6 else None
                        zbe_action = fields[1] if len(fields) > 1 else None
                        
                        if zbe_datetime and zbe_action:
                            try:
                                mvt_date = datetime.strptime(zbe_datetime, '%Y%m%d%H%M%S')
                            except ValueError:
                                # Gérer les formats de date invalides
                                continue

                            mouvement = Mouvement(
                                venue_id=current_venue.id,
                                event_datetime=mvt_date,
                                action_code=zbe_action
                            )
                            session.add(mouvement)
                            session.flush()
                            stats['mouvements_created'] += 1
                
                session.commit()
                stats['imported'] += 1
                
            except Exception as e:
                print(f"❌ Erreur lors du traitement de {hl7_file.name}: {str(e)}")
                session.rollback()
                stats['errors'] += 1
                continue
        
        # Afficher les statistiques détaillées
        print(f"\n📊 Résultats import PAM:")
        print(f"  ✓ Messages importés: {stats['imported']}")
        print(f"  ✗ Erreurs techniques: {stats['errors']}")
        print(f"  ⚠️  Erreurs de validation: {stats['validation_errors']}")
        print(f"  ⏭️  Messages ignorés: {stats['skipped']}")
        print(f"\n📈 Entités créées:")
        print(f"  + Patients: {stats['patients_created']}")
        print(f"  + Venues: {stats['venues_created']}")
        print(f"  + Mouvements: {stats['mouvements_created']}")

        return stats['imported']

    except Exception as e:
        print(f"❌ Erreur globale lors de l'import PAM: {str(e)}")
        session.rollback()
        raise
def main():
    """Point d'entrée du script."""
    # Parser les arguments
    parser = argparse.ArgumentParser(description="Import des fichiers de test.")
    parser.add_argument("--ght-code", default="GHT-TEST", help="Code du GHT à créer/utiliser")
    parser.add_argument("--skip-mfn", action="store_true", help="Ignorer l'import MFN de structure")
    parser.add_argument("--skip-pam", action="store_true", help="Ignorer l'import des messages PAM")
    parser.add_argument("--max-pam", type=int, default=20, help="Nombre maximum de messages PAM à importer")
    args = parser.parse_args()
    
    # Chemins des fichiers sources
    base_dir = Path(__file__).parent.parent / "tests" / "exemples"
    structure_file = base_dir / "ExempleExtractionStructure.txt"
    pam_dir = base_dir / "Fichier_test_pam"

    # Validation des fichiers sources
    if not args.skip_mfn and not structure_file.exists():
        print(f"⚠️  Fichier structure non trouvé: {structure_file}")
        return 1
    
    if not args.skip_pam and not pam_dir.exists():
        print(f"⚠️  Répertoire PAM non trouvé: {pam_dir}")
        return 1

    # Initialisation de la base
    try:
        init_db()
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base de données: {str(e)}")
        return 1
    
    try:
        with Session(engine) as session:
            # Créer/récupérer le contexte GHT
            ght = create_ght_test(session, args.ght_code)
            
            # Créer/récupérer l'entité juridique et les namespaces
            ej = create_ej_test(session, ght)
            init_namespaces(session, ght)
            
            success = True
            
            # Import MFN de structure
            if not args.skip_mfn:
                try:
                    import_structure_mfn(session, ej, structure_file)
                except Exception as e:
                    print(f"❌ Erreur lors de l'import MFN: {str(e)}")
                    success = False
            
            # Import des messages PAM
            if not args.skip_pam:
                try:
                    import_pam_messages(session, ej, pam_dir, args.max_pam)
                except Exception as e:
                    print(f"❌ Erreur lors de l'import PAM: {str(e)}")
                    success = False
            
            # Résumé de l'import
            if success:
                print("\n✅ Import terminé avec succès !")
            else:
                print("\n⚠️  Import terminé avec des erreurs.")
                
            print(f"   GHT: {args.ght_code}")
            print(f"   EJ: 700004591 (Etablissement Hospitalier Test)")
            print(f"   Fichiers sources: {base_dir}")
            
            return 0 if success else 1
            
    except Exception as e:
        print(f"❌ Erreur globale: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
