"""
Service de génération d'identifiants avec préfixes configurables.

Objectifs:
- Générer IPP/NDA/VENUE avec préfixes configurables (ex: '9...', '91...', '501...')
- Respecter les plages d'identifiants spécifiques du système récepteur
- Détecter et éviter les collisions avec identifiants existants
- Utiliser namespaces dédiés pour scénarios de test
"""

from __future__ import annotations

import random, threading
from typing import Optional, Tuple
from sqlmodel import Session, select, func

from app.models_identifiers import Identifier, IdentifierType
from app.models_structure_fhir import IdentifierNamespace


class IdentifierGenerationError(Exception):
    """Erreur lors de la génération d'un identifiant."""
    pass

# Verrou global pour sécuriser la génération concurrente (threads/tests)
_GEN_LOCK = threading.Lock()


def _parse_prefix_pattern(pattern: str) -> Tuple[str, int]:
    """
    Parse un pattern de préfixe et retourne (préfixe_fixe, nb_digits_variables).
    
    Exemples:
    - "9..." → ("9", 3) - préfixe '9' + 3 chiffres aléatoires
    - "91...." → ("91", 4) - préfixe '91' + 4 chiffres aléatoires
    - "501..." → ("501", 3) - préfixe '501' + 3 chiffres aléatoires
    
    Args:
        pattern: Pattern avec '.' représentant des chiffres à générer
        
    Returns:
        Tuple (préfixe_fixe, nombre_de_points)
        
    Raises:
        IdentifierGenerationError: Si pattern invalide
    """
    if not pattern:
        raise IdentifierGenerationError("Pattern vide")
    
    # Compter les points à la fin
    dots_count = 0
    for char in reversed(pattern):
        if char == '.':
            dots_count += 1
        else:
            break
    
    if dots_count == 0:
        # Pas de points = préfixe fixe complet
        return (pattern, 0)
    
    # Extraire préfixe fixe
    fixed_prefix = pattern[:-dots_count]
    
    # Valider que le préfixe ne contient que des chiffres
    if fixed_prefix and not fixed_prefix.isdigit():
        raise IdentifierGenerationError(
            f"Préfixe invalide '{fixed_prefix}': doit contenir uniquement des chiffres"
        )
    
    return (fixed_prefix, dots_count)


def _generate_with_prefix_pattern(
    session: Session,
    pattern: str,
    identifier_type: IdentifierType,
    namespace_system: str,
    max_attempts: int = 100
) -> str:
    """
    Génère un identifiant selon un pattern de préfixe.
    
    Args:
        session: Session DB pour vérifier les collisions
        pattern: Pattern type "9..." ou "501..."
        identifier_type: Type d'identifiant (IPP, NDA, etc.)
        namespace_system: System URI du namespace
        max_attempts: Nombre max de tentatives avant erreur
        
    Returns:
        Identifiant généré (ex: "9001234" pour pattern "9...")
        
    Raises:
        IdentifierGenerationError: Si impossible de générer sans collision
    """
    fixed_prefix, variable_digits = _parse_prefix_pattern(pattern)
    
    if variable_digits == 0:
        # Préfixe fixe sans génération = erreur (pas de variabilité)
        raise IdentifierGenerationError(
            f"Pattern '{pattern}' ne permet pas de génération (pas de '.')"
        )
    
    # Calculer min/max pour la partie variable (0 à 10^n - 1)
    min_val = 0
    max_val = (10 ** variable_digits) - 1   # ex: 999 pour 3 digits
    
    for attempt in range(max_attempts):
        # Générer partie variable avec padding zeros si nécessaire
        variable_part = random.randint(min_val, max_val)
        variable_str = str(variable_part).zfill(variable_digits)
        candidate = f"{fixed_prefix}{variable_str}"
        
        # Vérifier collision dans table Identifier
        existing = session.exec(
            select(Identifier).where(
                Identifier.value == candidate,
                Identifier.type == identifier_type,
                Identifier.system == namespace_system
            )
        ).first()
        
        if not existing:
            return candidate
    
    raise IdentifierGenerationError(
        f"Impossible de générer identifiant unique après {max_attempts} tentatives "
        f"pour pattern '{pattern}' (type={identifier_type}, system={namespace_system})"
    )


def _generate_with_range(
    session: Session,
    min_val: int,
    max_val: int,
    identifier_type: IdentifierType,
    namespace_system: str,
    max_attempts: int = 100
) -> str:
    """
    Génère un identifiant dans une plage numérique.
    
    Args:
        session: Session DB
        min_val: Valeur minimale (ex: 9000000)
        max_val: Valeur maximale (ex: 9999999)
        identifier_type: Type d'identifiant
        namespace_system: System URI
        max_attempts: Tentatives max
        
    Returns:
        Identifiant généré sous forme de string
        
    Raises:
        IdentifierGenerationError: Si plage saturée ou invalide
    """
    if min_val >= max_val:
        raise IdentifierGenerationError(
            f"Plage invalide: min={min_val} >= max={max_val}"
        )
    
    for attempt in range(max_attempts):
        candidate_int = random.randint(min_val, max_val)
        candidate = str(candidate_int)
        
        existing = session.exec(
            select(Identifier).where(
                Identifier.value == candidate,
                Identifier.type == identifier_type,
                Identifier.system == namespace_system
            )
        ).first()
        
        if not existing:
            return candidate
    
    raise IdentifierGenerationError(
        f"Impossible de générer identifiant unique dans plage [{min_val}, {max_val}] "
        f"après {max_attempts} tentatives"
    )


def generate_identifier(
    session: Session,
    namespace: IdentifierNamespace,
    identifier_type: IdentifierType,
    prefix_override: Optional[str] = None
) -> str:
    """
    Génère un identifiant selon la configuration du namespace.
    
    Cette fonction est le point d'entrée principal pour générer des identifiants
    de test avec gestion des préfixes et évitement de collisions.
    
    Args:
        session: Session DB pour vérifier les collisions
        namespace: IdentifierNamespace contenant la config de préfixe
        identifier_type: Type d'identifiant à générer (IPP, NDA, VN)
        prefix_override: Préfixe spécifique pour cette génération (override config namespace)
        
    Returns:
        Identifiant généré (ex: "9001234", "501789")
        
    Raises:
        IdentifierGenerationError: Si génération impossible
        
    Exemples:
    ```python
    # Avec namespace configuré avec prefix_pattern="9..."
    ipp = generate_identifier(session, ipp_namespace, IdentifierType.IPP)
    # → "9001234"
    
    # Avec override de préfixe
    nda = generate_identifier(session, nda_namespace, IdentifierType.NDA, prefix_override="501...")
    # → "501789"
    
    # Avec mode range
    ipp2 = generate_identifier(session, range_namespace, IdentifierType.IPP)
    # → "9234567" (dans plage min=9000000, max=9999999)
    ```
    """
    # Déterminer la source de configuration
    pattern = prefix_override if prefix_override else namespace.prefix_pattern
    mode = namespace.prefix_mode or "fixed"
    
    # Cas 1: Pattern de préfixe (mode par défaut)
    if pattern:
        with _GEN_LOCK:
            return _generate_with_prefix_pattern(
                session=session,
                pattern=pattern,
                identifier_type=identifier_type,
                namespace_system=namespace.system,
            )
    
    # Cas 2: Plage numérique (mode range)
    if mode == "range" and namespace.prefix_min is not None and namespace.prefix_max is not None:
        with _GEN_LOCK:
            return _generate_with_range(
                session=session,
                min_val=namespace.prefix_min,
                max_val=namespace.prefix_max,
                identifier_type=identifier_type,
                namespace_system=namespace.system,
            )
    
    # Cas 3: Pas de configuration = génération séquentielle simple
    # Trouver le dernier identifiant de ce type dans ce namespace
    with _GEN_LOCK:
        last_ident = session.exec(
            select(Identifier)
            .where(
                Identifier.type == identifier_type,
                Identifier.system == namespace.system
            )
            .order_by(Identifier.id.desc())
        ).first()
    
    if last_ident and last_ident.value.isdigit():
        with _GEN_LOCK:
            next_val = int(last_ident.value) + 1
            return str(next_val)
    
    # Fallback: commencer à 1000 pour ce namespace
    return "1000"


def generate_identifier_set(
    session: Session,
    ipp_namespace: IdentifierNamespace,
    nda_namespace: IdentifierNamespace,
    venue_namespace: Optional[IdentifierNamespace] = None,
    ipp_prefix_override: Optional[str] = None,
    nda_prefix_override: Optional[str] = None
) -> dict[str, str]:
    """
    Génère un ensemble complet d'identifiants IPP/NDA/VENUE pour un scénario.
    
    Utile pour préparer les identifiants avant l'exécution d'un scénario complet.
    
    Args:
        session: Session DB
        ipp_namespace: Namespace pour IPP
        nda_namespace: Namespace pour NDA
        venue_namespace: Namespace pour VENUE (optionnel)
        ipp_prefix_override: Override préfixe IPP
        nda_prefix_override: Override préfixe NDA
        
    Returns:
        Dictionnaire avec clés 'ipp', 'nda', 'venue'
        
    Exemple:
    ```python
    ids = generate_identifier_set(
        session,
        ipp_ns,
        nda_ns,
        venue_ns,
        ipp_prefix_override="9...",
        nda_prefix_override="501..."
    )
    # → {'ipp': '9001234', 'nda': '501789', 'venue': '3456789'}
    ```
    """
    result = {
        'ipp': generate_identifier(
            session, ipp_namespace, IdentifierType.IPP, ipp_prefix_override
        ),
        'nda': generate_identifier(
            session, nda_namespace, IdentifierType.NDA, nda_prefix_override
        ),
    }
    
    if venue_namespace:
        result['venue'] = generate_identifier(
            session, venue_namespace, IdentifierType.VN
        )
    
    return result


def generate_and_persist_identifier(
    session: Session,
    namespace: IdentifierNamespace,
    identifier_type: IdentifierType,
    prefix_override: Optional[str] = None
) -> str:
    """Génère et persiste immédiatement un identifiant de manière atomique.

    Cette fonction ferme la fenêtre de course potentielle entre la génération
    (vérification de disponibilité) et l'insertion effective dans la base en
    réalisant les deux opérations sous le même verrou global.

    Args:
        session: Session base de données
        namespace: Namespace configurant le préfixe / plage
        identifier_type: Type d'identifiant (IPP, NDA, VN)
        prefix_override: Override pattern si nécessaire

    Returns:
        La valeur d'identifiant générée et enregistrée.
    """
    pattern = prefix_override if prefix_override else namespace.prefix_pattern
    mode = namespace.prefix_mode or "fixed"

    with _GEN_LOCK:
        # Pattern
        if pattern:
            value = _generate_with_prefix_pattern(
                session=session,
                pattern=pattern,
                identifier_type=identifier_type,
                namespace_system=namespace.system,
            )
        # Plage
        elif mode == "range" and namespace.prefix_min is not None and namespace.prefix_max is not None:
            value = _generate_with_range(
                session=session,
                min_val=namespace.prefix_min,
                max_val=namespace.prefix_max,
                identifier_type=identifier_type,
                namespace_system=namespace.system,
            )
        else:
            # Séquentiel
            last_ident = session.exec(
                select(Identifier)
                .where(
                    Identifier.type == identifier_type,
                    Identifier.system == namespace.system
                )
                .order_by(Identifier.id.desc())
            ).first()
            if last_ident and last_ident.value.isdigit():
                value = str(int(last_ident.value) + 1)
            else:
                value = "1000"

        ident = Identifier(
            value=value,
            type=identifier_type,
            system=namespace.system,
            status="active"
        )
        session.add(ident)
        session.commit()
        return value


def count_available_identifiers(namespace: IdentifierNamespace) -> Optional[int]:
    """
    Estime le nombre d'identifiants disponibles dans un namespace.
    
    Utile pour détecter la saturation d'une plage.
    
    Args:
        namespace: Namespace à analyser
        
    Returns:
        Nombre d'identifiants disponibles, ou None si illimité/inconnu
        
    Exemple:
    ```python
    available = count_available_identifiers(namespace)
    if available and available < 100:
        print(f"⚠️ Seulement {available} identifiants disponibles!")
    ```
    """
    if namespace.prefix_mode == "range" and namespace.prefix_min and namespace.prefix_max:
        return namespace.prefix_max - namespace.prefix_min + 1
    
    if namespace.prefix_pattern:
        _, variable_digits = _parse_prefix_pattern(namespace.prefix_pattern)
        if variable_digits > 0:
            # Nombre de combinaisons possibles
            return (10 ** variable_digits) - (10 ** (variable_digits - 1))
    
    return None  # Illimité ou inconnu
