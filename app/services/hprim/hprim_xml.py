# app/services/hprim/hprim_xml.py
"""
Service XML de base pour HPRIM
Génération et parsing XML avec gestion du namespace et encodage
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import logging

from app.models.hprim_models import (
    HprimMessage, HprimEnteteMessage, HprimPatient, HprimProfessionnel,
    HprimActeCCAM, HprimActeNGAP, HprimVenue, HprimModificateur,
    HprimMontant, HprimPriseCharge, HprimMessageType, HprimAction
)

logger = logging.getLogger(__name__)


class HprimXmlService:
    """Service de génération/parsing XML HPRIM"""

    NAMESPACE = "http://www.hprim.org/hprimXML"
    NS = {"": NAMESPACE}

    def __init__(self):
        self.namespace_prefix = ""

    def generate_xml(self, message: HprimMessage) -> str:
        """
        Génère le XML complet d'un message HPRIM

        Args:
            message: Message HPRIM à convertir

        Returns:
            XML string en ISO-8859-1
        """
        if message.entete.message_type == HprimMessageType.EVENEMENTS_SERVEUR_ACTES:
            return self._generate_evenements_serveur_actes(message)
        elif message.entete.message_type == HprimMessageType.ACQUITTEMENTS_SERVEUR_ACTES:
            return self._generate_acquittements_serveur_actes(message)
        else:
            raise ValueError(f"Type de message non supporté: {message.entete.message_type}")

    def _generate_evenements_serveur_actes(self, message: HprimMessage) -> str:
        """Génère un message evenementsServeurActes"""
        root = ET.Element("evenementsServeurActes", version=message.version)

        # Attributs du root
        root.set("acquittementAttendu", "oui" if message.acquittement_attendu else "non")
        root.set("identifiantAttendu", "oui" if message.identifiant_attendu else "non")
        root.set("realise", "oui" if message.realise else "non")
        root.set("interrogation", "oui" if message.interrogation else "non")

        # En-tête
        entete = ET.SubElement(root, "enteteMessage")
        self._add_entete_message(entete, message.entete)

        # Contenu selon le type d'événement
        if message.actes_ccam:
            self._add_evenement_actes_ccam(root, message)
        elif message.actes_ngap:
            self._add_evenement_actes_ngap(root, message)
        elif message.actes_lpp:
            self._add_evenement_actes_lpp(root, message)
        elif message.actes_ucd:
            self._add_evenement_actes_ucd(root, message)
        elif message.interventions:
            self._add_evenement_interventions(root, message)

        return self._xml_to_string(root)

    def _add_entete_message(self, parent: ET.Element, entete: HprimEnteteMessage):
        """Ajoute l'en-tête du message"""
        # Émetteur
        emetteur = ET.SubElement(parent, "emetteur")
        ET.SubElement(emetteur, "id").text = entete.emetteur_id
        ET.SubElement(emetteur, "nom").text = entete.emetteur_nom

        # Destinataire
        destinataire = ET.SubElement(parent, "destinataire")
        ET.SubElement(destinataire, "id").text = entete.destinataire_id
        ET.SubElement(destinataire, "nom").text = entete.destinataire_nom

        # Date et message
        ET.SubElement(parent, "dateEmission").text = entete.date_emission.isoformat()
        message_elem = ET.SubElement(parent, "message")
        ET.SubElement(message_elem, "id").text = entete.message_id
        ET.SubElement(message_elem, "type").text = entete.message_type.value

    def _add_evenement_actes_ccam(self, root: ET.Element, message: HprimMessage):
        """Ajoute un événement avec actes CCAM"""
        evenement = ET.SubElement(root, "evenementServeurActe")

        # Date action
        ET.SubElement(evenement, "dateAction").text = datetime.now().isoformat()

        # Acteur
        acteur = ET.SubElement(evenement, "acteur")
        self._add_professionnel(acteur, "medecin", message.acteur)

        # Patient
        patient = ET.SubElement(evenement, "patient")
        self._add_patient(patient, message.patient)

        # Venue
        if message.venue:
            venue = ET.SubElement(evenement, "venue")
            self._add_venue(venue, message.venue)

        # Actes CCAM
        actes_ccam = ET.SubElement(evenement, "actesCCAM")
        for acte in message.actes_ccam:
            self._add_acte_ccam(actes_ccam, acte)

    def _add_acte_ccam(self, parent: ET.Element, acte: HprimActeCCAM):
        """Ajoute un acte CCAM"""
        acte_elem = ET.SubElement(parent, "acteCCAM")

        # Attributs
        acte_elem.set("action", acte.action.value)
        acte_elem.set("facturable", "oui" if acte.facturable else "non")
        acte_elem.set("valide", "oui" if acte.valide else "non")
        acte_elem.set("facture", "oui" if acte.facture else "non")

        if acte.remboursement_exceptionnel:
            acte_elem.set("remboursementExceptionnel", "oui")
        if acte.gratuit:
            acte_elem.set("gratuit", "oui")
        if acte.option_coordination:
            acte_elem.set("optionCoordination", "oui")
        if acte.top_prevention_amo_amc:
            acte_elem.set("topPreventionActionAmoAmc", "oui")
        if acte.signe:
            acte_elem.set("signe", "oui")
        if acte.documentaire:
            acte_elem.set("documentaire", "oui")

        # Attributs optionnels
        if acte.rapport_exoneration:
            acte_elem.set("rapportExoneration", acte.rapport_exoneration)
        if acte.supplement_charges:
            acte_elem.set("supplementCharges", acte.supplement_charges)
        if acte.forfait_securite_environnement_hospitalier:
            acte_elem.set("forfaitSecuriteEnvironnementHospitalier", acte.forfait_securite_environnement_hospitalier)
        if acte.exoneration_ccam:
            acte_elem.set("exonerationCCAM", acte.exoneration_ccam)
        if acte.pmsi:
            acte_elem.set("PMSI", acte.pmsi)

        # Date action
        ET.SubElement(acte_elem, "dateAction").text = datetime.now().isoformat()

        # Acteur
        acteur = ET.SubElement(acte_elem, "acteur")
        self._add_professionnel(acteur, "medecin", acte.executant)

        # Identifiant
        identifiant = ET.SubElement(acte_elem, "identifiant")
        emetteur = ET.SubElement(identifiant, "emetteur")
        emetteur.text = acte.identifiant
        emetteur.set("portee", "local")

        # Codes acte
        ET.SubElement(acte_elem, "codeActe").text = acte.code_acte
        if acte.code_acte_extension_pmsi:
            ET.SubElement(acte_elem, "codeActeExtensionPMSI").text = acte.code_acte_extension_pmsi
        ET.SubElement(acte_elem, "codeActivite").text = acte.code_activite
        ET.SubElement(acte_elem, "codePhase").text = acte.code_phase

        # Exécution
        execute = ET.SubElement(acte_elem, "execute")
        ET.SubElement(execute, "date").text = acte.execute_date.date().isoformat()
        if acte.execute_heure:
            ET.SubElement(execute, "heure").text = acte.execute_heure

        # Exécutant
        executant = ET.SubElement(acte_elem, "executant")
        medecins = ET.SubElement(executant, "medecins")
        self._add_professionnel(medecins, "medecin", acte.executant)

        # Modificateurs
        if acte.modificateurs:
            modificateurs = ET.SubElement(acte_elem, "modificateurs")
            for mod in acte.modificateurs:
                mod_elem = ET.SubElement(modificateurs, "modificateur")
                mod_elem.text = mod.code
                mod_elem.set("statut", mod.statut)

        # Quantité
        ET.SubElement(acte_elem, "quantite").text = str(acte.quantite)

        # Prise en charge
        if acte.prise_charge:
            prise_charge = ET.SubElement(acte_elem, "priseCharge")
            pc = acte.prise_charge
            if pc.risque:
                ET.SubElement(prise_charge, "risque").text = pc.risque
            if pc.date_demande_accord:
                ET.SubElement(prise_charge, "dateDemandeAccord").text = pc.date_demande_accord
            if pc.entente_prealable:
                prise_charge.set("ententePrealable", pc.entente_prealable)
            if pc.indicateur_parcours_soins:
                prise_charge.set("indicateurParcoursSoins", pc.indicateur_parcours_soins)

        # Montant
        if acte.montant:
            montant = ET.SubElement(acte_elem, "montant")
            ET.SubElement(montant, "valeur").text = str(acte.montant.valeur)
            ET.SubElement(montant, "devise").text = acte.montant.devise

        # Commentaire
        if acte.commentaire:
            ET.SubElement(acte_elem, "commentaire").text = acte.commentaire

    def _add_patient(self, parent: ET.Element, patient: HprimPatient):
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

    def _add_professionnel(self, parent: ET.Element, tag: str, prof: HprimProfessionnel):
        """Ajoute les informations d'un professionnel"""
        element = ET.SubElement(parent, tag)
        ET.SubElement(element, "nom").text = prof.nom
        ET.SubElement(element, "prenom").text = prof.prenom
        ET.SubElement(element, "numeroRPPS").text = prof.numero_rpps

        if prof.specialite:
            ET.SubElement(element, "specialite").text = prof.specialite

    def _add_venue(self, parent: ET.Element, venue):
        """Ajoute les informations de venue"""
        ET.SubElement(parent, "identifiant").text = venue.identifiant
        ET.SubElement(parent, "libelle").text = venue.libelle

    def _add_evenement_actes_ngap(self, root: ET.Element, message: HprimMessage):
        """Ajoute un événement avec actes NGAP"""
        # TODO: Implémenter
        pass

    def _add_evenement_actes_lpp(self, root: ET.Element, message: HprimMessage):
        """Ajoute un événement avec actes LPP"""
        # TODO: Implémenter
        pass

    def _add_evenement_actes_ucd(self, root: ET.Element, message: HprimMessage):
        """Ajoute un événement avec actes UCD"""
        # TODO: Implémenter
        pass

    def _add_evenement_interventions(self, root: ET.Element, message: HprimMessage):
        """Ajoute un événement avec interventions"""
        # TODO: Implémenter
        pass

    def _generate_acquittements_serveur_actes(self, message: HprimMessage) -> str:
        """Génère un message acquittementsServeurActes"""
        # TODO: Implémenter
        root = ET.Element("acquittementsServeurActes", version=message.version)
        return self._xml_to_string(root)

    def _xml_to_string(self, root: ET.Element) -> str:
        """Convertit un élément XML en string formatée ISO-8859-1"""
        rough_string = ET.tostring(root, encoding='iso-8859-1', method='xml')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='iso-8859-1').decode('iso-8859-1')

    def parse_xml(self, xml_string: str) -> HprimMessage:
        """
        Parse une chaîne XML en objet HprimMessage

        Args:
            xml_string: XML à parser

        Returns:
            Objet HprimMessage
        """
        # TODO: Implémenter le parsing
        raise NotImplementedError("XML parsing not yet implemented")

    def validate_encoding(self, xml_string: str) -> bool:
        """
        Vérifie que l'encodage est bien ISO-8859-1

        Args:
            xml_string: XML à vérifier

        Returns:
            True si encodage valide
        """
        try:
            xml_string.encode('iso-8859-1')
            return True
        except UnicodeEncodeError:
            return False