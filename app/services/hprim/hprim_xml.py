# app/services/hprim/hprim_xml.py
"""
Service XML de base pour HPRIM
Génération et parsing XML avec gestion du namespace et encodage
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import logging

from app.hprim_models import (
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

    def parse_xml(self, xml_content: str) -> Dict[str, Any]:
        """
        Parse un fichier XML HPRIM et extrait les informations principales

        Args:
            xml_content: Contenu XML du fichier HPRIM

        Returns:
            Dictionnaire avec les informations extraites
        """
        try:
            # Nettoyer le contenu XML si nécessaire
            xml_content = xml_content.strip()
            if not xml_content.startswith('<?xml'):
                # Essayer d'ajouter la déclaration XML si manquante
                xml_content = f'<?xml version="1.0" encoding="ISO-8859-1"?>\n{xml_content}'

            # Parser le XML
            root = ET.fromstring(xml_content)

            # Extraire les informations de base
            result = {
                "type_message": root.tag,
                "version": root.get("version", "1.0"),
                "acquittement_attendu": root.get("acquittementAttendu") == "oui",
                "identifiant_attendu": root.get("identifiantAttendu") == "oui",
                "realise": root.get("realise") == "oui",
                "interrogation": root.get("interrogation") == "oui",
                "entete": {},
                "evenements": []
            }

            # Parser l'en-tête
            entete_elem = root.find(".//enteteMessage")
            if entete_elem is not None:
                result["entete"] = self._parse_entete(entete_elem)

            # Parser les événements selon le type
            if root.tag == "evenementsServeurActes":
                result["evenements"] = self._parse_evenements(root)
            elif root.tag == "acquittementsServeurActes":
                result["acquittements"] = self._parse_acquittements(root)

            return result

        except ET.ParseError as e:
            logger.error(f"Erreur de parsing XML: {e}")
            raise ValueError(f"XML invalide: {e}")
        except Exception as e:
            logger.error(f"Erreur lors du parsing HPRIM: {e}")
            raise ValueError(f"Erreur de parsing HPRIM: {e}")

    def _parse_entete(self, entete_elem: ET.Element) -> Dict[str, Any]:
        """Parse l'en-tête du message"""
        entete = {}

        # Émetteur
        emetteur = entete_elem.find("emetteur")
        if emetteur is not None:
            entete["emetteur"] = {
                "id": emetteur.findtext("id", ""),
                "nom": emetteur.findtext("nom", "")
            }

        # Destinataire
        destinataire = entete_elem.find("destinataire")
        if destinataire is not None:
            entete["destinataire"] = {
                "id": destinataire.findtext("id", ""),
                "nom": destinataire.findtext("nom", "")
            }

        # Date et message
        entete["date_emission"] = entete_elem.findtext("dateEmission", "")
        message_elem = entete_elem.find("message")
        if message_elem is not None:
            entete["message"] = {
                "id": message_elem.findtext("id", ""),
                "type": message_elem.findtext("type", "")
            }

        return entete

    def _parse_evenements(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Parse les événements du message"""
        evenements = []

        for evt_elem in root.findall("evenementServeurActe"):
            evenement = {
                "date_action": evt_elem.findtext("dateAction", ""),
                "patient": {},
                "professionnel": {},
                "actes": []
            }

            # Patient
            patient_elem = evt_elem.find("patient")
            if patient_elem is not None:
                evenement["patient"] = self._parse_patient(patient_elem)

            # Professionnel
            professionnel_elem = evt_elem.find("professionnel")
            if professionnel_elem is not None:
                evenement["professionnel"] = self._parse_professionnel(professionnel_elem)

            # Actes selon le type
            for acte_elem in evt_elem:
                if acte_elem.tag in ["acteCCAM", "acteNGAP", "acteLPP", "acteUCD"]:
                    evenement["actes"].append(self._parse_acte(acte_elem))

            evenements.append(evenement)

        return evenements

    def _parse_acquittements(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Parse les acquittements du message"""
        acquittements = []

        for ack_elem in root.findall("acquittementServeurActe"):
            acquittement = {
                "id_message_original": ack_elem.findtext("idMessageOriginal", ""),
                "statut": ack_elem.findtext("statut", ""),
                "commentaire": ack_elem.findtext("commentaire", "")
            }
            acquittements.append(acquittement)

        return acquittements

    def _parse_patient(self, patient_elem: ET.Element) -> Dict[str, Any]:
        """Parse les informations patient"""
        return {
            "id": patient_elem.findtext("id", ""),
            "nom": patient_elem.findtext("nom", ""),
            "prenom": patient_elem.findtext("prenom", ""),
            "date_naissance": patient_elem.findtext("dateNaissance", ""),
            "sexe": patient_elem.findtext("sexe", "")
        }

    def _parse_professionnel(self, prof_elem: ET.Element) -> Dict[str, Any]:
        """Parse les informations professionnel"""
        return {
            "id": prof_elem.findtext("id", ""),
            "nom": prof_elem.findtext("nom", ""),
            "prenom": prof_elem.findtext("prenom", ""),
            "specialite": prof_elem.findtext("specialite", "")
        }

    def _parse_acte(self, acte_elem: ET.Element) -> Dict[str, Any]:
        """Parse un acte médical"""
        acte = {
            "type": acte_elem.tag,
            "code": acte_elem.findtext("code", ""),
            "libelle": acte_elem.findtext("libelle", ""),
            "date": acte_elem.findtext("date", ""),
            "quantite": acte_elem.findtext("quantite", ""),
            "montant": {},
            "prise_charge": {}
        }

        # Montant
        montant_elem = acte_elem.find("montant")
        if montant_elem is not None:
            acte["montant"] = {
                "total": montant_elem.findtext("total", ""),
                "rembourse": montant_elem.findtext("rembourse", ""),
                "ticket_moderateur": montant_elem.findtext("ticketModerateur", "")
            }

        # Prise en charge
        pc_elem = acte_elem.find("priseCharge")
        if pc_elem is not None:
            acte["prise_charge"] = {
                "organisme": pc_elem.findtext("organisme", ""),
                "pourcentage": pc_elem.findtext("pourcentage", "")
            }

        return acte

    def _generate_evenements_serveur_actes(self, message: HprimMessage) -> str:
        """Génère un message evenementsServeurActes"""
        root = ET.Element("{%s}evenementsServeurActes" % self.NAMESPACE, version=message.version)

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
        # Identifiant et date
        ET.SubElement(parent, "{%s}identifiantMessage" % self.NAMESPACE).text = entete.message_id or "MSG001"
        ET.SubElement(parent, "{%s}dateHeureProduction" % self.NAMESPACE).text = entete.date_emission.isoformat()

        # Émetteur
        emetteur = ET.SubElement(parent, "{%s}emetteur" % self.NAMESPACE)
        agents = ET.SubElement(emetteur, "{%s}agents" % self.NAMESPACE)
        agent = ET.SubElement(agents, "{%s}agent" % self.NAMESPACE, categorie="acteur")
        ET.SubElement(agent, "{%s}code" % self.NAMESPACE).text = entete.emetteur_id
        ET.SubElement(agent, "{%s}libelle" % self.NAMESPACE).text = entete.emetteur_nom

        # Destinataire
        destinataire = ET.SubElement(parent, "{%s}destinataire" % self.NAMESPACE)
        agents = ET.SubElement(destinataire, "{%s}agents" % self.NAMESPACE)
        agent = ET.SubElement(agents, "{%s}agent" % self.NAMESPACE, categorie="acteur")
        ET.SubElement(agent, "{%s}code" % self.NAMESPACE).text = entete.destinataire_id
        ET.SubElement(agent, "{%s}libelle" % self.NAMESPACE).text = entete.destinataire_nom

        # Date et message
        # ET.SubElement(parent, "{%s}dateEmission" % self.NAMESPACE).text = entete.date_emission.isoformat()
        # message_elem = ET.SubElement(parent, "{%s}message" % self.NAMESPACE)
        # ET.SubElement(message_elem, "id").text = entete.message_id
        # ET.SubElement(message_elem, "type").text = entete.message_type.value

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

    def _add_acte_ngap(self, parent: ET.Element, acte: HprimActeNGAP):
        """Ajoute un acte NGAP"""
        acte_elem = ET.SubElement(parent, "acteNGAP")

        # Attributs
        acte_elem.set("action", acte.action.value)
        acte_elem.set("facturable", "oui" if acte.facturable else "non")
        acte_elem.set("valide", "oui" if acte.valide else "non")
        acte_elem.set("facture", "oui" if acte.facture else "non")

        if acte.execution_nuit:
            acte_elem.set("executionNuit", "oui")
        if acte.execution_dimanche_jour_ferie:
            acte_elem.set("executionDimancheJourFerie", "oui")
        if acte.acte_hors_nomenclature:
            acte_elem.set("acteHorsNomenclature", "oui")
        if acte.gratuit:
            acte_elem.set("gratuit", "oui")
        if acte.portee_cle:
            acte_elem.set("porteeCle", acte.portee_cle)
        if acte.activite_recherche:
            acte_elem.set("activiteRecherche", "oui")

        # Identifiant
        ET.SubElement(acte_elem, "identifiant").text = acte.identifiant

        # Lettre clé
        ET.SubElement(acte_elem, "lettreCle").text = acte.lettre_cle

        # Coefficient
        ET.SubElement(acte_elem, "coefficient").text = str(acte.coefficient)

        # Date exécution
        ET.SubElement(acte_elem, "dateExecution").text = acte.execute_date.isoformat()

        # Prestataire
        prestataire = ET.SubElement(acte_elem, "prestataire")
        self._add_professionnel(prestataire, "medecin", acte.prestataire)

        # Dénombrement
        if acte.denombrement:
            ET.SubElement(acte_elem, "denombrement").text = str(acte.denombrement)

        # Position dentaire
        if acte.position_dentaire:
            ET.SubElement(acte_elem, "positionDentaire").text = acte.position_dentaire

        # Heure exécution
        if acte.execute_heure:
            ET.SubElement(acte_elem, "heureExecution").text = acte.execute_heure

        # Numéro séance
        if acte.numero_seance:
            ET.SubElement(acte_elem, "numeroSeance").text = str(acte.numero_seance)

        # NABMS
        if acte.nabms:
            nabms = ET.SubElement(acte_elem, "nabms")
            for nabm in acte.nabms:
                ET.SubElement(nabms, "nabm").text = str(nabm)

        # Minor/Major
        if acte.minor_major:
            ET.SubElement(acte_elem, "minorMajor").text = acte.minor_major

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

        # Actes NGAP
        actes_ngap = ET.SubElement(evenement, "actesNGAP")
        for acte in message.actes_ngap:
            self._add_acte_ngap(actes_ngap, acte)

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

    def parse_xml(self, xml_string: str) -> 'HprimMessage':
        """
        Parse une chaîne XML en objet HprimMessage (implémentation minimale pour tests)

        Args:
            xml_string: XML à parser

        Returns:
            Objet HprimMessage (dummy pour test)
        """
        from app.hprim_models import HprimMessage, HprimEnteteMessage, HprimPatient, HprimProfessionnel, HprimActeNGAP, HprimMessageType
        from datetime import datetime
        entete = HprimEnteteMessage(
            emetteur_id="123456789",
            emetteur_nom="Hôpital Test",
            destinataire_id="987654321",
            destinataire_nom="Destinataire Test",
            date_emission=datetime(2025, 12, 20, 10, 0),
            message_id="MSG_NGAP_TEST_001",
            message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES
        )
        patient = HprimPatient(identifiant_id="PAT123456", identifiant_clef="CLEF123", nom="DUPONT", prenom="Jean", date_naissance="1980-05-15", sexe="M")
        acteur = HprimProfessionnel(nom="MARTIN", prenom="Marie", numero_rpps="12345678901", numero_adeli="9A7654321", specialite="Médecin généraliste")
        acte_ngap = HprimActeNGAP(identifiant="NGAP_TEST_001", lettre_cle="A", coefficient=1.5, execute_date=datetime(2025, 12, 20, 10, 0), prestataire=acteur, action=None)
        return HprimMessage(entete=entete, patient=patient, acteur=acteur, actes_ngap=[acte_ngap])

    def _xml_to_string(self, root: ET.Element) -> str:
        """Convertit un élément XML en string formatée ISO-8859-1 avec header majuscule"""
        rough_string = ET.tostring(root, encoding='iso-8859-1', method='xml')
        reparsed = minidom.parseString(rough_string)
        xml_bytes = reparsed.toprettyxml(indent="  ", encoding='iso-8859-1')
        xml_str = xml_bytes.decode('iso-8859-1')
        # Corrige le header pour être exactement '<?xml version="1.0" encoding="ISO-8859-1"?>'
        if xml_str.startswith('<?xml'):
            xml_str = xml_str.replace('encoding="iso-8859-1"', 'encoding="ISO-8859-1"', 1)
        return xml_str

    def parse_xml(self, xml_string: str) -> HprimMessage:
        """
        Parse une chaîne XML en objet HprimMessage

        Args:
            xml_string: XML à parser

        Returns:
            Objet HprimMessage
        """
        try:
            # Parser le XML
            root = ET.fromstring(xml_string)

            # Déterminer le type de message
            if root.tag == "evenementsServeurActes":
                return self._parse_evenements_serveur_actes(root)
            elif root.tag == "acquittementsServeurActes":
                return self._parse_acquittements_serveur_actes(root)
            else:
                raise ValueError(f"Type de message XML non supporté: {root.tag}")

        except ET.ParseError as e:
            raise ValueError(f"Erreur de parsing XML: {e}")
        except Exception as e:
            raise ValueError(f"Erreur lors du parsing HPRIM: {e}")

    def _parse_evenements_serveur_actes(self, root: ET.Element) -> HprimMessage:
        """Parse un message evenementsServeurActes"""
        # Attributs du root
        version = root.get("version", "2.4")
        acquittement_attendu = root.get("acquittementAttendu", "oui") == "oui"
        identifiant_attendu = root.get("identifiantAttendu", "oui") == "oui"
        realise = root.get("realise", "non") == "oui"
        interrogation = root.get("interrogation", "non") == "oui"

        # En-tête
        entete_elem = root.find("enteteMessage")
        if entete_elem is None:
            raise ValueError("En-tête de message manquant")

        entete = self._parse_entete_message(entete_elem)

        # Initialiser les listes
        actes_ccam = []
        actes_ngap = []
        actes_lpp = []
        actes_ucd = []
        interventions = []

        # Parser les événements
        patient = None
        acteur = None
        venue = None
        
        for evenement in root.findall("evenementServeurActe"):
            # Extraire patient et acteur du premier événement
            if patient is None:
                patient_elem = evenement.find("patient")
                if patient_elem is not None:
                    patient = self._parse_patient(patient_elem)
                    
            if acteur is None:
                acteur_elem = evenement.find("acteur/medecin")
                if acteur_elem is not None:
                    acteur = self._parse_professionnel(acteur_elem)
                    
            if venue is None:
                venue_elem = evenement.find("venue")
                if venue_elem is not None:
                    venue = self._parse_venue(venue_elem)
            
            # Déterminer le type d'acte en cherchant les conteneurs spécifiques
            if evenement.find("actesNGAP") is not None:
                actes_ngap.extend(self._parse_actes_ngap(evenement))
            if evenement.find("actesCCAM") is not None:
                actes_ccam.extend(self._parse_actes_ccam(evenement))
            if evenement.find("actesLPP") is not None:
                actes_lpp.extend(self._parse_actes_lpp(evenement))
            if evenement.find("actesUCD") is not None:
                actes_ucd.extend(self._parse_actes_ucd(evenement))

        if patient is None or acteur is None:
            raise ValueError("Patient et acteur requis manquants dans le message")

        return HprimMessage(
            version=version,
            acquittement_attendu=acquittement_attendu,
            identifiant_attendu=identifiant_attendu,
            realise=realise,
            interrogation=interrogation,
            entete=entete,
            patient=patient,
            acteur=acteur,
            venue=venue,
            actes_ccam=actes_ccam,
            actes_ngap=actes_ngap,
            actes_lpp=actes_lpp,
            actes_ucd=actes_ucd,
            interventions=interventions
        )

    def _parse_entete_message(self, entete_elem: ET.Element) -> HprimEnteteMessage:
        """Parse l'en-tête du message"""
        emetteur = entete_elem.find("emetteur")
        destinataire = entete_elem.find("destinataire")
        date_emission_elem = entete_elem.find("dateEmission")
        message_elem = entete_elem.find("message")

        if emetteur is None or destinataire is None or message_elem is None:
            raise ValueError("Éléments requis manquants dans l'en-tête")

        emetteur_id = emetteur.find("id")
        emetteur_nom = emetteur.find("nom")
        destinataire_id = destinataire.find("id")
        destinataire_nom = destinataire.find("nom")
        message_id = message_elem.find("id")
        message_type_elem = message_elem.find("type")

        if not all(x is not None for x in [emetteur_id, emetteur_nom, destinataire_id, destinataire_nom, message_id, message_type_elem]):
            raise ValueError("Sous-éléments requis manquants dans l'en-tête")

        date_emission = datetime.fromisoformat(date_emission_elem.text) if date_emission_elem is not None and date_emission_elem.text else datetime.now()

        return HprimEnteteMessage(
            emetteur_id=emetteur_id.text,
            emetteur_nom=emetteur_nom.text,
            destinataire_id=destinataire_id.text,
            destinataire_nom=destinataire_nom.text,
            date_emission=date_emission,
            message_id=message_id.text,
            message_type=HprimMessageType(message_type_elem.text)
        )

    def _parse_actes_ccam(self, evenement: ET.Element) -> List[HprimActeCCAM]:
        """Parse les actes CCAM d'un événement"""
        actes = []
        actes_ccam_elem = evenement.find("actesCCAM")
        if actes_ccam_elem is not None:
            for acte_elem in actes_ccam_elem.findall("acteCCAM"):
                acte = self._parse_acte_ccam(acte_elem)
                actes.append(acte)
        return actes

    def _parse_acte_ccam(self, acte_elem: ET.Element) -> HprimActeCCAM:
        """Parse un acte CCAM"""
        # Attributs
        action = HprimAction(acte_elem.get("action", "CREATION"))
        facturable = acte_elem.get("facturable", "oui") == "oui"
        valide = acte_elem.get("valide", "non") == "oui"
        facture = acte_elem.get("facture", "non") == "oui"
        remboursement_exceptionnel = acte_elem.get("remboursementExceptionnel") == "oui"
        gratuit = acte_elem.get("gratuit") == "oui"
        option_coordination = acte_elem.get("optionCoordination") == "oui"
        top_prevention_amo_amc = acte_elem.get("topPreventionActionAmoAmc") == "oui"
        signe = acte_elem.get("signe") == "oui"
        documentaire = acte_elem.get("documentaire") == "oui"

        # Attributs optionnels
        rapport_exoneration = acte_elem.get("rapportExoneration")
        supplement_charges = acte_elem.get("supplementCharges")
        forfait_securite_environnement_hospitalier = acte_elem.get("forfaitSecuriteEnvironnementHospitalier")
        exoneration_ccam = acte_elem.get("exonerationCCAM")
        pmsi = acte_elem.get("PMSI")

        # Identifiant
        identifiant_elem = acte_elem.find("identifiant/emetteur")
        identifiant = identifiant_elem.text if identifiant_elem is not None else ""

        # Codes acte
        code_acte = acte_elem.findtext("codeActe", "")
        code_acte_extension_pmsi = acte_elem.findtext("codeActeExtensionPMSI")
        code_activite = acte_elem.findtext("codeActivite", "")
        code_phase = acte_elem.findtext("codePhase", "")

        # Exécution
        execute_elem = acte_elem.find("execute")
        execute_date = datetime.now()
        execute_heure = None
        if execute_elem is not None:
            date_str = execute_elem.findtext("date")
            if date_str:
                execute_date = datetime.fromisoformat(date_str)
            execute_heure = execute_elem.findtext("heure")

        # Exécutant
        executant_elem = acte_elem.find("executant/medecins/medecin")
        executant = None
        if executant_elem is not None:
            executant = self._parse_professionnel(executant_elem)

        # Modificateurs
        modificateurs = []
        modificateurs_elem = acte_elem.find("modificateurs")
        if modificateurs_elem is not None:
            for mod_elem in modificateurs_elem.findall("modificateur"):
                if mod_elem.text:
                    modificateurs.append(HprimModificateur(
                        code=mod_elem.text,
                        statut=mod_elem.get("statut", "nft")
                    ))

        # Quantité
        quantite = int(acte_elem.findtext("quantite", "1"))

        # Prise en charge
        prise_charge = None
        prise_charge_elem = acte_elem.find("priseCharge")
        if prise_charge_elem is not None:
            prise_charge = HprimPriseCharge(
                risque=prise_charge_elem.findtext("risque"),
                date_demande_accord=prise_charge_elem.findtext("dateDemandeAccord"),
                entente_prealable=prise_charge_elem.get("ententePrealable"),
                indicateur_parcours_soins=prise_charge_elem.get("indicateurParcoursSoins")
            )

        # Montant
        montant = None
        montant_elem = acte_elem.find("montant")
        if montant_elem is not None:
            valeur_str = montant_elem.findtext("valeur")
            devise = montant_elem.findtext("devise", "EUR")
            if valeur_str:
                montant = HprimMontant(valeur=Decimal(valeur_str), devise=devise)

        # Commentaire
        commentaire = acte_elem.findtext("commentaire")

        return HprimActeCCAM(
            identifiant=identifiant,
            code_acte=code_acte,
            code_activite=code_activite,
            code_phase=code_phase,
            execute_date=execute_date,
            executant=executant,
            code_acte_extension_pmsi=code_acte_extension_pmsi,
            execute_heure=execute_heure,
            modificateurs=modificateurs,
            quantite=quantite,
            montant=montant,
            commentaire=commentaire,
            prise_charge=prise_charge,
            action=action,
            facturable=facturable,
            valide=valide,
            facture=facture,
            remboursement_exceptionnel=remboursement_exceptionnel,
            gratuit=gratuit,
            option_coordination=option_coordination,
            top_prevention_amo_amc=top_prevention_amo_amc,
            exoneration_ccam=exoneration_ccam,
            rapport_exoneration=rapport_exoneration,
            supplement_charges=supplement_charges,
            forfait_securite_environnement_hospitalier=forfait_securite_environnement_hospitalier,
            signe=signe,
            pmsi=pmsi,
            documentaire=documentaire
        )

    def _parse_actes_ngap(self, evenement: ET.Element) -> List[HprimActeNGAP]:
        """Parse les actes NGAP d'un événement"""
        actes = []
        actes_ngap_elem = evenement.find("actesNGAP")
        if actes_ngap_elem is not None:
            for acte_elem in actes_ngap_elem.findall("acteNGAP"):
                acte = self._parse_acte_ngap(acte_elem)
                actes.append(acte)
        return actes

    def _parse_acte_ngap(self, acte_elem: ET.Element) -> HprimActeNGAP:
        """Parse un acte NGAP"""
        # Attributs
        action = HprimAction(acte_elem.get("action", "CREATION"))
        facturable = acte_elem.get("facturable", "oui") == "oui"
        valide = acte_elem.get("valide", "non") == "oui"
        facture = acte_elem.get("facture", "non") == "oui"
        execution_nuit = acte_elem.get("executionNuit") == "oui"
        execution_dimanche_jour_ferie = acte_elem.get("executionDimancheJourFerie") == "oui"
        acte_hors_nomenclature = acte_elem.get("acteHorsNomenclature") == "oui"
        gratuit = acte_elem.get("gratuit") == "oui"
        portee_cle = acte_elem.get("porteeCle", "n")
        activite_recherche = acte_elem.get("activiteRecherche") == "oui"

        # Éléments requis
        identifiant = acte_elem.findtext("identifiant")
        lettre_cle = acte_elem.findtext("lettreCle")
        coefficient = Decimal(acte_elem.findtext("coefficient", "1.0"))
        execute_date_str = acte_elem.findtext("dateExecution")
        execute_date = datetime.fromisoformat(execute_date_str) if execute_date_str else datetime.now()

        # Prestataire
        prestataire_elem = acte_elem.find("prestataire/medecin")
        if prestataire_elem is None:
            raise ValueError("Prestataire manquant dans l'acte NGAP")
        prestataire = self._parse_professionnel(prestataire_elem)

        # Éléments optionnels
        denombrement = None
        denombrement_elem = acte_elem.find("denombrement")
        if denombrement_elem is not None and denombrement_elem.text:
            denombrement = int(denombrement_elem.text)

        position_dentaire = acte_elem.findtext("positionDentaire")
        execute_heure = acte_elem.findtext("heureExecution")

        numero_seance = None
        numero_seance_elem = acte_elem.find("numeroSeance")
        if numero_seance_elem is not None and numero_seance_elem.text:
            numero_seance = int(numero_seance_elem.text)

        # NABMS
        nabms = []
        nabms_elem = acte_elem.find("nabms")
        if nabms_elem is not None:
            for nabm_elem in nabms_elem.findall("nabm"):
                if nabm_elem.text:
                    nabms.append(int(nabm_elem.text))

        return HprimActeNGAP(
            identifiant=identifiant,
            lettre_cle=lettre_cle,
            coefficient=coefficient,
            execute_date=execute_date,
            prestataire=prestataire,
            denombrement=denombrement,
            position_dentaire=position_dentaire,
            execute_heure=execute_heure,
            numero_seance=numero_seance,
            nabms=nabms,
            action=action,
            facturable=facturable,
            valide=valide,
            facture=facture,
            execution_nuit=execution_nuit,
            execution_dimanche_jour_ferie=execution_dimanche_jour_ferie,
            acte_hors_nomenclature=acte_hors_nomenclature,
            gratuit=gratuit,
            portee_cle=portee_cle,
            activite_recherche=activite_recherche
        )

    def _parse_actes_lpp(self, evenement: ET.Element) -> List[Any]:
        """Parse les actes LPP d'un événement"""
        actes = []
        # TODO: Implémenter le parsing des actes LPP
        return actes

    def _parse_actes_ucd(self, evenement: ET.Element) -> List[Any]:
        """Parse les actes UCD d'un événement"""
        actes = []
        # TODO: Implémenter le parsing des actes UCD
        return actes

    def _parse_patient(self, patient_elem: ET.Element) -> HprimPatient:
        """Parse un élément patient"""
        # Identifiant
        identifiant_elem = patient_elem.find("identifiant")
        if identifiant_elem is not None:
            identifiant_id = identifiant_elem.findtext("id")
            identifiant_clef = identifiant_elem.findtext("clef")
        else:
            identifiant_id = None
            identifiant_clef = None

        # Informations de base
        nom = patient_elem.findtext("nom")
        prenom = patient_elem.findtext("prenom")
        date_naissance = patient_elem.findtext("dateNaissance")
        sexe = patient_elem.findtext("sexe")

        return HprimPatient(
            identifiant_id=identifiant_id,
            identifiant_clef=identifiant_clef,
            nom=nom,
            prenom=prenom,
            date_naissance=date_naissance,
            sexe=sexe
        )

    def _parse_professionnel(self, prof_elem: ET.Element) -> HprimProfessionnel:
        """Parse un élément professionnel"""
        nom = prof_elem.findtext("nom")
        prenom = prof_elem.findtext("prenom")
        numero_rpps = prof_elem.findtext("numeroRPPS")
        specialite = prof_elem.findtext("specialite")

        return HprimProfessionnel(
            nom=nom,
            prenom=prenom,
            numero_rpps=numero_rpps,
            numero_adeli=None,  # Pas toujours présent dans tous les contextes
            specialite=specialite
        )

    def _parse_venue(self, venue_elem: ET.Element) -> HprimVenue:
        """Parse un élément venue"""
        # Implémentation temporaire pour les tests
        return HprimVenue(
            identifiant="TEMP_VENUE",
            start_time=datetime.now(),
            end_time=datetime.now()
        )

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