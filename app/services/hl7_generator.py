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
from app.models_contacts import PatientContact, VenueContact  # NK1 generation for identity & movement messages
from app.services.nature_mapping import derive_nature
from app.services.vocabulary_translate import reverse_map_code, map_code
from app.models_shared import SystemEndpoint
from app.models_identifiers import Identifier
from app.models_structure import IdentifierNamespace
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
    session: Optional[Session] = None,
    previous_uf: Optional[str] = None,
    trigger_event: Optional[str] = None,
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
    # PV1-2: Patient class HL7v2 -> derived from encounter-class (internal FHIR codes)
    # dossier.encounter_class may hold internal FHIR ActCode (IMP, AMB, EMER). If absent, derive from dossier_type.
    fhir_encounter_class = getattr(dossier, "encounter_class", None)
    if not fhir_encounter_class:
        dt = dossier.dossier_type.value if hasattr(dossier.dossier_type, "value") else dossier.dossier_type
        map_by_type = {"urgence": "EMER", "externe": "AMB", "hospitalise": "IMP"}
        fhir_encounter_class = map_by_type.get(str(dt), "IMP")
    # Translate FHIR encounter class to HL7 patient-class via vocabulary mappings if available.
    patient_class = reverse_map_code(session, "encounter-class", fhir_encounter_class, "patient-class") if session else None
    if not patient_class:
        # Fallback heuristic
        fallback_map = {"EMER": "E", "AMB": "O", "IMP": "I"}
        patient_class = fallback_map.get(fhir_encounter_class, "I")
    
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
    # PV1-6: Prior Patient Location / ici UF précédente en cas de transfert (A02)
    pv1_6 = ""
    if trigger_event == "A02" and previous_uf:
        # Format simple: ^^^^^UF_PRECEDENTE (reuse same pattern)
        pv1_6 = f"^^^^^{previous_uf}"
    
    # PV1-44: Date/heure admission
    admit_time = format_datetime(dossier.admit_time)
    
    # Insert pv1_6 at position PV1-6 (after PV1-5 empty placeholders)
    # Current skeleton: PV1||class|loc|PV1-4|PV1-5|PV1-6|PV1-7.... We'll keep blanks for 4,5.
    return f"PV1||{patient_class}|{location}|||{pv1_6}|||{uf}||||||||||||{visit_number}|||||||||||||||||||||||||{admit_time}"


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
    movement_id = getattr(movement, "mouvement_seq", None) or getattr(movement, "id", None)
    if namespace:
        zbe_1 = f"{movement_id}^{namespace.name}^{namespace.oid}^ISO"
    else:
        zbe_1 = str(movement_id)

    # ZBE-2
    zbe_2 = format_datetime(getattr(movement, "when", None))

    # ZBE-3 (vide)
    zbe_3 = ""

    # ZBE-4 Action
    effective_action = action or getattr(movement, "action", None) or "INSERT"
    if effective_action not in {"INSERT", "UPDATE", "CANCEL"}:
        effective_action = "INSERT"
    zbe_4 = effective_action

    # ZBE-5 Historic flag
    historic_flag = (is_historic if is_historic is not None else getattr(movement, "is_historic", False))
    zbe_5 = "Y" if historic_flag else "N"

    # ZBE-6 original trigger (only if UPDATE/CANCEL)
    orig_trig = original_trigger or getattr(movement, "original_trigger", None) or ""
    if zbe_4 in {"UPDATE", "CANCEL"} and not orig_trig:
        # Best effort fallback: use movement.trigger_event if present
        orig_trig = getattr(movement, "trigger_event", None) or ""
    zbe_6 = orig_trig if zbe_4 in {"UPDATE", "CANCEL"} else ""

    # ZBE-7 UF médicale XON format Nom^^^^^^^^^Code
    uf_med_code = getattr(movement, "uf_medicale_code", None) or uf_responsabilite or (getattr(getattr(movement, "venue", None), "uf_responsabilite", None) if getattr(movement, "venue", None) else None)
    uf_med_label = getattr(movement, "uf_medicale_label", None) or uf_med_code
    zbe_7 = f"{uf_med_label or ''}^^^^^^^^^{uf_med_code}" if uf_med_code else ""

    # ZBE-8 UF soins XON
    # Venue n'a pas (encore) d'attribut uf_soins; on ne tente pas de l'utiliser pour éviter AttributeError
    uf_soins_code = getattr(movement, "uf_soins_code", None) or uf_soins
    uf_soins_label = getattr(movement, "uf_soins_label", None) or uf_soins_code
    zbe_8 = f"{uf_soins_label or ''}^^^^^^^^^{uf_soins_code}" if uf_soins_code else ""

    # ZBE-9 Nature
    trigger = getattr(movement, "trigger_event", None) or original_trigger
    effective_nature = derive_nature(trigger, nature or getattr(movement, "nature", None))
    zbe_9 = effective_nature or ""

    return f"ZBE|{zbe_1}|{zbe_2}|{zbe_3}|{zbe_4}|{zbe_5}|{zbe_6}|{zbe_7}|{zbe_8}|{zbe_9}"


def build_nk1_segment(contact: PatientContact) -> str:
    """Construit un segment NK1 pour un contact patient (ADT A28/A31).

    Champs couverts (positions):
    - NK1-1: Set ID (sequence)
    - NK1-2: Nom (XPN: Family^Given^Middle^Suffix^Prefix)
    - NK1-3: Relation (CE: code^display^system)
    - NK1-4: Adresse (XAD: line1^line2^city^state^postal^country)
    - NK1-5: Téléphone personnel (XTN simplifié)
    - NK1-6: Téléphone professionnel (XTN simplifié)
    - NK1-7: Rôle du contact (code interne ou HL7) (CE simplifié: role^^^^display)
    - NK1-8: Date début relation (YYYYMMDD)
    - NK1-9: Date fin relation (YYYYMMDD)
    - NK1-15: Sexe administratif
    - NK1-16: Date de naissance
    - NK1-20: Langue
    - NK1-29: Raison du contact

    Les autres champs sont laissés vides pour conserver les positions mais ne sont
    pas encore utilisés.
    """
    def _fmt_date(d):
        from datetime import date as _d
        if not d:
            return ""
        if isinstance(d, _d):
            return d.strftime("%Y%m%d")
        # accepter string déjà au bon format
        s = str(d)
        if len(s) == 8 and s.isdigit():
            return s
        return ""

    name = f"{contact.family_name}^{contact.given_name or ''}^{contact.middle_name or ''}^{contact.suffix or ''}^{contact.prefix or ''}"
    relation = f"{contact.relationship_code}^{contact.relationship_display or ''}^{contact.relationship_system or ''}"
    address = f"{contact.address_line1 or ''}^{contact.address_line2 or ''}^{contact.address_city or ''}^" \
              f"^{contact.address_postalcode or ''}^{contact.address_country or ''}"
    phone_home = contact.phone_number or ''
    phone_work = contact.business_phone or ''
    role_ce = contact.contact_role or ''  # Could be expanded later to full CE format
    start_rel = _fmt_date(contact.start_date)
    end_rel = _fmt_date(contact.end_date)
    gender = contact.gender or ''
    birth = _fmt_date(contact.birth_date)
    language = contact.primary_language or ''
    reason = contact.contact_reason or ''

    # Build field list up to NK1-29. Index i corresponds to NK1-(i+1)
    fields = []
    fields.append(str(contact.sequence))            # 1
    fields.append(name)                             # 2
    fields.append(relation)                         # 3
    fields.append(address)                          # 4
    fields.append(phone_home)                       # 5
    fields.append(phone_work)                       # 6
    fields.append(role_ce)                          # 7
    fields.append(start_rel)                        # 8
    fields.append(end_rel)                          # 9
    # NK1-10..NK1-14 unused -> empty placeholders
    for _ in range(5):
        fields.append("")                           # 10-14
    fields.append(gender)                           # 15
    fields.append(birth)                            # 16
    # NK1-17..NK1-19 empty
    for _ in range(3):
        fields.append("")                           # 17-19
    fields.append(language)                         # 20
    # NK1-21..NK1-28 empty
    for _ in range(8):
        fields.append("")                           # 21-28
    fields.append(reason)                           # 29

    return "NK1|" + "|".join(fields)


def build_nk1_segment_venue(contact: VenueContact) -> str:
    """Construit un segment NK1 pour un contact lié à une venue (mouvements A01/A02/A03/A04).

    Structure similaire à build_nk1_segment mais utilise les champs spécifiques (start_datetime/end_datetime).
    """
    def _fmt_dt(d):
        from datetime import datetime as _dt
        if not d:
            return ""
        if isinstance(d, _dt):
            return d.strftime("%Y%m%d%H%M%S")
        s = str(d)
        if len(s) >= 8 and s[:8].isdigit():
            return s[:14]  # tolerer format déjà HL7
        return ""

    name = f"{contact.family_name}^{contact.given_name or ''}^{contact.middle_name or ''}^{contact.suffix or ''}^{contact.prefix or ''}"
    relation = f"{contact.relationship_code}^{contact.relationship_display or ''}^{contact.relationship_system or ''}"
    address = f"{contact.address_line1 or ''}^{contact.address_line2 or ''}^{contact.address_city or ''}^" \
              f"^{contact.address_postalcode or ''}^{contact.address_country or ''}"
    phone_home = contact.phone_number or ''
    phone_work = contact.business_phone or ''
    role_ce = contact.contact_role or ''
    start_dt = _fmt_dt(contact.start_datetime)
    end_dt = _fmt_dt(contact.end_datetime)
    gender = contact.gender or ''
    birth = _fmt_dt(contact.birth_date)[:8] if contact.birth_date else ''
    reason = contact.contact_reason or ''

    fields = []
    fields.append(str(contact.sequence))   # 1
    fields.append(name)                    # 2
    fields.append(relation)                # 3
    fields.append(address)                 # 4
    fields.append(phone_home)              # 5
    fields.append(phone_work)              # 6
    fields.append(role_ce)                 # 7
    fields.append(start_dt)                # 8 (start presence)
    fields.append(end_dt)                  # 9 (end presence)
    for _ in range(5):
        fields.append("")                 # 10-14
    fields.append(gender)                  # 15
    fields.append(birth)                   # 16
    for _ in range(3):
        fields.append("")                 # 17-19
    fields.append("")                      # 20 (langue non utilisée pour venue contact pour l'instant)
    for _ in range(8):
        fields.append("")                 # 21-28
    fields.append(reason)                  # 29
    return "NK1|" + "|".join(fields)


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
    build_pv1_segment(dossier, venue=venue, session=session, trigger_event=trigger_event)
    ]

    # Ajouter les segments NK1 pour les messages d'identité (A28, A31)
    if trigger_event in {"A28", "A31"}:
        # Charger les contacts si non présents et session fournie
        contacts: List[PatientContact] = []
        try:
            if hasattr(patient, "contacts") and patient.contacts:
                contacts = list(patient.contacts)
            elif session:
                from sqlmodel import select as _select
                contacts = session.exec(
                    _select(PatientContact).where(PatientContact.patient_id == patient.id).order_by(PatientContact.sequence)
                ).all()
        except Exception:
            contacts = []  # robust fallback
        # Trier par priority/sequence si attributs disponibles
        contacts.sort(key=lambda c: (getattr(c, 'priority', 1), c.sequence))
        for c in contacts:
            segments.append(build_nk1_segment(c))
    
    # Segment ZBE si mouvement présent
    if movement:
        movement_namespace = None
        if namespaces and "MOUVEMENT" in namespaces:
            movement_namespace = namespaces["MOUVEMENT"]
        # UF médicale et UF soins dérivées principalement du mouvement (ZBE-7/ZBE-8)
        # Ancienne logique référençait des attributs inexistants sur Dossier/Venue (uf_medicale, uf_soins).
        # Fallback: dossier.uf_responsabilite ou venue.uf_responsabilite pour UF médicale si mouvement n'a pas de code.
        uf_med = (
            getattr(movement, "uf_medicale_code", None)
            or getattr(dossier, "uf_medicale", None)  # compat éventuelle si ajouté plus tard
            or getattr(dossier, "uf_responsabilite", None)
            or (getattr(venue, "uf_responsabilite", None) if venue else None)
        )
        # UF soins seulement si fournie sur le mouvement; pas de fallback explicite (segment ZBE-8 peut être vide)
        uf_soins = (
            getattr(movement, "uf_soins_code", None)
            or getattr(dossier, "uf_soins", None)
            or (getattr(venue, "uf_soins", None) if venue else None)
        )
        # Determine previous UF for transfers (A02) from last movement if available
        previous_uf = None
        if trigger_event == "A02" and venue:
            from sqlmodel import select as _select
            if session:
                prev = session.exec(
                    _select(Mouvement)
                    .where(Mouvement.venue_id == venue.id)
                    .where(Mouvement.mouvement_seq < movement.mouvement_seq)
                    .order_by(Mouvement.mouvement_seq.desc())
                ).first()
                if prev and getattr(prev, "uf_medicale_code", None):
                    previous_uf = getattr(prev, "uf_medicale_code", None)
                elif prev and getattr(dossier, "uf_responsabilite", None):
                    previous_uf = getattr(dossier, "uf_responsabilite", None)
        # Rebuild PV1 with previous UF if needed (replace last appended PV1 segment)
        segments[2] = build_pv1_segment(dossier, venue=venue, session=session, previous_uf=previous_uf, trigger_event=trigger_event)
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
    
    # Ajouter NK1 segments pour les mouvements (venue contacts) si trigger mouvement
    movement_trigger_for_contacts = {"A01", "A02", "A03", "A04"}
    if trigger_event in movement_trigger_for_contacts and venue:
        venue_contacts: List[VenueContact] = []
        try:
            if hasattr(venue, "contacts") and venue.contacts:
                venue_contacts = list(venue.contacts)
            elif session:
                from sqlmodel import select as _select
                venue_contacts = session.exec(
                    _select(VenueContact).where(VenueContact.venue_id == venue.id).order_by(VenueContact.sequence)
                ).all()
        except Exception:
            venue_contacts = []
        venue_contacts.sort(key=lambda c: c.sequence)
        for vc in venue_contacts:
            segments.append(build_nk1_segment_venue(vc))

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
