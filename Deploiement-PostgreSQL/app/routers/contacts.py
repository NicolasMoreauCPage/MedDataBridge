"""
Routes CRUD pour PatientContact et VenueContact (UI HTML)
"""
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select
from app.db import get_session
from app.models_contacts import PatientContact, VenueContact
from app.models import Patient, Venue
from app.dependencies.ght import require_ght_context

router = APIRouter(
    prefix="/contacts",
    tags=["contacts"],
    dependencies=[Depends(require_ght_context)],
)

def get_templates(request: Request):
    return request.app.state.templates

@router.get("", response_class=HTMLResponse)
def list_contacts(request: Request, session=Depends(get_session)):
    """Liste tous les contacts (patients et venues)."""
    patient_contacts = session.exec(select(PatientContact)).all()
    venue_contacts = session.exec(select(VenueContact)).all()
    ctx = {
        "request": request,
        "title": "Contacts",
        "patient_contacts": patient_contacts,
        "venue_contacts": venue_contacts,
        "new_url": "/contacts/new",
    }
    templates = get_templates(request)
    return templates.TemplateResponse(request, "contacts_list.html", ctx)

@router.get("/new", response_class=HTMLResponse)
def new_contact(request: Request):
    """Formulaire de création d'un contact."""
    templates = get_templates(request)
    return templates.TemplateResponse(request, "contact_form.html", {"title": "Nouveau contact", "contact": None, "action_url": "/contacts/new"})

@router.post("/new")
def create_contact(
    request: Request,
    contact_type: str = Form(...),
    patient_id: int = Form(None),
    venue_id: int = Form(None),
    family_name: str = Form(...),
    given_name: str = Form(None),
    relationship_code: str = Form(...),
    phone_number: str = Form(None),
    business_phone: str = Form(None),
    email: str = Form(None),
    address_line1: str = Form(None),
    address_line2: str = Form(None),
    address_city: str = Form(None),
    address_postalcode: str = Form(None),
    address_country: str = Form(None),
    contact_role: str = Form(None),
    session=Depends(get_session)
):
    """Crée un contact patient ou venue."""
    import re
    error = None
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        error = "Format d'email invalide."
    if address_postalcode and not re.match(r"^\d{5}$", address_postalcode):
        error = "Code postal invalide (5 chiffres attendus)."
    if error:
        templates = get_templates(request)
        return templates.TemplateResponse(request, "contact_form.html", {
            "title": "Nouveau contact",
            "contact": None,
            "action_url": "/contacts/new",
            "error": error
        })
    if contact_type == "patient":
        contact = PatientContact(
            patient_id=patient_id,
            family_name=family_name,
            given_name=given_name,
            relationship_code=relationship_code,
            phone_number=phone_number,
            business_phone=business_phone,
            email=email,
            address_line1=address_line1,
            address_line2=address_line2,
            address_city=address_city,
            address_postalcode=address_postalcode,
            address_country=address_country,
            contact_role=contact_role
        )
    else:
        contact = VenueContact(
            venue_id=venue_id,
            family_name=family_name,
            given_name=given_name,
            relationship_code=relationship_code,
            phone_number=phone_number,
            business_phone=business_phone,
            email=email,
            address_line1=address_line1,
            address_line2=address_line2,
            address_city=address_city,
            address_postalcode=address_postalcode,
            address_country=address_country,
            contact_role=contact_role
        )
    session.add(contact)
    session.commit()
    return RedirectResponse(url="/contacts", status_code=303)

@router.get("/{contact_id:int}/edit", response_class=HTMLResponse)
def edit_contact(contact_id: int, request: Request, session=Depends(get_session)):
    """Formulaire d'édition d'un contact."""
    contact = session.get(PatientContact, contact_id) or session.get(VenueContact, contact_id)
    templates = get_templates(request)
    if not contact:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Contact introuvable"}, status_code=404)
    return templates.TemplateResponse(request, "contact_form.html", {"title": "Modifier contact", "contact": contact, "action_url": f"/contacts/{contact_id}/edit"})

@router.post("/{contact_id:int}/edit")
def update_contact(
    contact_id: int,
    family_name: str = Form(...),
    given_name: str = Form(None),
    relationship_code: str = Form(...),
    phone_number: str = Form(None),
    business_phone: str = Form(None),
    email: str = Form(None),
    address_line1: str = Form(None),
    address_line2: str = Form(None),
    address_city: str = Form(None),
    address_postalcode: str = Form(None),
    address_country: str = Form(None),
    contact_role: str = Form(None),
    session=Depends(get_session),
    request: Request = None
):
    """Met à jour un contact patient ou venue."""
    contact = session.get(PatientContact, contact_id) or session.get(VenueContact, contact_id)
    if not contact:
        templates = get_templates(request)
        return templates.TemplateResponse(request, "not_found.html", {"title": "Contact introuvable"}, status_code=404)
    import re
    error = None
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        error = "Format d'email invalide."
    if address_postalcode and not re.match(r"^\d{5}$", address_postalcode):
        error = "Code postal invalide (5 chiffres attendus)."
    if error:
        templates = get_templates(request)
        return templates.TemplateResponse(request, "contact_form.html", {
            "title": "Modifier contact",
            "contact": contact,
            "action_url": f"/contacts/{contact_id}/edit",
            "error": error
        })
    contact.family_name = family_name
    contact.given_name = given_name
    contact.relationship_code = relationship_code
    contact.phone_number = phone_number
    contact.business_phone = business_phone
    contact.email = email
    contact.address_line1 = address_line1
    contact.address_line2 = address_line2
    contact.address_city = address_city
    contact.address_postalcode = address_postalcode
    contact.address_country = address_country
    contact.contact_role = contact_role
    session.add(contact)
    session.commit()
    return RedirectResponse(url="/contacts", status_code=303)

@router.post("/{contact_id:int}/delete")
def delete_contact(contact_id: int, request: Request, session=Depends(get_session)):
    """Supprime un contact patient ou venue."""
    contact = session.get(PatientContact, contact_id) or session.get(VenueContact, contact_id)
    templates = get_templates(request)
    if not contact:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Contact introuvable"}, status_code=404)
    session.delete(contact)
    session.commit()
    return RedirectResponse(url="/contacts", status_code=303)
