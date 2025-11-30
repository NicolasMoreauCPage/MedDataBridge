"""
Convertisseurs FHIR → Models internes pour l'import.

Ce module fournit les classes pour convertir des ressources FHIR R4
vers les modèles internes de MedDataBridge.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlmodel import Session, select

from app.models_structure import EntiteJuridique
from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit, LocationPhysicalType
)
from app.models import Patient, Dossier, Mouvement, Venue
from app.models_identifiers import Identifier, IdentifierType


class FHIRImportError(Exception):
    """Erreur lors de l'import FHIR."""
    pass


class FHIRToLocationConverter:
    """Convertit des ressources FHIR Location vers les modèles de structure."""

    def __init__(self, session: Session, ej: EntiteJuridique):
        self.session = session
        self.ej = ej

    def convert_location(self, fhir_location: Dict[str, Any]) -> Any:
        """
        Convertit une ressource FHIR Location vers le modèle de structure approprié.
        
        Détermine automatiquement le type (EG, Pole, Service, UF, UH, Chambre, Lit)
        basé sur physicalType.
        """
        physical_type = self._extract_physical_type(fhir_location)
        name = fhir_location.get("name", "")
        identifiers = self._extract_identifiers(fhir_location)
        description = fhir_location.get("description")
        
        # Extraire le parent si présent
        part_of = fhir_location.get("partOf")
        parent_ref = part_of.get("reference") if part_of else None
        
        # Extraire identifier pour entité (NOT NULL required)
        identifier = identifiers[0]["value"] if identifiers else name.replace(" ", "_").upper()
        
        # Mapper vers le modèle approprié selon physicalType
        if physical_type == LocationPhysicalType.SI:
            # Site = Entité Géographique
            eg = EntiteGeographique(
                name=name,
                identifier=identifier,
                finess="999999999",  # FINESS par défaut si non fourni
                entite_juridique_id=self.ej.id,
                description=description
            )
            self.session.add(eg)
            self.session.commit()
            self.session.refresh(eg)
            return eg
            
        elif physical_type == LocationPhysicalType.BU:
            # Building = Pole
            parent_id = self._resolve_parent_id(parent_ref, EntiteGeographique)
            pole = Pole(
                name=name,
                identifier=identifier,
                physical_type=physical_type,
                entite_geo_id=parent_id,
                description=description
            )
            self.session.add(pole)
            self.session.commit()
            self.session.refresh(pole)
            return pole
            
        elif physical_type == LocationPhysicalType.WI:
            # Wing = Service
            parent_id = self._resolve_parent_id(parent_ref, Pole)
            service = Service(
                name=name,
                identifier=identifier,
                physical_type=physical_type,
                service_type="MCO",  # Par défaut
                pole_id=parent_id,
                description=description
            )
            self.session.add(service)
            self.session.commit()
            self.session.refresh(service)
            return service
            
        elif physical_type == LocationPhysicalType.WA:
            # Ward = Unité Fonctionnelle
            parent_id = self._resolve_parent_id(parent_ref, Service)
            uf = UniteFonctionnelle(
                name=name,
                identifier=identifier,
                physical_type=physical_type,
                service_id=parent_id,
                description=description
            )
            self.session.add(uf)
            self.session.commit()
            self.session.refresh(uf)
            return uf
            
        elif physical_type == LocationPhysicalType.LV:
            # Level = Unité d'Hébergement
            parent_id = self._resolve_parent_id(parent_ref, UniteFonctionnelle)
            uh = UniteHebergement(
                name=name,
                identifier=identifier,
                physical_type=physical_type,
                unite_fonctionnelle_id=parent_id,
                description=description
            )
            self.session.add(uh)
            self.session.commit()
            self.session.refresh(uh)
            return uh
            
        elif physical_type == LocationPhysicalType.RO:
            # Room = Chambre
            parent_id = self._resolve_parent_id(parent_ref, UniteHebergement)
            chambre = Chambre(
                name=name,
                identifier=identifier,
                physical_type=physical_type,
                unite_hebergement_id=parent_id,
                description=description
            )
            self.session.add(chambre)
            self.session.commit()
            self.session.refresh(chambre)
            return chambre
            
        elif physical_type == LocationPhysicalType.BD:
            # Bed = Lit
            parent_id = self._resolve_parent_id(parent_ref, Chambre)
            lit = Lit(
                name=name,
                identifier=identifier,
                physical_type=physical_type,
                chambre_id=parent_id,
                description=description
            )
            self.session.add(lit)
            self.session.commit()
            self.session.refresh(lit)
            return lit
            
        else:
            raise FHIRImportError(f"Type physique non supporté: {physical_type}")

    def _extract_physical_type(self, fhir_location: Dict[str, Any]) -> Optional[LocationPhysicalType]:
        """Extrait le type physique depuis physicalType et retourne un membre de LocationPhysicalType.

        FHIR peut fournir des codes en minuscules; notre enum stocke les valeurs en minuscules.
        """
        physical_type = fhir_location.get("physicalType")
        if not physical_type:
            return None

        coding = physical_type.get("coding", [])
        if coding:
            code = coding[0].get("code") or ""
            code_lc = code.lower()
            # Mapper quelques alias éventuels
            alias_map = {
                "ward": "wa",
                "wing": "wi",
                "level": "lv",
                "site": "si",
                "building": "bu",
                "room": "ro",
                "bed": "bd",
            }
            code_norm = alias_map.get(code_lc, code_lc)
            try:
                return LocationPhysicalType(code_norm)
            except ValueError:
                return None
        return None

    def _extract_identifiers(self, fhir_location: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extrait les identifiants."""
        identifiers = []
        for ident in fhir_location.get("identifier", []):
            identifiers.append({
                "system": ident.get("system", ""),
                "value": ident.get("value", ""),
                "use": ident.get("use", "official")
            })
        return identifiers

    def _resolve_parent_id(self, parent_ref: Optional[str], parent_model) -> Optional[int]:
        """Résout une référence parent vers un ID."""
        if not parent_ref:
            return None
        
        # Format: "Location/123" → extraire 123
        parts = parent_ref.split("/")
        if len(parts) != 2:
            return None
        
        # À FAIRE: Implémenter une vraie résolution depuis la base
        # Pour l'instant, on retourne l'ID extrait
        try:
            return int(parts[1])
        except ValueError:
            return None

    def _add_identifiers(self, entity, identifiers: List[Dict[str, str]]):
        """Ajoute des identifiants à une entité."""
        for ident_data in identifiers:
            # Déterminer le type d'identifiant
            system = ident_data.get("system", "")
            value = ident_data.get("value", "")
            
            # Mapper system vers IdentifierType
            identifier_type = self._map_system_to_type(system)
            
            # Créer l'identifiant - le modèle Identifier n'a pas de champs entity_type/entity_id génériques
            # On utilise les foreign keys spécifiques selon le type d'entité
            identifier_kwargs = {
                "type": identifier_type,
                "value": value,
                "system": system
            }
            
            # Mapper vers la foreign key appropriée
            if isinstance(entity, Patient):
                identifier_kwargs["patient_id"] = entity.id
            elif hasattr(entity, 'id'):
                # Pour les structures, on peut utiliser structure_id si disponible
                # Sinon, l'identifiant ne sera pas lié (limitation actuelle du modèle)
                pass
            
            identifier = Identifier(**identifier_kwargs)
            self.session.add(identifier)
        
        self.session.commit()

    def _map_system_to_type(self, system: str) -> str:
        """Mappe un system FHIR vers un IdentifierType."""
        # Mapping simplifié - un seul type par entité
        system_lower = system.lower()
        if "ipp" in system_lower or "urn:oid:1.2.250.1.71.4.2.1" in system:
            return IdentifierType.IPP.value
        elif "nda" in system_lower:
            return IdentifierType.NDA.value
        elif "vn" in system_lower:
            return IdentifierType.VN.value
        elif "mvt" in system_lower:
            return IdentifierType.MVT.value
        else:
            # Par défaut, considérer comme IPP (patient)
            return IdentifierType.IPP.value


class FHIRToPatientConverter:
    """Convertit des ressources FHIR Patient vers les modèles Patient."""

    def __init__(self, session: Session, ej: EntiteJuridique):
        self.session = session
        self.ej = ej

    def convert_patient(self, fhir_patient: Dict[str, Any]) -> Patient:
        """
        Convertit une ressource FHIR Patient vers le modèle Patient.
        """
        # Extraire les noms
        names = fhir_patient.get("name", [])
        official_name = next((n for n in names if n.get("use") == "official"), names[0] if names else {})
        
        family = official_name.get("family", "")
        given = " ".join(official_name.get("given", []))
        
        # Extraire les identifiants
        identifiers = fhir_patient.get("identifier", [])
        
        # Parser la date de naissance
        birth_date_str = fhir_patient.get("birthDate")
        birth_date = birth_date_str if birth_date_str else None
        
        # Parser le genre
        gender_fhir = fhir_patient.get("gender")
        gender = self._parse_gender(gender_fhir)
        
        # Créer le patient avec les vrais champs du modèle
        patient = Patient(
            family=family,
            given=given,
            birth_date=birth_date,
            gender=gender
        )
        
        self.session.add(patient)
        self.session.commit()
        self.session.refresh(patient)
        
        # Traiter les extensions FRCore
        self._process_fr_core_extensions(fhir_patient, patient)
        
        # Ajouter les identifiants
        for ident_data in identifiers:
            system = ident_data.get("system", "")
            value = ident_data.get("value", "")
            
            identifier_type = self._map_system_to_type(system)
            
            identifier = Identifier(
                type=identifier_type,
                value=value,
                system=system,
                patient_id=patient.id
            )
            self.session.add(identifier)
        
        self.session.commit()
        
        # Créer un dossier par défaut avec numéro de séquence
        # Générer dossier_seq unique basé sur l'ID patient et timestamp
        dossier_seq = patient.id * 10000 + int(datetime.now().timestamp() % 10000)
        
        dossier = Dossier(
            dossier_seq=dossier_seq,
            patient_id=patient.id,
            admit_time=datetime.now(),
            dossier_type="HOSPITALISE"
        )
        self.session.add(dossier)
        self.session.commit()
        
        return patient

    def _parse_birth_date(self, birth_date_str: Optional[str]) -> Optional[datetime]:
        """Parse une date de naissance FHIR."""
        if not birth_date_str:
            return None
        try:
            return datetime.fromisoformat(birth_date_str)
        except:
            return None

    def _parse_gender(self, gender: Optional[str]) -> Optional[str]:
        """Parse un sexe FHIR (garde les valeurs FHIR: male/female/other/unknown)."""
        if not gender:
            return "unknown"
        
        # Retourner la valeur FHIR telle quelle (le modèle stocke male/female/other/unknown)
        return gender.lower()

    def _map_system_to_type(self, system: str) -> str:
        """Mappe un system FHIR vers un IdentifierType."""
        # Mapping simplifié - un seul type par entité
        system_lower = system.lower()
        if "ipp" in system_lower or "urn:oid:1.2.250.1.71.4.2.1" in system:
            return IdentifierType.IPP.value
        elif "nda" in system_lower:
            return IdentifierType.NDA.value
        elif "vn" in system_lower:
            return IdentifierType.VN.value
        elif "mvt" in system_lower:
            return IdentifierType.MVT.value
        else:
            # Par défaut, considérer comme IPP (patient)
            return IdentifierType.IPP.value

    def _process_fr_core_extensions(self, fhir_patient: Dict[str, Any], patient: Patient):
        """Traite les extensions FRCore du patient FHIR."""
        extensions = fhir_patient.get("extension", [])
        
        for extension in extensions:
            url = extension.get("url", "")
            
            # Extension FRCore fiabilité d'identité
            if url == "http://interopsante.org/fhir/StructureDefinition/fr-core-patient-identity-reliability":
                self._process_identity_reliability_extension(extension, patient)
            
            # Extension FRCore lieu de naissance
            elif url == "http://interopsante.org/fhir/StructureDefinition/fr-core-patient-birth-place":
                self._process_birth_place_extension(extension, patient)

    def _process_identity_reliability_extension(self, extension: Dict[str, Any], patient: Patient):
        """Traite l'extension FRCore de fiabilité d'identité."""
        sub_extensions = extension.get("extension", [])
        
        for sub_ext in sub_extensions:
            sub_url = sub_ext.get("url", "")
            
            if sub_url == "identityReliability":
                coding = sub_ext.get("valueCoding", {})
                patient.identity_reliability_code = coding.get("code")
            
            elif sub_url == "identityReliabilityDate":
                patient.identity_reliability_date = sub_ext.get("valueDate")
            
            elif sub_url == "identityReliabilitySource":
                patient.identity_reliability_source = sub_ext.get("valueString")
        
        # Commit les changements
        self.session.commit()

    def _process_birth_place_extension(self, extension: Dict[str, Any], patient: Patient):
        """Traite l'extension FRCore de lieu de naissance."""
        address = extension.get("valueAddress", {})
        
        if address:
            patient.birth_city = address.get("city")
            patient.birth_state = address.get("state")
            patient.birth_postal_code = address.get("postalCode")
            patient.birth_country = address.get("country")
            
            # Commit les changements
            self.session.commit()


class FHIRToEncounterConverter:
    """Convertit des ressources FHIR Encounter vers les modèles Mouvement."""

    def __init__(self, session: Session, resource_map: Optional[Dict[str, int]] = None):
        self.session = session
        # mapping from bundle resource ids or fullUrls (e.g. 'pat-1' or 'Patient/pat-1')
        # to internal DB numeric ids (patient.id)
        # IMPORTANT: accept the exact dict passed in (even if empty) so the importer
        # and converters share the same mapping instance. Using `or {}` would create
        # a new dict when an empty one is passed.
        self.resource_map = resource_map if resource_map is not None else {}

    def convert_encounter(self, fhir_encounter: Dict[str, Any]) -> Mouvement:
        """
        Convertit une ressource FHIR Encounter vers le modèle Mouvement.
        """
        # Extraire le patient
        subject_ref = fhir_encounter.get("subject", {}).get("reference", "")
        patient_id = self._extract_id_from_reference(subject_ref)
        
        # Extraire les identifiants
        identifiers = fhir_encounter.get("identifier", [])
        nda = None
        for ident in identifiers:
            if "nda" in ident.get("system", "").lower():
                nda = ident.get("value")
                break
        
        # Extraire la période
        period = fhir_encounter.get("period", {})
        date_debut = self._parse_datetime(period.get("start"))
        date_fin = self._parse_datetime(period.get("end"))
        
        # Extraire le statut
        status = fhir_encounter.get("status", "planned")
        
        # Extraire la classe (type de mouvement)
        encounter_class = fhir_encounter.get("class", {})
        type_mouvement = encounter_class.get("code", "AMB")
        
        # Trouver le dossier du patient
        dossier = self.session.exec(select(Dossier).where(Dossier.patient_id == patient_id)).first()
        
        if not dossier:
            raise FHIRImportError(f"Aucun dossier trouvé pour le patient {patient_id}")
        
        # Trouver ou créer une venue pour ce dossier
        # À FAIRE: Implémenter une vraie résolution de venue depuis les locations
        # Pour l'instant, utiliser la première venue du dossier ou en créer une
        venue = self.session.exec(select(Venue).where(Venue.dossier_id == dossier.id)).first()
        if not venue:
            # Créer une venue par défaut (start_time = début de la period si disponible)
            venue_seq = dossier.id * 1000 + int(datetime.now().timestamp() % 1000)
            start_time = date_debut or datetime.now()
            venue = Venue(
                venue_seq=venue_seq,
                dossier_id=dossier.id,
                start_time=start_time
            )
            self.session.add(venue)
            self.session.commit()
            self.session.refresh(venue)
        
        # Générer un mouvement_seq unique (simple combinaison venue + horodatage courte fenêtre)
        mouvement_seq = venue.id * 10000 + int(datetime.now().timestamp() % 10000)
        
        # Créer le mouvement
        mouvement = Mouvement(
            mouvement_seq=mouvement_seq,
            venue_id=venue.id,
            type=type_mouvement,
            when=date_debut or datetime.now(),
            end_time=date_fin,
            status=self._map_status(status)
        )
        
        self.session.add(mouvement)
        self.session.commit()
        self.session.refresh(mouvement)
        
        # Ajouter l'identifiant NDA
        # REMARQUE: Le modèle Identifier n'a pas de foreign key pour Mouvement
        # On pourrait l'ajouter ou utiliser un autre mécanisme
        if nda:
            identifier = Identifier(
                type=IdentifierType.NDA,
                value=nda,
                system="http://example.org/nda"
                # Pas de mouvement_id dans le modèle Identifier actuel
            )
            self.session.add(identifier)
            self.session.commit()
        
        return mouvement

    def _extract_id_from_reference(self, reference: str) -> Optional[int]:
        """Extrait l'ID depuis une référence FHIR."""
        if not reference:
            return None

        # Normalize and strip whitespace
        ref = reference.strip()

        # Remove leading '#' used in some bundle-local references
        if ref.startswith('#'):
            ref = ref[1:]

        # If it's a full URL, keep only the tail (e.g. http://.../Patient/pat-999 -> Patient/pat-999)
        if '/' in ref:
            parts = ref.split('/')
            # prefer last two segments if available
            if len(parts) >= 2:
                resource_type = parts[-2]
                ref_id = parts[-1]
                candidate_full = f"{resource_type}/{ref_id}"
            else:
                # fallback
                ref_id = parts[-1]
                candidate_full = ref
        else:
            # bare id (e.g. 'pat-999')
            ref_id = ref
            candidate_full = None

    # (no debug prints)

        # Try numeric id first
        try:
            return int(ref_id)
        except (ValueError, TypeError):
            # Not a numeric id — try resolving via resource_map (bundle-local ids)
            if hasattr(self, 'resource_map') and self.resource_map:
                # exact original reference (e.g. 'Patient/pat-999' or long URL)
                if ref in self.resource_map:
                    return self.resource_map[ref]
                # normalized candidate like 'Patient/pat-999'
                if candidate_full and candidate_full in self.resource_map:
                    return self.resource_map[candidate_full]
                # bare id lookup
                if ref_id in self.resource_map:
                    return self.resource_map[ref_id]
            return None

    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Parse une datetime FHIR."""
        if not datetime_str:
            return None
        try:
            return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        except:
            return None

    def _map_status(self, fhir_status: str) -> str:
        """Mappe un statut FHIR vers un statut interne."""
        status_map = {
            "planned": "PRÉVU",
            "arrived": "ARRIVÉ",
            "triaged": "EN_ATTENTE",
            "in-progress": "EN_COURS",
            "onleave": "ABSENCE_TEMPORAIRE",
            "finished": "TERMINÉ",
            "cancelled": "ANNULÉ",
            "entered-in-error": "ERREUR"
        }
        return status_map.get(fhir_status.lower(), "EN_COURS")


class FHIRBundleImporter:
    """Importe un bundle FHIR complet."""

    def __init__(self, session: Session, ej: EntiteJuridique):
        self.session = session
        self.ej = ej
        # resource_map: maps bundle-local ids and references to DB ids
        self.resource_map: Dict[str, int] = {}
        self.location_converter = FHIRToLocationConverter(session, ej)
        self.patient_converter = FHIRToPatientConverter(session, ej)
        self.encounter_converter = FHIRToEncounterConverter(session, resource_map=self.resource_map)

    def import_bundle(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Importe un bundle FHIR complet.
        
        Returns:
            Résultat de l'import avec statistiques.
        """
        if bundle.get("resourceType") != "Bundle":
            raise FHIRImportError("La ressource n'est pas un Bundle FHIR")
        
        entries = bundle.get("entry", [])
        
        results = {
            "total": len(entries),
            "imported": 0,
            "errors": [],
            "locations": 0,
            "patients": 0,
            "encounters": 0
        }
        
        # Import des ressources dans l'ordre : Location → Patient → Encounter
        for entry in entries:
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")
            
            # Valider les profils FRCore
            self._validate_fr_core_profiles(resource)
            
            try:
                if resource_type == "Location":
                    entity = self.location_converter.convert_location(resource)
                    # Record mapping: resource.id and full reference
                    res_id = resource.get('id')
                    if res_id and hasattr(entity, 'id'):
                        self.resource_map[res_id] = entity.id
                        self.resource_map[f"Location/{res_id}"] = entity.id
                    results["locations"] += 1
                    results["imported"] += 1
                    
                elif resource_type == "Patient":
                    patient = self.patient_converter.convert_patient(resource)
                    res_id = resource.get('id')
                    if res_id and hasattr(patient, 'id'):
                        self.resource_map[res_id] = patient.id
                        self.resource_map[f"Patient/{res_id}"] = patient.id
                    results["patients"] += 1
                    results["imported"] += 1
                    
                elif resource_type == "Encounter":
                    mouvement = self.encounter_converter.convert_encounter(resource)
                    res_id = resource.get('id')
                    if res_id and hasattr(mouvement, 'id'):
                        self.resource_map[res_id] = mouvement.id
                        self.resource_map[f"Encounter/{res_id}"] = mouvement.id
                    results["encounters"] += 1
                    results["imported"] += 1
                    
            except Exception as e:
                results["errors"].append({
                    "resourceType": resource_type,
                    "error": str(e)
                })
        
        return results

    def _validate_fr_core_profiles(self, resource: Dict[str, Any]):
        """Valide que les ressources utilisent les profils FRCore appropriés."""
        resource_type = resource.get("resourceType")
        meta = resource.get("meta", {})
        profiles = meta.get("profile", [])
        
        # Profils FRCore attendus par type de ressource
        expected_profiles = {
            "Patient": ["http://interopsante.org/fhir/StructureDefinition/fr-core-patient"],
            "Encounter": ["http://interopsante.org/fhir/StructureDefinition/fr-encounter"],
            "Location": ["http://interopsante.org/fhir/StructureDefinition/fr-location"],
            "Organization": ["http://interopsante.org/fhir/StructureDefinition/fr-organization"]
        }
        
        if resource_type in expected_profiles:
            expected = expected_profiles[resource_type]
            # Vérifier qu'au moins un profil FRCore est présent
            has_fr_profile = any(profile in profiles for profile in expected)
            
            if not has_fr_profile:
                # Ne pas lever d'erreur, juste un avertissement dans les logs
                print(f"⚠️  Ressource {resource_type} sans profil FRCore. Profils attendus: {expected}, profils trouvés: {profiles}")

