"""Cas d'usage PAM liés aux médecins, transferts et changements de compte."""
from __future__ import annotations

from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import logging

from sqlmodel import Session, select

from app.models import Dossier, Patient, Venue, Mouvement
from app.db import get_next_sequence
from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check, parse_hl7_cx_identifier, create_identifier_from_hl7
from app.models_identifiers import Identifier
from app.utils.booleans import as_bool
from app.services.pam_correlations import (
    _identifier_tuple_for_classifier,
    validate_movement_timing,
)
from app.services.pam_extensions import (
    _apply_french_extension_segments_to_patient,
    _apply_zfv_to_mouvement,
)
from app.services.pam_intake import _parse_zbe_segment
from app.services.pam_cancellations import _handle_cancel_transfer

logger = logging.getLogger(__name__)


async def handle_doctor_message(
    session: Session, 
    trigger: str, 
    pid_data: dict, 
    pv1_data: dict,
    message: Optional[str] = None,
    ej_id: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Gère les messages de changement de médecin (A54/A55).
    IHE PAM: Change attending doctor
    
    A54: Changement de médecin responsable
    A55: Annulation du changement de médecin
    """
    try:
        # Parser le segment ZBE (présent dans TOUS les messages IHE PAM)
        zbe_data = _parse_zbe_segment(message) if message else None
        if zbe_data:
            logger.info(f"[pam][doctor] ZBE parsed: {zbe_data}")
        
        # Extraire les identifiants supplémentaires pour classification EJ
        account_number = pid_data.get("account_number")
        visit_number = pv1_data.get("visit_number") 
        movement_id = zbe_data.get("movement_id") if zbe_data else None
        
        identifiers = pid_data.get("identifiers", [])
        if not identifiers:
            return False, "No patient identifier found"
        identifier = identifiers[0][0].split("^")[0]

        # use global select
        patient = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
        if not patient:
            return False, "Patient not found"

        # Find active dossier
        dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
        if not dossier:
            return False, "Dossier not found"

        # Find current venue
        venue = session.exec(
            select(Venue)
            .where(Venue.dossier_id == dossier.id)
            .order_by(Venue.venue_seq.desc())
        ).first()
        if not venue:
            return False, "Venue not found"

        # Get attending doctor from PV1-7 or PV1-17
        attending_doctor = (pv1_data.get("attending_doctor") or "").strip()
        
        # Déterminer la date du mouvement : priorité ZBE-2, puis now
        movement_datetime = datetime.now(timezone.utc)
        if zbe_data and zbe_data.get("movement_datetime"):
            try:
                dt_str = zbe_data["movement_datetime"]
                movement_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"[pam][doctor] Failed to parse ZBE-2 datetime '{dt_str}': {e}")
        
        if trigger == "A54":
            # Change attending doctor
            if attending_doctor:
                venue.attending_doctor = attending_doctor
                dossier.attending_provider = attending_doctor
            
            # Create mouvement for doctor change
            m_seq = get_next_sequence(session, "mouvement")
            
            # Valider l'écart temporel avec le dernier mouvement
            try:
                validate_movement_timing(session, venue.id, movement_datetime)
            except ValueError as e:
                return False, str(e)
            
            mouvement = Mouvement(
                mouvement_seq=m_seq,
                venue_id=venue.id,
                type=f"ADT^{trigger}",
                when=movement_datetime,
                status="completed",
                movement_type="doctor-change",
                trigger_event=trigger,  # Pour validation des transitions IHE PAM
                location=venue.assigned_location,
                entite_juridique_id=ej_id,
            )
            session.add(mouvement)
            
        elif trigger == "A55":
            # Cancel doctor change - revert to previous
            # In real implementation, would need to track previous doctor
            # For now, just create a cancel mouvement
            m_seq = get_next_sequence(session, "mouvement")
            mouvement = Mouvement(
                mouvement_seq=m_seq,
                venue_id=venue.id,
                type=f"ADT^{trigger}",
                when=movement_datetime,
                status="cancelled",
                movement_type="doctor-change-cancel",
                trigger_event=trigger,  # Pour validation des transitions IHE PAM
                location=venue.assigned_location,
                entite_juridique_id=ej_id,
            )
            session.add(mouvement)
        
        session.add(venue)
        session.add(dossier)
        session.flush()
        
        logger.info(f"[pam][doctor] Processed {trigger} for venue_id={venue.id}")
        
        # Traiter les identifiants supplémentaires avec classification EJ
        # Dossier identifiers (PID-18)
        if account_number:
            dossier_identifiers = _identifier_tuple_for_classifier(account_number)
            if dossier_identifiers:
                _res = await create_identifiers_from_hl7_with_namespace_check(
                    session, [dossier_identifiers], dossier, "dossier"
                )
                for ident in (_res[0] if _res else []):
                    ident.dossier_id = dossier.id
                    exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                    if not exists_dup:
                        session.add(ident)

        # Venue identifiers (PV1-19)
        if visit_number:
            venue_identifiers = _identifier_tuple_for_classifier(visit_number)
            if venue_identifiers:
                _res = await create_identifiers_from_hl7_with_namespace_check(
                    session, [venue_identifiers], venue, "venue"
                )
                for ident in (_res[0] if _res else []):
                    ident.venue_id = venue.id
                    exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                    if not exists_dup:
                        session.add(ident)

        # Mouvement identifiers (ZBE-1)
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

        # REMARQUE: Message emission is now automatic via entity_events.py listeners

        return True, None
    except Exception as e:
        logger.error(f"[pam][doctor] Error: {e}", exc_info=True)
        return False, str(e)


# -------------------------------------------------------------
# HANDLER POUR LES TRANSFERTS (A02, A12)
# -------------------------------------------------------------
async def handle_transfer_message(
    session: Session,
    trigger: str,
    pid_data: Dict,
    pv1_data: Dict,
    message: Optional[str] = None,
    ej_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Traitement des messages de transfert patient (A02) et d'annulation de transfert (A12).
    
    Pour A02 : Crée un nouveau mouvement sur une venue existante
    Pour A12 : Annule un mouvement de transfert existant
    
    Args:
        session: Session DB
        trigger: Code trigger (A02 ou A12)
        pid_data: Données PID parsées
        pv1_data: Données PV1 parsées
        message: Message HL7 complet (requis pour parser ZBE)
        ej_id: ID de l'entité juridique
        
    Returns:
        Tuple[bool, Optional[str]]: (succès, message d'erreur)
    """
    try:
        logger.info(f"[pam][transfer] Processing {trigger} message")
        
        # Parser le segment ZBE (obligatoire pour les mouvements)
        zbe_data = _parse_zbe_segment(message) if message else {}
        if not zbe_data:
            return False, f"Segment ZBE obligatoire manquant pour {trigger}"
        
        # Pour A12 (annulation), vérifier qu'on a un mouvement à annuler
        if trigger == "A12":
            return await _handle_cancel_transfer(session, trigger, pid_data, pv1_data, message, ej_id)
        
        # Pour A02 (transfert), créer un nouveau mouvement sur venue existante
        
        # Identifier la venue existante via PV1-19 (visit_number)
        visit_number = pv1_data.get("visit_number")
        if not visit_number:
            return False, "PV1-19 (visit_number) requis pour identifier la venue de transfert"
        
        # Extraire l'ID de la venue
        venue_id_str = visit_number.split("^")[0] if "^" in visit_number else visit_number
        try:
            venue_seq = int(venue_id_str)
        except ValueError:
            return False, f"Format visit_number invalide: {visit_number}"
        
        # Trouver la venue existante
        venue = session.exec(select(Venue).where(Venue.venue_seq == venue_seq)).first()
        if not venue:
            return False, f"Venue {venue_seq} introuvable pour transfert"
        
        # Créer le mouvement de transfert
        m_seq = get_next_sequence(session, "mouvement")

        # Déterminer la date du mouvement
        movement_datetime = datetime.now(timezone.utc)
        if zbe_data and zbe_data.get("movement_datetime"):
            try:
                dt_str = zbe_data["movement_datetime"]
                movement_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"[pam][transfer] Failed to parse ZBE-2 datetime '{dt_str}': {e}")
        
        # Valider l'écart temporel avec le dernier mouvement
        try:
            validate_movement_timing(session, venue.id, movement_datetime)
        except ValueError as e:
            return False, str(e)
        
        # Déterminer les localisations de/vers
        from_location = pv1_data.get("previous_location") or ""
        to_location = pv1_data.get("location") or ""
        
        # Créer le mouvement
        mouvement = Mouvement(
            mouvement_seq=m_seq,
            venue_id=venue.id,
            entite_juridique_id=ej_id,
            type=f"ADT^{trigger}",
            when=movement_datetime,
            location=to_location,
            from_location=from_location,
            to_location=to_location,
            status="completed",
            trigger_event=trigger,
            movement_type="transfert",
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
        logger.info(f"[pam][transfer] Created transfer movement id={mouvement.id} mouvement_seq={mouvement.mouvement_seq} on venue {venue.venue_seq}")

        # Segments ZFD/ZFA/ZFP/ROL portent sur le patient, pas sur le mouvement — s'ils sont
        # présents dans ce message de transfert, on met aussi à jour le patient de la venue.
        dossier = session.get(Dossier, venue.dossier_id)
        if dossier:
            patient = session.get(Patient, dossier.patient_id)
            if patient:
                _apply_french_extension_segments_to_patient(patient, message)
                session.add(patient)
        
        # Créer les identifiants pour le mouvement (ZBE-1, répétable : on enregistre chaque
        # identifiant porté par la répétition, pas seulement le premier)
        for movement_id in zbe_data.get("movement_ids") or []:
            if parse_hl7_cx_identifier(movement_id):
                identifier = create_identifier_from_hl7(movement_id, "mouvement", mouvement.id)
                session.add(identifier)
        
        return True, None
        
    except Exception as e:
        logger.error(f"[pam][transfer] Error: {e}", exc_info=True)
        return False, str(e)


# -------------------------------------------------------------
# HANDLERS A44/A45
# -------------------------------------------------------------
async def handle_move_account_message(
    session: Session,
    trigger: str,
    pid_data: Dict,
    pv1_data: Dict,
    message: Optional[str] = None,
    ej_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """Réattribue le dossier administratif d'un patient à un autre (ADT^A44).

    PID-3 identifie le nouveau patient, PID-18 le dossier administratif et
    MRG-1 l'ancien patient. ZBE peut être présent suivant le correspondant,
    mais n'est pas la clé de la réattribution et ne doit pas être exigé pour
    accepter les messages CPage minimaux.

    Args:
        session: Session DB
        trigger: Code trigger (A44)
        pid_data: Données PID parsées
        pv1_data: Données PV1 parsées
        message: Message HL7 complet (requis pour parser ZBE)
        ej_id: ID de l'entité juridique

    Returns:
        Tuple[bool, Optional[str]]: (succès, message d'erreur)
    """
    try:
        logger.info(f"[pam][move_account] Processing {trigger} message")

        from app.services.patient_merge import _find_patient_by_identifiers, _parse_mrg_segment

        if not message:
            return False, "Message complet requis pour A44"
        mrg_data = _parse_mrg_segment(message)
        if not mrg_data or not mrg_data.get("identifiers"):
            return False, "MRG-1 (ancien identifiant patient) est requis pour A44"

        target_identifiers = [cx for cx, _type in (pid_data.get("identifiers") or [])]
        target_patient = _find_patient_by_identifiers(session, target_identifiers)
        if not target_patient:
            target_identifier = pid_data.get("external_id") or (target_identifiers[0].split("^")[0] if target_identifiers else None)
            if not target_identifier:
                return False, "PID-3 (nouvel identifiant patient) est requis pour A44"
            target_patient = Patient(
                identifier=target_identifier,
                family=pid_data.get("family") or "",
                given=pid_data.get("given") or "",
                gender=pid_data.get("gender") or "unknown",
            )
            session.add(target_patient)
            session.flush()

        source_patient = _find_patient_by_identifiers(session, mrg_data["identifiers"])
        if not source_patient:
            return False, "Patient source introuvable avec MRG-1 pour A44"
        if source_patient.id == target_patient.id:
            return False, "A44 invalide : le patient source et le nouveau patient sont identiques"

        account = pid_data.get("account_number")
        account_value = account.split("^")[0] if account else ""
        if not account_value:
            return False, "PID-18 (numéro de dossier administratif) est requis pour A44"
        try:
            dossier_seq = int(account_value)
        except (TypeError, ValueError):
            return False, f"PID-18 non exploitable comme numéro de dossier: {account_value}"
        dossier = session.exec(select(Dossier).where(Dossier.dossier_seq == dossier_seq)).first()
        if not dossier:
            return False, f"Dossier administratif {account_value} introuvable pour A44"
        if dossier.patient_id != source_patient.id:
            return False, "A44 incohérent : PID-18 n'est pas rattaché au patient indiqué dans MRG-1"

        dossier.patient_id = target_patient.id
        session.add(dossier)
        session.flush()
        logger.info("[pam][move_account] Dossier %s reassigned from patient %s to %s", dossier_seq, source_patient.id, target_patient.id)
        return True, None

    except Exception as e:
        logger.error(f"[pam][move_account] Error: {e}", exc_info=True)
        return False, str(e)
