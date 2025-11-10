"""
Génération de ressources FHIR individuelles par entité.

Architecture FHIR correcte :
- Patient → Patient resource
- Dossier → EpisodeOfCare resource
- Venue → Encounter resource (principal)
- Mouvement → Encounter resource (nested/contained dans venue Encounter)

Mapping HL7 ↔ FHIR :
- ADT^A31 (Patient) → Patient
- ADT^A05 (Venue) → Encounter
- ADT^A01/A04 (Mouvement admission) → Encounter nested
- ADT^A02 (Mouvement transfer) → Encounter nested
- ADT^A03 (Mouvement discharge) → Encounter nested
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Session
from app.models import Patient, Dossier, Venue, Mouvement


def generate_patient_resource(patient: Patient) -> dict:
    """Génère une ressource FHIR Patient.
    
    Args:
        patient: Le patient à convertir
        
    Returns:
        dict: Ressource FHIR Patient
    """
    identifiers = []
    if getattr(patient, "external_id", None):
        identifiers.append({
            "system": "urn:oid:1.2.250.1.71.4.2.1",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                    "code": "PI"
                }]
            },
            "value": patient.external_id
        })
    
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


def generate_episode_of_care_resource(dossier: Dossier, session: Optional[Session] = None) -> dict:
    """Génère une ressource FHIR EpisodeOfCare pour un dossier.
    
    Un dossier représente l'épisode de soins administratif global.
    
    Args:
        dossier: Le dossier à convertir
        session: Session SQLModel optionnelle
        
    Returns:
        dict: Ressource FHIR EpisodeOfCare
    """
    # Détermination du statut
    if dossier.admit_time:
        if dossier.discharge_time:
            status = "finished"
        else:
            status = "active"
    else:
        status = "planned"
    
    # Identifiants
    identifiers = [{
        "system": "urn:oid:1.2.250.1.71.4.2.3",
        "value": str(dossier.dossier_seq)
    }]
    
    # Type mapping
    dossier_type_val = getattr(dossier, "dossier_type", None)
    if hasattr(dossier_type_val, "value"):
        dossier_type_val = dossier_type_val.value
    
    encounter_class_code = getattr(dossier, "encounter_class", None)
    if not encounter_class_code:
        map_by_type = {"hospitalise": "IMP", "externe": "AMB", "urgence": "EMER"}
        encounter_class_code = map_by_type.get(str(dossier_type_val), "IMP")
    
    display_map = {
        "IMP": "inpatient encounter",
        "AMB": "ambulatory",
        "EMER": "emergency",
        "ACUTE": "acute inpatient",
        "NONAC": "non-acute inpatient"
    }
    
    episode_res = {
        "resourceType": "EpisodeOfCare",
        "id": f"eoc-{dossier.id}",
        "status": status,
        "identifier": identifiers,
        "patient": {"reference": f"Patient/pat-{dossier.patient_id}"},
        "period": {
            "start": dossier.admit_time.isoformat() if dossier.admit_time else None,
            "end": dossier.discharge_time.isoformat() if dossier.discharge_time else None,
        },
    }
    
    # Type
    if encounter_class_code:
        episode_res["type"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": encounter_class_code,
                "display": display_map.get(encounter_class_code, encounter_class_code),
            }]
        }]
    
    # Managing organization
    if getattr(dossier, "uf_responsabilite", None):
        episode_res["managingOrganization"] = {
            "reference": f"Organization/{dossier.uf_responsabilite}",
            "display": dossier.uf_responsabilite,
        }
    
    return episode_res


def generate_encounter_resource_for_venue(venue: Venue, session: Optional[Session] = None) -> dict:
    """Génère une ressource FHIR Encounter pour une venue.
    
    Une venue représente un séjour/admission spécifique (pre-admit, admission, etc.)
    
    Args:
        venue: La venue à convertir
        session: Session SQLModel optionnelle
        
    Returns:
        dict: Ressource FHIR Encounter
    """
    # Charger le dossier pour accès patient et encounter_class
    dossier = venue.dossier if hasattr(venue, "dossier") else None
    if not dossier:
        raise ValueError("Venue must have dossier loaded")
    
    # Déterminer encounter_class depuis dossier
    dossier_type_val = getattr(dossier, "dossier_type", None)
    if hasattr(dossier_type_val, "value"):
        dossier_type_val = dossier_type_val.value
    
    encounter_class_code = getattr(dossier, "encounter_class", None)
    if not encounter_class_code:
        map_by_type = {"hospitalise": "IMP", "externe": "AMB", "urgence": "EMER"}
        encounter_class_code = map_by_type.get(str(dossier_type_val), "IMP")
    
    display_map = {
        "IMP": "inpatient encounter",
        "AMB": "ambulatory",
        "EMER": "emergency"
    }
    
    # Status
    if venue.discharge_disposition:
        status = "finished"
    else:
        status = "in-progress"
    
    # Identifiants
    identifiers = [{
        "system": "http://hospital.local/venue-id",
        "value": str(venue.venue_seq)
    }]
    
    encounter_res = {
        "resourceType": "Encounter",
        "id": f"enc-venue-{venue.id}",
        "meta": {
            "profile": ["http://interop-sante.fr/fhir/StructureDefinition/fr-encounter"]
        },
        "identifier": identifiers,
        "status": status,
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": encounter_class_code,
            "display": display_map.get(encounter_class_code, "inpatient encounter")
        },
        "subject": {"reference": f"Patient/pat-{dossier.patient_id}"},
        "episodeOfCare": [{"reference": f"EpisodeOfCare/eoc-{dossier.id}"}],
        "period": {
            "start": venue.start_time.isoformat() if venue.start_time else None,
            "end": None  # Sera défini lors de la sortie
        }
    }
    
    # Service provider (UF)
    if getattr(venue, "uf_responsabilite", None):
        encounter_res["serviceProvider"] = {
            "reference": f"Organization/{venue.uf_responsabilite}",
            "display": venue.uf_responsabilite
        }
    
    # Participant (médecin)
    if getattr(venue, "attending_provider", None):
        encounter_res["participant"] = [{
            "type": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                    "code": "ATND",
                    "display": "attender"
                }]
            }],
            "individual": {
                "display": venue.attending_provider
            }
        }]
    
    # Location
    if getattr(venue, "assigned_location", None):
        encounter_res["location"] = [{
            "location": {"display": venue.assigned_location},
            "status": "active"
        }]
    
    return encounter_res


def generate_encounter_resource_for_mouvement(mouvement: Mouvement, session: Optional[Session] = None) -> dict:
    """Génère une ressource FHIR Encounter pour un mouvement.
    
    Un mouvement représente un événement au sein d'une venue (admission, transfer, discharge).
    Il est représenté comme un Encounter nested/contained dans l'Encounter de la venue.
    
    Args:
        mouvement: Le mouvement à convertir
        session: Session SQLModel optionnelle
        
    Returns:
        dict: Ressource FHIR Encounter (nested)
    """
    # Charger venue et dossier
    venue = mouvement.venue if hasattr(mouvement, "venue") else None
    if not venue:
        raise ValueError("Mouvement must have venue loaded")
    
    dossier = venue.dossier if hasattr(venue, "dossier") else None
    if not dossier:
        raise ValueError("Venue must have dossier loaded")
    
    # Déterminer le type d'événement
    msg_type = mouvement.type if mouvement.type else "ADT^A99"
    event_code = msg_type.split("^")[1] if "^" in msg_type else "A99"
    
    # Mapping événement → status
    status_map = {
        "A01": "arrived",      # Admission
        "A04": "arrived",      # Register
        "A02": "in-progress",  # Transfer
        "A03": "finished",     # Discharge
        "A08": "in-progress",  # Update
        "A11": "cancelled",    # Cancel admission
    }
    status = status_map.get(event_code, "in-progress")
    
    # Identifiants
    identifiers = [{
        "system": "http://hospital.local/mouvement-id",
        "value": str(mouvement.mouvement_seq)
    }]
    
    # Class depuis dossier
    encounter_class_code = getattr(dossier, "encounter_class", "IMP")
    
    encounter_res = {
        "resourceType": "Encounter",
        "id": f"enc-mvt-{mouvement.id}",
        "identifier": identifiers,
        "status": status,
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": encounter_class_code
        },
        "subject": {"reference": f"Patient/pat-{dossier.patient_id}"},
        "episodeOfCare": [{"reference": f"EpisodeOfCare/eoc-{dossier.id}"}],
        "partOf": {"reference": f"Encounter/enc-venue-{venue.id}"},  # Nested dans venue
        "period": {
            "start": mouvement.when.isoformat() if mouvement.when else None,
        }
    }
    
    # Type d'événement
    encounter_res["type"] = [{
        "coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/v2-0003",
            "code": event_code,
            "display": f"ADT {event_code}"
        }]
    }]
    
    # Location si changement
    if event_code == "A02" and getattr(mouvement, "to_location", None):
        encounter_res["location"] = [{
            "location": {"display": mouvement.to_location},
            "status": "active"
        }]
    
    return encounter_res


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
        patient_res = generate_patient_resource(entity)
        entries.append({
            "resource": patient_res,
            "fullUrl": f"urn:uuid:pat-{entity.id}"
        })
    
    elif entity_type == "dossier":
        # Dossier = EpisodeOfCare uniquement
        episode_res = generate_episode_of_care_resource(entity, session)
        entries.append({
            "resource": episode_res,
            "fullUrl": f"urn:uuid:eoc-{entity.id}"
        })
        
        # Ajouter aussi le patient
        patient_res = generate_patient_resource(entity.patient)
        entries.append({
            "resource": patient_res,
            "fullUrl": f"urn:uuid:pat-{entity.patient_id}"
        })
    
    elif entity_type == "venue":
        # Venue = Encounter
        encounter_res = generate_encounter_resource_for_venue(entity, session)
        entries.append({
            "resource": encounter_res,
            "fullUrl": f"urn:uuid:enc-venue-{entity.id}"
        })
        
        # Ajouter EpisodeOfCare et Patient
        dossier = entity.dossier
        episode_res = generate_episode_of_care_resource(dossier, session)
        entries.append({
            "resource": episode_res,
            "fullUrl": f"urn:uuid:eoc-{dossier.id}"
        })
        
        patient_res = generate_patient_resource(dossier.patient)
        entries.append({
            "resource": patient_res,
            "fullUrl": f"urn:uuid:pat-{dossier.patient_id}"
        })
    
    elif entity_type == "mouvement":
        # Mouvement = Encounter nested
        encounter_res = generate_encounter_resource_for_mouvement(entity, session)
        entries.append({
            "resource": encounter_res,
            "fullUrl": f"urn:uuid:enc-mvt-{entity.id}"
        })
        
        # Ajouter Encounter de la venue
        venue = entity.venue
        venue_encounter_res = generate_encounter_resource_for_venue(venue, session)
        entries.append({
            "resource": venue_encounter_res,
            "fullUrl": f"urn:uuid:enc-venue-{venue.id}"
        })
        
        # Ajouter EpisodeOfCare et Patient
        dossier = venue.dossier
        episode_res = generate_episode_of_care_resource(dossier, session)
        entries.append({
            "resource": episode_res,
            "fullUrl": f"urn:uuid:eoc-{dossier.id}"
        })
        
        patient_res = generate_patient_resource(dossier.patient)
        entries.append({
            "resource": patient_res,
            "fullUrl": f"urn:uuid:pat-{dossier.patient_id}"
        })
    
    # Créer le bundle
    bundle = {
        "resourceType": "Bundle",
        "id": f"bundle-{entity_type}-{entity.id}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        "type": "collection",
        "timestamp": datetime.utcnow().isoformat(),
        "entry": entries
    }
    
    return bundle
