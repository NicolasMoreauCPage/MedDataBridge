#!/usr/bin/env python3
"""
Export des données d'un établissement au format FHIR.

Usage:
    python3 tools/export_fhir.py [--ght-code GHT-TEST] [--finess 700004591]
    [--output-dir ./fhir_export] [--type structure,patients,venues]
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.db import engine, init_db
from app.models_structure_fhir import GHTContext, EntiteJuridique
from app.services.fhir_export_service import FHIRExportService

def main():
    """Point d'entrée du script."""
    # Parser les arguments
    parser = argparse.ArgumentParser(description="Export des données au format FHIR.")
    parser.add_argument("--ght-code", default="GHT-TEST",
                       help="Code du GHT")
    parser.add_argument("--finess", default="700004591",
                       help="FINESS de l'établissement à exporter")
    parser.add_argument("--output-dir", default="./fhir_export",
                       help="Répertoire de sortie pour les fichiers FHIR")
    parser.add_argument("--type", default="structure,patients,venues",
                       help="Types de données à exporter (structure,patients,venues)")
    parser.add_argument("--base-url", default="http://localhost:8000/fhir",
                       help="URL de base du serveur FHIR")
    args = parser.parse_args()
    
    # Valider les types demandés
    valid_types = {"structure", "patients", "venues"}
    requested_types = {t.strip() for t in args.type.split(",")}
    if not requested_types.issubset(valid_types):
        print(f"❌ Types invalides: {requested_types - valid_types}")
        print(f"Types valides: {valid_types}")
        return 1
    
    # Créer le répertoire de sortie
    output_dir = Path(args.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"❌ Erreur lors de la création du répertoire {output_dir}: {e}")
        return 1
    
    # Initialiser la base
    try:
        init_db()
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
        return 1
    
    try:
        with Session(engine) as session:
            # Chercher le GHT
            ght = session.exec(
                select(GHTContext)
                .where(GHTContext.code == args.ght_code)
            ).first()
            
            if not ght:
                print(f"❌ GHT {args.ght_code} non trouvé")
                return 1
            
            # Chercher l'établissement
            ej = session.exec(
                select(EntiteJuridique)
                .where(EntiteJuridique.ght_context_id == ght.id)
                .where(EntiteJuridique.finess_ej == args.finess)
            ).first()
            
            if not ej:
                print(f"❌ Établissement {args.finess} non trouvé")
                return 1
            
            # Créer le service d'export
            export_service = FHIRExportService(session, args.base_url)
            
            # Export de la structure
            if "structure" in requested_types:
                try:
                    print("📤 Export de la structure...")
                    bundle = export_service.export_structure(ej)
                    
                    output_file = output_dir / f"structure_{ej.finess_ej}.json"
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(bundle.dict(exclude_none=True), f, indent=2, ensure_ascii=False)
                    
                    print(f"  ✅ Structure exportée vers {output_file}")
                except Exception as e:
                    print(f"❌ Erreur lors de l'export de la structure: {e}")
                    return 1
            
            # Export des patients
            if "patients" in requested_types:
                try:
                    print("📤 Export des patients...")
                    bundle = export_service.export_patients(ej)
                    
                    output_file = output_dir / f"patients_{ej.finess_ej}.json"
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(bundle.dict(exclude_none=True), f, indent=2, ensure_ascii=False)
                    
                    print(f"  ✅ Patients exportés vers {output_file}")
                except Exception as e:
                    print(f"❌ Erreur lors de l'export des patients: {e}")
                    return 1
            
            # Export des venues
            if "venues" in requested_types:
                try:
                    print("📤 Export des venues...")
                    bundle = export_service.export_venues(ej)
                    
                    output_file = output_dir / f"venues_{ej.finess_ej}.json"
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(bundle.dict(exclude_none=True), f, indent=2, ensure_ascii=False)
                    
                    print(f"  ✅ Venues exportées vers {output_file}")
                except Exception as e:
                    print(f"❌ Erreur lors de l'export des venues: {e}")
                    return 1
            
            print("\n✅ Export terminé avec succès !")
            print(f"   GHT: {args.ght_code}")
            print(f"   EJ: {args.finess} ({ej.name})")
            print(f"   Fichiers exportés dans: {output_dir}")
            
            return 0
            
    except Exception as e:
        print(f"❌ Erreur globale: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())