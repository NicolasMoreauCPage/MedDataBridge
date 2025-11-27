from typing import Dict, List, Optional, Tuple, Any
from sqlmodel import Session, select
from datetime import datetime
import importlib
import logging
import re

from app.models import Dossier, Patient, Venue, Mouvement
from app.db import get_next_sequence
from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check, parse_hl7_cx_identifier, create_identifier_from_hl7
from app.models_identifiers import Identifier, IdentifierType
from app.services.vocabulary_translate import map_code
from app.services.vocabulary_translate import map_code

logger = logging.getLogger(__name__)

_adapter_module = None

try:
    _adapter_module = importlib.import_module("adapters.hl7_pam_fr")
except ModuleNotFoundError:
    build_message_for_movement = None  # pragma: no cover
else:
    build_message_for_movement = getattr(_adapter_module, "build_message_for_movement", None)


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


MOVEMENT_KIND_BY_TRIGGER = {
    # Événements Patient (pas de mouvement)
    "A28": "patient-add",       # Ajout patient (création)
    "A31": "patient-update",    # Mise à jour patient
    "A40": "patient-merge",     # Fusion de patients
    
    # Événements Admission
    "A04": "admission",         # Admission ambulatoire (consultation externe)
    "A05": "preadmission",      # Pré-admission
    "A06": "class-change",      # Changement classe ambulatoire → hospitalisation
    "A07": "class-change",      # Changement classe hospitalisation → ambulatoire
    
    # Événements Transfert/Sortie
    "A02": "transfer",          # Transfert
    "A03": "discharge",         # Sortie définitive
    "A21": "leave-out",         # Sortie temporaire (absence)
    "A22": "leave-return",      # Retour d'absence
    "A52": "leave-out-cancel",  # Annulation sortie temporaire
    "A53": "leave-return-cancel", # Annulation retour d'absence
    
    # Événements Annulation
    "A11": "admission-cancel",  # Annulation admission
    "A12": "transfer-cancel",   # Annulation transfert
    "A13": "discharge-cancel",  # Annulation sortie
    "A23": "registration-cancel", # Annulation enregistrement
    "A38": "preadmission-cancel", # Annulation pré-admission
    
    # Autres
    "A29": "patient-delete",    # Suppression patient
    "A54": "doctor-change",     # Changement médecin
    "A55": "doctor-change-cancel", # Annulation changement médecin
}

MOVEMENT_STATUS_BY_TRIGGER = {
    "A05": "planned",
    "A11": "cancelled",
    "A23": "cancelled",
    "A38": "cancelled",
    "A12": "cancelled",
    "A13": "cancelled",
    "A21": "leave",
    "A52": "leave",
    "A22": "completed",
    "A53": "completed",
    "A54": "completed",
    "A55": "cancelled",
}


# -------------------------------------------------------------
# API PRINCIPALE EXPOSEE AU RESTE DU CODE / TESTS
# -------------------------------------------------------------
def process_pam_message(session: Session, message: str) -> Dict[str, Any]:
    """Traite un message HL7 ADT (PAM) minimal.

    Implémentation simplifiée visant à satisfaire les tests d'intégration
    actuels qui vérifient surtout l'existence de la fonction. On parse
    quelques segments de base pour préparer une future logique métier.

    Args:
        session: Session SQLModel
        message: Chaîne HL7 (avec séparateurs CR ou LF)

    Returns:
        Dict résumant le parsing effectué.

    NOTE: Cette version ne crée pas encore d'entités. Les extensions
    pourront ajouter la logique complète (création Patient/Dossier/Venue,
    gestion annulations, etc.).
    """
    try:
        if not message or not message.startswith("MSH"):
            raise ValueError("Message HL7 invalide: MSH absent")

        lines = [l for l in re.split(r"\r|\n", message) if l.strip()]
        msh = next((l for l in lines if l.startswith("MSH")), None)
        pid = next((l for l in lines if l.startswith("PID")), None)
        pv1 = next((l for l in lines if l.startswith("PV1")), None)
        evn = next((l for l in lines if l.startswith("EVN")), None)

        trigger = None
        patient_identifier = None
        patient_name = None
        venue_location = None

        # MSH-9 contient ADT^A0X
        if msh:
            parts = msh.split("|")
            if len(parts) > 8 and parts[8]:
                trigger = parts[8]

        if pid:
            parts = pid.split("|")
            # PID-3 patient identifier
            if len(parts) > 3 and parts[3]:
                patient_identifier = parts[3].split("^")[0]
            # PID-5 family^given
            if len(parts) > 5 and parts[5]:
                name_components = parts[5].split("^")
                patient_name = {
                    "family": name_components[0] if name_components else None,
                    "given": name_components[1] if len(name_components) > 1 else None,
                }

        if pv1:
            parts = pv1.split("|")
            if len(parts) > 3 and parts[3]:
                venue_location = parts[3]

        result = {
            "trigger": trigger,
            "patient_identifier": patient_identifier,
            "patient_name": patient_name,
            "venue_location": venue_location,
            "segments": {
                "MSH": bool(msh),
                "EVN": bool(evn),
                "PID": bool(pid),
                "PV1": bool(pv1),
            }
        }

        # Placeholder: log operation; future enrichment: persist changes
        logger.debug(f"[pam] Parsed message trigger={trigger} pid={patient_identifier} location={venue_location}")
        return result
    except Exception as e:
        logger.error(f"[pam] Échec traitement message: {e}")
        raise


def _parse_zbe_segment(message: str) -> Optional[Dict]:
    """
    Parse le segment ZBE (mouvement patient - spécifique IHE PAM France).
    
    ZBE fields (selon IHE PAM France):
    - ZBE-1: Identifiant du mouvement (format: ID^NAMESPACE^OID^ISO ou simple ID)
    - ZBE-2: Date/heure du mouvement (HL7 timestamp: YYYYMMDDHHmmss)
    - ZBE-3: Action (généralement vide)
    - ZBE-4: Type d'action (INSERT / UPDATE / CANCEL)
    - ZBE-5: Indicateur annulation (Y/N)
    - ZBE-6: Événement d'origine (ex: "A01" pour un A11 qui annule un A01)
    - ZBE-7: UF médicale responsable (format: ^^^^^^TYPE^CODE^^^COMP^CP, code en position 10)
    - ZBE-8: UF de soins (format: ^^^^^^TYPE^CODE^^^COMP^CP, code en position 10)
    - ZBE-9: Nature du mouvement (M=Médical, H=Hébergement, S=Soins, L=Localisation, D=Date)
    
    Returns:
        Dict with movement_id, movement_datetime, action_type, cancel_flag, origin_event, uf_medicale, uf_soins, nature
    """
    out = {
        "movement_id": None,
        "movement_datetime": None,
        "action_type": None,
        "cancel_flag": None,
        "origin_event": None,
        "uf_responsable": None,
        "mode_traitement": None,
    }
    
    try:
        lines = re.split(r"\r|\n", message)
        zbe = next((l for l in lines if l.startswith("ZBE")), None)
        if not zbe:
            return None
            
        parts = zbe.split("|")
        
        # ZBE-1: Identifiant du mouvement (format: ID^NAMESPACE^OID^ISO)
        if len(parts) > 1 and parts[1]:
            movement_id_field = parts[1].strip()
            # Extraire juste l'ID (composant 1)
            out["movement_id"] = movement_id_field.split("^")[0] if "^" in movement_id_field else movement_id_field
        
        # ZBE-2: Date/heure du mouvement
        if len(parts) > 2 and parts[2]:
            out["movement_datetime"] = parts[2].strip()
        
        # ZBE-3: Action (généralement vide, on skip)
        
        # ZBE-4: Type d'action (INSERT, UPDATE, CANCEL)
        if len(parts) > 4 and parts[4]:
            out["action_type"] = parts[4].strip()
        
        # ZBE-5: Indicateur annulation (Y/N)
        if len(parts) > 5 and parts[5]:
            out["cancel_flag"] = parts[5].strip()
        
        # ZBE-6: Événement d'origine
        if len(parts) > 6 and parts[6]:
            out["origin_event"] = parts[6].strip()
        
        # ZBE-7: UF médicale responsable (format: ^^^^^^TYPE^CODE^^^COMP^CP)
        # Le code UF est en position 10 (composant 10 du champ composite)
        if len(parts) > 7 and parts[7]:
            uf_field = parts[7].strip()
            uf_components = uf_field.split("^")
            if len(uf_components) >= 10 and uf_components[9]:
                out["uf_medicale"] = uf_components[9]
                # Rétrocompatibilité : garder aussi "uf_responsable"
                out["uf_responsable"] = uf_components[9]
        
        # ZBE-8: UF de soins (format: ^^^^^^TYPE^CODE^^^COMP^CP)
        if len(parts) > 8 and parts[8]:
            uf_soins_field = parts[8].strip()
            uf_soins_components = uf_soins_field.split("^")
            if len(uf_soins_components) >= 10 and uf_soins_components[9]:
                out["uf_soins"] = uf_soins_components[9]
        
        # ZBE-9: Nature du mouvement (M/H/S/L/D)
        if len(parts) > 9 and parts[9]:
            out["nature"] = parts[9].strip()
        
        return out if out["movement_id"] else None
        
    except Exception as e:
        logger.warning(f"Failed to parse ZBE segment: {e}")
        return None


def generate_pam_messages_for_dossier(dossier: Dossier) -> List[str]:
    patient: Patient = dossier.patient
    venues: List[Venue] = sorted(dossier.venues, key=lambda v: v.start_time or "")
    messages: List[str] = []

    for v in venues:
        mouvements: List[Mouvement] = sorted(v.mouvements, key=lambda m: m.when)
        for m in mouvements:
            if build_message_for_movement:
                messages.append(build_message_for_movement(dossier=dossier, venue=v, movement=m, patient=patient))
            else:
                # Choose a stable primary patient identifier (prefer patient.identifier, fallback external_id, then patient_seq)
                primary_id = patient.identifier or patient.external_id or (f"PSEQ{patient.patient_seq}" if patient.patient_seq is not None else f"PID{patient.id}")
                # Emit PID-3 as CX with system tag for source context + type PI
                pid_cx = f"{primary_id}^^^SRC-PAM&1.2.250.1.211.99.1&ISO^PI"
                msh = f"MSH|^~\\&|MedBridge|SYSTEM|DST|DST|{m.when:%Y%m%d%H%M%S}||{m.type}|{dossier.dossier_seq}|P|2.5"
                pid = f"PID|||{pid_cx}||{patient.family}^{patient.given}||{patient.birth_date}|{patient.gender}"
                pv1_loc = m.location or v.code or "UNKNOWN"
                pv1 = f"PV1||I|{pv1_loc}|||^^^^^{v.uf_responsabilite}"
                messages.append("\r".join([msh, pid, pv1]))
    return messages


async def _handle_cancel_admission(
    session: Session,
    trigger: str,
    pid_data: dict,
    pv1_data: dict,
    message: Optional[str]
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
            # Fallback: chercher le dernier mouvement du patient
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
            
            # use global select
            original_mouvement = session.exec(
                select(Mouvement)
                .where(Mouvement.mouvement_seq == int(movement_id_str))
            ).first()
            
            if not original_mouvement:
                logger.warning(f"[pam][cancel] {trigger}: Movement seq={movement_id_str} not found, trying fallback by patient")
                # Fallback: chercher le dernier mouvement du patient
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
            when=datetime.utcnow(),
            status=MOVEMENT_STATUS_BY_TRIGGER.get(trigger, "cancelled"),
            movement_type=MOVEMENT_KIND_BY_TRIGGER.get(trigger, "admission-cancel"),
            trigger_event=trigger,  # Pour validation des transitions IHE PAM
            location=original_mouvement.location,
            from_location=original_mouvement.from_location,
            to_location=original_mouvement.to_location,
        )
        session.add(cancel_mouvement)
        
        # Mettre à jour le statut du mouvement original
        original_mouvement.status = "cancelled"
        session.add(original_mouvement)
        
        # Mettre à jour le statut de la venue
        venue.operational_status = "cancelled"
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
    message: Optional[str]
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
            logger.warning(f"[pam][cancel-discharge] No ZBE segment, fallback to last discharge")
            # Fallback: chercher la dernière sortie
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
            
            # use global select
            original_mouvement = session.exec(
                select(Mouvement)
                .where(Mouvement.mouvement_seq == int(movement_id_str))
            ).first()
            
            if not original_mouvement:
                logger.warning(f"[pam][cancel-discharge]: Movement seq={movement_id_str} not found, trying fallback")
                # Fallback: chercher la dernière sortie
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
        cancel_datetime = datetime.utcnow()
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
        )
        session.add(cancel_mouvement)
        
        # Annuler le mouvement original
        original_mouvement.status = "cancelled"
        session.add(original_mouvement)
        
        # Réactiver la venue
        venue.operational_status = "active"
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
    message: Optional[str]
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
            logger.warning(f"[pam][cancel-transfer] No ZBE segment, fallback to last transfer")
            # Fallback: chercher le dernier transfert
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
            
            # use global select
            original_mouvement = session.exec(
                select(Mouvement)
                .where(Mouvement.mouvement_seq == int(movement_id_str))
            ).first()
            
            if not original_mouvement:
                logger.warning(f"[pam][cancel-transfer]: Movement seq={movement_id_str} not found, trying fallback")
                # Fallback: chercher le dernier transfert
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
        cancel_datetime = datetime.utcnow()
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


async def handle_admission_message(
    session: Session, 
    trigger: str, 
    pid_data: dict, 
    pv1_data: dict, 
    message: Optional[str] = None,
    ej_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """Traitement des messages d'admission et d'annulation.

    - Pour les admissions normales (A01, A04, A05, A06, A07): crée Patient/Dossier/Venue/Mouvement
    - Pour les messages d'identité (A28, A31): mise à jour patient SANS mouvement
    - Pour les annulations (A11, A23, A38): parse ZBE-1 pour trouver le mouvement à annuler
    
    Args:
        session: Session DB
        trigger: Code trigger (A01, A04, A11, A28, A31, etc.)
        pid_data: Données PID parsées
        pv1_data: Données PV1 parsées
        message: Message HL7 complet (requis pour parser ZBE segment sur messages de mouvements)
    
    Returns:
        Tuple[bool, Optional[str]]: (succès, message d'erreur)
    """
    try:
        # Parser le segment ZBE (présent uniquement dans les messages de MOUVEMENTS)
        # Les messages d'identité (A28, A31, A40, A47) n'ont PAS de segment ZBE
        zbe_data = None
        if message and trigger not in ["A28", "A31", "A40", "A47"]:
            zbe_data = _parse_zbe_segment(message)
            if zbe_data:
                logger.info(f"[pam][admission] ZBE parsed: {zbe_data}")
        
        # Extraire les identifiants supplémentaires pour classification EJ
        account_number = pid_data.get("account_number")
        visit_number = pv1_data.get("visit_number") 
        movement_id = zbe_data.get("movement_id") if zbe_data else None
        
        logger.info(f"[pam][admission] Variables: account_number={account_number}, visit_number={visit_number}, movement_id={movement_id}, trigger={trigger}")
        logger.debug(f"[pam][admission] PID data keys: {list(pid_data.keys())}")
        if trigger in ["A11", "A23", "A38"]:
            return await _handle_cancel_admission(session, trigger, pid_data, pv1_data, message)
        
        # Gestion normale des admissions
        # Identifier patient (prendre le premier identifiant PID-3)
        logger.info("[pam][admission] Entering patient identification block")

        # --- PATCH: Robust PID-3 parsing and identifier assignment ---
        # Build robust identifier list from PID-3
        identifiers_raw = pid_data.get("identifiers", [])
        identifiers = []
        for cx_value, *_ in identifiers_raw:
            value, system, type_code = parse_hl7_cx_identifier(cx_value)
            identifiers.append((cx_value, system, type_code))

        # Main patient identifier (fallback logic)
        identifier = None
        if identifiers:
            # Prefer classified main identifier, fallback to first PID-3 value
            try:
                from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check
                identifiers_list, main_id_value, external_id_value = create_identifiers_from_hl7_with_namespace_check(
                    identifiers, "patient", session, ej_id
                )
                identifier = main_id_value or (identifiers[0][0].split("^")[0] if identifiers else None)
            except Exception as e:
                logger.warning(f"[pam] Failed to classify identifiers: {e}")
                identifier = identifiers[0][0].split("^")[0] if identifiers else None
        logger.debug(f"[pam][admission] Resolved identifier={identifier} (identifiers_count={len(identifiers)})")

        # Nom / prénom
        family = pid_data.get("family") or ""
        given = pid_data.get("given") or ""

        # Create or update patient
        reused_patient = None
        if identifier:
            # use global select
            from app.services.patient_update_helper import update_patient_from_pid_data
            existing = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
            if existing:
                update_patient_from_pid_data(existing, pid_data, session, create_mode=False)
                session.add(existing)
                session.flush()
                # Persist all PID-3 identifiers with namespace classification
                try:
                    from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check
                    identifiers_list, main_id_value, external_id_value = create_identifiers_from_hl7_with_namespace_check(
                        identifiers, "patient", session, ej_id
                    )
                    for ident in identifiers_list:
                        ident.patient_id = existing.id
                        exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                        if not exists_dup:
                            session.add(ident)
                except Exception as e:
                    logger.warning(f"[pam] Failed to create identifiers with namespace check: {e}")
                    # Fallback to legacy method
                    for raw_cx, _, _ in identifiers:
                        try:
                            ident = create_identifier_from_hl7(raw_cx, "patient", existing.id)
                            exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                            if not exists_dup:
                                session.add(ident)
                        except Exception:
                            continue
                reused_patient = existing
                if trigger in ("A28", "A31"):
                    # Identity-only update: no new dossier/venue/mouvement. Return early.
                    logger.info(f"[pam][admission] Identity-only update detected for existing patient, trigger={trigger}")
                    return True, None

        # Debug: inspect identifier resolution and reuse
        logger.debug(f"[pam][admission] identifiers={identifiers!r}")
        logger.debug(f"[pam][admission] identifier={identifier!r}, reused_patient={reused_patient!r}")

        # If patient already updated and trigger is identity, return early
        if reused_patient:
            patient = reused_patient
            logger.debug(f"[pam][admission] Using reused_patient id={getattr(patient,'id', None)}")
        else:
            from app.services.patient_update_helper import create_patient_from_pid_data
            patient = create_patient_from_pid_data(pid_data, session, identifier, identifier, ej_id)
            session.add(patient)
            session.flush()
            logger.debug(f"[pam][admission] Created patient id={getattr(patient,'id', None)}")

            # Persist all identifiers from PID-3 with namespace classification
            try:
                from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check
                identifiers_list, main_id_value, external_id_value = create_identifiers_from_hl7_with_namespace_check(
                    identifiers, "patient", session, ej_id
                )
                for ident in identifiers_list:
                    ident.patient_id = patient.id
                    exists = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                    if not exists:
                        session.add(ident)
            except Exception as e:
                logger.warning(f"[pam] Failed to create identifiers with namespace check: {e}")
                # Fallback to legacy method
                for raw_cx, _, _ in identifiers:
                    try:
                        ident = create_identifier_from_hl7(raw_cx, "patient", patient.id)
                        exists = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                        if not exists:
                            session.add(ident)
                    except Exception:
                        continue

            # For identity-only messages, do not create dossier/venue/mouvement
            if trigger in ("A28", "A31"):
                logger.debug(f"[pam][admission] Early return for identity-only trigger after create/update, trigger={trigger}, patient_id={getattr(patient,'id', None)}")
                return True, None
            
        # Créer un dossier et une venue
        # Utiliser l'identifiant dossier fourni dans PID-18 si disponible, sinon générer une séquence
        d_seq = None
        if account_number:
            try:
                # Extraire le numéro de dossier du format HL7 CX (peut contenir namespace)
                cx_parts = account_number.split("^")
                d_seq = int(cx_parts[0])
                logger.info(f"[pam][admission] Using provided dossier sequence: {d_seq} from PID-18")
            except (ValueError, IndexError) as e:
                logger.warning(f"[pam][admission] Invalid dossier sequence in PID-18 '{account_number}': {e}")
        
        if d_seq is None:
            d_seq = get_next_sequence(session, "dossier")
            logger.info(f"[pam][admission] Generated new dossier sequence: {d_seq}")
        # Use parsed datetime if available (pid parser provides birth_date_dt),
        # otherwise attempt to parse HL7 YYYYMMDD string, or fallback to now.
        admit_time = pv1_data.get("admit_time")
        if not admit_time and pid_data.get("birth_date_dt"):
            admit_time = pid_data.get("birth_date_dt")
        elif not admit_time and pid_data.get("birth_date"):
            try:
                admit_time = datetime.strptime(pid_data.get("birth_date"), "%Y%m%d")
            except Exception:
                admit_time = None
        if not admit_time:
            admit_time = datetime.utcnow()

        # Map PV1-2 patient_class (HL7v2) -> internal encounter-class (FHIR ActCode) via vocabulary mapping
        hl7_patient_class = pv1_data.get("patient_class") or "I"
        encounter_class_code = map_code(session, "patient-class", hl7_patient_class, "encounter-class") or (
            {"I": "IMP", "O": "AMB", "E": "EMER"}.get(hl7_patient_class, "IMP")
        )
        # Vérifier si le dossier_seq existe déjà
        existing_dossier = session.exec(select(Dossier).where(Dossier.dossier_seq == d_seq)).first()
        if existing_dossier:
            logger.error(f"[pam][admission] Doublon dossier_seq détecté: {d_seq}. Import annulé.")
            raise Exception(f"Un dossier avec le numéro {d_seq} existe déjà. Import ADT/PAM annulé.")
        dossier = Dossier(
            dossier_seq=d_seq,
            patient_id=patient.id,
            uf_responsabilite=pv1_data.get("hospital_service") or "UNKNOWN",
            admit_time=admit_time,
            encounter_class=encounter_class_code,
        )
        session.add(dossier)
        session.flush()
        print(f"[pam] Created dossier id={dossier.id} dossier_seq={dossier.dossier_seq} patient_id={dossier.patient_id}")

        # If PID-18 (account number) was provided, persist it as a Dossier identifier
        try:
            acc_raw = pid_data.get("account_number")
            if acc_raw:
                # use global Identifier from module-level import
                try:
                    ident = create_identifier_from_hl7(acc_raw, "dossier", dossier.id)
                    # Ensure PID-18 is recorded as AN (Account Number) when no explicit type present
                    try:
                        # use module-level IdentifierType
                        if ident.type == IdentifierType.PI:
                            ident.type = IdentifierType.AN
                    except Exception:
                        pass
                    exists = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                    if not exists:
                        session.add(ident)
                        session.flush()
                except Exception:
                    # tolerate bad format
                    pass
        except Exception:
            pass

        v_seq = get_next_sequence(session, "venue")
        
        # Utiliser l'identifiant venue fourni dans PV1-19 si disponible
        if visit_number:
            try:
                # Extraire le numéro de venue du format HL7 CX (peut contenir namespace)
                cx_parts = visit_number.split("^")
                v_seq = int(cx_parts[0])
                logger.info(f"[pam][admission] Using provided venue sequence: {v_seq} from PV1-19")
            except (ValueError, IndexError) as e:
                logger.warning(f"[pam][admission] Invalid venue sequence in PV1-19 '{visit_number}': {e}")
                v_seq = get_next_sequence(session, "venue")
        location_raw = (pv1_data.get("location") or "").strip()
        location_value = location_raw or None
        previous_location = (pv1_data.get("previous_location") or "").strip() or None
        hospital_service = (pv1_data.get("hospital_service") or "").strip() or None
        movement_code = f"ADT^{trigger}"
        movement_kind = MOVEMENT_KIND_BY_TRIGGER.get(trigger, "admission")
        movement_status = MOVEMENT_STATUS_BY_TRIGGER.get(trigger, "completed")

        operational_status = "active"
        if movement_status == "planned":
            operational_status = "planned"
        elif movement_status == "cancelled":
            operational_status = "cancelled"

        venue = Venue(
            venue_seq=v_seq,
            dossier_id=dossier.id,
            uf_responsabilite=dossier.uf_responsabilite,
            start_time=datetime.utcnow(),
            operational_status=operational_status,
            assigned_location=location_value,
            hospital_service=hospital_service or pv1_data.get("hospital_service") or dossier.uf_responsabilite,
        )
        session.add(venue)
        session.flush()
        print(f"[pam] Created venue id={venue.id} venue_seq={venue.venue_seq} dossier_id={venue.dossier_id}")

        # If PV1-19 (visit number) was provided, persist it as a Venue identifier
        try:
            visit_raw = pv1_data.get("visit_number")
            if visit_raw:
                # use global Identifier from module-level import
                try:
                    ident = create_identifier_from_hl7(visit_raw, "venue", venue.id)
                    # Ensure PV1-19 is recorded as VN (Visit Number) when no explicit type present
                    try:
                        # use module-level IdentifierType
                        if ident.type == IdentifierType.PI:
                            ident.type = IdentifierType.VN
                    except Exception:
                        pass
                    exists = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                    if not exists:
                        session.add(ident)
                        session.flush()
                except Exception:
                    # tolerate bad format
                    pass
        except Exception:
            pass

        # Déterminer la date du mouvement : priorité ZBE-2, puis PV1, puis now
        movement_datetime = datetime.utcnow()
        if zbe_data and zbe_data.get("movement_datetime"):
            try:
                # Parse HL7 timestamp: YYYYMMDDHHmmss
                dt_str = zbe_data["movement_datetime"]
                movement_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"[pam][admission] Failed to parse ZBE-2 datetime '{dt_str}': {e}")
        elif pv1_data.get("admit_time"):
            movement_datetime = pv1_data["admit_time"]
        
        # Déterminer les UF selon ZBE et PV1
        # - UF hébergement : PV1-3-1 (location)
        # - UF médicale : ZBE-7-10
        
        # - UF soins : ZBE-8-10
        uf_resp = dossier.uf_responsabilite
        uf_code_from_zbe = None
        
        # UF médicale depuis ZBE-7
        if zbe_data and zbe_data.get("uf_medicale"):
            uf_code_from_zbe = zbe_data["uf_medicale"]
            uf_resp = uf_code_from_zbe
            
            # Vérifier que l'UF existe dans la structure associée à l'EJ
            # Récupérer l'EJ depuis le patient (via un identifiant de type système)
            try:
                # use global select
                from app.models_structure import UniteFonctionnelle
                from app.models_structure import EntiteJuridique
                
                # Chercher l'UF dans la structure
                uf_found = session.exec(
                    select(UniteFonctionnelle)
                    .where(UniteFonctionnelle.identifier == uf_code_from_zbe)
                ).first()
                
                if not uf_found:
                    # Option d'auto-création contrôlée par variable d'environnement
                    import os
                    if os.getenv("PAM_AUTO_CREATE_UF", "0") in ("1", "true", "True"):
                        try:
                            from app.models_structure import (
                                UniteFonctionnelle, Service, Pole, LocationPhysicalType
                            )
                            from app.models_structure import EntiteGeographique
                            # use global select

                            # Récupérer/Créer une entité géographique (placeholder si absente)
                            eg = session.exec(select(EntiteGeographique)).first()
                            if not eg:
                                eg = EntiteGeographique(
                                    identifier="AUTO_EG", name="Entité Géographique Auto",
                                    finess="000000000"
                                )
                                session.add(eg)
                                session.flush()

                            # Récupérer/Créer un pôle virtuel
                            from app.models_structure import Pole as _PoleModel
                            pole = session.exec(select(_PoleModel).where(_PoleModel.identifier == "AUTO_POLE")).first()
                            if not pole:
                                pole = _PoleModel(
                                    identifier="AUTO_POLE",
                                    name="Pôle Auto",
                                    physical_type=LocationPhysicalType.SI,
                                    entite_geo_id=eg.id,
                                    is_virtual=True,
                                )
                                session.add(pole)
                                session.flush()

                            # Récupérer/Créer un service virtuel
                            from app.models_structure import Service as _ServiceModel, LocationServiceType
                            service = session.exec(select(_ServiceModel).where(_ServiceModel.identifier == "AUTO_SERVICE")).first()
                            if not service:
                                service = _ServiceModel(
                                    identifier="AUTO_SERVICE",
                                    name="Service Auto",
                                    physical_type=LocationPhysicalType.SI,
                                    service_type=LocationServiceType.MCO,
                                    pole_id=pole.id,
                                    is_virtual=True,
                                )
                                session.add(service)
                                session.flush()

                            # Créer l'UF minimale
                            uf_found = UniteFonctionnelle(
                                identifier=uf_code_from_zbe,
                                name=f"UF {uf_code_from_zbe}",
                                physical_type=LocationPhysicalType.SI,
                                service_id=service.id,
                                is_virtual=True,
                            )
                            session.add(uf_found)
                            session.flush()
                            logger.warning(
                                f"[pam][admission] UF '{uf_code_from_zbe}' auto-créée (placeholder) sous service 'AUTO_SERVICE'"
                            )
                        except Exception as _auto_e:
                            error_msg = (
                                f"UF Responsable '{uf_code_from_zbe}' (ZBE-7) introuvable et échec auto-création: {_auto_e}"
                            )
                            logger.error(f"[pam][admission] {error_msg}", exc_info=True)
                            return False, error_msg
                    else:
                        error_msg = (
                            f"UF Responsable '{uf_code_from_zbe}' (ZBE-7) introuvable dans la structure. "
                            f"Activer PAM_AUTO_CREATE_UF=1 pour auto-création placeholder ou importer via MFN^M05 avant."
                        )
                        logger.error(f"[pam][admission] {error_msg}")
                        return False, error_msg
                
                logger.info(f"[pam][admission] UF Responsable '{uf_code_from_zbe}' validée: {uf_found.name}")
                
            except Exception as e:
                logger.error(f"[pam][admission] Erreur validation UF: {e}", exc_info=True)
                return False, f"Erreur validation UF Responsable: {str(e)}"
        
        # Mettre à jour l'UF responsabilité du dossier et de la venue
        dossier.uf_responsabilite = uf_resp
        venue.uf_responsabilite = uf_resp
        session.add(dossier)
        session.add(venue)
        
        m_seq = get_next_sequence(session, "mouvement")
        
        # Utiliser l'identifiant mouvement fourni dans ZBE-1 si disponible
        if movement_id:
            try:
                # Extraire le numéro de mouvement du format HL7 CX (peut contenir namespace)
                cx_parts = movement_id.split("^")
                m_seq = int(cx_parts[0])
                logger.info(f"[pam][admission] Using provided mouvement sequence: {m_seq} from ZBE-1")
            except (ValueError, IndexError) as e:
                logger.warning(f"[pam][admission] Invalid mouvement sequence in ZBE-1 '{movement_id}': {e}")
                m_seq = get_next_sequence(session, "mouvement")
        
        # Valider l'écart temporel avec le dernier mouvement
        try:
            validate_movement_timing(session, venue.id, movement_datetime)
        except ValueError as e:
            return False, str(e)
        
        # Inject UF codes from ZBE if available (ZBE-7 / ZBE-8)
        uf_medicale_code = zbe_data.get("uf_medicale") if zbe_data else None
        uf_soins_code = zbe_data.get("uf_soins") if zbe_data else None
        mouvement = Mouvement(
            mouvement_seq=m_seq,
            venue_id=venue.id,
            type=movement_code,
            when=movement_datetime,
            status=movement_status,
            movement_type=movement_kind,
            trigger_event=trigger,  # Pour validation des transitions IHE PAM
            from_location=previous_location,
            to_location=location_value,
            location=location_value,  # PV1-3: Localisation actuelle
            uf_medicale_code=uf_medicale_code,
            uf_medicale_label=uf_medicale_code,
            uf_soins_code=uf_soins_code,
            uf_soins_label=uf_soins_code,
        )
        session.add(mouvement)
        session.flush()
        logger.info(
            f"[pam] Created mouvement mouv_seq={mouvement.mouvement_seq} venue_id={mouvement.venue_id} "
            f"movement_type={mouvement.movement_type} when={mouvement.when} "
            f"location={mouvement.location} uf_responsable={uf_resp}"
        )

        # Traiter les identifiants supplémentaires avec classification EJ
        # Dossier identifiers (PID-18)
        if account_number:
            dossier_identifiers = parse_hl7_cx_identifier(account_number)
            if dossier_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [dossier_identifiers], dossier, "dossier"
                )

        # Venue identifiers (PV1-19)
        if visit_number:
            venue_identifiers = parse_hl7_cx_identifier(visit_number)
            if venue_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [venue_identifiers], venue, "venue"
                )

        # Mouvement identifiers (ZBE-1)
        if movement_id:
            mouvement_identifiers = parse_hl7_cx_identifier(movement_id)
            if mouvement_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [mouvement_identifiers], mouvement, "mouvement"
                )

        # Note: Message emission is now automatic via entity_events.py listeners

        return True, None
    except Exception as e:
        return False, str(e)


async def handle_transfer_message(
    session: Session, 
    trigger: str, 
    pid_data: dict, 
    pv1_data: dict, 
    message: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Gère les messages de transfert et d'annulation de transfert.
    
    - A02: Transfert
    - A12: Annulation de transfert (parse ZBE-1 pour l'ID du mouvement)
    """
    try:
        # Parser le segment ZBE (présent dans TOUS les messages IHE PAM)
        zbe_data = _parse_zbe_segment(message) if message else None
        if zbe_data:
            logger.info(f"[pam][transfer] ZBE parsed: {zbe_data}")
        
        # Extraire les identifiants supplémentaires pour classification EJ
        account_number = pid_data.get("account_number")
        visit_number = pv1_data.get("visit_number") 
        movement_id = zbe_data.get("movement_id") if zbe_data else None
        if trigger == "A12":
            return await _handle_cancel_transfer(session, trigger, pid_data, pv1_data, message)
        
        # Gestion normale du transfert (A02)
        identifiers = pid_data.get("identifiers", [])
        if not identifiers:
            return False, "No patient identifier found"
        identifier = identifiers[0][0].split("^")[0]

        # use global select

        patient = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
        if not patient:
            return False, "Patient not found"

        # Find last venue for this patient (by dossier/venue_seq)
        dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
        if not dossier:
            return False, "Dossier not found"

        venue = session.exec(select(Venue).where(Venue.dossier_id == dossier.id).order_by(Venue.venue_seq.desc())).first()
        if not venue:
            return False, "Venue not found"

        previous_location_msg = (pv1_data.get("previous_location") or "").strip()
        previous_location = previous_location_msg or venue.assigned_location
        new_location_raw = (pv1_data.get("location") or "").strip()
        new_location = new_location_raw or previous_location or venue.assigned_location
        hospital_service = (pv1_data.get("hospital_service") or "").strip() or None

        # Déterminer la date du mouvement : priorité ZBE-2, puis now
        movement_datetime = datetime.utcnow()
        if zbe_data and zbe_data.get("movement_datetime"):
            try:
                dt_str = zbe_data["movement_datetime"]
                movement_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"[pam][transfer] Failed to parse ZBE-2 datetime '{dt_str}': {e}")
        
        print(f"[pam][transfer] patient_id={patient.id} venue_id={venue.id} creating mouvement")
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
            status=MOVEMENT_STATUS_BY_TRIGGER.get(trigger, "completed"),
            movement_type=MOVEMENT_KIND_BY_TRIGGER.get(trigger, "transfer"),
            trigger_event=trigger,  # Pour validation des transitions IHE PAM
            from_location=previous_location,
            to_location=new_location,
            location=new_location,
        )
        session.add(mouvement)

        venue.assigned_location = new_location
        if hospital_service:
            venue.hospital_service = hospital_service
            dossier.uf_responsabilite = hospital_service
            session.add(dossier)
        session.add(venue)

        session.flush()
        print(f"[pam][transfer] Created mouvement id={mouvement.id} seq={mouvement.mouvement_seq} from={previous_location} to={new_location}")
        
        # Traiter les identifiants supplémentaires avec classification EJ
        # Dossier identifiers (PID-18)
        if account_number:
            dossier_identifiers = parse_hl7_cx_identifier(account_number)
            if dossier_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [dossier_identifiers], dossier, "dossier"
                )

        # Venue identifiers (PV1-19)
        if visit_number:
            venue_identifiers = parse_hl7_cx_identifier(visit_number)
            if venue_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [venue_identifiers], venue, "venue"
                )

        # Mouvement identifiers (ZBE-1)
        if movement_id:
            mouvement_identifiers = parse_hl7_cx_identifier(movement_id)
            if mouvement_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [mouvement_identifiers], mouvement, "mouvement"
                )
        
        # Note: Message emission is now automatic via entity_events.py listeners
        
        return True, None
    except Exception as e:
        return False, str(e)


async def handle_discharge_message(
    session: Session, 
    trigger: str, 
    pid_data: dict, 
    pv1_data: dict, 
    message: Optional[str] = None,
    ej_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Gère les messages de sortie et d'annulation de sortie.
    
    - A03: Sortie
    - A13: Annulation de sortie (parse ZBE-1 pour l'ID du mouvement)
    """
    try:
        # Parser le segment ZBE (présent dans TOUS les messages IHE PAM)
        zbe_data = _parse_zbe_segment(message) if message else None
        if zbe_data:
            logger.info(f"[pam][discharge] ZBE parsed: {zbe_data}")
        
        # Extraire les identifiants supplémentaires pour classification EJ
        account_number = pid_data.get("account_number")
        visit_number = pv1_data.get("visit_number") 
        movement_id = zbe_data.get("movement_id") if zbe_data else None
        
        # Gestion de l'annulation de sortie (A13)
        if trigger == "A13":
            return await _handle_cancel_discharge(session, trigger, pid_data, pv1_data, message)
        
        # Gestion normale de la sortie (A03)
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

        venue = session.exec(select(Venue).where(Venue.dossier_id == dossier.id).order_by(Venue.venue_seq.desc())).first()
        if not venue:
            return False, "Venue not found"

        previous_location = venue.assigned_location
        discharge_time = pv1_data.get("discharge_time") or datetime.utcnow()
        hospital_service = (pv1_data.get("hospital_service") or "").strip() or None

        # Déterminer la date du mouvement : priorité ZBE-2, puis discharge_time, puis now
        movement_datetime = datetime.utcnow()
        if zbe_data and zbe_data.get("movement_datetime"):
            try:
                dt_str = zbe_data["movement_datetime"]
                movement_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"[pam][discharge] Failed to parse ZBE-2 datetime '{dt_str}': {e}")
        elif discharge_time:
            movement_datetime = discharge_time
        
        # Create a sortie mouvement and mark venue completed
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
            location=previous_location,
            status=MOVEMENT_STATUS_BY_TRIGGER.get(trigger, "completed"),
            movement_type=MOVEMENT_KIND_BY_TRIGGER.get(trigger, "discharge"),
            trigger_event=trigger,  # Pour validation des transitions IHE PAM
            from_location=previous_location,
            to_location=None,
        )
        session.add(mouvement)
        venue.operational_status = "completed"
        venue.assigned_location = None
        if hospital_service:
            venue.hospital_service = hospital_service
            dossier.uf_responsabilite = hospital_service
        dossier.discharge_time = discharge_time
        session.add(venue)
        session.add(dossier)
        session.flush()
        print(f"[pam][discharge] Created sortie mouvement seq={mouvement.mouvement_seq} and set venue {venue.id} status=completed")
        
        # Traiter les identifiants supplémentaires avec classification EJ
        # Dossier identifiers (PID-18)
        if account_number:
            dossier_identifiers = parse_hl7_cx_identifier(account_number)
            if dossier_identifiers:
                create_identifiers_from_hl7_with_namespace_check(
                    [dossier_identifiers], "dossier", session, ej_id
                )

        # Venue identifiers (PV1-19)
        if visit_number:
            venue_identifiers = parse_hl7_cx_identifier(visit_number)
            if venue_identifiers:
                create_identifiers_from_hl7_with_namespace_check(
                    [venue_identifiers], "venue", session, ej_id
                )

        # Mouvement identifiers (ZBE-1)
        if movement_id:
            mouvement_identifiers = parse_hl7_cx_identifier(movement_id)
            if mouvement_identifiers:
                create_identifiers_from_hl7_with_namespace_check(
                    [mouvement_identifiers], "mouvement", session, ej_id
                )
        
        # Note: Message emission is now automatic via entity_events.py listeners
        
        return True, None
    except Exception as e:
        return False, str(e)


async def handle_leave_message(
    session: Session, 
    trigger: str, 
    pid_data: dict, 
    pv1_data: dict,
    message: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Gère les messages de permission (A21/A52 = sortie temporaire, A22/A53 = retour).
    IHE PAM: Leave of Absence
    
    A21/A52: Patient part en permission temporaire
    A22/A53: Patient revient de permission
    """
    try:
        # Parser le segment ZBE (présent dans TOUS les messages IHE PAM)
        zbe_data = _parse_zbe_segment(message) if message else None
        if zbe_data:
            logger.info(f"[pam][leave] ZBE parsed: {zbe_data}")
        
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

        # Get location info
        location = (pv1_data.get("location") or "").strip() or venue.assigned_location
        hospital_service = (pv1_data.get("hospital_service") or "").strip() or venue.hospital_service
        
        # Déterminer la date du mouvement : priorité ZBE-2, puis now
        movement_datetime = datetime.utcnow()
        if zbe_data and zbe_data.get("movement_datetime"):
            try:
                dt_str = zbe_data["movement_datetime"]
                movement_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"[pam][leave] Failed to parse ZBE-2 datetime '{dt_str}': {e}")
        
        # Create mouvement for leave of absence
        m_seq = get_next_sequence(session, "mouvement")
        
        # Valider l'écart temporel avec le dernier mouvement
        try:
            validate_movement_timing(session, venue.id, movement_datetime)
        except ValueError as e:
            return False, str(e)
        
        movement_type = "leave-out" if trigger in ["A21", "A52"] else "leave-return"
        status = "leave" if trigger in ["A21", "A52"] else "completed"
        
        mouvement = Mouvement(
            mouvement_seq=m_seq,
            venue_id=venue.id,
            type=f"ADT^{trigger}",
            when=movement_datetime,
            status=status,
            movement_type=movement_type,
            trigger_event=trigger,  # Pour validation des transitions IHE PAM
            location=location,
        )
        session.add(mouvement)
        
        # Update venue status if leaving
        if trigger in ["A21", "A52"]:
            venue.status = "leave"
        elif trigger in ["A22", "A53"]:
            venue.status = "active"
        
        if hospital_service:
            venue.hospital_service = hospital_service
        
        session.add(venue)
        session.flush()
        
        logger.info(f"[pam][leave] Created mouvement id={mouvement.id} seq={mouvement.mouvement_seq} type={movement_type}")
        
        # Traiter les identifiants supplémentaires avec classification EJ
        # Dossier identifiers (PID-18)
        if account_number:
            dossier_identifiers = parse_hl7_cx_identifier(account_number)
            if dossier_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [dossier_identifiers], dossier, "dossier"
                )

        # Venue identifiers (PV1-19)
        if visit_number:
            venue_identifiers = parse_hl7_cx_identifier(visit_number)
            if venue_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [venue_identifiers], venue, "venue"
                )

        # Mouvement identifiers (ZBE-1)
        if movement_id:
            mouvement_identifiers = parse_hl7_cx_identifier(movement_id)
            if mouvement_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [mouvement_identifiers], mouvement, "mouvement"
                )
        
        # Note: Message emission is now automatic via entity_events.py listeners
        
        return True, None
    except Exception as e:
        logger.error(f"[pam][leave] Error: {e}", exc_info=True)
        return False, str(e)


async def handle_doctor_message(
    session: Session, 
    trigger: str, 
    pid_data: dict, 
    pv1_data: dict,
    message: Optional[str] = None
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
        movement_datetime = datetime.utcnow()
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
            )
            session.add(mouvement)
        
        session.add(venue)
        session.add(dossier)
        session.flush()
        
        logger.info(f"[pam][doctor] Processed {trigger} for venue_id={venue.id}")
        
        # Traiter les identifiants supplémentaires avec classification EJ
        # Dossier identifiers (PID-18)
        if account_number:
            dossier_identifiers = parse_hl7_cx_identifier(account_number)
            if dossier_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [dossier_identifiers], dossier, "dossier"
                )

        # Venue identifiers (PV1-19)
        if visit_number:
            venue_identifiers = parse_hl7_cx_identifier(visit_number)
            if venue_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [venue_identifiers], venue, "venue"
                )

        # Mouvement identifiers (ZBE-1)
        if movement_id:
            mouvement_identifiers = parse_hl7_cx_identifier(movement_id)
            if mouvement_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, [mouvement_identifiers], mouvement, "mouvement"
                )
        
        # Note: Message emission is now automatic via entity_events.py listeners
        
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
            movement_id = zbe_data.get("movement_id")
            if not movement_id:
                return False, "ZBE-1 (movement_id) requis pour annulation A12"
            
            # Trouver et annuler le mouvement
            mouvement = session.exec(select(Mouvement).where(Mouvement.mouvement_seq == int(movement_id))).first()
            if not mouvement:
                return False, f"Mouvement {movement_id} introuvable pour annulation"
            
            mouvement.status = "cancelled"
            session.add(mouvement)
            session.flush()
            logger.info(f"[pam][transfer] Cancelled movement {movement_id}")
            return True, None
        
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
        movement_datetime = datetime.utcnow()
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
            is_historic=bool(zbe_data.get("is_historic")),
            original_trigger=zbe_data.get("original_trigger")
        )
        
        session.add(mouvement)
        session.flush()
        logger.info(f"[pam][transfer] Created transfer movement id={mouvement.id} mouvement_seq={mouvement.mouvement_seq} on venue {venue.venue_seq}")
        
        # Créer les identifiants pour le mouvement (ZBE-1)
        movement_id = zbe_data.get("movement_id")
        if movement_id:
            mouvement_identifiers = parse_hl7_cx_identifier(movement_id)
            if mouvement_identifiers:
                # Créer l'identifiant directement depuis la valeur CX
                identifier = create_identifier_from_hl7(movement_id, "mouvement", mouvement.id)
                session.add(identifier)
        
        return True, None
        
    except Exception as e:
        logger.error(f"[pam][transfer] Error: {e}", exc_info=True)
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
            movement_id = zbe_data.get("movement_id")
            if not movement_id:
                return False, "ZBE-1 (movement_id) requis pour annulation A13"
            
            # Trouver et annuler le mouvement
            mouvement = session.exec(select(Mouvement).where(Mouvement.mouvement_seq == int(movement_id))).first()
            if not mouvement:
                return False, f"Mouvement {movement_id} introuvable pour annulation"
            
            mouvement.status = "cancelled"
            session.add(mouvement)
            session.flush()
            logger.info(f"[pam][discharge] Cancelled movement {movement_id}")
            return True, None
        
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
        
        # Créer le mouvement de sortie
        m_seq = get_next_sequence(session, "mouvement")
        
        # Déterminer la date du mouvement
        movement_datetime = datetime.utcnow()
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
            is_historic=bool(zbe_data.get("is_historic")),
            original_trigger=zbe_data.get("original_trigger")
        )
        
        session.add(mouvement)
        session.flush()
        logger.info(f"[pam][discharge] Created discharge movement id={mouvement.id} mouvement_seq={mouvement.mouvement_seq} on venue {venue.venue_seq}")
        
        # Créer les identifiants pour le mouvement (ZBE-1)
        movement_id = zbe_data.get("movement_id")
        if movement_id:
            mouvement_identifiers = parse_hl7_cx_identifier(movement_id)
            if mouvement_identifiers:
                create_identifiers_from_hl7_with_namespace_check(
                    [mouvement_identifiers], "mouvement", session, ej_id
                )
        
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
            mouvement = session.exec(select(Mouvement).where(Mouvement.mouvement_seq == int(movement_id))).first()
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
        movement_datetime = datetime.utcnow()
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
            is_historic=bool(zbe_data.get("is_historic")),
            original_trigger=zbe_data.get("original_trigger")
        )
        
        session.add(mouvement)
        session.flush()
        logger.info(f"[pam][leave] Created leave movement id={mouvement.id} mouvement_seq={mouvement.mouvement_seq} on venue {venue.venue_seq}")
        
        # Créer les identifiants pour le mouvement (ZBE-1)
        movement_id = zbe_data.get("movement_id")
        if movement_id:
            mouvement_identifiers = parse_hl7_cx_identifier(movement_id)
            if mouvement_identifiers:
                await create_identifiers_from_hl7_with_namespace_check(
                    session, mouvement_identifiers, mouvement, "mouvement"
                )
        
        return True, None
        
    except Exception as e:
        logger.error(f"[pam][leave] Error: {e}", exc_info=True)
        return False, str(e)
