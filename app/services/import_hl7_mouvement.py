# Import HL7 PAM message and create a Mouvement instance with mapping HL7->métier
from app.models import Mouvement
from app.movement_type_mapping import from_standard_movement_code
from typing import Optional

def import_mouvement_from_hl7(hl7_message: str, venue, session) -> Optional[Mouvement]:
    """
    Parse un message HL7 ADT (PAM) et crée un Mouvement avec mapping du type HL7 vers le code métier interne.
    - hl7_message : message HL7 complet (str)
    - venue : instance de Venue à rattacher
    - session : session SQLModel
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

    # Création du Mouvement
    m = Mouvement(
        venue_id=venue.id,
        type=hl7_code,
        movement_type=movement_type,
        when=when_dt,
        status=status,
        mouvement_seq=mouvement_seq,
    )
    session.add(m)
    return m
