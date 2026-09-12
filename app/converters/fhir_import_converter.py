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
    EntiteGeographique, Pole, Service, UniteFonctionnelle, UniteActivite,
    UniteHebergement, Chambre, Lit, LocationPhysicalType, LocationStatus
)
from app.converters.fhir_converter import FRCORE_PROFILES
from app.models import Patient, Dossier, Mouvement, Venue
from app.models_identifiers import Identifier, IdentifierType
from app.models_practitioners import MedecinResponsable
from app.services.medecin_extractor import get_or_create_medecin


class FHIRImportError(Exception):
    """Erreur lors de l'import FHIR."""
    pass


def _canonical_uri(profile: str) -> str:
    """Retire la version éventuelle d'un canonical FHIR (``uri|version``)."""
    return profile.split("|", 1)[0]


def _has_profile(profiles: List[str], expected: str) -> bool:
    """Accepte les canonicals FR Core versionnés et non versionnés."""
    return any(_canonical_uri(profile) == expected for profile in profiles)


class FHIRToLocationConverter:
    """Convertit des ressources FHIR Location vers les modèles de structure."""

    def __init__(self, session: Session, ej: EntiteJuridique, resource_map: Optional[Dict[str, int]] = None):
        self.session = session
        self.ej = ej
        self.resource_map = resource_map if resource_map is not None else {}

    def convert_location(self, fhir_location: Dict[str, Any]) -> Any:
        """
        Convertit une ressource FHIR Location vers le modèle de structure approprié.

        Depuis FRCore 2.2.0, seuls les lieux physiques (UH, Chambre, Lit) sont des
        ressources Location — EG/Pole/Service/UF/UAC sont désormais des Organization
        (voir FHIRToOrganizationConverter). Le type est déterminé en priorité par
        `Location.type` (code UH/CHAMB/LIT, conforme au profil), avec un solution de
        repli sur l'ancien mapping physicalType (bu/wi/wa/lv/ro/bd) pour la lecture de
        ressources produites par une version antérieure de cet export.
        """
        name = fhir_location.get("name", "")
        status = fhir_location.get("status") or "active"
        identifiers = self._extract_identifiers(fhir_location)
        description = fhir_location.get("description")

        # Extraire le parent si présent
        part_of = fhir_location.get("partOf")
        parent_ref = part_of.get("reference") if part_of else None

        # Extraire identifier pour entité (NOT NULL required)
        identifier = fhir_location.get("id") or (identifiers[0]["value"] if identifiers else name.replace(" ", "_").upper())

        location_kind = self._extract_location_kind(fhir_location)

        if location_kind == "UH":
            # UH est désormais partOf une Organization UF (pas une autre Location)
            parent_id = self._resolve_parent_id(parent_ref, UniteFonctionnelle)
            if parent_id is None:
                raise FHIRImportError("UH sans parent UF résoluble")
            uh = self.session.exec(select(UniteHebergement).where(UniteHebergement.identifier == identifier)).first()
            if uh is None:
                uh = UniteHebergement(identifier=identifier, unite_fonctionnelle_id=parent_id)
            uh.name, uh.unite_fonctionnelle_id, uh.description, uh.status = name, parent_id, description, status
            self.session.add(uh)
            self.session.commit()
            self.session.refresh(uh)
            return uh

        elif location_kind == "CHAMB":
            parent_id = self._resolve_parent_id(parent_ref, UniteHebergement)
            if parent_id is None:
                raise FHIRImportError("Chambre sans parent UH résoluble")
            chambre = self.session.exec(select(Chambre).where(Chambre.identifier == identifier)).first()
            if chambre is None:
                chambre = Chambre(identifier=identifier, unite_hebergement_id=parent_id)
            chambre.name = name
            chambre.physical_type = LocationPhysicalType.RO
            chambre.type_chambre = self._extract_extension_code(
                fhir_location, f"{FRCORE_PROFILES['location'].rsplit('/StructureDefinition', 1)[0]}/StructureDefinition/fr-core-location-type-chambre"
            )
            chambre.unite_hebergement_id, chambre.description, chambre.status = parent_id, description, status
            self.session.add(chambre)
            self.session.commit()
            self.session.refresh(chambre)
            return chambre

        elif location_kind == "LIT":
            parent_id = self._resolve_parent_id(parent_ref, Chambre)
            if parent_id is None:
                raise FHIRImportError("Lit sans parent Chambre résoluble")
            lit = self.session.exec(select(Lit).where(Lit.identifier == identifier)).first()
            if lit is None:
                lit = Lit(identifier=identifier, chambre_id=parent_id)
            lit.name, lit.physical_type = name, LocationPhysicalType.BD
            lit.chambre_id, lit.description, lit.status = parent_id, description, status
            self.session.add(lit)
            self.session.commit()
            self.session.refresh(lit)
            return lit

        else:
            raise FHIRImportError(f"Type de Location non supporté (attendu UH/CHAMB/LIT): {location_kind}")

    def _extract_location_kind(self, fhir_location: Dict[str, Any]) -> Optional[str]:
        """Détermine UH/CHAMB/LIT depuis Location.type (conforme FRCore 2.2.0), avec
        solution de repli sur l'ancien physicalType (bu/wi/wa/lv/ro/bd) pour la lecture
        de ressources produites avant cette mise en conformité."""
        for type_cc in fhir_location.get("type", []) or []:
            for coding in type_cc.get("coding", []):
                code = (coding.get("code") or "").upper()
                if code in ("UH", "CHAMB", "LIT"):
                    return code
        # Solution de repli : ancien mapping physicalType
        physical_type = self._extract_physical_type(fhir_location)
        legacy_map = {
            LocationPhysicalType.LV: "UH",
            LocationPhysicalType.RO: "CHAMB",
            LocationPhysicalType.BD: "LIT",
        }
        return legacy_map.get(physical_type)

    def _extract_extension_code(self, resource: Dict[str, Any], extension_url: str) -> Optional[str]:
        """Extrait le `code` d'une extension valueCoding par son URL."""
        for ext in resource.get("extension", []) or []:
            if ext.get("url") == extension_url:
                coding = ext.get("valueCoding") or {}
                return coding.get("code")
        return None

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
        """Résout une référence FHIR par id logique, map du bundle ou identifiant métier."""
        if not parent_ref:
            return None
        parts = parent_ref.rsplit("/", 1)
        if len(parts) != 2:
            return None
        identifier = parts[1]
        parent = self.session.exec(
            select(parent_model).where(parent_model.identifier == identifier)
        ).first()
        if parent:
            return parent.id
        try:
            return int(identifier)
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


class FHIRToOrganizationConverter:
    """Convertit des ressources FHIR Organization vers les modèles de structure
    administrative (EG, Pôle, Service, UF, UAC) — depuis FRCore 2.2.0, ces niveaux
    sont des Organization, seuls UH/Chambre/Lit restent des Location (voir
    FHIRToLocationConverter). La création d'EntiteJuridique elle-même n'est pas
    gérée ici : l'EJ est le contexte racine déjà résolu par l'appelant.
    """

    def __init__(self, session: Session, ej: EntiteJuridique, resource_map: Optional[Dict[str, int]] = None):
        self.session = session
        self.ej = ej
        self.resource_map = resource_map if resource_map is not None else {}

    def convert_organization(self, fhir_organization: Dict[str, Any]) -> Any:
        """Dispatch par `meta.profile` (FRCoreOrganizationEtablissementProfile /
        FRCoreOrganizationUFProfile / FRCoreOrganizationUACProfile), avec une
        heuristique de profondeur pour Pôle/Service qui n'ont plus de profil dédié
        (le type du parent réel en base détermine s'il s'agit d'un Pôle — enfant
        d'EG — ou d'un Service — enfant de Pôle)."""
        profiles = (fhir_organization.get("meta") or {}).get("profile", [])
        name = fhir_organization.get("name", "")
        status = "active" if fhir_organization.get("active", True) else "inactive"
        identifiers = fhir_organization.get("identifier", []) or []
        identifier = fhir_organization.get("id") or (identifiers[0].get("value") if identifiers else name.replace(" ", "_").upper())
        part_of = fhir_organization.get("partOf")
        parent_ref = part_of.get("reference") if part_of else None

        if _has_profile(profiles, FRCORE_PROFILES["organization_etablissement"]):
            type_code = None
            for type_cc in fhir_organization.get("type", []) or []:
                for coding in type_cc.get("coding", []):
                    type_code = coding.get("code")
            if type_code in {"GEOGRAPHICAL-ENTITY", "EG"}:
                eg = self.session.exec(select(EntiteGeographique).where(EntiteGeographique.identifier == identifier)).first()
                if eg is None:
                    eg = EntiteGeographique(identifier=identifier, entite_juridique_id=self.ej.id)
                eg.name = name
                eg.finess = self._extract_identifier_value(fhir_organization, "FINEG") or "999999999"
                eg.entite_juridique_id, eg.status = self.ej.id, LocationStatus(status)
                self.session.add(eg)
                self.session.commit()
                self.session.refresh(eg)
                return eg
            if type_code in {"LEGAL-ENTITY", "EJ"}:
                return self.ej
            raise FHIRImportError(f"Type d'établissement non supporté à l'import: {type_code}")

        if _has_profile(profiles, FRCORE_PROFILES["organization_uf"]):
            parent_id = self._resolve_parent_id(parent_ref, Service)
            if parent_id is None:
                raise FHIRImportError("UF sans parent Service résoluble")
            uf = self.session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == identifier)).first()
            if uf is None:
                uf = UniteFonctionnelle(identifier=identifier, service_id=parent_id)
            uf.name, uf.service_id, uf.status = name, parent_id, status
            self.session.add(uf)
            self.session.commit()
            self.session.refresh(uf)
            return uf

        if _has_profile(profiles, FRCORE_PROFILES["organization_uac"]):
            parent_id = self._resolve_parent_id(parent_ref, UniteFonctionnelle)
            if parent_id is None:
                raise FHIRImportError("UAC sans parent UF résoluble")
            uac = self.session.exec(select(UniteActivite).where(UniteActivite.identifier == identifier)).first()
            if uac is None:
                uac = UniteActivite(identifier=identifier, unite_fonctionnelle_id=parent_id)
            uac.name, uac.unite_fonctionnelle_id, uac.status = name, parent_id, status
            self.session.add(uac)
            self.session.commit()
            self.session.refresh(uac)
            return uac

        if _has_profile(profiles, FRCORE_PROFILES["organization"]):
            # Pôle ou Service : plus de profil dédié depuis FRCore 2.2.0, distingués
            # par le type du parent réel en base (EG -> Pôle, Pôle -> Service).
            parent_id = self._resolve_parent_id(parent_ref, EntiteGeographique)
            parent_eg = self.session.get(EntiteGeographique, parent_id) if parent_id else None
            if parent_eg:
                pole = self.session.exec(select(Pole).where(Pole.identifier == identifier)).first()
                if pole is None:
                    pole = Pole(identifier=identifier, entite_geo_id=parent_eg.id)
                pole.name, pole.entite_geo_id, pole.status = name, parent_eg.id, status
                self.session.add(pole)
                self.session.commit()
                self.session.refresh(pole)
                return pole
            parent_id = self._resolve_parent_id(parent_ref, Pole)
            parent_pole = self.session.get(Pole, parent_id) if parent_id else None
            if parent_pole:
                service = self.session.exec(select(Service).where(Service.identifier == identifier)).first()
                if service is None:
                    service = Service(identifier=identifier, service_type="MCO", pole_id=parent_pole.id)
                service.name, service.pole_id, service.status = name, parent_pole.id, status
                self.session.add(service)
                self.session.commit()
                self.session.refresh(service)
                return service
            raise FHIRImportError("Organization générique (Pôle/Service) sans parent EG/Pôle résoluble")

        raise FHIRImportError(f"Profil Organization non reconnu à l'import: {profiles}")

    def _extract_identifier_value(self, fhir_organization: Dict[str, Any], type_code: str) -> Optional[str]:
        for ident in fhir_organization.get("identifier", []) or []:
            coding = (ident.get("type") or {}).get("coding", [])
            if any(c.get("code") == type_code for c in coding):
                return ident.get("value")
        return None

    def _extract_parent_numeric_id(self, parent_ref: Optional[str]) -> Optional[int]:
        if not parent_ref:
            return None
        parts = parent_ref.split("/")
        if len(parts) != 2:
            return None
        try:
            return int(parts[1])
        except ValueError:
            return None

    def _resolve_parent_id(self, parent_ref: Optional[str], parent_model) -> Optional[int]:
        if not parent_ref:
            return None
        identifier = parent_ref.rsplit("/", 1)[-1]
        parent = self.session.exec(select(parent_model).where(parent_model.identifier == identifier)).first()
        if parent:
            return parent.id
        return self._extract_parent_numeric_id(parent_ref)


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
            gender=gender,
            entite_juridique_id=self.ej.id,
            ght_context_id=self.ej.ght_context_id
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
            dossier_type="HOSPITALISE",
            entite_juridique_id=self.ej.id
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
        
        # Extraire le médecin responsable depuis participant[ATND]
        medecin_responsable_id = self._extract_medecin_from_participants(fhir_encounter)
        
        # Créer le mouvement
        mouvement = Mouvement(
            mouvement_seq=mouvement_seq,
            venue_id=venue.id,
            type=type_mouvement,
            when=date_debut or datetime.now(),
            end_time=date_fin,
            status=self._map_status(status),
            medecin_responsable_id=medecin_responsable_id
        )
        
        self.session.add(mouvement)
        self.session.commit()
        self.session.refresh(mouvement)
        
        # Si un médecin a été trouvé et que le dossier n'en a pas encore, l'assigner aussi au dossier
        if medecin_responsable_id and not dossier.medecin_responsable_id:
            dossier.medecin_responsable_id = medecin_responsable_id
            self.session.add(dossier)
            self.session.commit()
        
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

    def _extract_medecin_from_participants(self, fhir_encounter: Dict[str, Any]) -> Optional[int]:
        """
        Extrait le médecin responsable depuis Encounter.participant[ATND].
        
        Recherche un participant avec type.coding.code = "ATND" (Attender),
        extrait la référence vers Practitioner, et crée/récupère le MedecinResponsable.
        
        Returns:
            ID du MedecinResponsable ou None si non trouvé
        """
        participants = fhir_encounter.get("participant", [])
        
        for participant in participants:
            # Vérifier si c'est un ATND (Attender = médecin responsable)
            types = participant.get("type", [])
            is_attender = False
            
            for type_item in types:
                codings = type_item.get("coding", [])
                for coding in codings:
                    if coding.get("code") == "ATND":
                        is_attender = True
                        break
                if is_attender:
                    break
            
            if not is_attender:
                continue
            
            # Récupérer la référence vers le Practitioner
            individual = participant.get("individual", {})
            practitioner_ref = individual.get("reference", "")
            
            if not practitioner_ref:
                # Pas de référence, peut-être juste un display
                display = individual.get("display", "")
                if display:
                    # Essayer de parser le display pour extraire le nom
                    # Format attendu: "Dr KENNOUCHE Moussa Samir" ou "KENNOUCHE^Moussa Samir"
                    medecin_data = self._parse_practitioner_display(display)
                    if medecin_data:
                        medecin = get_or_create_medecin(self.session, medecin_data)
                        return medecin.id if medecin else None
                continue
            
            # Essayer de résoudre la référence dans le bundle
            practitioner = self._resolve_practitioner_reference(practitioner_ref, fhir_encounter)
            
            if practitioner:
                medecin_data = self._extract_medecin_from_practitioner(practitioner)
                if medecin_data:
                    medecin = get_or_create_medecin(self.session, medecin_data)
                    return medecin.id if medecin else None
        
        return None
    
    def _resolve_practitioner_reference(self, reference: str, encounter: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Résout une référence vers un Practitioner dans le bundle ou la base de données.
        
        Args:
            reference: Référence FHIR (ex: "Practitioner/pract-123" ou "#pract-1")
            encounter: Ressource Encounter contenant potentiellement le Practitioner en contained
            
        Returns:
            Ressource Practitioner ou None
        """
        # Vérifier si c'est une référence contained (commence par #)
        if reference.startswith("#"):
            contained_id = reference[1:]
            contained_resources = encounter.get("contained", [])
            
            for resource in contained_resources:
                if resource.get("id") == contained_id and resource.get("resourceType") == "Practitioner":
                    return resource
        
        # Sinon, essayer de trouver dans le bundle (via resource_map)
        # Note: Dans un vrai bundle, il faudrait chercher dans bundle.entry
        # Pour l'instant, on ne supporte que les contained resources
        
        return None
    
    def _extract_medecin_from_practitioner(self, practitioner: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extrait les données médecin depuis une ressource FHIR Practitioner.
        
        Args:
            practitioner: Ressource FHIR Practitioner
            
        Returns:
            Dict avec rpps, adeli, family_name, given_name, etc.
        """
        medecin_data = {}
        
        # Extraire les identifiants (RPPS/ADELI)
        identifiers = practitioner.get("identifier", [])
        for identifier in identifiers:
            system = identifier.get("system", "")
            value = identifier.get("value", "")
            
            if not value:
                continue
            
            # RPPS: 11 chiffres
            if "rpps" in system.lower() or (value.isdigit() and len(value) == 11):
                medecin_data["rpps"] = value
            # ADELI: 9 chiffres
            elif "adeli" in system.lower() or (value.isdigit() and len(value) == 9):
                medecin_data["adeli"] = value
        
        # Extraire le nom
        names = practitioner.get("name", [])
        if names:
            name = names[0]  # Prendre le premier nom
            medecin_data["family_name"] = name.get("family", "")
            given_names = name.get("given", [])
            if given_names:
                medecin_data["given_name"] = " ".join(given_names)
            medecin_data["prefix"] = " ".join(name.get("prefix", []))
            medecin_data["suffix"] = " ".join(name.get("suffix", []))
        
        # Extraire la spécialité
        qualifications = practitioner.get("qualification", [])
        if qualifications:
            qual = qualifications[0]
            code = qual.get("code", {})
            codings = code.get("coding", [])
            if codings:
                medecin_data["specialty"] = codings[0].get("display", "")
        
        # Vérifier qu'on a au moins un identifiant ou un nom
        if not (medecin_data.get("rpps") or medecin_data.get("adeli") or medecin_data.get("family_name")):
            return None
        
        return medecin_data
    
    def _parse_practitioner_display(self, display: str) -> Optional[Dict[str, Any]]:
        """
        Parse un display de Practitioner pour extraire les données.
        
        Formats supportés:
        - "Dr KENNOUCHE Moussa Samir"
        - "KENNOUCHE^Moussa Samir"
        - "KENNOUCHE Moussa Samir"
        
        Args:
            display: Chaîne de caractères à parser
            
        Returns:
            Dict avec family_name, given_name, prefix ou None
        """
        if not display:
            return None
        
        medecin_data = {}
        
        # Format XCN: FAMILY^GIVEN
        if "^" in display:
            parts = display.split("^")
            if len(parts) >= 2:
                medecin_data["family_name"] = parts[0].strip()
                medecin_data["given_name"] = parts[1].strip()
            return medecin_data if medecin_data else None
        
        # Format texte: "Dr FAMILY GIVEN" ou "FAMILY GIVEN"
        parts = display.strip().split()
        if not parts:
            return None
        
        # Extraire le préfixe (Dr, Pr, etc.)
        if parts[0] in ["Dr", "Pr", "Prof", "Docteur", "Professeur"]:
            medecin_data["prefix"] = parts[0]
            parts = parts[1:]
        
        if not parts:
            return None
        
        # Le premier mot est le nom de famille, le reste est le prénom
        medecin_data["family_name"] = parts[0]
        if len(parts) > 1:
            medecin_data["given_name"] = " ".join(parts[1:])
        
        return medecin_data if medecin_data else None

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


class FHIRToPractitionerConverter:
    """Convertit des ressources FHIR Practitioner vers le modèle MedecinResponsable."""

    def __init__(self, session: Session):
        self.session = session

    def convert_practitioner(self, fhir_practitioner: Dict[str, Any]) -> Optional[MedecinResponsable]:
        """
        Convertit une ressource FHIR Practitioner vers MedecinResponsable, en réutilisant
        `get_or_create_medecin` (upsert par RPPS puis ADELI puis nom complet) partagé avec
        l'extraction depuis PV1-7 côté HL7v2.
        """
        rpps = None
        adeli = None
        for identifier in fhir_practitioner.get("identifier", []):
            system = identifier.get("system", "")
            value = identifier.get("value")
            if not value:
                continue
            if "1.2.250.1.71.4.2.1.1" in system:
                adeli = value
            elif "1.2.250.1.71.4.2.1" in system:
                rpps = value

        names = fhir_practitioner.get("name", [])
        name = names[0] if names else {}
        given = name.get("given", [])
        telecoms = fhir_practitioner.get("telecom", [])
        phone = next((t.get("value") for t in telecoms if t.get("system") == "phone"), None)
        email = next((t.get("value") for t in telecoms if t.get("system") == "email"), None)

        medecin_data = {
            "rpps": rpps,
            "adeli": adeli,
            "family_name": name.get("family"),
            "given_name": given[0] if given else None,
            "middle_name": given[1] if len(given) > 1 else None,
            "prefix": (name.get("prefix") or [None])[0],
            "suffix": (name.get("suffix") or [None])[0],
            "phone": phone,
            "email": email,
            "active": fhir_practitioner.get("active", True),
        }
        medecin_data = {k: v for k, v in medecin_data.items() if v not in (None, "")}

        return get_or_create_medecin(self.session, medecin_data)


class FHIRBundleImporter:
    """Importe un bundle FHIR complet."""

    def __init__(self, session: Session, ej: EntiteJuridique):
        self.session = session
        self.ej = ej
        # resource_map: maps bundle-local ids and references to DB ids
        self.resource_map: Dict[str, int] = {}
        self.location_converter = FHIRToLocationConverter(session, ej, self.resource_map)
        self.organization_converter = FHIRToOrganizationConverter(session, ej, self.resource_map)
        self.patient_converter = FHIRToPatientConverter(session, ej)
        self.encounter_converter = FHIRToEncounterConverter(session, resource_map=self.resource_map)
        self.practitioner_converter = FHIRToPractitionerConverter(session)

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
            "encounters": 0,
            "practitioners": 0,
            "organizations": 0
        }
        
        # La hiérarchie FRCore doit être importée des parents vers les enfants.
        # Les anciens imports Location-first rendaient les références partOf
        # non résolubles pour les Organization/UF et les UH.
        organization_rank = {
            FRCORE_PROFILES["organization_etablissement"]: 0,
            FRCORE_PROFILES["organization"]: 1,
            FRCORE_PROFILES["organization_uf"]: 2,
            FRCORE_PROFILES["organization_uac"]: 3,
        }
        organizations = [entry for entry in entries if (entry.get("resource") or {}).get("resourceType") == "Organization"]
        organizations.sort(key=lambda entry: min(
            (organization_rank.get(_canonical_uri(profile), 99) for profile in ((entry.get("resource") or {}).get("meta") or {}).get("profile", [])),
            default=99,
        ))
        ordered_entries = organizations + [
            entry for entry in entries if (entry.get("resource") or {}).get("resourceType") != "Organization"
        ]
        for entry in ordered_entries:
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

                elif resource_type == "Practitioner":
                    medecin = self.practitioner_converter.convert_practitioner(resource)
                    res_id = resource.get('id')
                    if res_id and medecin is not None:
                        self.resource_map[res_id] = medecin.id
                        self.resource_map[f"Practitioner/{res_id}"] = medecin.id
                    results["practitioners"] += 1
                    results["imported"] += 1

                elif resource_type == "Organization":
                    entity = self.organization_converter.convert_organization(resource)
                    res_id = resource.get('id')
                    identifier = next((item.get("value") for item in resource.get("identifier", []) if item.get("value")), None)
                    if hasattr(entity, "id"):
                        if res_id:
                            self.resource_map[res_id] = entity.id
                            self.resource_map[f"Organization/{res_id}"] = entity.id
                        if identifier:
                            self.resource_map[f"Organization/{identifier}"] = entity.id
                    results["organizations"] += 1
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
        
        # Profils FR Core 2.2.0 attendus par type de ressource.  Les anciens
        # URI ``interopsante.org`` ne correspondent plus aux bundles émis par
        # l'application et créaient des avertissements trompeurs à chaque
        # import valide.
        expected_profiles = {
            "Location": [FRCORE_PROFILES["location"]],
            "Organization": [
                FRCORE_PROFILES["organization"],
                FRCORE_PROFILES["organization_etablissement"],
                FRCORE_PROFILES["organization_uf"],
                FRCORE_PROFILES["organization_uac"],
            ],
        }
        
        if resource_type in expected_profiles:
            expected = expected_profiles[resource_type]
            # Vérifier qu'au moins un profil FRCore est présent
            has_fr_profile = any(_has_profile(profiles, profile) for profile in expected)
            
            if not has_fr_profile:
                # Ne pas lever d'erreur, juste un avertissement dans les logs
                print(f"⚠️  Ressource {resource_type} sans profil FRCore. Profils attendus: {expected}, profils trouvés: {profiles}")
