"""Corrélation et règles temporelles des mouvements PAM."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from sqlmodel import Session, select

from app.models import Mouvement
from app.models_identifiers import Identifier, IdentifierType
from app.services.identifier_manager import parse_hl7_cx_identifier

def _identifier_tuple_for_classifier(cx_value: str) -> Tuple[str, str, Optional[str], str]:
    """
    Convertit une chaîne HL7 CX/EI brute en tuple (value, system, type_code, cx_value)
    attendu par la branche 4-tuple de create_identifiers_from_hl7_with_namespace_check().

    parse_hl7_cx_identifier() renvoie (value, system, authority_oid, type_code) — un ordre
    différent, incompatible si passé tel quel à ce wrapper (l'OID se retrouverait interprété
    comme type_code, et le type_code comme cx_value complet).
    """
    value, system, _oid, type_code = parse_hl7_cx_identifier(cx_value)
    return (value, system, type_code, cx_value)


def _find_mouvement_by_movement_id(session: Session, movement_id: Optional[str]) -> Optional["Mouvement"]:
    """
    Résout une valeur ZBE-1 vers le Mouvement qu'elle désigne, pour les corrélations
    UPDATE/CANCEL/annulation (A12/A13/A21/A22/A44/A52/A53/A11/A23/A38...).

    ZBE-1 peut être soit :
    - un identifiant externe (fourni par l'émetteur, au format CX/EI complet, ex.
      "12345^SYS_A^1.2.3^ISO") — tracé dans la table Identifier (type=MVT) plutôt que
      copié dans notre mouvement_seq interne ;
    - directement notre propre mouvement_seq (ex. quand l'émetteur nous renvoie tel
      quel l'identifiant que NOUS avions émis dans ZBE-1 pour ce mouvement).

    Avant ce correctif, ces call sites faisaient `int(movement_id)` directement, ce qui
    levait ValueError pour tout ZBE-1 réellement porteur de composants CX (le cas normal
    conforme au spec) — la corrélation échouait silencieusement pour ~tous les messages
    IHE PAM France réels.
    """
    if not movement_id:
        return None

    bare_id = movement_id.split("^")[0] if "^" in movement_id else movement_id

    ident = session.exec(
        select(Identifier)
        .where(Identifier.type == IdentifierType.MVT)
        .where(Identifier.value == bare_id)
        .where(Identifier.status == "active")
        .where(Identifier.mouvement_id.isnot(None))
    ).first()
    if ident:
        mouvement = session.get(Mouvement, ident.mouvement_id)
        if mouvement:
            return mouvement

    try:
        mouvement_seq = int(bare_id)
    except (ValueError, TypeError):
        return None
    return session.exec(select(Mouvement).where(Mouvement.mouvement_seq == mouvement_seq)).first()

def validate_movement_timing(session: Session, venue_id: int, movement_datetime: datetime) -> None:
    """
    Valide qu'il y a au moins 1 minute d'écart entre le nouveau mouvement et le dernier mouvement de la venue.
    
    Args:
        session: Session de base de données
        venue_id: ID de la venue
        movement_datetime: Date/heure du nouveau mouvement
        
    Raises:
        ValueError: Si la validation échoue
    """
    from datetime import timedelta
    
    # Récupérer le dernier mouvement de cette venue
    last_movement = session.exec(
        select(Mouvement)
        .where(Mouvement.venue_id == venue_id)
        .order_by(Mouvement.when.desc())
    ).first()
    
    if last_movement and last_movement.when:
        # Vérifier qu'il y a au moins 1 minute d'écart
        if movement_datetime < last_movement.when + timedelta(minutes=1):
            raise ValueError(
                f"Il doit y avoir au moins 1 minute d'écart entre deux mouvements consécutifs. "
                f"Dernier mouvement: {last_movement.when.strftime('%d/%m/%Y %H:%M')}, "
                f"nouveau mouvement: {movement_datetime.strftime('%d/%m/%Y %H:%M')}"
            )
