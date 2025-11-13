# Import HL7 PAM message and create a Mouvement instance with mapping HL7->métier
from app.models import Mouvement
from app.movement_type_mapping import from_standard_movement_code
from typing import Optional
from sqlmodel import select

def extract_nature_from_hl7(pv1: str, zbe: Optional[str]) -> Optional[str]:
    """
    Extract patient care nature from HL7 segments.
    
    Priority:
    1. ZBE-2 (PAM France) = nature directe (S, H, O, U)
    2. PV1-2 (patient class) = I (Inpatient=H), O (Outpatient=S), E (Emergency=S/O)
    3. None (undefined)
    
    Returns: "S" (externe/ambulatoire), "H" (hospitalisé), "O" (urgence), "U" (autre)
    """
    # Try ZBE-2 first (PAM France standard)
    if zbe:
        zbe_fields = zbe.split('|')
        if len(zbe_fields) > 2 and zbe_fields[2]:
            nature = zbe_fields[2].strip()
            if nature in ["S", "H", "O", "U"]:
                return nature
    
    # Fallback: deduce from PV1-2 (patient class)
    if pv1:
        pv1_fields = pv1.split('|')
        if len(pv1_fields) > 2 and pv1_fields[2]:
            patient_class = pv1_fields[2].strip()
            # HL7 standard patient classes
            if patient_class == "I":
                return "H"  # Inpatient → Hospitalisé
            elif patient_class in ["O", "E"]:
                return "S"  # Outpatient/Emergency → Externe
    
    return None


def validate_a06_a07_coherence(entity: Mouvement, hl7_code: str, session) -> Optional[str]:
    """
    Validate A06/A07 semantic coherence with movement history.
    
    A06 (Outpatient → Inpatient):
    - Current nature must be "H"
    - Previous movement on same venue should have nature "S"
    
    A07 (Inpatient → Outpatient):
    - Current nature must be "S"
    - Previous movement on same venue should have nature "H"
    
    Returns:
    - Error message if incoherent (should reject message)
    - None if coherent or code is not A06/A07 (proceed normally)
    """
    if hl7_code not in ["ADT^A06", "ADT^A07"]:
        return None  # No validation needed
    
    if not hasattr(entity, "nature") or not entity.nature:
        return f"{hl7_code} reçu mais nature non extraite du mouvement"
    
    if not hasattr(entity, "venue_id") or not entity.venue_id:
        return f"{hl7_code} reçu mais venue non définie"
    
    # Query previous movements on same venue
    previous_movements = session.exec(
        select(Mouvement)
        .where(Mouvement.venue_id == entity.venue_id)
        .where(Mouvement.when < entity.when)
        .order_by(Mouvement.when.desc())
    ).all()
    
    if not previous_movements:
        # No previous history on this venue
        return (
            f"{hl7_code} reçu mais pas de mouvement antérieur sur cette venue. "
            f"Impossible de valider la transition."
        )
    
    # Find last movement with defined nature
    last_nature = None
    for prev in previous_movements:
        if hasattr(prev, "nature") and getattr(prev, "nature") in ["H", "S", "O"]:
            last_nature = getattr(prev, "nature")
            break
    
    if not last_nature:
        return (
            f"{hl7_code} reçu mais pas de nature antérieure pour validation. "
            f"Impossible de valider la transition."
        )
    
    # Validate A06: S → H
    if hl7_code == "ADT^A06":
        if last_nature != "S":
            return (
                f"A06 (Outpatient→Inpatient) reçu mais dernier mouvement n'est pas externe (S): {last_nature}. "
                f"Rejeter message ou créer mouvement externe implicite."
            )
        if entity.nature != "H":
            return (
                f"A06 reçu mais nature courante n'est pas hospitalisée (H): {entity.nature}. "
                f"Incohérence détectée."
            )
    
    # Validate A07: H → S
    elif hl7_code == "ADT^A07":
        if last_nature != "H":
            return (
                f"A07 (Inpatient→Outpatient) reçu mais dernier mouvement n'est pas hospitalisé (H): {last_nature}. "
                f"Rejeter message ou créer mouvement hospitalisé implicite."
            )
        if entity.nature != "S":
            return (
                f"A07 reçu mais nature courante n'est pas externe (S): {entity.nature}. "
                f"Incohérence détectée."
            )
    
    return None  # Coherent


def import_mouvement_from_hl7(hl7_message: str, venue, session) -> Optional[Mouvement]:
    """
    Parse un message HL7 ADT (PAM) et crée un Mouvement avec mapping du type HL7 vers le code métier interne.
    - hl7_message : message HL7 complet (str)
    - venue : instance de Venue à rattacher
    - session : session SQLModel
    
    Enrichissements (13 nov 2025):
    - Extrait la nature (S/H/O/U) depuis ZBE-2 ou PV1-2
    - Valide cohérence A06/A07 vs historique
    
    Retourne l'instance Mouvement créée (non commit) ou None si erreur.
    """
    # Découpage simple des segments (suppose CR comme séparateur)
    segments = [line.strip() for line in hl7_message.split('\r') if line.strip()]
    msh = next((s for s in segments if s.startswith('MSH|')), None)
    evn = next((s for s in segments if s.startswith('EVN|')), None)
    pid = next((s for s in segments if s.startswith('PID|')), None)
    pv1 = next((s for s in segments if s.startswith('PV1|')), None)
    zbe = next((s for s in segments if s.startswith('ZBE|')), None)
    if not msh or not evn or not pid or not pv1:
        return None

    # Extraire le type de mouvement HL7 (ex: ADT^A01)
    msh_fields = msh.split('|')
    msg_type = msh_fields[8] if len(msh_fields) > 8 else ''
    hl7_code = msg_type.split('^')[0] + '^' + msg_type.split('^')[1] if '^' in msg_type else msg_type
    # Conversion HL7 -> métier
    movement_type = from_standard_movement_code(hl7_code, 'hl7') or 'autre'

    # Date/heure du mouvement (EVN-2 ou PV1-44)
    evn_fields = evn.split('|')
    when = evn_fields[2] if len(evn_fields) > 2 else ''
    from datetime import datetime
    when_dt = None
    try:
        when_dt = datetime.strptime(when, '%Y%m%d%H%M%S')
    except Exception:
        pass
    if not when_dt and pv1:
        pv1_fields = pv1.split('|')
        if len(pv1_fields) > 44 and pv1_fields[44]:
            try:
                when_dt = datetime.strptime(pv1_fields[44], '%Y%m%d%H%M%S')
            except Exception:
                pass

    # Statut (par défaut 'active')
    status = 'active'

    # Numéro de séquence (ZBE-1 ou PV1-19 ou None)
    mouvement_seq = None
    if zbe:
        zbe_fields = zbe.split('|')
        if len(zbe_fields) > 1 and zbe_fields[1]:
            try:
                mouvement_seq = int(zbe_fields[1])
            except Exception:
                pass
    if not mouvement_seq and pv1:
        pv1_fields = pv1.split('|')
        if len(pv1_fields) > 19 and pv1_fields[19]:
            try:
                mouvement_seq = int(pv1_fields[19])
            except Exception:
                pass

    # ✅ NOUVEAU: Extraire la nature (S/H/O/U)
    nature = extract_nature_from_hl7(pv1, zbe)

    # Création du Mouvement
    m = Mouvement(
        venue_id=venue.id,
        type=hl7_code,
        movement_type=movement_type,
        nature=nature,  # ✅ NOUVEAU: nature extraite
        when=when_dt,
        status=status,
        mouvement_seq=mouvement_seq,
    )
    
    # ✅ NOUVEAU: Valider cohérence A06/A07
    coherence_error = validate_a06_a07_coherence(m, hl7_code, session)
    if coherence_error:
        # Log warning but don't block (allow override if needed)
        import logging
        logging.warning(f"A06/A07 coherence issue: {coherence_error}")
        # Optionally: set flag on mouvement for manual review
        # m.has_validation_warning = True
        # m.validation_warning_msg = coherence_error
    
    session.add(m)
    return m
