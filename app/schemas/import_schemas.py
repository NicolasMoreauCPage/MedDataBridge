"""
Schémas Pydantic pour l'import Excel de structure
Validation des données par feuille Excel
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum


# ========================================
# TYPES & ENUMS
# ========================================

class ImportMode(str, Enum):
    """Mode d'import"""
    CREATE = "create"      # Créer uniquement (erreur si existe)
    UPDATE = "update"      # Mettre à jour uniquement (erreur si n'existe pas)
    REPLACE = "replace"    # Remplacer tout (dangereux)


class ImportAction(str, Enum):
    """Action à effectuer sur une entité"""
    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"
    ERROR = "error"


class ImportSeverity(str, Enum):
    """Niveau de sévérité des messages"""
    ERROR = "error"      # Bloque l'import
    WARNING = "warning"  # Avertissement mais continue
    INFO = "info"        # Informatif


# ========================================
# SCHEMAS PAR ENTITE
# ========================================

class ExcelRowEG(BaseModel):
    """Ligne Excel pour Entité Géographique"""
    code: str = Field(..., min_length=1, max_length=50)
    nom: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    code_postal: Optional[str] = None
    telephone: Optional[str] = None
    
    @validator('code')
    def code_must_be_uppercase(cls, v):
        return v.upper().strip()
    
    @validator('nom')
    def nom_must_be_stripped(cls, v):
        return v.strip()


class ExcelRowPole(BaseModel):
    """Ligne Excel pour Pôle"""
    code: str = Field(..., min_length=1, max_length=50)
    nom: str = Field(..., min_length=1, max_length=255)
    eg_code: str = Field(..., description="Code de l'EG parent")
    description: Optional[str] = None
    responsable: Optional[str] = None
    
    @validator('code', 'eg_code')
    def codes_must_be_uppercase(cls, v):
        return v.upper().strip()


class ExcelRowService(BaseModel):
    """Ligne Excel pour Service"""
    code: str = Field(..., min_length=1, max_length=50)
    nom: str = Field(..., min_length=1, max_length=255)
    pole_code: str = Field(..., description="Code du Pôle parent")
    type_service: Optional[str] = None
    description: Optional[str] = None
    responsable: Optional[str] = None
    
    @validator('code', 'pole_code')
    def codes_must_be_uppercase(cls, v):
        return v.upper().strip()


class ExcelRowUF(BaseModel):
    """Ligne Excel pour Unité Fonctionnelle"""
    code: str = Field(..., min_length=1, max_length=50)
    nom: str = Field(..., min_length=1, max_length=255)
    service_code: str = Field(..., description="Code du Service parent")
    type_activite: Optional[str] = None  # MCO, SSR, PSY, HAD
    capacite: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None
    
    @validator('code', 'service_code')
    def codes_must_be_uppercase(cls, v):
        return v.upper().strip()


class ExcelRowUH(BaseModel):
    """Ligne Excel pour Unité d'Hébergement"""
    code: str = Field(..., min_length=1, max_length=50)
    nom: str = Field(..., min_length=1, max_length=255)
    service_code: str = Field(..., description="Code du Service parent")
    capacite: Optional[int] = Field(None, ge=0)
    etage: Optional[str] = None
    
    @validator('code', 'service_code')
    def codes_must_be_uppercase(cls, v):
        return v.upper().strip()


class ExcelRowChambre(BaseModel):
    """Ligne Excel pour Chambre"""
    code: str = Field(..., min_length=1, max_length=50)
    nom: str = Field(..., min_length=1, max_length=255)
    uh_code: str = Field(..., description="Code de l'UH parent")
    capacite: Optional[int] = Field(None, ge=1, le=6)
    numero: Optional[str] = None
    
    @validator('code', 'uh_code')
    def codes_must_be_uppercase(cls, v):
        return v.upper().strip()


class ExcelRowLit(BaseModel):
    """Ligne Excel pour Lit"""
    code: str = Field(..., min_length=1, max_length=50)
    nom: str = Field(..., min_length=1, max_length=255)
    chambre_code: str = Field(..., description="Code de la Chambre parent")
    numero: Optional[str] = None
    
    @validator('code', 'chambre_code')
    def codes_must_be_uppercase(cls, v):
        return v.upper().strip()


# ========================================
# SCHEMAS DE PREVIEW
# ========================================

class ImportMessage(BaseModel):
    """Message d'erreur, avertissement ou info"""
    severity: ImportSeverity
    message: str
    entity_type: str
    entity_code: Optional[str] = None
    row_number: Optional[int] = None


class ImportEntityPreview(BaseModel):
    """Aperçu d'une entité à importer"""
    entity_type: str  # eg, pole, service, uf, uh, chambre, lit
    code: str
    nom: str
    action: ImportAction
    parent_code: Optional[str] = None
    row_number: int
    messages: List[ImportMessage] = []


class ImportPreview(BaseModel):
    """Résultat de la validation avant import"""
    mode: ImportMode
    total_rows: int
    to_create: List[ImportEntityPreview] = []
    to_update: List[ImportEntityPreview] = []
    to_skip: List[ImportEntityPreview] = []
    errors: List[ImportMessage] = []
    warnings: List[ImportMessage] = []
    
    @property
    def has_errors(self) -> bool:
        """Retourne True si des erreurs bloquantes existent"""
        return len(self.errors) > 0
    
    @property
    def can_proceed(self) -> bool:
        """Retourne True si l'import peut être confirmé"""
        return not self.has_errors


class ImportResult(BaseModel):
    """Résultat final de l'import"""
    success: bool
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    messages: List[ImportMessage] = []
    duration_seconds: float = 0.0
