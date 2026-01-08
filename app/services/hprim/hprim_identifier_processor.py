# app/services/hprim/hprim_identifier_processor.py
"""
Service de traitement des identifiants HPRIM émetteur/destinataire.

Ce service applique la logique spécifique HPRIM pour classifier les identifiants
selon le contexte émission/réception :
- Réception : émetteur = externe, destinataire = interne
- Émission : émetteur = interne, destinataire = externe
"""

from typing import Dict, Optional, Tuple
from sqlmodel import Session

from app.services.identifier_namespace_classifier import classify_hprim_identifiers
from app.models_identifiers import IdentifierType
from app.hprim_models import HprimEnteteMessage


class HprimIdentifierProcessor:
    """Processeur des identifiants HPRIM émetteur/destinataire"""

    def __init__(self, session: Session, ej_id: int):
        self.session = session
        self.ej_id = ej_id

    def classify_entete_identifiers(
        self,
        entete: HprimEnteteMessage,
        is_emission: bool,
        emetteur_system: str = "FINESS",
        destinataire_system: str = "FINESS"
    ) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        Classifie les identifiants émetteur/destinataire d'un en-tête HPRIM.

        Args:
            entete: En-tête du message HPRIM
            is_emission: True si c'est une émission, False si c'est une réception
            emetteur_system: Système/namespace de l'émetteur (défaut: FINESS)
            destinataire_system: Système/namespace du destinataire (défaut: FINESS)

        Returns:
            Classification des identifiants :
            {
                "emetteur": (is_main_identifier, external_namespace),
                "destinataire": (is_main_identifier, external_namespace)
            }
        """
        return classify_hprim_identifiers(
            session=self.session,
            emetteur_id=entete.emetteur_id,
            emetteur_system=emetteur_system,
            destinataire_id=entete.destinataire_id,
            destinataire_system=destinataire_system,
            is_emission=is_emission,
            ej_id=self.ej_id,
            identifier_type=IdentifierType.IPP
        )

    def process_reception_identifiers(self, entete: HprimEnteteMessage) -> Dict[str, Dict]:
        """
        Traite les identifiants lors de la réception d'un message HPRIM.

        Logique : émetteur = externe, destinataire = interne (nous)

        Args:
            entete: En-tête du message reçu

        Returns:
            Informations de traitement des identifiants
        """
        classification = self.classify_entete_identifiers(entete, is_emission=False)

        return {
            "emetteur": {
                "id": entete.emetteur_id,
                "nom": entete.emetteur_nom,
                "is_main_identifier": classification["emetteur"][0],
                "external_namespace": classification["emetteur"][1],
                "classification": "EXTERNE" if not classification["emetteur"][0] else "INTERNE"
            },
            "destinataire": {
                "id": entete.destinataire_id,
                "nom": entete.destinataire_nom,
                "is_main_identifier": classification["destinataire"][0],
                "external_namespace": classification["destinataire"][1],
                "classification": "EXTERNE" if not classification["destinataire"][0] else "INTERNE"
            },
            "contexte": "RECEPTION",
            "logique": "émetteur=externe, destinataire=interne"
        }

    def process_emission_identifiers(self, entete: HprimEnteteMessage) -> Dict[str, Dict]:
        """
        Traite les identifiants lors de l'émission d'un message HPRIM.

        Logique : émetteur = interne (nous), destinataire = externe

        Args:
            entete: En-tête du message à émettre

        Returns:
            Informations de traitement des identifiants
        """
        classification = self.classify_entete_identifiers(entete, is_emission=True)

        return {
            "emetteur": {
                "id": entete.emetteur_id,
                "nom": entete.emetteur_nom,
                "is_main_identifier": classification["emetteur"][0],
                "external_namespace": classification["emetteur"][1],
                "classification": "EXTERNE" if not classification["emetteur"][0] else "INTERNE"
            },
            "destinataire": {
                "id": entete.destinataire_id,
                "nom": entete.destinataire_nom,
                "is_main_identifier": classification["destinataire"][0],
                "external_namespace": classification["destinataire"][1],
                "classification": "EXTERNE" if not classification["destinataire"][0] else "INTERNE"
            },
            "contexte": "EMISSION",
            "logique": "émetteur=interne, destinataire=externe"
        }