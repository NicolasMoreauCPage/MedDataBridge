"""
Modèles pour le module Analytics (Mode Gestionnaire)
"""
from datetime import date, datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum


class AlertType(str, Enum):
    """Types d'alertes de gestion"""
    SUROCCUPATION = "suroccupation"  # > 100% occupation
    TENSION = "tension"  # > 95% occupation
    SOUS_UTILISATION = "sous_utilisation"  # < 50% occupation pendant 7j
    DMS_ANORMALE = "dms_anormale"  # DMS > 150% médiane


class AlertSeverity(str, Enum):
    """Niveaux de sévérité des alertes"""
    HIGH = "high"  # Rouge - Action immédiate requise
    MEDIUM = "medium"  # Jaune - Surveillance renforcée
    LOW = "low"  # Bleu - Information


class OccupationSnapshot(SQLModel, table=True):
    """
    Snapshot quotidien de l'occupation des lits pour historique et analytics.
    
    Permet de calculer les KPIs sur une période sans recalculer depuis les mouvements.
    Un snapshot est créé chaque jour (ex: job nocturne 00:30) pour chaque lit.
    """
    __tablename__ = "occupation_snapshots"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Date du snapshot
    snapshot_date: date = Field(index=True)
    
    # Référence au lit
    lit_id: int = Field(foreign_key="lit.id", index=True)
    
    # État d'occupation au moment du snapshot
    is_occupied: bool = Field(default=False)
    
    # Informations contextuelles (dénormalisées pour performances)
    eg_id: int = Field(foreign_key="entitegeographique.id", index=True)
    uf_id: Optional[int] = Field(default=None, foreign_key="unitefonctionnelle.id")
    service_id: Optional[int] = Field(default=None, foreign_key="service.id")
    pole_id: Optional[int] = Field(default=None, foreign_key="pole.id")
    
    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relations (optionnelles, pour faciliter les requêtes)
    # lit: "Lit" = Relationship(back_populates="occupation_snapshots")


class AlertRule(SQLModel, table=True):
    """
    Configuration des règles d'alerte pour le mode gestionnaire.
    
    Définit les seuils et conditions qui déclenchent des alertes.
    Peut être globale (eg_id=None, um_code=None) ou spécifique à un EG/UM.
    """
    __tablename__ = "alert_rules"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Type d'alerte
    alert_type: AlertType = Field(index=True)
    
    # Seuil déclencheur (interprétation dépend du type)
    # Ex: suroccupation → 100.0 = 100%, sous_utilisation → 50.0 = 50%
    threshold_value: float = Field(ge=0.0, le=200.0)
    
    # Sévérité associée
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM)
    
    # Périmètre (si null = s'applique à tous)
    eg_id: Optional[int] = Field(default=None, foreign_key="entitegeographique.id", index=True)
    um_code: Optional[str] = Field(default=None, max_length=10)  # MCO, SSR, PSY, HAD
    
    # Activation
    is_active: bool = Field(default=True, index=True)
    
    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None, max_length=100)  # Username
    
    # Description personnalisée (optionnel)
    description: Optional[str] = Field(default=None, max_length=500)


class ComputedAlert(SQLModel):
    """
    Modèle Pydantic (non-table) pour représenter une alerte calculée.
    
    Généré à la volée par l'endpoint /api/analytics/alerts en comparant
    les données réelles avec les AlertRule actives.
    """
    alert_type: AlertType
    severity: AlertSeverity
    
    # Entité concernée
    entity_type: str  # "service", "uf", "pole"
    entity_id: int
    entity_name: str
    
    # Valeur actuelle vs seuil
    current_value: float
    threshold_value: float
    
    # Message explicatif
    message: str
    
    # Timestamp de génération
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# Schémas Pydantic pour les réponses API (non-tables)

class KpiResponse(SQLModel):
    """Réponse pour l'endpoint /api/analytics/kpis"""
    
    # Taux d'occupation (%)
    occupation_rate: float = Field(ge=0.0, le=200.0)
    occupation_trend: Optional[float] = None  # +5% = 5.0, -3% = -3.0
    
    # Durée Moyenne de Séjour (jours)
    dms: float = Field(ge=0.0)
    dms_trend: Optional[float] = None
    
    # Taux de rotation (admissions/lits)
    rotation_rate: float = Field(ge=0.0)
    rotation_trend: Optional[float] = None
    
    # Capacité disponible
    available_beds: int = Field(ge=0)
    total_beds: int = Field(ge=0)
    
    # Taux d'ouverture lits (lits ouverts / lits installés)
    beds_opening_rate: float = Field(ge=0.0, le=100.0)
    
    # Période de référence
    period: str  # "7d", "30d", "1y"
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class CapacityByServiceResponse(SQLModel):
    """Capacité et occupation par service"""
    service_id: int
    service_name: str
    service_code: Optional[str] = None
    
    total_beds: int
    occupied_beds: int
    occupation_rate: float  # %
    
    # Code couleur pour UI
    status_color: str  # "green", "yellow", "red"


class CapacityByUmResponse(SQLModel):
    """Répartition capacité par type UM"""
    um_code: str  # MCO, SSR, PSY, HAD
    um_label: str
    
    total_beds: int
    occupied_beds: int
    occupation_rate: float  # %
