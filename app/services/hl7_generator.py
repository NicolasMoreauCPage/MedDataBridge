"""
Générateur de messages HL7 PAM dynamiques.

Ce module génère des messages HL7 v2.5 PAM (Patient Administration Management)
à partir des entités du modèle de données (Patient, Dossier, Venue, Mouvement).

Avantages:
- Dates toujours actuelles (plus besoin de update_hl7_message_dates)
- Cohérence Patient HL7 = Patient en base
- Support complet des namespaces et identifiants
- Génération dynamique avec ZBE segments
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import os

from app.models import Patient, Dossier, Venue, Mouvement
from app.models_shared import SystemEndpoint
from app.models_identifiers import Identifier
from app.models_structure_fhir import IdentifierNamespace
from sqlmodel import Session, select


def format_datetime(dt: Optional[datetime] = None) -> str:
    """Format datetime en HL7 timestamp (YYYYMMDDHHmmss)."""
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime("%Y%m%d%H%M%S")


def format_date(dt: Optional[datetime] = None) -> str:
    """Format datetime en HL7 date (YYYYMMDD)."""
    if dt is None:
        return ""
    # Accepter aussi des chaînes ISO ("YYYY-MM-DD") ou déjà format HL7
    if isinstance(dt, str):
        s = dt.strip()
        if len(s) == 8 and s.isdigit():  # déjà au format YYYYMMDD
            return s
        # Essayer quelques formats courants
        from datetime import datetime as _dt
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return _dt.strptime(s, fmt).strftime("%Y%m%d")
            except Exception:
                continue
        # fallback: retirer non chiffres
        digits = ''.join(c for c in s if c.isdigit())
        if len(digits) >= 8:
            return digits[:8]
        return ""
    return dt.strftime("%Y%m%d")


def build_msh_segment(
    *,
    message_type: str,
    trigger_event: str,
    control_id: str,
    timestamp: Optional[datetime] = None,
    sending_application: str = "MedBridge",
    sending_facility: str = "POC",
    receiving_application: str = "TARGET",
    receiving_facility: str = "TARGET"
) -> str:
    """
    Construit le segment MSH (Message Header).
    
    Args:
        message_type: Type de message (ex: "ADT")
        trigger_event: Événement déclencheur (ex: "A01", "A02")
        control_id: ID de contrôle du message
        timestamp: Date/heure du message
        sending_application: Application émettrice
        sending_facility: Établissement émetteur
        receiving_application: Application réceptrice
        receiving_facility: Établissement récepteur
    
    Returns:
        Segment MSH formaté
    """
    ts = format_datetime(timestamp)
    return (
        f"MSH|^~\\&|{sending_application}|{sending_facility}|"
        f"{receiving_application}|{receiving_facility}|"
        f"{ts}||{message_type}^{trigger_event}|{control_id}|P|2.5"
    )


def build_pid_segment(
    patient: Patient,
    identifiers: Optional[List[Identifier]] = None,
    session: Optional[Session] = None
) -> str:
    """
    Construit le segment PID (Patient Identification).
    
    Args:
        patient: Patient
        identifiers: Liste des identifiants (optionnel, sinon chargés depuis DB)
        session: Session DB pour charger les identifiants si besoin
    
    Returns:
        Segment PID formaté
    """
    # Charger les identifiants si pas fournis
    if identifiers is None and session:
        identifiers = session.exec(
            select(Identifier).where(Identifier.patient_id == patient.id)
        ).all()
    
    # PID-3: Identifiants patient (format: ID^^^AUTHORITY&OID&ISO^PI)
    pid_3_parts = []
    if identifiers:
        for ident in identifiers:
            # Charger le namespace via system match si session disponible
            namespace = None
            if session and ident.system:
                namespace = session.exec(
                    select(IdentifierNamespace).where(IdentifierNamespace.system == ident.system)
                ).first()
            
            if namespace:
                # Format: ID^^^AUTHORITY&OID&ISO^PI
                pid_3_parts.append(
                    f"{ident.value}^^^{namespace.name}&{namespace.system.split(':')[-1]}&ISO^PI"
                )
            else:
                # Fallback: utiliser OID directement de l'identifier
                oid = ident.oid or ident.system.split(":")[-1] if ident.system else "UNKNOWN"
                pid_3_parts.append(f"{ident.value}^^^{oid}^PI")
    
    # Si pas d'identifiants, utiliser l'external_id si présent
    if not pid_3_parts and patient.external_id:
        pid_3_parts.append(patient.external_id)
    
    pid_3 = "~".join(pid_3_parts) if pid_3_parts else ""
    
    # PID-5: Nom du patient (Family^Given)
    pid_5 = f"{patient.family or ''}^{patient.given or ''}"
    
    # PID-7: Date de naissance
    pid_7 = format_date(patient.birth_date)
    
    # PID-8: Genre
    pid_8 = patient.gender or ""
    
    return f"PID|||{pid_3}||{pid_5}||{pid_7}|{pid_8}"


def build_pv1_segment(
    dossier: Dossier,
    venue: Optional[Venue] = None,
    identifiers: Optional[List[Identifier]] = None,
    session: Optional[Session] = None
) -> str:
    """
    Construit le segment PV1 (Patient Visit).
    
    Args:
        dossier: Dossier patient
        venue: Venue/séjour (optionnel)
        identifiers: Identifiants du dossier
        session: Session DB
    
    Returns:
        Segment PV1 formaté
    """
    # PV1-2: Type de patient (I=Inpatient, O=Outpatient, E=Emergency)
    patient_class = dossier.dossier_type or "I"
    if patient_class == "URGENCE":
        patient_class = "E"
    elif patient_class == "EXTERNE":
        patient_class = "O"
    else:
        patient_class = "I"
    
    # PV1-3: Localisation (code venue si présent)
    location = ""
    if venue:
        location = venue.code or ""
    
    # PV1-19: Numéro de visite (NDA)
    visit_number = ""
    if identifiers is None and session:
        identifiers = session.exec(
            select(Identifier).where(Identifier.dossier_id == dossier.id)
        ).all()
    
    if identifiers:
        for ident in identifiers:
            namespace = None
            if session and ident.system:
                namespace = session.exec(
                    select(IdentifierNamespace).where(IdentifierNamespace.system == ident.system)
                ).first()
            
            if namespace and namespace.type == "NDA":
                visit_number = f"{ident.value}^^^{namespace.name}&{namespace.system.split(':')[-1]}&ISO^VN"
                break
            elif ident.type == "NDA":
                # Fallback sans namespace
                oid = ident.oid or ident.system.split(":")[-1] if ident.system else "UNKNOWN"
                visit_number = f"{ident.value}^^^{oid}^VN"
                break
    
    # PV1-10: UF responsable (format: ^^^^^UF_CODE)
    uf = dossier.uf_responsabilite or ""
    
    # PV1-44: Date/heure admission
    admit_time = format_datetime(dossier.admit_time)
    
    return f"PV1||{patient_class}|{location}|||||||{uf}||||||||||||{visit_number}|||||||||||||||||||||||||{admit_time}"


def build_zbe_segment(
    movement: Mouvement,
    namespace: Optional[IdentifierNamespace] = None,
    uf_responsabilite: Optional[str] = None,
    uf_soins: Optional[str] = None,
    action: Optional[str] = None,
    original_trigger: Optional[str] = None,
    is_historic: Optional[bool] = None,
    nature: Optional[str] = None,
) -> str:
    """Construit le segment ZBE conforme IHE PAM FR.

    Champs couverts:
    - ZBE-1: Identifiants mouvement (principal + répétés) (ici uniquement principal)
    - ZBE-2: Date/heure du mouvement
    - ZBE-3: Réservé (vide dans profil FR)
    - ZBE-4: Action (INSERT|UPDATE|CANCEL)
    - ZBE-5: Historique (Y|N)
    - ZBE-6: Trigger original (requis si UPDATE/CANCEL)
    - ZBE-7: UF médicale (XON) composant 1 label, composant 10 code
    - ZBE-8: UF soins (XON) composant 1 label, composant 10 code
    - ZBE-9: Nature (S,H,M,L,D,SM)
    """
    # ZBE-1
    movement_id = movement.mouvement_seq or movement.id
    if namespace:
        zbe_1 = f"{movement_id}^{namespace.name}^{namespace.oid}^ISO"
    else:
        zbe_1 = str(movement_id)

    # ZBE-2
    zbe_2 = format_datetime(movement.when)

    # ZBE-3 (vide)
    zbe_3 = ""

    # ZBE-4 Action
    effective_action = action or movement.action or "INSERT"
    if effective_action not in {"INSERT", "UPDATE", "CANCEL"}:
        effective_action = "INSERT"
    zbe_4 = effective_action

    # ZBE-5 Historic flag
    historic_flag = (is_historic if is_historic is not None else movement.is_historic)
    zbe_5 = "Y" if historic_flag else "N"

    # ZBE-6 original trigger (only if UPDATE/CANCEL)
    orig_trig = original_trigger or movement.original_trigger or ""
    if zbe_4 in {"UPDATE", "CANCEL"} and not orig_trig:
        # Best effort fallback: use movement.trigger_event if present
        orig_trig = movement.trigger_event or ""
    zbe_6 = orig_trig if zbe_4 in {"UPDATE", "CANCEL"} else ""

    # ZBE-7 UF médicale XON format Nom^^^^^^^^^Code
    uf_med_code = movement.uf_medicale_code or uf_responsabilite or movement.venue.uf_responsabilite if getattr(movement, "venue", None) else None
    uf_med_label = movement.uf_medicale_label or uf_med_code
    zbe_7 = f"{uf_med_label or ''}^^^^^^^^^{uf_med_code}" if uf_med_code else ""

    # ZBE-8 UF soins XON
    uf_soins_code = movement.uf_soins_code or uf_soins or getattr(movement, "venue", None) and movement.venue.uf_soins or None
    uf_soins_label = movement.uf_soins_label or uf_soins_code
    zbe_8 = f"{uf_soins_label or ''}^^^^^^^^^{uf_soins_code}" if uf_soins_code else ""

    # ZBE-9 Nature
    effective_nature = nature or movement.nature or ""
    valid_natures = {"S", "H", "M", "L", "D", "SM"}
    if effective_nature not in valid_natures:
        # Attempt derivation: map trigger events to nature
        trigger = movement.trigger_event or ""
        mapping = {
            "A01": "H",  # Admission
            "A02": "M",  # Mutation/Transfert
            "A03": "S",  # Sortie
            "A11": "CANCEL",  # Admission annulée -> nature stays H (admission context)
        }
        derived = mapping.get(trigger, "")
        effective_nature = derived if derived in valid_natures else ""
    zbe_9 = effective_nature or ""

    return f"ZBE|{zbe_1}|{zbe_2}|{zbe_3}|{zbe_4}|{zbe_5}|{zbe_6}|{zbe_7}|{zbe_8}|{zbe_9}"


def _is_strict_pam(endpoint: Optional[SystemEndpoint]) -> bool:
    """Détermine si le mode strict PAM FR est actif.

    Priorité:
    1. EntiteJuridique liée à l'endpoint (champ strict_pam_fr)
    2. Variable d'environnement STRICT_PAM_FR
    """
    if endpoint and getattr(endpoint, "entite_juridique", None):
        try:
            if getattr(endpoint.entite_juridique, "strict_pam_fr", False):
                return True
        except Exception:
            pass
    import os as _os
    return _os.getenv("STRICT_PAM_FR", "0") in {"1", "true", "True"}


def generate_adt_message(
    *,
    patient: Patient,
    dossier: Dossier,
    venue: Optional[Venue] = None,
    movement: Optional[Mouvement] = None,
    message_type: str = "ADT",
    trigger_event: str = "A01",
    session: Optional[Session] = None,
    namespaces: Optional[Dict[str, IdentifierNamespace]] = None,
    control_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    endpoint: Optional[SystemEndpoint] = None,
) -> str:
    """
    Génère un message ADT complet.
    
    Args:
        patient: Patient
        dossier: Dossier patient
        venue: Venue/séjour (optionnel)
        movement: Mouvement patient (optionnel, ajoute segment ZBE)
        message_type: Type de message (défaut: "ADT")
        trigger_event: Événement (A01=Admission, A02=Transfert, A03=Sortie, etc.)
        session: Session DB pour charger les identifiants
        namespaces: Dictionnaire des namespaces disponibles
        control_id: ID de contrôle (généré si absent)
        timestamp: Date/heure du message (maintenant si absent)
    
    Returns:
        Message HL7 PAM complet
        
    Raises:
        ValueError: Si les segments obligatoires selon le profil IHE PAM FR ne peuvent pas être générés
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    
    if control_id is None:
        control_id = f"MSG{timestamp.strftime('%Y%m%d%H%M%S')}"
    
    # Validation des segments obligatoires selon le profil IHE PAM FR
    # Triggers considérés comme mouvement (requièrent segment ZBE) selon IHE PAM FR.
    # Les messages d'identité pure (A08 update identité, A28 new patient, A31 update patient, A40/A47 merges/identifier changes)
    # ne doivent PAS exiger ZBE.
    identity_only_triggers = {"A08", "A28", "A31", "A40", "A47"}
    movement_triggers = {"A01", "A02", "A03", "A04", "A05", "A06", "A07",
                         "A11", "A12", "A13", "A21", "A22", "A23", "A38",
                         "A52", "A53", "A54", "A55"}

    # Mode strict PAM FR : exclure A08 si strict (per-EJ ou env)
    if _is_strict_pam(endpoint):
        if trigger_event == "A08":
            raise ValueError("L'événement A08 (mise à jour) est désactivé en mode strict PAM FR (EJ ou environnement)")
        # A08 reste considéré identité-only et ne doit pas être ajouté aux mouvements.
    
    # Validation ZBE assouplie: A01 et A04 peuvent être générés sans mouvement pour
    # permettre des tests d'identité et admissions simples. Les autres movement_triggers
    # exigent un mouvement si le segment ZBE est pertinent.
    if trigger_event in movement_triggers and movement is None and trigger_event not in {"A01", "A04"}:
        raise ValueError(
            f"Le segment ZBE est obligatoire pour le message ADT^{trigger_event} (sauf A01/A04 simplifiés). "
            f"Fournir un objet Mouvement pour générer ZBE."
        )
    
    # Messages A40 (fusion) et A47 (changement identifiant) ne sont pas encore supportés
    # car ils nécessitent le segment MRG
    if trigger_event in {"A40", "A47"}:
        raise NotImplementedError(
            f"Le message ADT^{trigger_event} n'est pas encore supporté par le générateur. "
            f"Ce type de message requiert le segment MRG (Merge Patient Information) qui n'est pas encore implémenté."
        )
    
    # Segments obligatoires
    segments = [
        build_msh_segment(
            message_type=message_type,
            trigger_event=trigger_event,
            control_id=control_id,
            timestamp=timestamp
        ),
        build_pid_segment(patient, session=session),
        build_pv1_segment(dossier, venue=venue, session=session)
    ]
    
    # Segment ZBE si mouvement présent
    if movement:
        movement_namespace = None
        if namespaces and "MOUVEMENT" in namespaces:
            movement_namespace = namespaces["MOUVEMENT"]
        uf_med = dossier.uf_medicale or dossier.uf_responsabilite or (venue.uf_responsabilite if venue else None)
        uf_soins = dossier.uf_soins or (venue.uf_soins if venue else None)
        segments.append(
            build_zbe_segment(
                movement,
                namespace=movement_namespace,
                uf_responsabilite=uf_med,
                uf_soins=uf_soins,
                action=movement.action,
                original_trigger=movement.original_trigger,
                is_historic=movement.is_historic,
                nature=movement.nature,
            )
        )
    
    return "\r".join(segments)


def generate_admission_message(
    patient: Patient,
    dossier: Dossier,
    venue: Venue,
    movement: Optional[Mouvement] = None,
    session: Optional[Session] = None,
    namespaces: Optional[Dict[str, IdentifierNamespace]] = None
) -> str:
    """Génère un message ADT^A01 (Admission)."""
    return generate_adt_message(
        patient=patient,
        dossier=dossier,
        venue=venue,
        movement=movement,
        trigger_event="A01",
        session=session,
        namespaces=namespaces
    )


def generate_transfer_message(
    patient: Patient,
    dossier: Dossier,
    venue: Venue,
    movement: Mouvement,
    session: Optional[Session] = None,
    namespaces: Optional[Dict[str, IdentifierNamespace]] = None
) -> str:
    """Génère un message ADT^A02 (Transfert)."""
    return generate_adt_message(
        patient=patient,
        dossier=dossier,
        venue=venue,
        movement=movement,
        trigger_event="A02",
        session=session,
        namespaces=namespaces
    )


def generate_discharge_message(
    patient: Patient,
    dossier: Dossier,
    venue: Venue,
    movement: Optional[Mouvement] = None,
    session: Optional[Session] = None,
    namespaces: Optional[Dict[str, IdentifierNamespace]] = None
) -> str:
    """Génère un message ADT^A03 (Sortie).

    Fournir un mouvement si l'on veut inclure le segment ZBE (recommandé pour conformité IHE PAM FR).
    """
    return generate_adt_message(
        patient=patient,
        dossier=dossier,
        venue=venue,
        movement=movement,
        trigger_event="A03",
        session=session,
        namespaces=namespaces
    )


def generate_update_message(*, endpoint: Optional[SystemEndpoint] = None, **kwargs) -> str:
    """Génère un message ADT^A08 si autorisé.

    Blocage si:
    - EntiteJuridique liée strict_pam_fr=True
    - OU variable d'environnement STRICT_PAM_FR activée
    """
    if _is_strict_pam(endpoint):
        raise NotImplementedError("generate_update_message (A08) désactivé (mode strict PAM FR per-EJ ou env)")
    return generate_adt_message(trigger_event="A08", endpoint=endpoint, **kwargs)


def generate_cancel_admission_message(
    patient: Patient,
    dossier: Dossier,
    venue: Venue,
    session: Optional[Session] = None,
    namespaces: Optional[Dict[str, IdentifierNamespace]] = None
) -> str:
    """Génère un message ADT^A11 (Annulation admission)."""
    return generate_adt_message(
        patient=patient,
        dossier=dossier,
        venue=venue,
        trigger_event="A11",
        session=session,
        namespaces=namespaces
    )
