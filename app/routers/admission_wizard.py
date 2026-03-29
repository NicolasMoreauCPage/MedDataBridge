"""
Multi-step admission wizard: Patient → Dossier → Venue
Consolidates patient creation, dossier setup, and initial venue/mouvement in one workflow.
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Patient, Dossier, Venue, Mouvement, DossierType
from app.models_structure import Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
from app.services import patients_service
from app.services.patients_service import PatientCreateSchema
from app.utils.dossier_helpers import sync_dossier_class
from app.state_transitions import SUPPORTED_WORKFLOW_EVENTS

router = APIRouter(prefix="/wizard", tags=["wizard"])

def get_templates(request: Request):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates


@router.get("/admission", response_class=HTMLResponse)
def wizard_admission_start(
    request: Request, 
    session: Session = Depends(get_session),
    templates=Depends(get_templates)
):
    """Affiche le wizard d'admission au step 1 (Patient)"""
    return templates.TemplateResponse("admission_wizard.html", {
        "request": request,
        "current_step": 1,
        "patient": {},
        "services": session.exec(select(Service)).all()
    })


@router.post("/admission", response_class=HTMLResponse)
def wizard_admission_post(
    request: Request,
    step: int = Form(1),
    action: str = Form("next"),
    # Step 1: Patient
    prefix: Optional[str] = Form(None),
    family: Optional[str] = Form(None),
    given: Optional[str] = Form(None),
    birth_date: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    # Step 2: Dossier
    admission_type: Optional[str] = Form(None),
    admission_reason: Optional[str] = Form(None),
    attending_provider: Optional[str] = Form(None),
    # Step 3: Venue
    service_id: Optional[int] = Form(None),
    uf_id: Optional[int] = Form(None),
    lit_id: Optional[int] = Form(None),
    admission_date: Optional[str] = Form(None),
    admission_time: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    templates=Depends(get_templates)
):
    """Multi-step wizard POST handler"""
    
    # Handle navigation
    if action == "prev":
        next_step = max(1, step - 1)
    elif action == "complete":
        next_step = 4  # Complete the wizard
    else:  # action == "next" or implicit
        next_step = min(3, step + 1)
    
    # Collect data from current step
    wizard_data = {
        "patient": {
            "prefix": prefix,
            "family": family,
            "given": given,
            "birth_date": birth_date,
            "gender": gender,
            "phone": phone
        },
        "dossier": {
            "admission_type": admission_type,
            "admission_reason": admission_reason,
            "attending_provider": attending_provider
        },
        "venue": {
            "service_id": service_id,
            "uf_id": uf_id,
            "lit_id": lit_id,
            "admission_date": admission_date,
            "admission_time": admission_time
        }
    }
    
    # Validate step 1 if trying to advance
    if step == 1 and action == "next":
        if not family or not given or not birth_date or not gender:
            return templates.TemplateResponse("admission_wizard.html", {
                "request": request,
                "current_step": 1,
                "error": "Veuillez remplir tous les champs requis: Nom, Prénom, Date de naissance, Sexe",
                "patient": wizard_data["patient"],
                "services": session.exec(select(Service)).all()
            }, status_code=400)
    
    # Validate step 2 if trying to advance
    if step == 2 and action == "next":
        if not admission_type:
            return templates.TemplateResponse("admission_wizard.html", {
                "request": request,
                "current_step": 2,
                "error": "Veuillez sélectionner un type d'admission",
                "patient_recap": wizard_data["patient"],
                "dossier": wizard_data["dossier"],
                "services": session.exec(select(Service)).all()
            }, status_code=400)
    
    # Validate step 3 and create the admission
    if step == 3 and action == "complete":
        if not lit_id or not admission_date or not admission_time:
            return templates.TemplateResponse("admission_wizard.html", {
                "request": request,
                "current_step": 3,
                "error": "Veuillez sélectionner un lit et une date/heure d'admission",
                "patient_recap": wizard_data["patient"],
                "dossier_recap": wizard_data["dossier"],
                "services": session.exec(select(Service)).all()
            }, status_code=400)
        
        # Create the complete admission
        try:
            # 1. Create patient
            patient_data = PatientCreateSchema(
                family=wizard_data["patient"]["family"],
                given=wizard_data["patient"]["given"],
                birth_date=wizard_data["patient"]["birth_date"],
                gender=wizard_data["patient"]["gender"],
                phone=wizard_data["patient"]["phone"]
            )
            ght_context = getattr(request.state, "ght_context", None)
            patient = patients_service.create_patient(
                session=session,
                patient_data=patient_data,
                ght_context=ght_context
            )
            session.add(patient)
            session.flush()
            
            # 2. Create dossier
            dossier = Dossier(
                patient_id=patient.id,
                dossier_type=DossierType.NORMAL,
                admission_type=wizard_data["dossier"]["admission_type"],
                admission_reason=wizard_data["dossier"]["admission_reason"],
                attending_provider=wizard_data["dossier"]["attending_provider"],
                opened_at=datetime.now()
            )
            ej_context = getattr(request.state, "ej_context", None)
            if ej_context:
                dossier.entite_juridique_id = ej_context.id
            
            session.add(dossier)
            session.flush()
            
            # 3. Create venue
            lit = session.get(Lit, wizard_data["venue"]["lit_id"])
            if not lit:
                raise HTTPException(status_code=404, detail="Lit not found")
            
            admission_datetime = datetime.strptime(
                f"{wizard_data['venue']['admission_date']} {wizard_data['venue']['admission_time']}", 
                "%Y-%m-%d %H:%M"
            )
            
            venue = Venue(
                dossier_id=dossier.id,
                lit_id=lit.id,
                admission_date=admission_datetime,
                opened_at=datetime.now(),
                status="open"
            )
            session.add(venue)
            session.flush()
            
            # 4. Create initial mouvement (ADMISSION)
            mouvement = Mouvement(
                venue_id=venue.id,
                when=admission_datetime,
                movement_type="admission",
                lit_id=lit.id,
                status="completed"
            )
            session.add(mouvement)
            
            # Sync dossier class and commit
            sync_dossier_class(dossier, session)
            session.commit()
            
            # Redirect to newly created venue detail page
            return RedirectResponse(
                url=f"/venues/{venue.id}",
                status_code=303
            )
            
        except Exception as e:
            session.rollback()
            return templates.TemplateResponse("admission_wizard.html", {
                "request": request,
                "current_step": 3,
                "error": f"Erreur lors de la création de l'admission: {str(e)}",
                "patient_recap": wizard_data["patient"],
                "dossier_recap": wizard_data["dossier"],
                "services": session.exec(select(Service)).all()
            }, status_code=500)
    
    # Show next step
    ctx = {
        "request": request,
        "current_step": next_step,
        "patient": wizard_data["patient"],
        "patient_recap": wizard_data["patient"],
        "dossier": wizard_data["dossier"],
        "dossier_recap": wizard_data["dossier"],
        "venue": wizard_data["venue"],
        "services": session.exec(select(Service)).all()
    }
    
    return templates.TemplateResponse("admission_wizard.html", ctx)


@router.get("/api/services/{service_id}/ufs")
async def get_service_ufs(
    service_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint: Get UFs for a given service"""
    ufs = session.exec(
        select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service_id)
    ).all()
    return [{"id": uf.id, "name": uf.name} for uf in ufs]


@router.get("/api/ufs/{uf_id}/lits")
async def get_uf_lits(
    uf_id: int,
    status: str = "free",
    session: Session = Depends(get_session)
):
    """API endpoint: Get available lits for a given UF"""
    # Join through the structure hierarchy
    query = (
        select(Lit)
        .join(Chambre, Lit.chambre_id == Chambre.id)
        .join(UniteHebergement, Chambre.unite_hebergement_id == UniteHebergement.id)
        .join(UniteFonctionnelle, UniteHebergement.unite_fonctionnelle_id == UniteFonctionnelle.id)
        .where(UniteFonctionnelle.id == uf_id)
    )
    
    if status == "free":
        query = query.where((Lit.operational_status == "active") | (Lit.operational_status == None))
    
    lits = session.exec(query).all()
    return [{"id": lit.id, "name": lit.name, "status": "available"} for lit in lits]
