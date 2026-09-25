"""Cas d'usage PAM de fusion, sortie et permission."""
from __future__ import annotations

from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import logging

from sqlmodel import Session, select

from app.models import Dossier, Patient, Venue, Mouvement
from app.db import get_next_sequence
from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check
from app.models.identifiers import Identifier
from app.utils.booleans import as_bool
from app.services.pam_correlations import (
    _find_mouvement_by_movement_id,
    _identifier_tuple_for_classifier,
    validate_movement_timing,
)
from app.services.pam_extensions import (
    _apply_french_extension_segments_to_patient,
    _apply_zfv_to_mouvement,
)
from app.services.pam_intake import _parse_zbe_segment
from app.services.pam_cancellations import _handle_cancel_discharge

logger = logging.getLogger(__name__)

async def handle_merge_movement_message(
    session: Session,
    trigger: str,
    pid_data: Dict,
    pv1_data: Dict,
    message: Optional[str] = None,
    ej_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Traitement de A45 (Fusion de mouvement) : fusionne deux enregistrements de mouvement —
    le mouvement identifié via PV1-19 (visit_number, l'ancien enregistrement) voit son
    identifiant métier (mouvement_seq) et ses identifiants (table Identifier) rattachés au
    nouveau movement_id porté par ZBE-1. L'ancien mouvement est marqué "merged" plutôt que
    supprimé, pour conserver la traçabilité (même logique que `handle_merge_patient` au
    niveau Patient, appliquée ici au niveau Mouvement).

    Args:
        session: Session DB
        trigger: Code trigger (A45)
        pid_data: Données PID parsées
        pv1_data: Données PV1 parsées
        message: Message HL7 complet (requis pour parser ZBE)
        ej_id: ID de l'entité juridique

    Returns:
        Tuple[bool, Optional[str]]: (succès, message d'erreur)
    """
    try:
        logger.info(f"[pam][merge_movement] Processing {trigger} message")

        zbe_data = _parse_zbe_segment(message) if message else {}
        if not zbe_data:
            return False, f"Segment ZBE obligatoire manquant pour {trigger}"

        new_movement_id = zbe_data.get("movement_id")
        if not new_movement_id:
            return False, "ZBE-1 (nouvel identifiant de mouvement) requis pour fusion A45"

        visit_number = pv1_data.get("visit_number")
        if not visit_number:
            return False, "PV1-19 (visit_number) requis pour identifier le mouvement à fusionner"

        venue_id_str = visit_number.split("^")[0] if "^" in visit_number else visit_number
        try:
            venue_seq = int(venue_id_str)
        except ValueError:
            return False, f"Format visit_number invalide: {visit_number}"

        venue = session.exec(select(Venue).where(Venue.venue_seq == venue_seq)).first()
        if not venue:
            return False, f"Venue {venue_seq} introuvable pour fusion de mouvement"

        mouvement = session.exec(
            select(Mouvement).where(Mouvement.venue_id == venue.id).order_by(Mouvement.when.desc())
        ).first()
        if not mouvement:
            return False, f"Aucun mouvement à fusionner sur la venue {venue_seq}"

        try:
            new_seq = int(new_movement_id)
        except ValueError:
            return False, f"Format movement_id invalide: {new_movement_id}"

        mouvement.mouvement_seq = new_seq
        mouvement.status = "merged"
        session.add(mouvement)
        session.flush()
        logger.info(f"[pam][merge_movement] Merged movement on venue {venue_seq} into mouvement_seq {new_seq}")
        return True, None

    except Exception as e:
        logger.error(f"[pam][merge_movement] Error: {e}", exc_info=True)
        return False, str(e)


# -------------------------------------------------------------
# HANDLER POUR LES SORTIES (A03, A13)
# -------------------------------------------------------------
async def handle_discharge_message(
    session: Session,
    trigger: str,
    pid_data: Dict,
    pv1_data: Dict,
    message: Optional[str] = None,
    ej_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Traitement des messages de sortie patient (A03) et d'annulation de sortie (A13).
    
    Pour A03 : Crée un mouvement de sortie sur une venue existante
    Pour A13 : Annule un mouvement de sortie existant
    
    Args:
        session: Session DB
        trigger: Code trigger (A03 ou A13)
        pid_data: Données PID parsées
        pv1_data: Données PV1 parsées
        message: Message HL7 complet (requis pour parser ZBE)
        ej_id: ID de l'entité juridique
        
    Returns:
        Tuple[bool, Optional[str]]: (succès, message d'erreur)
    """
    try:
        logger.info(f"[pam][discharge] Processing {trigger} message")
        
        # Parser le segment ZBE (obligatoire pour les mouvements)
        zbe_data = _parse_zbe_segment(message) if message else {}
        if not zbe_data:
            return False, f"Segment ZBE obligatoire manquant pour {trigger}"
        
        # Pour A13 (annulation), vérifier qu'on a un mouvement à annuler
        if trigger == "A13":
            return await _handle_cancel_discharge(session, trigger, pid_data, pv1_data, message, ej_id)
        
        # Pour A03 (sortie), créer un mouvement de sortie sur venue existante
        
        # Identifier la venue existante via PV1-19 (visit_number)
        visit_number = pv1_data.get("visit_number")
        if not visit_number:
            return False, "PV1-19 (visit_number) requis pour identifier la venue de sortie"
        
        # Extraire l'ID de la venue
        venue_id_str = visit_number.split("^")[0] if "^" in visit_number else visit_number
        try:
            venue_seq = int(venue_id_str)
        except ValueError:
            return False, f"Format visit_number invalide: {visit_number}"
        
        # Trouver la venue existante
        venue = session.exec(select(Venue).where(Venue.venue_seq == venue_seq)).first()
        if not venue:
            return False, f"Venue {venue_seq} introuvable pour sortie"
        
        # Créer le mouvement de sortie. Comme pour les admissions, conserver
        # l'identifiant métier ZBE-1 lorsqu'il est numérique : il permet à un
        # récepteur de rejouer fidèlement le mouvement et d'adresser ensuite
        # ses annulations/corrections.
        m_seq = get_next_sequence(session, "mouvement")
        movement_id = zbe_data.get("movement_id")
        if movement_id:
            try:
                m_seq = int(movement_id.split("^")[0])
            except (ValueError, TypeError):
                logger.warning("[pam][discharge] ZBE-1 non numérique, séquence locale conservée: %s", movement_id)
        
        # Déterminer la date du mouvement
        movement_datetime = datetime.now(timezone.utc)
        if zbe_data and zbe_data.get("movement_datetime"):
            try:
                dt_str = zbe_data["movement_datetime"]
                movement_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"[pam][discharge] Failed to parse ZBE-2 datetime '{dt_str}': {e}")
        
        # Valider l'écart temporel avec le dernier mouvement
        try:
            validate_movement_timing(session, venue.id, movement_datetime)
        except ValueError as e:
            return False, str(e)
        
        # Créer le mouvement
        mouvement = Mouvement(
            mouvement_seq=m_seq,
            venue_id=venue.id,
            entite_juridique_id=ej_id,
            type=f"ADT^{trigger}",
            when=movement_datetime,
            status="completed",
            trigger_event=trigger,
            movement_type="sortie",
            # UF depuis ZBE
            uf_responsabilite=zbe_data.get("uf_medicale"),
            uf_soins_code=zbe_data.get("uf_soins_code"),
            uf_soins_label=zbe_data.get("uf_soins_label"),
            nature=zbe_data.get("nature"),
            # Métadonnées ZBE
            action=zbe_data.get("action"),
            is_historic=as_bool(zbe_data.get("is_historic")),
            original_trigger=zbe_data.get("original_trigger")
        )
        _apply_zfv_to_mouvement(mouvement, message)

        session.add(mouvement)
        session.flush()
        logger.info(f"[pam][discharge] Created discharge movement id={mouvement.id} mouvement_seq={mouvement.mouvement_seq} on venue {venue.venue_seq}")

        dossier = session.get(Dossier, venue.dossier_id)
        if dossier:
            patient = session.get(Patient, dossier.patient_id)
            if patient:
                _apply_french_extension_segments_to_patient(patient, message)
                session.add(patient)
        
        # Créer les identifiants pour le mouvement (ZBE-1)
        movement_id = zbe_data.get("movement_id")
        if movement_id:
            mouvement_identifiers = _identifier_tuple_for_classifier(movement_id)
            if mouvement_identifiers:
                _res = await create_identifiers_from_hl7_with_namespace_check(
                    [mouvement_identifiers], "mouvement", session, ej_id
                )
                for ident in (_res[0] if _res else []):
                    ident.mouvement_id = mouvement.id
                    exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                    if not exists_dup:
                        session.add(ident)

        return True, None
        
    except Exception as e:
        logger.error(f"[pam][discharge] Error: {e}", exc_info=True)
        return False, str(e)


# -------------------------------------------------------------
# HANDLER POUR LES PERMISSIONS (A21, A22, A52, A53)
# -------------------------------------------------------------
async def handle_leave_message(
    session: Session,
    trigger: str,
    pid_data: Dict,
    pv1_data: Dict,
    message: Optional[str] = None,
    ej_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Traitement des messages de permission/absence patient.
    
    A21 : Début d'absence (leave out)
    A22 : Retour d'absence (leave return)  
    A52 : Annulation début d'absence
    A53 : Annulation retour d'absence
    
    Args:
        session: Session DB
        trigger: Code trigger (A21, A22, A52, A53)
        pid_data: Données PID parsées
        pv1_data: Données PV1 parsées
        message: Message HL7 complet (requis pour parser ZBE)
        ej_id: ID de l'entité juridique
        
    Returns:
        Tuple[bool, Optional[str]]: (succès, message d'erreur)
    """
    try:
        logger.info(f"[pam][leave] Processing {trigger} message")
        
        # Parser le segment ZBE (obligatoire pour les mouvements)
        zbe_data = _parse_zbe_segment(message) if message else {}
        if not zbe_data:
            return False, f"Segment ZBE obligatoire manquant pour {trigger}"
        
        # Pour les annulations A52/A53, vérifier qu'on a un mouvement à annuler
        if trigger in ("A52", "A53"):
            movement_id = zbe_data.get("movement_id")
            if not movement_id:
                return False, f"ZBE-1 (movement_id) requis pour annulation {trigger}"

            # Trouver et annuler le mouvement
            mouvement = _find_mouvement_by_movement_id(session, movement_id)
            if not mouvement:
                return False, f"Mouvement {movement_id} introuvable pour annulation"

            mouvement.status = "cancelled"
            session.add(mouvement)
            session.flush()
            logger.info(f"[pam][leave] Cancelled movement {movement_id}")
            return True, None
        
        # Pour A21/A22, créer un mouvement sur venue existante
        
        # Identifier la venue existante via PV1-19 (visit_number)
        visit_number = pv1_data.get("visit_number")
        if not visit_number:
            return False, f"PV1-19 (visit_number) requis pour {trigger}"
        
        # Extraire l'ID de la venue
        venue_id_str = visit_number.split("^")[0] if "^" in visit_number else visit_number
        try:
            venue_seq = int(venue_id_str)
        except ValueError:
            return False, f"Format visit_number invalide: {visit_number}"
        
        # Trouver la venue existante
        venue = session.exec(select(Venue).where(Venue.venue_seq == venue_seq)).first()
        if not venue:
            return False, f"Venue {venue_seq} introuvable pour {trigger}"
        
        # Créer le mouvement
        m_seq = get_next_sequence(session, "mouvement")
        
        # Déterminer la date du mouvement
        movement_datetime = datetime.now(timezone.utc)
        if zbe_data and zbe_data.get("movement_datetime"):
            try:
                dt_str = zbe_data["movement_datetime"]
                movement_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"[pam][leave] Failed to parse ZBE-2 datetime '{dt_str}': {e}")
        
        # Valider l'écart temporel avec le dernier mouvement
        try:
            validate_movement_timing(session, venue.id, movement_datetime)
        except ValueError as e:
            return False, str(e)
        
        # Déterminer le type de mouvement
        if trigger == "A21":
            movement_type = "permission_debut"
            status = "leave"
        elif trigger == "A22":
            movement_type = "permission_retour"
            status = "completed"
        else:
            movement_type = "permission"
            status = "completed"
        
        # Créer le mouvement
        mouvement = Mouvement(
            mouvement_seq=m_seq,
            venue_id=venue.id,
            entite_juridique_id=ej_id,
            type=f"ADT^{trigger}",
            when=movement_datetime,
            status=status,
            trigger_event=trigger,
            movement_type=movement_type,
            # UF depuis ZBE
            uf_responsabilite=zbe_data.get("uf_medicale"),
            uf_soins_code=zbe_data.get("uf_soins_code"),
            uf_soins_label=zbe_data.get("uf_soins_label"),
            nature=zbe_data.get("nature"),
            # Métadonnées ZBE
            action=zbe_data.get("action"),
            is_historic=as_bool(zbe_data.get("is_historic")),
            original_trigger=zbe_data.get("original_trigger")
        )
        
        session.add(mouvement)
        session.flush()
        logger.info(f"[pam][leave] Created leave movement id={mouvement.id} mouvement_seq={mouvement.mouvement_seq} on venue {venue.venue_seq}")
        
        # Créer les identifiants pour le mouvement (ZBE-1)
        movement_id = zbe_data.get("movement_id")
        if movement_id:
            mouvement_identifiers = _identifier_tuple_for_classifier(movement_id)
            if mouvement_identifiers:
                _res = await create_identifiers_from_hl7_with_namespace_check(
                    session, [mouvement_identifiers], mouvement, "mouvement"
                )
                for ident in (_res[0] if _res else []):
                    ident.mouvement_id = mouvement.id
                    exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                    if not exists_dup:
                        session.add(ident)

        return True, None
        
    except Exception as e:
        logger.error(f"[pam][leave] Error: {e}", exc_info=True)
        return False, str(e)
