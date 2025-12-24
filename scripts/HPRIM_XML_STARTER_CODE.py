# Exemple d'Implémentation HPRIM XML - Point de Départ

## Structure de Base

Voici un exemple de code pour commencer l'implémentation du service HPRIM.

```python
# app/services/hprim/hprim_models.py
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from enum import Enum

class HprimMessageType(Enum):
    EVENEMENTS_SERVEUR_ACTES = "evenementsServeurActes"
    ACQUITTEMENTS_SERVEUR_ACTES = "acquittementsServeurActes"

class HprimAction(Enum):
    CREATION = "création"
    MODIFICATION = "modification"
    SUPPRESSION = "suppression"
    INFORMATION = "information"

@dataclass
class HprimEnteteMessage:
    emetteur_id: str
    emetteur_nom: str
    destinataire_id: str
    destinataire_nom: str
    date_emission: datetime
    message_id: str
    message_type: HprimMessageType

@dataclass
class HprimPatient:
    identifiant_id: str
    identifiant_clef: str
    nom: str
    prenom: str
    date_naissance: Optional[str] = None
    sexe: Optional[str] = None

@dataclass
class HprimProfessionnel:
    nom: str
    prenom: str
    numero_rpps: str
    specialite: Optional[str] = None

@dataclass
class HprimActeCCAM:
    identifiant: str
    code_acte: str  # Format: AAAA999
    code_acte_extension_pmsi: Optional[str] = None  # Format: 99
    code_activite: str  # 2 chiffres
    code_phase: str  # 2 chiffres
    execute_date: datetime
    execute_heure: Optional[str] = None
    executant: HprimProfessionnel
    modificateurs: List[str] = None  # Liste de codes A-Z, 0-9
    quantite: int = 1
    montant_valeur: Optional[Decimal] = None
    montant_devise: str = "EUR"
    commentaire: Optional[str] = None
    action: HprimAction = HprimAction.CREATION
    facturable: bool = True
    valide: bool = False
    facture: bool = False

    def __post_init__(self):
        if self.modificateurs is None:
            self.modificateurs = []

@dataclass
class HprimMessage:
    entete: HprimEnteteMessage
    patient: HprimPatient
    acteur: HprimProfessionnel
    actes_ccam: List[HprimActeCCAM] = None
    version: str = "2.4"
    acquittement_attendu: bool = True

    def __post_init__(self):
        if self.actes_ccam is None:
            self.actes_ccam = []
```

## Service de Génération XML

```python
# app/services/hprim/hprim_xml_generator.py
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import List
from .hprim_models import HprimMessage, HprimActeCCAM, HprimAction

class HprimXmlGenerator:
    NAMESPACE = "http://www.hprim.org/hprimXML"
    NS = {"": NAMESPACE}

    def generate_evenements_serveur_actes(self, message: HprimMessage) -> str:
        """Génère un message evenementsServeurActes en XML"""
        root = ET.Element("evenementsServeurActes", version=message.version)
        root.set("acquittementAttendu", "oui" if message.acquittement_attendu else "non")

        # En-tête
        entete = ET.SubElement(root, "enteteMessage")
        self._add_entete_message(entete, message.entete)

        # Événement acte
        evenement = ET.SubElement(root, "evenementServeurActe")

        # Date action
        date_action = ET.SubElement(evenement, "dateAction")
        date_action.text = datetime.now().isoformat()

        # Acteur
        acteur = ET.SubElement(evenement, "acteur")
        self._add_professionnel(acteur, "medecin", message.acteur)

        # Patient
        patient = ET.SubElement(evenement, "patient")
        self._add_patient(patient, message.patient)

        # Actes CCAM
        if message.actes_ccam:
            actes_ccam = ET.SubElement(evenement, "actesCCAM")
            for acte in message.actes_ccam:
                self._add_acte_ccam(actes_ccam, acte)

        # Convertir en string avec encodage
        rough_string = ET.tostring(root, encoding='iso-8859-1', method='xml')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='iso-8859-1').decode('iso-8859-1')

    def _add_entete_message(self, parent: ET.Element, entete):
        """Ajoute l'en-tête du message"""
        emetteur = ET.SubElement(parent, "emetteur")
        ET.SubElement(emetteur, "id").text = entete.emetteur_id
        ET.SubElement(emetteur, "nom").text = entete.emetteur_nom

        destinataire = ET.SubElement(parent, "destinataire")
        ET.SubElement(destinataire, "id").text = entete.destinataire_id
        ET.SubElement(destinataire, "nom").text = entete.destinataire_nom

        ET.SubElement(parent, "dateEmission").text = entete.date_emission.isoformat()

        message = ET.SubElement(parent, "message")
        ET.SubElement(message, "id").text = entete.message_id
        ET.SubElement(message, "type").text = entete.message_type.value

    def _add_patient(self, parent: ET.Element, patient):
        """Ajoute les informations patient"""
        identifiant = ET.SubElement(parent, "identifiant")
        ET.SubElement(identifiant, "id").text = patient.identifiant_id
        ET.SubElement(identifiant, "clef").text = patient.identifiant_clef

        ET.SubElement(parent, "nom").text = patient.nom
        ET.SubElement(parent, "prenom").text = patient.prenom

        if patient.date_naissance:
            ET.SubElement(parent, "dateNaissance").text = patient.date_naissance

        if patient.sexe:
            ET.SubElement(parent, "sexe").text = patient.sexe

    def _add_professionnel(self, parent: ET.Element, tag: str, prof):
        """Ajoute les informations d'un professionnel"""
        element = ET.SubElement(parent, tag)
        ET.SubElement(element, "nom").text = prof.nom
        ET.SubElement(element, "prenom").text = prof.prenom
        ET.SubElement(element, "numeroRPPS").text = prof.numero_rpps

        if prof.specialite:
            ET.SubElement(element, "specialite").text = prof.specialite

    def _add_acte_ccam(self, parent: ET.Element, acte: HprimActeCCAM):
        """Ajoute un acte CCAM"""
        acte_element = ET.SubElement(parent, "acteCCAM")
        acte_element.set("action", acte.action.value)
        acte_element.set("facturable", "oui" if acte.facturable else "non")
        acte_element.set("valide", "oui" if acte.valide else "non")
        acte_element.set("facture", "oui" if acte.facture else "non")

        # Date action
        ET.SubElement(acte_element, "dateAction").text = datetime.now().isoformat()

        # Acteur
        acteur = ET.SubElement(acte_element, "acteur")
        self._add_professionnel(acteur, "medecin", acte.executant)

        # Identifiant
        identifiant = ET.SubElement(acte_element, "identifiant")
        emetteur = ET.SubElement(identifiant, "emetteur")
        emetteur.text = acte.identifiant
        emetteur.set("portee", "local")

        # Code acte
        ET.SubElement(acte_element, "codeActe").text = acte.code_acte

        if acte.code_acte_extension_pmsi:
            ET.SubElement(acte_element, "codeActeExtensionPMSI").text = acte.code_acte_extension_pmsi

        ET.SubElement(acte_element, "codeActivite").text = acte.code_activite
        ET.SubElement(acte_element, "codePhase").text = acte.code_phase

        # Exécution
        execute = ET.SubElement(acte_element, "execute")
        ET.SubElement(execute, "date").text = acte.execute_date.date().isoformat()

        if acte.execute_heure:
            ET.SubElement(execute, "heure").text = acte.execute_heure

        # Exécutant
        executant = ET.SubElement(acte_element, "executant")
        medecins = ET.SubElement(executant, "medecins")
        self._add_professionnel(medecins, "medecin", acte.executant)

        # Modificateurs
        if acte.modificateurs:
            modificateurs = ET.SubElement(acte_element, "modificateurs")
            for mod in acte.modificateurs:
                mod_element = ET.SubElement(modificateurs, "modificateur")
                mod_element.text = mod
                mod_element.set("statut", "nft")

        # Quantité
        ET.SubElement(acte_element, "quantite").text = str(acte.quantite)

        # Montant
        if acte.montant_valeur is not None:
            montant = ET.SubElement(acte_element, "montant")
            ET.SubElement(montant, "valeur").text = str(acte.montant_valeur)
            ET.SubElement(montant, "devise").text = acte.montant_devise

        # Commentaire
        if acte.commentaire:
            ET.SubElement(acte_element, "commentaire").text = acte.commentaire
```

## Exemple d'Utilisation

```python
# app/services/hprim/hprim_service.py
from datetime import datetime
from .hprim_models import *
from .hprim_xml_generator import HprimXmlGenerator

class HprimService:
    def __init__(self):
        self.generator = HprimXmlGenerator()

    def creer_acte_ccam(self, code_acte: str, patient_id: str, medecin_rpps: str) -> str:
        """Crée un acte CCAM et génère le XML"""

        # Créer les objets de données
        entete = HprimEnteteMessage(
            emetteur_id="FINESS_123456789",
            emetteur_nom="EHPAD LES ROSIERS",
            destinataire_id="FINESS_987654321",
            destinataire_nom="CENTRE HOSPITALIER",
            date_emission=datetime.now(),
            message_id=f"MSG_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES
        )

        patient = HprimPatient(
            identifiant_id=patient_id,
            identifiant_clef=patient_id,
            nom="DUPONT",
            prenom="JEAN",
            date_naissance="1950-01-01"
        )

        medecin = HprimProfessionnel(
            nom="MARTIN",
            prenom="PIERRE",
            numero_rpps=medecin_rpps,
            specialite="Médecine générale"
        )

        acte = HprimActeCCAM(
            identifiant=f"ACTE_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            code_acte=code_acte,
            code_activite="01",
            code_phase="00",
            execute_date=datetime.now(),
            executant=medecin,
            modificateurs=["K"],
            quantite=1,
            montant_valeur=25.50
        )

        message = HprimMessage(
            entete=entete,
            patient=patient,
            acteur=medecin,
            actes_ccam=[acte]
        )

        # Générer le XML
        return self.generator.generate_evenements_serveur_actes(message)
```

## Test de Validation

```python
# test_hprim_basic.py
import pytest
from app.services.hprim.hprim_service import HprimService

def test_generation_xml_ccam():
    service = HprimService()

    xml_content = service.creer_acte_ccam(
        code_acte="AAFA001",
        patient_id="123456789",
        medecin_rpps="12345678901"
    )

    # Vérifications de base
    assert "evenementsServeurActes" in xml_content
    assert "AAFA001" in xml_content
    assert "123456789" in xml_content
    assert "12345678901" in xml_content

    print("XML généré:")
    print(xml_content)

if __name__ == "__main__":
    test_generation_xml_ccam()
```

Ce code constitue un point de départ solide pour l'implémentation HPRIM XML. Il peut être étendu avec la validation XSD, la gestion des acquittements, et les autres types d'actes.</content>
<parameter name="filePath">/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/HPRIM_XML_STARTER_CODE.py