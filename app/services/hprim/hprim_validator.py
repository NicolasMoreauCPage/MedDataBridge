# app/services/hprim/hprim_validator.py
"""
Service de validation HPRIM XML
Validation XSD, formats et nomenclatures
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from xmlschema import XMLSchema, XMLSchemaValidationError
from lxml import etree

from app.hprim_models import (
    HprimActeCCAM, HprimActeNGAP, HprimActeLPP, HprimActeUCD,
    HprimProfessionnel, HprimPatient, HprimEnteteMessage
)

logger = logging.getLogger(__name__)


class HprimValidationError(Exception):
    """Erreur de validation HPRIM"""
    def __init__(self, code: str, message: str, field: Optional[str] = None):
        self.code = code
        self.message = message
        self.field = field
        super().__init__(f"{code}: {message}")


class HprimValidator:
    """Validateur HPRIM XML et données"""

    # Schémas XSD
    SCHEMAS = {
        'evenements_serveur_actes': 'msgEvenementsServeurActes2_4.xsd',
        'acquittements_serveur_actes': 'msgAcquittementsServeurActes2_4.xsd',
        'evenements_frais_divers': 'msgEvenementsFraisDivers2_4.xsd',
        'acquittements_frais_divers': 'msgAcquittementsFraisDivers2_4.xsd',
        'evenements_pmsi': 'msgEvenementsPmsi2_4.xsd',
        'acquittements_pmsi': 'msgAcquittementsPmsi2_4.xsd',
        'evenements_serveur_etats_patient': 'msgEvenementsServeurEtatsPatient2_4.xsd',
        'acquittements_serveur_etats_patient': 'msgAcquittementsServeurEtatsPatient2_4.xsd',
    }

    # Mapping des éléments racine vers les noms de schémas internes
    ROOT_TO_SCHEMA = {
        'evenementsServeurActes': 'evenements_serveur_actes',
        'acquittementsServeurActes': 'acquittements_serveur_actes',
        'evenementsFraisDivers': 'evenements_frais_divers',
        'acquittementsFraisDivers': 'acquittements_frais_divers',
        'evenementsPmsi': 'evenements_pmsi',
        'acquittementsPmsi': 'acquittements_pmsi',
        'evenementsServeurEtatsPatient': 'evenements_serveur_etats_patient',
        'acquittementsServeurEtatsPatient': 'acquittements_serveur_etats_patient',
    }

    # Patterns de validation
    PATTERNS = {
        'ccam': re.compile(r'^[A-Z]{4}\d{3}$'),
        'ccam_pmsi': re.compile(r'^\d{2}$'),
        'numero2': re.compile(r'^\d{1,2}$'),
        'numero5': re.compile(r'^\d{1,5}$'),
        'numero13': re.compile(r'^\d{13}$'),
        'numero20': re.compile(r'^\d{1,20}$'),
        'finess': re.compile(r'^\d{9}$'),
        'rpps': re.compile(r'^\d{11}$'),
        'nom1': re.compile(r'^[A-Za-z0-9\-_]$'),
        'nom10': re.compile(r'^[A-Za-z0-9\-_]{1,10}$'),
        'nom17': re.compile(r'^[A-Za-z0-9\-_]{1,17}$'),
        'nom21': re.compile(r'^[A-Za-z0-9\-_]{1,21}$'),
        'nom120': re.compile(r'^[A-Za-z0-9\-_]{1,120}$'),
        'texte35': re.compile(r'^.{1,35}$'),
        'texte80': re.compile(r'^.{1,80}$'),
        'texte120': re.compile(r'^.{1,120}$'),
    }

    def __init__(self, schemas_path: Optional[Path] = None):
        # Préférence: dossiers officiels HPRIM dans docs/HPRIM_XML
        default_docs_path = Path(__file__).resolve().parents[3] / 'docs' / 'HPRIM_XML' / 'hprimXmlVs2_4' / 'schema'
        default_static_path = Path(__file__).parent.parent.parent / 'static' / 'schemas' / 'hprim'
        if schemas_path is not None:
            self.schemas_path = schemas_path
        else:
            self.schemas_path = default_docs_path if default_docs_path.exists() else default_static_path
        self._schemas: Dict[str, XMLSchema] = {}
        # Ne pas charger les schémas au démarrage pour accélérer l'initialisation
        # self._load_schemas()

    def _load_schema(self, schema_name: str) -> bool:
        """Charge un schéma spécifique"""
        if schema_name not in self.SCHEMAS:
            return False

        filename = self.SCHEMAS[schema_name]
        schema_path = self.schemas_path / filename

        if schema_path.exists():
            try:
                self._schemas[schema_name] = XMLSchema(str(schema_path))
                logger.info(f"Schéma chargé: {schema_name} -> {filename}")
                return True
            except Exception as e:
                logger.error(f"Erreur chargement schéma {schema_name}: {e}")
                return False
        else:
            logger.warning(f"Schéma non trouvé: {schema_path}")
            return False

    def _load_schemas(self):
        """Charge les schémas XSD"""
        for name, filename in self.SCHEMAS.items():
            schema_path = self.schemas_path / filename
            if schema_path.exists():
                try:
                    self._schemas[name] = XMLSchema(str(schema_path))
                    logger.info(f"Schéma chargé: {name} -> {filename}")
                except Exception as e:
                    logger.error(f"Erreur chargement schéma {name}: {e}")
            else:
                logger.warning(f"Schéma non trouvé: {schema_path}")

    def guess_schema_name(self, xml_string: str) -> Optional[str]:
        """Détermine le schéma à utiliser selon l'élément racine XML.

        Retourne le nom de schéma (clé de SCHEMAS) ou None si indéterminé.
        """
        try:
            # Parser sans valider, récupérer le nom local (sans namespace)
            root = etree.fromstring(xml_string.encode('iso-8859-1'))
            # localname: séparer namespace si présent
            tag = root.tag
            if '}' in tag:
                local = tag.split('}', 1)[1]
            else:
                local = tag
            return self.ROOT_TO_SCHEMA.get(local)
        except Exception as e:
            logger.warning(f"Impossible de déterminer le schéma depuis le root: {e}")
            return None

    def validate_xml_string(self, xml_string: str, schema_name: str) -> Tuple[bool, List[str]]:
        """
        Valide une chaîne XML contre un schéma

        Args:
            xml_string: XML à valider
            schema_name: Nom du schéma dans SCHEMAS

        Returns:
            (is_valid, errors_list)
        """
        # Charger le schéma à la volée si nécessaire
        if schema_name not in self._schemas:
            loaded = self._load_schema(schema_name)
            if not loaded:
                return False, [f"Schéma {schema_name} non disponible ({self.schemas_path})"]

        try:
            # Parse XML
            xml_doc = etree.fromstring(xml_string.encode('iso-8859-1'))

            # Validation XSD
            self._schemas[schema_name].validate(xml_doc)

            return True, []

        except XMLSchemaValidationError as e:
            errors = [f"XSD Error: {e.message}"]
            return False, errors
        except etree.XMLSyntaxError as e:
            errors = [f"XML Syntax Error: {e.message}"]
            return False, errors
        except Exception as e:
            errors = [f"Validation Error: {str(e)}"]
            return False, errors

    def validate_acte_ccam(self, acte: HprimActeCCAM) -> List[HprimValidationError]:
        """Valide un acte CCAM"""
        errors = []

        # Code acte
        if not self.PATTERNS['ccam'].match(acte.code_acte):
            errors.append(HprimValidationError(
                "CCAM_FORMAT_001",
                f"Code acte CCAM invalide: {acte.code_acte} (doit être AAAA999)",
                "code_acte"
            ))

        # Extension PMSI
        if acte.code_acte_extension_pmsi and not self.PATTERNS['ccam_pmsi'].match(acte.code_acte_extension_pmsi):
            errors.append(HprimValidationError(
                "CCAM_PMSI_001",
                f"Extension PMSI invalide: {acte.code_acte_extension_pmsi} (doit être 2 chiffres)",
                "code_acte_extension_pmsi"
            ))

        # Code activité
        if not self.PATTERNS['numero2'].match(acte.code_activite):
            errors.append(HprimValidationError(
                "CCAM_ACTIVITY_001",
                f"Code activité invalide: {acte.code_activite} (doit être 1-2 chiffres)",
                "code_activite"
            ))

        # Code phase
        if not self.PATTERNS['numero2'].match(acte.code_phase):
            errors.append(HprimValidationError(
                "CCAM_PHASE_001",
                f"Code phase invalide: {acte.code_phase} (doit être 1-2 chiffres)",
                "code_phase"
            ))

        # Quantité
        if acte.quantite < 1:
            errors.append(HprimValidationError(
                "CCAM_QUANTITY_001",
                f"Quantité invalide: {acte.quantite} (doit être >= 1)",
                "quantite"
            ))

        # Modificateurs
        for mod in acte.modificateurs:
            if not self.PATTERNS['nom1'].match(mod.code):
                errors.append(HprimValidationError(
                    "CCAM_MOD_001",
                    f"Modificateur invalide: {mod.code} (doit être A-Z, 0-9)",
                    "modificateurs"
                ))

        # Exécutant RPPS
        if not self.PATTERNS['rpps'].match(acte.executant.numero_rpps):
            errors.append(HprimValidationError(
                "CCAM_RPPS_001",
                f"RPPS exécutant invalide: {acte.executant.numero_rpps} (doit être 11 chiffres)",
                "executant.numero_rpps"
            ))

        return errors

    def validate_acte_ngap(self, acte: HprimActeNGAP) -> List[HprimValidationError]:
        """Valide un acte NGAP"""
        errors = []

        # Lettre clé
        if not re.match(r'^[A-Z]$', acte.lettre_cle):
            errors.append(HprimValidationError(
                "NGAP_CLE_001",
                f"Lettre clé invalide: {acte.lettre_cle} (doit être A-Z)",
                "lettre_cle"
            ))

        # Coefficient
        if acte.coefficient <= 0:
            errors.append(HprimValidationError(
                "NGAP_COEF_001",
                f"Coefficient invalide: {acte.coefficient} (doit être > 0)",
                "coefficient"
            ))

        # Dénombrement
        if acte.denombrement and acte.denombrement < 1:
            errors.append(HprimValidationError(
                "NGAP_DENOM_001",
                f"Dénombrement invalide: {acte.denombrement} (doit être >= 1)",
                "denombrement"
            ))

        # Prestataire RPPS
        if not self.PATTERNS['rpps'].match(acte.prestataire.numero_rpps):
            errors.append(HprimValidationError(
                "NGAP_RPPS_001",
                f"RPPS prestataire invalide: {acte.prestataire.numero_rpps} (doit être 11 chiffres)",
                "prestataire.numero_rpps"
            ))

        return errors

    def validate_patient(self, patient: HprimPatient) -> List[HprimValidationError]:
        """Valide les données patient"""
        errors = []

        # Identifiant
        if not patient.identifiant_id or len(patient.identifiant_id) > 17:
            errors.append(HprimValidationError(
                "PATIENT_ID_001",
                f"Identifiant patient invalide: {patient.identifiant_id}",
                "identifiant_id"
            ))

        # Nom et prénom
        if not patient.nom or len(patient.nom) > 80:
            errors.append(HprimValidationError(
                "PATIENT_NOM_001",
                f"Nom patient invalide: {patient.nom}",
                "nom"
            ))

        if not patient.prenom or len(patient.prenom) > 80:
            errors.append(HprimValidationError(
                "PATIENT_PRENOM_001",
                f"Prénom patient invalide: {patient.prenom}",
                "prenom"
            ))

        # Date naissance (format YYYY-MM-DD)
        if patient.date_naissance:
            try:
                # Validation basique du format
                if not re.match(r'^\d{4}-\d{2}-\d{2}$', patient.date_naissance):
                    errors.append(HprimValidationError(
                        "PATIENT_NAISS_001",
                        f"Date naissance invalide: {patient.date_naissance} (format YYYY-MM-DD attendu)",
                        "date_naissance"
                    ))
            except:
                errors.append(HprimValidationError(
                    "PATIENT_NAISS_002",
                    f"Date naissance invalide: {patient.date_naissance}",
                    "date_naissance"
                ))

        return errors

    def validate_professionnel(self, prof: HprimProfessionnel) -> List[HprimValidationError]:
        """Valide les données professionnel"""
        errors = []

        # RPPS
        if not self.PATTERNS['rpps'].match(prof.numero_rpps):
            errors.append(HprimValidationError(
                "PROF_RPPS_001",
                f"RPPS invalide: {prof.numero_rpps} (doit être 11 chiffres)",
                "numero_rpps"
            ))

        # Nom et prénom
        if not prof.nom or len(prof.nom) > 80:
            errors.append(HprimValidationError(
                "PROF_NOM_001",
                f"Nom professionnel invalide: {prof.nom}",
                "nom"
            ))

        if not prof.prenom or len(prof.prenom) > 80:
            errors.append(HprimValidationError(
                "PROF_PRENOM_001",
                f"Prénom professionnel invalide: {prof.prenom}",
                "prenom"
            ))

        return errors

    def validate_entete_message(self, entete: HprimEnteteMessage) -> List[HprimValidationError]:
        """Valide l'en-tête de message"""
        errors = []

        # Émetteur et destinataire
        for field, label in [("emetteur_id", "Émetteur"), ("destinataire_id", "Destinataire")]:
            value = getattr(entete, field)
            if not value or len(value) > 17:
                errors.append(HprimValidationError(
                    f"HEADER_{field.upper()}_001",
                    f"{label} ID invalide: {value}",
                    field
                ))

        # Message ID
        if not entete.message_id or len(entete.message_id) > 17:
            errors.append(HprimValidationError(
                "HEADER_MSG_ID_001",
                f"Message ID invalide: {entete.message_id}",
                "message_id"
            ))

        return errors

    def validate_message_complet(self, message) -> List[HprimValidationError]:
        """Validation complète d'un message HPRIM"""
        errors = []

        # En-tête
        errors.extend(self.validate_entete_message(message.entete))

        # Patient
        errors.extend(self.validate_patient(message.patient))

        # Acteur
        errors.extend(self.validate_professionnel(message.acteur))

        # Actes selon le type
        for acte in message.actes_ccam:
            errors.extend(self.validate_acte_ccam(acte))

        for acte in message.actes_ngap:
            errors.extend(self.validate_acte_ngap(acte))

        return errors