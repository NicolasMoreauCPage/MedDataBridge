"""Annulations d'admission, de sortie et de transfert PAM."""
from __future__ import annotations

from typing import Optional, Tuple
from datetime import datetime, timezone
import logging

from sqlmodel import Session, select

from app.models import Dossier, Patient, Venue, Mouvement
from app.db import get_next_sequence
from app.services.pam_correlations import (
    _find_mouvement_by_movement_id,
)
from app.services.pam_intake import _parse_zbe_segment
from app.services.pam_constants import MOVEMENT_KIND_BY_TRIGGER, MOVEMENT_STATUS_BY_TRIGGER

logger = logging.getLogger(__name__)

async def _handle_cancel_admission(
    session: Session,
    trigger: str,
    pid_data: dict,
    pv1_data: dict,
    message: Optional[str],
    ej_id: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Gère les annulations d'admission (A11, A23, A38).
    
    Parse le segment ZBE-1 pour identifier le mouvement à annuler,
    puis crée un nouveau mouvement d'annulation.
    """
    try:
        # Parser ZBE pour obtenir le movement_id à annuler
        zbe_data = _parse_zbe_segment(message) if message else None
        
        if not zbe_data or not zbe_data.get("movement_id"):
            logger.warning(f"[pam][cancel] {trigger}: No ZBE segment or movement_id found, fallback to last movement")
            # Solution de repli: chercher le dernier mouvement du patient
            identifiers = pid_data.get("identifiers", [])
            if not identifiers:
                return False, "No patient identifier found"
            identifier = identifiers[0][0].split("^")[0]
            
            # use global select
            patient = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
            if not patient:
                return False, "Patient not found"
            
            dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
            if not dossier:
                return False, "Dossier not found"
            
            venue = session.exec(
                select(Venue)
                .where(Venue.dossier_id == dossier.id)
                .order_by(Venue.venue_seq.desc())
            ).first()
            if not venue:
                return False, "Venue not found"
            
            # Trouver le dernier mouvement d'admission
            original_mouvement = session.exec(
                select(Mouvement)
                .where(Mouvement.venue_id == venue.id)
                .where(Mouvement.movement_type.in_(["admission", "preadmission", "registration"]))
                .order_by(Mouvement.when.desc())
            ).first()
        else:
            # Utiliser ZBE-1 pour trouver le mouvement spécifique
            movement_id_str = zbe_data["movement_id"]
            logger.info(f"[pam][cancel] {trigger}: Looking for movement with seq={movement_id_str}")

            original_mouvement = _find_mouvement_by_movement_id(session, movement_id_str)

            if not original_mouvement:
                logger.warning(f"[pam][cancel] {trigger}: Movement seq={movement_id_str} not found, trying fallback by patient")
                # Solution de repli: chercher le dernier mouvement du patient
                identifiers = pid_data.get("identifiers", [])
                if not identifiers:
                    return False, f"Movement with seq={movement_id_str} not found (no patient identifier for fallback)"
                identifier = identifiers[0][0].split("^")[0]
                
                patient = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
                if not patient:
                    return False, f"Movement with seq={movement_id_str} not found (patient not found for fallback)"
                
                dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
                if not dossier:
                    return False, f"Movement with seq={movement_id_str} not found (dossier not found for fallback)"
                
                venue = session.exec(
                    select(Venue)
                    .where(Venue.dossier_id == dossier.id)
                    .order_by(Venue.venue_seq.desc())
                ).first()
                if not venue:
                    return False, f"Movement with seq={movement_id_str} not found (venue not found for fallback)"
                
                # Trouver le dernier mouvement d'admission
                original_mouvement = session.exec(
                    select(Mouvement)
                    .where(Mouvement.venue_id == venue.id)
                    .where(Mouvement.movement_type.in_(["admission", "preadmission", "registration"]))
                    .order_by(Mouvement.when.desc())
                ).first()
                
                if not original_mouvement:
                    return False, f"Movement with seq={movement_id_str} not found (no admission movement for fallback)"
            else:
                venue = original_mouvement.venue
        
        if not original_mouvement:
            return False, "No admission movement found to cancel"
        
        # Créer un nouveau mouvement d'annulation
        m_seq = get_next_sequence(session, "mouvement")
        cancel_mouvement = Mouvement(
            mouvement_seq=m_seq,
            venue_id=venue.id,
            type=f"ADT^{trigger}",
            when=datetime.now(timezone.utc),
            status=MOVEMENT_STATUS_BY_TRIGGER.get(trigger, "cancelled"),
            movement_type=MOVEMENT_KIND_BY_TRIGGER.get(trigger, "admission-cancel"),
            trigger_event=trigger,  # Pour validation des transitions IHE PAM
            location=original_mouvement.location,
            from_location=original_mouvement.from_location,
            to_location=original_mouvement.to_location,
            entite_juridique_id=ej_id,
        )
        session.add(cancel_mouvement)
        
        # Mettre à jour le statut du mouvement original
        original_mouvement.status = "cancelled"
        session.add(original_mouvement)
        
        # ``Venue`` ne porte pas de statut opérationnel dans notre modèle ;
        # l'annulation est représentée par le mouvement A11 et l'état du
        # mouvement d'origine, sans écrire un attribut fantôme.
        session.add(venue)
        
        session.flush()
        
        logger.info(
            f"[pam][cancel] {trigger}: Created cancel movement seq={cancel_mouvement.mouvement_seq} "
            f"cancelling original movement seq={original_mouvement.mouvement_seq}"
        )
        
        return True, None
        
    except Exception as e:
        logger.error(f"[pam][cancel] {trigger} failed: {e}", exc_info=True)
        return False, str(e)


async def _handle_cancel_discharge(
    session: Session,
    trigger: str,
    pid_data: dict,
    pv1_data: dict,
    message: Optional[str],
    ej_id: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Gère l'annulation de sortie (A13).
    
    Parse le segment ZBE-1 pour identifier le mouvement à annuler,
    puis crée un nouveau mouvement d'annulation.
    """
    try:
        # Parser ZBE pour obtenir le movement_id à annuler
        zbe_data = _parse_zbe_segment(message) if message else None
        
        if not zbe_data or not zbe_data.get("movement_id"):
            logger.warning("[pam][cancel-discharge] No ZBE segment, fallback to last discharge")
            # Solution de repli: chercher la dernière sortie
            identifiers = pid_data.get("identifiers", [])
            if not identifiers:
                return False, "No patient identifier found"
            identifier = identifiers[0][0].split("^")[0]
            
            # use global select
            patient = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
            if not patient:
                return False, "Patient not found"
            
            dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
            if not dossier:
                return False, "Dossier not found"
            
            venue = session.exec(
                select(Venue)
                .where(Venue.dossier_id == dossier.id)
                .order_by(Venue.venue_seq.desc())
            ).first()
            if not venue:
                return False, "Venue not found"
            
            # Trouver la dernière sortie
            original_mouvement = session.exec(
                select(Mouvement)
                .where(Mouvement.venue_id == venue.id, Mouvement.type == "ADT^A03")
                .order_by(Mouvement.when.desc())
            ).first()
        else:
            # Utiliser ZBE-1
            movement_id_str = zbe_data["movement_id"]
            logger.info(f"[pam][cancel-discharge] Looking for movement seq={movement_id_str}")

            original_mouvement = _find_mouvement_by_movement_id(session, movement_id_str)

            if not original_mouvement:
                logger.warning(f"[pam][cancel-discharge]: Movement seq={movement_id_str} not found, trying fallback")
                # Solution de repli: chercher la dernière sortie
                identifiers = pid_data.get("identifiers", [])
                if not identifiers:
                    return False, f"Movement with seq={movement_id_str} not found (no patient identifier for fallback)"
                identifier = identifiers[0][0].split("^")[0]
                
                patient = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
                if not patient:
                    return False, f"Movement with seq={movement_id_str} not found (patient not found for fallback)"
                
                dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
                if not dossier:
                    return False, f"Movement with seq={movement_id_str} not found (dossier not found for fallback)"
                
                venue = session.exec(
                    select(Venue)
                    .where(Venue.dossier_id == dossier.id)
                    .order_by(Venue.venue_seq.desc())
                ).first()
                if not venue:
                    return False, f"Movement with seq={movement_id_str} not found (venue not found for fallback)"
                
                # Trouver la dernière sortie
                original_mouvement = session.exec(
                    select(Mouvement)
                    .where(Mouvement.venue_id == venue.id, Mouvement.type == "ADT^A03")
                    .order_by(Mouvement.when.desc())
                ).first()
                
                if not original_mouvement:
                    return False, f"Movement with seq={movement_id_str} not found (no discharge movement for fallback)"
            else:
                venue = original_mouvement.venue
        
        if not original_mouvement:
            return False, "No discharge movement found to cancel"
        
        # Déterminer la date du mouvement d'annulation : priorité ZBE-2 puis now
        cancel_datetime = datetime.now(timezone.utc)
        if zbe_data and zbe_data.get("movement_datetime"):
            try:
                dt_str = zbe_data["movement_datetime"]
                cancel_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"[pam][cancel-discharge] Failed to parse ZBE-2 datetime '{dt_str}': {e}")

        # Créer mouvement d'annulation
        m_seq = get_next_sequence(session, "mouvement")
        cancel_mouvement = Mouvement(
            mouvement_seq=m_seq,
            venue_id=venue.id,
            type=f"ADT^{trigger}",
            when=cancel_datetime,
            status="cancelled",
            movement_type="discharge-cancel",
            trigger_event=trigger,  # Pour validation des transitions IHE PAM
            location=original_mouvement.location,
            from_location=original_mouvement.from_location,
            to_location=original_mouvement.to_location,
            cancelled_movement_seq=original_mouvement.mouvement_seq,
            entite_juridique_id=ej_id,
        )
        session.add(cancel_mouvement)
        
        # Annuler le mouvement original
        original_mouvement.status = "cancelled"
        session.add(original_mouvement)
        
        # Venue ne porte pas de statut opérationnel : celui-ci appartient aux
        # ressources de structure (lit/chambre). La réactivation du séjour se
        # déduit de l'annulation du mouvement de sortie ci-dessus.
        dossier = venue.dossier
        dossier.discharge_time = None
        
        session.add(venue)
        session.add(dossier)
        session.flush()
        
        logger.info(
            f"[pam][cancel-discharge] Created cancel movement seq={cancel_mouvement.mouvement_seq} "
            f"cancelling discharge seq={original_mouvement.mouvement_seq}"
        )
        
        return True, None
        
    except Exception as e:
        logger.error(f"[pam][cancel-discharge] failed: {e}", exc_info=True)
        return False, str(e)


async def _handle_cancel_transfer(
    session: Session,
    trigger: str,
    pid_data: dict,
    pv1_data: dict,
    message: Optional[str],
    ej_id: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Gère l'annulation de transfert (A12).
    
    Parse le segment ZBE-1 pour identifier le mouvement à annuler,
    puis crée un nouveau mouvement d'annulation.
    """
    try:
        # Parser ZBE pour obtenir le movement_id à annuler
        zbe_data = _parse_zbe_segment(message) if message else None
        
        if not zbe_data or not zbe_data.get("movement_id"):
            logger.warning("[pam][cancel-transfer] No ZBE segment, fallback to last transfer")
            # Solution de repli: chercher le dernier transfert
            identifiers = pid_data.get("identifiers", [])
            if not identifiers:
                return False, "No patient identifier found"
            identifier = identifiers[0][0].split("^")[0]
            
            # use global select
            patient = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
            if not patient:
                return False, "Patient not found"
            
            dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
            if not dossier:
                return False, "Dossier not found"
            
            venue = session.exec(
                select(Venue)
                .where(Venue.dossier_id == dossier.id)
                .order_by(Venue.venue_seq.desc())
            ).first()
            if not venue:
                return False, "Venue not found"
            
            # Trouver le dernier transfert
            original_mouvement = session.exec(
                select(Mouvement)
                .where(Mouvement.venue_id == venue.id, Mouvement.type == "ADT^A02")
                .order_by(Mouvement.when.desc())
            ).first()
        else:
            # Utiliser ZBE-1
            movement_id_str = zbe_data["movement_id"]
            logger.info(f"[pam][cancel-transfer] Looking for movement seq={movement_id_str}")

            original_mouvement = _find_mouvement_by_movement_id(session, movement_id_str)

            if not original_mouvement:
                logger.warning(f"[pam][cancel-transfer]: Movement seq={movement_id_str} not found, trying fallback")
                # Solution de repli: chercher le dernier transfert
                identifiers = pid_data.get("identifiers", [])
                if not identifiers:
                    return False, f"Movement with seq={movement_id_str} not found (no patient identifier for fallback)"
                identifier = identifiers[0][0].split("^")[0]
                
                patient = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
                if not patient:
                    return False, f"Movement with seq={movement_id_str} not found (patient not found for fallback)"
                
                dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
                if not dossier:
                    return False, f"Movement with seq={movement_id_str} not found (dossier not found for fallback)"
                
                venue = session.exec(
                    select(Venue)
                    .where(Venue.dossier_id == dossier.id)
                    .order_by(Venue.venue_seq.desc())
                ).first()
                if not venue:
                    return False, f"Movement with seq={movement_id_str} not found (venue not found for fallback)"
                
                # Trouver le dernier transfert
                original_mouvement = session.exec(
                    select(Mouvement)
                    .where(Mouvement.venue_id == venue.id, Mouvement.type == "ADT^A02")
                    .order_by(Mouvement.when.desc())
                ).first()
                
                if not original_mouvement:
                    return False, f"Movement with seq={movement_id_str} not found (no transfer movement for fallback)"
            else:
                venue = original_mouvement.venue
        
        if not original_mouvement:
            return False, "No transfer movement found to cancel"
        
        # Déterminer la date du mouvement d'annulation : priorité ZBE-2 puis now
        cancel_datetime = datetime.now(timezone.utc)
        if zbe_data and zbe_data.get("movement_datetime"):
            try:
                dt_str = zbe_data["movement_datetime"]
                cancel_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"[pam][cancel-transfer] Failed to parse ZBE-2 datetime '{dt_str}': {e}")

        # Créer mouvement d'annulation
        m_seq = get_next_sequence(session, "mouvement")
        cancel_mouvement = Mouvement(
            mouvement_seq=m_seq,
            venue_id=venue.id,
            type=f"ADT^{trigger}",
            when=cancel_datetime,
            status="cancelled",
            movement_type="transfer-cancel",
            trigger_event=trigger,  # Pour validation des transitions IHE PAM
            location=original_mouvement.from_location,
            from_location=original_mouvement.to_location,
            to_location=original_mouvement.from_location,
            cancelled_movement_seq=original_mouvement.mouvement_seq,
            entite_juridique_id=ej_id,
        )
        session.add(cancel_mouvement)
        
        # Annuler le mouvement original
        original_mouvement.status = "cancelled"
        session.add(original_mouvement)
        
        # Restaurer la location précédente
        if original_mouvement.from_location:
            venue.assigned_location = original_mouvement.from_location
            session.add(venue)
        
        session.flush()
        
        logger.info(
            f"[pam][cancel-transfer] Created cancel movement seq={cancel_mouvement.mouvement_seq} "
            f"cancelling transfer seq={original_mouvement.mouvement_seq}"
        )
        
        return True, None
        
    except Exception as e:
        logger.error(f"[pam][cancel-transfer] failed: {e}", exc_info=True)
        return False, str(e)

