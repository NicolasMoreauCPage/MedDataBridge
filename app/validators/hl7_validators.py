"""
Validateurs pour les messages HL7.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import re

@dataclass
class ValidationError:
    """Erreur de validation avec contexte."""
    message: str
    segment: Optional[str] = None
    field: Optional[str] = None
    value: Optional[str] = None
    line_number: Optional[int] = None

@dataclass
class ValidationResult:
    """Résultat de validation avec erreurs et avertissements."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]

class HL7Validator:
    """Validateur de base pour les messages HL7."""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
    
    def validate_segment_exists(self, segments: List[str], segment_type: str, required: bool = True) -> bool:
        """Vérifie la présence d'un segment."""
        found = any(s.startswith(f"{segment_type}|") for s in segments)
        if required and not found:
            self.errors.append(ValidationError(
                message=f"Segment {segment_type} obligatoire manquant",
                segment=segment_type
            ))
        return found

    def validate_field_not_empty(self, field_value: str, segment: str, field_name: str, field_position: int) -> bool:
        """Vérifie qu'un champ n'est pas vide."""
        if not field_value or field_value.isspace():
            self.errors.append(ValidationError(
                message=f"Champ {field_name} vide",
                segment=segment,
                field=f"F{field_position}",
                value=field_value
            ))
            return False
        return True

    def validate_datetime(self, value: str, format: str = "%Y%m%d%H%M%S") -> bool:
        """Valide un format de date/heure."""
        try:
            datetime.strptime(value, format)
            return True
        except ValueError:
            return False

    def get_field(self, segment: str, position: int) -> Tuple[str, List[str]]:
        """Extrait un champ et ses composants d'un segment."""
        fields = segment.split("|")
        if position < len(fields):
            value = fields[position]
            components = value.split("^") if value else []
            return value, components
        return "", []

class PAMValidator(HL7Validator):
    """Validateur spécifique pour les messages PAM."""
    
    def __init__(self):
        super().__init__()
        self.required_segments = ["MSH", "PID", "PV1"]
    
    def validate_message(self, content: str) -> ValidationResult:
        """Valide un message PAM complet."""
        segments = content.replace("\r\n", "\r").replace("\n", "\r").split("\r")
        
        # Vérifier segments obligatoires
        for segment_type in self.required_segments:
            self.validate_segment_exists(segments, segment_type)
        
        # Valider chaque segment
        for i, segment in enumerate(segments, 1):
            if not segment.strip():
                continue
                
            if segment.startswith("PID|"):
                self.validate_pid_segment(segment, i)
            elif segment.startswith("PV1|"):
                self.validate_pv1_segment(segment, i)
            elif segment.startswith("ZBE|"):
                self.validate_zbe_segment(segment, i)
        
        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings
        )
    
    def validate_pid_segment(self, segment: str, line: int):
        """Valide un segment PID."""
        # IPP (champ 3)
        ipp, ipp_components = self.get_field(segment, 3)
        if not self.validate_field_not_empty(ipp, "PID", "IPP", 3):
            return
            
        # Nom/Prénom (champ 5)
        name, name_components = self.get_field(segment, 5)
        if self.validate_field_not_empty(name, "PID", "Nom", 5):
            if len(name_components) < 2:
                self.warnings.append(ValidationError(
                    message="Prénom manquant",
                    segment="PID",
                    field="F5",
                    value=name,
                    line_number=line
                ))
    
    def validate_pv1_segment(self, segment: str, line: int):
        """Valide un segment PV1."""
        # Numéro de venue (champ 19)
        visit_nb, _ = self.get_field(segment, 19)
        self.validate_field_not_empty(visit_nb, "PV1", "Numéro de venue", 19)
        
        # UF (champ 3)
        uf, _ = self.get_field(segment, 3)
        if not uf:
            self.warnings.append(ValidationError(
                message="UF d'hébergement non renseignée",
                segment="PV1",
                field="F3",
                line_number=line
            ))
    
    def validate_zbe_segment(self, segment: str, line: int):
        """Valide un segment ZBE."""
        # Code mouvement (champ 1)
        mvt_code, _ = self.get_field(segment, 1)
        if self.validate_field_not_empty(mvt_code, "ZBE", "Code mouvement", 1):
            if mvt_code not in ["ADMIT", "TRANSFER", "DISCHARGE"]:
                self.warnings.append(ValidationError(
                    message=f"Code mouvement inconnu: {mvt_code}",
                    segment="ZBE",
                    field="F1",
                    value=mvt_code,
                    line_number=line
                ))
        
        # Date/heure (champ 6)
        datetime_value, _ = self.get_field(segment, 6)
        if self.validate_field_not_empty(datetime_value, "ZBE", "Date/Heure", 6):
            if not self.validate_datetime(datetime_value):
                self.errors.append(ValidationError(
                    message="Format de date/heure invalide",
                    segment="ZBE",
                    field="F6",
                    value=datetime_value,
                    line_number=line
                ))

class MFNValidator(HL7Validator):
    """Validateur spécifique pour les messages MFN."""
    
    def __init__(self):
        super().__init__()
        self.required_segments = ["MSH", "MFI"]
        self.valid_loc_types = {
            "ETBL_GRPQ", "PL", "D", "UF", "UH", "CH", "LIT"
        }
    
    def validate_message(self, content: str) -> ValidationResult:
        """Valide un message MFN complet."""
        segments = content.replace("\r\n", "\r").replace("\n", "\r").split("\r")
        
        # Vérifier segments obligatoires
        for segment_type in self.required_segments:
            self.validate_segment_exists(segments, segment_type)
        
        current_loc = None
        
        # Valider chaque segment
        for i, segment in enumerate(segments, 1):
            if not segment.strip():
                continue
                
            if segment.startswith("LOC|"):
                current_loc = self.validate_loc_segment(segment, i)
            elif segment.startswith("LCH|"):
                self.validate_lch_segment(segment, i, current_loc)
        
        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings
        )
    
    def validate_loc_segment(self, segment: str, line: int) -> Optional[str]:
        """Valide un segment LOC."""
        # Identifiant (champ 1)
        loc_id, _ = self.get_field(segment, 1)
        if not self.validate_field_not_empty(loc_id, "LOC", "Identifiant", 1):
            return None
            
        # Type (champ 3)
        loc_type, _ = self.get_field(segment, 3)
        if self.validate_field_not_empty(loc_type, "LOC", "Type", 3):
            if loc_type not in self.valid_loc_types:
                self.errors.append(ValidationError(
                    message=f"Type de localisation invalide: {loc_type}",
                    segment="LOC",
                    field="F3",
                    value=loc_type,
                    line_number=line
                ))
                return None
        
        return loc_type
    
    def validate_lch_segment(self, segment: str, line: int, current_loc: Optional[str]):
        """Valide un segment LCH."""
        if not current_loc:
            self.errors.append(ValidationError(
                message="Segment LCH sans LOC parent valide",
                segment="LCH",
                line_number=line
            ))
            return
        
        # Code attribut (champ 3)
        attr_code, attr_components = self.get_field(segment, 3)
        if not attr_components:
            self.warnings.append(ValidationError(
                message="Code attribut mal formaté",
                segment="LCH",
                field="F3",
                value=attr_code,
                line_number=line
            ))
        
        # Valeur (champ 4)
        value, _ = self.get_field(segment, 4)
        self.validate_field_not_empty(value, "LCH", "Valeur", 4)