"""Interface de paramétrage clinique des systèmes destinataires."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models_endpoints import SystemEndpoint
from app.models_practitioners import MedecinResponsable
from app.models_scenario_target_profiles import ScenarioTargetLocation, ScenarioTargetProfile
from app.models_structure import EntiteJuridique, UniteFonctionnelle
from app.services.scenario_qualification_service import target_key
from app.services.scenario_target_profile_service import ROLE_LABELS


router = APIRouter(prefix="/scenario-target-profiles", tags=["scenario-target-profiles"])


def _templates(request: Request):
    return request.app.state.templates


@router.get("", response_class=HTMLResponse, name="scenario_target_profile_list")
def list_profiles(request: Request, session: Session = Depends(get_session)):
    profiles = session.exec(select(ScenarioTargetProfile).order_by(ScenarioTargetProfile.target_system_key)).all()
    endpoints = session.exec(select(SystemEndpoint)).all()
    endpoints_by_key: dict[str, list[SystemEndpoint]] = {}
    for endpoint in endpoints:
        endpoints_by_key.setdefault(target_key(endpoint.target_system_key or endpoint.name), []).append(endpoint)
    return _templates(request).TemplateResponse(request, "scenario_target_profiles.html", {
        "request": request, "profiles": profiles, "endpoints_by_key": endpoints_by_key,
        "title": "Profils de destinations", "roles": ROLE_LABELS,
    })


@router.get("/new", response_class=HTMLResponse)
def new_profile(request: Request, target_system_key: Optional[str] = None, session: Session = Depends(get_session)):
    if target_system_key:
        existing = session.exec(
            select(ScenarioTargetProfile).where(ScenarioTargetProfile.target_system_key == target_key(target_system_key))
        ).first()
        if existing:
            return RedirectResponse(url=f"/scenario-target-profiles/{existing.id}", status_code=303)
    profile = ScenarioTargetProfile(target_system_key=target_key(target_system_key)) if target_system_key else None
    return _profile_form(request, session, profile)


@router.post("/new")
def create_profile(
    target_system_key: str = Form(...), name: Optional[str] = Form(None), description: Optional[str] = Form(None),
    entite_juridique_id: Optional[int] = Form(None), is_active: bool = Form(False), session: Session = Depends(get_session),
):
    key = target_key(target_system_key)
    if session.exec(select(ScenarioTargetProfile).where(ScenarioTargetProfile.target_system_key == key)).first():
        raise HTTPException(status_code=409, detail="Un profil existe déjà pour cette destination")
    profile = ScenarioTargetProfile(target_system_key=key, name=name or None, description=description or None, entite_juridique_id=entite_juridique_id, is_active=is_active)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return RedirectResponse(url=f"/scenario-target-profiles/{profile.id}", status_code=303)


@router.get("/{profile_id}", response_class=HTMLResponse)
def edit_profile(profile_id: int, request: Request, session: Session = Depends(get_session)):
    profile = session.get(ScenarioTargetProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil de destination introuvable")
    return _profile_form(request, session, profile)


def _profile_form(request: Request, session: Session, profile: Optional[ScenarioTargetProfile]):
    rows = {row.role: row for row in session.exec(select(ScenarioTargetLocation).where(ScenarioTargetLocation.profile_id == profile.id)).all()} if profile and profile.id else {}
    endpoints = session.exec(select(SystemEndpoint)).all()
    endpoints_for_target = [endpoint for endpoint in endpoints if profile and target_key(endpoint.target_system_key or endpoint.name) == profile.target_system_key]
    ufs = session.exec(select(UniteFonctionnelle).order_by(UniteFonctionnelle.identifier, UniteFonctionnelle.name)).all()
    doctors = session.exec(select(MedecinResponsable).where(MedecinResponsable.active == True).order_by(MedecinResponsable.family_name, MedecinResponsable.given_name)).all()  # noqa: E712
    ejs = session.exec(select(EntiteJuridique).order_by(EntiteJuridique.name)).all()
    return _templates(request).TemplateResponse(request, "scenario_target_profile_form.html", {
        "request": request, "profile": profile, "rows": rows, "roles": ROLE_LABELS,
        "ufs": ufs, "doctors": doctors, "ejs": ejs, "endpoints": endpoints_for_target,
        "title": "Profil de destination",
    })


@router.post("/{profile_id}/save")
async def save_profile_async(
    profile_id: int, request: Request, session: Session = Depends(get_session),
):
    profile = session.get(ScenarioTargetProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil de destination introuvable")
    form = await request.form()
    profile.name = (form.get("name") or "").strip() or None
    profile.description = (form.get("description") or "").strip() or None
    profile.entite_juridique_id = int(form["entite_juridique_id"]) if form.get("entite_juridique_id") else None
    profile.is_active = form.get("is_active") == "true"
    profile.updated_at = datetime.utcnow()
    for role in ROLE_LABELS:
        uf_id = int(form[f"{role}_uf_id"]) if form.get(f"{role}_uf_id") else None
        doctor_id = int(form[f"{role}_doctor_id"]) if form.get(f"{role}_doctor_id") else None
        room, bed = (form.get(f"{role}_room") or "").strip() or None, (form.get(f"{role}_bed") or "").strip() or None
        row = session.exec(select(ScenarioTargetLocation).where(ScenarioTargetLocation.profile_id == profile.id).where(ScenarioTargetLocation.role == role)).first()
        if not any((uf_id, doctor_id, room, bed)):
            if row:
                session.delete(row)
            continue
        uf = session.get(UniteFonctionnelle, uf_id) if uf_id else None
        doctor = session.get(MedecinResponsable, doctor_id) if doctor_id else None
        if uf_id and not uf:
            raise HTTPException(status_code=422, detail=f"UF inconnue pour {ROLE_LABELS[role]}")
        if doctor_id and (not doctor or not doctor.active):
            raise HTTPException(status_code=422, detail=f"Médecin inactif ou inconnu pour {ROLE_LABELS[role]}")
        if uf and doctor and uf.medecin_responsable_id and uf.medecin_responsable_id != doctor.id:
            raise HTTPException(status_code=422, detail=f"Le médecin choisi n'est pas le responsable de l'UF pour {ROLE_LABELS[role]}")
        if not row:
            row = ScenarioTargetLocation(profile_id=profile.id, role=role)
            session.add(row)
        row.unite_fonctionnelle_id, row.medecin_responsable_id = uf_id, doctor_id
        row.room, row.bed, row.updated_at = room, bed, datetime.utcnow()
        session.add(row)
    session.add(profile)
    session.commit()
    return RedirectResponse(url=f"/scenario-target-profiles/{profile.id}", status_code=303)
