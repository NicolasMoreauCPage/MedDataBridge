# app/services/hprim/hprim_service.py
"""
Service principal HPRIM
Orchestration des fonctionnalités de cotation des actes
"""

import logging
from decimal import Decimal
from xml.etree import ElementTree as ET
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

from app.hprim_models import (
    HprimMessage, HprimEnteteMessage, HprimPatient, HprimProfessionnel,
    HprimActeCCAM, HprimActeNGAP, HprimMessageType, HprimAction, HprimVenue,
    HprimMontant
)
from .hprim_validator import HprimValidator, HprimValidationError
from .hprim_xml import HprimXmlService

logger = logging.getLogger(__name__)


class HprimService:
    """Service principal pour la gestion HPRIM"""

    def __init__(self):
        self.validator = HprimValidator()
        self.xml_service = HprimXmlService()

    def creer_message_actes_ccam(
        self,
        emetteur_id: str,
        emetteur_nom: str,
        destinataire_id: str,
        destinataire_nom: str,
        patient: HprimPatient,
        acteur: HprimProfessionnel,
        actes: List[HprimActeCCAM],
        venue: Optional[HprimVenue] = None,
        message_id: Optional[str] = None
    ) -> HprimMessage:
        """
        Crée un message HPRIM pour des actes CCAM

        Args:
            emetteur_id: ID de l'émetteur (FINESS)
            emetteur_nom: Nom de l'émetteur
            destinataire_id: ID du destinataire (FINESS)
            destinataire_nom: Nom du destinataire
            patient: Informations patient
            acteur: Médecin acteur
            actes: Liste des actes CCAM
            venue: Informations de venue (optionnel)
            message_id: ID du message (auto-généré si None)

        Returns:
            Message HPRIM prêt à être généré
        """
        if not message_id:
            message_id = uuid4().hex[:17].upper()

        entete = HprimEnteteMessage(
            emetteur_id=emetteur_id,
            emetteur_nom=emetteur_nom,
            destinataire_id=destinataire_id,
            destinataire_nom=destinataire_nom,
            date_emission=datetime.now(),
            message_id=message_id,
            message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES
        )

        return HprimMessage(
            entete=entete,
            patient=patient,
            acteur=acteur,
            venue=venue,
            actes_ccam=actes
        )

    def valider_message(self, message: HprimMessage) -> List[HprimValidationError]:
        """
        Valide un message HPRIM complet

        Args:
            message: Message à valider

        Returns:
            Liste des erreurs de validation
        """
        return self.validator.validate_message_complet(message)

    def generer_xml(self, message: HprimMessage, valider: bool = True) -> str:
        """
        Génère le XML d'un message HPRIM

        Args:
            message: Message à convertir
            valider: Si True, valide avant génération

        Returns:
            XML string en ISO-8859-1

        Raises:
            HprimValidationError: Si validation échoue et valider=True
        """
        if valider:
            erreurs = self.valider_message(message)
            if erreurs:
                raise HprimValidationError(
                    "VALIDATION_FAILED",
                    f"Validation échouée: {len(erreurs)} erreur(s)",
                    "message"
                ) from erreurs[0]

        return self.xml_service.generate_xml(message)

    def traiter_message_xml(self, xml_string: str) -> Dict[str, Any]:
        """
        Traite un message XML entrant (parsing + validation)

        Args:
            xml_string: XML reçu

        Returns:
            Dictionnaire avec résultat du traitement
        """
        try:
            import time as _time
            start = _time.time()
            # Validation encodage
            if not self.xml_service.validate_encoding(xml_string):
                # Metrics (encoding error)
                try:
                    from app.metrics import record_hprim_validation
                    record_hprim_validation(
                        succes=False,
                        schema=None,
                        error_type="encoding",
                        direction="inbound",
                        duration_seconds=_time.time() - start,
                    )
                except Exception:
                    pass
                return {
                    "succes": False,
                    "erreur": "Encodage invalide (ISO-8859-1 requis)",
                    "type_erreur": "ENCODING"
                }

            # Validation XSD: déterminer automatiquement le schéma selon le root
            schema_auto = self.validator.guess_schema_name(xml_string) or 'evenements_serveur_actes'
            is_valid_xsd, xsd_errors = self.validator.validate_xml_string(
                xml_string,
                schema_name=schema_auto
            )
            # Toujours archiver le résultat de la validation XSD (même si KO)
            try:
                from app.metrics import record_hprim_validation
                record_hprim_validation(
                    succes=is_valid_xsd,
                    schema=schema_auto,
                    error_type=(None if is_valid_xsd else "xsd"),
                    direction="inbound",
                    duration_seconds=_time.time() - start,
                )
            except Exception:
                pass
            # Si XSD KO, on continue l'intégration mais on ajoute le résultat dans le retour
            xsd_result = {
                "xsd_valid": is_valid_xsd,
                "xsd_errors": xsd_errors if not is_valid_xsd else None,
                "schema_utilise": schema_auto
            }

            # Parsing XML (on tente même si XSD KO)
            message = self.xml_service.parse_xml(xml_string)

            # Validation contenu
            erreurs = self.valider_message(message)

            if erreurs:
                # Metrics (content error)
                try:
                    from app.metrics import record_hprim_validation
                    record_hprim_validation(
                        succes=False,
                        schema=schema_auto,
                        error_type="content",
                        direction="inbound",
                        duration_seconds=_time.time() - start,
                    )
                except Exception:
                    pass
                return {
                    "succes": False,
                    "erreur": f"Validation échouée: {len(erreurs)} erreur(s)",
                    "erreurs": [e.__dict__ for e in erreurs],
                    "type_erreur": "VALIDATION",
                    **xsd_result
                }

            # Metrics (success)
            try:
                from app.metrics import record_hprim_validation
                record_hprim_validation(
                    succes=True,
                    schema=schema_auto,
                    error_type=None,
                    direction="inbound",
                    duration_seconds=_time.time() - start,
                )
            except Exception:
                pass

            return {
                "succes": True,
                "message": message,
                "type_message": message.entete.message_type.value,
                **xsd_result
            }

        except Exception as e:
            logger.error(f"Erreur traitement XML: {e}")
            try:
                from app.metrics import record_hprim_validation
                record_hprim_validation(
                    succes=False,
                    schema=None,
                    error_type="processing",
                    direction="inbound",
                )
            except Exception:
                pass
            return {
                "succes": False,
                "erreur": str(e),
                "type_erreur": "TRAITEMENT"
            }

    def creer_acte_ccam_simple(
        self,
        code_acte: str,
        code_activite: str,
        code_phase: str,
        executant_rpps: str,
        date_execution: datetime,
        quantite: int = 1,
        modificateurs: Optional[List[str]] = None,
        montant: Optional[float] = None
    ) -> HprimActeCCAM:
        """
        Crée un acte CCAM simple avec les paramètres minimaux

        Args:
            code_acte: Code CCAM (AAAA999)
            code_activite: Code activité (01-99)
            code_phase: Code phase (00-99)
            executant_rpps: RPPS du médecin exécutant
            date_execution: Date d'exécution
            quantite: Quantité (défaut: 1)
            modificateurs: Liste des modificateurs (optionnel)
            montant: Montant en euros (optionnel)

        Returns:
            Objet HprimActeCCAM
        """
        # Créer l'exécutant
        executant = HprimProfessionnel(
            nom="INCONNU",  # À compléter avec les vraies données
            prenom="INCONNU",
            numero_rpps=executant_rpps
        )

        # Créer les modificateurs
        mods = []
        if modificateurs:
            from app.hprim_models import HprimModificateur
            for mod in modificateurs:
                mods.append(HprimModificateur(code=mod))

        # Créer le montant
        montant_obj = None
        if montant:
            from app.hprim_models import HprimMontant
            from decimal import Decimal
            montant_obj = HprimMontant(valeur=Decimal(str(montant)))

        # Générer l'identifiant
        identifiant = f"CCAM_{code_acte}_{date_execution.strftime('%Y%m%d_%H%M%S')}"

        return HprimActeCCAM(
            identifiant=identifiant,
            code_acte=code_acte,
            code_activite=code_activite,
            code_phase=code_phase,
            execute_date=date_execution,
            executant=executant,
            modificateurs=mods,
            quantite=quantite,
            montant=montant_obj
        )

    def creer_acte_ngap_simple(
        self,
        lettre_cle: str,
        coefficient: float,
        execute_date: datetime,
        prestataire_rpps: Optional[str] = None,
        denombrement: Optional[int] = None,
        position_dentaire: Optional[str] = None,
        execute_heure: Optional[str] = None,
        numero_seance: Optional[int] = None,
        nabms: Optional[List[int]] = None,
        minor_major: Optional[str] = None,
        montant: Optional[float] = None,
        commentaire: Optional[str] = None,
        bhn_phns: Optional[Dict[str, Any]] = None,
    ) -> HprimActeNGAP:
        prestataire = HprimProfessionnel(
            nom="INCONNU",
            prenom="INCONNU",
            numero_rpps=prestataire_rpps or "00000000000",
        )

        montant_obj = None
        if montant is not None:
            montant_obj = HprimMontant(valeur=Decimal(str(montant)))

        identifiant = f"NGAP_{lettre_cle}_{execute_date.strftime('%Y%m%d_%H%M%S')}"
        return HprimActeNGAP(
            identifiant=identifiant,
            lettre_cle=lettre_cle,
            coefficient=Decimal(str(coefficient)),
            execute_date=execute_date,
            prestataire=prestataire,
            denombrement=denombrement,
            position_dentaire=position_dentaire,
            execute_heure=execute_heure,
            numero_seance=numero_seance,
            nabms=nabms or [],
            minor_major=minor_major,
            montant=montant_obj,
            commentaire=commentaire,
            bhn_phns=bhn_phns,
        )

    def creer_message_actes_ngap(
        self,
        emetteur_id: str,
        emetteur_nom: str,
        destinataire_id: str,
        destinataire_nom: str,
        patient: HprimPatient,
        acteur: HprimProfessionnel,
        actes: List[HprimActeNGAP],
        venue: Optional[HprimVenue] = None,
        dossier_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> HprimMessage:
        if not message_id:
            message_id = uuid4().hex[:17].upper()

        entete = HprimEnteteMessage(
            emetteur_id=emetteur_id,
            emetteur_nom=emetteur_nom,
            destinataire_id=destinataire_id,
            destinataire_nom=destinataire_nom,
            date_emission=datetime.now(),
            message_id=message_id,
            message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES,
        )

        return HprimMessage(
            entete=entete,
            patient=patient,
            acteur=acteur,
            venue=venue,
            actes_ngap=actes,
        )

    def generer_acquittement(
        self,
        message_original: HprimMessage,
        statut: str = "OK",
        erreurs: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Génère un acquittement pour un message

        Args:
            message_original: Message original
            statut: Statut de l'acquittement (OK, ERREUR)
            erreurs: Liste des erreurs (optionnel)

        Returns:
            XML d'acquittement
        """
        root = ET.Element("acquittementServeurActes")
        entete = ET.SubElement(root, "entete")
        ET.SubElement(entete, "identifiantMessageOriginal").text = message_original.entete.message_id
        ET.SubElement(entete, "dateAcquittement").text = datetime.utcnow().isoformat()
        ET.SubElement(entete, "statut").text = statut

        erreurs_elem = ET.SubElement(root, "erreurs")
        for erreur in erreurs or []:
            erreur_elem = ET.SubElement(erreurs_elem, "erreur")
            ET.SubElement(erreur_elem, "code").text = str(erreur.get("code", "UNKNOWN"))
            ET.SubElement(erreur_elem, "message").text = str(erreur.get("message", ""))
            if erreur.get("field"):
                ET.SubElement(erreur_elem, "champ").text = str(erreur["field"])

        return ET.tostring(root, encoding="unicode")

    def get_statistiques_validation(self) -> Dict[str, Any]:
        """
        Retourne des statistiques sur les validations effectuées

        Returns:
            Dictionnaire de statistiques
        """
        # TODO: Implémenter les statistiques
        return {
            "validations_total": 0,
            "erreurs_total": 0,
            "types_erreur": {},
            "performance_moyenne": 0.0
        }