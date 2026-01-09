# app/api/contracts.py
"""
API endpoints pour la gestion des contrats médicaux avec validation HPRIM
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from pydantic import BaseModel, field_validator, model_validator

from app.db import get_session
from app.models import Contract, Dossier
from app.models_practitioners import MedecinResponsable
from app.services.contract_service import ContractService

router = APIRouter(prefix="/api/contracts", tags=["Contrats"])


class ContractCreate(BaseModel):
    """Modèle de création de contrat avec validation HPRIM"""
    dossier_id: int
    contract_type: str
    status: str
    date_debut: date
    date_fin: Optional[date] = None
    organisme_payeur: Optional[str] = None
    numero_contrat: Optional[str] = None
    taux_prise_en_charge: Optional[float] = None
    plafond_annuel: Optional[float] = None
    conditions_particulieres: Optional[str] = None
    medecin_responsable_id: Optional[int] = None

    @field_validator('contract_type')
    @classmethod
    def validate_contract_type(cls, v):
        if v not in ['NGAP', 'UCD', 'LPP']:
            raise ValueError('Type de contrat invalide. Valeurs autorisées: NGAP, UCD, LPP')
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v not in ['actif', 'suspendu', 'termine']:
            raise ValueError('Statut invalide. Valeurs autorisées: actif, suspendu, termine')
        return v

    @field_validator('numero_contrat')
    @classmethod
    def validate_numero_contrat(cls, v):
        if v and len(v.strip()) > 50:
            raise ValueError('Le numéro de contrat ne peut pas dépasser 50 caractères')
        return v

    @field_validator('taux_prise_en_charge')
    @classmethod
    def validate_taux_prise_en_charge(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Le taux de prise en charge doit être entre 0 et 100%')
        return v

    @field_validator('plafond_annuel')
    @classmethod
    def validate_plafond_annuel(cls, v):
        if v is not None and v < 0:
            raise ValueError('Le plafond annuel ne peut pas être négatif')
        return v

    @model_validator(mode='after')
    def validate_dates(self):
        if self.date_fin and self.date_debut and self.date_fin <= self.date_debut:
            raise ValueError('La date de fin doit être postérieure à la date de début')
        return self


class ContractResponse(BaseModel):
    """Modèle de réponse pour les contrats"""
    id: int
    dossier_id: int
    contract_type: str
    status: str
    date_debut: date
    date_fin: Optional[date]
    organisme_payeur: Optional[str]
    numero_contrat: Optional[str]
    taux_prise_en_charge: Optional[float]
    plafond_annuel: Optional[float]
    conditions_particulieres: Optional[str]
    medecin_responsable_id: Optional[int]
    created_at: Optional[date]
    updated_at: Optional[date]

    class Config:
        from_attributes = True


@router.post("/", response_model=ContractResponse)
async def create_contract(contract: ContractCreate, db: Session = Depends(get_session)):
    """Créer un nouveau contrat avec validation HPRIM"""
    try:
        result = ContractService.create_contract(
            session=db,
            dossier_id=contract.dossier_id,
            contract_type=contract.contract_type,
            status=contract.status,
            date_debut=contract.date_debut,
            date_fin=contract.date_fin,
            organisme_payeur=contract.organisme_payeur,
            numero_contrat=contract.numero_contrat,
            taux_prise_en_charge=contract.taux_prise_en_charge,
            plafond_annuel=contract.plafond_annuel,
            conditions_particulieres=contract.conditions_particulieres,
            medecin_responsable_id=contract.medecin_responsable_id
        )
        return ContractResponse.model_validate(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création du contrat: {str(e)}")


@router.get("/dossier/{dossier_id}", response_model=List[ContractResponse])
async def get_contracts_by_dossier(dossier_id: int, db: Session = Depends(get_session)):
    """Récupérer tous les contrats d'un dossier"""
    try:
        contracts = ContractService.get_contracts_for_dossier(db, dossier_id)
        return [ContractResponse.model_validate(contract) for contract in contracts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des contrats: {str(e)}")


@router.get("/dossier/{dossier_id}/active", response_model=List[ContractResponse])
async def get_active_contracts_by_dossier(
    dossier_id: int,
    contract_type: Optional[str] = None,
    db: Session = Depends(get_session)
):
    """Récupérer les contrats actifs d'un dossier"""
    try:
        contracts = ContractService.get_active_contracts_for_dossier(db, dossier_id, contract_type)
        return [ContractResponse.model_validate(contract) for contract in contracts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des contrats actifs: {str(e)}")


@router.put("/{contract_id}/status", response_model=ContractResponse)
async def update_contract_status(contract_id: int, status: str, db: Session = Depends(get_session)):
    """Mettre à jour le statut d'un contrat"""
    try:
        result = ContractService.update_contract_status(db, contract_id, status)
        return ContractResponse.model_validate(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour du statut: {str(e)}")


@router.get("/dossier/{dossier_id}/coverage/{contract_type}/{act_date}")
async def get_contract_coverage(
    dossier_id: int,
    contract_type: str,
    act_date: date,
    db: Session = Depends(get_session)
):
    """Vérifier la couverture contractuelle pour un acte à une date donnée"""
    try:
        contract = ContractService.get_contract_coverage(db, dossier_id, contract_type, act_date)
        if contract:
            return {
                "covered": True,
                "contract": ContractResponse.model_validate(contract),
                "taux_prise_en_charge": contract.taux_prise_en_charge,
                "plafond_annuel": contract.plafond_annuel
            }
        else:
            return {"covered": False, "message": "Aucun contrat actif trouvé pour cette période"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la vérification de couverture: {str(e)}")


@router.post("/calculate-reimbursement")
async def calculate_reimbursement(
    contract_id: int,
    act_amount: float,
    db: Session = Depends(get_session)
):
    """Calculer le montant de remboursement selon le contrat"""
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contrat non trouvé")

        reimbursed_amount = ContractService.calculate_reimbursement_amount(contract, act_amount)
        return {
            "original_amount": act_amount,
            "reimbursed_amount": reimbursed_amount,
            "taux_prise_en_charge": contract.taux_prise_en_charge,
            "plafond_annuel": contract.plafond_annuel
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du calcul du remboursement: {str(e)}")