# app/services/lpp_service.py
"""
Service pour la gestion des actes LPP
"""

from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from fastapi import HTTPException

from app.models import LPPAct, Dossier
from app.schemas.lpp import LPPActCreate, LPPActUpdate, LPPActResponse


class LPPService:
    def __init__(self, db: Session):
        self.db = db

    def _validate_code_lpp(self, code_lpp: str):
        if not code_lpp or len(code_lpp) != 13 or not code_lpp.isdigit():
            raise HTTPException(status_code=400, detail="Code LPP invalide")

    async def create_act(self, act_data: LPPActCreate) -> LPPActResponse:
        """Créer un nouvel acte LPP"""
        dossier = self.db.get(Dossier, act_data.dossier_id)
        if not dossier:
            raise HTTPException(status_code=404, detail="Dossier non trouvé")

        self._validate_code_lpp(act_data.code_lpp)

        if act_data.quantite <= 0:
            raise HTTPException(status_code=400, detail="Quantité doit être positive")

        if act_data.montant_unitaire_facture_ttc <= 0:
            raise HTTPException(status_code=400, detail="Montant unitaire facturé TTC doit être positif")

        act = LPPAct(**act_data.model_dump())

        self.db.add(act)
        self.db.commit()
        self.db.refresh(act)

        return LPPActResponse.model_validate(act)

    async def get_acts_by_dossier(self, dossier_id: int) -> List[LPPActResponse]:
        """Récupérer les actes LPP d'un dossier"""
        query = select(LPPAct).where(LPPAct.dossier_id == dossier_id)
        result = self.db.execute(query)
        acts = result.scalars().all()

        return [LPPActResponse.model_validate(act) for act in acts]

    async def update_act(self, act_id: int, act_data: LPPActUpdate) -> LPPActResponse:
        """Mettre à jour un acte LPP"""
        act = self.db.get(LPPAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte LPP non trouvé")

        if act_data.code_lpp is not None:
            self._validate_code_lpp(act_data.code_lpp)

        if act_data.quantite is not None and act_data.quantite <= 0:
            raise HTTPException(status_code=400, detail="Quantité doit être positive")

        if act_data.montant_unitaire_facture_ttc is not None and act_data.montant_unitaire_facture_ttc <= 0:
            raise HTTPException(status_code=400, detail="Montant unitaire facturé TTC doit être positif")

        for field, value in act_data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(act, field, value)

        self.db.commit()
        self.db.refresh(act)

        return LPPActResponse.model_validate(act)

    async def delete_act(self, act_id: int):
        """Supprimer un acte LPP"""
        act = self.db.get(LPPAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte LPP non trouvé")

        self.db.delete(act)
        self.db.commit()

    async def get_act_by_id(self, act_id: int) -> LPPActResponse:
        """Récupérer un acte LPP par son ID"""
        act = self.db.get(LPPAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte LPP non trouvé")

        return LPPActResponse.model_validate(act)

    async def validate_act(self, act_id: int) -> LPPActResponse:
        """Valider un acte LPP"""
        act = self.db.get(LPPAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte LPP non trouvé")

        act.valide = True
        self.db.commit()
        self.db.refresh(act)

        return LPPActResponse.model_validate(act)
