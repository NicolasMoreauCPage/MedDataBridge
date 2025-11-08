"""
Service de remplacement des identifiants dans les payloads HL7 pour scénarios de test.

Objectifs:
- Remplacer IPP/NDA/VENUE dans messages HL7 selon règles de préfixe
- Conserver la structure HL7 intacte (segments, délimiteurs)
- Gérer les répétitions d'identifiants (PID-3 multiple avec ~)
- Logger les transformations pour traçabilité
"""

from __future__ import annotations

import re
from typing import Optional, Dict, Tuple
from sqlmodel import Session

from app.models_structure_fhir import IdentifierNamespace
from app.models_identifiers import IdentifierType
from app.services.identifier_generator import generate_identifier, generate_identifier_set


def _extract_segment(message: str, segment_name: str) -> Optional[str]:
    """
    Extrait un segment HL7 d'un message complet.
    
    Args:
        message: Message HL7 complet (segments séparés par \\r ou \\n)
        segment_name: Nom du segment (ex: 'PID', 'PV1')
        
    Returns:
        Ligne du segment ou None si absent
    """
    lines = message.replace('\r', '\n').split('\n')
    for line in lines:
        if line.startswith(f"{segment_name}|"):
            return line
    return None


def _replace_segment(message: str, segment_name: str, new_segment: str) -> str:
    """
    Remplace un segment dans un message HL7.
    
    Args:
        message: Message HL7 complet
        segment_name: Nom du segment à remplacer
        new_segment: Nouveau contenu du segment
        
    Returns:
        Message avec segment remplacé
    """
    lines = message.replace('\r', '\n').split('\n')
    result = []
    replaced = False
    
    for line in lines:
        if line.startswith(f"{segment_name}|"):
            result.append(new_segment)
            replaced = True
        else:
            result.append(line)
    
    # Si segment absent, l'ajouter après MSH
    if not replaced:
        for i, line in enumerate(result):
            if line.startswith("MSH|"):
                result.insert(i + 1, new_segment)
                break
    
    return '\r'.join(result)


def _replace_pid3_identifiers(
    pid_segment: str,
    ipp_value: Optional[str] = None,
    ipp_namespace: Optional[IdentifierNamespace] = None,
    external_id_value: Optional[str] = None
) -> str:
    """
    Remplace les identifiants dans PID-3 (Patient Identifier List).
    
    Format HL7 v2.5 PID-3: ID1^^^SYSTEM1&OID1&ISO^TYPE~ID2^^^SYSTEM2&OID2&ISO^TYPE
    
    Args:
        pid_segment: Ligne PID complète
        ipp_value: Nouvel IPP à injecter
        ipp_namespace: Namespace IPP pour system/OID
        external_id_value: ID externe à injecter (optionnel)
        
    Returns:
        Segment PID modifié
    """
    fields = pid_segment.split('|')
    
    if len(fields) < 4:
        # PID-3 absent, le créer
        while len(fields) < 4:
            fields.append('')
    
    # Construire nouveau PID-3
    identifiers = []
    
    if ipp_value and ipp_namespace:
        # Extraire OID du system (ex: "urn:oid:1.2.3.4" → "1.2.3.4")
        oid = ipp_namespace.oid or ipp_namespace.system.split(':')[-1]
        identifiers.append(f"{ipp_value}^^^{ipp_namespace.name}&{oid}&ISO^PI")
    
    if external_id_value:
        identifiers.append(f"{external_id_value}^^^EXTERNAL_SYS^PI")
    
    if identifiers:
        fields[3] = '~'.join(identifiers)
    
    return '|'.join(fields)


def _replace_pv1_visit_number(
    pv1_segment: str,
    nda_value: Optional[str] = None,
    nda_namespace: Optional[IdentifierNamespace] = None
) -> str:
    """
    Remplace le numéro de visite dans PV1-19 (Visit Number).
    
    Format: NDA^^^SYSTEM&OID&ISO^VN
    
    Args:
        pv1_segment: Ligne PV1 complète
        nda_value: Nouveau NDA
        nda_namespace: Namespace NDA pour system/OID
        
    Returns:
        Segment PV1 modifié
    """
    fields = pv1_segment.split('|')
    
    # PV1-19 est le 19ème champ
    while len(fields) < 20:
        fields.append('')
    
    if nda_value and nda_namespace:
        oid = nda_namespace.oid or nda_namespace.system.split(':')[-1]
        fields[19] = f"{nda_value}^^^{nda_namespace.name}&{oid}&ISO^VN"
    
    return '|'.join(fields)


def _replace_pv1_alternate_visit_id(
    pv1_segment: str,
    venue_value: Optional[str] = None,
    venue_namespace: Optional[IdentifierNamespace] = None
) -> str:
    """
    Remplace l'identifiant de venue dans PV1-50 (Alternate Visit ID).
    
    Format: VENUE^^^SYSTEM&OID&ISO^VN
    
    Args:
        pv1_segment: Ligne PV1 complète
        venue_value: Nouveau VENUE
        venue_namespace: Namespace VENUE
        
    Returns:
        Segment PV1 modifié
    """
    fields = pv1_segment.split('|')
    
    # PV1-50 est le 50ème champ
    while len(fields) < 51:
        fields.append('')
    
    if venue_value and venue_namespace:
        oid = venue_namespace.oid or venue_namespace.system.split(':')[-1]
        fields[50] = f"{venue_value}^^^{venue_namespace.name}&{oid}&ISO^VN"
    
    return '|'.join(fields)


def replace_identifiers_in_hl7_message(
    message: str,
    session: Session,
    ipp_namespace: Optional[IdentifierNamespace] = None,
    nda_namespace: Optional[IdentifierNamespace] = None,
    venue_namespace: Optional[IdentifierNamespace] = None,
    ipp_prefix_override: Optional[str] = None,
    nda_prefix_override: Optional[str] = None,
    generated_ids: Optional[Dict[str, str]] = None
) -> Tuple[str, Dict[str, str]]:
    """
    Remplace tous les identifiants dans un message HL7 selon les namespaces configurés.
    
    Cette fonction est le point d'entrée principal pour transformer un message
    de scénario avant envoi à un système récepteur.
    
    Args:
        message: Message HL7 complet (avec \\r entre segments)
        session: Session DB pour génération d'identifiants
        ipp_namespace: Namespace pour IPP
        nda_namespace: Namespace pour NDA
        venue_namespace: Namespace pour VENUE (optionnel)
        ipp_prefix_override: Override préfixe IPP pour cette exécution
        nda_prefix_override: Override préfixe NDA pour cette exécution
        generated_ids: Identifiants pré-générés (si None, génération automatique)
        
    Returns:
        Tuple (message_modifié, dict_identifiants_générés)
        
    Exemple:
    ```python
    modified_msg, ids = replace_identifiers_in_hl7_message(
        original_msg,
        session,
        ipp_namespace=ipp_ns,
        nda_namespace=nda_ns,
        ipp_prefix_override="9...",
        nda_prefix_override="501..."
    )
    # ids = {'ipp': '9001234', 'nda': '501789', 'venue': None}
    ```
    """
    # Génération des identifiants si non fournis
    if not generated_ids:
        if not ipp_namespace or not nda_namespace:
            # Pas de namespace configuré = pas de remplacement
            return (message, {})
        
        generated_ids = generate_identifier_set(
            session=session,
            ipp_namespace=ipp_namespace,
            nda_namespace=nda_namespace,
            venue_namespace=venue_namespace,
            ipp_prefix_override=ipp_prefix_override,
            nda_prefix_override=nda_prefix_override
        )
    
    result_message = message
    
    # Remplacer PID-3 (identifiants patient)
    pid_segment = _extract_segment(result_message, 'PID')
    if pid_segment:
        new_pid = _replace_pid3_identifiers(
            pid_segment,
            ipp_value=generated_ids.get('ipp'),
            ipp_namespace=ipp_namespace
        )
        result_message = _replace_segment(result_message, 'PID', new_pid)
    
    # Remplacer PV1-19 (NDA)
    pv1_segment = _extract_segment(result_message, 'PV1')
    if pv1_segment:
        new_pv1 = _replace_pv1_visit_number(
            pv1_segment,
            nda_value=generated_ids.get('nda'),
            nda_namespace=nda_namespace
        )
        
        # Remplacer PV1-50 (VENUE) si configuré
        if venue_namespace and generated_ids.get('venue'):
            new_pv1 = _replace_pv1_alternate_visit_id(
                new_pv1,
                venue_value=generated_ids.get('venue'),
                venue_namespace=venue_namespace
            )
        
        result_message = _replace_segment(result_message, 'PV1', new_pv1)
    
    return (result_message, generated_ids)


def preview_identifier_replacement(
    message: str,
    session: Session,
    ipp_namespace: IdentifierNamespace,
    nda_namespace: IdentifierNamespace,
    venue_namespace: Optional[IdentifierNamespace] = None,
    ipp_prefix_override: Optional[str] = None,
    nda_prefix_override: Optional[str] = None
) -> Dict[str, any]:
    """
    Génère un aperçu des identifiants qui seront utilisés sans modifier le message.
    
    Utile pour l'interface utilisateur pour montrer à l'avance quels identifiants
    seront générés avant l'exécution réelle du scénario.
    
    Args:
        message: Message HL7 original
        session: Session DB
        ipp_namespace, nda_namespace, venue_namespace: Namespaces configurés
        ipp_prefix_override, nda_prefix_override: Overrides de préfixes
        
    Returns:
        Dictionnaire avec:
        - 'generated_ids': Dict des identifiants qui seront générés
        - 'original_pid3': Valeur PID-3 originale
        - 'original_pv1_19': Valeur PV1-19 originale
        - 'new_pid3': Valeur PID-3 qui sera générée
        - 'new_pv1_19': Valeur PV1-19 qui sera générée
        
    Exemple:
    ```python
    preview = preview_identifier_replacement(msg, session, ipp_ns, nda_ns)
    print(f"IPP: {preview['generated_ids']['ipp']}")
    print(f"NDA: {preview['generated_ids']['nda']}")
    ```
    """
    # Générer les identifiants
    generated_ids = generate_identifier_set(
        session=session,
        ipp_namespace=ipp_namespace,
        nda_namespace=nda_namespace,
        venue_namespace=venue_namespace,
        ipp_prefix_override=ipp_prefix_override,
        nda_prefix_override=nda_prefix_override
    )
    
    # Extraire valeurs originales
    pid_segment = _extract_segment(message, 'PID')
    pv1_segment = _extract_segment(message, 'PV1')
    
    original_pid3 = None
    if pid_segment:
        fields = pid_segment.split('|')
        original_pid3 = fields[3] if len(fields) > 3 else None
    
    original_pv1_19 = None
    if pv1_segment:
        fields = pv1_segment.split('|')
        original_pv1_19 = fields[19] if len(fields) > 19 else None
    
    # Construire nouvelles valeurs
    new_pid3 = None
    if ipp_namespace and generated_ids.get('ipp'):
        oid = ipp_namespace.oid or ipp_namespace.system.split(':')[-1]
        new_pid3 = f"{generated_ids['ipp']}^^^{ipp_namespace.name}&{oid}&ISO^PI"
    
    new_pv1_19 = None
    if nda_namespace and generated_ids.get('nda'):
        oid = nda_namespace.oid or nda_namespace.system.split(':')[-1]
        new_pv1_19 = f"{generated_ids['nda']}^^^{nda_namespace.name}&{oid}&ISO^VN"
    
    return {
        'generated_ids': generated_ids,
        'original_pid3': original_pid3,
        'original_pv1_19': original_pv1_19,
        'new_pid3': new_pid3,
        'new_pv1_19': new_pv1_19,
        'namespaces': {
            'ipp': {
                'name': ipp_namespace.name,
                'system': ipp_namespace.system,
                'pattern': ipp_prefix_override or ipp_namespace.prefix_pattern
            },
            'nda': {
                'name': nda_namespace.name,
                'system': nda_namespace.system,
                'pattern': nda_prefix_override or nda_namespace.prefix_pattern
            }
        }
    }
