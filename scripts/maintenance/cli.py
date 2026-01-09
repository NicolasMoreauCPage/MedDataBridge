#!/usr/bin/env python3
"""
CLI pour MedDataBridge - Commandes utilitaires.

Usage:
    python cli.py export-fhir --ej-id 1 --output structure.json
    python cli.py import-fhir --input bundle.json --ej-id 1
    python cli.py validate-hl7 --input message.hl7
    python cli.py metrics
"""
import click
import json
import sys
from pathlib import Path
from sqlmodel import select

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session
from app.db import engine, init_db
from app.models_structure import EntiteJuridique
from app.services.fhir_export_service import FHIRExportService
from app.validators.hl7_validators import PAMValidator, MFNValidator
from app.utils.structured_logging import metrics


@click.group()
def cli():
    """MedDataBridge CLI - Outils en ligne de commande."""
    pass


@cli.command()
@click.option('--ej-id', type=int, required=True, help='ID de l\'entité juridique')
@click.option('--output', type=click.Path(), help='Fichier de sortie (optionnel)')
@click.option('--type', type=click.Choice(['structure', 'patients', 'venues', 'all']), default='all', help='Type de données à exporter')
def export_fhir(ej_id: int, output: str, type: str):
    """Exporte des données au format FHIR."""
    init_db()
    
    with Session(engine) as session:
        # Récupérer l'EJ
        ej = session.get(EntiteJuridique, ej_id)
        if not ej:
            click.echo(f"❌ Entité juridique {ej_id} non trouvée", err=True)
            sys.exit(1)
        
        click.echo(f"📤 Export FHIR pour {ej.name} (ID: {ej_id})")
        
        # Créer le service d'export
        fhir_url = ej.ght_context.fhir_server_url if ej.ght_context else "http://localhost:8000/fhir"
        service = FHIRExportService(session, fhir_url)
        
        # Exporter selon le type
        data = {}
        
        if type in ['structure', 'all']:
            click.echo("  📍 Export de la structure...")
            structure_bundle = service.export_structure(ej)
            data['structure'] = structure_bundle.dict()
            click.echo(f"    ✓ {len(structure_bundle.entry)} locations exportées")
        
        if type in ['patients', 'all']:
            click.echo("  👤 Export des patients...")
            patient_bundle = service.export_patients(ej)
            data['patients'] = patient_bundle.dict()
            click.echo(f"    ✓ {len(patient_bundle.entry)} patients exportés")
        
        if type in ['venues', 'all']:
            click.echo("  🏥 Export des venues...")
            venue_bundle = service.export_venues(ej)
            data['venues'] = venue_bundle.dict()
            click.echo(f"    ✓ {len(venue_bundle.entry)} venues exportées")
        
        # Si un seul type, extraire directement le bundle
        if type != 'all':
            data = data[type]
        
        # Écrire dans le fichier ou stdout
        json_output = json.dumps(data, indent=2, ensure_ascii=False)
        
        if output:
            Path(output).write_text(json_output, encoding='utf-8')
            click.echo(f"\n✅ Export terminé: {output}")
        else:
            click.echo("\n" + json_output)


@cli.command()
@click.option('--input', type=click.Path(exists=True), required=True, help='Fichier bundle FHIR')
@click.option('--ej-id', type=int, required=True, help='ID de l\'entité juridique')
@click.option('--validate-only', is_flag=True, help='Valider uniquement sans importer')
def import_fhir(input: str, ej_id: int, validate_only: bool):
    """Importe un bundle FHIR."""
    init_db()
    
    # Lire le fichier
    bundle = json.loads(Path(input).read_text(encoding='utf-8'))
    
    # Valider
    click.echo(f"🔍 Validation du bundle {input}...")
    
    if bundle.get('resourceType') != 'Bundle':
        click.echo("❌ Le fichier n'est pas un Bundle FHIR", err=True)
        sys.exit(1)
    
    entries = bundle.get('entry', [])
    click.echo(f"  ✓ Bundle valide avec {len(entries)} entrées")
    
    if validate_only:
        click.echo("\n✅ Validation terminée (mode validation seule)")
        return
    
    # À FAIRE: Implémenter l'import réel
    click.echo(f"\n⚠️  Import non encore implémenté")
    click.echo(f"  Pour importer ce bundle, utilisez l'API POST /api/fhir/import/bundle")


@cli.command()
@click.option('--input', type=click.Path(exists=True), required=True, help='Fichier message HL7')
@click.option('--type', type=click.Choice(['PAM', 'MFN']), default='PAM', help='Type de message')
def validate_hl7(input: str, type: str):
    """Valide un message HL7."""
    # Lire le message
    message = Path(input).read_text(encoding='utf-8')
    
    click.echo(f"🔍 Validation du message {type}...")
    
    # Valider selon le type
    if type == 'PAM':
        validator = PAMValidator(message)
    else:
        validator = MFNValidator(message)
    
    is_valid = validator.validate()
    
    if is_valid:
        click.echo("✅ Message valide")
        
        if validator.warnings:
            click.echo(f"\n⚠️  Avertissements ({len(validator.warnings)}):")
            for warning in validator.warnings:
                click.echo(f"  - {warning}")
    else:
        click.echo("❌ Message invalide")
        click.echo(f"\nErreurs ({len(validator.errors)}):")
        for error in validator.errors:
            click.echo(f"  - {error}")
        
        sys.exit(1)


@cli.command()
def show_metrics():
    """Affiche les métriques d'opérations."""
    all_metrics = metrics.get_metrics()
    
    if not all_metrics:
        click.echo("📊 Aucune métrique disponible")
        return
    
    click.echo("📊 Métriques d'opérations:\n")
    
    for operation, data in all_metrics.items():
        click.echo(f"🔹 {operation}:")
        click.echo(f"  Exécutions: {data['count']}")
        click.echo(f"  Succès: {data['success_count']} ({data.get('success_rate', 0)*100:.1f}%)")
        click.echo(f"  Erreurs: {data['error_count']}")
        click.echo(f"  Durée moyenne: {data.get('avg_duration', 0):.3f}s")
        click.echo(f"  Durée min/max: {data['min_duration']:.3f}s / {data['max_duration']:.3f}s")
        click.echo()


@cli.command()
@click.option('--ej-id', type=int, required=True, help='ID de l\'entité juridique')
def stats(ej_id: int):
    """Affiche les statistiques d'une entité juridique."""
    init_db()
    
    with Session(engine) as session:
        from app.models import Patient, Venue, Dossier
        from app.models_structure import (
            EntiteGeographique, Pole, Service, UniteFonctionnelle,
            UniteHebergement, Chambre, Lit
        )
        
        # Récupérer l'EJ
        ej = session.get(EntiteJuridique, ej_id)
        if not ej:
            click.echo(f"❌ Entité juridique {ej_id} non trouvée", err=True)
            sys.exit(1)
        
        click.echo(f"📊 Statistiques pour {ej.name} (ID: {ej_id})\n")
        
        # Compter les structures
        eg_count = session.exec(
            select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == ej_id)
        ).count()
        
        click.echo(f"🏢 Structure:")
        click.echo(f"  Entités géographiques: {eg_count}")
        
        # À FAIRE: Ajouter plus de statistiques
        click.echo(f"\n💡 Pour plus de détails, utilisez l'API GET /api/fhir/export/statistics/{ej_id}")


if __name__ == '__main__':
    cli()
