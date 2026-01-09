"""
Services de gestion des identifiants et mappings FHIR/HL7
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from app.models_identifiers import Identifier, IdentifierType
from app.services.identifier_namespace_classifier import classify_incoming_identifiers


def map_hl7_type_to_identifier_type(type_code: Optional[str]) -> Optional[IdentifierType]:
    """
    Mappe un code HL7 (ex: PI, AN, NH) vers l'enum IdentifierType.
    Règles principales:
    - 'PI' (HL7 Patient Identifier) -> IdentifierType.IPP
    - 'AN' (Accession Number) -> IdentifierType.NDA
    - 'NH' (National Health number / SNS) -> IdentifierType.NDA
    - otherwise attempt direct mapping to enum by value
    """
    if not type_code:
        return None

    code = type_code.strip()
    # Mapping explicite HL7 -> enum
    if code == "PI":
        return IdentifierType.IPP
    if code == "AN":
        return IdentifierType.NDA
    if code == "NH":
        return IdentifierType.NDA
    # Solution de repli: try direct enum construction
    try:
        return IdentifierType(code)
    except ValueError:
        return None


def parse_hl7_cx_identifier(cx_value: str) -> Tuple[str, str, Optional[str], Optional[str]]:
    """
    Parse un identifiant au format HL7 CX (Component/Subcomponent Separator: ^)
    Format HL7 standard: ID^Check Digit^Check Digit Scheme^Assigning Authority^Identifier Type Code
    Pour simplifier, on extrait: value (pos 0), system (assigning authority à pos 3), type_code (pos 4)
    Support des OID: Assigning Authority peut être "SYSTEM&OID&ISO"
    Retourne: (value, system, authority_oid, type_code)
    """
    parts = cx_value.split("^")
    value = parts[0] if len(parts) > 0 else ""
    # CX-4 = Assigning Authority (system) - peut contenir "SYSTEM&OID&ISO"
    system_full = parts[3] if len(parts) > 3 else ""
    # CX-5 = Identifier Type Code
    type_code = parts[4] if len(parts) > 4 else None

    # Extraire l'OID si présent dans le format "SYSTEM&OID&ISO"
    system = system_full
    authority_oid = None
    if "&" in system_full:
        system_parts = system_full.split("&")
        if len(system_parts) >= 2:
            system = system_parts[0]
            authority_oid = system_parts[1]

    return value, system, authority_oid, type_code


def create_identifier_from_hl7(
    cx_value: str,
    entity_type: str,
    entity_id: int
) -> Identifier:
    """
    Crée un identifiant à partir d'une valeur HL7 CX
    """
    value, namespace, authority_oid, type_code = parse_hl7_cx_identifier(cx_value)
    
    # Déterminer le type d'identifiant — par défaut on considère PI (Patient Internal)
    # Convertir le code HL7 en IdentifierType via le mapping
    id_type = map_hl7_type_to_identifier_type(type_code) or IdentifierType.IPP
    
    # Créer l'identifiant
    identifier = Identifier(
        value=value,
        system=namespace,
        oid=authority_oid,  # Stocker l'OID extrait
        type=id_type,
        status="active"
    )
    
    # Associer à l'entité
    if entity_type == "patient":
        identifier.patient_id = entity_id
    elif entity_type == "dossier":
        identifier.dossier_id = entity_id
    elif entity_type == "venue":
        identifier.venue_id = entity_id
    elif entity_type == "mouvement":
        identifier.mouvement_id = entity_id
    
    return identifier


def create_identifiers_from_hl7_with_namespace_check(*args, **kwargs) -> Tuple[List[Identifier], Optional[str], Optional[str]]:
    """
    Backwards-compatible wrapper that creates identifiers from HL7 CX values with namespace checks.

    Supports two call signatures for historical reasons:
    1) New style: create_identifiers_from_hl7_with_namespace_check(identifiers_data, entity_type, session, ej_id=None)
    2) Old style used across the codebase: create_identifiers_from_hl7_with_namespace_check(session, identifiers_data, entity_obj_or_type, entity_type?)

    The wrapper normalizes to (identifiers_data, entity_type, session, ej_id) and delegates to the internal implementation.
    """
    # Normalize arguments
    from sqlmodel import Session as _Session

    identifiers_data = None
    entity_type = None
    session = None
    ej_id = kwargs.get("ej_id")

    # Case A: first arg is a Session -> old style
    if len(args) >= 1 and isinstance(args[0], _Session):
        session = args[0]
        if len(args) >= 2:
            identifiers_data = args[1]
        if len(args) >= 3:
            third = args[2]
            # third may be an entity instance or a string entity_type
            if isinstance(third, str):
                entity_type = third
                if len(args) >= 4:
                    ej_id = args[3]
            else:
                # third is entity object; fourth should be entity_type string if present
                if len(args) >= 4 and isinstance(args[3], str):
                    entity_type = args[3]
                else:
                    # try to infer type from object's class name
                    try:
                        entity_type = getattr(third, "__tablename__", None) or third.__class__.__name__.lower()
                    except Exception:
                        entity_type = None
    else:
        # Assume new style: identifiers_data, entity_type, session, ej_id
        if len(args) >= 1:
            identifiers_data = args[0]
        if len(args) >= 2:
            entity_type = args[1]
        if len(args) >= 3:
            session = args[2]
        if len(args) >= 4:
            ej_id = args[3]

    # Solution de repli to kwargs if still missing
    if identifiers_data is None:
        identifiers_data = kwargs.get("identifiers_data")
    if entity_type is None:
        entity_type = kwargs.get("entity_type")
    if session is None:
        session = kwargs.get("session")

    # Now call the internal implementation with normalized parameters
    # (The rest of the original function expects identifiers_data, entity_type, session, ej_id)

    # Synchronous implementation that Renvoie a tuple-like object which is also awaitable.
    class _AwaitableTuple(tuple):
        def __await__(self):
            async def _inner():
                return tuple(self)
            return _inner().__await__()

    if not identifiers_data:
        return _AwaitableTuple(([], None, None))

    # Normalize incoming identifier tuple shapes and convert for the classifier
    # Also build a mapping from clean value -> (system, oid) for later use
    classifier_data = []
    value_to_cx_map = {}  # Maps clean value -> original CX for OID extraction
    
    for item in identifiers_data:
        try:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                cx_value, system, id_type_str = item
            elif isinstance(item, (list, tuple)) and len(item) == 4:
                # New format from pam.py: (value, system, type_code, cx_value)
                value, system, id_type_str, cx_value = item
                value_to_cx_map[value] = cx_value
            else:
                cx_value = str(item)
                system = ""
                id_type_str = None
        except Exception:
            cx_value = str(item)
            system = ""
            id_type_str = None

        # Extract clean value from CX if not already done
        if cx_value and "^" in cx_value:
            clean_value = cx_value.split("^")[0]
            if clean_value not in value_to_cx_map:
                value_to_cx_map[clean_value] = cx_value
        elif cx_value:
            if cx_value not in value_to_cx_map:
                value_to_cx_map[cx_value] = cx_value

        id_type = map_hl7_type_to_identifier_type(id_type_str) or IdentifierType.IPP
        classifier_data.append((cx_value, system, id_type))

    classification = classify_incoming_identifiers(
        session, classifier_data, entity_type, ej_id
    )

    identifiers = []
    if classification.get('main_identifier'):
        main_value = classification['main_identifier']
        main_system = ""
        main_oid = ""
        
        # Extract system and OID from original CX
        cx_for_main = value_to_cx_map.get(main_value, main_value)
        if cx_for_main and "^" in cx_for_main:
            _, parsed_system, parsed_oid, _ = parse_hl7_cx_identifier(cx_for_main)
            main_system = parsed_system or ""
            main_oid = parsed_oid or ""
        
        main_id = Identifier(
            value=main_value,
            system=main_system,
            oid=main_oid,
            type=IdentifierType.IPP,
            status="active"
        )
        identifiers.append(main_id)

    for ext_id_data in classification.get('external_identifiers', []):
        ext_value = ext_id_data['value']
        ext_system = ext_id_data.get('external_namespace') or ext_id_data.get('system', '')
        ext_oid = ""
        
        # Extract system and OID from original CX
        cx_for_ext = value_to_cx_map.get(ext_value, ext_value)
        if cx_for_ext and "^" in cx_for_ext:
            _, parsed_system, parsed_oid, _ = parse_hl7_cx_identifier(cx_for_ext)
            if parsed_system:
                ext_system = parsed_system
            ext_oid = parsed_oid or ""
        
        ext_id = Identifier(
            value=ext_value,
            system=ext_system,
            oid=ext_oid,
            type=ext_id_data['type'],
            status="active"
        )
        identifiers.append(ext_id)

    return _AwaitableTuple((identifiers, classification.get('main_identifier'), classification.get('external_id')))
    """
    Crée des identifiants à partir de données HL7 en vérifiant les namespaces EJ.
    
    Args:
        identifiers_data: Liste de tuples (cx_value, identifier_type) depuis parse_patient_identifiers
        entity_type: Type d'entité ('patient', 'dossier', 'venue', 'mouvement')
        session: Session DB
        ej_id: ID de l'EJ pour la classification
        
    Returns:
        Tuple (identifiers, main_identifier_value, external_id_value)
        - identifiers: Liste des objets Identifier créés
        - main_identifier_value: Valeur de l'identifiant principal (si applicable)
        - external_id_value: Valeur de l'identifiant externe (si applicable)
    """
    if not identifiers_data:
        return [], None, None
    
    # Normalize incoming identifier tuple shapes and convert for the classifier
    classifier_data = []
    cx_mapping = {}  # Pour mapper value -> CX complet
    
    for item in identifiers_data:
        # Support multiple formats:
        # (value, system, type_code, cx_value) - nouveau format depuis pam.py
        # (cx_value, system, id_type_str) - ancien format
        # (value, system, authority_oid, type_code) - format parse_hl7_cx_identifier
        try:
            if isinstance(item, (list, tuple)) and len(item) == 4:
                # Nouveau format: (value, system, type_code, cx_value)
                value, system, id_type_str, cx_value = item
                cx_mapping[value] = cx_value
            elif isinstance(item, (list, tuple)) and len(item) == 3:
                # Format (cx_value, system, id_type_str) ou (value, system, type_code)
                value_or_cx, system, id_type_str = item
                # Si contient ^, c'est un CX complet, parser
                if "^" in value_or_cx:
                    value, system, _, id_type_str = parse_hl7_cx_identifier(value_or_cx)
                    cx_mapping[value] = value_or_cx
                else:
                    value = value_or_cx
                    cx_mapping[value] = value_or_cx
            else:
                # Unexpected shape: coerce to string and treat as raw CX
                value_str = str(item)
                if "^" in value_str:
                    value, system, _, id_type_str = parse_hl7_cx_identifier(value_str)
                    cx_mapping[value] = value_str
                else:
                    value = value_str
                    system = ""
                    id_type_str = None
                    cx_mapping[value] = value
        except Exception:
            value = str(item)
            system = ""
            id_type_str = None
            cx_mapping[value] = value

        # Convert HL7 type string to enum via the mapper
        id_type = map_hl7_type_to_identifier_type(id_type_str) or IdentifierType.IPP

        classifier_data.append((value, system, id_type))
    
    # Classifier les identifiants selon les namespaces EJ
    classification = classify_incoming_identifiers(
        session, classifier_data, entity_type, ej_id
    )
    
    identifiers = []
    
    # Traiter les identifiants principaux
    if classification.get('main_identifier'):
        # Récupérer le system et l'OID depuis le CX original via mapping
        main_system = ""
        main_oid = ""
        main_value = classification['main_identifier']
        
        # Chercher le CX complet dans le mapping
        cx_value = cx_mapping.get(main_value, main_value)
        if "^" in cx_value:
            # Parser le CX complet pour extraire system et OID
            _, parsed_system, parsed_oid, _ = parse_hl7_cx_identifier(cx_value)
            main_system = parsed_system
            main_oid = parsed_oid or ""
        else:
            # Fallback: chercher dans classifier_data
            for value, system, id_type in classifier_data:
                if value == main_value:
                    main_system = system
                    if "&" in system:
                        parts = system.split("&")
                        if len(parts) >= 2:
                            main_oid = parts[1]
                    break
        
        # Créer un identifiant principal
        main_id = Identifier(
            value=classification['main_identifier'],
            system=main_system,
            oid=main_oid,
            type=IdentifierType.IPP,  # Type par défaut
            status="active"
        )
        identifiers.append(main_id)
    
    # Traiter les identifiants externes
    for ext_id_data in classification.get('external_identifiers', []):
        # Récupérer system et OID depuis le CX original via mapping
        ext_value = ext_id_data['value']
        ext_system = ext_id_data.get('external_namespace') or ext_id_data.get('system', '')
        ext_oid = ""
        
        # Chercher le CX complet dans le mapping
        cx_value = cx_mapping.get(ext_value, ext_value)
        if "^" in cx_value:
            # Parser le CX complet pour extraire system et OID
            _, parsed_system, parsed_oid, _ = parse_hl7_cx_identifier(cx_value)
            ext_system = parsed_system
            ext_oid = parsed_oid or ""
        else:
            # Fallback: chercher dans classifier_data
            for value, system, id_type in classifier_data:
                if value == ext_value:
                    ext_system = system
                    if "&" in system:
                        parts = system.split("&")
                        if len(parts) >= 2:
                            ext_oid = parts[1]
                    break
        
        ext_id = Identifier(
            value=ext_value,
            system=ext_system,
            oid=ext_oid,
            type=ext_id_data['type'],
            status="active"
        )
        identifiers.append(ext_id)
    
    return (
        identifiers,
        classification.get('main_identifier'),
        classification.get('external_id')
    )


def create_fhir_identifier(identifier: Identifier) -> Dict:
    """
    Convertit un identifiant en structure FHIR
    """
    fhir_id = {
        "use": "official",
        "system": identifier.system,
        "value": identifier.value
    }
    
    def map_identifier_type_to_hl7_code(id_type: IdentifierType) -> str:
        """Retourne le code HL7 (v2) correspondant à l'enum interne.

        - IdentifierType.IPP -> 'PI'
        - IdentifierType.NDA -> 'AN'
        - For other types, return the enum value as-is.
        """
        if id_type == IdentifierType.IPP:
            return "PI"
        if id_type == IdentifierType.NDA:
            return "AN"
        return id_type.value

    if identifier.type:
        hl7_code = map_identifier_type_to_hl7_code(identifier.type)
        fhir_id["type"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                "code": hl7_code
            }]
        }
    
    return fhir_id


def create_identifier_from_fhir(fhir_identifier: Dict) -> Identifier:
    """
    Crée un identifiant à partir d'une structure FHIR
    """
    # Extraire le type si présent
    id_type = None
    if "type" in fhir_identifier and "coding" in fhir_identifier["type"]:
        for coding in fhir_identifier["type"]["coding"]:
            if coding["system"] == "http://terminology.hl7.org/CodeSystem/v2-0203":
                # Mapper HL7 code -> IdentifierType
                id_type = map_hl7_type_to_identifier_type(coding.get("code"))
                if id_type:
                    break
    
    return Identifier(
        value=fhir_identifier["value"],
        system=fhir_identifier.get("system", ""),
        type=id_type,
        status="active"
    )


def get_main_identifier(identifiers: List[Identifier], id_type: Optional[IdentifierType] = None) -> Optional[Identifier]:
    """
    Récupère l'identifiant principal d'une liste selon le type
    """
    if not identifiers:
        return None
        
    # Si un type est spécifié, chercher d'abord ce type
    if id_type:
        for identifier in identifiers:
            if identifier.type == id_type and identifier.status == "active":
                return identifier
    
    # Sinon prendre le premier actif
    for identifier in identifiers:
        if identifier.status == "active":
            return identifier
            
    return identifiers[0]  # Si aucun actif, prendre le premier


def merge_identifiers(
    existing: List[Identifier],
    new: List[Identifier],
    keep_inactive: bool = True
) -> List[Identifier]:
    """
    Fusionne deux listes d'identifiants en gérant les conflits
    """
    result = []
    seen = set()
    
    # Ajouter les nouveaux identifiants
    for identifier in new:
        key = (identifier.system, identifier.value)
        seen.add(key)
        result.append(identifier)
    
    # Ajouter ou mettre à jour les existants
    for identifier in existing:
        key = (identifier.system, identifier.value)
        if key not in seen:
            if identifier.status == "active" or keep_inactive:
                result.append(identifier)
                seen.add(key)
    
    return result
