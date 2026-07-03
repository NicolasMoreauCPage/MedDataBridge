# app/services/ucd_service.py
"""
Service pour la gestion des actes UCD
"""

from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from fastapi import HTTPException

from app.models import UCDAct, Dossier
from app.schemas.ucd import UCDActCreate, UCDActUpdate, UCDActResponse


class UCDService:
    def __init__(self, db: Session):
        self.db = db

    def _validate_code_ucd(self, code_ucd: str):
        if not code_ucd or len(code_ucd) != 13 or not code_ucd.isdigit():
            raise HTTPException(status_code=400, detail="Code UCD / CIP-13 invalide")

    async def create_act(self, act_data: UCDActCreate) -> UCDActResponse:
        """Créer un nouvel acte UCD"""
        dossier = self.db.get(Dossier, act_data.dossier_id)
        if not dossier:
            raise HTTPException(status_code=404, detail="Dossier non trouvé")

        self._validate_code_ucd(act_data.code_ucd)

        if act_data.quantite <= 0:
            raise HTTPException(status_code=400, detail="Quantité doit être positive")

        act = UCDAct(**act_data.model_dump())

        self.db.add(act)
        self.db.commit()
        self.db.refresh(act)

        return UCDActResponse.model_validate(act)

    async def get_acts_by_dossier(self, dossier_id: int) -> List[UCDActResponse]:
        """Récupérer les actes UCD d'un dossier"""
        query = select(UCDAct).where(UCDAct.dossier_id == dossier_id)
        result = self.db.execute(query)
        acts = result.scalars().all()

        return [UCDActResponse.model_validate(act) for act in acts]

    async def update_act(self, act_id: int, act_data: UCDActUpdate) -> UCDActResponse:
        """Mettre à jour un acte UCD"""
        act = self.db.get(UCDAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte UCD non trouvé")

        if act_data.code_ucd is not None:
            self._validate_code_ucd(act_data.code_ucd)

        if act_data.quantite is not None and act_data.quantite <= 0:
            raise HTTPException(status_code=400, detail="Quantité doit être positive")

        for field, value in act_data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(act, field, value)

        self.db.commit()
        self.db.refresh(act)

        return UCDActResponse.model_validate(act)

    async def delete_act(self, act_id: int):
        """Supprimer un acte UCD"""
        act = self.db.get(UCDAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte UCD non trouvé")

        self.db.delete(act)
        self.db.commit()

    async def get_act_by_id(self, act_id: int) -> UCDActResponse:
        """Récupérer un acte UCD par son ID"""
        act = self.db.get(UCDAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte UCD non trouvé")

        return UCDActResponse.model_validate(act)

    async def validate_act(self, act_id: int) -> UCDActResponse:
        """Valider un acte UCD"""
        act = self.db.get(UCDAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte UCD non trouvé")

        act.valide = True
        self.db.commit()
        self.db.refresh(act)

        return UCDActResponse.model_validate(act)
