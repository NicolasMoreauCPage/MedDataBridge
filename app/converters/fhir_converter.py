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
    meta: Optional[Dict[str, Any]] = None
    identifier: List[FHIRIdentifier]
    status: str = "active"
    name: str
    description: Optional[str] = None
    type: Optional[List[FHIRCodeableConcept]] = None
    physicalType: Optional[FHIRCodeableConcept] = None
    partOf: Optional[FHIRReference] = None
    extension: Optional[List[Dict[str, Any]]] = None

class FHIROrganization(BaseModel):
    """Ressource Organization FHIR."""
    resourceType: str = "Organization"
    id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    identifier: Optional[List[Dict[str, Any]]] = None
    active: bool = True
    type: Optional[List[Dict[str, Any]]] = None
    name: Optional[str] = None
    alias: Optional[List[str]] = None
    partOf: Optional[FHIRReference] = None
    extension: Optional[List[Dict[str, Any]]] = None

class FHIRPatient(BaseModel):
    """Ressource Patient FHIR."""
    resourceType: str = "Patient"
    id: Optional[str] = None
    identifier: List[FHIRIdentifier]
    active: bool = True
    name: List[Dict[str, Any]]
    managingOrganization: Optional[FHIRReference] = None
    contact: Optional[List[Dict[str, Any]]] = None  # Patient.contact[]

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
    participant: Optional[List[Dict[str, Any]]] = None  # Encounter.participant[]
    serviceProvider: Optional[FHIRReference] = None

class FHIRRelatedPerson(BaseModel):
    """Ressource RelatedPerson FHIR pour VenueContact."""
    resourceType: str = "RelatedPerson"
    id: Optional[str] = None
    patient: FHIRReference
    relationship: Optional[List[FHIRCodeableConcept]] = None
    name: Optional[List[Dict[str, Any]]] = None
    telecom: Optional[List[Dict[str, Any]]] = None
    gender: Optional[str] = None
    birthDate: Optional[str] = None
    address: Optional[Dict[str, Any]] = None
    period: Optional[FHIRPeriod] = None

class FHIRBundleEntry(BaseModel):
    """Entrée de bundle FHIR."""
    resource: Union[FHIRLocation, FHIROrganization, FHIRPatient, FHIREncounter, Dict[str, Any]]
    request: Optional[Dict[str, str]] = None

class FHIRBundle(BaseModel):
    """Bundle FHIR."""
    resourceType: str = "Bundle"
    type: str = "transaction"
    entry: List[FHIRBundleEntry]
    total: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None

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
    def create_bundle_entry(resource: Union[FHIRLocation, FHIROrganization, FHIRPatient, FHIREncounter],
                          method: str = "POST") -> FHIRBundleEntry:
        """Crée une entrée de bundle FHIR."""
        return FHIRBundleEntry(
            resource=resource,
            request={
                "method": method,
                "url": f"{resource.resourceType}"
            }
        )


# ---------------------------------------------------------------------------
# Convertisseur de structure hospitalière vers FHIR, conforme au guide FRCore
# v2.2.0 (https://hl7.fr/ig/fhir/core/2.2.0/) — vérifié contre le FSH source
# publié (github.com/Interop-Sante/hl7.fhir.fr.core, tag 2.2.0), pas contre les
# anciens domaines interop-sante.fr/interopsante.org abandonnés depuis la 2.0.1.
#
# Depuis la 2.2.0, FRCore n'a plus de profil dédié "Pôle" (FRCoreOrganizationPoleProfile
# a été supprimé) : seuls Etablissement (EJ/EG) et UF ont un profil Organization
# spécifique. Pôle et Service sont donc exportés comme Organization générique
# (FRCoreOrganizationProfile de base). UH/Chambre/Lit restent des Location (lieux
# physiques), la bascule Organization → Location se faisant au niveau UH.
# ---------------------------------------------------------------------------

FRCORE_BASE = "https://hl7.fr/ig/fhir/core"
FRCORE_VERSION = "2.2.0"

FRCORE_PROFILES = {
    "organization": f"{FRCORE_BASE}/StructureDefinition/fr-core-organization",
    "organization_etablissement": f"{FRCORE_BASE}/StructureDefinition/fr-core-organization-etablissement",
    "organization_uf": f"{FRCORE_BASE}/StructureDefinition/fr-core-organization-uf",
    "organization_uac": f"{FRCORE_BASE}/StructureDefinition/fr-core-organization-uac",
    "location": f"{FRCORE_BASE}/StructureDefinition/fr-core-location",
}

FRCORE_CS_V2_0203 = f"{FRCORE_BASE}/CodeSystem/fr-core-cs-v2-0203"
FRCORE_CS_V2_3307 = f"{FRCORE_BASE}/CodeSystem/fr-core-cs-v2-3307"


def frcore_profile(profile_name: str) -> str:
    """Retourne le canonical FR Core versionné pour ``meta.profile``.

    La version explicite rend le contrat interopérable sans ambiguïté avec le
    guide publié. Les imports acceptent néanmoins aussi l'URI non versionné,
    conformément au format canonical FHIR.
    """
    return f"{FRCORE_PROFILES[profile_name]}|{FRCORE_VERSION}"


class StructureToFHIRConverter:
    """Convertisseur de la hiérarchie structurelle (EJ/EG/Pôle/Service/UF/UAC/UH/
    Chambre/Lit) vers des ressources FHIR Organization/Location conformes FRCore 2.2.0.
    """

    def __init__(self, base_url: str = "http://localhost/fhir"):
        self.base_url = base_url
        self.converter = HL7ToFHIRConverter()

    # ------------------------------------------------------------------
    # Organization : Etablissement (EJ/EG)
    # ------------------------------------------------------------------
    def create_organization_etablissement(
        self,
        identifier: str,
        name: str,
        entity_type: str,
        finess: Optional[str] = None,
        finess_type_code: str = "FINEG",
        siren: Optional[str] = None,
        siret: Optional[str] = None,
        rpps_rang: Optional[str] = None,
        active: bool = True,
        parent_ref: Optional[FHIRReference] = None,
    ) -> FHIROrganization:
        """Crée une Organization FRCoreOrganizationEtablissementProfile pour une
        EntiteJuridique (finess_type_code="FINEJ") ou une EntiteGeographique
        (finess_type_code="FINEG").
        """
        identifiers = []
        if finess:
            identifiers.append({
                "use": "official",
                "type": {"coding": [{"system": FRCORE_CS_V2_0203, "code": finess_type_code}]},
                "system": "https://finess.esante.gouv.fr",
                "value": finess,
            })
        if siren:
            identifiers.append({
                "type": {"coding": [{"system": FRCORE_CS_V2_0203, "code": "SIREN"}]},
                "system": "https://sirene.fr",
                "value": siren,
            })
        if siret:
            identifiers.append({
                "type": {"coding": [{"system": FRCORE_CS_V2_0203, "code": "SIRET"}]},
                "system": "https://sirene.fr",
                "value": siret,
            })
        if rpps_rang:
            identifiers.append({
                "type": {"coding": [{"system": FRCORE_CS_V2_0203, "code": "RPPSRG"}]},
                "system": "https://rppsrang.esante.gouv.fr",
                "value": rpps_rang,
            })
        if not identifiers and identifier:
            # Solution de repli si aucun identifiant national n'est renseigné :
            # au moins un identifier ou un name est requis par le profil (org-1).
            identifiers.append({"value": identifier})

        entity_type_codes = {
            # EJ/EG sont les libellés historiques internes ; le guide FR Core
            # 2.2.0 impose les codes de la table v2-3307 ci-dessous.
            "EJ": "LEGAL-ENTITY",
            "LEGAL-ENTITY": "LEGAL-ENTITY",
            "EG": "GEOGRAPHICAL-ENTITY",
            "GEOGRAPHICAL-ENTITY": "GEOGRAPHICAL-ENTITY",
        }
        try:
            frcore_entity_type = entity_type_codes[entity_type]
        except KeyError as exc:
            raise ValueError(f"Type d'établissement FR Core invalide : {entity_type}") from exc

        return FHIROrganization(
            id=identifier,
            meta={"profile": [frcore_profile("organization_etablissement")]},
            identifier=identifiers,
            active=active,
            type=[{"coding": [{"system": FRCORE_CS_V2_3307, "code": frcore_entity_type}]}],
            name=name,
            partOf=parent_ref,
        )

    # ------------------------------------------------------------------
    # Organization générique (Pôle / Service — pas de profil FRCore dédié en 2.2.0)
    # ------------------------------------------------------------------
    def create_organization_generic(
        self,
        identifier: str,
        name: str,
        active: bool = True,
        type_code: Optional[str] = None,
        type_display: Optional[str] = None,
        parent_ref: Optional[FHIRReference] = None,
    ) -> FHIROrganization:
        """Crée une Organization FRCoreOrganizationProfile de base, pour les niveaux
        Pôle et Service qui n'ont plus de profil dédié depuis FRCore 2.2.0."""
        type_field = None
        if type_code:
            coding = {"system": FRCORE_CS_V2_3307, "code": type_code}
            if type_display:
                coding["display"] = type_display
            type_field = [{"coding": [coding]}]
        return FHIROrganization(
            id=identifier,
            meta={"profile": [frcore_profile("organization")]},
            identifier=[{"value": identifier}] if identifier else None,
            active=active,
            type=type_field,
            name=name,
            partOf=parent_ref,
        )

    # ------------------------------------------------------------------
    # Organization : Unité Fonctionnelle (UF)
    # ------------------------------------------------------------------
    def create_organization_uf(
        self,
        identifier: str,
        name: str,
        active: bool = True,
        type_activite_code: Optional[str] = None,
        parent_ref: Optional[FHIRReference] = None,
    ) -> FHIROrganization:
        """Crée une Organization FRCoreOrganizationUFProfile. `type` est fixé à UF
        (CodeSystem v2-3307) conformément au profil ; `type_activite_code` alimente
        l'extension fr-core-organization-type-activite quand une donnée existe
        (issue de UFActivity ou du champ uf_type de secours)."""
        extensions = []
        if type_activite_code:
            extensions.append({
                "url": f"{FRCORE_BASE}/StructureDefinition/fr-core-organization-type-activite",
                "valueCodeableConcept": {"coding": [{"code": type_activite_code}]},
            })
        return FHIROrganization(
            id=identifier,
            meta={"profile": [frcore_profile("organization_uf")]},
            identifier=[{"value": identifier}] if identifier else None,
            active=active,
            type=[{"coding": [{"system": FRCORE_CS_V2_3307, "code": "UF"}]}],
            name=name,
            partOf=parent_ref,
            extension=extensions or None,
        )

    # ------------------------------------------------------------------
    # Organization : Unité d'Activité (UAC / PAC) — nouveau profil FRCore 2.2.0
    # ------------------------------------------------------------------
    def create_organization_uac(
        self,
        identifier: str,
        name: str,
        active: bool = True,
        discipline_prestation_code: Optional[str] = None,
        tarif_code: Optional[str] = None,
        parent_ref: Optional[FHIRReference] = None,
    ) -> FHIROrganization:
        """Crée une Organization FRCoreOrganizationUACProfile. `partOf` doit
        obligatoirement référencer une FRCoreOrganizationUFProfile (contrainte du
        profil)."""
        extensions = []
        if discipline_prestation_code:
            extensions.append({
                "url": f"{FRCORE_BASE}/StructureDefinition/fr-core-organization-discipline-prestation",
                "valueCoding": {"code": discipline_prestation_code},
            })
        if tarif_code:
            extensions.append({
                "url": f"{FRCORE_BASE}/StructureDefinition/fr-core-organization-tarif",
                "valueCoding": {"code": tarif_code},
            })
        return FHIROrganization(
            id=identifier,
            meta={"profile": [frcore_profile("organization_uac")]},
            identifier=[{"value": identifier}] if identifier else None,
            active=active,
            type=[{"coding": [{"system": FRCORE_CS_V2_3307, "code": "UAC"}]}],
            name=name,
            partOf=parent_ref,
            extension=extensions or None,
        )

    # ------------------------------------------------------------------
    # Location : UH / Chambre / Lit (lieux physiques)
    # ------------------------------------------------------------------
    def create_location(
        self,
        identifier: str,
        name: str,
        location_kind: str,
        status: str = "active",
        type_chambre_code: Optional[str] = None,
        position_lit_code: Optional[str] = None,
        parent_ref: Optional[FHIRReference] = None,
    ) -> FHIRLocation:
        """Crée une Location FRCoreLocationProfile.

        `location_kind` : "UH" | "CHAMB" | "LIT" — détermine `type` et les
        extensions applicables (typeChambre pour une chambre, positionLit pour un
        lit ; obligatoires par les invariants du profil quand ces extensions sont
        posées : `type` doit alors valoir respectivement CHAMB/LIT).
        """
        extensions = []
        type_coding = None
        if location_kind == "CHAMB":
            type_coding = {"code": "CHAMB", "display": "Chambre"}
            if type_chambre_code:
                extensions.append({
                    "url": f"{FRCORE_BASE}/StructureDefinition/fr-core-location-type-chambre",
                    "valueCoding": {"code": type_chambre_code},
                })
        elif location_kind == "LIT":
            type_coding = {"code": "LIT", "display": "Lit"}
            if position_lit_code:
                extensions.append({
                    "url": f"{FRCORE_BASE}/StructureDefinition/fr-core-location-position-lit",
                    "valueCoding": {"code": position_lit_code},
                })
        elif location_kind == "UH":
            type_coding = {"code": "UH", "display": "Unité d'hébergement"}

        return FHIRLocation(
            id=identifier,
            meta={"profile": [frcore_profile("location")]},
            identifier=[self.converter.create_identifier(f"{self.base_url}/location/identifier", identifier)],
            status=status or "active",
            name=name,
            type=[self.converter.create_codeable_concept(
                type_coding["code"], FRCORE_BASE + "/CodeSystem/fr-core-cs-location-type", type_coding["display"]
            )] if type_coding else None,
            partOf=parent_ref,
            extension=extensions or None,
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
                      organization_ref: Optional[FHIRReference] = None,
                      contacts: Optional[List[Dict[str, Any]]] = None) -> FHIRPatient:
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
            managingOrganization=organization_ref,
            contact=contacts
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
                        location_ref: Optional[FHIRReference] = None,
                        participants: Optional[List[Dict[str, Any]]] = None,
                        service_provider_ref: Optional[FHIRReference] = None) -> FHIREncounter:
        """Crée une ressource Encounter FHIR.

        `location_ref` doit référencer un lieu physique (Location — UH/Chambre/Lit) ;
        `service_provider_ref` référence l'Organization responsable (UF), séparément,
        via Encounter.serviceProvider — depuis que l'UF est une Organization (FRCore
        2.2.0) et non plus une Location, elle ne peut plus être posée sur `location`.
        """

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
                "location": location_ref.model_dump(),
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
            location=locations,
            participant=participants,
            serviceProvider=service_provider_ref,
        )

    def create_related_person(self,
                              identifier: str,
                              patient_ref: FHIRReference,
                              relationship_code: str,
                              relationship_display: str,
                              name: Dict[str, Any],
                              telecom: Optional[List[Dict[str, Any]]] = None,
                              gender: Optional[str] = None,
                              birth_date: Optional[str] = None,
                              address: Optional[Dict[str, Any]] = None,
                              period: Optional[FHIRPeriod] = None) -> FHIRRelatedPerson:
        """Crée une ressource RelatedPerson FHIR."""
        rel_cc = self.converter.create_codeable_concept(
            relationship_code,
            "http://terminology.hl7.org/CodeSystem/v2-0063",
            relationship_display or relationship_code
        )
        return FHIRRelatedPerson(
            id=identifier,
            patient=patient_ref,
            relationship=[rel_cc],
            name=[name],
            telecom=telecom,
            gender=gender,
            birthDate=birth_date,
            address=address,
            period=period
        )
