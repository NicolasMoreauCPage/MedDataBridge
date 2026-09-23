"""Génération d'un Bundle FHIR (Patient + Encounter + EpisodeOfCare) pour un dossier.

Extension: ajout de la ressource EpisodeOfCare pour représenter l'épisode
administratif global (pré-admission → admission → sortie). Cette ressource
est requise par la demande récente afin de compléter la représentation
longitudinale administrative du dossier côté FHIR.

Ressources incluses:
    - Patient
    - Encounter (rencontre courante liée au dossier)
    - EpisodeOfCare (nouvel ajout)

Notes d'implémentation:
    - Status EpisodeOfCare:
             * planned  : si aucune date d'admission (rare) ou si future
             * active   : si admit_time définie et pas de discharge_time
             * finished : si discharge_time définie
    - Identifiers: dossier_seq utilisé comme identifiant principal EpisodeOfCare
    - managingOrganization: utilisation de l'UF de responsabilité si disponible
    - Type / Class minimal: mapping simple sur dossier_type (IMP/AMB/EMER) en mirroir d'Encounter.class
    - Cohérence Patient.email: ajout telecom email si présent (alignement avec génération HL7 PID-13 / autre branche FHIR)
"""

from app.models import Dossier

from datetime import datetime
from typing import Optional
from sqlmodel import Session
from app.services.fhir_resources import generate_practitioner_resource, generate_organization_resource

def generate_fhir_bundle_for_dossier(dossier: Dossier, session: Optional[Session] = None) -> dict:
    """Génère un Bundle FHIR contenant Patient + Encounter + EpisodeOfCare (+ locations).

    Args:
        dossier: Le dossier à convertir.
        session: Session SQLModel optionnelle pour chargement lazy.

    Returns:
        dict: Bundle FHIR au format "collection".
    """
    p = dossier.patient
    
    # Identifiants avec systèmes standardisés
    identifiers = []
    if getattr(p, "ssn", None):
        identifiers.append({
            "system": "http://hl7.org/fhir/sid/us-ssn",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203", 
                    "code": "SS"
                }]
            },
            "value": p.ssn
        })

    patient_res = {
        "resourceType": "Patient",
        "id": f"pat-{p.id}",
        "identifier": identifiers,
        "name": [{
            "family": p.family,
            "given": [x for x in [p.given, getattr(p, "middle", None)] if x],
            "prefix": [p.prefix] if getattr(p, "prefix", None) else [],
            "suffix": [p.suffix] if getattr(p, "suffix", None) else [],
        }],
        "telecom": (
            ([{"system": "phone", "value": p.phone}] if getattr(p, "phone", None) else [])
            + ([{"system": "email", "value": p.email}] if getattr(p, "email", None) else [])
        ),
        "address": [{
            "line": [p.address] if getattr(p, "address", None) else [],
            "city": getattr(p, "city", None),
            "state": getattr(p, "state", None),
            "postalCode": getattr(p, "postal_code", None),
        }] if getattr(p, "address", None) or getattr(p, "city", None) else [],
        "gender": p.gender,
        "birthDate": p.birth_date,
        "maritalStatus": {"text": p.marital_status} if getattr(p, "marital_status", None) else None,
    }

    # Extensions FRCore 2.2.0 pour conformité FHIR France
    # Réf: https://hl7.fr/ig/fhir/core/2.2.0/ (StructureDefinition/CodeSystem/ValueSet ci-dessous
    # vérifiés contre le FSH source publié, pas contre l'ancien domaine interopsante.org/interop-sante.fr
    # qui a été abandonné dès la version 2.0.1 du guide)
    extensions = []

    # Extension fr-core-identity-reliability (sous-extensions composites)
    if getattr(p, "identity_reliability_code", None):
        identity_sub_extensions = [{
            "url": "identityStatus",
            "valueCoding": {
                "system": "https://hl7.fr/ig/fhir/core/ValueSet/fr-core-vs-identity-reliability-status",
                "code": p.identity_reliability_code
            }
        }]
        if getattr(p, "identity_reliability_date", None):
            identity_sub_extensions.append({
                "url": "validationDate",
                "valueDate": p.identity_reliability_date.isoformat() if hasattr(p.identity_reliability_date, "isoformat") else p.identity_reliability_date
            })
        if getattr(p, "identity_reliability_source", None):
            identity_sub_extensions.append({
                "url": "validationMode",
                "valueCoding": {
                    "system": "https://hl7.fr/ig/fhir/core/ValueSet/fr-core-vs-mode-validation-identity",
                    "code": p.identity_reliability_source
                }
            })
        extensions.append({
            "url": "https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-identity-reliability",
            "extension": identity_sub_extensions
        })

    # Lieu de naissance : extension standard HL7 patient-birthPlace (Address), pas une extension
    # FRCore custom — seul le code INSEE de la commune de naissance est porté par une extension
    # FRCore imbriquée sur l'Address (fr-core-address-insee-code).
    if getattr(p, "birth_city", None) or getattr(p, "birth_country", None) or getattr(p, "birth_insee_code", None):
        birth_place_address = {}
        if getattr(p, "birth_city", None):
            birth_place_address["city"] = p.birth_city
        if getattr(p, "birth_state", None):
            birth_place_address["state"] = p.birth_state
        if getattr(p, "birth_postal_code", None):
            birth_place_address["postalCode"] = p.birth_postal_code
        if getattr(p, "birth_country", None):
            birth_place_address["country"] = p.birth_country
        if getattr(p, "birth_insee_code", None):
            birth_place_address["extension"] = [{
                "url": "https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-address-insee-code",
                "valueCoding": {
                    "system": "https://hl7.fr/ig/fhir/core/CodeSystem/fr-core-cs-v2-0399",
                    "code": p.birth_insee_code
                }
            }]

        extensions.append({
            "url": "http://hl7.org/fhir/StructureDefinition/patient-birthPlace",
            "valueAddress": birth_place_address
        })
    if getattr(p, "primary_care_provider", None):
        extensions.append({
            "url": "http://example.org/fhir/StructureDefinition/primary-care-provider",
            "valueString": p.primary_care_provider
        })

    if extensions:
        patient_res["extension"] = extensions

    # Use encounter_class if present, else derive from dossier_type
    encounter_class_code = getattr(dossier, "encounter_class", None)
    if not encounter_class_code:
        dossier_type_val = getattr(dossier, "dossier_type", None)
        if hasattr(dossier_type_val, "value"):
            dossier_type_val = dossier_type_val.value
        map_by_type = {"hospitalise": "IMP", "externe": "AMB", "urgence": "EMER"}
        encounter_class_code = map_by_type.get(str(dossier_type_val), "IMP")
    # Provide display labels per FHIR ActCode
    display_map = {"IMP": "inpatient encounter", "AMB": "ambulatory", "EMER": "emergency", "ACUTE": "acute inpatient", "NONAC": "non-acute inpatient"}
    class_info = {"code": encounter_class_code, "display": display_map.get(encounter_class_code, "inpatient encounter")}
    
    # Encounter avec tous les champs mappés
    encounter_res = {
        "resourceType": "Encounter",
        "id": f"enc-{dossier.id}",
        "meta": {
            "profile": ["http://interop-sante.fr/fhir/StructureDefinition/fr-encounter"]
        },
        "identifier": [{
            "system": "urn:oid:1.2.250.1.71.4.2.2",
            "value": str(dossier.id)
        }],
        "status": "finished" if dossier.discharge_time else "in-progress",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": class_info["code"],
            "display": class_info["display"]
        },
        "subject": {"reference": f"Patient/pat-{p.id}"},
        "period": {
            "start": dossier.admit_time.isoformat() if dossier.admit_time else None,
            "end": dossier.discharge_time.isoformat() if dossier.discharge_time else None
        }
    }
    
    # Type de rencontre (encounter_type)
    if getattr(dossier, "encounter_type", None):
        encounter_res["type"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/encounter-type",
                "code": dossier.encounter_type,
                "display": dossier.encounter_type
            }]
        }]
    
    # UF responsabilité comme serviceProvider (ressource Organization ajoutée au bundle plus bas)
    organization_res = None
    if getattr(dossier, "uf_responsabilite", None):
        organization_res = generate_organization_resource(dossier.uf_responsabilite)
        encounter_res["serviceProvider"] = {
            "reference": f"Organization/{organization_res['id']}",
            "display": dossier.uf_responsabilite
        }
    
    # Hospitalisation (admission_type, admission_source, discharge_disposition)
    hospitalization = {}
    if getattr(dossier, "admission_source", None):
        hospitalization["admitSource"] = {
            "text": dossier.admission_source
        }
    if getattr(dossier, "admission_type", None):
        # Mapping HL7 Table 0007 → FHIR
        hospitalization["admitSource"] = hospitalization.get("admitSource", {})
        hospitalization["admitSource"]["coding"] = [{
            "system": "http://terminology.hl7.org/CodeSystem/admit-source",
            "code": dossier.admission_type,
            "display": dossier.admission_type
        }]
    if getattr(dossier, "discharge_disposition", None):
        hospitalization["dischargeDisposition"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/discharge-disposition",
                "code": dossier.discharge_disposition
            }]
        }
    if hospitalization:
        encounter_res["hospitalization"] = hospitalization
    
    # Participant (médecin responsable) : ressource Practitioner à part entière si le dossier
    # est lié à un MedecinResponsable réel (RPPS/ADELI), sinon simple display de secours.
    practitioner_res = None
    medecin = getattr(dossier, "medecin_responsable", None)
    if medecin is not None:
        practitioner_res = generate_practitioner_resource(medecin)
        individual = {
            "reference": f"Practitioner/{practitioner_res['id']}",
            "display": medecin.get_full_name() if hasattr(medecin, "get_full_name") else None,
        }
    elif getattr(dossier, "attending_provider", None):
        individual = {"display": dossier.attending_provider}
    else:
        individual = None

    if individual:
        encounter_res["participant"] = [{
            "type": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                    "code": "ATND",
                    "display": "attender"
                }]
            }],
            "individual": individual
        }]
    
    # Diagnostic principal
    if getattr(dossier, "primary_diagnosis", None):
        encounter_res["diagnosis"] = [{
            "condition": {
                "display": dossier.primary_diagnosis
            },
            "use": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/diagnosis-role",
                    "code": "AD",
                    "display": "Admission diagnosis"
                }]
            },
            "rank": 1
        }]

    # Ajouter les mouvements comme locations
    if hasattr(dossier, "venues") and dossier.venues:
        encounter_res["location"] = []
        for venue in dossier.venues:
            if venue.mouvements:
                for mvt in venue.mouvements:
                    encounter_res["location"].append({
                        "location": {"reference": f"Location/{mvt.location}" if mvt.location else None},
                        "status": "completed" if mvt.when and mvt.when < datetime.utcnow() else "active",
                        "period": {
                            "start": mvt.when.isoformat() if mvt.when else None
                        }
                    })

    # EpisodeOfCare (administrative episode spanning the dossier lifecycle)
    # Détermination du statut EpisodeOfCare
    if dossier.admit_time:
        if dossier.discharge_time:
            episode_status = "finished"
        else:
            episode_status = "active"
    else:
        episode_status = "planned"

    episode_identifiers = [{
        "system": "urn:oid:1.2.250.1.71.4.2.3",  # OID fictif interne EpisodeOfCare
        "value": str(dossier.dossier_seq)
    }]

    episode_res = {
        "resourceType": "EpisodeOfCare",
        "id": f"eoc-{dossier.id}",
        "status": episode_status,
        "identifier": episode_identifiers,
        "patient": {"reference": f"Patient/pat-{p.id}"},
        "period": {
            "start": dossier.admit_time.isoformat() if dossier.admit_time else None,
            "end": dossier.discharge_time.isoformat() if dossier.discharge_time else None,
        },
    }

    # Type mapping minimal (réutilise dossier_type → class_mapping codes) placé en extension simple
    if dossier_type_val:
        episode_res["type"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/episodeofcare-type",
                "code": class_info["code"],
                "display": class_info["display"],
            }]
        }]

    # managingOrganization depuis UF responsabilité si disponible (même Organization que serviceProvider)
    if organization_res is not None:
        episode_res["managingOrganization"] = {
            "reference": f"Organization/{organization_res['id']}",
            "display": dossier.uf_responsabilite,
        }

    # Bundle avec identifiant unique
    # Use stable fullUrl values (ResourceType/id) to ensure uniqueness and
    # better interoperability (avoids duplicate urn:uuid collisions).
    entries = [
        {"resource": patient_res, "fullUrl": f"Patient/{patient_res['id']}"},
        {"resource": encounter_res, "fullUrl": f"Encounter/{encounter_res['id']}"},
        {"resource": episode_res, "fullUrl": f"EpisodeOfCare/{episode_res['id']}"},
    ]
    if practitioner_res is not None:
        entries.append({"resource": practitioner_res, "fullUrl": f"Practitioner/{practitioner_res['id']}"})
    if organization_res is not None:
        entries.append({"resource": organization_res, "fullUrl": f"Organization/{organization_res['id']}"})

    bundle = {
        "resourceType": "Bundle",
        "id": f"bundle-{dossier.id}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        "type": "collection",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entry": entries
    }

    return bundle
