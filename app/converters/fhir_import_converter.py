"""
Convertisseurs FHIR → Models internes pour l'import.

Ce module fournit les classes pour convertir des ressources FHIR R4
vers les modèles internes de MedDataBridge.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlmodel import Session

from app.models_structure_fhir import EntiteJuridique
from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit, LocationPhysicalType
)
from app.models import Patient, Dossier, Mouvement
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

    def _extract_physical_type(self, fhir_location: Dict[str, Any]) -> Optional[str]:
        """Extrait le type physique depuis physicalType."""
        physical_type = fhir_location.get("physicalType")
        if not physical_type:
            return None
        
        coding = physical_type.get("coding", [])
        if coding:
            return coding[0].get("code")
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
        
        # TODO: Implémenter une vraie résolution depuis la base
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
        # Mapping basique
        if "finess" in system.lower():
            return IdentifierType.FINESS.value
        elif "ej" in system.lower():
            return IdentifierType.EJ.value
        elif "eg" in system.lower():
            return IdentifierType.EG.value
        else:
            return IdentifierType.EG.value  # Par défaut


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
        """Parse un sexe FHIR."""
        if not gender:
            return None
        
        gender_map = {
            "male": "M",
            "female": "F",
            "other": "O",
            "unknown": "I"
        }
        return gender_map.get(gender.lower(), "I")

    def _map_system_to_type(self, system: str) -> str:
        """Mappe un system FHIR vers un IdentifierType."""
        if "ipp" in system.lower():
            return IdentifierType.IPP.value
        elif "ins" in system.lower():
            return IdentifierType.INS.value
        else:
            return IdentifierType.IPP.value


class FHIRToEncounterConverter:
    """Convertit des ressources FHIR Encounter vers les modèles Mouvement."""

    def __init__(self, session: Session):
        self.session = session

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
        dossier = self.session.query(Dossier).filter(
            Dossier.patient_id == patient_id
        ).first()
        
        if not dossier:
            raise FHIRImportError(f"Aucun dossier trouvé pour le patient {patient_id}")
        
        # Créer le mouvement
        mouvement = Mouvement(
            dossier_id=dossier.id,
            type=type_mouvement,
            date_debut=date_debut,
            date_fin=date_fin,
            statut=self._map_status(status)
        )
        
        self.session.add(mouvement)
        self.session.commit()
        self.session.refresh(mouvement)
        
        # Ajouter l'identifiant NDA
        # Note: Le modèle Identifier n'a pas de foreign key pour Mouvement
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
        
        parts = reference.split("/")
        if len(parts) != 2:
            return None
        
        try:
            return int(parts[1])
        except ValueError:
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
        self.location_converter = FHIRToLocationConverter(session, ej)
        self.patient_converter = FHIRToPatientConverter(session, ej)
        self.encounter_converter = FHIRToEncounterConverter(session)

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
            
            try:
                if resource_type == "Location":
                    self.location_converter.convert_location(resource)
                    results["locations"] += 1
                    results["imported"] += 1
                    
                elif resource_type == "Patient":
                    self.patient_converter.convert_patient(resource)
                    results["patients"] += 1
                    results["imported"] += 1
                    
                elif resource_type == "Encounter":
                    self.encounter_converter.convert_encounter(resource)
                    results["encounters"] += 1
                    results["imported"] += 1
                    
            except Exception as e:
                results["errors"].append({
                    "resourceType": resource_type,
                    "error": str(e)
                })
        
        return results
