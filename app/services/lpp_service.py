# app/services/lpp_service.py
"""
Service pour la gestion des actes LPP
"""

from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from fastapi import HTTPException

from app.models import LPPAct, Dossier
from app.schemas.lpp import LPPActCreate, LPPActUpdate, LPPActResponse


class LPPService:
    def __init__(self, db: Session):
        self.db = db

    async def create_act(self, act_data: LPPActCreate) -> LPPActResponse:
        """Créer un nouvel acte LPP"""
        # Vérifier que le dossier existe
        dossier = self.db.get(Dossier, act_data.dossier_id)
        if not dossier:
            raise HTTPException(status_code=404, detail="Dossier non trouvé")

        # Validation des données
        if not act_data.code_lpp or len(act_data.code_lpp) != 13 or not act_data.code_lpp.isdigit():
            raise HTTPException(status_code=400, detail="Code LPP invalide")

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

        # Créer l'acte — mapper les champs du schéma vers le modèle LPPAct
        # Le modèle attend `montant_unitaire_facture_ttc` (obligatoire),
        # tandis que le schéma utilise `prix_unitaire` et `montant_total`.
        montant_unitaire = float(act_data.prix_unitaire)
        quantite_val = int(act_data.quantite) if act_data.quantite is not None else 1
        if montant_unitaire is None or montant_unitaire <= 0:
            raise HTTPException(status_code=400, detail="montant_unitaire_facture_ttc doit être positif et renseigné")

        act = LPPAct(
            dossier_id=act_data.dossier_id,
            code_lpp=act_data.code_lpp,
            denomination_libelle=act_data.libelle,
            quantite=quantite_val,
            montant_unitaire_facture_ttc=montant_unitaire,
            execute_date=act_data.execute_date,
            prestataire_id=getattr(act_data, "prestataire_id", None),
            commentaire=getattr(act_data, "commentaire", None),
        )

        self.db.add(act)
        self.db.commit()
        self.db.refresh(act)

        return LPPActResponse(**act.__dict__)

    async def get_acts_by_dossier(self, dossier_id: int) -> List[LPPActResponse]:
        """Récupérer les actes LPP d'un dossier"""
        query = select(LPPAct).where(LPPAct.dossier_id == dossier_id)
        result = self.db.execute(query)
        acts = result.scalars().all()

        return [LPPActResponse(**act.__dict__) for act in acts]

    async def update_act(self, act_id: int, act_data: LPPActUpdate) -> LPPActResponse:
        """Mettre à jour un acte LPP"""
        act = self.db.get(LPPAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte LPP non trouvé")

        # Validation des champs fournis
        if act_data.code_lpp is not None and (not act_data.code_lpp or len(act_data.code_lpp) != 13 or not act_data.code_lpp.isdigit()):
            raise HTTPException(status_code=400, detail="Code LPP invalide")

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

        return LPPActResponse(**act.__dict__)

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

        return LPPActResponse(**act.__dict__)

    async def validate_act(self, act_id: int) -> LPPActResponse:
        """Valider un acte LPP"""
        act = self.db.get(LPPAct, act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Acte LPP non trouvé")

        act.valide = True
        self.db.commit()
        self.db.refresh(act)

        return LPPActResponse(**act.__dict__)