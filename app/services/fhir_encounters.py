from datetime import datetime
from typing import Optional
from sqlmodel import Session
from app.models import Dossier, Venue, Mouvement

def generate_episode_of_care_resource(dossier: Dossier, session: Optional[Session] = None) -> dict:
    # ...existing code from fhir_resources.py...
    if dossier.admit_time:
        if dossier.discharge_time:
            status = "finished"
        else:
            status = "active"
    else:
        status = "planned"
    identifiers = [{
        "system": "urn:oid:1.2.250.1.71.4.2.3",
        "value": str(dossier.dossier_seq)
    }]
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
    if encounter_class_code:
        episode_res["type"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": encounter_class_code,
                "display": display_map.get(encounter_class_code, encounter_class_code),
            }]
        }]
    if getattr(dossier, "uf_responsabilite", None):
        episode_res["managingOrganization"] = {
            "reference": f"Organization/{dossier.uf_responsabilite}",
            "display": dossier.uf_responsabilite,
        }
    return episode_res

def generate_encounter_resource_for_venue(venue: Venue, session: Optional[Session] = None) -> dict:
    dossier = venue.dossier if hasattr(venue, "dossier") else None
    if not dossier:
        raise ValueError("Venue must have dossier loaded")
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
    if venue.discharge_disposition:
        status = "finished"
    else:
        status = "in-progress"
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
            "end": None
        }
    }
    if getattr(venue, "uf_responsabilite", None):
        encounter_res["serviceProvider"] = {
            "reference": f"Organization/{venue.uf_responsabilite}",
            "display": venue.uf_responsabilite
        }
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
    if getattr(venue, "assigned_location", None):
        encounter_res["location"] = [{
            "location": {"display": venue.assigned_location},
            "status": "active"
        }]
    return encounter_res

def generate_encounter_resource_for_mouvement(mouvement: Mouvement, session: Optional[Session] = None) -> dict:
    venue = mouvement.venue if hasattr(mouvement, "venue") else None
    if not venue:
        raise ValueError("Mouvement must have venue loaded")
    dossier = venue.dossier if hasattr(venue, "dossier") else None
    if not dossier:
        raise ValueError("Venue must have dossier loaded")
    msg_type = mouvement.type if mouvement.type else "ADT^A99"
    event_code = msg_type.split("^")[1] if "^" in msg_type else "A99"
    status_map = {
        "A01": "arrived",
        "A04": "arrived",
        "A02": "in-progress",
        "A03": "finished",
        "A08": "in-progress",
        "A11": "cancelled",
    }
    status = status_map.get(event_code, "in-progress")
    identifiers = [{
        "system": "http://hospital.local/mouvement-id",
        "value": str(mouvement.mouvement_seq)
    }]
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
        "partOf": {"reference": f"Encounter/enc-venue-{venue.id}"},
        "period": {
            "start": mouvement.when.isoformat() if mouvement.when else None,
        }
    }
    encounter_res["type"] = [{
        "coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/v2-0003",
            "code": event_code,
            "display": f"ADT {event_code}"
        }]
    }]
    if event_code == "A02" and getattr(mouvement, "to_location", None):
        encounter_res["location"] = [{
            "location": {"display": mouvement.to_location},
            "status": "active"
        }]
    return encounter_res
