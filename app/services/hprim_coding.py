"""Service de codage HPRIM/XML Santé.

Ce service implémente le standard HPRIM (Hospital - Patient - Résumé d'Intervention Médicale)
pour le codage et l'échange d'actes médicaux selon les spécifications françaises.
"""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime, date
from dataclasses import dataclass, field
from enum import Enum
import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom


class HprimMessageType(Enum):
    """Types de messages HPRIM."""
    ACTES_MEDICAUX = "actes_medicaux"
    ETAT_PATIENT = "etat_patient"
    FRAIS_DIVERS = "frais_divers"
    PMSI_MCO = "pmsi_mco"
    PMSI_SSR = "pmsi_ssr"
    PMSI_PSY = "pmsi_psy"
    PMSI_HAD = "pmsi_had"


class ActeType(Enum):
    """Types d'actes médicaux."""
    CCAM = "CCAM"
    NGAP = "NGAP"
    LPP = "LPP"
    UCD = "UCD"


@dataclass
class HprimActe:
    """Représentation d'un acte médical HPRIM."""
    code: str
    type_acte: ActeType
    date_execution: date
    quantite: int = 1
    coefficient: float = 1.0
    modificateurs: List[str] = field(default_factory=list)
    localisation: Optional[str] = None
    contexte: Optional[str] = None
    executant: Optional[str] = None
    prescripteur: Optional[str] = None
    montant: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HprimPatient:
    """Informations patient pour HPRIM."""
    numero_sejour: str
    ipp: Optional[str] = None
    iep: Optional[str] = None
    nom: Optional[str] = None
    prenom: Optional[str] = None
    date_naissance: Optional[date] = None
    sexe: Optional[str] = None
    uf: Optional[str] = None
    um: Optional[str] = None


@dataclass
class HprimMessage:
    """Message HPRIM complet."""
    id: str
    type_message: HprimMessageType
    etablissement: str
    patient: HprimPatient
    actes: List[HprimActe] = field(default_factory=list)
    date_creation: datetime = field(default_factory=datetime.now)
    version_hprim: str = "2.4"
    metadata: Dict[str, Any] = field(default_factory=dict)


class HprimXmlGenerator:
    """Générateur de messages XML HPRIM."""

    def __init__(self, version: str = "2.4"):
        self.version = version
        self.namespaces = {
            'hprim': 'http://www.interopsante.org/hprim/xml',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }

    def generate_actes_medicaux(self, message: HprimMessage) -> str:
        """Génère un message XML d'actes médicaux."""
        root = ET.Element("hprim:actes_medicaux", self.namespaces)
        root.set('version', self.version)

        # En-tête
        header = ET.SubElement(root, "hprim:entete")
        self._add_header_info(header, message)

        # Patient
        patient_elem = ET.SubElement(root, "hprim:patient")
        self._add_patient_info(patient_elem, message.patient)

        # Actes
        actes_elem = ET.SubElement(root, "hprim:actes")
        for acte in message.actes:
            acte_elem = ET.SubElement(actes_elem, "hprim:acte")
            self._add_acte_info(acte_elem, acte)

        return self._prettify_xml(root)

    def generate_etat_patient(self, message: HprimMessage) -> str:
        """Génère un message XML d'état patient."""
        root = ET.Element("hprim:etat_patient", self.namespaces)
        root.set('version', self.version)

        # En-tête
        header = ET.SubElement(root, "hprim:entete")
        self._add_header_info(header, message)

        # Patient
        patient_elem = ET.SubElement(root, "hprim:patient")
        self._add_patient_info(patient_elem, message.patient)

        # État patient (diagnostics, dépendance, etc.)
        etat_elem = ET.SubElement(root, "hprim:etat")
        # TODO: Implémenter selon spécifications

        return self._prettify_xml(root)

    def _add_header_info(self, header_elem: ET.Element, message: HprimMessage) -> None:
        """Ajoute les informations d'en-tête."""
        ET.SubElement(header_elem, "hprim:id_message").text = message.id
        ET.SubElement(header_elem, "hprim:type_message").text = message.type_message.value
        ET.SubElement(header_elem, "hprim:etablissement").text = message.etablissement
        ET.SubElement(header_elem, "hprim:date_creation").text = message.date_creation.isoformat()

    def _add_patient_info(self, patient_elem: ET.Element, patient: HprimPatient) -> None:
        """Ajoute les informations patient."""
        ET.SubElement(patient_elem, "hprim:numero_sejour").text = patient.numero_sejour

        if patient.ipp:
            ET.SubElement(patient_elem, "hprim:ipp").text = patient.ipp
        if patient.iep:
            ET.SubElement(patient_elem, "hprim:iep").text = patient.iep
        if patient.nom:
            ET.SubElement(patient_elem, "hprim:nom").text = patient.nom
        if patient.prenom:
            ET.SubElement(patient_elem, "hprim:prenom").text = patient.prenom
        if patient.date_naissance:
            ET.SubElement(patient_elem, "hprim:date_naissance").text = patient.date_naissance.isoformat()
        if patient.sexe:
            ET.SubElement(patient_elem, "hprim:sexe").text = patient.sexe
        if patient.uf:
            ET.SubElement(patient_elem, "hprim:uf").text = patient.uf
        if patient.um:
            ET.SubElement(patient_elem, "hprim:um").text = patient.um

    def _add_acte_info(self, acte_elem: ET.Element, acte: HprimActe) -> None:
        """Ajoute les informations d'un acte."""
        ET.SubElement(acte_elem, "hprim:code").text = acte.code
        ET.SubElement(acte_elem, "hprim:type_acte").text = acte.type_acte.value
        ET.SubElement(acte_elem, "hprim:date_execution").text = acte.date_execution.isoformat()
        ET.SubElement(acte_elem, "hprim:quantite").text = str(acte.quantite)
        ET.SubElement(acte_elem, "hprim:coefficient").text = str(acte.coefficient)

        if acte.modificateurs:
            mod_elem = ET.SubElement(acte_elem, "hprim:modificateurs")
            for mod in acte.modificateurs:
                ET.SubElement(mod_elem, "hprim:modificateur").text = mod

        if acte.localisation:
            ET.SubElement(acte_elem, "hprim:localisation").text = acte.localisation
        if acte.contexte:
            ET.SubElement(acte_elem, "hprim:contexte").text = acte.contexte
        if acte.executant:
            ET.SubElement(acte_elem, "hprim:executant").text = acte.executant
        if acte.prescripteur:
            ET.SubElement(acte_elem, "hprim:prescripteur").text = acte.prescripteur
        if acte.montant is not None:
            ET.SubElement(acte_elem, "hprim:montant").text = str(acte.montant)

    def _prettify_xml(self, elem: ET.Element) -> str:
        """Formate le XML pour une meilleure lisibilité."""
        rough_string = ET.tostring(elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")


class HprimXmlParser:
    """Parseur de messages XML HPRIM."""

    def __init__(self):
        self.namespaces = {'hprim': 'http://www.interopsante.org/hprim/xml'}

    def parse_actes_medicaux(self, xml_content: str) -> HprimMessage:
        """Parse un message XML d'actes médicaux."""
        root = ET.fromstring(xml_content)

        # Extraire l'en-tête
        header = root.find('.//hprim:entete', self.namespaces)
        message_id = header.find('hprim:id_message', self.namespaces).text
        etablissement = header.find('hprim:etablissement', self.namespaces).text

        # Extraire le patient
        patient_elem = root.find('.//hprim:patient', self.namespaces)
        patient = self._parse_patient(patient_elem)

        # Extraire les actes
        actes = []
        actes_elem = root.find('.//hprim:actes', self.namespaces)
        if actes_elem is not None:
            for acte_elem in actes_elem.findall('hprim:acte', self.namespaces):
                acte = self._parse_acte(acte_elem)
                actes.append(acte)

        return HprimMessage(
            id=message_id,
            type_message=HprimMessageType.ACTES_MEDICAUX,
            etablissement=etablissement,
            patient=patient,
            actes=actes
        )

    def _parse_patient(self, patient_elem: ET.Element) -> HprimPatient:
        """Parse les informations patient."""
        numero_sejour = patient_elem.find('hprim:numero_sejour', self.namespaces).text

        patient = HprimPatient(numero_sejour=numero_sejour)

        # Champs optionnels
        ipp_elem = patient_elem.find('hprim:ipp', self.namespaces)
        if ipp_elem is not None:
            patient.ipp = ipp_elem.text

        iep_elem = patient_elem.find('hprim:iep', self.namespaces)
        if iep_elem is not None:
            patient.iep = iep_elem.text

        nom_elem = patient_elem.find('hprim:nom', self.namespaces)
        if nom_elem is not None:
            patient.nom = nom_elem.text

        prenom_elem = patient_elem.find('hprim:prenom', self.namespaces)
        if prenom_elem is not None:
            patient.prenom = prenom_elem.text

        date_naissance_elem = patient_elem.find('hprim:date_naissance', self.namespaces)
        if date_naissance_elem is not None:
            patient.date_naissance = date.fromisoformat(date_naissance_elem.text)

        sexe_elem = patient_elem.find('hprim:sexe', self.namespaces)
        if sexe_elem is not None:
            patient.sexe = sexe_elem.text

        uf_elem = patient_elem.find('hprim:uf', self.namespaces)
        if uf_elem is not None:
            patient.uf = uf_elem.text

        um_elem = patient_elem.find('hprim:um', self.namespaces)
        if um_elem is not None:
            patient.um = um_elem.text

        return patient

    def _parse_acte(self, acte_elem: ET.Element) -> HprimActe:
        """Parse les informations d'un acte."""
        code = acte_elem.find('hprim:code', self.namespaces).text
        type_acte_str = acte_elem.find('hprim:type_acte', self.namespaces).text
        type_acte = ActeType(type_acte_str)

        date_execution_str = acte_elem.find('hprim:date_execution', self.namespaces).text
        date_execution = date.fromisoformat(date_execution_str)

        quantite_elem = acte_elem.find('hprim:quantite', self.namespaces)
        quantite = int(quantite_elem.text) if quantite_elem is not None else 1

        coefficient_elem = acte_elem.find('hprim:coefficient', self.namespaces)
        coefficient = float(coefficient_elem.text) if coefficient_elem is not None else 1.0

        acte = HprimActe(
            code=code,
            type_acte=type_acte,
            date_execution=date_execution,
            quantite=quantite,
            coefficient=coefficient
        )

        # Modificateurs
        mod_elem = acte_elem.find('hprim:modificateurs', self.namespaces)
        if mod_elem is not None:
            acte.modificateurs = [
                mod.text for mod in mod_elem.findall('hprim:modificateur', self.namespaces)
            ]

        # Champs optionnels
        localisation_elem = acte_elem.find('hprim:localisation', self.namespaces)
        if localisation_elem is not None:
            acte.localisation = localisation_elem.text

        contexte_elem = acte_elem.find('hprim:contexte', self.namespaces)
        if contexte_elem is not None:
            acte.contexte = contexte_elem.text

        executant_elem = acte_elem.find('hprim:executant', self.namespaces)
        if executant_elem is not None:
            acte.executant = executant_elem.text

        prescripteur_elem = acte_elem.find('hprim:prescripteur', self.namespaces)
        if prescripteur_elem is not None:
            acte.prescripteur = prescripteur_elem.text

        montant_elem = acte_elem.find('hprim:montant', self.namespaces)
        if montant_elem is not None:
            acte.montant = float(montant_elem.text)

        return acte


class HprimValidationService:
    """Service de validation des messages HPRIM."""

    def __init__(self):
        self.required_fields = {
            HprimMessageType.ACTES_MEDICAUX: [
                'id', 'etablissement', 'patient.numero_sejour'
            ]
        }

    def validate_message(self, message: HprimMessage) -> Dict[str, Any]:
        """
        Valide un message HPRIM.

        Args:
            message: Message HPRIM à valider

        Returns:
            Résultat de validation
        """
        errors = []
        warnings = []

        # Validation des champs requis
        required = self.required_fields.get(message.type_message, [])
        for field_path in required:
            if not self._check_required_field(message, field_path):
                errors.append(f"Champ requis manquant: {field_path}")

        # Validation spécifique par type de message
        if message.type_message == HprimMessageType.ACTES_MEDICAUX:
            self._validate_actes_medicaux(message, errors, warnings)

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def _check_required_field(self, message: HprimMessage, field_path: str) -> bool:
        """Vérifie si un champ requis est présent."""
        parts = field_path.split('.')
        current = message

        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
                if current is None:
                    return False
            else:
                return False

        return True

    def _validate_actes_medicaux(self, message: HprimMessage,
                                errors: List[str], warnings: List[str]) -> None:
        """Validation spécifique pour les actes médicaux."""
        if not message.actes:
            warnings.append("Aucun acte trouvé dans le message")

        for i, acte in enumerate(message.actes):
            # Validation du code d'acte selon le type
            if acte.type_acte == ActeType.CCAM and not acte.code.startswith(('A', 'B', 'C', 'D')):
                errors.append(f"Acte {i+1}: Code CCAM invalide: {acte.code}")

            # Validation de la date
            if acte.date_execution > date.today():
                errors.append(f"Acte {i+1}: Date d'exécution dans le futur")

            # Validation de la quantité
            if acte.quantite <= 0:
                errors.append(f"Acte {i+1}: Quantité invalide: {acte.quantite}")


class HprimCodingService:
    """Service principal de codage HPRIM."""

    def __init__(self):
        self.generator = HprimXmlGenerator()
        self.parser = HprimXmlParser()
        self.validator = HprimValidationService()

    def create_actes_message(self, patient: HprimPatient, actes: List[HprimActe],
                           etablissement: str) -> HprimMessage:
        """Crée un message d'actes médicaux."""
        return HprimMessage(
            id=str(uuid.uuid4()),
            type_message=HprimMessageType.ACTES_MEDICAUX,
            etablissement=etablissement,
            patient=patient,
            actes=actes
        )

    def generate_xml(self, message: HprimMessage) -> str:
        """Génère le XML pour un message HPRIM."""
        if message.type_message == HprimMessageType.ACTES_MEDICAUX:
            return self.generator.generate_actes_medicaux(message)
        elif message.type_message == HprimMessageType.ETAT_PATIENT:
            return self.generator.generate_etat_patient(message)
        else:
            raise ValueError(f"Type de message non supporté: {message.type_message}")

    def parse_xml(self, xml_content: str) -> HprimMessage:
        """Parse un message XML HPRIM."""
        # Détection automatique du type de message
        if '<actes_medicaux' in xml_content:
            return self.parser.parse_actes_medicaux(xml_content)
        else:
            raise ValueError("Type de message XML non reconnu")

    def validate_message(self, message: HprimMessage) -> Dict[str, Any]:
        """Valide un message HPRIM."""
        return self.validator.validate_message(message)

    def create_acte_from_ccam(self, code_ccam: str, date_exec: date,
                            executant: str, uf: str, um: str,
                            quantite: int = 1, coefficient: float = 1.0) -> HprimActe:
        """Crée un acte CCAM."""
        return HprimActe(
            code=code_ccam,
            type_acte=ActeType.CCAM,
            date_execution=date_exec,
            quantite=quantite,
            coefficient=coefficient,
            executant=executant,
            localisation=f"{uf}/{um}"
        )

    def create_acte_from_ngap(self, code_ngap: str, date_exec: date,
                            executant: str, quantite: int = 1) -> HprimActe:
        """Crée un acte NGAP."""
        return HprimActe(
            code=code_ngap,
            type_acte=ActeType.NGAP,
            date_execution=date_exec,
            quantite=quantite,
            coefficient=1.0,
            executant=executant
        )