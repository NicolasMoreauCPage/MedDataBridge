"""
Service d'importation de ressources FHIR.
"""
from typing import Dict, Any, Optional, List
from sqlmodel import Session
from app.models import Patient, Dossier, Venue
import json


class FHIRImportService:
    """Service pour importer des ressources FHIR."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def import_bundle(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Importe un Bundle FHIR."""
        if bundle.get("resourceType") != "Bundle":
            raise ValueError("Resource type must be Bundle")
        
        results = {
            "imported": 0,
            "errors": [],
            "resources": []
        }
        
        entries = bundle.get("entry", [])
        for entry in entries:
            resource = entry.get("resource", {})
            try:
                imported = self.import_resource(resource)
                if imported:
                    results["imported"] += 1
                    results["resources"].append(imported)
            except Exception as e:
                results["errors"].append({
                    "resource": resource.get("resourceType"),
                    "error": str(e)
                })
        
        return results
    
    def import_resource(self, resource: Dict[str, Any]) -> Optional[Any]:
        """Importe une ressource FHIR individuelle."""
        resource_type = resource.get("resourceType")
        
        if resource_type == "Patient":
            return self.import_patient(resource)
        elif resource_type == "Encounter":
            return self.import_encounter(resource)
        else:
            raise ValueError(f"Unsupported resource type: {resource_type}")
    
    def import_patient(self, fhir_patient: Dict[str, Any]) -> Patient:
        """Importe un Patient FHIR."""
        # Extraction des données de base
        name = fhir_patient.get("name", [{}])[0]
        
        patient = Patient(
            nom=name.get("family"),
            prenom=" ".join(name.get("given", [])),
            sexe=fhir_patient.get("gender", "").upper()[:1] if fhir_patient.get("gender") else None,
        )
        
        # Date de naissance
        birth_date = fhir_patient.get("birthDate")
        if birth_date:
            from datetime import datetime
            patient.date_naissance = datetime.fromisoformat(birth_date)
        
        self.session.add(patient)
        self.session.commit()
        self.session.refresh(patient)
        return patient
    
    def import_encounter(self, fhir_encounter: Dict[str, Any]) -> Optional[Venue]:
        """Importe un Encounter FHIR comme Venue."""
        # TODO: Implémenter l'import d'Encounter
        return None
    
    def export_patient_to_fhir(self, patient: Patient) -> Dict[str, Any]:
        """Exporte un Patient vers FHIR."""
        fhir_patient = {
            "resourceType": "Patient",
            "id": str(patient.id),
            "name": [{
                "family": patient.nom,
                "given": [patient.prenom] if patient.prenom else []
            }],
            "gender": patient.sexe.lower() if patient.sexe else "unknown",
        }
        
        if patient.date_naissance:
            fhir_patient["birthDate"] = patient.date_naissance.date().isoformat()
        
        if patient.ipp:
            fhir_patient["identifier"] = [{
                "system": "urn:oid:1.2.250.1.213",
                "value": patient.ipp
            }]
        
        return fhir_patient
