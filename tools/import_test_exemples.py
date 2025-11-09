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
from app.models import Sequence


def get_next_sequence(session: Session, name: str) -> int:
    """Simple sequence generator used by the import tool to assign venue/dossier sequence ids."""
    seq = session.exec(select(Sequence).where(Sequence.name == name)).first()
    if not seq:
        seq = Sequence(name=name, value=1)
        session.add(seq)
        session.flush()
        return seq.value
    seq.value += 1
    session.add(seq)
    session.flush()
    return seq.value

def init_namespaces(session: Session, ght: GHTContext) -> dict[str, IdentifierNamespace]:
    """Initialise les namespaces requis pour l'exemple."""
    namespaces = {}
    
    # Provide canonical URN OIDs for the namespaces so the IdentifierNamespace.system
    # (non-null) constraint is satisfied when creating GHT-level namespaces.
    ns_configs = {
        "IPP": ("IPP", "Identifiant Permanent Patient", "1.2.250.1.211.10.200.2"),
        "NDA": ("NDA", "Numéro de Dossier Administratif", "1.2.250.1.211.12.1.2"),
        "IEL": ("IEL", "Identifiant Episode Local", "1.2.250.1.211.12.1.2"),
        "FINESSEJ": ("FINESS EJ", "Identifiant FINESS Entité Juridique", "1.2.250.1.211.10.200.1"),
        "FINESSEG": ("FINESS EG", "Identifiant FINESS Entité Géographique", "1.2.250.1.211.10.200.1"),
    }
    
    for ns_type, (name, desc, oid) in ns_configs.items():
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
                system=f"urn:oid:{oid}",
                oid=oid,
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
                
                # Si on crée un Service sans Pôle, créer un Pôle par défaut
                if loc_type == 'D' and last_entities['pole'] is None and last_entities['eg']:
                    default_pole = session.exec(
                        select(Pole).where(
                            Pole.identifier == f"POLE_DEFAULT_{last_entities['eg'].identifier}"
                        )
                    ).first()
                    if not default_pole:
                        default_pole = Pole(
                            identifier=f"POLE_DEFAULT_{last_entities['eg'].identifier}",
                            name="Pôle par défaut",
                            entite_geo_id=last_entities['eg'].id,
                            physical_type='SI'
                        )
                        session.add(default_pole)
                        session.flush()
                    last_entities['pole'] = default_pole
                
                entity_configs = {
                    'M': (None, None, {}),  # Ignore EJ (déjà existant)
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
                    
                    # Skip if entity_class is None (e.g., EJ already exists)
                    if entity_class is None:
                        continue
                    
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
        # Collections for per-file reporting
        imported_files = []
        validation_failed = []
        error_files = []

        for hl7_file in hl7_files[:max_files]:
            try:
                # Lecture et validation du fichier HL7
                with open(hl7_file, 'r', encoding='utf-8', errors='ignore') as f:
                    hl7_content = f.read()

                validator = PAMValidator()
                result = validator.validate_message(hl7_content)
                
                if not result.is_valid:
                    # Capture validation failures with the raw PV1/ZBE lines for easier debugging
                    pv1_line = None
                    zbe_line = None
                    try:
                        c = hl7_content.replace('\r\n', '\r').replace('\n', '\r')
                        segs = c.split('\r')
                        for s in segs:
                            if s.startswith('PV1|'):
                                pv1_line = s
                            if s.startswith('ZBE|'):
                                zbe_line = s
                    except Exception:
                        pass

                    validation_failed.append({
                        'file': hl7_file.name,
                        'errors': [(e.segment, e.field, e.message, e.line_number) for e in result.errors],
                        'warnings': [(w.segment, w.field, w.message, w.line_number) for w in (result.warnings or [])],
                        'pv1': pv1_line,
                        'zbe': zbe_line
                    })

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
                        pid_id = fields[3].split('^')[0] if len(fields) > 3 and fields[3] else None
                        pid_name = fields[5].split('^') if len(fields) > 5 and fields[5] else []
                        family = pid_name[0] if pid_name and pid_name[0] else 'Inconnu'
                        given = pid_name[1] if len(pid_name) > 1 and pid_name[1] else None

                        # Chercher le patient existant ou en créer un nouveau
                        current_patient = session.exec(
                            select(Patient).where(Patient.identifier == pid_id)
                        ).first()

                        if not current_patient:
                            # Patient.family is NOT NULL in the model; provide a default
                            current_patient = Patient(
                                identifier=pid_id,
                                family=family,
                                given=given,
                                entite_juridique_id=ej.id
                            )
                            session.add(current_patient)
                            session.flush()
                            stats['patients_created'] += 1
                    
                    elif segment.startswith('PV1|') and current_patient:
                        # Informations de venue
                        pv1_id = fields[19] if len(fields) > 19 and fields[19] else None
                        # PV1-3 may contain a composite like "UF-CARDIO-H^^^..."; take first component
                        pv1_loc = fields[3].split('^')[0] if len(fields) > 3 and fields[3] else None

                        # Chercher l'UH correspondante
                        uh = None
                        if pv1_loc:
                            uh = session.exec(
                                select(UniteHebergement)
                                .where(UniteHebergement.identifier == pv1_loc)
                            ).first()

                        # Chercher la venue existante en utilisant l'identifiant PV1-19
                        current_venue = None
                        if pv1_id:
                            # PV1-19 may be stored as an Identifier record linked to a Venue
                            from app.models_identifiers import Identifier as IdModel
                            ident = session.exec(
                                select(IdModel).where(IdModel.value == pv1_id, IdModel.type == 'VN')
                            ).first()
                            if ident and ident.venue_id:
                                current_venue = session.exec(select(Venue).where(Venue.id == ident.venue_id)).first()

                        if not current_venue:
                            # Create a minimal Dossier for this patient so Venue.dossier_id can be set
                            try:
                                d_seq = get_next_sequence(session, "dossier")
                                dossier = Dossier(
                                    dossier_seq=d_seq,
                                    patient_id=current_patient.id,
                                    uf_responsabilite=uh.identifier if uh and hasattr(uh, 'identifier') else None,
                                    admit_time=datetime.utcnow()
                                )
                                session.add(dossier)
                                session.flush()
                                stats.setdefault('dossiers_created', 0)
                                stats['dossiers_created'] += 1
                            except Exception:
                                dossier = None

                            # Create a new Venue linked to the Dossier
                            current_venue = Venue(
                                # Use a generated venue_seq to avoid unique constraint collisions
                                venue_seq=get_next_sequence(session, "venue"),
                                dossier_id=dossier.id if dossier else None,
                                patient_id=current_patient.id,
                                unite_hebergement_id=uh.id if uh else None,
                                entite_juridique_id=ej.id,
                                start_time=datetime.utcnow()
                            )
                            session.add(current_venue)
                            session.flush()
                            stats['venues_created'] += 1

                            # Persist PV1-19 as an Identifier for later lookups
                            if pv1_id:
                                try:
                                    from app.models_identifiers import Identifier as IdModel, IdentifierType as IdType
                                    ident = IdModel(value=pv1_id, type=IdType.VN, system=f"urn:hl7:pv1:19", venue_id=current_venue.id)
                                    session.add(ident)
                                    session.flush()
                                except Exception:
                                    pass
                    
                    elif segment.startswith('ZBE|') and current_venue:
                        # Informations de mouvement (extraction tolérante)
                        zbe_fields = segment.split('|')
                        f1 = zbe_fields[1] if len(zbe_fields) > 1 else ""

                        # Heuristique: integration-style if f1 empty, numeric, startswith MVT or contains '^'
                        is_integration = (not f1) or f1.isdigit() or f1.startswith('MVT') or ('^' in f1)

                        if is_integration:
                            zbe_datetime_raw = zbe_fields[2] if len(zbe_fields) > 2 else None
                            # action may be in F3/F4/F5 depending on feed
                            zbe_action = None
                            for idx in (3, 4, 5):
                                if len(zbe_fields) > idx and zbe_fields[idx]:
                                    zbe_action = zbe_fields[idx]
                                    break
                        else:
                            zbe_datetime_raw = zbe_fields[6] if len(zbe_fields) > 6 else None
                            zbe_action = f1 or None

                        def parse_hl7_ts(raw: str):
                            if not raw:
                                return None
                            m = __import__('re').match(r"^(\d+)", raw)
                            if not m:
                                return None
                            digits = m.group(1)
                            fmts = [('%Y%m%d%H%M%S', 14), ('%Y%m%d%H%M', 12), ('%Y%m%d%H', 10), ('%Y%m%d', 8)]
                            from datetime import datetime as _dt
                            for fmt, needed in fmts:
                                s = digits
                                if len(s) < needed:
                                    s = s.ljust(needed, '0')
                                elif len(s) > needed:
                                    s = s[:needed]
                                try:
                                    return _dt.strptime(s, fmt)
                                except Exception:
                                    continue
                            return None

                        if zbe_datetime_raw and zbe_action:
                            mvt_date = parse_hl7_ts(zbe_datetime_raw)
                            if not mvt_date:
                                # skip messages with unparseable date
                                continue

                            # Use model field names: 'when' is required (NOT NULL) and 'action' maps to ZBE action
                            mouvement = Mouvement(
                                mouvement_seq=get_next_sequence(session, "mouvement"),
                                venue_id=current_venue.id,
                                when=mvt_date,
                                action=zbe_action
                            )
                            session.add(mouvement)
                            session.flush()
                            stats['mouvements_created'] += 1
                
                session.commit()
                stats['imported'] += 1
                imported_files.append(hl7_file.name)
                
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                print(f"❌ Erreur lors du traitement de {hl7_file.name}: {str(e)}")
                print(tb)
                session.rollback()
                stats['errors'] += 1
                error_files.append({'file': hl7_file.name, 'error': str(e), 'trace': tb})
                continue
        
        # Afficher les statistiques détaillées
        # Print summary and detailed per-file report
        print(f"\n📊 Résultats import PAM:")
        print(f"  ✓ Messages importés: {stats['imported']}")
        print(f"  ✗ Erreurs techniques: {stats['errors']}")
        print(f"  ⚠️  Erreurs de validation: {stats['validation_errors']}")
        print(f"  ⏭️  Messages ignorés: {stats['skipped']}")
        print(f"\n📈 Entités créées:")
        print(f"  + Patients: {stats['patients_created']}")
        print(f"  + Venues: {stats['venues_created']}")
        print(f"  + Mouvements: {stats['mouvements_created']}")

        # Detailed lists
        if imported_files:
            print(f"\n🗂️  Fichiers importés ({len(imported_files)}):")
            for name in imported_files:
                print(f"  - {name}")

        if validation_failed:
            print(f"\n⚠️  Fichiers avec erreurs de validation ({len(validation_failed)}):")
            for v in validation_failed:
                print(f"\n  - {v['file']}")
                for seg, fld, msg, ln in v['errors']:
                    lninfo = f" (ligne {ln})" if ln else ""
                    print(f"     • {seg}{(' - '+fld) if fld else ''}: {msg}{lninfo}")
                if v.get('pv1'):
                    print(f"     PV1: {v.get('pv1')}")
                if v.get('zbe'):
                    print(f"     ZBE: {v.get('zbe')}")

        if error_files:
            print(f"\n❌ Fichiers avec erreurs techniques ({len(error_files)}):")
            for e in error_files:
                print(f"\n  - {e['file']}")
                print(f"     Erreur: {e['error']}")
                print(f"     Trace: {e['trace'].splitlines()[-1]}")

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
