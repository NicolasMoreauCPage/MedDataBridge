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
    HprimMontant, HprimPriseCharge, HprimMessageType, HprimAction,
    HprimCivilite, HprimActeLPP, HprimActeUCD, HprimLPP, HprimUCD,
    HprimIntervention, HprimAcquittement, HprimReponse, HprimTypeActe
)

logger = logging.getLogger(__name__)

def _parse_hprim_datetime(value: Optional[str], *, xs_date: bool = False) -> datetime:
    """Parse une date HPRIM sans jamais la transformer ni en inventer une.

    Les dates d'acte HPRIM sont des ``xs:date`` et doivent donc être portées
    sous la forme ``YYYY-MM-DD``. Les valeurs compactes HL7 (``YYYYMMDD``),
    les jetons non résolus et les valeurs absentes sont volontairement refusés.
    ``dateHeureProduction`` reste, lui, une date-heure XML ISO 8601.
    """
    raw = (value or "").strip()
    expected = "xs:date (YYYY-MM-DD)" if xs_date else "xs:dateTime ISO 8601"
    if not raw or raw.startswith("$"):
        raise ValueError(f"Date HPRIM obligatoire au format {expected}")
    try:
        return datetime.strptime(raw, "%Y-%m-%d") if xs_date else datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"Date HPRIM invalide {raw!r} : format attendu {expected}") from exc


class HprimXmlService:
    """Service de génération/parsing XML HPRIM"""

    NAMESPACE = "http://www.hprim.org/hprimXML"
    NS = {"ns0": NAMESPACE}

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
        root = ET.Element("{%s}evenementsServeurActes" % self.NAMESPACE, version=message.version)

        # Attributs du root
        root.set("acquittementAttendu", "oui" if message.acquittement_attendu else "non")
        root.set("identifiantAttendu", "oui" if message.identifiant_attendu else "non")
        root.set("realise", "oui" if message.realise else "non")
        root.set("interrogation", "oui" if message.interrogation else "non")

        # En-tête
        entete = ET.SubElement(root, "{%s}enteteMessage" % self.NAMESPACE)
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
        """Ajoute l'en-tête du message

        Structure HPRIM adoptée : agents/agent/code/libelle
        Cette approche permet une modélisation générique des acteurs (émetteurs/destinataires)
        offrant plus de flexibilité que la structure simple id/nom.
        """
        # Identifiant et date
        ET.SubElement(parent, "{%s}identifiantMessage" % self.NAMESPACE).text = entete.message_id or "MSG001"
        ET.SubElement(parent, "{%s}dateHeureProduction" % self.NAMESPACE).text = entete.date_emission.isoformat()

        # Émetteur - Structure agents/agent pour flexibilité
        emetteur = ET.SubElement(parent, "{%s}emetteur" % self.NAMESPACE)
        agents = ET.SubElement(emetteur, "{%s}agents" % self.NAMESPACE)
        agent = ET.SubElement(agents, "{%s}agent" % self.NAMESPACE, categorie="acteur")
        ET.SubElement(agent, "{%s}code" % self.NAMESPACE).text = entete.emetteur_id
        ET.SubElement(agent, "{%s}libelle" % self.NAMESPACE).text = entete.emetteur_nom

        # Destinataire - Structure agents/agent pour flexibilité
        destinataire = ET.SubElement(parent, "{%s}destinataire" % self.NAMESPACE)
        agents = ET.SubElement(destinataire, "{%s}agents" % self.NAMESPACE)
        agent = ET.SubElement(agents, "{%s}agent" % self.NAMESPACE, categorie="acteur")
        ET.SubElement(agent, "{%s}code" % self.NAMESPACE).text = entete.destinataire_id
        ET.SubElement(agent, "{%s}libelle" % self.NAMESPACE).text = entete.destinataire_nom

    def _add_prenoms(self, parent: ET.Element, prenom: Optional[str]):
        if not prenom:
            return
        prenoms = ET.SubElement(parent, "{%s}prenoms" % self.NAMESPACE)
        ET.SubElement(prenoms, "{%s}prenom" % self.NAMESPACE).text = prenom

    def _add_civilite(self, parent: ET.Element, civilite: Optional[HprimCivilite]):
        if not civilite:
            return
        civilite_elem = ET.SubElement(parent, "{%s}civiliteHprim" % self.NAMESPACE, valeur=civilite.value)
        ET.SubElement(civilite_elem, "{%s}code" % self.NAMESPACE).text = civilite.value

    def _add_professionnel_sante(self, parent: ET.Element, prof: HprimProfessionnel):
        if prof.numero_adeli:
            ET.SubElement(parent, "{%s}numeroAdeli" % self.NAMESPACE).text = prof.numero_adeli
        elif prof.numero_rpps:
            ET.SubElement(parent, "{%s}noRPPS" % self.NAMESPACE).text = prof.numero_rpps

        personne = ET.SubElement(parent, "{%s}personne" % self.NAMESPACE)
        if prof.nom:
            ET.SubElement(personne, "{%s}nomUsuel" % self.NAMESPACE).text = prof.nom
        self._add_prenoms(personne, prof.prenom)
        self._add_civilite(personne, prof.civilite)

        if prof.specialite:
            specialite = ET.SubElement(parent, "{%s}specialiteHprim" % self.NAMESPACE)
            ET.SubElement(specialite, "{%s}libelle" % self.NAMESPACE).text = prof.specialite

    def _add_identifiant_simple(self, parent: ET.Element, value: Optional[str], tag: str = "emetteur"):
        if not value:
            return
        identifiant = ET.SubElement(parent, "{%s}identifiant" % self.NAMESPACE)
        node = ET.SubElement(identifiant, "{%s}%s" % (self.NAMESPACE, tag), portee="local")
        node.text = value

    def _add_patient_identifiant(self, parent: ET.Element, patient: HprimPatient):
        identifiant = ET.SubElement(parent, "{%s}identifiant" % self.NAMESPACE)
        identifiant_admin = patient.identifiant_administration_patient

        if identifiant_admin and identifiant_admin.emetteur and identifiant_admin.emetteur.valeur:
            emetteur = ET.SubElement(identifiant, "{%s}emetteur" % self.NAMESPACE)
            if identifiant_admin.emetteur.etat:
                emetteur.set("etat", identifiant_admin.emetteur.etat.value)
            if identifiant_admin.emetteur.portee:
                emetteur.set("portee", identifiant_admin.emetteur.portee.value)
            emetteur.set("referent", "oui" if identifiant_admin.emetteur.referent else "non")
            ET.SubElement(emetteur, "{%s}valeur" % self.NAMESPACE).text = identifiant_admin.emetteur.valeur
        elif patient.identifiant_id:
            emetteur = ET.SubElement(identifiant, "{%s}emetteur" % self.NAMESPACE, portee="local", etat="permanent", referent="oui")
            ET.SubElement(emetteur, "{%s}valeur" % self.NAMESPACE).text = patient.identifiant_id

        if identifiant_admin and identifiant_admin.numero_identifiant_sante:
            numero_identifiant_sante = ET.SubElement(identifiant, "{%s}numeroIdentifiantSante" % self.NAMESPACE)
            ins = identifiant_admin.numero_identifiant_sante
            if ins.identifiant:
                ET.SubElement(numero_identifiant_sante, "{%s}identifiant" % self.NAMESPACE).text = ins.identifiant
            for ins_c in ins.ins_c:
                ins_c_elem = ET.SubElement(numero_identifiant_sante, "{%s}insC" % self.NAMESPACE)
                ET.SubElement(ins_c_elem, "{%s}valeur" % self.NAMESPACE).text = ins_c.get("valeur")
                ET.SubElement(ins_c_elem, "{%s}dateEffet" % self.NAMESPACE).text = ins_c.get("date_effet")
            if ins.ins_a:
                ET.SubElement(numero_identifiant_sante, "{%s}insA" % self.NAMESPACE).text = ins.ins_a

        if identifiant_admin and identifiant_admin.numero_identifiant_patients:
            numeros = ET.SubElement(identifiant, "{%s}numeroIdentifiantPatients" % self.NAMESPACE)
            for numero in identifiant_admin.numero_identifiant_patients.numero_identifiant_patient:
                numero_elem = ET.SubElement(numeros, "{%s}numeroIdentifiantPatient" % self.NAMESPACE)
                ET.SubElement(numero_elem, "{%s}identifiant" % self.NAMESPACE).text = numero.identifiant
                autorite = ET.SubElement(numero_elem, "{%s}autorite" % self.NAMESPACE, type=numero.autorite.type_autorite.value)
                ET.SubElement(autorite, "{%s}nom" % self.NAMESPACE).text = numero.autorite.nom
                if numero.autorite.oid:
                    ET.SubElement(autorite, "{%s}OID" % self.NAMESPACE).text = numero.autorite.oid
                if numero.date_debut_validite:
                    ET.SubElement(numero_elem, "{%s}dateDebutValidite" % self.NAMESPACE).text = numero.date_debut_validite
                if numero.date_fin_validite:
                    ET.SubElement(numero_elem, "{%s}dateFinValidite" % self.NAMESPACE).text = numero.date_fin_validite

    def _add_montant(self, parent: ET.Element, montant_obj: Optional[HprimMontant], quantite: Optional[int] = None):
        if not montant_obj:
            return
        montant = ET.SubElement(parent, "{%s}montant" % self.NAMESPACE)
        ET.SubElement(montant, "{%s}montantTotal" % self.NAMESPACE).text = str(montant_obj.valeur)
        if quantite is not None:
            ET.SubElement(montant, "{%s}quantite" % self.NAMESPACE).text = str(quantite)

    def _format_xsd_time(self, raw_value: Optional[str]) -> Optional[str]:
        if not raw_value:
            return None
        if len(raw_value) == 5:
            return f"{raw_value}:00"
        return raw_value

        # Date et message
        # ET.SubElement(parent, "{%s}dateEmission" % self.NAMESPACE).text = entete.date_emission.isoformat()
        # message_elem = ET.SubElement(parent, "{%s}message" % self.NAMESPACE)
        # ET.SubElement(message_elem, "id").text = entete.message_id
        # ET.SubElement(message_elem, "type").text = entete.message_type.value

    def _add_evenement_actes_ccam(self, root: ET.Element, message: HprimMessage):
        """Ajoute un événement avec actes CCAM"""
        evenement = ET.SubElement(root, "{%s}evenementServeurActe" % self.NAMESPACE)

        # Date action
        ET.SubElement(evenement, "{%s}dateAction" % self.NAMESPACE).text = datetime.now().isoformat()

        # Acteur
        acteur = ET.SubElement(evenement, "{%s}acteur" % self.NAMESPACE)
        self._add_professionnel_sante(acteur, message.acteur)

        # Patient
        patient = ET.SubElement(evenement, "{%s}patient" % self.NAMESPACE)
        self._add_patient(patient, message.patient)

        # Venue
        if message.venue:
            venue = ET.SubElement(evenement, "{%s}venue" % self.NAMESPACE)
            self._add_venue(venue, message.venue)

        # Actes CCAM
        actes_ccam = ET.SubElement(evenement, "{%s}actesCCAM" % self.NAMESPACE)
        for acte in message.actes_ccam:
            self._add_acte_ccam(actes_ccam, acte)

    def _add_acte_ccam(self, parent: ET.Element, acte: HprimActeCCAM):
        """Ajoute un acte CCAM"""
        acte_elem = ET.SubElement(parent, "{%s}acteCCAM" % self.NAMESPACE)

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
        ET.SubElement(acte_elem, "{%s}dateAction" % self.NAMESPACE).text = datetime.now().isoformat()

        # Acteur
        acteur = ET.SubElement(acte_elem, "{%s}acteur" % self.NAMESPACE)
        self._add_professionnel_sante(acteur, acte.executant)

        # Identifiant
        self._add_identifiant_simple(acte_elem, acte.identifiant)

        # Codes acte
        ET.SubElement(acte_elem, "{%s}codeActe" % self.NAMESPACE).text = acte.code_acte
        if acte.code_acte_extension_pmsi:
            ET.SubElement(acte_elem, "{%s}codeActeExtensionPMSI" % self.NAMESPACE).text = acte.code_acte_extension_pmsi
        ET.SubElement(acte_elem, "{%s}codeActivite" % self.NAMESPACE).text = acte.code_activite
        if acte.code_phase:
            ET.SubElement(acte_elem, "{%s}codePhase" % self.NAMESPACE).text = acte.code_phase

        # Exécution
        execute = ET.SubElement(acte_elem, "{%s}execute" % self.NAMESPACE)
        ET.SubElement(execute, "{%s}date" % self.NAMESPACE).text = acte.execute_date.date().isoformat()
        if acte.execute_heure:
            ET.SubElement(execute, "{%s}heure" % self.NAMESPACE).text = self._format_xsd_time(acte.execute_heure)

        # Exécutant
        executant = ET.SubElement(acte_elem, "{%s}executant" % self.NAMESPACE)
        medecins = ET.SubElement(executant, "{%s}medecins" % self.NAMESPACE)
        medecin_executant = ET.SubElement(medecins, "{%s}medecinExecutant" % self.NAMESPACE, principal="oui")
        medecin = ET.SubElement(medecin_executant, "{%s}medecin" % self.NAMESPACE)
        self._add_professionnel_sante(medecin, acte.executant)

        # Modificateurs
        if acte.modificateurs:
            modificateurs = ET.SubElement(acte_elem, "{%s}modificateurs" % self.NAMESPACE)
            for mod in acte.modificateurs:
                mod_elem = ET.SubElement(modificateurs, "{%s}modificateur" % self.NAMESPACE)
                mod_elem.text = mod.code
                mod_elem.set("statut", mod.statut)

        # Quantité
        ET.SubElement(acte_elem, "{%s}quantite" % self.NAMESPACE).text = str(acte.quantite)

        # Prise en charge
        if acte.prise_charge:
            prise_charge = ET.SubElement(acte_elem, "{%s}priseCharge" % self.NAMESPACE)
            pc = acte.prise_charge
            if pc.risque:
                ET.SubElement(prise_charge, "{%s}risque" % self.NAMESPACE).text = pc.risque
            if pc.date_demande_accord:
                ET.SubElement(prise_charge, "{%s}dateDemandeAccord" % self.NAMESPACE).text = pc.date_demande_accord
            if pc.entente_prealable:
                prise_charge.set("ententePrealable", pc.entente_prealable)
            if pc.indicateur_parcours_soins:
                prise_charge.set("indicateurParcoursSoins", pc.indicateur_parcours_soins)

        # Montant
        self._add_montant(acte_elem, acte.montant, acte.quantite)

        # Commentaire
        if acte.commentaire:
            ET.SubElement(acte_elem, "{%s}commentaire" % self.NAMESPACE).text = acte.commentaire

    def _add_acte_ngap(self, parent: ET.Element, acte: HprimActeNGAP):
        """Ajoute un acte NGAP"""
        acte_elem = ET.SubElement(parent, "{%s}acteNGAP" % self.NAMESPACE)

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
        self._add_identifiant_simple(acte_elem, acte.identifiant)

        # Lettre clé
        ET.SubElement(acte_elem, "{%s}lettreCle" % self.NAMESPACE).text = acte.lettre_cle

        # Coefficient
        ET.SubElement(acte_elem, "{%s}coefficient" % self.NAMESPACE).text = str(acte.coefficient)

        # Dénombrement
        if acte.denombrement:
            ET.SubElement(acte_elem, "{%s}denombrement" % self.NAMESPACE).text = str(acte.denombrement)

        # Position dentaire
        if acte.position_dentaire:
            ET.SubElement(acte_elem, "{%s}positionDentaire" % self.NAMESPACE).text = acte.position_dentaire

        # Date exécution
        execute = ET.SubElement(acte_elem, "{%s}execute" % self.NAMESPACE)
        ET.SubElement(execute, "{%s}date" % self.NAMESPACE).text = acte.execute_date.date().isoformat()
        if acte.execute_heure:
            ET.SubElement(execute, "{%s}heure" % self.NAMESPACE).text = self._format_xsd_time(acte.execute_heure)

        # Prestataire
        prestataire = ET.SubElement(acte_elem, "{%s}prestataire" % self.NAMESPACE)
        medecins = ET.SubElement(prestataire, "{%s}medecins" % self.NAMESPACE)
        medecin = ET.SubElement(medecins, "{%s}medecin" % self.NAMESPACE)
        self._add_professionnel_sante(medecin, acte.prestataire)

        # Numéro séance
        if acte.numero_seance:
            ET.SubElement(acte_elem, "{%s}numeroSeance" % self.NAMESPACE).text = str(acte.numero_seance)

        # NABMS
        if acte.nabms:
            nabms = ET.SubElement(acte_elem, "{%s}NABMs" % self.NAMESPACE)
            for nabm in acte.nabms:
                ET.SubElement(nabms, "{%s}code" % self.NAMESPACE).text = str(nabm)

        # Montant
        self._add_montant(acte_elem, acte.montant)

        # Commentaire
        if acte.commentaire:
            ET.SubElement(acte_elem, "{%s}commentaire" % self.NAMESPACE).text = acte.commentaire

    def _add_patient(self, parent: ET.Element, patient: HprimPatient):
        """Ajoute les informations patient"""
        self._add_patient_identifiant(parent, patient)

        personne = ET.SubElement(parent, "{%s}personnePhysique" % self.NAMESPACE, sexe=patient.sexe or "I")
        if patient.nom:
            ET.SubElement(personne, "{%s}nomUsuel" % self.NAMESPACE).text = patient.nom
        self._add_prenoms(personne, patient.prenom)
        if patient.date_naissance:
            date_naissance = ET.SubElement(personne, "{%s}dateNaissance" % self.NAMESPACE)
            ET.SubElement(date_naissance, "{%s}date" % self.NAMESPACE).text = patient.date_naissance

    def _add_venue(self, parent: ET.Element, venue):
        """Ajoute les informations de venue"""
        identifiant = ET.SubElement(parent, "{%s}identifiant" % self.NAMESPACE)
        emetteur = ET.SubElement(identifiant, "{%s}emetteur" % self.NAMESPACE, portee="local", etat="permanent", referent="oui")
        ET.SubElement(emetteur, "{%s}valeur" % self.NAMESPACE).text = venue.identifiant

        entree = ET.SubElement(parent, "{%s}entree" % self.NAMESPACE)
        date_heure = ET.SubElement(entree, "{%s}dateHeureOptionnelle" % self.NAMESPACE)
        ET.SubElement(date_heure, "{%s}date" % self.NAMESPACE).text = datetime.now().date().isoformat()

    def _add_evenement_actes_ngap(self, root: ET.Element, message: HprimMessage):
        """Ajoute un événement avec actes NGAP"""
        evenement = ET.SubElement(root, "{%s}evenementServeurActe" % self.NAMESPACE)

        # Date action
        ET.SubElement(evenement, "{%s}dateAction" % self.NAMESPACE).text = datetime.now().isoformat()

        # Acteur
        acteur = ET.SubElement(evenement, "{%s}acteur" % self.NAMESPACE)
        self._add_professionnel_sante(acteur, message.acteur)

        # Patient
        patient = ET.SubElement(evenement, "{%s}patient" % self.NAMESPACE)
        self._add_patient(patient, message.patient)

        # Venue
        if message.venue:
            venue = ET.SubElement(evenement, "{%s}venue" % self.NAMESPACE)
            self._add_venue(venue, message.venue)

        # Actes NGAP
        actes_ngap = ET.SubElement(evenement, "{%s}actesNGAP" % self.NAMESPACE)
        for acte in message.actes_ngap:
            self._add_acte_ngap(actes_ngap, acte)

    def _add_evenement_actes_lpp(self, root: ET.Element, message: HprimMessage):
        """Ajoute un événement avec actes LPP"""
        evenement = self._add_evenement_context(root, message, "evenementServeurLPP")
        lpps = ET.SubElement(evenement, "{%s}LPPs" % self.NAMESPACE)
        acte_lpp = message.actes_lpp
        acte_id = acte_lpp.identifiant if isinstance(acte_lpp, HprimActeLPP) else message.entete.message_id
        for lpp in (acte_lpp.lpps if isinstance(acte_lpp, HprimActeLPP) else acte_lpp or []):
            self._add_lpp(lpps, lpp, acte_id, message)

    def _add_evenement_actes_ucd(self, root: ET.Element, message: HprimMessage):
        """Ajoute un événement avec actes UCD"""
        evenement = self._add_evenement_context(root, message, "evenementServeurUCD")
        ucds = ET.SubElement(evenement, "{%s}UCDs" % self.NAMESPACE)
        acte_ucd = message.actes_ucd
        acte_id = acte_ucd.identifiant if isinstance(acte_ucd, HprimActeUCD) else message.entete.message_id
        for ucd in (acte_ucd.ucds if isinstance(acte_ucd, HprimActeUCD) else acte_ucd or []):
            self._add_ucd(ucds, ucd, acte_id, message)

    def _add_evenement_interventions(self, root: ET.Element, message: HprimMessage):
        """Ajoute un événement avec interventions"""
        for intervention in message.interventions:
            evenement = self._add_evenement_context(root, message, "evenementServeurIntervention")
            evenement.set("action", "creation")
            intervention_elem = ET.SubElement(evenement, "{%s}intervention" % self.NAMESPACE)
            self._add_identifiant_simple(intervention_elem, intervention.identifiant)
            debut = ET.SubElement(intervention_elem, "{%s}debut" % self.NAMESPACE)
            ET.SubElement(debut, "{%s}date" % self.NAMESPACE).text = intervention.date_intervention.date().isoformat()
            if intervention.libelle:
                ET.SubElement(intervention_elem, "{%s}libelle" % self.NAMESPACE).text = intervention.libelle

    def _add_evenement_context(self, root: ET.Element, message: HprimMessage, event_tag: str) -> ET.Element:
        """Ajoute la partie commune des événements de cotation."""
        evenement = ET.SubElement(root, "{%s}%s" % (self.NAMESPACE, event_tag))
        ET.SubElement(evenement, "{%s}dateAction" % self.NAMESPACE).text = datetime.now().isoformat()
        acteur = ET.SubElement(evenement, "{%s}acteur" % self.NAMESPACE)
        self._add_professionnel_sante(acteur, message.acteur)
        patient = ET.SubElement(evenement, "{%s}patient" % self.NAMESPACE)
        self._add_patient(patient, message.patient)
        if message.venue:
            venue = ET.SubElement(evenement, "{%s}venue" % self.NAMESPACE)
            self._add_venue(venue, message.venue)
        return evenement

    def _add_lpp(self, parent: ET.Element, acte: HprimLPP, acte_id: str, message: HprimMessage) -> None:
        """Ajoute une LPP dans l'ordre imposé par le XSD HPRIM 2.4."""
        lpp = ET.SubElement(parent, "{%s}LPP" % self.NAMESPACE)
        lpp.set("action", HprimAction.CREATION.value)
        ET.SubElement(lpp, "{%s}dateAction" % self.NAMESPACE).text = datetime.now().isoformat()
        self._add_identifiant_simple(lpp, acte_id)
        date_pose = ET.SubElement(lpp, "{%s}datePose" % self.NAMESPACE)
        ET.SubElement(date_pose, "{%s}date" % self.NAMESPACE).text = datetime.now().date().isoformat()
        code = ET.SubElement(lpp, "{%s}codeLPP" % self.NAMESPACE, portee=acte.code.portee)
        code.text = acte.code.code
        fournisseur = ET.SubElement(lpp, "{%s}identifiantFournisseur" % self.NAMESPACE)
        ET.SubElement(fournisseur, "{%s}code" % self.NAMESPACE).text = message.entete.emetteur_id[:17]
        ET.SubElement(fournisseur, "{%s}libelle" % self.NAMESPACE).text = message.entete.emetteur_nom[:120]
        ET.SubElement(lpp, "{%s}montantUnitaireFactureTTC" % self.NAMESPACE).text = str(acte.prix_unitaire)
        ET.SubElement(lpp, "{%s}quantite" % self.NAMESPACE).text = str(acte.quantite)
        if acte.libelle:
            denomination = ET.SubElement(lpp, "{%s}denomination" % self.NAMESPACE)
            ET.SubElement(denomination, "{%s}libelle" % self.NAMESPACE).text = acte.libelle[:80]

    def _add_ucd(self, parent: ET.Element, acte: HprimUCD, acte_id: str, message: HprimMessage) -> None:
        """Ajoute une UCD dans l'ordre imposé par le XSD HPRIM 2.4."""
        ucd = ET.SubElement(parent, "{%s}UCD" % self.NAMESPACE)
        ucd.set("action", HprimAction.CREATION.value)
        ET.SubElement(ucd, "{%s}dateAction" % self.NAMESPACE).text = datetime.now().isoformat()
        self._add_identifiant_simple(ucd, acte_id)
        date = ET.SubElement(ucd, "{%s}date" % self.NAMESPACE)
        ET.SubElement(date, "{%s}date" % self.NAMESPACE).text = datetime.now().date().isoformat()
        prescripteur = ET.SubElement(ucd, "{%s}prescripteur" % self.NAMESPACE)
        medecin = ET.SubElement(prescripteur, "{%s}medecin" % self.NAMESPACE)
        self._add_professionnel_sante(medecin, message.acteur)
        ET.SubElement(ucd, "{%s}codeUCD" % self.NAMESPACE).text = acte.code
        ET.SubElement(ucd, "{%s}montantEcartIndemnisable" % self.NAMESPACE).text = "0"
        ET.SubElement(ucd, "{%s}montantUnitaireFactureTTC" % self.NAMESPACE).text = str(acte.prix_unitaire)
        ET.SubElement(ucd, "{%s}quantiteFractionnee" % self.NAMESPACE).text = str(acte.quantite)
        denomination = ET.SubElement(ucd, "{%s}denomination" % self.NAMESPACE)
        ET.SubElement(denomination, "{%s}libelle" % self.NAMESPACE).text = acte.designation[:80]

    def _generate_acquittements_serveur_actes(self, message: HprimMessage) -> str:
        """Génère un acquittement HPRIM 2.4 conforme au XSD officiel."""
        if not message.acquittement:
            raise ValueError("Un acquittement HPRIM doit contenir son statut et le message acquitté")
        ack = message.acquittement
        ack_status = {"OK": "ok", "AVERTISSEMENT": "avt", "ERREUR": "err", "REJET": "rj"}.get(
            ack.statut.upper(), ack.statut.lower()
        )
        root = ET.Element("{%s}acquittementsServeurActes" % self.NAMESPACE, version=message.version)
        entete = ET.SubElement(root, "{%s}enteteMessage" % self.NAMESPACE, statut=ack_status)
        self._add_entete_message(entete, message.entete)
        ET.SubElement(entete, "{%s}identifiantMessageAcquitte" % self.NAMESPACE).text = ack.message_id_original[:12]

        reponses = list(ack.reponses_actes) + list(ack.reponses_interventions)
        if reponses:
            container = ET.SubElement(root, "{%s}reponses" % self.NAMESPACE)
            patient = ET.SubElement(container, "{%s}patient" % self.NAMESPACE)
            self._add_patient(patient, message.patient)
            if message.venue:
                venue = ET.SubElement(container, "{%s}venue" % self.NAMESPACE)
                self._add_venue(venue, message.venue)
            for response in reponses:
                self._add_acquittement_reponse(container, response)
        return self._xml_to_string(root)

    def _add_acquittement_reponse(self, parent: ET.Element, response: HprimReponse) -> None:
        """Ajoute une réponse d'acquittement, en conservant le type d'acte."""
        status = {"OK": "ok", "AVERTISSEMENT": "avt", "ERREUR": "err"}.get(
            response.statut.upper(), response.statut.lower()
        )
        reponse = ET.SubElement(parent, "{%s}reponse" % self.NAMESPACE, statut=status)
        if response.codeErreur:
            reponse.set("codeErreur", response.codeErreur)
        type_acte = response.type_acte.value if isinstance(response.type_acte, HprimTypeActe) else str(response.type_acte)
        if type_acte == "LPP":
            content = ET.SubElement(reponse, "{%s}LPP" % self.NAMESPACE, valide="oui" if status == "ok" else "non")
            self._add_identifiant_simple(content, response.identifiant_acte)
            date_pose = ET.SubElement(content, "{%s}datePose" % self.NAMESPACE)
            ET.SubElement(date_pose, "{%s}date" % self.NAMESPACE).text = datetime.now().date().isoformat()
            code = ET.SubElement(content, "{%s}codeLPP" % self.NAMESPACE, portee="n")
            code.text = response.code
        elif type_acte == "UCD":
            content = ET.SubElement(reponse, "{%s}UCD" % self.NAMESPACE, valide="oui" if status == "ok" else "non")
            self._add_identifiant_simple(content, response.identifiant_acte)
            date = ET.SubElement(content, "{%s}date" % self.NAMESPACE)
            ET.SubElement(date, "{%s}date" % self.NAMESPACE).text = datetime.now().date().isoformat()
            # Le XSD d'acquittement limite codeUCD à 7 chiffres. Un CIP-13
            # reçu est donc renvoyé dans l'alternative codeCommercial afin de
            # préserver sa valeur tout en restant conforme au schéma.
            code_tag = "codeUCD" if response.code.isdigit() and len(response.code) <= 7 else "codeCommercial"
            ET.SubElement(content, "{%s}%s" % (self.NAMESPACE, code_tag)).text = response.code
        else:
            raise ValueError(f"Acquittement HPRIM non supporté pour le type {type_acte}")
        if response.messageErreur:
            erreur = ET.SubElement(reponse, "{%s}erreur" % self.NAMESPACE)
            ET.SubElement(erreur, "{%s}code" % self.NAMESPACE).text = (response.codeErreur or "erreur")[:17]
            ET.SubElement(erreur, "{%s}libelle" % self.NAMESPACE).text = response.messageErreur[:120]

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
            # Les exports historiques HPRIM 1.x rencontrés en recette ne
            # déclarent pas systématiquement l'espace de noms HPRIM. Le
            # modèle de lecture interne, lui, utilise des recherches
            # qualifiées. On le rétablit ici *après* le parsing : le XML
            # d'origine reste inchangé pour la validation XSD et pour
            # l'archivage, tandis que la lecture métier fonctionne de la même
            # façon avec les deux écritures.
            self._qualify_legacy_namespace(root)

            # Déterminer le type de message (gérer les namespaces)
            tag_local = root.tag.split('}')[-1] if '}' in root.tag else root.tag
            if tag_local == "evenementsServeurActes":
                return self._parse_evenements_serveur_actes(root)
            elif tag_local == "acquittementsServeurActes":
                return self._parse_acquittements_serveur_actes(root)
            else:
                raise ValueError(f"Type de message XML non supporté: {root.tag}")

        except ET.ParseError as e:
            raise ValueError(f"Erreur de parsing XML: {e}")
        except Exception as e:
            raise ValueError(f"Erreur lors du parsing HPRIM: {e}")

    def _qualify_legacy_namespace(self, root: ET.Element) -> None:
        """Ajoute le namespace HPRIM aux éléments non qualifiés d'un export.

        HPRIM XML 2.4 est namespacé, mais des flux HPRIM 1.06/2.00 encore
        utilisés par les éditeurs omettent ce préfixe. Ne pas le faire ici
        faisait créer un en-tête de secours (dont ``message_type`` était une
        chaîne), puis échouer l'intégration avec ``.value`` ou avec un patient
        fictif. Les attributs ne sont volontairement pas touchés.
        """
        for element in root.iter():
            if not element.tag.startswith("{"):
                element.tag = f"{{{self.NAMESPACE}}}{element.tag}"

    def _parse_acquittements_serveur_actes(self, root: ET.Element) -> HprimMessage:
        """Parse un acquittement HPRIM 2.4 sans le confondre avec un événement."""
        entete_elem = root.find(f"{{{self.NAMESPACE}}}enteteMessage")
        if entete_elem is None:
            raise ValueError("En-tête absent de l'acquittement HPRIM")
        entete = self._parse_entete_message(entete_elem)
        entete.message_type = HprimMessageType.ACQUITTEMENTS_SERVEUR_ACTES
        original_id = entete_elem.findtext(f"{{{self.NAMESPACE}}}identifiantMessageAcquitte", "")
        responses: List[HprimReponse] = []
        for response_elem in root.findall(f".//{{{self.NAMESPACE}}}reponse"):
            status = response_elem.get("statut", "err")
            code_error = response_elem.get("codeErreur")
            error_text = response_elem.findtext(
                f"{{{self.NAMESPACE}}}erreur/{{{self.NAMESPACE}}}libelle"
            )
            for tag, act_type, code_tag in (
                ("LPP", HprimTypeActe.LPP, "codeLPP"),
                ("UCD", HprimTypeActe.UCD, "codeUCD"),
            ):
                content = response_elem.find(f"{{{self.NAMESPACE}}}{tag}")
                if content is None:
                    continue
                act_id = content.findtext(
                    f"{{{self.NAMESPACE}}}identifiant/{{{self.NAMESPACE}}}emetteur/{{{self.NAMESPACE}}}valeur", ""
                )
                code = content.findtext(f"{{{self.NAMESPACE}}}{code_tag}", "")
                responses.append(HprimReponse(act_id, act_type, code, status, code_error, error_text))

        patient_elem = root.find(f".//{{{self.NAMESPACE}}}reponses/{{{self.NAMESPACE}}}patient")
        patient = self._parse_patient(patient_elem) if patient_elem is not None else HprimPatient(
            identifiant_id="ACK", identifiant_clef="", nom="ACQUITTEMENT", prenom="HPRIM"
        )
        return HprimMessage(
            entete=entete,
            patient=patient,
            acteur=HprimProfessionnel(nom="ACQUITTEMENT", prenom="HPRIM"),
            acquittement=HprimAcquittement(
                statut=entete_elem.get("statut", "err"),
                message_id_original=original_id,
                date_acquittement=entete.date_emission,
                reponses_actes=responses,
            ),
        )

    def _parse_evenements_serveur_actes(self, root: ET.Element) -> HprimMessage:
        """Parse un message evenementsServeurActes"""
        # Attributs du root
        version = root.get("version", "2.4")
        acquittement_attendu = root.get("acquittementAttendu", "oui") == "oui"
        identifiant_attendu = root.get("identifiantAttendu", "oui") == "oui"
        realise = root.get("realise", "non") == "oui"
        interrogation = root.get("interrogation", "non") == "oui"

        # En-tête
        entete_elem = root.find(".//{http://www.hprim.org/hprimXML}enteteMessage")
        if entete_elem is None:
            # En-tête manquant - créer une structure par défaut pour les tests
            from app.hprim_models import HprimEnteteMessage
            entete = HprimEnteteMessage(
                emetteur_id="TEST_EMETTEUR",
                emetteur_nom="Test Emetteur",
                destinataire_id="TEST_DESTINATAIRE", 
                destinataire_nom="Test Destinataire",
                date_emission=datetime.now(),
                message_id="TEST_MSG",
                message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES
            )
            logger.warning("En-tête de message manquant dans le XML HPRIM - utilisation de valeurs par défaut")
        else:
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
        
        event_tags = (
            "evenementServeurActe",
            "evenementServeurLPP",
            "evenementServeurUCD",
        )
        for evenement in (
            node
            for tag in event_tags
            for node in root.findall(f".//{{{self.NAMESPACE}}}{tag}")
        ):
            # Extraire patient et acteur du premier événement
            if patient is None:
                patient_elem = evenement.find(".//{http://www.hprim.org/hprimXML}patient")
                if patient_elem is not None:
                    patient = self._parse_patient(patient_elem)
                    
            if acteur is None:
                acteur_elem = evenement.find(".//{http://www.hprim.org/hprimXML}acteur")
                if acteur_elem is not None:
                    medecin_elem = acteur_elem.find(".//{http://www.hprim.org/hprimXML}medecin")
                    if medecin_elem is not None:
                        acteur = self._parse_professionnel(medecin_elem)
                    else:
                        acteur = self._parse_professionnel(acteur_elem)
                    
            if venue is None:
                venue_elem = evenement.find(".//{http://www.hprim.org/hprimXML}venue")
                if venue_elem is not None:
                    venue = self._parse_venue(venue_elem)
            
            # Déterminer le type d'acte en cherchant les conteneurs spécifiques
            if evenement.find(".//{http://www.hprim.org/hprimXML}actesNGAP") is not None:
                actes_ngap.extend(self._parse_actes_ngap(evenement))
            if evenement.find(".//{http://www.hprim.org/hprimXML}actesCCAM") is not None:
                actes_ccam.extend(self._parse_actes_ccam(evenement))
            if evenement.find(".//{http://www.hprim.org/hprimXML}LPPs") is not None:
                actes_lpp.extend(self._parse_actes_lpp(evenement))
            if evenement.find(".//{http://www.hprim.org/hprimXML}UCDs") is not None:
                actes_ucd.extend(self._parse_actes_ucd(evenement))

        if patient is None or acteur is None:
            # Pour les données de test incomplètes, créer des objets par défaut
            if patient is None:
                patient = HprimPatient(
                    identifiant_id="TEST_PATIENT",
                    identifiant_clef="CLEF_TEST",
                    nom="TEST",
                    prenom="Patient",
                    date_naissance="1900-01-01",
                    sexe="U"
                )
                logger.warning("Patient manquant dans le message HPRIM - utilisation de valeurs par défaut")
            
            if acteur is None:
                acteur = HprimProfessionnel(
                    nom="TEST",
                    prenom="Acteur", 
                    numero_rpps="00000000000",
                    numero_adeli="0A0000000",
                    specialite="Test"
                )
                logger.warning("Acteur manquant dans le message HPRIM - utilisation de valeurs par défaut")

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
        emetteur = entete_elem.find(".//{http://www.hprim.org/hprimXML}emetteur")
        destinataire = entete_elem.find(".//{http://www.hprim.org/hprimXML}destinataire")

        # Valeurs par défaut pour les tests
        emetteur_id = "TEST_EMETTEUR"
        emetteur_nom = "Test Emetteur"
        destinataire_id = "TEST_DESTINATAIRE"
        destinataire_nom = "Test Destinataire"

        if emetteur is not None:
            # Essayer différentes structures pour l'emetteur
            emetteur_agent = emetteur.find(".//{http://www.hprim.org/hprimXML}agent[@categorie='application']")
            if emetteur_agent is None:
                emetteur_agent = emetteur.find(".//{http://www.hprim.org/hprimXML}agent")

            if emetteur_agent is not None:
                code_elem = emetteur_agent.find(".//{http://www.hprim.org/hprimXML}code")
                libelle_elem = emetteur_agent.find(".//{http://www.hprim.org/hprimXML}libelle")
                if code_elem is not None and code_elem.text:
                    emetteur_id = code_elem.text
                if libelle_elem is not None and libelle_elem.text:
                    emetteur_nom = libelle_elem.text

        if destinataire is not None:
            # Essayer différentes structures pour le destinataire
            destinataire_agent = destinataire.find(".//{http://www.hprim.org/hprimXML}agent[@categorie='application']")
            if destinataire_agent is None:
                destinataire_agent = destinataire.find(".//{http://www.hprim.org/hprimXML}agent")

            if destinataire_agent is not None:
                code_elem = destinataire_agent.find(".//{http://www.hprim.org/hprimXML}code")
                libelle_elem = destinataire_agent.find(".//{http://www.hprim.org/hprimXML}libelle")
                if code_elem is not None and code_elem.text:
                    destinataire_id = code_elem.text
                if libelle_elem is not None and libelle_elem.text:
                    destinataire_nom = libelle_elem.text

        date_value = entete_elem.findtext(".//{http://www.hprim.org/hprimXML}dateHeureProduction")
        date_emission = _parse_hprim_datetime(date_value)
        
        # Parser l'identifiant du message
        message_id_elem = entete_elem.find(".//{http://www.hprim.org/hprimXML}identifiantMessage")
        message_id = message_id_elem.text if message_id_elem is not None and message_id_elem.text else "MSG001"

        return HprimEnteteMessage(
            message_id=message_id,
            date_emission=date_emission,
            emetteur_id=emetteur_id,
            emetteur_nom=emetteur_nom,
            destinataire_id=destinataire_id,
            destinataire_nom=destinataire_nom,
            message_type=(
                HprimMessageType.ACQUITTEMENTS_SERVEUR_ACTES
                if entete_elem.get("statut") else HprimMessageType.EVENEMENTS_SERVEUR_ACTES
            )
        )

    def _parse_actes_ccam(self, evenement: ET.Element) -> List[HprimActeCCAM]:
        """Parse les actes CCAM d'un événement"""
        actes = []
        actes_ccam_elem = evenement.find(".//{http://www.hprim.org/hprimXML}actesCCAM")
        if actes_ccam_elem is not None:
            for acte_elem in actes_ccam_elem.findall(".//{http://www.hprim.org/hprimXML}acteCCAM"):
                acte = self._parse_acte_ccam(acte_elem)
                actes.append(acte)
        return actes

    def _parse_acte_ccam(self, acte_elem: ET.Element) -> HprimActeCCAM:
        """Parse un acte CCAM"""
        # Attributs
        action_str = acte_elem.get("action", "CREATION")
        # Normaliser accents pour compatibilité
        if action_str.lower() in ("création", "Création"):
            action_str = "creation"
        action = HprimAction(action_str.upper() if action_str.isupper() else action_str.lower())
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
        identifiant_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}identifiant/{http://www.hprim.org/hprimXML}emetteur")
        identifiant = identifiant_elem.text if identifiant_elem is not None and identifiant_elem.text else ""
        valeur_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}identifiant/{http://www.hprim.org/hprimXML}emetteur/{http://www.hprim.org/hprimXML}valeur")
        if valeur_elem is not None and valeur_elem.text:
            identifiant = valeur_elem.text

        # Codes acte
        code_acte = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codeActe", "")
        code_acte_extension_pmsi = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codeActeExtensionPMSI", None)
        code_activite = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codeActivite", "")
        # Normaliser le code activité à 2 chiffres pour les tests
        if code_activite and len(code_activite) == 1:
            code_activite = f"0{code_activite}"
        code_phase = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codePhase", "")
        # Normaliser le code phase à 2 chiffres pour les tests
        if code_phase and len(code_phase) == 1:
            code_phase = f"0{code_phase}"

        # Exécution
        execute_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}execute")
        date_str = execute_elem.findtext(".//{http://www.hprim.org/hprimXML}date") if execute_elem is not None else None
        execute_date = _parse_hprim_datetime(date_str, xs_date=True)
        execute_heure = (
            execute_elem.findtext(".//{http://www.hprim.org/hprimXML}heure")
            if execute_elem is not None else None
        )

        # Exécutant
        executant_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}executant/{http://www.hprim.org/hprimXML}medecins/{http://www.hprim.org/hprimXML}medecinExecutant/{http://www.hprim.org/hprimXML}medecin")
        if executant_elem is None:
            executant_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}executant/{http://www.hprim.org/hprimXML}medecins/{http://www.hprim.org/hprimXML}medecin")
        executant = None
        if executant_elem is not None:
            executant = self._parse_professionnel(executant_elem)
        else:
            # Exécutant manquant - utiliser une valeur par défaut
            executant = HprimProfessionnel(
                nom="EXECUTANT_INCONNU",
                prenom="",
                numero_rpps="00000000000",
                numero_adeli="0A0000000",
                specialite="Inconnue"
            )
            logger.warning("Exécutant manquant dans l'acte CCAM - utilisation de valeurs par défaut")

        # Modificateurs
        modificateurs = []
        modificateurs_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}modificateurs")
        if modificateurs_elem is not None:
            for mod_elem in modificateurs_elem.findall(".//{http://www.hprim.org/hprimXML}modificateur"):
                if mod_elem.text:
                    modificateurs.append(HprimModificateur(
                        code=mod_elem.text,
                        statut=mod_elem.get("statut", "nft")
                    ))

        # Quantité
        quantite = int(acte_elem.findtext(".//{http://www.hprim.org/hprimXML}quantite", "1"))

        # Prise en charge
        prise_charge = None
        prise_charge_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}priseCharge")
        if prise_charge_elem is not None:
            prise_charge = HprimPriseCharge(
                risque=prise_charge_elem.findtext(".//{http://www.hprim.org/hprimXML}risque"),
                date_demande_accord=prise_charge_elem.findtext(".//{http://www.hprim.org/hprimXML}dateDemandeAccord"),
                entente_prealable=prise_charge_elem.get("ententePrealable"),
                indicateur_parcours_soins=prise_charge_elem.get("indicateurParcoursSoins")
            )

        # Montant
        montant = None
        montant_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}montant")
        if montant_elem is not None:
            valeur_str = montant_elem.findtext(".//{http://www.hprim.org/hprimXML}montantTotal")
            if not valeur_str:
                valeur_str = montant_elem.findtext(".//{http://www.hprim.org/hprimXML}valeur")
            devise = montant_elem.findtext(".//{http://www.hprim.org/hprimXML}devise", "EUR")
            if valeur_str:
                montant = HprimMontant(valeur=Decimal(valeur_str), devise=devise)

        # Commentaire
        commentaire = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}commentaire")

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
        actes_ngap_elem = evenement.find(".//{http://www.hprim.org/hprimXML}actesNGAP")
        if actes_ngap_elem is not None:
            for acte_elem in actes_ngap_elem.findall(".//{http://www.hprim.org/hprimXML}acteNGAP"):
                acte = self._parse_acte_ngap(acte_elem)
                actes.append(acte)
        return actes

    def _parse_acte_ngap(self, acte_elem: ET.Element) -> HprimActeNGAP:
        """Parse un acte NGAP"""
        # Attributs
        action_str = acte_elem.get("action", "CREATION")
        if action_str.lower() in ("création", "Création"):
            action_str = "creation"
        action = HprimAction(action_str.upper() if action_str.isupper() else action_str.lower())
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
        identifiant = acte_elem.findtext("identifiant", "")
        if not identifiant:
            identifiant = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}identifiant/{http://www.hprim.org/hprimXML}emetteur", "")
        valeur_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}identifiant/{http://www.hprim.org/hprimXML}emetteur/{http://www.hprim.org/hprimXML}valeur")
        if valeur_elem is not None and valeur_elem.text:
            identifiant = valeur_elem.text
        lettre_cle = acte_elem.findtext("{%s}lettreCle" % self.NAMESPACE, "")
        coefficient_str = acte_elem.findtext("{%s}coefficient" % self.NAMESPACE, "1.0")
        coefficient = Decimal(coefficient_str) if coefficient_str else Decimal("1.0")
        execute_date_str = acte_elem.findtext("dateExecution")
        if not execute_date_str:
            execute_date_str = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}execute/{http://www.hprim.org/hprimXML}date")
        execute_date = _parse_hprim_datetime(execute_date_str, xs_date=True)

        # Prestataire
        prestataire_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}prestataire/{http://www.hprim.org/hprimXML}medecins/{http://www.hprim.org/hprimXML}medecin")
        if prestataire_elem is None:
            # Essayer sans namespace pour prestataire
            prestataire_elem = acte_elem.find(".//prestataire/{http://www.hprim.org/hprimXML}medecin")
        if prestataire_elem is None:
            # Essayer sans namespace du tout
            prestataire_elem = acte_elem.find(".//medecin")
        
        if prestataire_elem is not None:
            prestataire = self._parse_professionnel(prestataire_elem)
        else:
            # Prestataire manquant - utiliser l'acteur du message ou une valeur par défaut
            prestataire = HprimProfessionnel(
                nom="PRESTATAIRE_INCONNU",
                prenom="",
                numero_rpps="00000000000",
                numero_adeli="0A0000000",
                specialite="Inconnue"
            )
            logger.warning("Prestataire manquant dans l'acte NGAP - utilisation de valeurs par défaut")

        # Éléments optionnels
        denombrement = None
        denombrement_elem = acte_elem.find("denombrement")
        if denombrement_elem is not None and denombrement_elem.text:
            denombrement = int(denombrement_elem.text)

        position_dentaire = acte_elem.findtext("{%s}positionDentaire" % self.NAMESPACE, None)
        execute_heure = acte_elem.findtext("heureExecution", None)
        if not execute_heure:
            execute_heure = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}execute/{http://www.hprim.org/hprimXML}heure", None)

        numero_seance = None
        numero_seance_elem = acte_elem.find("numeroSeance")
        if numero_seance_elem is not None and numero_seance_elem.text:
            numero_seance = int(numero_seance_elem.text)

        # NABMS
        nabms = []
        nabms_elem = acte_elem.find("nabms")
        if nabms_elem is None:
            nabms_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}NABMs")
        if nabms_elem is not None:
            for nabm_elem in nabms_elem.findall("nabm") + nabms_elem.findall("{http://www.hprim.org/hprimXML}code"):
                if nabm_elem.text:
                    nabms.append(int(nabm_elem.text))

        # Minor/Major
        minor_major = acte_elem.findtext("minorMajor", None)
        if minor_major is None:
            minor_major_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}minorMajor")
            if minor_major_elem is not None:
                if minor_major_elem.find(".//{http://www.hprim.org/hprimXML}majoration") is not None:
                    minor_major = "majoration"
                elif minor_major_elem.find(".//{http://www.hprim.org/hprimXML}minoration") is not None:
                    minor_major = "minoration"

        # Montant
        montant = None
        montant_elem = acte_elem.find("montant")
        if montant_elem is None:
            montant_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}montant")
        if montant_elem is not None:
            valeur_str = montant_elem.findtext("{%s}montantTotal" % self.NAMESPACE, None)
            if valeur_str is None:
                valeur_str = montant_elem.findtext("{%s}valeur" % self.NAMESPACE, None)
            devise = montant_elem.findtext("{%s}devise" % self.NAMESPACE, "EUR")
            if valeur_str:
                montant = HprimMontant(valeur=Decimal(valeur_str), devise=devise)

        # Commentaire
        commentaire = acte_elem.findtext("{%s}commentaire" % self.NAMESPACE)

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
            minor_major=minor_major,
            montant=montant,
            commentaire=commentaire,
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
        actes_lpp_elem = evenement.find(".//{http://www.hprim.org/hprimXML}LPPs")
        if actes_lpp_elem is not None:
            for acte_elem in actes_lpp_elem.findall("{http://www.hprim.org/hprimXML}LPP"):
                acte = self._parse_acte_lpp(acte_elem)
                actes.append(acte)
        return actes

    def _parse_acte_lpp(self, acte_elem: ET.Element) -> Any:
        """Parse un acte LPP"""
        from types import SimpleNamespace
        
        # Attributs
        action_str = acte_elem.get("action", "creation")
        if action_str.lower() in ("création", "Création"):
            action_str = "creation"
        
        facturable = acte_elem.get("facturable", "oui") == "oui"
        valide = acte_elem.get("valide", "non") == "oui"
        facture = acte_elem.get("facture", "non")
        gratuit = acte_elem.get("gratuit") == "oui"
        
        # Identifiant
        identifiant = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}identifiant", "")
        
        # Codes LPP (obligatoire: montant unitaire facturé TTC)
        code_interne_lpp = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codeInterneLPP", None)
        code_lpp = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codeLPP", None)
        code_commercial_lpp = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codeCommercialLPP", None)
        
        # Dénomination
        denomination_libelle = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}denomination/{http://www.hprim.org/hprimXML}libelle", None)
        
        # Date d'exécution (obligatoire)
        execute_date_str = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}datePose/{http://www.hprim.org/hprimXML}date")
        execute_date = _parse_hprim_datetime(execute_date_str, xs_date=True)
        
        # Quantité (obligatoire)
        quantite_str = acte_elem.findtext("{http://www.hprim.org/hprimXML}quantite", "1")
        quantite = int(quantite_str) if quantite_str else 1
        
        # Montants (montant unitaire facturé TTC obligatoire)
        montant_unitaire_facture_ttc_str = acte_elem.findtext("{http://www.hprim.org/hprimXML}montantUnitaireFactureTTC", "0.0")
        montant_value = Decimal(montant_unitaire_facture_ttc_str) if montant_unitaire_facture_ttc_str else Decimal("0.0")
        montant = SimpleNamespace(valeur=montant_value, devise="EUR") if montant_value else None
        
        # Prise en charge
        risque = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}priseCharge/{http://www.hprim.org/hprimXML}risque", None)
        entente_prealable = acte_elem.get("ententePrealable", None)
        indicateur_parcours_soins = acte_elem.get("indicateurParcoursSoins", None)
        date_demande_accord_str = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}priseCharge/{http://www.hprim.org/hprimXML}dateDemandeAccord")
        date_demande_accord = date_demande_accord_str if date_demande_accord_str else None
        
        # Fournisseur
        siret_fournisseur = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}siretFournisseur", None)
        
        # Autres champs
        nature_prestation = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}naturePrestation", None)
        numero_lot = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}numeroLot", None)
        numero_serie = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}numeroSerie", None)
        iud_id = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}IUD", None)
        commentaire = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}commentaire")
        
        return SimpleNamespace(
            identifiant=identifiant,
            code_interne_lpp=code_interne_lpp,
            code_lpp=code_lpp,
            code_commercial_lpp=code_commercial_lpp,
            denomination_libelle=denomination_libelle,
            execute_date=execute_date,
            quantite=quantite,
            montant=montant,
            risque=risque,
            entente_prealable=entente_prealable,
            indicateur_parcours_soins=indicateur_parcours_soins,
            date_demande_accord=date_demande_accord,
            siret_fournisseur=siret_fournisseur,
            nature_prestation=nature_prestation,
            numero_lot=numero_lot,
            numero_serie=numero_serie,
            iud_id=iud_id,
            commentaire=commentaire,
            action=action_str,
            facturable=facturable,
            valide=valide,
            facture=facture,
            gratuit=gratuit
        )

    def _parse_actes_ucd(self, evenement: ET.Element) -> List[Any]:
        """Parse les actes UCD d'un événement"""
        actes = []
        actes_ucd_elem = evenement.find(".//{http://www.hprim.org/hprimXML}UCDs")
        if actes_ucd_elem is not None:
            for acte_elem in actes_ucd_elem.findall("{http://www.hprim.org/hprimXML}UCD"):
                acte = self._parse_acte_ucd(acte_elem)
                actes.append(acte)
        return actes

    def _parse_acte_ucd(self, acte_elem: ET.Element) -> Any:
        """Parse un acte UCD"""
        from types import SimpleNamespace
        
        # Attributs
        action_str = acte_elem.get("action", "creation")
        if action_str.lower() in ("création", "Création"):
            action_str = "creation"
        
        facturable = acte_elem.get("facturable", "oui") == "oui"
        valide = acte_elem.get("valide", "non") == "oui"
        facture = acte_elem.get("facture", "non")
        gratuit = acte_elem.get("gratuit") == "oui"
        liberal = acte_elem.get("liberal") == "oui"
        retrocession = acte_elem.get("retrocession") == "oui"
        essai_therapeutique = acte_elem.get("essaiTherapeutique") == "oui"
        
        # Identifiant
        identifiant = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}identifiant", "")
        
        # Codes UCD (Code CIP-13 obligatoire)
        code_interne_ucd = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codeInterneUCD", None)
        code_ucd = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codeUCD", None)
        code_commercial = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codeCommercial", None)
        
        # Dénomination
        denomination_libelle = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}denomination/{http://www.hprim.org/hprimXML}libelle", None)
        denomination_dosage = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}denomination/{http://www.hprim.org/hprimXML}dosage", None)
        denomination_forme = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}denomination/{http://www.hprim.org/hprimXML}forme", None)
        
        # Date (obligatoire) avec nature optionnelle
        execute_elem = acte_elem.find(".//{http://www.hprim.org/hprimXML}date")
        date_str = execute_elem.findtext(".//{http://www.hprim.org/hprimXML}date") if execute_elem is not None else None
        execute_date = _parse_hprim_datetime(date_str, xs_date=True)
        nature_date = execute_elem.get("natureDate", None) if execute_elem is not None else None
        
        # Quantité fractionnée (obligatoire)
        quantite_str = acte_elem.findtext("{http://www.hprim.org/hprimXML}quantiteFractionnee", "1")
        quantite = float(quantite_str) if quantite_str else 1.0
        
        # Montants
        taux_tva_str = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}montant/{http://www.hprim.org/hprimXML}tauxTVA")
        taux_tva = float(taux_tva_str) if taux_tva_str else None
        
        montant_unitaire_facture_ttc_str = acte_elem.findtext("{http://www.hprim.org/hprimXML}montantUnitaireFactureTTC", "0.0")
        montant_value = Decimal(montant_unitaire_facture_ttc_str) if montant_unitaire_facture_ttc_str else Decimal("0.0")
        montant = SimpleNamespace(valeur=montant_value, devise="EUR") if montant_value else None
        
        # Prise en charge
        risque = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}priseCharge/{http://www.hprim.org/hprimXML}risque", None)
        entente_prealable = acte_elem.get("ententePrealable", None)
        indicateur_parcours_soins = acte_elem.get("indicateurParcoursSoins", None)
        date_demande_accord_str = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}priseCharge/{http://www.hprim.org/hprimXML}dateDemandeAccord")
        date_demande_accord = date_demande_accord_str if date_demande_accord_str else None
        
        # Fournisseur
        siret_fournisseur = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}siretFournisseur", None)
        numero_lot = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}numeroLot", None)
        
        # Autres champs
        nature_prestation = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}naturePrestation", None)
        code_indication_les = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}codeIndicationLES", None)
        commentaire = acte_elem.findtext(".//{http://www.hprim.org/hprimXML}commentaire")
        
        return SimpleNamespace(
            identifiant=identifiant,
            code_interne_ucd=code_interne_ucd,
            code_ucd=code_ucd,
            code_commercial=code_commercial,
            denomination_libelle=denomination_libelle,
            denomination_dosage=denomination_dosage,
            denomination_forme=denomination_forme,
            execute_date=execute_date,
            nature_date=nature_date,
            quantite=quantite,
            montant=montant,
            taux_tva=taux_tva,
            risque=risque,
            entente_prealable=entente_prealable,
            indicateur_parcours_soins=indicateur_parcours_soins,
            date_demande_accord=date_demande_accord,
            siret_fournisseur=siret_fournisseur,
            numero_lot=numero_lot,
            nature_prestation=nature_prestation,
            code_indication_les=code_indication_les,
            commentaire=commentaire,
            action=action_str,
            facturable=facturable,
            valide=valide,
            facture=facture,
            gratuit=gratuit,
            liberal=liberal,
            retrocession=retrocession,
            essai_therapeutique=essai_therapeutique
        )

    def _parse_patient(self, patient_elem: ET.Element) -> HprimPatient:
        """Parse un élément patient"""
        # Identifiant
        identifiant_elem = patient_elem.find(".//{http://www.hprim.org/hprimXML}identifiant")
        if identifiant_elem is not None:
            identifiant_id = identifiant_elem.findtext(".//{http://www.hprim.org/hprimXML}id")
            if not identifiant_id:
                identifiant_id = identifiant_elem.findtext(".//{http://www.hprim.org/hprimXML}emetteur/{http://www.hprim.org/hprimXML}valeur")
            if not identifiant_id:
                # Un acte de suppression peut ne présenter que l'identifiant
                # récepteur : c'est toujours un identifiant patient valide et
                # doit être accepté au même titre que l'émetteur.
                identifiant_id = identifiant_elem.findtext(".//{http://www.hprim.org/hprimXML}recepteur/{http://www.hprim.org/hprimXML}valeur")
            if not identifiant_id:
                identifiant_id = identifiant_elem.findtext(".//{http://www.hprim.org/hprimXML}numeroIdentifiantPatient/{http://www.hprim.org/hprimXML}identifiant")
            identifiant_clef = identifiant_elem.findtext(".//{http://www.hprim.org/hprimXML}clef")
            # Gérer le cas où findtext retourne un dict
            identifiant_id = identifiant_id if isinstance(identifiant_id, str) else None
            identifiant_clef = identifiant_clef if isinstance(identifiant_clef, str) else None
        else:
            identifiant_id = None
            identifiant_clef = None

        # Informations de base
        nom = patient_elem.findtext(".//{http://www.hprim.org/hprimXML}nom")
        if not nom:
            nom = patient_elem.findtext(".//{http://www.hprim.org/hprimXML}personnePhysique/{http://www.hprim.org/hprimXML}nomUsuel")
        prenom = patient_elem.findtext(".//{http://www.hprim.org/hprimXML}prenom")
        if not prenom:
            prenom = patient_elem.findtext(".//{http://www.hprim.org/hprimXML}personnePhysique/{http://www.hprim.org/hprimXML}prenoms/{http://www.hprim.org/hprimXML}prenom")
        date_naissance = patient_elem.findtext(".//{http://www.hprim.org/hprimXML}dateNaissance")
        if date_naissance:
            date_naissance = date_naissance.strip()
        if not date_naissance:
            date_naissance = patient_elem.findtext(".//{http://www.hprim.org/hprimXML}dateNaissance/{http://www.hprim.org/hprimXML}date")
        sexe = patient_elem.findtext(".//{http://www.hprim.org/hprimXML}sexe")
        personne_physique = patient_elem.find(".//{http://www.hprim.org/hprimXML}personnePhysique")
        if personne_physique is not None:
            sexe = personne_physique.get("sexe") or sexe

        # Gérer le cas où findtext retourne un dict
        nom = nom if isinstance(nom, str) else None
        prenom = prenom if isinstance(prenom, str) else None
        date_naissance = date_naissance if isinstance(date_naissance, str) else None
        sexe = sexe if isinstance(sexe, str) else None

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
        nom = prof_elem.findtext(".//{http://www.hprim.org/hprimXML}nom")
        if not nom:
            nom = prof_elem.findtext(".//{http://www.hprim.org/hprimXML}personne/{http://www.hprim.org/hprimXML}nomUsuel")
        prenom = prof_elem.findtext(".//{http://www.hprim.org/hprimXML}prenom")
        if not prenom:
            prenom = prof_elem.findtext(".//{http://www.hprim.org/hprimXML}personne/{http://www.hprim.org/hprimXML}prenoms/{http://www.hprim.org/hprimXML}prenom")
        numero_rpps = prof_elem.findtext(".//{http://www.hprim.org/hprimXML}numeroRPPS")
        if not numero_rpps:
            numero_rpps = prof_elem.findtext(".//{http://www.hprim.org/hprimXML}noRPPS")
        specialite = prof_elem.findtext(".//{http://www.hprim.org/hprimXML}specialite")
        if not specialite:
            specialite = prof_elem.findtext(".//{http://www.hprim.org/hprimXML}specialiteHprim/{http://www.hprim.org/hprimXML}libelle")

        # Gérer le cas où findtext retourne un dict au lieu d'une string (namespace issue)
        nom = nom if isinstance(nom, str) else None
        prenom = prenom if isinstance(prenom, str) else None
        numero_rpps = numero_rpps if isinstance(numero_rpps, str) else None
        specialite = specialite if isinstance(specialite, str) else None

        return HprimProfessionnel(
            nom=nom,
            prenom=prenom,
            numero_rpps=numero_rpps,
            numero_adeli=prof_elem.findtext(".//{http://www.hprim.org/hprimXML}numeroAdeli"),
            specialite=specialite
        )

    def _parse_venue(self, venue_elem: ET.Element) -> HprimVenue:
        """Parse un élément venue"""
        # Extraire l'identifiant et le libellé
        identifiant = venue_elem.findtext(".//{http://www.hprim.org/hprimXML}identifiant", "")
        if not identifiant:
            identifiant = venue_elem.findtext(".//{http://www.hprim.org/hprimXML}identifiant/{http://www.hprim.org/hprimXML}emetteur/{http://www.hprim.org/hprimXML}valeur", "")
        if not identifiant:
            identifiant = venue_elem.findtext(".//{http://www.hprim.org/hprimXML}identifiant/{http://www.hprim.org/hprimXML}recepteur/{http://www.hprim.org/hprimXML}valeur", "")
        if not identifiant:
            identifiant = venue_elem.findtext(".//{http://www.hprim.org/hprimXML}numeroIdentifiantVenue/{http://www.hprim.org/hprimXML}identifiant", "")
        libelle = venue_elem.findtext(".//{http://www.hprim.org/hprimXML}libelle", "")
        
        # Si pas d'identifiant, utiliser une valeur par défaut
        if not identifiant:
            identifiant = "VENUE_UNKNOWN"
        if not libelle:
            libelle = "Venue inconnue"
            
        return HprimVenue(
            identifiant=identifiant,
            libelle=libelle
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
