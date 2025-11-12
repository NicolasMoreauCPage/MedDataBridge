from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import List, Optional
from app.db import get_session, get_next_sequence, peek_next_sequence
from app.models import Dossier, Patient, DossierType
from app.models_endpoints import SystemEndpoint
from app.models_scenarios import ScenarioBinding, InteropScenario
from app.services.emit_on_create import emit_to_senders
from app.utils.seq_generator import generate_dossier_seq
from app.services.scenario_runner import send_scenario
from app.services.scenario_capture import capture_dossier_as_template
from app.form_config import get_field_config, MODEL_FIELDS
from app.utils.flash import flash
from app.dependencies.ght import require_ght_context
from app.models_structure import UniteFonctionnelle, Service, Pole
from app.models_structure_fhir import EntiteGeographique, EntiteJuridique

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(
    prefix="/dossiers",
    tags=["dossiers"],
    dependencies=[Depends(require_ght_context)],
)

@router.get("", response_class=HTMLResponse)
def list_dossiers(
    request: Request,
    patient_id: int | None = Query(None),
    dossier_type: DossierType | None = Query(None),
    dossier_seq: int | None = Query(None),
    session=Depends(get_session)
):
    # Construction de la requête de base
    stmt = select(Dossier).options(selectinload(Dossier.venues))
    # Filtrer par contexte EJ si présent
    ej_context = getattr(request.state, "ej_context", None)
    if ej_context and getattr(ej_context, "id", None):
        # Filtrer via la relation Patient -> entite_juridique_id
        stmt = stmt.join(Patient).where(Patient.entite_juridique_id == ej_context.id)

    if patient_id:
        stmt = stmt.where(Dossier.patient_id == patient_id)
        # Récupérer les infos du patient pour le fil d'Ariane
        patient = session.get(Patient, patient_id)

    if dossier_type:
        stmt = stmt.where(Dossier.dossier_type == dossier_type)

    if dossier_seq:
        stmt = stmt.where(Dossier.dossier_seq == dossier_seq)

    # Exécuter la requête
    dossiers = session.exec(stmt).all()

    # Injecter les options de vocabulaire pour le type de dossier
    from app.services.vocabulary_lookup import get_vocabulary_options
    dossier_type_options = get_vocabulary_options("dossier-type") or [
        {"value": t.value, "label": t.value.capitalize()} for t in DossierType
    ]

    # Préparer les lignes avec les actions détaillées
    rows = [
        {
            "cells": [
                d.dossier_seq, 
                d.id, 
                d.patient_id, 
                # Récupérer l'UF depuis la première venue du dossier
                (d.venues[0].uf_responsabilite if d.venues and d.venues[0].uf_responsabilite else "N/A"),
                getattr(d, 'dossier_type', DossierType.HOSPITALISE).value.capitalize(),
                d.admit_time.strftime("%d/%m/%Y %H:%M") if d.admit_time else None,
                d.discharge_time.strftime("%d/%m/%Y %H:%M") if d.discharge_time else None
            ],
            "detail_url": f"/dossiers/{d.id}",
            "context_url": f"/context/dossier/{d.id}",
            "timeline_url": f"/timeline/dossier/{d.id}",
            "edit_url": f"/dossiers/{d.id}/edit",
            "delete_url": f"/dossiers/{d.id}/delete"
        }
        for d in dossiers
    ]

    # Construire le fil d'Ariane
    breadcrumbs = [{"label": "Dossiers", "url": "/dossiers"}]
    if patient_id and patient:
        breadcrumbs.insert(0, {"label": f"Patient: {patient.family} {patient.given}", "url": f"/patients/{patient_id}"})

    # Définir les filtres de recherche
    filters = [
        {
            "label": "Numéro de dossier",
            "name": "dossier_seq",
            "type": "number",
            "placeholder": "Numéro de dossier",
            "value": dossier_seq
        },
        {
            "label": "UF responsabilité",
            "name": "uf",
            "type": "text",
            "placeholder": "Filtrer par UF"
        },
        {
            "label": "Type de dossier",
            "name": "dossier_type",
            "type": "select",
            "placeholder": "Tous les types",
            "options": [{"value": t.value, "label": t.value.capitalize()} for t in DossierType]
        },
        {
            "label": "Type d'admission",
            "name": "admission_type",
            "type": "select",
            "placeholder": "Tous les types",
            "options": get_vocabulary_options("admission-type") or [
                {"value": "URGENCE", "label": "Urgence"},
                {"value": "PROGRAMME", "label": "Programmé"},
                {"value": "MUTATION", "label": "Mutation"}
            ]
        },
        {
            "label": "Statut",
            "name": "status",
            "type": "select",
            "placeholder": "Tous les statuts",
            "options": [
                {"value": "ACTIF", "label": "En cours"},
                {"value": "TERMINE", "label": "Terminé"}
            ]
        }
    ]

    # Définir les actions disponibles
    actions = [
        {
            "type": "link",
            "label": "Export FHIR",
            "url": "/dossiers/export/fhir"
        },
        {
            "type": "link",
            "label": "Export HL7",
            "url": "/dossiers/export/hl7"
        }
    ]

    # Construire le contexte complet
    ctx = {
        "request": request,
        "title": "Dossiers" if not patient_id else f"Dossiers du patient {patient.family} {patient.given}",
        "breadcrumbs": breadcrumbs,
        "headers": ["Seq", "ID", "Patient", "UF resp.", "Type", "Admission", "Sortie"],
        "rows": rows,
        "new_url": "/dossiers/new" + (f"?patient_id={patient_id}" if patient_id else ""),
        "filters": filters,
        "actions": actions,
        "show_actions": True,
        "dossier_type_options": dossier_type_options
    }
    return templates.TemplateResponse(request, "list.html", ctx)

@router.get("/new", response_class=HTMLResponse)
def new_dossier(request: Request, session=Depends(get_session)):
    # Vérifier qu'il y a un patient en contexte
    patient_context = getattr(request.state, "patient_context", None)
    if not patient_context:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/patients", status_code=303)
    
    # L'identifiant sera généré automatiquement basé sur le timestamp
    next_seq = None
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M")  # valeur par défaut = maintenant
    
    # Récupérer les UF de l'EJ en contexte (via jointures)
    uf_options = []
    if hasattr(request.state, "ej_context") and request.state.ej_context:
        ej_id = request.state.ej_context.id
        # Jointure: UniteFonctionnelle → Service → Pole → EntiteGeographique → EntiteJuridique
        ufs = session.exec(
            select(UniteFonctionnelle)
            .join(Service, UniteFonctionnelle.service_id == Service.id)
            .join(Pole, Service.pole_id == Pole.id)
            .join(EntiteGeographique, Pole.entite_geo_id == EntiteGeographique.id)
            .where(EntiteGeographique.entite_juridique_id == ej_id)
            .where(UniteFonctionnelle.status == "active")
        ).all()
        uf_options = [{"value": uf.identifier, "label": f"{uf.identifier} - {uf.name}"} for uf in ufs]
    
    # Types de dossier
    dossier_type_opts = [
        {"value": "hospitalise", "label": "Hospitalisé"},
        {"value": "externe", "label": "Consultation externe"},
        {"value": "urgence", "label": "Urgence"}
    ]
    
    # Construction des champs avec la configuration centralisée
    from app.services.vocabulary_lookup import get_vocabulary_options
    current_state_opts = get_vocabulary_options("dossier-current-state") or [
        {"value": v, "label": v} for v in ["Pas de venue courante", "Pré-admis consult.ext.", "Pré-admis hospit.", "Hospitalisé", "Absence temporaire", "Consultant externe"]
    ]
    base_fields = [
        {"name": "uf_responsabilite", "label": "UF de responsabilité", "type": "select", "options": uf_options},
        {"name": "dossier_type", "label": "Type de dossier", "type": "select", "options": dossier_type_opts},
        {"name": "admission_source", "label": "Source d'admission", "type": "text", "placeholder": "Domicile, Transfert, etc."},
        {"name": "attending_provider", "label": "Médecin responsable", "type": "text"},
        {"name": "admit_time", "label": "Date d'admission", "type": "datetime-local"},
        {"name": "current_state", "label": "État courant", "type": "select", "options": current_state_opts, "value": "Pas de venue courante", "readonly": True},
    ]
    
    # Enrichir les champs avec la configuration
    fields = []
    for field in base_fields:
        field_name = field["name"]
        config = get_field_config("Dossier", field_name)
        
        if field_name == "admit_time":
            field["value"] = now_str
        elif field_name == "dossier_seq":
            field["value"] = "Auto-généré"
            field["readonly"] = True
            
        # Fusionner la configuration avec les valeurs de base
        field.update(config)
        fields.append(field)
    return templates.TemplateResponse(request, "form.html", {"title": "Nouveau dossier", "fields": fields})

@router.post("/new")
def create_dossier(
    request: Request,
    patient_id_display: str = Form(None),  # Gardé pour compatibilité template, ignoré
    uf_responsabilite: str = Form(None),
    dossier_type: str = Form("hospitalise"),
    admission_source: str = Form(None),
    attending_provider: str = Form(None),
    admit_time: str = Form(...),
    dossier_seq: int | None = Form(None),
    current_state: str = Form("Pas de venue courante"),  # État initial du dossier
    # Champs supplémentaires du formulaire (ignorés)
    description: str = Form(None),
    from_location: str = Form(None),
    location: str = Form(None),
    to_location: str = Form(None),
    type: str = Form(None),
    viewport: str = Form(None),
    when: str = Form(None),
    session=Depends(get_session),
):
    # Utiliser le patient du contexte
    patient_context = getattr(request.state, "patient_context", None)
    if not patient_context:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/patients", status_code=303)
    
    patient_id = patient_context.id
    admit_dt = datetime.fromisoformat(admit_time)
    # Générer l'identifiant dossier via identifier_generator (NDA logic)
    from app.services.identifier_generator import generate_identifier
    from app.models_identifiers import IdentifierType
    from app.models_structure_fhir import IdentifierNamespace
    # Récupérer le namespace NDA actif pour l'entité juridique du patient
    ej_id = patient_context.entite_juridique_id if hasattr(patient_context, 'entite_juridique_id') else None
    nda_namespace = None
    if ej_id:
        nda_namespace = session.exec(
            select(IdentifierNamespace)
            .where(IdentifierNamespace.entite_juridique_id == ej_id)
            .where(IdentifierNamespace.type == "NDA")
            .where(IdentifierNamespace.is_active == True)
        ).first()
    if nda_namespace:
        seq = dossier_seq or generate_identifier(session, nda_namespace, IdentifierType.NDA)
    else:
        # Fallback: use old logic if no namespace found
        from app.utils.seq_generator import generate_dossier_seq
        seq = dossier_seq or generate_dossier_seq()
    d = Dossier(
        patient_id=patient_id,
        uf_responsabilite=uf_responsabilite,
        dossier_type=DossierType(dossier_type),
        admission_source=admission_source,
        attending_provider=attending_provider,
        admit_time=admit_dt,
        dossier_seq=seq,
        current_state=current_state,  # Utiliser la valeur du formulaire
        entite_juridique_id=getattr(patient_context, 'entite_juridique_id', None)
    )
    session.add(d)
    session.commit()
    session.refresh(d)  # Assurer que l'ID est disponible
    
    # ⚠️ IMPORTANT : La création d'un dossier génère un message FHIR EpisodeOfCare
    # et PAS de message IHE PAM
    from app.services.emit_on_create import generate_fhir
    generate_fhir(d, "dossier", session)
    
    # À la place, on crée automatiquement une VENUE qui génère le message ADT^A05 (Pre-admit)
    from app.models import Venue
    from app.db import get_next_sequence
    
    venue_seq = get_next_sequence(session, "venue")
    venue = Venue(
        dossier_id=d.id,
        uf_responsabilite=uf_responsabilite,
        start_time=admit_dt,
        hospital_service=None,  # Sera défini plus tard si nécessaire
        assigned_location=None,
        attending_provider=attending_provider,
        venue_seq=venue_seq,
        code="PRE_ADMIT",
        label="Pré-admission automatique"
    )
    session.add(venue)
    session.commit()
    
    # La venue génère le message ADT^A05
    emit_to_senders(venue, "venue", session)
    
    # Support AJAX/JSON and HTML responses
    if request.headers.get("Accept") == "application/json":
        return {"message": "Enregistrement réussi", "redirect": "/dossiers"}
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dossiers", status_code=303)
@router.get("/{dossier_id}", response_class=HTMLResponse)
def dossier_detail(dossier_id: int, request: Request, session=Depends(get_session)):

    d = session.exec(select(Dossier).where(Dossier.id == dossier_id).options(selectinload(Dossier.venues))).first()
    if not d:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Dossier introuvable"}, status_code=404)
    # Définir le contexte dossier en session
    request.session["dossier_id"] = d.id
    if hasattr(d, 'patient') and d.patient:
        request.session["patient_id"] = d.patient.id
    session.refresh(d, attribute_names=["patient", "venues"])
    for v in d.venues:
        session.refresh(v, attribute_names=["mouvements"])

    patient = d.patient if hasattr(d, 'patient') else None

    bindings = session.exec(
        select(ScenarioBinding).where(ScenarioBinding.dossier_id == dossier_id)
    ).all()
    scenario_entries = []
    for binding in bindings:
        scenario = session.get(InteropScenario, binding.scenario_id)
        if scenario:
            scenario_entries.append({"binding": binding, "scenario": scenario})

    endpoints = session.exec(
        select(SystemEndpoint)
        .where(SystemEndpoint.is_enabled == True)
        .where(SystemEndpoint.role.in_(["sender", "both"]))
        .order_by(SystemEndpoint.name)
    ).all()

    from app.services.vocabulary_lookup import get_vocabulary_options
    dossier_type_options = get_vocabulary_options("dossier-type") or [
        {"value": t.value, "label": t.value.capitalize()} for t in DossierType
    ]
    admission_type_options = get_vocabulary_options("admission-type") or [
        {"value": "URGENCE", "label": "Urgence"},
        {"value": "PROGRAMME", "label": "Programmé"},
        {"value": "MUTATION", "label": "Mutation"}
    ]
    discharge_disp_options = get_vocabulary_options("discharge-disposition") or []
    return templates.TemplateResponse(request, "dossier_detail.html", {
            "dossier": d,
            "patient": patient,
            "scenario_entries": scenario_entries,
            "replay_endpoints": endpoints,
            "dossier_type_options": dossier_type_options,
            "admission_type_options": admission_type_options,
            "discharge_disp_options": discharge_disp_options,
        })


@router.get("/{dossier_id}/edit", response_class=HTMLResponse)
def edit_dossier(dossier_id: int, request: Request, session=Depends(get_session)):
    d = session.get(Dossier, dossier_id)
    if not d:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Dossier introuvable"}, status_code=404)
    
    session.refresh(d, attribute_names=["venues"])
    
    # Récupérer les UF de l'EJ en contexte (via jointures)
    uf_options = []
    if hasattr(request.state, "ej_context") and request.state.ej_context:
        ej_id = request.state.ej_context.id
        # Jointure: UniteFonctionnelle → Service → Pole → EntiteGeographique → EntiteJuridique
        ufs = session.exec(
            select(UniteFonctionnelle)
            .join(Service, UniteFonctionnelle.service_id == Service.id)
            .join(Pole, Service.pole_id == Pole.id)
            .join(EntiteGeographique, Pole.entite_geo_id == EntiteGeographique.id)
            .where(EntiteGeographique.entite_juridique_id == ej_id)
            .where(UniteFonctionnelle.status == "active")
        ).all()
        uf_options = [{"value": uf.identifier, "label": f"{uf.identifier} - {uf.name}"} for uf in ufs]
    
    # Types de dossier
    dossier_type_opts = [
        {"value": "hospitalise", "label": "Hospitalisé"},
        {"value": "externe", "label": "Consultation externe"},
        {"value": "urgence", "label": "Urgence"}
    ]
    
    # Get uf_responsabilite value safely
    uf_responsabilite_value = None
    if d.venues and len(d.venues) > 0:
        uf_responsabilite_value = d.venues[0].uf_responsabilite
    
    fields = [
        {"label": "Patient ID", "name": "patient_id", "type": "number", "value": d.patient_id},
        {"label": "UF de responsabilité", "name": "uf_responsabilite", "type": "select", "options": uf_options, "value": uf_responsabilite_value},
        {"label": "Type de dossier", "name": "dossier_type", "type": "select", "options": dossier_type_opts, "value": d.dossier_type.value if d.dossier_type else "hospitalise"},
        {"label": "Source d'admission", "name": "admission_source", "type": "text", "value": getattr(d, "admission_source", None), "placeholder": "Domicile, Transfert, etc."},
        {"label": "Médecin responsable", "name": "attending_provider", "type": "text", "value": getattr(d,'attending_provider',None)},
        {"label": "Date d'admission", "name": "admit_time", "type": "datetime-local", "value": d.admit_time.strftime('%Y-%m-%dT%H:%M') if d.admit_time else ''},
        {"label": "Numéro de séquence", "name": "dossier_seq", "type": "number", "value": d.dossier_seq, "readonly": True},
    ]
    return templates.TemplateResponse(request, "form.html", {"title": "Modifier dossier", "fields": fields, "action_url": f"/dossiers/{dossier_id}/edit"})



@router.post("/{dossier_id}/edit")
def update_dossier(
    dossier_id: int,
    patient_id: int = Form(...),
    uf_responsabilite: str = Form(...),
    dossier_type: str = Form("hospitalise"),
    admission_source: str = Form(None),
    attending_provider: str = Form(None),
    admit_time: str = Form(...),
    dossier_seq: int = Form(...),
    session=Depends(get_session),
    request: Request = None,
):
    d = session.get(Dossier, dossier_id)
    if not d:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Dossier introuvable"}, status_code=404)
    
    session.refresh(d, attribute_names=["venues"])
    d.patient_id = patient_id
    # Update the first venue's uf_responsabilite
    if d.venues:
        d.venues[0].uf_responsabilite = uf_responsabilite
    d.dossier_type = DossierType(dossier_type)
    d.admission_source = admission_source
    d.attending_provider = attending_provider
    d.admit_time = datetime.fromisoformat(admit_time)
    d.dossier_seq = dossier_seq
    session.add(d); session.commit()
    emit_to_senders(d, "dossier", session)
    return RedirectResponse(url="/dossiers", status_code=303)


@router.post("/{dossier_id}/replay")
async def replay_dossier_scenario(
    dossier_id: int,
    request: Request,
    scenario_id: int = Form(...),
    endpoint_ids: List[str] = Form(...),
    identifier_prefix_ipp: Optional[str] = Form(None),
    identifier_prefix_nda: Optional[str] = Form(None),
    use_test_namespace: bool = Form(False),
    session=Depends(get_session),
):
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Dossier introuvable"}, status_code=404)

    if not endpoint_ids:
        flash(request, "Veuillez sélectionner au moins un endpoint expéditeur.", level="error")
        return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=303)

    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        flash(request, "Scénario introuvable pour ce dossier.", level="error")
        return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=303)

    try:
        endpoint_ids_int = [int(eid) for eid in endpoint_ids]
    except ValueError:
        flash(request, "Identifiants d'endpoint invalides.", level="error")
        return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=303)

    endpoints = session.exec(
        select(SystemEndpoint)
        .where(SystemEndpoint.id.in_(endpoint_ids_int))
        .where(SystemEndpoint.role.in_(["sender", "both"]))
    ).all()

    if not endpoints:
        flash(request, "Aucun endpoint valide sélectionné.", level="error")
        return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=303)

    # Créer ou mettre à jour le ScenarioBinding avec configuration des préfixes
    binding = session.exec(
        select(ScenarioBinding).where(
            ScenarioBinding.scenario_id == scenario_id,
            ScenarioBinding.dossier_id == dossier_id
        )
    ).first()
    
    if not binding:
        binding = ScenarioBinding(
            scenario_id=scenario_id,
            dossier_id=dossier_id
        )
    
    # Mettre à jour configuration préfixes
    binding.use_test_namespace = use_test_namespace
    binding.identifier_prefix_ipp = identifier_prefix_ipp.strip() if identifier_prefix_ipp else None
    binding.identifier_prefix_nda = identifier_prefix_nda.strip() if identifier_prefix_nda else None
    session.add(binding)
    session.commit()
    session.refresh(binding)

    summary_lines = []
    for endpoint in endpoints:
        try:
            logs = await send_scenario(session, scenario, endpoint, binding=binding)
        except Exception as exc:
            flash(request, f"{endpoint.name}: {exc}", level="error")
            continue
        sent = sum(1 for log in logs if log.status == "sent")
        skipped = sum(1 for log in logs if log.status == "skipped")
        errors = [log for log in logs if log.status not in {"sent", "skipped"}]
        line = f"{endpoint.name}: {sent} envoyés"
        if skipped:
            line += f", {skipped} ignorés"
        if errors:
            line += f", {len(errors)} erreurs"
        summary_lines.append(line)
        
    # Ajouter info sur identifiants générés
    if binding.generated_ipp or binding.generated_nda:
        ids_info = f"Identifiants générés: IPP={binding.generated_ipp or 'N/A'}, NDA={binding.generated_nda or 'N/A'}"
        summary_lines.append(ids_info)

    if not summary_lines:
        return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=303)
    flash(
        request,
        "Relecture du scénario terminée. " + " ; ".join(summary_lines),
        level="success",
    )
    return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=303)


@router.post("/{dossier_id}/capture-as-template")
def capture_dossier_template(
    dossier_id: int,
    request: Request,
    template_name: Optional[str] = Form(None),
    template_description: Optional[str] = Form(None),
    session=Depends(get_session),
):
    """
    Capture un dossier existant comme ScenarioTemplate réutilisable.
    
    Le template créé est INDÉPENDANT du dossier source :
    - Snapshot des données à l'instant T (pas de référence FK)
    - Modification/suppression du dossier n'affecte pas le template
    - Le template peut être rejoué comme les templates IHE importés
    """
    try:
        template = capture_dossier_as_template(
            db=session,
            dossier_id=dossier_id,
            template_name=template_name,
            template_description=template_description,
            category="captured",
        )
        flash(
            request,
            f"Template '{template.name}' créé avec succès (clé: {template.key}). "
            f"Retrouvez-le dans /scenarios/templates",
            level="success",
        )
    except ValueError as exc:
        flash(request, f"Erreur capture: {exc}", level="error")
    except Exception as exc:
        flash(request, f"Erreur inattendue: {exc}", level="error")
    
    return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=303)


@router.post("/{dossier_id}/delete")
def delete_dossier(dossier_id: int, request: Request, session=Depends(get_session)):
    d = session.get(Dossier, dossier_id)
    if not d:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Dossier introuvable"}, status_code=404)
    session.delete(d); session.commit()
    emit_to_senders(d, "dossier", session)
    return RedirectResponse(url="/dossiers", status_code=303)
