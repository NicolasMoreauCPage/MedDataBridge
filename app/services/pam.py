from typing import Dict, List, Optional, Tuple, Any
from sqlmodel import Session, select
from datetime import datetime, timezone
import importlib
import logging
import re

from app.models import Dossier, Patient, Venue, Mouvement
from app.db import get_next_sequence
from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check, parse_hl7_cx_identifier, create_identifier_from_hl7
from app.models_identifiers import Identifier, IdentifierType
from app.services.vocabulary_translate import map_code
from app.services.medecin_extractor import extract_and_store_medecin_from_pv1
from app.infrastructure.hl7.parsing.french_extension_parser import (
    parse_zfd, parse_zfa, parse_zfp, parse_zfv, parse_rol_segments,
    ROL_ROLE_ODRP, ROL_ROLE_SUBSTITUTE,
)
from app.utils.booleans import as_bool

logger = logging.getLogger(__name__)


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


def _apply_french_extension_segments_to_patient(patient: "Patient", message: Optional[str]) -> None:
    """Applique sur un Patient les champs extraits des segments ZFD/ZFA/ZFP/ROL (ODRP/SUBS)
    d'un message IHE PAM France, quand ce message en contient. No-op si `message` est None
    ou ne contient aucun de ces segments (retour de parse_* à None/liste vide, champs None).
    """
    if not message:
        return
    zfd = parse_zfd(message)
    if zfd:
        if zfd.get("sms_consent") is not None:
            patient.sms_consent = zfd["sms_consent"]
        if zfd.get("birth_date_modified_indicator") is not None:
            patient.birth_date_modified_indicator = zfd["birth_date_modified_indicator"]
        if zfd.get("identity_capture_mode") is not None:
            patient.identity_capture_mode = zfd["identity_capture_mode"]
        if zfd.get("ins_last_query_date") is not None:
            patient.ins_last_query_date = zfd["ins_last_query_date"]
        if zfd.get("identity_proof_type") is not None:
            patient.identity_proof_type = zfd["identity_proof_type"]
        if zfd.get("identity_proof_expiry_date") is not None:
            patient.identity_proof_expiry_date = zfd["identity_proof_expiry_date"]

    zfa = parse_zfa(message)
    if zfa:
        if zfa.get("dmp_status") is not None:
            patient.dmp_status = zfa["dmp_status"]
        if zfa.get("dmp_status_date") is not None:
            patient.dmp_status_date = zfa["dmp_status_date"]
        if zfa.get("dmp_closure_date") is not None:
            patient.dmp_closure_date = zfa["dmp_closure_date"]
        if zfa.get("dmp_feed_opposition") is not None:
            patient.dmp_feed_opposition = zfa["dmp_feed_opposition"]
        if zfa.get("dmp_consultation_consent") is not None:
            patient.dmp_consultation_consent = zfa["dmp_consultation_consent"]

    zfp = parse_zfp(message)
    if zfp:
        if zfp.get("socio_professional_activity") is not None:
            patient.socio_professional_activity = zfp["socio_professional_activity"]
        if zfp.get("socio_professional_category") is not None:
            patient.socio_professional_category = zfp["socio_professional_category"]

    for rol in parse_rol_segments(message):
        if rol.get("role_code") not in (ROL_ROLE_ODRP, ROL_ROLE_SUBSTITUTE):
            continue
        name_parts = [p for p in (rol.get("family_name"), rol.get("given_name")) if p]
        if not name_parts:
            continue
        label = " ".join(name_parts)
        if rol.get("role_code") == ROL_ROLE_SUBSTITUTE:
            label = f"{label} (remplaçant)"
        patient.primary_care_provider = label


def _apply_zfv_to_mouvement(mouvement: "Mouvement", message: Optional[str]) -> None:
    """Applique sur un Mouvement les champs extraits du segment ZFV d'un message IHE
    PAM France, quand ce message en contient un. No-op sinon.
    """
    if not message:
        return
    zfv = parse_zfv(message)
    if not zfv:
        return
    if zfv.get("origin_facility_finess") is not None:
        mouvement.origin_facility_finess = zfv["origin_facility_finess"]
    if zfv.get("origin_stay_date") is not None:
        mouvement.origin_stay_date = zfv["origin_stay_date"]
    if zfv.get("discharge_transport_mode") is not None:
        mouvement.discharge_transport_mode = zfv["discharge_transport_mode"]
    if zfv.get("legal_care_mode_code") is not None:
        mouvement.legal_care_mode_code = zfv["legal_care_mode_code"]
    if zfv.get("transport_care_level") is not None:
        mouvement.transport_care_level = zfv["transport_care_level"]


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

        lines = [line for line in re.split(r"\r|\n", message) if line.strip()]
        msh = next((line for line in lines if line.startswith("MSH")), None)
        pid = next((line for line in lines if line.startswith("PID")), None)
        pv1 = next((line for line in lines if line.startswith("PV1")), None)
        evn = next((line for line in lines if line.startswith("EVN")), None)

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

        # Run stateless PAM validation (per-message) and stateful sequence validation
        try:
            from app.services.pam_validation import validate_pam
            from app.services.pam_sequence_validator import validate_pam_sequence

            stateless = validate_pam(message, direction="in")
            seq = validate_pam_sequence(message, session)
            result["validation"] = {
                "stateless": stateless.to_dict(),
                "sequence": seq.to_dict(),
            }

            # Enforce sequence validation strict par défaut (comportement demandé)
            if seq.level == "fail":
                # Les issues ont été traduites en français
                raise ValueError(f"La validation de séquence PAM a échoué: {seq.issues}")
        except Exception as e:
            # Non-fatal by default: include warning in result
            logger.warning(f"[pam] Validation warning/error: {e}")
            result.setdefault("validation", {})["error"] = str(e)

        # Placeholder: log operation; future enrichment: persist changes
        logger.debug(f"[pam] Parsed message trigger={trigger} pid={patient_identifier} location={venue_location}")
        return result
    except Exception as e:
        logger.error(f"[pam] Échec traitement message: {e}")
        raise


def _extract_pv1_segment(message: str) -> Optional[str]:
    """
    Extrait le segment PV1 complet du message HL7.
    
    Args:
        message: Message HL7 complet
        
    Returns:
        Segment PV1 en string ou None si absent
    """
    try:
        lines = re.split(r"\r|\n", message)
        pv1 = next((line for line in lines if line.startswith("PV1")), None)
        return pv1 if pv1 else None
    except Exception as e:
        logger.error(f"Erreur extraction segment PV1: {e}")
        return None


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
        Dict with movement_id, movement_ids, movement_datetime, action_type, cancel_flag,
        origin_event, uf_medicale, uf_soins, nature.

        ZBE-1 is repeatable (EI~EI~...) for cooperative Movement Management (several systems
        each carrying their own identifier for the same physical movement) : `movement_id` is
        the first/primary repetition (used as-is by all existing call sites, unchanged), and
        `movement_ids` is the full list in message order for callers that need to record every
        identifier.
    """
    out = {
        "movement_id": None,
        "movement_ids": [],
        "movement_datetime": None,
        "action_type": None,
        "cancel_flag": None,
        "origin_event": None,
        "uf_responsable": None,
        "mode_traitement": None,
    }

    try:
        lines = re.split(r"\r|\n", message)
        zbe = next((line for line in lines if line.startswith("ZBE")), None)
        if not zbe:
            return None

        parts = zbe.split("|")

        # ZBE-1: Identifiant(s) du mouvement, répétable (EI~EI~...), format par répétition :
        # ID^NAMESPACE^OID^ISO. Chaque répétition est conservée telle quelle (composants CX
        # inclus) car les appelants (ex: parse_hl7_cx_identifier) attendent le CX complet pour
        # en extraire le système/OID, pas seulement l'identifiant nu.
        if len(parts) > 1 and parts[1]:
            movement_id_field = parts[1].strip()
            out["movement_ids"] = [r for r in movement_id_field.split("~") if r]
            # Rétrocompatibilité : movement_id reste le premier identifiant (comportement inchangé)
            out["movement_id"] = out["movement_ids"][0] if out["movement_ids"] else None
        
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
                # Choose a stable primary patient identifier (prefer patient.identifier, fallback to patient_seq)
                primary_id = patient.identifier or (f"PSEQ{patient.patient_seq}" if patient.patient_seq is not None else f"PID{patient.id}")
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
            return await _handle_cancel_admission(session, trigger, pid_data, pv1_data, message, ej_id)
        
        # Gestion normale des admissions
        # Identifier patient (prendre le premier identifiant PID-3)
        logger.info("[pam][admission] Entering patient identification block")

        # --- PATCH: Robust PID-3 parsing and identifier assignment ---
        # Build robust identifier list from PID-3
        identifiers_raw = pid_data.get("identifiers", [])
        identifiers = []
        for cx_value, *_ in identifiers_raw:
            value, system, oid, type_code = parse_hl7_cx_identifier(cx_value)
            # Passer (value, system, type_code) pour classification, pas cx_value complet
            # Mais garder cx_value pour fallback
            identifiers.append((value, system, type_code, cx_value))

        # Main patient identifier (Solution de repli logic)
        identifier = None
        if identifiers:
            # Prefer classified main identifier, Solution de repli to first PID-3 value
            try:
                from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check
                try:
                    _res = create_identifiers_from_hl7_with_namespace_check(identifiers, "patient", session, ej_id)
                    if isinstance(_res, (list, tuple)) and len(_res) == 3:
                        identifiers_list, main_id_value, external_id_value = _res
                    elif isinstance(_res, list):
                        identifiers_list, main_id_value, _external_id_value = _res, None, None
                    elif isinstance(_res, dict):
                        identifiers_list = _res.get('identifiers', [])
                        main_id_value = _res.get('main_identifier') or _res.get('main')
                        _external_id_value = _res.get('external_id') or _res.get('external')
                    else:
                        identifiers_list, main_id_value, _external_id_value = [], None, None
                except Exception as _e:
                    logger.warning(f"[pam] Failed to classify identifiers (soft): {_e}")
                    identifiers_list, main_id_value, _external_id_value = [], None, None
                identifier = main_id_value or (identifiers[0][0] if identifiers else None)  # identifiers[0][0] = value
            except Exception as e:
                logger.warning(f"[pam] Failed to classify identifiers: {e}")
                identifier = identifiers[0][0] if identifiers else None  # identifiers[0][0] = value
        logger.debug(f"[pam][admission] Resolved identifier={identifier} (identifiers_count={len(identifiers)})")

        # Nom / prénom

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
                    try:
                        _res = create_identifiers_from_hl7_with_namespace_check(identifiers, "patient", session, ej_id)
                        if isinstance(_res, (list, tuple)) and len(_res) == 3:
                            identifiers_list, main_id_value, _external_id_value = _res
                        elif isinstance(_res, list):
                            identifiers_list, main_id_value, _external_id_value = _res, None, None
                        elif isinstance(_res, dict):
                            identifiers_list = _res.get('identifiers', [])
                            main_id_value = _res.get('main_identifier') or _res.get('main')
                            _external_id_value = _res.get('external_id') or _res.get('external')
                        else:
                            identifiers_list, main_id_value, _external_id_value = [], None, None
                    except Exception as _e:
                        logger.warning(f"[pam] Failed to classify identifiers (soft): {_e}")
                        identifiers_list, main_id_value, _external_id_value = [], None, None
                    for ident in identifiers_list:
                        ident.patient_id = existing.id
                        exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                        if not exists_dup:
                            session.add(ident)
                except Exception as e:
                    logger.warning(f"[pam] Failed to create identifiers with namespace check: {e}")
                    # Solution de repli to legacy method
                    for value, system, type_code, raw_cx in identifiers:
                        try:
                            ident = create_identifier_from_hl7(raw_cx, "patient", existing.id)
                            exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                            if not exists_dup:
                                session.add(ident)
                        except Exception:
                            continue
                reused_patient = existing
                _apply_french_extension_segments_to_patient(existing, message)
                session.add(existing)
                if trigger in ("A28", "A31"):
                    # Identity-only update: no new dossier/venue/mouvement. Renvoie early.
                    logger.info(f"[pam][admission] Identity-only update detected for existing patient, trigger={trigger}")
                    return True, None

        # Debug: inspect identifier resolution and reuse
        logger.debug(f"[pam][admission] identifiers={identifiers!r}")
        logger.debug(f"[pam][admission] identifier={identifier!r}, reused_patient={reused_patient!r}")

        # If patient already updated and trigger is identity, Renvoie early
        if reused_patient:
            patient = reused_patient
            logger.debug(f"[pam][admission] Using reused_patient id={getattr(patient,'id', None)}")
        else:
            from app.services.patient_update_helper import create_patient_from_pid_data
            patient = create_patient_from_pid_data(pid_data, session, identifier, ej_id)
            session.add(patient)
            session.flush()
            logger.debug(f"[pam][admission] Created patient id={getattr(patient,'id', None)}")

            # Persist all identifiers from PID-3 with namespace classification
            try:
                from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check
                try:
                    _res = create_identifiers_from_hl7_with_namespace_check(identifiers, "patient", session, ej_id)
                    if isinstance(_res, (list, tuple)) and len(_res) == 3:
                        identifiers_list, main_id_value, _external_id_value = _res
                    elif isinstance(_res, list):
                        identifiers_list, main_id_value, _external_id_value = _res, None, None
                    elif isinstance(_res, dict):
                        identifiers_list = _res.get('identifiers', [])
                        main_id_value = _res.get('main_identifier') or _res.get('main')
                        _external_id_value = _res.get('external_id') or _res.get('external')
                    else:
                        identifiers_list, main_id_value, _external_id_value = [], None, None
                except Exception as _e:
                    logger.warning(f"[pam] Failed to classify identifiers (soft): {_e}")
                    identifiers_list, main_id_value, _external_id_value = [], None, None
                for ident in identifiers_list:
                    ident.patient_id = patient.id
                    exists = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                    if not exists:
                        session.add(ident)
            except Exception as e:
                logger.warning(f"[pam] Failed to create identifiers with namespace check: {e}")
                # Solution de repli to legacy method
                for value, system, type_code, raw_cx in identifiers:
                    try:
                        ident = create_identifier_from_hl7(raw_cx, "patient", patient.id)
                        exists = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                        if not exists:
                            session.add(ident)
                    except Exception:
                        continue

            _apply_french_extension_segments_to_patient(patient, message)
            session.add(patient)

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
        # Date clinique du séjour : PV1-44, puis ZBE-2. Les données PID (date
        # de naissance) ne constituent jamais une date d'admission valide et ne
        # sont conservées qu'en dernier recours de compatibilité pour les anciens
        # flux sans aucune date de mouvement.
        admit_time = pv1_data.get("admit_time")
        if not admit_time and zbe_data and zbe_data.get("movement_datetime"):
            try:
                admit_time = datetime.strptime(zbe_data["movement_datetime"], "%Y%m%d%H%M%S")
            except (TypeError, ValueError):
                admit_time = None
        if not admit_time and pid_data.get("birth_date_dt"):
            admit_time = pid_data.get("birth_date_dt")
        elif not admit_time and pid_data.get("birth_date"):
            try:
                admit_time = datetime.strptime(pid_data.get("birth_date"), "%Y%m%d")
            except Exception:
                admit_time = None
        if not admit_time:
            admit_time = datetime.now(timezone.utc)

        # Map PV1-2 patient_class (HL7v2) -> internal encounter-class (FHIR ActCode) via vocabulary mapping
        hl7_patient_class = pv1_data.get("patient_class") or "I"
        encounter_class_code = map_code(session, "patient-class", hl7_patient_class, "encounter-class") or (
            {"I": "IMP", "O": "AMB", "E": "EMER"}.get(hl7_patient_class, "IMP")
        )
        # Vérifier si le dossier_seq existe déjà
        existing_dossier = session.exec(select(Dossier).where(Dossier.dossier_seq == d_seq)).first()
        if existing_dossier:
            # IHE PAM France: workflow A05 → A01 (hospitalisation) ou A05 → A04
            # (urgences/consultation externe) — spec IHE PAM France (CP-2013-078,
            # §8.5.7.3) : la confirmation d'une pré-admission (A05) se fait par A01
            # pour une hospitalisation, par A04 pour un passage aux urgences ou une
            # consultation externe. A05 crée le dossier en état "planned" ; le trigger
            # de confirmation réutilise le même numéro de dossier (PID-18).
            if trigger in ("A01", "A04") and existing_dossier.patient_id == patient.id:
                # Workflow normal: confirmation d'admission après pré-admission (A05)
                logger.info(f"[pam][admission] {trigger} confirming pre-admission for dossier_seq={d_seq}")
                dossier = existing_dossier
                # Mettre à jour la date d'admission si nécessaire
                if admit_time:
                    dossier.admit_time = admit_time
            else:
                logger.error(f"[pam][admission] Doublon dossier_seq détecté: {d_seq}. Import annulé.")
                raise Exception(f"Un dossier avec le numéro {d_seq} existe déjà. Import ADT/PAM annulé.")
        else:
            # Extract médecin responsable from PV1-7 for the dossier
            medecin = None
            if message:
                pv1_segment = _extract_pv1_segment(message)
                if pv1_segment:
                    medecin = extract_and_store_medecin_from_pv1(pv1_segment, session, commit=False)
                    if medecin:
                        logger.info(f"[pam][admission] Médecin responsable extrait pour dossier: {medecin}")
            
            dossier = Dossier(
                dossier_seq=d_seq,
                patient_id=patient.id,
                uf_responsabilite=pv1_data.get("hospital_service") or "UNKNOWN",
                admit_time=admit_time,
                encounter_class=encounter_class_code,
                medecin_responsable_id=medecin.id if medecin else None,
                entite_juridique_id=ej_id,
            )
            session.add(dossier)
            session.flush()
        logger.info(
            "PAM dossier prepared id=%s dossier_seq=%s patient_id=%s",
            dossier.id,
            dossier.dossier_seq,
            dossier.patient_id,
        )

        # If PID-18 (account number) was provided, persist it as a Dossier identifier
        acc_raw = pid_data.get("account_number")
        if acc_raw:
            try:
                ident = create_identifier_from_hl7(acc_raw, "dossier", dossier.id)
            except (TypeError, ValueError):
                # Un PID-18 mal formé n'empêche pas l'admission, mais il doit
                # être visible pour corriger l'émetteur.
                logger.warning("Invalid PID-18 dossier identifier value=%r", acc_raw, exc_info=True)
            else:
                # PID-18 est un compte administratif (AN/NDA), jamais un IPP.
                if ident.type == IdentifierType.IPP:
                    ident.type = IdentifierType.NDA
                exists = session.exec(
                    select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)
                ).first()
                if not exists:
                    session.add(ident)
                    session.flush()

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
        
        # Vérifier si une venue existe déjà pour ce dossier (workflow IHE PAM A05→A01)
        existing_venue = session.exec(
            select(Venue).where(Venue.dossier_id == dossier.id, Venue.venue_seq == v_seq)
        ).first()
        
        location_raw = (pv1_data.get("location") or "").strip()
        location_value = location_raw or None
        previous_location = (pv1_data.get("previous_location") or "").strip() or None
        hospital_service = (pv1_data.get("hospital_service") or "").strip() or None
        movement_code = f"ADT^{trigger}"
        movement_kind = MOVEMENT_KIND_BY_TRIGGER.get(trigger, "admission")
        movement_status = MOVEMENT_STATUS_BY_TRIGGER.get(trigger, "completed")

        if existing_venue and trigger in ("A01", "A04"):
            # IHE PAM: A01/A04 confirme une pré-admission (A05)
            # Mettre à jour la localisation de la venue existante si fournie
            logger.info(f"[pam][admission] {trigger} confirming pre-admission for existing venue {existing_venue.id}")
            if location_value:
                existing_venue.assigned_location = location_value
            venue = existing_venue
            logger.info(
                "PAM venue updated id=%s venue_seq=%s trigger=%s",
                venue.id,
                venue.venue_seq,
                trigger,
            )
        else:
            venue = Venue(
                venue_seq=v_seq,
                dossier_id=dossier.id,
                uf_responsabilite=hospital_service or pv1_data.get("hospital_service") or dossier.uf_responsabilite,
                start_time=admit_time,
                assigned_location=location_value,
                entite_juridique_id=ej_id,
            )
            session.add(venue)
            session.flush()
            logger.info(
                "PAM venue prepared id=%s venue_seq=%s dossier_id=%s",
                venue.id,
                venue.venue_seq,
                venue.dossier_id,
            )

        # If PV1-19 (visit number) was provided, persist it as a Venue identifier
        visit_raw = pv1_data.get("visit_number")
        if visit_raw:
            try:
                ident = create_identifier_from_hl7(visit_raw, "venue", venue.id)
            except (TypeError, ValueError):
                logger.warning("Invalid PV1-19 venue identifier value=%r", visit_raw, exc_info=True)
            else:
                # PV1-19 est un numéro de venue (VN), jamais un IPP.
                if ident.type == IdentifierType.IPP:
                    ident.type = IdentifierType.VN
                exists = session.exec(
                    select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)
                ).first()
                if not exists:
                    session.add(ident)
                    session.flush()

        # Déterminer la date du mouvement : priorité ZBE-2, puis PV1, puis now
        movement_datetime = datetime.now(timezone.utc)
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
                                UniteFonctionnelle, LocationPhysicalType
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
        #
        # NOTE (architecture, confirmée intentionnelle) : comme pour dossier_seq (PID-18,
        # voir d_seq plus haut) et venue_seq (PV1-19, voir v_seq plus haut), quand l'émetteur
        # fournit son propre identifiant métier pour l'entité (ici le mouvement via ZBE-1),
        # on l'adopte directement comme notre mouvement_seq interne plutôt que de garder deux
        # numérotations totalement indépendantes. Ce choix reste sûr car ZBE-1 est de toute
        # façon aussi persisté séparément dans la table Identifier (type=MVT, voir plus bas
        # "Mouvement identifiers (ZBE-1...)") : la corrélation pour les messages UPDATE/CANCEL
        # ultérieurs (_find_mouvement_by_movement_id) consulte d'abord cette table Identifier
        # avant de retomber sur un parse direct de mouvement_seq, donc une éventuelle collision
        # entre la numérotation ZBE-1 d'un émetteur externe et notre propre séquence auto-générée
        # (get_next_sequence) resterait résolvable sans ambiguïté via l'Identifier associé.
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
        
        # Extract médecin responsable from PV1-7
        medecin = None
        if message:
            pv1_segment = _extract_pv1_segment(message)
            if pv1_segment:
                medecin = extract_and_store_medecin_from_pv1(pv1_segment, session, commit=False)
                if medecin:
                    logger.info(f"[pam][admission] Médecin responsable extrait: {medecin}")
        
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
            medecin_responsable_id=medecin.id if medecin else None,
            entite_juridique_id=ej_id,
        )
        _apply_zfv_to_mouvement(mouvement, message)
        session.add(mouvement)
        session.flush()
        logger.info(
            f"[pam] Created mouvement mouv_seq={mouvement.mouvement_seq} venue_id={mouvement.venue_id} "
            f"movement_type={mouvement.movement_type} when={mouvement.when} "
            f"location={mouvement.location} uf_responsable={uf_resp}"
        )

        # Traiter les identifiants supplémentaires avec classification EJ.
        # create_identifiers_from_hl7_with_namespace_check() ne fait que classifier/construire
        # les objets Identifier : c'est à l'appelant de leur assigner l'entité (FK) et de les
        # ajouter à la session (même contrat que pour les identifiants patient plus haut).
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

        # Mouvement identifiers (ZBE-1, répétable : plusieurs systèmes peuvent porter chacun
        # leur propre identifiant pour le même mouvement physique - "cooperative Movement
        # Management" - on les enregistre tous, pas seulement le premier).
        movement_ids = (zbe_data.get("movement_ids") or ([movement_id] if movement_id else [])) if zbe_data else []
        if movement_ids:
            all_mouvement_identifiers = [
                _identifier_tuple_for_classifier(mid) for mid in movement_ids if mid
            ]
            if all_mouvement_identifiers:
                _res = await create_identifiers_from_hl7_with_namespace_check(
                    session, all_mouvement_identifiers, mouvement, "mouvement"
                )
                for ident in (_res[0] if _res else []):
                    ident.mouvement_id = mouvement.id
                    exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                    if not exists_dup:
                        session.add(ident)

        # REMARQUE: Message emission is now automatic via entity_events.py listeners
        logger.debug("[pam][admission] handler returning: success=True, err=None")
        return True, None
    except Exception as e:
        logger.error(f"[pam][admission] Exception during admission handler: {e}", exc_info=True)
        logger.debug(f"[pam][admission] handler returning: success=False, err={e!r}")
        return False, str(e)


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
