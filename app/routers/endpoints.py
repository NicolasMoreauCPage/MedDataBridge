from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request as FastAPIRequest
from sqlmodel import select, Session
from starlette import status
from datetime import datetime, timezone
import logging

from app.db import get_session

logger = logging.getLogger(__name__)
from app.models_endpoints import SystemEndpoint
from app.models_context import (
    EndpointContext, PatientContextMapping, DossierContextMapping,
    VenueContextMapping, MouvementContextMapping
)
from app.models_structure import GHTContext, EntiteJuridique
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.runners import registry
from sqlmodel.sql.expression import select as sqlmodel_select
from sqlalchemy.orm import selectinload


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter(prefix="/endpoints", tags=["endpoints"])

def _bool_from_str(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).lower() in {"1","true","on","yes","y"}

@router.get("/admin", response_class=HTMLResponse)
def admin_list_endpoints(request: Request, session=Depends(get_session)):
    """Route d'administration : affiche TOUS les endpoints sans filtrage"""
    return list_endpoints(request, session, admin=True)

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def list_endpoints(request: Request, session=Depends(get_session), admin: bool = False):
    """
    Liste les endpoints selon le contexte actif.
    
    - Si admin=True (via /admin/endpoints), affiche tous les endpoints
    - Si contexte GHT actif, affiche uniquement les endpoints de ce GHT
    - Si contexte EJ actif (depuis session), affiche uniquement les endpoints de cette EJ
    - Si aucun contexte, redirige vers la page de sélection GHT
    """
    # Récupérer le contexte actif
    ght_context = getattr(request.state, 'ght_context', None)
    ej_context_id = request.session.get('ej_context_id')

    # Si pas de contexte et pas en mode admin, rediriger vers la sélection GHT
    if not admin and not ght_context and not ej_context_id:
        return RedirectResponse(url="/context/select", status_code=303)

    # Load endpoints with GHT context and EJ (including GHT via EJ)
    stmt = (
        sqlmodel_select(SystemEndpoint)
        .options(
            selectinload(SystemEndpoint.ght_context).selectinload(GHTContext.entites_juridiques),
            selectinload(SystemEndpoint.entite_juridique).selectinload(EntiteJuridique.ght_context)
        )
    )

    # Filtrer selon le contexte si on n'est pas en mode admin
    if not admin:
        if ej_context_id:
            # Contexte EJ : afficher seulement les endpoints de cette EJ
            stmt = stmt.where(SystemEndpoint.entite_juridique_id == ej_context_id)
        elif ght_context:
            # Contexte GHT : afficher les endpoints de ce GHT (directement ou via EJ)
            # Recharger le contexte GHT depuis la session pour éviter DetachedInstanceError
            db_ght_context = session.get(GHTContext, ght_context.id) if ght_context else None
            ej_ids = [ej.id for ej in db_ght_context.entites_juridiques] if db_ght_context else []
            from sqlalchemy import or_
            stmt = stmt.where(
                or_(
                    SystemEndpoint.ght_context_id == db_ght_context.id if db_ght_context else False,
                    SystemEndpoint.entite_juridique_id.in_(ej_ids) if ej_ids else False
                )
            )

    eps = session.exec(stmt).unique().all()
    running_ids = set(registry.running_ids())
    
    # Group endpoints by GHT and EJ
    ght_groups = {}
    no_ght_endpoints = []
    
    for e in eps:
        # Déterminer le GHT : soit directement, soit via l'EJ
        ght = e.ght_context
        if not ght and e.entite_juridique:
            # Charger le GHT via l'EJ si nécessaire
            if hasattr(e.entite_juridique, 'ght_context') and e.entite_juridique.ght_context:
                ght = e.entite_juridique.ght_context
            elif e.entite_juridique.ght_context_id:
                # Charger le GHT si pas déjà chargé
                ght = session.get(GHTContext, e.entite_juridique.ght_context_id)
        
        if ght:
            ght_id = ght.id
            if ght_id not in ght_groups:
                ght_groups[ght_id] = {
                    "ght": ght,
                    "ej_groups": {},
                    "no_ej_endpoints": []
                }
            
            # Group by EJ if endpoint has one
            if e.entite_juridique:
                ej_id = e.entite_juridique.id
                if ej_id not in ght_groups[ght_id]["ej_groups"]:
                    ght_groups[ght_id]["ej_groups"][ej_id] = {
                        "ej": e.entite_juridique,
                        "endpoints": []
                    }
                ght_groups[ght_id]["ej_groups"][ej_id]["endpoints"].append(e)
            else:
                ght_groups[ght_id]["no_ej_endpoints"].append(e)
        else:
            no_ght_endpoints.append(e)
    
    def _make_endpoint_row(e):
        # Pour les endpoints FILE, "running" = is_enabled (scanner automatique)
        # Pour les endpoints MLLP/FHIR, "running" = dans le registry
        if e.kind == "FILE":
            runtime = "RUNNING" if e.is_enabled else "STOPPED"
        else:
            runtime = "RUNNING" if e.id in running_ids else "STOPPED"
        return {
            "cells": [e.id, e.name, e.kind, e.role, e.host or "-", e.port or "-", e.base_url or "-", "ON" if e.is_enabled else "OFF", runtime],
            "detail_url": f"/endpoints/{e.id}",
            "context_url": f"/endpoints/{e.id}/context"
        }
    
    # Build hierarchical structure for template
    hierarchy = []
    
    # GHT groups
    for ght_id in sorted(ght_groups.keys()):
        ght_data = ght_groups[ght_id]
        ght_children = []
        
        # EJ subgroups
        for ej_id in sorted(ght_data["ej_groups"].keys()):
            ej_info = ght_data["ej_groups"][ej_id]
            ej_endpoints = [_make_endpoint_row(e) for e in ej_info["endpoints"]]
            ght_children.append({
                "type": "ej",
                "ej": ej_info["ej"],
                "endpoints": ej_endpoints
            })
        
        # Endpoints without EJ in this GHT
        for e in ght_data["no_ej_endpoints"]:
            ght_children.append({
                "type": "endpoint",
                "endpoint": _make_endpoint_row(e)
            })
        
        hierarchy.append({
            "type": "ght",
            "ght": ght_data["ght"],
            "children": ght_children
        })
    
    # Endpoints without GHT
    if no_ght_endpoints:
        hierarchy.append({
            "type": "no_ght",
            "endpoints": [_make_endpoint_row(e) for e in no_ght_endpoints]
        })
    
    # Déterminer le titre selon le contexte
    if admin:
        title = "Systèmes - Administration (tous les endpoints)"
    elif ej_context_id:
        try:
            ej = session.get(EntiteJuridique, ej_context_id)
            ej_name = ej.name if ej else "Établissement Juridique"
            title = f"Systèmes - {ej_name}"
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'EJ {ej_context_id}: {e}")
            title = "Systèmes - Établissement Juridique"
    elif ght_context:
        title = f"Systèmes - {ght_context.name}"
    else:
        title = "Systèmes (Paramétrage)"
    
    ctx = {
        "request": request,
        "title": title,
        "hierarchy": hierarchy,
        "new_url": "/endpoints/new",
        "is_admin": admin,
        "is_filtered": not admin and (ght_context is not None or ej_context_id is not None)
    }
    return get_templates_with_filters(request).TemplateResponse(request, "endpoints_hierarchical.html", ctx)

@router.get("/new", response_class=HTMLResponse)
def new_endpoint(request: Request, session=Depends(get_session)):
    from app.models_structure import GHTContext, EntiteJuridique
    from sqlmodel import select
    # Contexts from request
    ght_ctx = getattr(request.state, 'ght_context', None)
    ej_ctx = getattr(request.state, 'ej_context', None)

    # Récupérer les GHT et EJ disponibles
    ghts = session.exec(select(GHTContext).where(GHTContext.is_active == True)).all()
    # If a GHT context is active, limit EJs to that GHT to avoid showing EJs from other GHTs
    if ght_ctx:
        ejs = session.exec(select(EntiteJuridique).where(
            EntiteJuridique.is_active == True,
            EntiteJuridique.ght_context_id == ght_ctx.id
        )).all()
    else:
        ejs = session.exec(select(EntiteJuridique).where(EntiteJuridique.is_active == True)).all()

    # Create a temporary empty endpoint object to populate the template
    e = SystemEndpoint()
    e.name = ''
    e.kind = (request.query_params.get('kind') or 'MLLP')
    e.role = 'receiver'
    e.is_enabled = True
    # Default emits: keep same defaults as form
    e.emit_hl7_pam = True
    e.emit_fhir_identity = True
    e.emit_hl7_mfn = True
    e.emit_fhir_structure = True
    e.emit_hprim_ccam = False
    e.emit_hprim_ngap = False
    e.emit_hprim_ucd = False
    e.emit_hprim_lpp = False

    # All endpoints for anti-rebond select
    all_endpoints = session.exec(select(SystemEndpoint)).all()

    ctx = {
        "request": request,
        "title": "Nouveau système",
        "e": e,
        "all_endpoints": all_endpoints,
        "ghts": ghts,
        "ejs": ejs,
        "action_url": "/endpoints/new",
        "cancel_url": "/endpoints",
        "is_new": True
    }
    return get_templates_with_filters(request).TemplateResponse(request, "endpoint_detail.html", ctx)

@router.post("/new")
def create_endpoint(
    request: Request,
    name: str = Form(...),
    kind: str = Form(...),
    role: str = Form("receiver"),
    is_enabled: str = Form("true"),
    ght_context_id: str = Form(None),
    entite_juridique_id: str = Form(None),
    host: str = Form(None),
    port: int = Form(None),
    sending_app: str = Form(None),
    sending_facility: str = Form(None),
    receiving_app: str = Form(None),
    receiving_facility: str = Form(None),
    base_url: str = Form(None),
    auth_kind: str = Form("none"),
    auth_token: str = Form(None),
    inbox_path: str = Form(None),
    outbox_path: str = Form(None),
    archive_path: str = Form(None),
    error_path: str = Form(None),
    file_extensions: str = Form(None),
    emit_hl7_pam: bool = Form(False),
    emit_hl7_mfn: bool = Form(False),
    emit_fhir_structure: bool = Form(False),
    emit_fhir_identity: bool = Form(False),
    emit_hprim_ccam: bool = Form(False),
    emit_hprim_ngap: bool = Form(False),
    emit_hprim_ucd: bool = Form(False),
    emit_hprim_lpp: bool = Form(False),
    linked_endpoint_id: str = Form(None),
    session=Depends(get_session),
):
    # Debug: log incoming form data without leaking credentials/secrets
    import logging
    logger = logging.getLogger("endpoints_debug")
    logger.warning(
        "Form data received: name=%s, kind=%s, role=%s, is_enabled=%s, ght_context_id=%s, "
        "entite_juridique_id=%s, host=%s, port=%s, sending_app=%s, sending_facility=%s, "
        "receiving_app=%s, receiving_facility=%s, base_url=%s, auth_kind=%s, auth_token=[REDACTED], "
        "inbox_path=%s, outbox_path=%s, archive_path=%s, error_path=%s, file_extensions=%s",
        name,
        kind,
        role,
        is_enabled,
        ght_context_id,
        entite_juridique_id,
        host,
        port,
        sending_app,
        sending_facility,
        receiving_app,
        receiving_facility,
        base_url,
        auth_kind,
        inbox_path,
        outbox_path,
        archive_path,
        error_path,
        file_extensions,
    )
    ght_id = int(ght_context_id) if ght_context_id and str(ght_context_id).strip() else None
    ej_id = int(entite_juridique_id) if entite_juridique_id and str(entite_juridique_id).strip() else None
    # Fall back to active contexts if not provided by form (e.g., hidden by context)
    if not ght_id:
        gctx = getattr(request.state, 'ght_context', None)
        if gctx:
            ght_id = gctx.id
    if not ej_id:
        ejctx = getattr(request.state, 'ej_context', None)
        if ejctx:
            ej_id = ejctx.id

    # Cohérence GHT/EJ: si EJ fourni et GHT absent, déduire le GHT depuis l'EJ
    if ej_id and not ght_id:
        from app.models_structure import EntiteJuridique
        ej_obj = session.get(EntiteJuridique, ej_id)
        ght_id = ej_obj.ght_context_id if ej_obj else None
    # Si les deux sont fournis, vérifier l'appartenance
    if ej_id and ght_id:
        from app.models_structure import EntiteJuridique
        ej_obj = session.get(EntiteJuridique, ej_id)
        if ej_obj and ej_obj.ght_context_id != ght_id:
            raise HTTPException(status_code=400, detail="L'établissement choisi n'appartient pas au GHT sélectionné")
    
    if not ght_id and not ej_id:
        raise HTTPException(
            status_code=400,
            detail="Un endpoint doit être rattaché à un GHT Context ou à une Entité Juridique"
        )
    
    e = SystemEndpoint(
        name=name, kind=kind.upper(), role=role, is_enabled=_bool_from_str(is_enabled, True),
        ght_context_id=ght_id,
        entite_juridique_id=ej_id,
        host=host, port=port,
        sending_app=sending_app, sending_facility=sending_facility,
        receiving_app=receiving_app, receiving_facility=receiving_facility,
        base_url=base_url, auth_kind=auth_kind, auth_token=auth_token,
        inbox_path=inbox_path, outbox_path=outbox_path, archive_path=archive_path,
        error_path=error_path, file_extensions=file_extensions,
        emit_hl7_pam=bool(emit_hl7_pam),
        emit_hl7_mfn=bool(emit_hl7_mfn),
        emit_fhir_structure=bool(emit_fhir_structure),
        emit_fhir_identity=bool(emit_fhir_identity),
        emit_hprim_ccam=bool(emit_hprim_ccam),
        emit_hprim_ngap=bool(emit_hprim_ngap),
        emit_hprim_ucd=bool(emit_hprim_ucd),
        emit_hprim_lpp=bool(emit_hprim_lpp)
    )
    # linked endpoint (anti-rebond)
    if linked_endpoint_id and str(linked_endpoint_id).strip():
        try:
            e.linked_endpoint_id = int(linked_endpoint_id)
        except Exception:
            pass
    session.add(e); session.commit()
    session.refresh(e)  # Get the assigned ID
    
    # Démarrer automatiquement l'endpoint s'il est activé
    if e.is_enabled and e.kind == "MLLP" and e.role == "receiver":
        registry.start(e, session)
        session.commit()
    
    return RedirectResponse(url="/endpoints", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/{endpoint_id}", response_class=HTMLResponse)
def detail_endpoint(endpoint_id: int, request: Request, session=Depends(get_session)):
    from app.models_structure import GHTContext, EntiteJuridique
    
    e = session.get(SystemEndpoint, endpoint_id)
    if not e:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    # Récupérer les GHT et EJ pour les dropdowns
    ghts = session.exec(select(GHTContext).where(GHTContext.is_active == True)).all()
    ejs = session.exec(select(EntiteJuridique).where(EntiteJuridique.is_active == True)).all()
    
    # Récupérer tous les endpoints pour l'association anti-rebond
    all_endpoints = session.exec(select(SystemEndpoint)).all()
    
    # Pour les endpoints FILE, "running" = is_enabled (scanner automatique)
    # Pour les endpoints MLLP/FHIR, "running" = dans le registry
    if e.kind == "FILE":
        is_running = e.is_enabled
    else:
        is_running = endpoint_id in set(registry.running_ids())
    
    return get_templates_with_filters(request).TemplateResponse(request, "endpoint_detail.html", {
        "e": e,
        "is_running": is_running,
        "ghts": ghts,
        "ejs": ejs,
        "all_endpoints": all_endpoints
    })

# ========= AJOUTS =========

@router.post("/{endpoint_id}/update")
def update_endpoint(
    endpoint_id: int,
    request: Request,
    name: str = Form(...),
    kind: str = Form(...),
    role: str = Form("receiver"),
    is_enabled: str = Form("true"),
    ght_context_id: str = Form(None),
    entite_juridique_id: str = Form(None),
    linked_endpoint_id: str = Form(None),
    host: str = Form(None),
    port: int = Form(None),
    sending_app: str = Form(None),
    sending_facility: str = Form(None),
    receiving_app: str = Form(None),
    receiving_facility: str = Form(None),
    base_url: str = Form(None),
    auth_kind: str = Form("none"),
    auth_token: str = Form(None),
    inbox_path: str = Form(None),
    outbox_path: str = Form(None),
    archive_path: str = Form(None),
    error_path: str = Form(None),
    file_extensions: str = Form(None),
    ftp_host: str = Form(None),
    ftp_port: int = Form(None),
    ftp_username: str = Form(None),
    ftp_password: str = Form(None),
    ftp_use_sftp: str = Form("false"),
    ftp_remote_inbox_path: str = Form(None),
    ftp_remote_outbox_path: str = Form(None),
    ftp_remote_archive_path: str = Form(None),
    ftp_remote_error_path: str = Form(None),
    emit_hl7_pam: bool = Form(False),
    emit_hl7_mfn: bool = Form(False),
    emit_fhir_structure: bool = Form(False),
    emit_fhir_identity: bool = Form(False),
    emit_hprim_ccam: bool = Form(False),
    emit_hprim_ngap: bool = Form(False),
    emit_hprim_ucd: bool = Form(False),
    emit_hprim_lpp: bool = Form(False),
    session=Depends(get_session),
):
    e = session.get(SystemEndpoint, endpoint_id)
    if not e:
        raise HTTPException(404, "Endpoint not found")

    # Validation: au moins GHT ou EJ doit être défini
    ght_id = int(ght_context_id) if ght_context_id and ght_context_id.strip() else None
    ej_id = int(entite_juridique_id) if entite_juridique_id and entite_juridique_id.strip() else None
    
    if not ght_id and not ej_id:
        # Re-render with error instead of raising to keep user in the form
        ghts = session.exec(select(GHTContext).where(GHTContext.is_active == True)).all()
        ejs = session.exec(select(EntiteJuridique).where(EntiteJuridique.is_active == True)).all()
        all_endpoints = session.exec(select(SystemEndpoint)).all()
        # Pour les endpoints FILE, "running" = is_enabled
        is_running = e.is_enabled if e.kind == "FILE" else endpoint_id in set(registry.running_ids())
        return get_templates_with_filters(request).TemplateResponse(request, "endpoint_detail.html", {
            "e": e,
            "is_running": is_running,
            "ghts": ghts,
            "ejs": ejs,
            "all_endpoints": all_endpoints,
            "error": "Un endpoint doit être rattaché à un GHT Context ou à une Entité Juridique",
        }, status_code=400)

    # Cohérence GHT/EJ
    if ej_id and not ght_id:
        from app.models_structure import EntiteJuridique
        ej_obj = session.get(EntiteJuridique, ej_id)
        ght_id = ej_obj.ght_context_id if ej_obj else None
    if ej_id and ght_id:
        from app.models_structure import EntiteJuridique
        ej_obj = session.get(EntiteJuridique, ej_id)
        if ej_obj and ej_obj.ght_context_id != ght_id:
            # Re-render form with error message
            ghts = session.exec(select(GHTContext).where(GHTContext.is_active == True)).all()
            ejs = session.exec(select(EntiteJuridique).where(EntiteJuridique.is_active == True)).all()
            all_endpoints = session.exec(select(SystemEndpoint)).all()
            # Pour les endpoints FILE, "running" = is_enabled
            is_running = e.is_enabled if e.kind == "FILE" else endpoint_id in set(registry.running_ids())
            return get_templates_with_filters(request).TemplateResponse(request, "endpoint_detail.html", {
                "e": e,
                "is_running": is_running,
                "ghts": ghts,
                "ejs": ejs,
                "all_endpoints": all_endpoints,
                "error": "L'établissement choisi n'appartient pas au GHT sélectionné",
            }, status_code=400)

    e.name = name
    e.kind = kind.upper()
    e.role = role
    e.is_enabled = _bool_from_str(is_enabled, True)
    e.ght_context_id = ght_id
    e.entite_juridique_id = ej_id
    e.linked_endpoint_id = int(linked_endpoint_id) if linked_endpoint_id and linked_endpoint_id.strip() else None
    e.host, e.port = host, port
    e.sending_app, e.sending_facility = sending_app, sending_facility
    e.receiving_app, e.receiving_facility = receiving_app, receiving_facility
    e.base_url, e.auth_kind, e.auth_token = base_url, auth_kind, auth_token
    e.inbox_path, e.outbox_path, e.archive_path = inbox_path, outbox_path, archive_path
    e.error_path, e.file_extensions = error_path, file_extensions
    e.ftp_host, e.ftp_port = ftp_host, ftp_port
    e.ftp_username, e.ftp_password = ftp_username, ftp_password
    e.ftp_use_sftp = _bool_from_str(ftp_use_sftp, False)
    e.ftp_remote_inbox_path, e.ftp_remote_outbox_path = ftp_remote_inbox_path, ftp_remote_outbox_path
    e.ftp_remote_archive_path, e.ftp_remote_error_path = ftp_remote_archive_path, ftp_remote_error_path
    e.emit_hl7_pam = bool(emit_hl7_pam)
    e.emit_hl7_mfn = bool(emit_hl7_mfn)
    e.emit_fhir_structure = bool(emit_fhir_structure)
    e.emit_fhir_identity = bool(emit_fhir_identity)
    e.emit_hprim_ccam = bool(emit_hprim_ccam)
    e.emit_hprim_ngap = bool(emit_hprim_ngap)
    e.emit_hprim_ucd = bool(emit_hprim_ucd)
    e.emit_hprim_lpp = bool(emit_hprim_lpp)
    e.updated_at = datetime.now(timezone.utc)

    session.add(e); session.commit()
    
    # Démarrer automatiquement l'endpoint s'il est maintenant activé et pas déjà en cours
    if e.is_enabled and e.kind == "MLLP" and e.role == "receiver":
        if endpoint_id not in set(registry.running_ids()):
            registry.start(e, session)
            session.commit()
    # Arrêter l'endpoint s'il est désactivé mais en cours d'exécution
    elif endpoint_id in set(registry.running_ids()):
        registry.stop(e, session)
        session.commit()
    
    return RedirectResponse(url="/endpoints", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{endpoint_id}/delete")
def delete_endpoint(endpoint_id: int, session=Depends(get_session)):
    e = session.get(SystemEndpoint, endpoint_id)
    if not e:
        raise HTTPException(404, "Endpoint not found")
    # stop si en cours d'exécution
    if endpoint_id in set(registry.running_ids()):
        registry.stop(e, session)
    session.delete(e); session.commit()
    return RedirectResponse(url="/endpoints", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{endpoint_id}/start")
def start_endpoint(endpoint_id: int, session=Depends(get_session)):
    e = session.get(SystemEndpoint, endpoint_id)
    if not e:
        raise HTTPException(404, "Endpoint not found")
    if endpoint_id not in set(registry.running_ids()):
        registry.start(e, session); session.commit()
    return RedirectResponse(url=f"/endpoints/{endpoint_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{endpoint_id}/stop")
def stop_endpoint(endpoint_id: int, session=Depends(get_session)):
    e = session.get(SystemEndpoint, endpoint_id)
    if not e:
        raise HTTPException(404, "Endpoint not found")
    if endpoint_id in set(registry.running_ids()):
        registry.stop(e, session); session.commit()
    return RedirectResponse(url=f"/endpoints/{endpoint_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{endpoint_id}/restart")
def restart_endpoint(endpoint_id: int, session=Depends(get_session)):
    e = session.get(SystemEndpoint, endpoint_id)
    if not e:
        raise HTTPException(404, "Endpoint not found")
    if endpoint_id in set(registry.running_ids()):
        registry.stop(e, session)
    registry.start(e, session); session.commit()
    return RedirectResponse(url=f"/endpoints/{endpoint_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/{endpoint_id}/clone-structure", response_class=HTMLResponse)
def show_clone_structure_form(endpoint_id: int, request: Request, session: Session = Depends(get_session)):
    """Affiche le formulaire pour cloner la structure d'un endpoint vers un autre"""
    source = session.get(SystemEndpoint, endpoint_id)
    if not source:
        raise HTTPException(404, "Endpoint source not found")
        
    # Récupérer tous les autres endpoints disponibles comme cibles potentielles
    targets = session.exec(
        select(SystemEndpoint)
        .where(SystemEndpoint.id != endpoint_id)
        .where(SystemEndpoint.role == "receiver")
    ).all()
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "endpoint_clone_structure.html",
        {
            "source": source,
            "targets": targets
        }
    )

@router.post("/{source_id}/clone-structure/{target_id}")
async def clone_structure(
    source_id: int,
    target_id: int,
    session: Session = Depends(get_session)
):
    """Clone la structure et les mappings d'un endpoint vers un autre"""
    source = session.get(SystemEndpoint, source_id)
    target = session.get(SystemEndpoint, target_id)
    
    if not source or not target:
        raise HTTPException(404, "Endpoint not found")
    
    if target.role != "receiver":
        raise HTTPException(400, "Target endpoint must be a receiver")
        
    try:
        # Récupérer les contextes
        source_context = session.exec(
            select(EndpointContext)
            .where(EndpointContext.endpoint_id == source_id)
        ).first()
        
        if not source_context:
            raise HTTPException(400, "Source endpoint has no context")
            
        target_context = session.exec(
            select(EndpointContext)
            .where(EndpointContext.endpoint_id == target_id)
        ).first()
        
        if not target_context:
            target_context = EndpointContext(endpoint_id=target_id)
            session.add(target_context)
            session.commit()
            session.refresh(target_context)
            
        # Cloner les mappings de patients
        source_mappings = session.exec(
            select(PatientContextMapping)
            .where(PatientContextMapping.context_id == source_context.id)
        ).all()
        
        for mapping in source_mappings:
            new_mapping = PatientContextMapping(
                context_id=target_context.id,
                patient_id=mapping.patient_id,
                external_id=mapping.external_id
            )
            session.add(new_mapping)
            
        # Cloner les mappings de dossiers
        source_mappings = session.exec(
            select(DossierContextMapping)
            .where(DossierContextMapping.context_id == source_context.id)
        ).all()
        
        for mapping in source_mappings:
            new_mapping = DossierContextMapping(
                context_id=target_context.id,
                dossier_id=mapping.dossier_id,
                external_id=mapping.external_id
            )
            session.add(new_mapping)
            
        # Cloner les mappings de venues
        source_mappings = session.exec(
            select(VenueContextMapping)
            .where(VenueContextMapping.context_id == source_context.id)
        ).all()
        
        for mapping in source_mappings:
            new_mapping = VenueContextMapping(
                context_id=target_context.id,
                venue_id=mapping.venue_id,
                external_id=mapping.external_id
            )
            session.add(new_mapping)
            
        # Cloner les mappings de mouvements
        source_mappings = session.exec(
            select(MouvementContextMapping)
            .where(MouvementContextMapping.context_id == source_context.id)
        ).all()
        
        for mapping in source_mappings:
            new_mapping = MouvementContextMapping(
                context_id=target_context.id,
                mouvement_id=mapping.mouvement_id,
                external_id=mapping.external_id
            )
            session.add(new_mapping)
            
        # Mettre à jour la dernière valeur de séquence
        target_context.last_sequence_value = source_context.last_sequence_value
        target_context.updated_at = datetime.now(timezone.utc)
        session.add(target_context)
        
        session.commit()
        
        return RedirectResponse(
            url=f"/endpoints/{target_id}/context",
            status_code=status.HTTP_303_SEE_OTHER
        )
        
    except Exception as e:
        logger.exception("Error cloning structure")
        raise HTTPException(500, f"Error cloning structure: {str(e)}")

@router.get("/{endpoint_id}/context", response_class=HTMLResponse)
def show_endpoint_context(endpoint_id: int, request: Request, session: Session = Depends(get_session)):
    """Affiche le contexte d'un endpoint et tous ses mappings"""
    endpoint = session.get(SystemEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
        
    # Récupérer le contexte
    context = session.exec(
        select(EndpointContext)
        .where(EndpointContext.endpoint_id == endpoint_id)
    ).first()
    
    if not context:
        # Créer un nouveau contexte si nécessaire
        context = EndpointContext(endpoint_id=endpoint_id)
        session.add(context)
        session.commit()
        session.refresh(context)
    
    # Récupérer tous les mappings
    patient_mappings = session.exec(
        select(PatientContextMapping)
        .where(PatientContextMapping.context_id == context.id)
    ).all()
    
    dossier_mappings = session.exec(
        select(DossierContextMapping)
        .where(DossierContextMapping.context_id == context.id)
    ).all()
    
    venue_mappings = session.exec(
        select(VenueContextMapping)
        .where(VenueContextMapping.context_id == context.id)
    ).all()
    
    mouvement_mappings = session.exec(
        select(MouvementContextMapping)
        .where(MouvementContextMapping.context_id == context.id)
    ).all()
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "endpoint_context.html",
        {
            "endpoint": endpoint,
            "context": context,
            "patient_mappings": patient_mappings,
            "dossier_mappings": dossier_mappings,
            "venue_mappings": venue_mappings,
            "mouvement_mappings": mouvement_mappings
        }
    )


# ==================== ROUTES SCÉNARIOS ====================

@router.get("/{endpoint_id}/scenarios", response_class=HTMLResponse)
def endpoint_scenarios(
    endpoint_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """Affiche les scénarios disponibles pour cet endpoint avec possibilité d'exécution."""
    
    endpoint = session.get(SystemEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    # Récupérer tous les scénarios actifs avec leurs steps
    scenarios = session.exec(
        select(InteropScenario)
        .where(InteropScenario.is_active == True)
        .order_by(InteropScenario.category, InteropScenario.name)
    ).all()
    
    # Charger les steps pour chaque scénario
    for scenario in scenarios:
        scenario.steps = session.exec(
            select(InteropScenarioStep)
            .where(InteropScenarioStep.scenario_id == scenario.id)
            .order_by(InteropScenarioStep.order_index)
        ).all()
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "endpoint_scenarios.html",
        {
            "endpoint": endpoint,
            "scenarios": scenarios,
            "bound_scenario_ids": set()  # Pas de binding pour l'instant
        }
    )


@router.post("/{endpoint_id}/scenarios/{scenario_id}/execute")
async def execute_scenario_on_endpoint(
    endpoint_id: int,
    scenario_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """Exécute un scénario complet sur cet endpoint."""
    from app.services.scenario_runner import execute_scenario_on_endpoint as exec_scenario
    from app.utils.flash import flash
    
    # Vérifier que l'endpoint existe
    endpoint = session.get(SystemEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    # Vérifier que le scénario existe
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Charger les steps du scénario
    steps = session.exec(
        select(InteropScenarioStep)
        .where(InteropScenarioStep.scenario_id == scenario_id)
        .order_by(InteropScenarioStep.order_index)
    ).all()
    
    if not steps:
        flash(request, "error", f"Le scénario '{scenario.name}' n'a aucun message à exécuter.")
        return RedirectResponse(
            url=f"/endpoints/{endpoint_id}/scenarios",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    try:
        # Exécuter le scénario
        result = await exec_scenario(
            endpoint=endpoint,
            scenario=scenario,
            steps=steps,
            session=session
        )
        
        flash(request, "success", 
              f"Scénario '{scenario.name}' exécuté avec succès: {result['success_count']}/{result['total_count']} messages OK")
        
    except Exception as e:
        flash(request, "error", f"Erreur lors de l'exécution: {str(e)}")
    
    return RedirectResponse(
        url=f"/endpoints/{endpoint_id}/scenarios",
        status_code=status.HTTP_303_SEE_OTHER
    )
