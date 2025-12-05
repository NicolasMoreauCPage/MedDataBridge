#!/usr/bin/env python3
"""
HL7 Import Pipeline with Validation
Intègre le validateur dans le pipeline d'import des scénarios

Utilisation:
    python3 validate_hl7_imports.py --input <file> --mode LENIENT|STRICT --output <dir>
"""

import argparse
import sys
from pathlib import Path
from hl7_import_validator import HL7ImportValidator, HL7ImportQualityReport, ValidationResult


def validate_scenario_file(file_path: str, mode: str = "LENIENT") -> HL7ImportQualityReport:
    """
    Valide tous les messages HL7 d'un fichier de scénario
    
    Args:
        file_path: Chemin du fichier HL7
        mode: Mode de validation (STRICT ou LENIENT)
        
    Returns:
        Rapport de qualité
    """
    validator = HL7ImportValidator(mode=mode)
    report = HL7ImportQualityReport()
    
    print(f"\n📁 Validation du fichier: {file_path}")
    print(f"   Mode: {mode}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Parse les messages (séparés par \n\n ou une autre délimitation)
    messages = content.strip().split("\n\n")
    
    for i, message in enumerate(messages, 1):
        if not message.strip():
            continue
        
        validation_report = validator.validate_message(message)
        report.add_report(validation_report)
    
    return report


def apply_corrections(file_path: str, output_dir: str) -> str:
    """
    Applique les corrections et exporte les messages corrigés
    
    Args:
        file_path: Chemin du fichier source
        output_dir: Répertoire de sortie
        
    Returns:
        Chemin du fichier corrigé
    """
    validator = HL7ImportValidator(mode="LENIENT")
    output_path = Path(output_dir) / f"{Path(file_path).stem}_CORRECTED.txt"
    
    print(f"\n🔧 Application des corrections...")
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    messages = content.strip().split("\n\n")
    corrected_messages = []
    
    for i, message in enumerate(messages, 1):
        if not message.strip():
            continue
        
        report = validator.validate_message(message)
        
        if report.status == ValidationResult.FIXABLE and report.corrected_message:
            corrected_messages.append(report.corrected_message)
            print(f"   ✅ Message {i} ({report.trigger}): corrigé")
        else:
            corrected_messages.append(message)
            print(f"   {'✅' if report.status == ValidationResult.VALID else '❌'} Message {i} ({report.trigger}): {report.status.value}")
    
    # Exporte les messages corrigés
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(corrected_messages))
    
    print(f"   ✅ Fichier corrigé exporté: {output_path}")
    return str(output_path)


def generate_correction_report(file_path: str, output_dir: str) -> None:
    """
    Génère un rapport détaillé de correction
    
    Args:
        file_path: Chemin du fichier
        output_dir: Répertoire de sortie
    """
    validator = HL7ImportValidator(mode="LENIENT")
    report_path = Path(output_dir) / f"{Path(file_path).stem}_VALIDATION_REPORT.md"
    
    print(f"\n📋 Génération du rapport de correction...")
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    messages = content.strip().split("\n\n")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# HL7 Import Validation & Correction Report\n\n")
        f.write(f"**File**: {Path(file_path).name}\n")
        f.write(f"**Total Messages**: {len(messages)}\n\n")
        
        f.write("## Détails par Message\n\n")
        
        for i, message in enumerate(messages, 1):
            if not message.strip():
                continue
            
            report = validator.validate_message(message)
            
            f.write(f"### Message {i}: {report.trigger}\n\n")
            f.write(f"- **ID**: {report.message_id}\n")
            f.write(f"- **Status**: {report.status.value}\n")
            
            if report.errors:
                f.write(f"- **Erreurs**:\n")
                for error in report.errors:
                    f.write(f"  - {error}\n")
            
            if report.corrections_applied:
                f.write(f"- **Corrections applicables**:\n")
                for correction in report.corrections_applied:
                    f.write(f"  - {correction}\n")
            
            f.write("\n")
        
        # Résumé
        f.write("## Résumé\n\n")
        valid = sum(1 for r in [validator.validate_message(m) for m in messages if m.strip()] 
                   if r.status == ValidationResult.VALID)
        fixable = sum(1 for r in [validator.validate_message(m) for m in messages if m.strip()] 
                     if r.status == ValidationResult.FIXABLE)
        rejected = sum(1 for r in [validator.validate_message(m) for m in messages if m.strip()] 
                      if r.status == ValidationResult.REJECTED)
        
        f.write(f"- ✅ Valides: {valid}\n")
        f.write(f"- 🔧 Fixables: {fixable}\n")
        f.write(f"- ❌ Rejetés: {rejected}\n")
    
    print(f"   ✅ Rapport exporté: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="HL7 Import Validator - Valide et corrige les HL7 à l'import"
    )
    parser.add_argument("--input", "-i", required=True, help="Fichier HL7 source")
    parser.add_argument("--mode", "-m", choices=["STRICT", "LENIENT"], default="LENIENT",
                       help="Mode de validation (STRICT=rejets, LENIENT=corrections)")
    parser.add_argument("--output", "-o", default=".", help="Répertoire de sortie")
    parser.add_argument("--fix", action="store_true", help="Appliquer les corrections")
    parser.add_argument("--report", action="store_true", help="Générer un rapport détaillé")
    
    args = parser.parse_args()
    
    # Valide que le fichier existe
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Erreur: Fichier non trouvé: {args.input}")
        sys.exit(1)
    
    # Crée le répertoire de sortie
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Étape 1: Valide les messages
    quality_report = validate_scenario_file(str(input_path), mode=args.mode)
    quality_report.print_summary()
    
    # Étape 2: Applique les corrections si demandé
    if args.fix:
        corrected_file = apply_corrections(str(input_path), str(output_dir))
        print(f"\n✅ Fichier corrigé: {corrected_file}")
    
    # Étape 3: Génère un rapport si demandé
    if args.report:
        generate_correction_report(str(input_path), str(output_dir))
    
    # Exit code basé sur le nombre de rejetés
    if quality_report.rejected_messages > 0:
        print(f"\n⚠️ {quality_report.rejected_messages} messages rejetés")
        if args.mode == "STRICT":
            sys.exit(1)


if __name__ == "__main__":
    main()
