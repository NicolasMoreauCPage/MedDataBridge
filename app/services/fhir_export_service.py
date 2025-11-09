"""
Service d'export des données vers FHIR.
"""
from datetime import datetime
from typing import Dict, List, Optional
from sqlmodel import Session, select

from app.models_structure_fhir import EntiteJuridique, EntiteGeographique
from app.utils.structured_logging import StructuredLogger, log_operation, metrics
from app.models_structure import (
    Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
)
from app.models import Mouvement, Patient, Dossier, Venue

from app.converters.fhir_converter import (
    FHIRBundle, FHIRReference,
    StructureToFHIRConverter,
    PatientToFHIRConverter,
    EncounterToFHIRConverter,
    HL7ToFHIRConverter
)

class FHIRExportService:
    """Service d'export des données vers FHIR."""
    
    def __init__(self, session: Session, base_url: str):
        self.session = session
        self.base_url = base_url
        self.structure_converter = StructureToFHIRConverter(base_url)
        self.patient_converter = PatientToFHIRConverter(base_url)
        self.encounter_converter = EncounterToFHIRConverter(base_url)
        self.converter = HL7ToFHIRConverter()
        self.logger = StructuredLogger(__name__)
        
        # Cache des références
        self._location_refs: Dict[str, FHIRReference] = {}
        self._patient_refs: Dict[str, FHIRReference] = {}
    
    def export_structure(self, ej: EntiteJuridique) -> FHIRBundle:
        """Exporte la structure d'un établissement en FHIR."""
        import time
        start_time = time.time()
        
        self.logger.info(
            "Starting structure export",
            ej_id=ej.id,
            ej_name=ej.name
        )
        
        entries = []
        
        # Organisation (EJ)
        org_ref = self.converter.create_reference(
            "Organization", ej.finess_ej, ej.name
        )
        
        # Entités géographiques
        for eg in self.session.exec(
            select(EntiteGeographique)
            .where(EntiteGeographique.entite_juridique_id == ej.id)
        ).all():
            location = self.structure_converter.create_location(
                eg.identifier,
                eg.name,
                "ETBL_GRPQ",
                "SI"
            )
            entries.append(self.converter.create_bundle_entry(location))
            self._location_refs[eg.identifier] = self.converter.create_reference(
                "Location", eg.identifier, eg.name
            )
            
            # Pôles
            for pole in self.session.exec(
                select(Pole)
                .where(Pole.entite_geo_id == eg.id)
            ).all():
                location = self.structure_converter.create_location(
                    pole.identifier,
                    pole.name,
                    "PL",
                    pole.physical_type,
                    self._location_refs[eg.identifier]
                )
                entries.append(self.converter.create_bundle_entry(location))
                self._location_refs[pole.identifier] = self.converter.create_reference(
                    "Location", pole.identifier, pole.name
                )
                
                # Services
                for service in self.session.exec(
                    select(Service)
                    .where(Service.pole_id == pole.id)
                ).all():
                    location = self.structure_converter.create_location(
                        service.identifier,
                        service.name,
                        "D",
                        service.physical_type,
                        self._location_refs[pole.identifier]
                    )
                    entries.append(self.converter.create_bundle_entry(location))
                    self._location_refs[service.identifier] = self.converter.create_reference(
                        "Location", service.identifier, service.name
                    )
                    
                    # UFs
                    for uf in self.session.exec(
                        select(UniteFonctionnelle)
                        .where(UniteFonctionnelle.service_id == service.id)
                    ).all():
                        location = self.structure_converter.create_location(
                            uf.identifier,
                            uf.name,
                            "UF",
                            uf.physical_type,
                            self._location_refs[service.identifier]
                        )
                        entries.append(self.converter.create_bundle_entry(location))
                        self._location_refs[uf.identifier] = self.converter.create_reference(
                            "Location", uf.identifier, uf.name
                        )
                        
                        # UHs
                        for uh in self.session.exec(
                            select(UniteHebergement)
                            .where(UniteHebergement.unite_fonctionnelle_id == uf.id)
                        ).all():
                            location = self.structure_converter.create_location(
                                uh.identifier,
                                uh.name,
                                "UH",
                                uh.physical_type,
                                self._location_refs[uf.identifier]
                            )
                            entries.append(self.converter.create_bundle_entry(location))
                            self._location_refs[uh.identifier] = self.converter.create_reference(
                                "Location", uh.identifier, uh.name
                            )
                            
                            # Chambres
                            for chambre in self.session.exec(
                                select(Chambre)
                                .where(Chambre.unite_hebergement_id == uh.id)
                            ).all():
                                location = self.structure_converter.create_location(
                                    chambre.identifier,
                                    chambre.name,
                                    "CH",
                                    chambre.physical_type,
                                    self._location_refs[uh.identifier]
                                )
                                entries.append(self.converter.create_bundle_entry(location))
                                self._location_refs[chambre.identifier] = self.converter.create_reference(
                                    "Location", chambre.identifier, chambre.name
                                )
                                
                                # Lits
                                for lit in self.session.exec(
                                    select(Lit)
                                    .where(Lit.chambre_id == chambre.id)
                                ).all():
                                    location = self.structure_converter.create_location(
                                        lit.identifier,
                                        lit.name,
                                        "LIT",
                                        lit.physical_type,
                                        self._location_refs[chambre.identifier]
                                    )
                                    entries.append(self.converter.create_bundle_entry(location))
                                    self._location_refs[lit.identifier] = self.converter.create_reference(
                                        "Location", lit.identifier, lit.name
                                    )
        
        duration = time.time() - start_time
        self.logger.info(
            "Structure export completed",
            ej_id=ej.id,
            entries_count=len(entries),
            duration_seconds=duration
        )
        metrics.record_operation(
            "export_structure",
            duration,
            status="success",
            ej_id=ej.id,
            entries_count=len(entries)
        )
        
        return FHIRBundle(entry=entries)
    
    def export_patients(self, ej: EntiteJuridique) -> FHIRBundle:
        """Exporte les patients d'un établissement en FHIR."""
        entries = []
        
        # Organisation
        org_ref = self.converter.create_reference(
            "Organization", ej.finess_ej, ej.name
        )
        
        # Patients - find all patients who have venues in this EJ's UFs
        patients_qs = (
            select(Patient)
            .join(Dossier, Patient.dossiers)
            .join(Venue, Dossier.venues)
            .join(UniteFonctionnelle, UniteFonctionnelle.identifier == Venue.uf_responsabilite)
            .join(Service, Service.id == UniteFonctionnelle.service_id)
            .join(Pole, Pole.id == Service.pole_id)
            .join(EntiteGeographique, EntiteGeographique.id == Pole.entite_geo_id)
            .where(EntiteGeographique.entite_juridique_id == ej.id)
            .distinct()  # Ensure no duplicate patients
        )
        
        for patient in self.session.exec(patients_qs).all():
            fhir_patient = self.patient_converter.create_patient(
                patient.identifier,
                patient.given,
                patient.family,
                org_ref
            )
            entries.append(self.converter.create_bundle_entry(fhir_patient))
            self._patient_refs[patient.identifier] = self.converter.create_reference(
                "Patient", patient.identifier,
                f"{patient.family} {patient.given}"
            )
        
        return FHIRBundle(entry=entries)
    
    def export_venues(self, ej: EntiteJuridique) -> FHIRBundle:
        """Exporte les venues d'un établissement en FHIR."""
        entries = []
        
        # Venues - find all venues linked to UFs in this EJ
        venues_qs = (
            select(Venue)
            .join(UniteFonctionnelle, UniteFonctionnelle.identifier == Venue.uf_responsabilite)
            .join(Service, Service.id == UniteFonctionnelle.service_id)
            .join(Pole, Pole.id == Service.pole_id)
            .join(EntiteGeographique, EntiteGeographique.id == Pole.entite_geo_id)
            .where(EntiteGeographique.entite_juridique_id == ej.id)
        )
        
        for venue in self.session.exec(venues_qs).all():
            if not venue.dossier or not venue.dossier.patient:
                continue
            
            # Get patient from dossier
            patient = venue.dossier.patient
            
            # Dates du séjour
            mouvements = self.session.exec(
                select(Mouvement)
                .where(Mouvement.venue_id == venue.id)
                .order_by(Mouvement.when)
            ).all()
            
            start_date = None
            end_date = None
            status = "finished"
            
            if mouvements:
                start_date = mouvements[0].when
                if mouvements[-1].action != "DISCHARGE":
                    status = "in-progress"
                else:
                    end_date = mouvements[-1].when
            
            # UF responsable
            location_ref = None
            if venue.uf_responsabilite:
                if venue.uf_responsabilite in self._location_refs:
                    location_ref = self._location_refs[venue.uf_responsabilite]
            
            # Find any venue identifiers
            venue_id = None
            for identifier in venue.identifiers:
                venue_id = identifier.value
                break
            if not venue_id:
                venue_id = str(venue.venue_seq)
                
            # Créer l'encounter
            encounter = self.encounter_converter.create_encounter(
                venue_id,
                self._patient_refs[patient.identifier],
                status,
                start_date,
                end_date,
                location_ref
            )
            entries.append(self.converter.create_bundle_entry(encounter))
        
        return FHIRBundle(entry=entries)