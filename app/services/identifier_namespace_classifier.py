"""
Service de classification des identifiants basée sur les espaces de noms EJ.

Ce service détermine si un identifiant entrant doit être traité comme
identifiant principal ou identifiant externe selon que son namespace
correspond à celui de l'Entité Juridique (EJ) ou non.
"""

from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import select, Session

from app.models_structure import EntiteJuridique
from app.models_structure import Lit, Chambre, UniteHebergement, UniteFonctionnelle, Service, Pole
from app.models_structure import IdentifierNamespace
from app.models_identifiers import IdentifierType


# Types d'entités autorisés pour la classification EJ
# Un namespace par type d'entité dans la structure et c'est tout
ALLOWED_ENTITY_TYPES = {
    'patient',      # identite (IPP, PI, PG)
    'dossier',      # dossier (NDA, NA, NDP) 
    'venue',        # venue (VN)
    'mouvement',    # mouvement (MVT)
    'contact'       # contacts (PC - NK1-33)
}


class IdentifierNamespaceClassifier:
    """
    Classe pour classifier les identifiants selon les namespaces EJ.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_ej_namespaces(self, ej_id: int, identifier_type: Optional[IdentifierType] = None) -> List[IdentifierNamespace]:
        """
        Récupère tous les namespaces configurés pour une EJ donnée.

        Args:
            ej_id: ID de l'Entité Juridique
            identifier_type: Type d'identifiant (optionnel, pour filtrer)

        Returns:
            Liste des IdentifierNamespace pour cette EJ
        """
        stmt = select(IdentifierNamespace).where(IdentifierNamespace.entite_juridique_id == ej_id)

        if identifier_type:
            stmt = stmt.where(IdentifierNamespace.type == identifier_type.value)

        return self.session.exec(stmt).all()

    def get_hierarchical_namespaces(
        self,
        lit_id: Optional[int] = None,
        chambre_id: Optional[int] = None,
        unite_hebergement_id: Optional[int] = None,
        unite_fonctionnelle_id: Optional[int] = None,
        service_id: Optional[int] = None,
        pole_id: Optional[int] = None,
        entite_geographique_id: Optional[int] = None,
        entite_juridique_id: Optional[int] = None,
        ght_context_id: Optional[int] = None,
        identifier_type: Optional[IdentifierType] = None
    ) -> List[IdentifierNamespace]:
        """
        Récupère tous les namespaces configurés selon la hiérarchie structurelle,
        du plus spécifique au plus général.

        Args:
            lit_id: ID du lit (niveau le plus spécifique)
            chambre_id: ID de la chambre
            unite_hebergement_id: ID de l'unité d'hébergement
            unite_fonctionnelle_id: ID de l'unité fonctionnelle
            service_id: ID du service
            pole_id: ID du pôle
            entite_geographique_id: ID de l'entité géographique
            entite_juridique_id: ID de l'entité juridique
            ght_context_id: ID du contexte GHT (niveau le plus général)
            identifier_type: Type d'identifiant (optionnel, pour filtrer)

        Returns:
            Liste des IdentifierNamespace triés du plus spécifique au plus général
        """
        conditions = []
        
        # Ajouter les conditions pour chaque niveau hiérarchique
        if lit_id:
            conditions.append(IdentifierNamespace.lit_id == lit_id)
        if chambre_id:
            conditions.append(IdentifierNamespace.chambre_id == chambre_id)
        if unite_hebergement_id:
            conditions.append(IdentifierNamespace.unite_hebergement_id == unite_hebergement_id)
        if unite_fonctionnelle_id:
            conditions.append(IdentifierNamespace.unite_fonctionnelle_id == unite_fonctionnelle_id)
        if service_id:
            conditions.append(IdentifierNamespace.service_id == service_id)
        if pole_id:
            conditions.append(IdentifierNamespace.pole_id == pole_id)
        if entite_geographique_id:
            conditions.append(IdentifierNamespace.entite_geographique_id == entite_geographique_id)
        if entite_juridique_id:
            conditions.append(IdentifierNamespace.entite_juridique_id == entite_juridique_id)
        if ght_context_id:
            conditions.append(IdentifierNamespace.ght_context_id == ght_context_id)

        if not conditions:
            return []

        # Construire la requête avec OR entre les niveaux
        from sqlmodel import or_
        stmt = select(IdentifierNamespace).where(or_(*conditions))

        if identifier_type:
            stmt = stmt.where(IdentifierNamespace.type == identifier_type.value)

        return self.session.exec(stmt).all()

    def get_namespaces_for_location(
        self,
        lit_id: Optional[int] = None,
        chambre_id: Optional[int] = None,
        unite_hebergement_id: Optional[int] = None,
        unite_fonctionnelle_id: Optional[int] = None,
        service_id: Optional[int] = None,
        pole_id: Optional[int] = None,
        entite_geographique_id: Optional[int] = None,
        entite_juridique_id: Optional[int] = None,
        ght_context_id: Optional[int] = None,
        identifier_type: Optional[IdentifierType] = None
    ) -> List[IdentifierNamespace]:
        """
        Récupère tous les namespaces applicables à un emplacement structurel donné,
        en traversant la hiérarchie du plus spécifique au plus général.

        Args:
            lit_id: ID du lit (si fourni, récupère aussi les namespaces des niveaux supérieurs)
            chambre_id: ID de la chambre
            unite_hebergement_id: ID de l'unité d'hébergement
            unite_fonctionnelle_id: ID de l'unité fonctionnelle
            service_id: ID du service
            pole_id: ID du pôle
            entite_geographique_id: ID de l'entité géographique
            entite_juridique_id: ID de l'entité juridique
            ght_context_id: ID du contexte GHT
            identifier_type: Type d'identifiant (optionnel)

        Returns:
            Liste des IdentifierNamespace du plus spécifique au plus général
        """
        # Collecter tous les IDs de la hiérarchie
        hierarchy_ids = {
            'lit_id': lit_id,
            'chambre_id': chambre_id,
            'unite_hebergement_id': unite_hebergement_id,
            'unite_fonctionnelle_id': unite_fonctionnelle_id,
            'service_id': service_id,
            'pole_id': pole_id,
            'entite_geographique_id': entite_geographique_id,
            'entite_juridique_id': entite_juridique_id,
            'ght_context_id': ght_context_id,
        }

        # Si on a un lit, récupérer la hiérarchie complète
        if lit_id:
            lit = self.session.get(Lit, lit_id)
            if lit:
                hierarchy_ids['chambre_id'] = lit.chambre_id
                if lit.chambre:
                    hierarchy_ids['unite_hebergement_id'] = lit.chambre.unite_hebergement_id
                    if lit.chambre.unite_hebergement:
                        hierarchy_ids['unite_fonctionnelle_id'] = lit.chambre.unite_hebergement.unite_fonctionnelle_id
                        if lit.chambre.unite_hebergement.unite_fonctionnelle:
                            hierarchy_ids['service_id'] = lit.chambre.unite_hebergement.unite_fonctionnelle.service_id
                            if lit.chambre.unite_hebergement.unite_fonctionnelle.service:
                                hierarchy_ids['pole_id'] = lit.chambre.unite_hebergement.unite_fonctionnelle.service.pole_id
                                if lit.chambre.unite_hebergement.unite_fonctionnelle.service.pole:
                                    hierarchy_ids['entite_geographique_id'] = lit.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo_id
                                    if lit.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo:
                                        hierarchy_ids['entite_juridique_id'] = lit.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo.entite_juridique_id
                                        if lit.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo.entite_juridique:
                                            hierarchy_ids['ght_context_id'] = lit.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo.entite_juridique.ght_context_id

        # Et ainsi de suite pour les autres niveaux... (simplifié pour l'exemple)
        # Pour l'instant, on utilise la méthode existante
        return self.get_hierarchical_namespaces(
            identifier_type=identifier_type,
            **hierarchy_ids
        )

    def is_ej_namespace(self, system: str, ej_id: int, identifier_type: Optional[IdentifierType] = None) -> bool:
        """
        Vérifie si un système/namespace correspond à un namespace configuré pour l'EJ.

        Args:
            system: Le système/namespace de l'identifiant
            ej_id: ID de l'Entité Juridique
            identifier_type: Type d'identifiant (optionnel)

        Returns:
            True si le namespace correspond à l'EJ, False sinon
        """
        ej_namespaces = self.get_ej_namespaces(ej_id, identifier_type)

        for ns in ej_namespaces:
            if ns.system == system or ns.oid == system:
                return True

        return False

    def classify_identifier(
        self,
        value: str,
        system: str,
        identifier_type: IdentifierType,
        ej_id: Optional[int] = None,
        location_hierarchy: Optional[Dict[str, Optional[int]]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Classifie un identifiant comme principal ou externe selon la hiérarchie des namespaces.

        Args:
            value: Valeur de l'identifiant
            system: Système/namespace de l'identifiant
            identifier_type: Type d'identifiant
            ej_id: ID de l'EJ (optionnel, pour compatibilité)
            location_hierarchy: Hiérarchie structurelle complète (optionnel)

        Returns:
            Tuple (is_main_identifier, external_namespace)
            - is_main_identifier: True si doit être identifiant principal
            - external_namespace: Le namespace externe si différent, None sinon
        """
        # Utiliser la hiérarchie structurelle si fournie, sinon Solution de repli vers EJ
        if location_hierarchy:
            applicable_namespaces = self.get_hierarchical_namespaces(
                identifier_type=identifier_type,
                **location_hierarchy
            )
        elif ej_id:
            # Solution de repli vers la logique EJ existante
            applicable_namespaces = self.get_ej_namespaces(ej_id, identifier_type)
        else:
            return True, None  # Par défaut, traiter comme principal si pas de contexte

        # Vérifier si le namespace correspond à un namespace applicable
        for ns in applicable_namespaces:
            if ns.system == system or ns.oid == system:
                return True, None  # Identifiant principal
            # Vérifier aussi le code (compatibilité)
            if hasattr(ns, 'code') and ns.code == system:
                return True, None

        return False, system  # Identifiant externe

    def classify_hprim_identifiers(
        self,
        emetteur_id: str,
        emetteur_system: str,
        destinataire_id: str,
        destinataire_system: str,
        is_emission: bool,
        ej_id: int,
        identifier_type: IdentifierType = IdentifierType.IPP
    ) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        Classifie les identifiants émetteur/destinataire HPRIM selon le contexte émission/réception.

        Logique HPRIM :
        - En RÉCEPTION : émetteur = externe (autre établissement), destinataire = interne (nous)
        - En ÉMISSION : émetteur = interne (nous), destinataire = externe (autre établissement)

        Args:
            emetteur_id: ID de l'émetteur
            emetteur_system: Système/namespace de l'émetteur
            destinataire_id: ID du destinataire
            destinataire_system: Système/namespace du destinataire
            is_emission: True si c'est une émission, False si c'est une réception
            ej_id: ID de l'entité juridique locale
            identifier_type: Type d'identifiant (défaut: EJ pour établissements)

        Returns:
            Dictionnaire avec classification pour émetteur et destinataire :
            {
                "emetteur": (is_main_identifier, external_namespace),
                "destinataire": (is_main_identifier, external_namespace)
            }
        """
        # Récupérer les namespaces de l'EJ locale
        ej_namespaces = self.get_ej_namespaces(ej_id, identifier_type)

        def _is_local_namespace(system: str) -> bool:
            """Vérifie si un système correspond aux namespaces locaux"""
            for ns in ej_namespaces:
                if ns.system == system or ns.oid == system:
                    return True
            return False

        result = {}

        if is_emission:
            # ÉMISSION : émetteur = interne (nous), destinataire = externe
            result["emetteur"] = (True, None)  # Toujours principal pour l'émetteur en émission
            result["destinataire"] = (_is_local_namespace(destinataire_system), destinataire_system)
        else:
            # RÉCEPTION : émetteur = externe, destinataire = interne (nous)
            result["emetteur"] = (_is_local_namespace(emetteur_system), emetteur_system)
            result["destinataire"] = (True, None)  # Toujours principal pour le destinataire en réception

        return result

    def process_patient_identifiers(
        self,
        identifiers_data: List[Tuple[str, str, IdentifierType]],
        ej_id: Optional[int] = None,
        location_hierarchy: Optional[Dict[str, Optional[int]]] = None
    ) -> Dict[str, Any]:
        """
        Traite une liste d'identifiants patient et les classe selon la hiérarchie.

        Args:
            identifiers_data: Liste de tuples (value, system, type)
            ej_id: ID de l'EJ (optionnel, pour compatibilité)
            location_hierarchy: Hiérarchie structurelle complète (optionnel)

        Returns:
            Dict avec 'main_identifier', 'external_id', 'external_identifiers'
        """
        result = {
            'main_identifier': None,
            'external_id': None,
            'external_identifiers': []
        }

        for value, system, id_type in identifiers_data:
            is_main, external_ns = self.classify_identifier(value, system, id_type, ej_id, location_hierarchy)

            if is_main:
                # Utiliser comme identifiant principal
                if result['main_identifier'] is None:
                    result['main_identifier'] = value
            else:
                # Traiter comme identifiant externe
                result['external_identifiers'].append({
                    'value': value,
                    'system': system,
                    'type': id_type,
                    'external_namespace': external_ns
                })

                # Si pas d'identifiant principal, utiliser le premier externe comme external_id
                if result['external_id'] is None:
                    result['external_id'] = value

        return result

    def process_dossier_identifiers(
        self,
        identifiers_data: List[Tuple[str, str, IdentifierType]],
        ej_id: Optional[int] = None,
        location_hierarchy: Optional[Dict[str, Optional[int]]] = None
    ) -> Dict[str, Any]:
        """
        Traite une liste d'identifiants dossier (NDA).
        """
        result = {
            'main_identifier': None,
            'external_identifiers': []
        }

        for value, system, id_type in identifiers_data:
            is_main, external_ns = self.classify_identifier(value, system, id_type, ej_id, location_hierarchy)

            if is_main:
                if result['main_identifier'] is None:
                    result['main_identifier'] = value
            else:
                result['external_identifiers'].append({
                    'value': value,
                    'system': system,
                    'type': id_type,
                    'external_namespace': external_ns
                })

        return result

    def process_venue_identifiers(
        self,
        identifiers_data: List[Tuple[str, str, IdentifierType]],
        ej_id: Optional[int] = None,
        location_hierarchy: Optional[Dict[str, Optional[int]]] = None
    ) -> Dict[str, Any]:
        """
        Traite une liste d'identifiants venue (VN).
        """
        # Logique similaire à dossier
        return self.process_dossier_identifiers(identifiers_data, ej_id, location_hierarchy)

    def process_mouvement_identifiers(
        self,
        identifiers_data: List[Tuple[str, str, IdentifierType]],
        ej_id: Optional[int] = None,
        location_hierarchy: Optional[Dict[str, Optional[int]]] = None
    ) -> Dict[str, Any]:
        """
        Traite une liste d'identifiants mouvement (MVT).
        """
        # Logique similaire à dossier
        return self.process_dossier_identifiers(identifiers_data, ej_id, location_hierarchy)


def classify_incoming_identifiers(
    session: Session,
    identifiers_data: List[Tuple[str, str, IdentifierType]],
    entity_type: str,
    ej_id: Optional[int] = None,
    location_hierarchy: Optional[Dict[str, Optional[int]]] = None
) -> Dict[str, Any]:
    """
    Fonction utilitaire pour classifier des identifiants entrants selon la hiérarchie structurelle.
    
    Seuls les types d'entités suivants sont autorisés pour la classification :
    - patient (identite)
    - dossier  
    - venue
    - mouvement
    - contact

    Args:
        session: Session DB
        identifiers_data: Liste de tuples (value, system, type)
        entity_type: Type d'entité ('patient', 'dossier', 'venue', 'mouvement', 'contact')
        ej_id: ID de l'EJ (optionnel, pour compatibilité)
        location_hierarchy: Hiérarchie structurelle complète (optionnel)

    Returns:
        Dict avec la classification des identifiants
    """
    # Vérifier que le type d'entité est autorisé
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise ValueError(f"Type d'entité non autorisé pour la classification : {entity_type}. "
                        f"Types autorisés: {', '.join(sorted(ALLOWED_ENTITY_TYPES))}")
    
    classifier = IdentifierNamespaceClassifier(session)

    if entity_type == 'patient':
        return classifier.process_patient_identifiers(identifiers_data, ej_id, location_hierarchy)
    elif entity_type == 'dossier':
        return classifier.process_dossier_identifiers(identifiers_data, ej_id, location_hierarchy)
    elif entity_type == 'venue':
        return classifier.process_venue_identifiers(identifiers_data, ej_id, location_hierarchy)
    elif entity_type == 'mouvement':
        return classifier.process_mouvement_identifiers(identifiers_data, ej_id, location_hierarchy)
    elif entity_type == 'contact':
        # Pour les contacts, utiliser la même logique que les patients
        return classifier.process_patient_identifiers(identifiers_data, ej_id, location_hierarchy)
    else:
        # Cette branche ne devrait jamais être atteinte à cause de la vérification ci-dessus
        raise ValueError(f"Type d'entité non supporté: {entity_type}")


def classify_hprim_identifiers(
    session: Session,
    emetteur_id: str,
    emetteur_system: str,
    destinataire_id: str,
    destinataire_system: str,
    is_emission: bool,
    ej_id: int,
    identifier_type: IdentifierType = IdentifierType.IPP
) -> Dict[str, Tuple[bool, Optional[str]]]:
    """
    Fonction utilitaire pour classifier les identifiants HPRIM émetteur/destinataire.

    Args:
        session: Session de base de données
        emetteur_id: ID de l'émetteur
        emetteur_system: Système/namespace de l'émetteur
        destinataire_id: ID du destinataire
        destinataire_system: Système/namespace du destinataire
        is_emission: True si émission, False si réception
        ej_id: ID de l'entité juridique locale
        identifier_type: Type d'identifiant

    Returns:
        Classification des identifiants émetteur/destinataire
    """
    classifier = IdentifierNamespaceClassifier(session)
    return classifier.classify_hprim_identifiers(
        emetteur_id=emetteur_id,
        emetteur_system=emetteur_system,
        destinataire_id=destinataire_id,
        destinataire_system=destinataire_system,
        is_emission=is_emission,
        ej_id=ej_id,
        identifier_type=identifier_type
    )
