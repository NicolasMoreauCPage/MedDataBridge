"""
Classes pour l'export de données vers FHIR.
"""
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel

class FHIRIdentifier(BaseModel):
    """Identifiant FHIR."""
    use: str = "official"
    system: str
    value: str

class FHIRReference(BaseModel):
    """Référence vers une ressource FHIR."""
    reference: str
    display: Optional[str] = None

class FHIRCodeableConcept(BaseModel):
    """Concept codable FHIR."""
    coding: List[Dict[str, str]]
    text: Optional[str] = None

class FHIRPeriod(BaseModel):
    """Période FHIR."""
    start: Optional[str] = None
    end: Optional[str] = None

class FHIRLocation(BaseModel):
    """Ressource Location FHIR."""
    resourceType: str = "Location"
    id: Optional[str] = None
    identifier: List[FHIRIdentifier]
    status: str = "active"
    name: str
    description: Optional[str] = None
    type: Optional[List[FHIRCodeableConcept]] = None
    physicalType: Optional[FHIRCodeableConcept] = None
    partOf: Optional[FHIRReference] = None

class FHIRPatient(BaseModel):
    """Ressource Patient FHIR."""
    resourceType: str = "Patient"
    id: Optional[str] = None
    identifier: List[FHIRIdentifier]
    active: bool = True
    name: List[Dict[str, Any]]
    managingOrganization: Optional[FHIRReference] = None

class FHIREncounter(BaseModel):
    """Ressource Encounter FHIR."""
    resourceType: str = "Encounter"
    id: Optional[str] = None
    identifier: List[FHIRIdentifier]
    status: str
    class_: Dict[str, str]
    subject: FHIRReference
    period: Optional[FHIRPeriod] = None
    location: Optional[List[Dict[str, Any]]] = None

class FHIRBundle(BaseModel):
    """Bundle FHIR."""
    resourceType: str = "Bundle"
    type: str = "transaction"
    entry: List[Dict[str, Any]]

class HL7ToFHIRConverter:
    """Convertisseur de données HL7 vers FHIR."""

    @staticmethod
    def create_identifier(system: str, value: str, use: str = "official") -> FHIRIdentifier:
        """Crée un identifiant FHIR."""
        return FHIRIdentifier(
            system=system,
            value=value,
            use=use
        )

    @staticmethod
    def create_reference(resource_type: str, resource_id: str, display: Optional[str] = None) -> FHIRReference:
        """Crée une référence FHIR."""
        return FHIRReference(
            reference=f"{resource_type}/{resource_id}",
            display=display
        )

    @staticmethod
    def create_codeable_concept(code: str, system: str, display: str) -> FHIRCodeableConcept:
        """Crée un concept codable FHIR."""
        return FHIRCodeableConcept(
            coding=[{
                "system": system,
                "code": code,
                "display": display
            }]
        )

    @staticmethod
    def create_period(start: Optional[datetime] = None, end: Optional[datetime] = None) -> FHIRPeriod:
        """Crée une période FHIR."""
        return FHIRPeriod(
            start=start.isoformat() if start else None,
            end=end.isoformat() if end else None
        )

    @staticmethod
    def create_bundle_entry(resource: Union[FHIRLocation, FHIRPatient, FHIREncounter],
                          method: str = "POST") -> Dict[str, Any]:
        """Crée une entrée de bundle FHIR."""
        return {
            "resource": resource.dict(exclude_none=True, by_alias=True),
            "request": {
                "method": method,
                "url": f"{resource.resourceType}"
            }
        }

class StructureToFHIRConverter:
    """Convertisseur de structure vers FHIR."""
    
    PHYSICAL_TYPES = {
        "SI": ("si", "Site"),
        "BU": ("bu", "Building"),
        "FL": ("fl", "Floor"),
        "WI": ("wi", "Wing"),
        "WA": ("wa", "Ward"),
        "RO": ("ro", "Room"),
        "BD": ("bd", "Bed")
    }
    
    LOCATION_TYPES = {
        "ETBL_GRPQ": ("ETBL", "Établissement Géographique"),
        "PL": ("POLE", "Pôle"),
        "D": ("SERV", "Service"),
        "UF": ("UF", "Unité Fonctionnelle"),
        "UH": ("UH", "Unité d'Hébergement"),
        "CH": ("ROOM", "Chambre"),
        "LIT": ("BED", "Lit")
    }
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.converter = HL7ToFHIRConverter()

    def create_location(self, 
                       identifier: str,
                       name: str,
                       location_type: str,
                       physical_type: str,
                       parent_ref: Optional[FHIRReference] = None) -> FHIRLocation:
        """Crée une ressource Location FHIR."""
        
        # Identifiant
        identifiers = [
            self.converter.create_identifier(
                f"{self.base_url}/location/identifier",
                identifier
            )
        ]
        
        # Type de localisation
        type_code, type_display = self.LOCATION_TYPES.get(location_type, ("UNK", "Inconnu"))
        location_type = self.converter.create_codeable_concept(
            type_code,
            f"{self.base_url}/location/type",
            type_display
        )
        
        # Type physique - handle both lowercase and uppercase physical types
        phys_code, phys_display = self.PHYSICAL_TYPES.get(
            physical_type.upper(), 
            self.PHYSICAL_TYPES.get(physical_type, ("bu", "Building"))
        )
        physical_type = self.converter.create_codeable_concept(
            phys_code,
            "http://terminology.hl7.org/CodeSystem/location-physical-type",
            phys_display
        )
        
        return FHIRLocation(
            identifier=identifiers,
            name=name,
            type=[location_type],
            physicalType=physical_type,
            partOf=parent_ref
        )

class PatientToFHIRConverter:
    """Convertisseur de patient vers FHIR."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.converter = HL7ToFHIRConverter()
    
    def create_patient(self,
                      identifier: str,
                      name: str,
                      surname: str,
                      organization_ref: Optional[FHIRReference] = None) -> FHIRPatient:
        """Crée une ressource Patient FHIR."""
        
        # Identifiant
        identifiers = [
            self.converter.create_identifier(
                f"{self.base_url}/patient/identifier",
                identifier
            )
        ]
        
        # Nom
        names = [{
            "family": surname,
            "given": [name],
            "use": "official"
        }]
        
        return FHIRPatient(
            identifier=identifiers,
            name=names,
            managingOrganization=organization_ref
        )

class EncounterToFHIRConverter:
    """Convertisseur de venue vers FHIR."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.converter = HL7ToFHIRConverter()
    
    def create_encounter(self,
                        identifier: str,
                        patient_ref: FHIRReference,
                        status: str,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None,
                        location_ref: Optional[FHIRReference] = None) -> FHIREncounter:
        """Crée une ressource Encounter FHIR."""
        
        # Identifiant
        identifiers = [
            self.converter.create_identifier(
                f"{self.base_url}/encounter/identifier",
                identifier
            )
        ]
        
        # Période
        period = self.converter.create_period(start_date, end_date)
        
        # Localisation
        locations = []
        if location_ref:
            locations.append({
                "location": location_ref.dict(),
                "status": "active"
            })
        
        return FHIREncounter(
            identifier=identifiers,
            status=status,
            class_={
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "IMP",
                "display": "inpatient encounter"
            },
            subject=patient_ref,
            period=period,
            location=locations
        )