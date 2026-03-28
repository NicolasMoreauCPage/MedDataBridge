"""
Service d'importation de ressources FHIR.
"""
from typing import Dict, Any, Optional, List
from sqlmodel import Session, select
from app.models import Patient, Dossier, Venue, Mouvement
from datetime import datetime
import json


class FHIRImportService:
    """Service pour importer des ressources FHIR."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def _normalize_bundle(self, bundle: Any) -> Dict[str, Any]:
        """Normalize dict/Pydantic-like bundle objects to a plain dict."""
        if isinstance(bundle, dict):
            return bundle
        if hasattr(bundle, "model_dump"):
            return bundle.model_dump()
        if hasattr(bundle, "dict"):
            return bundle.dict()
        raise ValueError("Unsupported bundle payload")

    def _validate_bundle(self, bundle: Dict[str, Any]) -> bool:
        """Basic Bundle validation hook (kept for test compatibility)."""
        return bundle.get("resourceType") == "Bundle"

    async def _process_patient(self, resource: Dict[str, Any]) -> Optional[int]:
        """Process a FHIR Patient resource and return internal id."""
        patient = self.import_patient(resource)
        return patient.id if patient else None

    async def _process_encounter(self, resource: Dict[str, Any]) -> Optional[int]:
        """Process a FHIR Encounter resource and return internal id if created."""
        venue = self.import_encounter(resource)
        return venue.id if venue else None

    async def import_bundle(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Importe un Bundle FHIR."""
        bundle = self._normalize_bundle(bundle)
        if not self._validate_bundle(bundle):
            raise ValueError("Resource type must be Bundle")
        
        results = {
            "imported": 0,
            "errors": [],
            "resources": []
        }
        
        entries = bundle.get("entry", [])
        for entry in entries:
            if isinstance(entry, dict):
                resource = entry.get("resource", {})
            else:
                resource = getattr(entry, "resource", {})
                if hasattr(resource, "model_dump"):
                    resource = resource.model_dump()
                elif hasattr(resource, "dict"):
                    resource = resource.dict()
            try:
                resource_type = resource.get("resourceType")
                if resource_type == "Patient":
                    imported = await self._process_patient(resource)
                elif resource_type == "Encounter":
                    imported = await self._process_encounter(resource)
                else:
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
        """Importe un Encounter FHIR comme Venue (admission/mouvement)."""
        try:
            # Extract patient reference
            subject = fhir_encounter.get("subject", {})
            patient_ref = subject.get("reference", "")
            
            if not patient_ref:
                raise ValueError("Encounter must have a patient reference (subject)")
            
            # Parse patient ID from reference (e.g., "Patient/123" → 123)
            patient_id = int(patient_ref.split("/")[-1])
            
            # Find patient and associated dossier
            patient = self.session.exec(select(Patient).where(Patient.id == patient_id)).first()
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            # Get the main dossier (assuming one dossier per patient for FHIR import)
            dossier = self.session.exec(
                select(Dossier).where(Dossier.patient_id == patient_id)
            ).first()
            if not dossier:
                # Create a default dossier if none exists
                dossier = Dossier(patient_id=patient_id, admitting_organization="DEFAULT")
                self.session.add(dossier)
                self.session.flush()
            
            # Extract encounter details
            period = fhir_encounter.get("period", {})
            start_time_str = period.get("start")
            end_time_str = period.get("end")
            
            if not start_time_str:
                raise ValueError("Encounter period.start is required")
            
            # Parse datetime
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            end_time = None
            if end_time_str:
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            
            # Extract location and class information
            status = fhir_encounter.get("status", "in-progress")
            encounter_class = fhir_encounter.get("class", {})
            class_code = encounter_class.get("code", "AMB")  # Default to ambulatory
            
            location_refs = fhir_encounter.get("location", [])
            location_code = None
            if location_refs and len(location_refs) > 0:
                location_ref = location_refs[0].get("location", {})
                location_code = location_ref.get("reference", "").split("/")[-1]
            
            # Get next venue sequence
            last_venue = self.session.exec(
                select(Venue).order_by(Venue.venue_seq.desc())
            ).first()
            next_seq = (last_venue.venue_seq if last_venue else 0) + 1
            
            # Create Venue (admission)
            venue = Venue(
                venue_seq=next_seq,
                dossier_id=dossier.id,
                code=location_code,
                label=f"Venue from Encounter {fhir_encounter.get('id', 'unknown')}",
                assigned_location=location_code,
                uf_responsabilite=encounter_class.get("display", "").split("-")[0] if encounter_class.get("display") else None,
                nature=self._map_encounter_class_to_nature(class_code),
                start_time=start_time,
                hospital_service=encounter_class.get("display"),
                attending_provider=None  # Would need to extract from participant[type=ATND]
            )
            
            self.session.add(venue)
            self.session.flush()
            
            # Create associated Mouvement (movement/status change)
            last_mouvement = self.session.exec(
                select(Mouvement).order_by(Mouvement.mouvement_seq.desc())
            ).first()
            next_mov_seq = (last_mouvement.mouvement_seq if last_mouvement else 0) + 1
            
            mouvement = Mouvement(
                mouvement_seq=next_mov_seq,
                venue_id=venue.id,
                type=f"ADT^A01",  # Default ADT admission
                when=start_time,
                end_time=end_time,
                status=status,
                location=location_code,
                trigger_event="A01",  # Admission
                action="INSERT",
                nature=self._map_encounter_class_to_nature(class_code),
                uf_responsabilite=venue.uf_responsabilite
            )
            
            self.session.add(mouvement)
            self.session.commit()
            self.session.refresh(venue)
            
            return venue
            
        except Exception as e:
            self.session.rollback()
            raise ValueError(f"Failed to import Encounter: {str(e)}")
    
    def _map_encounter_class_to_nature(self, class_code: str) -> str:
        """Map FHIR Encounter class to IHE PAM nature code."""
        mapping = {
            "AMB": "S",      # Ambulatory → Soins
            "IMP": "H",      # Inpatient → Hospitalisation
            "EMER": "U",     # Emergency
            "VR": "M",       # Virtual → Mouvement
        }
        return mapping.get(class_code, "S")
    
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
