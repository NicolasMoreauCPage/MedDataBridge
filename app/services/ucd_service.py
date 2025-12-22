# app/services/ucd_service.py
"""
Service pour la gestion des actes UCD
"""

from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from fastapi import HTTPException

from app.models import UCDAct, Dossier
from app.schemas.ucd import UCDActCreate, UCDActUpdate, UCDActResponse


class UCDService:
    def __init__(self, db: Session):
        self.db = db

    async def create_act(self, act_data: UCDActCreate) -> UCDActResponse:
        """Créer un nouvel acte UCD"""
        # Vérifier que le dossier existe
        dossier = self.db.get(Dossier, act_data.dossier_id)
        if not dossier:
            raise HTTPException(status_code=404, detail="Dossier non trouvé")

        # Validation des données
        if not act_data.code_cip or len(act_data.code_cip) != 13 or not act_data.code_cip.isdigit():
            raise HTTPException(status_code=400, detail="Code CIP-13 invalide")

        if act_data.quantite <= 0:
            raise HTTPException(status_code=400, detail="Quantité doit être positive")

        if act_data.prix_unitaire <= 0:
            raise HTTPException(status_code=400, detail="Prix unitaire doit être positif")

        if act_data.montant_total <= 0:
            raise HTTPException(status_code=400, detail="Montant total doit être positif")

        # Vérification cohérence calcul
        expected_total = act_data.prix_unitaire * act_data.quantite
        if abs(act_data.montant_total - expected_total) > 0.01:
            raise HTTPException(status_code=400, detail="Montant total incohérent avec prix unitaire * quantité")

        # Créer l'acte
        act = UCDAct(
            dossier_id=act_data.dossier_id,
            code_cip=act_data.code_cip,
            designation=act_data.designation,
            quantite=act_data.quantite,
            prix_unitaire=act_data.prix_unitaire,
            montant_total=act_data.montant_total,
            execute_date=act_data.execute_date,
            prestataire_id=act_data.prestataire_id,
            commentaire=act_data.commentaire
        )

        self.db.add(act)
        self.db.commit()
        self.db.refresh(act)

        return UCDActResponse(**act.__dict__)

    async def get_acts_by_dossier(self, dossier_id: int) -> List[UCDActResponse]:
        """Récupérer les actes UCD d'un dossier"""
        query = select(UCDAct).where(UCDAct.dossier_id == dossier_id)
        result = self.db.execute(query)
        acts = result.scalars().all()

        return [UCDActResponse(**act.__dict__) for act in acts]

    async def update_act(self, act_id: int, act_data: UCDActUpdate) -> UCDActResponse:
        """Mettre à jour un acte UCD"""
        act = self.db.get(UCDAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte UCD non trouvé")

        # Validation des champs fournis
        if act_data.code_cip is not None and (not act_data.code_cip or len(act_data.code_cip) != 13 or not act_data.code_cip.isdigit()):
            raise HTTPException(status_code=400, detail="Code CIP-13 invalide")

        if act_data.quantite is not None and act_data.quantite <= 0:
            raise HTTPException(status_code=400, detail="Quantité doit être positive")

        if act_data.prix_unitaire is not None and act_data.prix_unitaire <= 0:
            raise HTTPException(status_code=400, detail="Prix unitaire doit être positif")

        if act_data.montant_total is not None and act_data.montant_total <= 0:
            raise HTTPException(status_code=400, detail="Montant total doit être positif")

        # Vérification cohérence calcul si prix_unitaire et quantite sont fournis
        if act_data.prix_unitaire is not None and act_data.quantite is not None and act_data.montant_total is not None:
            expected_total = act_data.prix_unitaire * act_data.quantite
            if abs(act_data.montant_total - expected_total) > 0.01:
                raise HTTPException(status_code=400, detail="Montant total incohérent avec prix unitaire * quantité")

        # Mise à jour
        for field, value in act_data.__dict__.items():
            if value is not None:
                setattr(act, field, value)

        self.db.commit()
        self.db.refresh(act)

        return UCDActResponse(**act.__dict__)

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

        return UCDActResponse(**act.__dict__)

    async def validate_act(self, act_id: int) -> UCDActResponse:
        """Valider un acte UCD"""
        act = self.db.get(UCDAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte UCD non trouvé")

        act.valide = True
        self.db.commit()
        self.db.refresh(act)

        return UCDActResponse(**act.__dict__)