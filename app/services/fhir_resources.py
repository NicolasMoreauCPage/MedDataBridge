from datetime import datetime
from typing import Optional

from sqlmodel import Session

from app.models import Patient
from app.services.fhir_encounters import (
    generate_encounter_resource_for_mouvement,
    generate_encounter_resource_for_venue,
    generate_episode_of_care_resource,
)


def generate_practitioner_resource(medecin) -> dict:
    """Génère une ressource FHIR Practitioner à partir d'un MedecinResponsable.

    Args:
        medecin: Instance de MedecinResponsable (RPPS/ADELI + identité XCN).
    Returns:
        dict: Ressource FHIR Practitioner.
    """
    identifiers = []
    if getattr(medecin, "rpps", None):
        identifiers.append({
            "system": "urn:oid:1.2.250.1.71.4.2.1",  # RPPS
            "value": medecin.rpps,
        })
    if getattr(medecin, "adeli", None):
        identifiers.append({
            "system": "urn:oid:1.2.250.1.71.4.2.1.1",  # ADELI (OID conventionnel FR)
            "value": medecin.adeli,
        })

    return {
        "resourceType": "Practitioner",
        "id": f"prac-{medecin.id}",
        "identifier": identifiers,
        "active": getattr(medecin, "active", True),
        "name": [{
            "family": medecin.family_name,
            "given": [g for g in [medecin.given_name, medecin.middle_name] if g],
            "prefix": [medecin.prefix] if getattr(medecin, "prefix", None) else [],
            "suffix": [medecin.suffix] if getattr(medecin, "suffix", None) else [],
        }],
        "telecom": (
            ([{"system": "phone", "value": medecin.phone}] if getattr(medecin, "phone", None) else [])
            + ([{"system": "email", "value": medecin.email}] if getattr(medecin, "email", None) else [])
        ),
    }


def generate_organization_resource(code: str, name: Optional[str] = None) -> dict:
    """Génère une ressource FHIR Organization minimale à partir d'un code d'UF/structure.

    Utilisée pour représenter les références `Organization/{code}` déjà émises par
    `serviceProvider`/`managingOrganization` (auparavant des références non résolues, sans
    ressource correspondante dans le bundle).

    Args:
        code: Code de l'UF/structure (utilisé tel quel comme id de ressource pour rester
            compatible avec les références déjà émises ailleurs dans le bundle).
        name: Libellé lisible, si disponible (à défaut, le code est réutilisé).
    Returns:
        dict: Ressource FHIR Organization.
    """
    return {
        "resourceType": "Organization",
        "id": code,
        "identifier": [{"value": code}],
        "name": name or code,
        "active": True,
    }


def generate_patient_resource(patient: Patient, forced_identifier_system=None, forced_identifier_oid=None) -> dict:
    """Génère une ressource FHIR Patient.
    Args:
        patient: Le patient à convertir
        forced_identifier_system: Override system for all identifiers (optional)
        forced_identifier_oid: Override assigner OID for all identifiers (optional)
    Returns:
        dict: Ressource FHIR Patient
    """
    identifiers = []
    if getattr(patient, "patient_seq", None):
        identifiers.append({
            "system": "http://hospital.local/patient-id",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                    "code": "MR"
                }]
            },
            "value": str(patient.patient_seq)
        })
    # Always include patient ID as identifier
    if patient.id:
        identifiers.append({
            "system": "http://hospital.local/patient-id",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                    "code": "MR"
                }]
            },
            "value": str(patient.id)
        })
    if getattr(patient, "ssn", None):
        identifiers.append({
            "system": "http://hl7.org/fhir/sid/us-ssn",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                    "code": "SS"
                }]
            },
            "value": patient.ssn
        })
    # Apply forced system/assigner if provided
    if forced_identifier_system:
        for iid in identifiers:
            iid["system"] = forced_identifier_system
            if forced_identifier_oid:
                iid["assigner"] = {"identifier": {"value": forced_identifier_oid}}
    return {
        "resourceType": "Patient",
        "id": f"pat-{patient.id}",
        "identifier": identifiers,
        "name": [{
            "family": patient.family,
            "given": [x for x in [patient.given, getattr(patient, "middle", None)] if x],
            "prefix": [patient.prefix] if getattr(patient, "prefix", None) else [],
            "suffix": [patient.suffix] if getattr(patient, "suffix", None) else [],
        }],
        "telecom": (
            ([{"system": "phone", "value": patient.phone}] if getattr(patient, "phone", None) else [])
            + ([{"system": "email", "value": patient.email}] if getattr(patient, "email", None) else [])
        ),
        "address": [{
            "line": [patient.address] if getattr(patient, "address", None) else [],
            "city": getattr(patient, "city", None),
            "state": getattr(patient, "state", None),
            "postalCode": getattr(patient, "postal_code", None),
        }] if getattr(patient, "address", None) or getattr(patient, "city", None) else [],
        "gender": patient.gender,
        "birthDate": str(patient.birth_date) if patient.birth_date else None,
        "maritalStatus": {"text": patient.marital_status} if getattr(patient, "marital_status", None) else None,
    }
def generate_fhir_bundle_for_entity(
    entity,
    entity_type: str,
    session: Optional[Session] = None
) -> dict:
    """Génère un Bundle FHIR pour une entité donnée.
    
    Args:
        entity: L'entité à convertir
        entity_type: Type d'entité ("patient", "dossier", "venue", "mouvement")
        session: Session SQLModel optionnelle
        
    Returns:
        dict: Bundle FHIR contenant les ressources appropriées
    """
    entries = []
    
    if entity_type == "patient":
        # Pass forced_identifier_system/oid if present
        import inspect
        frame = inspect.currentframe().f_back
        forced_identifier_system = frame.f_locals.get("forced_identifier_system", None)
        forced_identifier_oid = frame.f_locals.get("forced_identifier_oid", None)
        patient_res = generate_patient_resource(entity, forced_identifier_system, forced_identifier_oid)
        entries.append({
            "resource": patient_res,
            "fullUrl": f"Patient/{patient_res['id']}"
        })
    
    elif entity_type == "dossier":
        # Dossier = EpisodeOfCare uniquement
        episode_res = generate_episode_of_care_resource(entity, session)
        entries.append({
            "resource": episode_res,
            "fullUrl": f"EpisodeOfCare/{episode_res['id']}"
        })
        
        # Ajouter aussi le patient
        patient_res = generate_patient_resource(entity.patient)
        entries.append({
            "resource": patient_res,
            "fullUrl": f"Patient/{patient_res['id']}"
        })
    
    elif entity_type == "venue":
        # Venue = Encounter
        encounter_res = generate_encounter_resource_for_venue(entity, session)
        entries.append({
            "resource": encounter_res,
            "fullUrl": f"Encounter/{encounter_res['id']}"
        })
        
        # Ajouter EpisodeOfCare et Patient
        dossier = entity.dossier
        episode_res = generate_episode_of_care_resource(dossier, session)
        entries.append({
            "resource": episode_res,
            "fullUrl": f"EpisodeOfCare/{episode_res['id']}"
        })
        
        patient_res = generate_patient_resource(dossier.patient)
        entries.append({
            "resource": patient_res,
            "fullUrl": f"Patient/{patient_res['id']}"
        })
    
    elif entity_type == "mouvement":
        # Mouvement = Encounter nested
        encounter_res = generate_encounter_resource_for_mouvement(entity, session)
        entries.append({
            "resource": encounter_res,
            "fullUrl": f"Encounter/{encounter_res['id']}"
        })
        
        # Ajouter Encounter de la venue
        venue = entity.venue
        venue_encounter_res = generate_encounter_resource_for_venue(venue, session)
        entries.append({
            "resource": venue_encounter_res,
            "fullUrl": f"Encounter/{venue_encounter_res['id']}"
        })
        
        # Ajouter EpisodeOfCare et Patient
        dossier = venue.dossier
        episode_res = generate_episode_of_care_resource(dossier, session)
        entries.append({
            "resource": episode_res,
            "fullUrl": f"EpisodeOfCare/{episode_res['id']}"
        })
        
        patient_res = generate_patient_resource(dossier.patient)
        entries.append({
            "resource": patient_res,
            "fullUrl": f"Patient/{patient_res['id']}"
        })
    
    # Créer le bundle
    bundle = {
        "resourceType": "Bundle",
        "id": f"bundle-{entity_type}-{entity.id}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        "type": "collection",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entry": entries
    }
    
    return bundle
