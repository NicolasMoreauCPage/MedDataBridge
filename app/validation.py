"""
Système de validation et sanitisation des données d'entrée pour MedData Bridge.

Fournit des validateurs réutilisables pour les données utilisateur, avec sanitisation
automatique et validation de sécurité.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# Patterns de validation courants
PATTERNS = {
    "email": re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
    "phone_fr": re.compile(r'^(\+33|0)[1-9](\d{2}){4}$'),
    "postal_code_fr": re.compile(r'^\d{5}$'),
    "nss_fr": re.compile(r'^\d{13}$'),  # Numéro de sécurité sociale français
    "hl7_datetime": re.compile(r'^\d{14}(\.\d{1,4})?$'),  # Format HL7 datetime
    "fhir_id": re.compile(r'^[A-Za-z0-9\-\.]{1,64}$'),  # FHIR ID format
    "safe_string": re.compile(r'^[a-zA-Z0-9\s\-_\.]+$'),  # Chaîne sûre sans caractères spéciaux
}

# Liste des mots-clés SQL dangereux
SQL_KEYWORDS = {
    'select', 'insert', 'update', 'delete', 'drop', 'create', 'alter',
    'exec', 'execute', 'union', 'join', 'where', 'from', 'having',
    'group', 'order', 'limit', 'script', 'eval', 'system'
}


class ValidationError(Exception):
    """Erreur de validation personnalisée avec détails."""

    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"{field}: {message}")


class DataSanitizer:
    """Utilitaire pour nettoyer et sécuriser les données d'entrée."""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Nettoie une chaîne de caractères."""
        if not isinstance(value, str):
            value = str(value)

        # Supprimer les caractères de contrôle
        value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)

        # Échapper les caractères HTML dangereux
        value = value.replace('&', '&amp;')
        value = value.replace('<', '&lt;')
        value = value.replace('>', '&gt;')
        value = value.replace('"', '&quot;')
        value = value.replace("'", '&#x27;')

        # Limiter la longueur
        if len(value) > max_length:
            value = value[:max_length] + '...'

        return value.strip()

    @staticmethod
    def sanitize_sql_like(value: str) -> str:
        """Nettoie une valeur pour utilisation dans LIKE SQL."""
        if not isinstance(value, str):
            value = str(value)

        # Échapper les caractères spéciaux SQL LIKE
        value = value.replace('%', '\\%')
        value = value.replace('_', '\\_')
        value = value.replace('[', '\\[')

        return value

    @staticmethod
    def check_sql_injection(value: str) -> bool:
        """Vérifie si une valeur contient des patterns d'injection SQL."""
        if not isinstance(value, str):
            return False

        value_lower = value.lower()
        return any(keyword in value_lower for keyword in SQL_KEYWORDS)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Nettoie un nom de fichier."""
        if not isinstance(filename, str):
            filename = str(filename)

        # Supprimer les caractères dangereux
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)

        # Limiter la longueur
        if len(filename) > 255:
            filename = filename[:255]

        return filename or "unnamed_file"


class BaseValidatedModel(BaseModel):
    """Modèle Pydantic de base avec validation étendue."""

    @field_validator('*', mode='before')
    @classmethod
    def sanitize_inputs(cls, v):
        """Sanitisation automatique de tous les champs string."""
        if isinstance(v, str):
            # Vérifier les injections SQL
            if DataSanitizer.check_sql_injection(v):
                raise ValueError("Contenu potentiellement dangereux détecté")
            # Sanitiser les chaînes
            return DataSanitizer.sanitize_string(v)
        return v


# Modèles de validation spécifiques aux cas d'usage MedData Bridge
class PatientSearchRequest(BaseValidatedModel):
    """Requête de recherche de patients avec validation."""

    query: str = Field(..., min_length=1, max_length=100)
    limit: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0)
    search_fields: Optional[List[str]] = Field(None)

    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('La requête doit contenir au moins 2 caractères')
        return v

    @field_validator('search_fields')
    @classmethod
    def validate_search_fields(cls, v):
        if v:
            allowed_fields = {'nom', 'prenom', 'nss', 'ipp', 'date_naissance'}
            invalid_fields = set(v) - allowed_fields
            if invalid_fields:
                raise ValueError(f'Champs de recherche invalides: {invalid_fields}')
        return v


class FHIRResourceRequest(BaseValidatedModel):
    """Requête de ressource FHIR avec validation."""

    resource_type: str = Field(..., pattern=r'^[A-Z][a-zA-Z]+$')
    resource_id: Optional[str] = Field(None, pattern=PATTERNS['fhir_id'])
    patient_id: Optional[str] = Field(None, pattern=PATTERNS['fhir_id'])

    @field_validator('resource_type')
    @classmethod
    def validate_resource_type(cls, v):
        allowed_types = {
            'Patient', 'Encounter', 'Observation', 'Condition',
            'Medication', 'AllergyIntolerance', 'Procedure'
        }
        if v not in allowed_types:
            raise ValueError(f'Type de ressource non supporté: {v}')
        return v


class HL7MessageRequest(BaseValidatedModel):
    """Requête de message HL7 avec validation."""

    message_type: str = Field(..., pattern=r'^[A-Z]{3}\^[A-Z0-9]{3}$')
    content: str = Field(..., max_length=10000)
    patient_id: Optional[str] = Field(None, pattern=PATTERNS['fhir_id'])

    @field_validator('content')
    @classmethod
    def validate_hl7_content(cls, v):
        # Vérifications basiques du format HL7
        if not v.startswith('MSH|'):
            raise ValueError('Message HL7 invalide (doit commencer par MSH|)')

        # Vérifier la présence des segments de base
        required_segments = ['MSH', 'PID']
        for segment in required_segments:
            if f'\n{segment}|' not in v and not v.startswith(f'{segment}|'):
                raise ValueError(f'Segment requis manquant: {segment}')

        return v


class FileUploadRequest(BaseValidatedModel):
    """Requête d'upload de fichier avec validation."""

    filename: str = Field(..., max_length=255)
    content_type: str = Field(...)
    size: int = Field(..., gt=0, le=10*1024*1024)  # Max 10MB

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        sanitized = DataSanitizer.sanitize_filename(v)
        if sanitized != v:
            logger.warning(f"Nom de fichier sanitizé: {v} -> {sanitized}")
        return sanitized

    @field_validator('content_type')
    @classmethod
    def validate_content_type(cls, v):
        allowed_types = {
            'text/plain', 'text/csv', 'application/json', 'application/xml',
            'text/xml', 'application/octet-stream'
        }
        if v not in allowed_types:
            raise ValueError(f'Type de contenu non autorisé: {v}')
        return v


# Validateurs utilitaires pour les routeurs
def validate_and_sanitize(data: Dict[str, Any], model_class) -> BaseModel:
    """
    Valide et sanitise des données avec un modèle Pydantic.

    Args:
        data: Données brutes à valider
        model_class: Classe de modèle Pydantic

    Returns:
        Instance validée du modèle

    Raises:
        ValidationError: Si la validation échoue
    """
    try:
        return model_class(**data)
    except ValidationError as e:
        # Reformater les erreurs pour plus de clarté
        errors = []
        for error in e.errors():
            field = '.'.join(str(loc) for loc in error['loc'])
            message = error['msg']
            errors.append(f"{field}: {message}")

        raise ValidationError('validation', '; '.join(errors))


def safe_query_param(value: str, max_length: int = 100) -> str:
    """
    Sanitise un paramètre de requête pour utilisation sécurisée.

    Args:
        value: Valeur du paramètre
        max_length: Longueur maximale autorisée

    Returns:
        Valeur sanitizée
    """
    if not isinstance(value, str):
        value = str(value)

    # Sanitisation basique
    value = DataSanitizer.sanitize_string(value, max_length)

    # Vérification injection SQL
    if DataSanitizer.check_sql_injection(value):
        logger.warning(f"Tentative d'injection SQL détectée: {value}")
        raise ValidationError('query_param', 'Paramètre de requête invalide')

    return value


# Fonction de validation pour les middlewares
async def validate_request_data(request_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valide des données de requête contre un schéma simple.

    Args:
        request_data: Données de la requête
        schema: Schéma de validation simple

    Returns:
        Données validées

    Raises:
        ValidationError: Si la validation échoue
    """
    validated = {}

    for field, rules in schema.items():
        value = request_data.get(field)

        # Champ requis
        if rules.get('required', False) and value is None:
            raise ValidationError(field, 'Champ requis')

        if value is not None:
            # Type
            expected_type = rules.get('type')
            if expected_type and not isinstance(value, expected_type):
                try:
                    value = expected_type(value)
                except (ValueError, TypeError):
                    raise ValidationError(field, f'Type attendu: {expected_type.__name__}')

            # Longueur minimale/maximale pour les chaînes
            if isinstance(value, str):
                min_len = rules.get('min_length')
                max_len = rules.get('max_length', 1000)

                if min_len and len(value) < min_len:
                    raise ValidationError(field, f'Longueur minimale: {min_len}')

                if len(value) > max_len:
                    raise ValidationError(field, f'Longueur maximale: {max_len}')

                # Pattern
                pattern = rules.get('pattern')
                if pattern and not re.match(pattern, value):
                    raise ValidationError(field, 'Format invalide')

            # Valeurs autorisées
            allowed_values = rules.get('allowed_values')
            if allowed_values and value not in allowed_values:
                raise ValidationError(field, f'Valeur non autorisée: {value}')

            validated[field] = value

    return validated