"""
Service d'export des données vers FHIR.
"""
from datetime import datetime
from typing import Dict, List, Optional
from sqlmodel import Session, select
import hashlib

from app.models_structure_fhir import EntiteJuridique, EntiteGeographique
from app.utils.structured_logging import StructuredLogger, log_operation, metrics
from app.models_structure import (
    Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
)
from app.models import Mouvement, Patient, Dossier, Venue
from app.models_contacts import PatientContact, VenueContact

from app.converters.fhir_converter import (
    FHIRBundle, FHIRReference,
    StructureToFHIRConverter,
    PatientToFHIRConverter,
    EncounterToFHIRConverter,
    HL7ToFHIRConverter
)

from app.services.cache_service import get_cache_service

class FHIRExportService:
    """Service d'export des données vers FHIR."""
    
    def __init__(self, session: Session, base_url: str, enable_cache: bool = True):
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
        
        # Service de cache Redis
        self.enable_cache = enable_cache
        self.cache = get_cache_service() if enable_cache else None
    
    def export_structure(self, ej: EntiteJuridique) -> FHIRBundle:
        """Exporte la structure d'un établissement en FHIR."""
        import time
        start_time = time.time()
        
        # Vérifier le cache
        cache_key = f"fhir:export:structure:ej:{ej.id}"
        if self.cache and self.enable_cache:
            cached = self.cache.get(cache_key)
            if cached:
                self.logger.info(
                    "Structure export from cache",
                    ej_id=ej.id,
                    cache_hit=True,
                    duration_ms=round((time.time() - start_time) * 1000, 2)
                )
                metrics.observe("fhir.export.duration", (time.time() - start_time) * 1000, {"type": "structure", "cache": "hit"})
                return FHIRBundle(**cached)
        
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
        
        bundle = FHIRBundle(entry=entries)
        
        # Mise en cache
        if self.cache and self.enable_cache:
            cache_ttl = 3600  # 1 heure pour structure (change rarement)
            self.cache.set(cache_key, bundle.model_dump(), ttl=cache_ttl)
            self.logger.debug("Structure cached", cache_key=cache_key, ttl=cache_ttl)
        
        metrics.observe("fhir.export.duration", duration * 1000, {"type": "structure", "cache": "miss"})
        
        return bundle
    
    def export_patients(self, ej: EntiteJuridique) -> FHIRBundle:
        """Exporte les patients d'un établissement en FHIR."""
        import time
        start_time = time.time()
        
        # Vérifier le cache
        cache_key = f"fhir:export:patients:ej:{ej.id}"
        if self.cache and self.enable_cache:
            cached = self.cache.get(cache_key)
            if cached:
                self.logger.info("Patients export from cache", ej_id=ej.id, cache_hit=True)
                metrics.observe("fhir.export.duration", (time.time() - start_time) * 1000, {"type": "patients", "cache": "hit"})
                return FHIRBundle(**cached)
        
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
            # Build Patient.contact[] from PatientContact models
            contacts_payload = []
            try:
                for pc in sorted(patient.contacts, key=lambda c: (c.priority, c.sequence)):
                    rel_display = pc.relationship_display or pc.relationship_code
                    relationship_coding = [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0063",
                        "code": pc.relationship_code,
                        "display": rel_display
                    }]
                    contact_entry = {
                        "relationship": [{"coding": relationship_coding[0:1]}],
                        "name": {
                            "family": pc.family_name,
                            "given": [g for g in [pc.given_name] if g],
                            "prefix": [pc.prefix] if pc.prefix else None,
                            "suffix": [pc.suffix] if pc.suffix else None
                        },
                        "telecom": [t for t in [
                            {"system": "phone", "value": pc.phone_number, "use": "home"} if pc.phone_number else None,
                            {"system": "phone", "value": pc.business_phone, "use": "work"} if pc.business_phone else None,
                        ] if t],
                        "address": {
                            "line": [l for l in [pc.address_line1, pc.address_line2] if l],
                            "city": pc.address_city,
                            "postalCode": pc.address_postalcode,
                            "country": pc.address_country
                        } if any([pc.address_line1, pc.address_line2, pc.address_city, pc.address_postalcode, pc.address_country]) else None,
                        "gender": ({"M": "male", "F": "female", "O": "other", "U": "unknown"}.get(pc.gender) if pc.gender else None),
                        "period": {
                            "start": pc.start_date.isoformat() if pc.start_date else None,
                            "end": pc.end_date.isoformat() if pc.end_date else None
                        } if pc.start_date or pc.end_date else None,
                        "extension": [
                            {
                                "url": f"{self.base_url}/StructureDefinition/contact-role",
                                "valueCode": pc.contact_role
                            }
                        ] if pc.contact_role else None
                    }
                    contacts_payload.append(contact_entry)
            except Exception:
                pass

            fhir_patient = self.patient_converter.create_patient(
                patient.identifier,
                patient.given,
                patient.family,
                org_ref,
                contacts=contacts_payload or None
            )
            entries.append(self.converter.create_bundle_entry(fhir_patient))
            self._patient_refs[patient.identifier] = self.converter.create_reference(
                "Patient", patient.identifier,
                f"{patient.family} {patient.given}"
            )
        
        bundle = FHIRBundle(entry=entries)
        
        # Mise en cache (TTL court car patients changent souvent)
        if self.cache and self.enable_cache:
            cache_ttl = 600  # 10 minutes
            self.cache.set(cache_key, bundle.model_dump(), ttl=cache_ttl)
            self.logger.debug("Patients cached", cache_key=cache_key, ttl=cache_ttl)
        
        duration = time.time() - start_time
        metrics.observe("fhir.export.duration", duration * 1000, {"type": "patients", "cache": "miss"})
        
        return bundle
    
    def export_venues(self, ej: EntiteJuridique) -> FHIRBundle:
        """Exporte les venues d'un établissement en FHIR."""
        import time
        start_time = time.time()
        
        # Vérifier le cache
        cache_key = f"fhir:export:venues:ej:{ej.id}"
        if self.cache and self.enable_cache:
            cached = self.cache.get(cache_key)
            if cached:
                self.logger.info("Venues export from cache", ej_id=ej.id, cache_hit=True)
                metrics.observe("fhir.export.duration", (time.time() - start_time) * 1000, {"type": "venues", "cache": "hit"})
                return FHIRBundle(**cached)
        
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
            # Build RelatedPerson resources and Encounter.participant entries from VenueContact
            participants = []
            related_person_entries = []
            try:
                for vc in sorted(venue.contacts, key=lambda c: (c.sequence, c.family_name)):
                    rp_id = f"VC-{venue.venue_seq}-{vc.sequence}"
                    name = {
                        "family": vc.family_name,
                        "given": [g for g in [vc.given_name] if g],
                        "prefix": [vc.prefix] if vc.prefix else None,
                        "suffix": [vc.suffix] if vc.suffix else None
                    }
                    telecom = [t for t in [
                        {"system": "phone", "value": vc.phone_number, "use": "home"} if vc.phone_number else None,
                        {"system": "phone", "value": vc.business_phone, "use": "work"} if vc.business_phone else None,
                    ] if t]
                    address = {
                        "line": [l for l in [vc.address_line1, vc.address_line2] if l],
                        "city": vc.address_city,
                        "postalCode": vc.address_postalcode,
                        "country": vc.address_country
                    } if any([vc.address_line1, vc.address_line2, vc.address_city, vc.address_postalcode, vc.address_country]) else None
                    period = self.encounter_converter.converter.create_period(vc.start_datetime, vc.end_datetime) if (vc.start_datetime or vc.end_datetime) else None
                    related_person = self.encounter_converter.create_related_person(
                        rp_id,
                        self._patient_refs[patient.identifier],
                        vc.relationship_code,
                        vc.relationship_display or vc.relationship_code,
                        name,
                        telecom=telecom or None,
                        gender=( {"M":"male","F":"female","O":"other","U":"unknown"}.get(vc.gender) if vc.gender else None ),
                        birth_date=vc.birth_date.isoformat() if vc.birth_date else None,
                        address=address,
                        period=period
                    )
                    related_person_entries.append(self.converter.create_bundle_entry(related_person))
                    participants.append({
                        "individual": {"reference": f"RelatedPerson/{rp_id}"},
                        "type": [{
                            "coding": [{
                                "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                                "code": "PART",
                                "display": "participant"
                            }]
                        }],
                        "period": {
                            "start": vc.start_datetime.isoformat() if vc.start_datetime else None,
                            "end": vc.end_datetime.isoformat() if vc.end_datetime else None
                        } if vc.start_datetime or vc.end_datetime else None,
                        "extension": [
                            {
                                "url": f"{self.base_url}/StructureDefinition/contact-role",
                                "valueCode": vc.contact_role
                            }
                        ] if vc.contact_role else None
                    })
            except Exception:
                pass

            encounter = self.encounter_converter.create_encounter(
                venue_id,
                self._patient_refs[patient.identifier],
                status,
                start_date,
                end_date,
                location_ref,
                participants=participants or None
            )
            entries.append(self.converter.create_bundle_entry(encounter))
            # Append related persons to bundle after encounter
            entries.extend(related_person_entries)
        
        bundle = FHIRBundle(entry=entries)
        
        # Mise en cache (TTL très court car venues changent en temps réel)
        if self.cache and self.enable_cache:
            cache_ttl = 300  # 5 minutes
            self.cache.set(cache_key, bundle.model_dump(), ttl=cache_ttl)
            self.logger.debug("Venues cached", cache_key=cache_key, ttl=cache_ttl)
        
        duration = time.time() - start_time
        metrics.observe("fhir.export.duration", duration * 1000, {"type": "venues", "cache": "miss"})
        
        return bundle