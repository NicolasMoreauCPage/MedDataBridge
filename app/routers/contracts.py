# app/routers/contracts.py
"""
Routes web pour la gestion des contrats médicaux
"""

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from app.db import get_session
from app.models import Dossier, Contract
from app.models_practitioners import MedecinResponsable
from app.services.contract_service import ContractService

router = APIRouter(prefix="/contracts", tags=["Contrats Web"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def contracts_dashboard(request: Request, db: Session = Depends(get_session)):
    """Dashboard des contrats"""
    return templates.TemplateResponse("contracts/dashboard.html", {
        "request": request,
        "title": "Gestion des contrats médicaux"
    })


@router.get("/dossier/{dossier_id}")
async def contracts_by_dossier(
    request: Request,
    dossier_id: int,
    db: Session = Depends(get_session)
):
    """Contrats d'un dossier"""
    dossier = db.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")

    contracts = ContractService.get_contracts_for_dossier(db, dossier_id)
    active_contracts = ContractService.get_active_contracts_for_dossier(db, dossier_id)

    return templates.TemplateResponse("contracts/dossier_contracts.html", {
        "request": request,
        "dossier": dossier,
        "contracts": contracts,
        "active_contracts": active_contracts,
        "title": f"Contrats - Dossier #{dossier.dossier_seq}"
    })


@router.get("/create/{dossier_id}")
async def create_contract_form(
    request: Request,
    dossier_id: int,
    db: Session = Depends(get_session)
):
    """Formulaire de création de contrat"""
    dossier = db.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")

    # Récupérer la liste des médecins pour le select
    medecins = db.query(MedecinResponsable).order_by(MedecinResponsable.family_name, MedecinResponsable.given_name).all()

    return templates.TemplateResponse("contracts/create_form.html", {
        "request": request,
        "dossier": dossier,
        "medecins": medecins,
        "title": f"Nouveau contrat - Dossier #{dossier.dossier_seq}"
    })


@router.post("/create/{dossier_id}")
async def create_contract(
    request: Request,
    dossier_id: int,
    contract_type: str = Form(...),
    status: str = Form(...),
    date_debut: str = Form(...),
    date_fin: Optional[str] = Form(None),
    organisme_payeur: Optional[str] = Form(None),
    numero_contrat: Optional[str] = Form(None),
    taux_prise_en_charge: Optional[float] = Form(None),
    plafond_annuel: Optional[float] = Form(None),
    conditions_particulieres: Optional[str] = Form(None),
    medecin_responsable_id: Optional[int] = Form(None),
    db: Session = Depends(get_session)
):
    """Créer un contrat médical"""
    try:
        # Conversion des dates
        date_debut_parsed = date.fromisoformat(date_debut)
        date_fin_parsed = date.fromisoformat(date_fin) if date_fin else None

        # Création du contrat
        contract = ContractService.create_contract(
            session=db,
            dossier_id=dossier_id,
            contract_type=contract_type,
            status=status,
            date_debut=date_debut_parsed,
            date_fin=date_fin_parsed,
            organisme_payeur=organisme_payeur,
            numero_contrat=numero_contrat,
            taux_prise_en_charge=taux_prise_en_charge,
            plafond_annuel=plafond_annuel,
            conditions_particulieres=conditions_particulieres,
            medecin_responsable_id=medecin_responsable_id
        )

        return templates.TemplateResponse("contracts/contract_created.html", {
            "request": request,
            "contract": contract,
            "title": "Contrat créé"
        })

    except ValueError as e:
        # En cas d'erreur de validation, retourner au formulaire avec l'erreur
        dossier = db.get(Dossier, dossier_id)
        medecins = db.query(Medecin).order_by(Medecin.nom, Medecin.prenom).all()

        return templates.TemplateResponse("contracts/create_form.html", {
            "request": request,
            "dossier": dossier,
            "medecins": medecins,
            "error": str(e),
            "form_data": {
                "contract_type": contract_type,
                "status": status,
                "date_debut": date_debut,
                "date_fin": date_fin,
                "organisme_payeur": organisme_payeur,
                "numero_contrat": numero_contrat,
                "taux_prise_en_charge": taux_prise_en_charge,
                "plafond_annuel": plafond_annuel,
                "conditions_particulieres": conditions_particulieres,
                "medecin_responsable_id": medecin_responsable_id
            },
            "title": f"Nouveau contrat - Dossier #{dossier.dossier_seq}"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création du contrat: {str(e)}")


@router.post("/{contract_id}/status")
async def update_contract_status_route(
    request: Request,
    contract_id: int,
    status: str = Form(...),
    db: Session = Depends(get_session)
):
    """Mettre à jour le statut d'un contrat"""
    try:
        contract = ContractService.update_contract_status(db, contract_id, status)

        # Rediriger vers la page du dossier
        return templates.TemplateResponse("contracts/status_updated.html", {
            "request": request,
            "contract": contract,
            "title": "Statut mis à jour"
        })

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour du statut: {str(e)}")