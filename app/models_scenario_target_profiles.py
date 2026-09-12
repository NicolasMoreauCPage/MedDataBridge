"""Configuration clinique des scénarios par système destinataire.

Un ``target_system_key`` représente un logiciel partenaire, potentiellement
accessible avec plusieurs transports (MLLP, HPRIM fichier, FHIR). Le profil
porte donc les UF et praticiens à projeter dans les messages qui lui sont
destinés, sans dupliquer cette configuration par endpoint technique.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class ScenarioTargetProfile(SQLModel, table=True):
    """Profil fonctionnel réutilisé par tous les endpoints d'une cible."""

    __tablename__ = "scenariotargetprofile"

    id: Optional[int] = Field(default=None, primary_key=True)
    target_system_key: str = Field(index=True, unique=True, max_length=120)
    name: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = None
    # La structure locale utilisée pour les replis automatiques. Lorsque non
    # renseignée, celle de l'endpoint puis celle du scénario est utilisée.
    entite_juridique_id: Optional[int] = Field(default=None, foreign_key="entitejuridique.id", index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScenarioTargetLocation(SQLModel, table=True):
    """Association d'un rôle clinique à une UF et, optionnellement, un médecin.

    Le médecin explicite est prioritaire. Si absent, le médecin responsable de
    l'UF est employé. Les rôles sont volontairement textuels pour préserver la
    compatibilité avec les scénarios historiques et permettre leur extension.
    """

    __tablename__ = "scenariotargetlocation"
    __table_args__ = (
        UniqueConstraint("profile_id", "role", name="uq_scenario_target_location_role"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="scenariotargetprofile.id", index=True)
    role: str = Field(index=True, max_length=48)
    unite_fonctionnelle_id: Optional[int] = Field(default=None, foreign_key="unitefonctionnelle.id", index=True)
    medecin_responsable_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id", index=True)
    room: Optional[str] = Field(default=None, max_length=20)
    bed: Optional[str] = Field(default=None, max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
