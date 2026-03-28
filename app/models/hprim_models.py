"""Persistance SQL dédiée aux échanges HPRIM."""

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class HprimMessage(SQLModel, table=True):
    """Message HPRIM archivé pour émission, roundtrip ou réception."""

    message_id: str = Field(primary_key=True, index=True)
    type_message: str = Field(index=True)
    direction: str = Field(default="generated", index=True)
    status: str = Field(default="stored", index=True)
    patient_id: Optional[str] = Field(default=None, index=True)
    emetteur_id: Optional[str] = Field(default=None, index=True)
    destinataire_id: Optional[str] = Field(default=None, index=True)
    filename: Optional[str] = Field(default=None, index=True)
    source: Optional[str] = Field(default=None)
    xml_content: str = Field(default="", sa_column_kwargs={"nullable": False})
    xml_size: int = Field(default=0)
    validation_errors: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class HprimCCAMAct(SQLModel, table=True):
    """Acte CCAM HPRIM persistant pour consultation et historique."""

    id: str = Field(primary_key=True, index=True)
    patient_id: Optional[str] = Field(default=None, index=True)
    message_id: Optional[str] = Field(default=None, foreign_key="hprimmessage.message_id", index=True)
    code_acte: str
    code_activite: str
    code_phase: str
    executant_rpps: str
    date_execution: datetime = Field(index=True)
    quantite: int = Field(default=1)
    modificateurs: str = Field(default="")
    montant: Optional[float] = Field(default=None)
    commentaire: Optional[str] = Field(default=None)
    action: str = Field(default="creation", index=True)
    facturable: bool = Field(default=True)
    valide: bool = Field(default=False)
    facture: bool = Field(default=False)
    deleted: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class HprimNGAPAct(SQLModel, table=True):
    """Acte NGAP HPRIM persistant pour consultation et historique."""

    id: str = Field(primary_key=True, index=True)
    patient_id: Optional[str] = Field(default=None, index=True)
    message_id: Optional[str] = Field(default=None, foreign_key="hprimmessage.message_id", index=True)
    lettre_cle: str
    coefficient: float
    execute_date: datetime = Field(index=True)
    denombrement: Optional[int] = Field(default=None)
    position_dentaire: Optional[str] = Field(default=None)
    execute_heure: Optional[str] = Field(default=None)
    numero_seance: Optional[int] = Field(default=None)
    nabms: str = Field(default="")
    minor_major: Optional[str] = Field(default=None)
    montant: Optional[float] = Field(default=None)
    commentaire: Optional[str] = Field(default=None)
    action: str = Field(default="creation", index=True)
    facturable: bool = Field(default=True)
    valide: bool = Field(default=False)
    facture: bool = Field(default=False)
    deleted: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)