from fastapi import APIRouter, Depends, Request, Form, Body
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse, RedirectResponse
from app.models import Patient, DossierType
from app.db import get_session
from app.dependencies.ght import require_ght_context
from sqlmodel import select
from app.routers.contacts import get_templates
from app.services.vocabulary_lookup import get_vocabulary_options
from app.utils.seq_generator import generate_patient_seq

router = APIRouter(
    prefix="/patients",
    tags=["patients"],
    dependencies=[Depends(require_ght_context)],
)

@router.post("/api/patients", response_class=JSONResponse)
async def api_create_patient(
    family: str = Body(...),
    given: str = Body(None),
    birth_date: str = Body(None),
    session=Depends(get_session)
):
    # API REST pour créer un patient (utilisé par les tests d'intégration)
    try:
        patient = Patient(family=family, given=given, birth_date=birth_date)
        session.add(patient)
        session.commit()
        session.refresh(patient)
        return {"id": patient.id, "family": patient.family, "given": patient.given, "birth_date": patient.birth_date}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

    # Génération aléatoire
    gender = random.choice(["M", "F", "U"])
    
    if gender == "M":
        given = random.choice(given_names_m)
        prefix = "M."
    elif gender == "F":
        given = random.choice(given_names_f)
        prefix = random.choice(["Mme", "Mlle"])
    else:
        given = random.choice(given_names_m + given_names_f)
        prefix = ""
    
    family = random.choice(family_names)
    middle = random.choice([None, None, random.choice(middle_names)])  # 33% chance
    
    # Date de naissance (entre 18 et 95 ans)
    age_days = random.randint(18*365, 95*365)
    birth_date = (datetime.now() - timedelta(days=age_days)).strftime("%Y-%m-%d")
    
    # Adresse
    street_number = random.randint(1, 200)
    street = random.choice(streets)
    city = random.choice(cities)
    postal_code = f"{random.randint(1, 95):05d}"
    
    # Téléphone
    phone = f"0{random.randint(1, 5)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}"
    mobile = f"0{random.randint(6, 7)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}"
    
    # Email
    email = f"{given.lower()}.{family.lower()}@example.fr"
    
    # NIR (fake mais format valide)
    gender_code = "1" if gender == "M" else "2"
    year = birth_date[2:4]
    month = birth_date[5:7]
    dept = f"{random.randint(1, 95):02d}"
    commune = f"{random.randint(1, 999):03d}"
    ordre = f"{random.randint(1, 999):03d}"
    nir = f"{gender_code} {year} {month} {dept} {commune} {ordre}"
    
    # Statut marital
    marital_status = random.choice(["S", "M", "D", "W", ""])
    
    return {
        "prefix": prefix,
        "family": family,
        "given": given,
        "middle": middle or "",
        "birth_date": birth_date,
        "gender": gender,
        "address": f"{street_number} {street}",
        "city": city,
        "postal_code": postal_code,
        "country": "FRA",
        "phone": phone,
        "mobile": mobile,
        "email": email,
        "nir": nir,
        "marital_status": marital_status,
        "nationality": "FRA"
    }



router = APIRouter(
    prefix="/patients",
    tags=["patients"],
    dependencies=[Depends(require_ght_context)],
)

@router.post("/api/patients", response_class=JSONResponse)
async def api_create_patient(
    family: str = Body(...),
    given: str = Body(None),
    birth_date: str = Body(None),
    session=Depends(get_session)
):
    # API REST pour créer un patient (utilisé par les tests d'intégration)
    try:
        patient = Patient(family=family, given=given, birth_date=birth_date)
        session.add(patient)
        session.commit()
        session.refresh(patient)
        return {"id": patient.id, "family": patient.family, "given": patient.given, "birth_date": patient.birth_date}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@router.get("", response_class=HTMLResponse)
def list_patients(request: Request, session=Depends(get_session)):
    # Liste paginée des patients (vue HTML)
    ght_context = getattr(request.state, "ght_context", None)
    ej_context = getattr(request.state, "ej_context", None)
    query = select(Patient)
    # Si EJ sélectionné, filtrer uniquement par EJ
    if ej_context and getattr(ej_context, "id", None):
        query = query.where(Patient.entite_juridique_id == ej_context.id)
    elif ght_context and getattr(ght_context, "id", None):
        query = query.where(Patient.ght_context_id == ght_context.id)
    patients = session.exec(query).all()
    rows = [
        {
            "cells": [p.id, p.external_id, f"{p.family} {p.given}", p.birth_date, p.gender],
            "detail_url": f"/patients/{p.id}",
            "context_url": f"/context/patient/{p.id}",
            "timeline_url": f"/timeline/patient/{p.id}",
            "edit_url": f"/patients/{p.id}/edit",
            "delete_url": f"/patients/{p.id}/delete"
        }
        for p in patients
    ]

    # Définir le fil d'Ariane
    breadcrumbs = [
        {"label": "Patients", "url": "/patients"}
    ]
    
    # Définir les filtres
    filters = [
        {
            "label": "Nom",
            "name": "name",
            "type": "text",
            "placeholder": "Rechercher par nom"
        },
        {
            "label": "Genre",
            "name": "gender",
            "type": "select",
            "placeholder": "Tous les genres",
            "options": [
                {"value": "male", "label": "Homme"},
                {"value": "female", "label": "Femme"},
                {"value": "other", "label": "Autre"},
                {"value": "unknown", "label": "Non spécifié"}
            ]
        }
    ]

    # Définir les actions supplémentaires
    actions = [
        {
            "type": "link",
            "label": "Export FHIR",
            "url": "/patients/export/fhir"
        },
        {
            "type": "link", 
            "label": "Import FHIR",
            "url": "/patients/import/fhir"
        }
    ]

    debug_info = f"EJ context: {getattr(ej_context, 'id', None)} | GHT context: {getattr(ght_context, 'id', None)} | patients: {len(rows)}"
    ctx = {
        "request": request,
        "title": "Patients",
        "breadcrumbs": breadcrumbs,
        "headers": ["ID", "ExtID", "Nom", "Date naiss.", "Genre"],
        "rows": rows,
        "new_url": "/patients/new",
        "filters": filters,
        "actions": actions,
        "show_actions": True,
        "ght_context": ght_context,
        "debug_info": debug_info,
    }
    
    templates = get_templates(request)
    return templates.TemplateResponse(request, "list.html", ctx)


@router.get("/{patient_id:int}", response_class=HTMLResponse)
def patient_detail(patient_id: int, request: Request, session=Depends(get_session)):
    # Affiche le détail d'un patient (lecture seule)
    p = session.get(Patient, patient_id)
    templates = get_templates(request)
    if not p:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Patient introuvable"}, status_code=404)

    # Définir le contexte patient en session
    request.session["patient_id"] = p.id

    # Charger la hiérarchie dossiers > venues > mouvements
    dossiers = session.exec(select(type(p.dossiers[0])).where(type(p.dossiers[0]).patient_id == p.id)).all() if p.dossiers else []
    
    from app.services.vocabulary_lookup import get_vocabulary_options
    dossier_type_options = get_vocabulary_options("dossier-type") or [
        {"value": t.value, "label": t.value.capitalize()} for t in DossierType] if dossiers else []
    discharge_disp_options = get_vocabulary_options("discharge-disposition") or []
    
    for dossier in dossiers:
        dossier.venues = session.exec(select(type(dossier.venues[0])).where(type(dossier.venues[0]).dossier_id == dossier.id)).all() if dossier.venues else []
        for venue in dossier.venues:
            venue.mouvements = session.exec(select(type(venue.mouvements[0])).where(type(venue.mouvements[0]).venue_id == venue.id)).all() if venue.mouvements else []
    return templates.TemplateResponse(request, "patient_detail.html", {
        "patient": p,
        "dossiers": dossiers,
        "dossier_type_options": dossier_type_options,
        "discharge_disp_options": discharge_disp_options
    })


@router.get("/{patient_id:int}/edit", response_class=HTMLResponse)
def edit_patient(patient_id: int, request: Request, session=Depends(get_session)):
    # Affiche le formulaire d'édition d'un patient existant (conforme RGPD France)
    p = session.get(Patient, patient_id)
    templates = get_templates(request)
    if not p:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Patient introuvable"}, status_code=404)
    
    # Options dynamiques (fallback enum via service si vocabulaire absent)
    # HL7 Table 0445 - Identity Reliability Code (IHE PAM France)
    identity_opts = get_vocabulary_options("identity-reliability-rniv") or [
        {"value": code, "label": label} for code, label in [
            ("VALI", "Validée (avec INS qualifié)"),
            ("PROV", "Provisoire"),
            ("VIDE", "Non qualifiée"),
            ("DOUB", "Doublon détecté"),
            ("DESA", "Désactivée"),
            ("IDVER", "Vérifiée"),
            ("ANOM", "Anonyme")
        ]
    ]
    # Statuts maritaux HL7v2
    marital_opts = get_vocabulary_options("marital-status") or [
        {"value": c, "label": l} for c, l in [
            ("S", "Célibataire"), ("M", "Marié"), ("D", "Divorcé"), ("W", "Veuf"),
            ("P", "Partenaire"), ("A", "Séparé"), ("U", "Inconnu")
        ]
    ]
    ins_type_opts = get_vocabulary_options("ins-type") or [
        {"value": v, "label": v} for v in ["NIR", "INS-C"]
    ]
    gender_opts = get_vocabulary_options("administrative-gender-v2") or [
        {"value": c, "label": l} for c, l in [
            ("M", "Masculin"), ("F", "Féminin"), ("O", "Autre"), ("U", "Indéterminé")
        ]
    ]
    country_opts = get_vocabulary_options("country-codes") or [
        {"value": c, "label": l} for c, l in [
            ("FRA", "🇫🇷 France"), ("BEL", "🇧🇪 Belgique"), ("CHE", "🇨🇭 Suisse"),
            ("LUX", "🇱🇺 Luxembourg"), ("DEU", "🇩🇪 Allemagne"), ("ITA", "🇮🇹 Italie"),
            ("ESP", "🇪🇸 Espagne"), ("GBR", "🇬🇧 Royaume-Uni")
        ]
    ]
    return templates.TemplateResponse(request, "patient_form.html", {
        "title": "Modifier patient",
        "patient": p,
        "action_url": f"/patients/{patient_id}/edit",
        "sample_data": {},
        "identity_reliability_options": identity_opts,
        "marital_status_options": marital_opts,
        "ins_type_options": ins_type_opts,
        "gender_options": gender_opts,
        "country_options": country_opts,
    })


@router.post("/{patient_id:int}/edit")
def update_patient(
    patient_id: int,
    external_id: str = Form(None),
    family: str = Form(...),
    given: str = Form(...),
    birth_date: str = Form(None),
    gender: str = Form(None),
    middle: str = Form(None),
    prefix: str = Form(None),
    suffix: str = Form(None),
    birth_family: str = Form(None),
    address: str = Form(None),
    city: str = Form(None),
    state: str = Form(None),
    postal_code: str = Form(None),
    country: str = Form(None),
    phone: str = Form(None),
    mobile: str = Form(None),
    work_phone: str = Form(None),
    email: str = Form(None),
    birth_address: str = Form(None),
    birth_city: str = Form(None),
    birth_state: str = Form(None),
    birth_postal_code: str = Form(None),
    birth_country: str = Form(None),
    marital_status: str = Form(None),
    mothers_maiden_name: str = Form(None),
    primary_care_provider: str = Form(None),
    nir: str = Form(None),
    nationality: str = Form(None),
    identity_reliability_code: str = Form(None),
    session=Depends(get_session),
    request: Request = None,
):
    # Met à jour un patient existant (conforme RGPD - pas de race/religion)
    p = session.get(Patient, patient_id)
    if not p:
        templates = get_templates(request)
        if not p:
            return templates.TemplateResponse(request, "not_found.html", {"title": "Patient introuvable"}, status_code=404)
    # Mise à jour des champs - Identité
    p.external_id = external_id or p.external_id
    p.family = family
    p.given = given
    p.middle = middle
    p.prefix = prefix
    p.suffix = suffix
    p.birth_family = birth_family
    p.birth_date = birth_date
    p.gender = gender
    
    # Coordonnées domicile
    p.address = address
    p.city = city
    p.state = state
    p.postal_code = postal_code
    p.country = country
    p.phone = phone
    p.mobile = mobile
    p.work_phone = work_phone
    p.email = email
    
    # Lieu de naissance
    p.birth_address = birth_address
    p.birth_city = birth_city
    p.birth_state = birth_state
    p.birth_postal_code = birth_postal_code
    p.birth_country = birth_country
    
    # Informations administratives
    p.marital_status = marital_status
    p.mothers_maiden_name = mothers_maiden_name
    p.primary_care_provider = primary_care_provider
    p.nir = nir
    p.nationality = nationality
    p.identity_reliability_code = identity_reliability_code
    
    # RGPD: on ne met PAS à jour race/religion/ssn/administrative_gender
    
    session.add(p)
    # Force SQLAlchemy to detect changes even if values are the same
    from sqlalchemy.orm import attributes
    attributes.flag_modified(p, "family")  # Flag at least one column as modified
    session.flush()  # Trigger before_update/after_update events
    session.commit()
    # Note: L'émission automatique est gérée par entity_events.py (after_update listener)
    return RedirectResponse(url="/patients", status_code=303)


@router.post("/{patient_id:int}/delete")
def delete_patient(patient_id: int, request: Request, session=Depends(get_session)):
    # Supprime un patient et revient à la liste
    p = session.get(Patient, patient_id)
    templates = get_templates(request)
    if not p:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Patient introuvable"}, status_code=404)
    session.delete(p)
    session.commit()
    # Note: L'émission automatique pour les suppressions n'est pas encore implémentée
    return RedirectResponse(url="/patients", status_code=303)

@router.get("/new", response_class=HTMLResponse)
def new_patient(request: Request, session=Depends(get_session)):
    # Affiche le formulaire de création d'un patient (conforme RGPD France)
    # L'identifiant sera généré automatiquement basé sur le timestamp
    # Pas besoin de pré-générer un numéro de séquence
    next_seq = None
    
    # Générer des données de démonstration pré-remplies
    sample_data = {}
    
    # HL7 Table 0445 - Identity Reliability Code (IHE PAM France)
    identity_opts = get_vocabulary_options("identity-reliability-rniv") or [
        {"value": code, "label": label} for code, label in [
            ("VALI", "Validée (avec INS qualifié)"),
            ("PROV", "Provisoire"),
            ("VIDE", "Non qualifiée"),
            ("DOUB", "Doublon détecté"),
            ("DESA", "Désactivée"),
            ("IDVER", "Vérifiée"),
            ("ANOM", "Anonyme")
        ]
    ]
    marital_opts = get_vocabulary_options("marital-status") or [
        {"value": c, "label": l} for c, l in [
            ("S", "Célibataire"), ("M", "Marié"), ("D", "Divorcé"), ("W", "Veuf"),
            ("P", "Partenaire"), ("A", "Séparé"), ("U", "Inconnu")
        ]
    ]
    ins_type_opts = get_vocabulary_options("ins-type") or [
        {"value": v, "label": v} for v in ["NIR", "INS-C"]
    ]
    gender_opts = get_vocabulary_options("administrative-gender-v2") or [
        {"value": c, "label": l} for c, l in [
            ("M", "Masculin"), ("F", "Féminin"), ("O", "Autre"), ("U", "Indéterminé")
        ]
    ]
    country_opts = get_vocabulary_options("country-codes") or [
        {"value": c, "label": l} for c, l in [
            ("FRA", "🇫🇷 France"), ("BEL", "🇧🇪 Belgique"), ("CHE", "🇨🇭 Suisse"),
            ("LUX", "🇱🇺 Luxembourg"), ("DEU", "🇩🇪 Allemagne"), ("ITA", "🇮🇹 Italie"),
            ("ESP", "🇪🇸 Espagne"), ("GBR", "🇬🇧 Royaume-Uni")
        ]
    ]
    templates = get_templates(request)
    return templates.TemplateResponse(request, "patient_form.html", {
        "title": "Nouveau patient",
        "patient": None,
        "next_seq": next_seq,
        "action_url": "/patients/new",
        "sample_data": sample_data,
        "identity_reliability_options": identity_opts,
        "marital_status_options": marital_opts,
        "ins_type_options": ins_type_opts,
        "gender_options": gender_opts,
        "country_options": country_opts,
    })

@router.post("/new")
async def create_patient(
    request: Request,
    patient_seq: int = Form(None),
    external_id: str = Form(None),
    family: str = Form(...),
    given: str = Form(...),
    middle: str = Form(None),
    prefix: str = Form(None),
    suffix: str = Form(None),
    birth_family: str = Form(None),
    birth_date: str = Form(None),
    gender: str = Form(None),
    address: str = Form(None),
    city: str = Form(None),
    state: str = Form(None),
    postal_code: str = Form(None),
    country: str = Form(None),
    phone: str = Form(None),
    mobile: str = Form(None),
    work_phone: str = Form(None),
    email: str = Form(None),
    birth_address: str = Form(None),
    birth_city: str = Form(None),
    birth_state: str = Form(None),
    birth_postal_code: str = Form(None),
    birth_country: str = Form(None),
    nir: str = Form(None),
    marital_status: str = Form(None),
    nationality: str = Form(None),
    identity_reliability_code: str = Form(None),
    mothers_maiden_name: str = Form(None),
    primary_care_provider: str = Form(None),
    session=Depends(get_session)
):
    # Crée un nouveau patient (conforme RGPD - pas de race/religion) et redirige
    is_ajax = request.headers.get('accept') == 'application/json'

    try:
        # Générer l'identifiant patient basé sur timestamp (12 chiffres, préfixe '9')
        if patient_seq is None:
            patient_seq = generate_patient_seq()
        
        # Générer l'IPP automatiquement si non fourni
        if not identifier:
            identifier = str(generate_patient_seq())
        
        ght_context = getattr(request.state, "ght_context", None)
        patient = Patient(
            patient_seq=patient_seq,
            external_id=external_id,
            identifier=identifier,
            family=family,
            given=given,
            middle=middle,
            prefix=prefix,
            suffix=suffix,
            birth_family=birth_family,
            birth_date=birth_date,
            gender=gender,
            address=address,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            phone=phone,
            mobile=mobile,
            work_phone=work_phone,
            email=email,
            birth_address=birth_address,
            birth_city=birth_city,
            birth_state=birth_state,
            birth_postal_code=birth_postal_code,
            birth_country=birth_country,
            nir=nir,
            marital_status=marital_status,
            nationality=nationality,
            identity_reliability_code=identity_reliability_code,
            mothers_maiden_name=mothers_maiden_name,
            primary_care_provider=primary_care_provider,
            ght_context_id=getattr(ght_context, "id", None)
        )
        session.add(patient)
        session.commit()
        # Note: L'émission automatique est gérée par entity_events.py (after_insert listener)
        try:
            from app.utils.flash import flash as _flash
            _flash(request, "Enregistrement patient réussi", "success")
        except Exception:
            pass

        if is_ajax:
            return {"status": "success", "message": "Patient créé avec succès", "redirect": "/patients"}
        return RedirectResponse(url="/patients", status_code=303)

    except Exception as e:
        session.rollback()
        if is_ajax:
            return {"status": "error", "message": str(e)}
        # En cas d'erreur, retourner au formulaire avec les données
        return RedirectResponse(url="/patients/new", status_code=303)
