"""Service de validation PAM pour les tests d'interfaces.

Ce service fournit des fonctionnalités de validation HL7 PAM
pour les tests d'interfaces GAM/GAP.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import re


@dataclass
class ValidationResult:
    """Résultat de validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class PAMValidator:
    """Validateur HL7 PAM pour les tests d'interfaces."""

    def __init__(self):
        self.required_segments = {
            'MSH': ['MSH.1', 'MSH.2', 'MSH.7', 'MSH.9', 'MSH.10', 'MSH.12'],
            'PID': ['PID.1', 'PID.3'],
            'PV1': ['PV1.1', 'PV1.2']
        }

        self.pam_message_types = {
            'ADT': ['A01', 'A02', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08',
                   'A11', 'A12', 'A13', 'A17', 'A21', 'A22', 'A28', 'A31'],
            'SIU': ['S12', 'S13', 'S14', 'S15', 'S22', 'S23']
        }

    def validate_message(self, parsed_message: Dict[str, Any]) -> ValidationResult:
        """
        Valide un message HL7 parsé selon les spécifications PAM.

        Args:
            parsed_message: Message HL7 parsé

        Returns:
            Résultat de validation
        """
        errors = []
        warnings = []

        # Validation de base des segments requis
        for segment_type, required_fields in self.required_segments.items():
            if segment_type not in parsed_message:
                errors.append(f"Segment {segment_type} manquant")
                continue

            segment = parsed_message[segment_type]
            for field in required_fields:
                if not self._has_field(segment, field):
                    errors.append(f"Champ requis {field} manquant dans {segment_type}")

        # Validation du type de message PAM
        if 'MSH' in parsed_message:
            msh = parsed_message['MSH']
            message_type = msh.get('9.1', '')
            trigger_event = msh.get('9.2', '')

            if message_type not in self.pam_message_types:
                warnings.append(f"Type de message {message_type} non standard PAM")
            elif trigger_event not in self.pam_message_types.get(message_type, []):
                warnings.append(f"Événement déclencheur {trigger_event} non standard pour {message_type}")

        # Validation des identifiants patient
        if 'PID' in parsed_message:
            pid = parsed_message['PID']
            patient_id = pid.get('3.1', '')
            if not patient_id:
                errors.append("Identifiant patient manquant (PID.3.1)")
            elif len(patient_id) < 3:
                warnings.append("Identifiant patient potentiellement trop court")

        # Validation des informations de séjour
        if 'PV1' in parsed_message:
            pv1 = parsed_message['PV1']
            patient_class = pv1.get('2', '')
            if patient_class not in ['I', 'O', 'E', 'P']:
                warnings.append(f"Classe patient {patient_class} non standard (attendu: I, O, E, P)")

        # Validation des dates
        date_fields = [
            ('MSH', '7', 'Date/heure du message'),
            ('PID', '7', 'Date de naissance'),
            ('PV1', '44', 'Date d\'admission')
        ]

        for segment_type, field_num, description in date_fields:
            if segment_type in parsed_message:
                segment = parsed_message[segment_type]
                date_value = segment.get(field_num, '')
                if date_value and not self._is_valid_hl7_date(date_value):
                    warnings.append(f"Format de date invalide pour {description}: {date_value}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _has_field(self, segment: Dict[str, Any], field_path: str) -> bool:
        """Vérifie si un champ existe dans un segment."""
        try:
            parts = field_path.split('.')
            if len(parts) == 2:
                field_num = parts[1]
                return field_num in segment and segment[field_num]
            return False
        except:
            return False

    def _is_valid_hl7_date(self, date_str: str) -> bool:
        """Vérifie si une date est au format HL7 valide."""
        # Formats HL7 courants: YYYYMMDDHHMMSS, YYYYMMDDHHMM, YYYYMMDD
        patterns = [
            r'^\d{8}$',      # YYYYMMDD
            r'^\d{12}$',     # YYYYMMDDHHMM
            r'^\d{14}$',     # YYYYMMDDHHMMSS
        ]

        return any(re.match(pattern, date_str) for pattern in patterns)


class FHIRValidator:
    """Validateur FHIR pour les tests d'interfaces."""

    def __init__(self):
        self.required_bundle_fields = ['resourceType', 'type', 'entry']
        self.supported_bundle_types = ['transaction', 'batch', 'collection', 'searchset']

    def validate_bundle(self, bundle: Dict[str, Any],
                       validate_references: bool = True,
                       check_encounters: bool = True) -> ValidationResult:
        """
        Valide un bundle FHIR.

        Args:
            bundle: Bundle FHIR à valider
            validate_references: Si True, valide les références internes
            check_encounters: Si True, vérifie la cohérence des encounters

        Returns:
            Résultat de validation
        """
        errors = []
        warnings = []

        # Validation de base du bundle
        for field in self.required_bundle_fields:
            if field not in bundle:
                errors.append(f"Champ requis manquant: {field}")

        if bundle.get('resourceType') != 'Bundle':
            errors.append("Le document doit être un Bundle FHIR")

        bundle_type = bundle.get('type', '')
        if bundle_type not in self.supported_bundle_types:
            warnings.append(f"Type de bundle non standard: {bundle_type}")

        # Validation des entrées
        entries = bundle.get('entry', [])
        if not entries:
            warnings.append("Bundle vide (aucune entrée)")

        # Validation des ressources individuelles
        for i, entry in enumerate(entries):
            if 'resource' not in entry:
                errors.append(f"Entrée {i}: ressource manquante")
                continue

            resource = entry['resource']
            resource_type = resource.get('resourceType', '')

            # Validation spécifique par type de ressource
            if resource_type == 'Patient':
                self._validate_patient_resource(resource, warnings, i)
            elif resource_type == 'Encounter':
                if check_encounters:
                    self._validate_encounter_resource(resource, warnings, i)
            elif resource_type == 'Observation':
                self._validate_observation_resource(resource, warnings, i)

        # Validation des références si demandée
        if validate_references:
            self._validate_bundle_references(bundle, errors, warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _validate_patient_resource(self, patient: Dict[str, Any],
                                 warnings: List[str], entry_index: int):
        """Valide une ressource Patient."""
        if 'identifier' not in patient:
            warnings.append(f"Patient {entry_index}: pas d'identifiant")

        if 'name' not in patient:
            warnings.append(f"Patient {entry_index}: nom manquant")

    def _validate_encounter_resource(self, encounter: Dict[str, Any],
                                   warnings: List[str], entry_index: int):
        """Valide une ressource Encounter."""
        if 'status' not in encounter:
            warnings.append(f"Encounter {entry_index}: statut manquant")

        if 'class' not in encounter:
            warnings.append(f"Encounter {entry_index}: classe manquante")

        # Vérification des dates
        period = encounter.get('period', {})
        if 'start' not in period:
            warnings.append(f"Encounter {entry_index}: date de début manquante")

    def _validate_observation_resource(self, observation: Dict[str, Any],
                                     warnings: List[str], entry_index: int):
        """Valide une ressource Observation."""
        if 'status' not in observation:
            warnings.append(f"Observation {entry_index}: statut manquant")

        if 'code' not in observation:
            warnings.append(f"Observation {entry_index}: code manquant")

        if 'subject' not in observation:
            warnings.append(f"Observation {entry_index}: sujet manquant")

    def _validate_bundle_references(self, bundle: Dict[str, Any],
                                  errors: List[str], warnings: List[str]):
        """Valide les références internes du bundle."""
        entries = bundle.get('entry', [])
        resources_by_id = {}

        # Indexer les ressources par ID
        for entry in entries:
            resource = entry.get('resource', {})
            resource_id = resource.get('id')
            resource_type = resource.get('resourceType')

            if resource_id and resource_type:
                full_id = f"{resource_type}/{resource_id}"
                resources_by_id[full_id] = resource

        # Vérifier les références
        for entry in entries:
            resource = entry.get('resource', {})
            self._check_references_in_resource(resource, resources_by_id, warnings)


    def _check_references_in_resource(self, resource: Dict[str, Any],
                                    resources_by_id: Dict[str, Any],
                                    warnings: List[str]):
        """Vérifie les références dans une ressource."""
        def check_reference(ref_obj):
            if isinstance(ref_obj, dict):
                reference = ref_obj.get('reference', '')
                if reference and reference not in resources_by_id:
                    warnings.append(f"Référence introuvable: {reference}")

        # Fonction récursive pour parcourir tous les champs
        def walk_object(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == 'reference' and isinstance(value, str):
                        if value not in resources_by_id:
                            warnings.append(f"Référence introuvable: {value}")
                    elif isinstance(value, (dict, list)):
                        walk_object(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk_object(item)

        walk_object(resource)