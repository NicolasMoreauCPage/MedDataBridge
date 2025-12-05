#!/usr/bin/env python3
"""
HL7 Import Validator & Enricher
Valide et enrichit les messages HL7 à l'import selon le profil IHE PAM-FR

Règles P0:
1. MSH: sending_app, sending_facility obligatoires
2. A0X: ZBE segment obligatoire
3. Z99: ZBE-1 (movement ID) obligatoire
4. Format: pas de caractères invalides
"""

import re
from typing import Tuple, Optional, List, Dict
from dataclasses import dataclass
from enum import Enum


class ValidationResult(Enum):
    """Résultat de validation"""
    VALID = "VALID"
    FIXABLE = "FIXABLE"  # Peut être corrigé automatiquement
    REJECTED = "REJECTED"  # Doit être rejeté


@dataclass
class HL7ValidationReport:
    """Rapport de validation d'un message HL7"""
    message_id: str
    trigger: str
    status: ValidationResult
    errors: List[str]
    warnings: List[str]
    corrections_applied: List[str]
    corrected_message: Optional[str] = None


class HL7ImportValidator:
    """Validateur HL7 pour l'import selon profil PAM-FR"""
    
    def __init__(self, mode: str = "LENIENT"):
        """
        Args:
            mode: "STRICT" (production) ou "LENIENT" (import avec auto-correction)
        """
        self.mode = mode
        self.field_separator = "|"
        self.component_separator = "^"
    
    def validate_message(self, message: str) -> HL7ValidationReport:
        """
        Valide un message HL7 complet
        
        Args:
            message: Message HL7 (segments séparés par \r ou \n)
            
        Returns:
            HL7ValidationReport avec détails de validation
        """
        # Parse segments
        segments = self._parse_segments(message)
        if not segments:
            return HL7ValidationReport(
                message_id="UNKNOWN",
                trigger="?",
                status=ValidationResult.REJECTED,
                errors=["Format invalide - pas de segments HL7"],
                warnings=[],
                corrections_applied=[]
            )
        
        # Récupère MSH et MSH-9 (trigger)
        msh = segments.get("MSH", {})
        trigger = self._extract_trigger(msh)
        message_id = self._extract_message_id(msh)
        
        report = HL7ValidationReport(
            message_id=message_id,
            trigger=trigger,
            status=ValidationResult.VALID,
            errors=[],
            warnings=[],
            corrections_applied=[]
        )
        
        # Validation 1: MSH fields
        self._validate_msh(msh, report)
        
        # Validation 2: Segments requis selon trigger
        self._validate_required_segments(segments, trigger, report)
        
        # Validation 3: Format général
        self._validate_format(segments, report)
        
        # Détermine le statut AVANT correction
        if report.errors:
            report.status = ValidationResult.REJECTED if self.mode == "STRICT" else ValidationResult.FIXABLE
        
        # Correction si LENIENT mode et messages fixables
        if self.mode == "LENIENT" and report.status == ValidationResult.FIXABLE:
            report.corrected_message = self._apply_corrections(message, segments, report)
        
        return report
    
    def _parse_segments(self, message: str) -> Dict[str, Dict]:
        """Parse les segments HL7"""
        segments = {}
        lines = message.replace("\r", "\n").split("\n")
        
        for line in lines:
            if not line.strip():
                continue
            
            # Récupère le type de segment (3 premiers caractères)
            if len(line) < 3:
                continue
            
            segment_type = line[:3]
            fields = line.split(self.field_separator)
            
            segments[segment_type] = {
                "type": segment_type,
                "raw": line,
                "fields": fields
            }
        
        return segments
    
    def _extract_trigger(self, msh: Dict) -> str:
        """Extrait le trigger du segment MSH"""
        if not msh or "fields" not in msh:
            return "?"
        
        # MSH-9 est à l'index 9
        try:
            field_9 = msh["fields"][9] if len(msh["fields"]) > 9 else ""
            # Format: ADT^A01 ou SIU^S12
            parts = field_9.split(self.component_separator)
            return parts[1] if len(parts) > 1 else "?"
        except (IndexError, AttributeError):
            return "?"
    
    def _extract_message_id(self, msh: Dict) -> str:
        """Extrait l'ID du message du segment MSH"""
        if not msh or "fields" not in msh:
            return "UNKNOWN"
        
        # MSH-10 est à l'index 10
        try:
            return msh["fields"][10] if len(msh["fields"]) > 10 else "UNKNOWN"
        except (IndexError, AttributeError):
            return "UNKNOWN"
    
    def _validate_msh(self, msh: Dict, report: HL7ValidationReport) -> None:
        """Valide le segment MSH"""
        if not msh:
            report.errors.append("MSH segment manquant")
            return
        
        fields = msh.get("fields", [])
        
        # MSH-3: Sending Application (index 3)
        if len(fields) <= 3 or not fields[3]:
            report.errors.append("MSH-3 (Sending Application) manquant")
            report.corrections_applied.append("MSH-3 → sera généré")
        
        # MSH-4: Sending Facility (index 4)
        if len(fields) <= 4 or not fields[4]:
            report.errors.append("MSH-4 (Sending Facility) manquant")
            report.corrections_applied.append("MSH-4 → sera généré")
    
    def _validate_required_segments(self, segments: Dict, trigger: str, report: HL7ValidationReport) -> None:
        """Valide les segments requis selon le trigger"""
        
        # Messages de mouvement (A0X) requis ZBE
        if trigger.startswith("A0"):
            if "ZBE" not in segments:
                report.errors.append(f"ZBE segment manquant pour ADT^{trigger}")
                report.corrections_applied.append(f"ZBE → sera généré avec mouvement {self._movement_type(trigger)}")
        
        # Messages Z99 requis ZBE-1
        if trigger == "Z99":
            if "ZBE" not in segments:
                report.errors.append("Z99 message requires ZBE segment with movement ID")
                report.corrections_applied.append("ZBE-1 → sera généré")
            else:
                zbe = segments["ZBE"]
                fields = zbe.get("fields", [])
                if len(fields) <= 1 or not fields[1]:
                    report.errors.append("ZBE-1 (movement ID) manquant pour Z99")
                    report.corrections_applied.append("ZBE-1 → sera généré")
        
        # Messages de fusion (A40, A47) requis MRG
        if trigger in ["A40", "A47"]:
            if "MRG" not in segments:
                report.errors.append(f"MRG segment manquant pour ADT^{trigger} (fusion de patients)")
                # Pour A40/A47, on ne peut pas générer MRG (trop critique)
                report.corrections_applied.pop()  # Remove auto-fix
    
    def _validate_format(self, segments: Dict, report: HL7ValidationReport) -> None:
        """Valide le format général"""
        for segment_type, segment in segments.items():
            raw = segment.get("raw", "")
            
            # Vérifie les caractères invalides
            if not self._is_valid_hl7_format(raw):
                report.warnings.append(f"Segment {segment_type}: caractères potentiellement invalides")
    
    def _is_valid_hl7_format(self, segment: str) -> bool:
        """Vérifie si un segment a un format HL7 valide"""
        # Doit contenir au moins type + séparateur + données
        if len(segment) < 4:
            return False
        
        # Doit commencer par 3 lettres
        if not re.match(r"^[A-Z]{3}", segment):
            return False
        
        # Doit contenir le séparateur
        if self.field_separator not in segment:
            return False
        
        return True
    
    def _movement_type(self, trigger: str) -> str:
        """Retourne le type de mouvement IHE PAM pour un trigger"""
        mapping = {
            "A01": "ADMISSION",
            "A02": "TRANSFER",
            "A03": "DISCHARGE",
            "A04": "REGISTER",
            "A05": "PRE-ADMISSION",
            "A06": "CHANGE ATTENDING DOCTOR",
        }
        return mapping.get(trigger, "UNKNOWN")
    
    def _apply_corrections(self, message: str, segments: Dict, report: HL7ValidationReport) -> str:
        """Applique les corrections au message
        
        Reconstructs the entire message preserving all segments,
        correcting only those that are broken/missing fields
        """
        corrected_lines = []
        lines = message.replace("\r", "\n").split("\n")
        
        for line in lines:
            if not line.strip():
                continue
            
            segment_type = line[:3] if len(line) >= 3 else ""
            
            if segment_type == "MSH" and segment_type in segments:
                # Fix MSH
                corrected = self._fix_msh_segment(segments[segment_type], report.trigger)
                corrected_lines.append(corrected)
            elif segment_type == "ZBE" and segment_type in segments:
                # Fix ZBE
                corrected = self._fix_zbe_segment(segments[segment_type], report.trigger)
                corrected_lines.append(corrected)
            else:
                # Keep as-is
                corrected_lines.append(line)
        
        return "\r".join(corrected_lines)
    
    
    def _fix_msh_segment(self, segment: Dict, trigger: str) -> str:
        """Répare le segment MSH
        
        MSH has special structure after split:
        ['MSH', 'encoding', '', '', 'MSH-3', 'MSH-4', ...]
                ^field[1]              ^field[3] ^field[4]
        """
        raw = segment.get("raw", "")
        fields = segment.get("fields", [])
        
        # Ensure we have enough fields (MSH has min 12 fields)
        while len(fields) < 12:
            fields.append("")
        
        # Fix MSH-3 at fields[3]
        if not fields[3]:
            fields[3] = "MEDBRIDGEDATA"
        
        # Fix MSH-4 at fields[4]
        if not fields[4]:
            fields[4] = "IMPORT-SOURCE"
        
        # Reconstruct properly with encoding at position [1]
        reconstructed_parts = [fields[1]] + fields[2:]  # encoding + rest
        return "MSH|" + self.field_separator.join(reconstructed_parts)
    
    
    def _fix_zbe_segment(self, segment: Dict, trigger: str) -> str:
        """Répare le segment ZBE"""
        fields = segment.get("fields", [])
        
        # Complète les champs
        while len(fields) < 10:
            fields.append("")
        
        # ZBE-1: Movement ID (si manquant)
        if not fields[1]:
            import uuid
            fields[1] = str(uuid.uuid4())[:12]  # ID court
        
        # ZBE-2: Movement Type (si manquant)
        if not fields[2]:
            fields[2] = f"{self._movement_type(trigger)}^MOVEMENT^L^IHE_PAM_FR"
        
        return self.field_separator.join(fields)


class HL7ImportQualityReport:
    """Rapport d'analyse de qualité du lot d'import"""
    
    def __init__(self):
        self.total_messages = 0
        self.valid_messages = 0
        self.fixable_messages = 0
        self.rejected_messages = 0
        self.reports: List[HL7ValidationReport] = []
    
    def add_report(self, report: HL7ValidationReport) -> None:
        """Ajoute un rapport de validation"""
        self.reports.append(report)
        self.total_messages += 1
        
        if report.status == ValidationResult.VALID:
            self.valid_messages += 1
        elif report.status == ValidationResult.FIXABLE:
            self.fixable_messages += 1
        else:
            self.rejected_messages += 1
    
    def print_summary(self) -> None:
        """Affiche le résumé du rapport"""
        print("\n" + "="*80)
        print("📊 HL7 IMPORT QUALITY REPORT")
        print("="*80)
        
        print(f"\n📈 Statistiques:")
        print(f"   Total:     {self.total_messages} messages")
        print(f"   ✅ Valides: {self.valid_messages} ({self.valid_messages*100/max(1,self.total_messages):.1f}%)")
        print(f"   🔧 Fixables: {self.fixable_messages} ({self.fixable_messages*100/max(1,self.total_messages):.1f}%)")
        print(f"   ❌ Rejetés: {self.rejected_messages} ({self.rejected_messages*100/max(1,self.total_messages):.1f}%)")
        
        print(f"\n🎯 Erreurs courantes:")
        error_counts: Dict[str, int] = {}
        for report in self.reports:
            for error in report.errors:
                error_counts[error] = error_counts.get(error, 0) + 1
        
        for error, count in sorted(error_counts.items(), key=lambda x: -x[1])[:5]:
            print(f"   - {error}: {count} messages")
        
        print(f"\n🔧 Corrections applicables:")
        correction_counts: Dict[str, int] = {}
        for report in self.reports:
            for correction in report.corrections_applied:
                correction_counts[correction] = correction_counts.get(correction, 0) + 1
        
        for correction, count in sorted(correction_counts.items(), key=lambda x: -x[1])[:5]:
            print(f"   - {correction}: {count} messages")
        
        if self.rejected_messages > 0:
            print(f"\n❌ Messages rejetés:")
            for report in self.reports:
                if report.status == ValidationResult.REJECTED:
                    print(f"   [{report.message_id}] {report.trigger}: {report.errors}")
        
        print("\n" + "="*80 + "\n")


# Exemple d'utilisation
if __name__ == "__main__":
    import sys
    
    # Exemple de messages HL7 problématiques
    test_messages = [
        # Manque MSH-3 et MSH-4
        "MSH||^~\\&||||20240101|1234||ADT^A28|||2.5\rMSH|Field 1\rPID|1|123456",
        
        # A01 sans ZBE
        "MSH|^~\\&|APP|FAC|REC|FAC|20240101|1234||ADT^A01|||2.5\rPID|1|123456",
        
        # Z99 sans ZBE-1
        "MSH|^~\\&|APP|FAC|REC|FAC|20240101|1234||ADT^Z99|||2.5\rZBE|",
        
        # Format invalide
        "INVALID|||",
    ]
    
    validator = HL7ImportValidator(mode="LENIENT")
    quality_report = HL7ImportQualityReport()
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n📨 Message {i}:")
        report = validator.validate_message(message)
        quality_report.add_report(report)
        
        print(f"   Trigger: {report.trigger}")
        print(f"   Status: {report.status.value}")
        if report.errors:
            print(f"   Erreurs: {report.errors}")
        if report.corrections_applied:
            print(f"   Corrections: {report.corrections_applied}")
    
    quality_report.print_summary()
