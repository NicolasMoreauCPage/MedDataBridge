"""
Service pour extraction et gestion des médecins responsables depuis HL7
"""
from typing import Optional, Tuple
from sqlmodel import Session, select
from app.models_practitioners import MedecinResponsable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def parse_xcn_field(xcn_field: str) -> dict:
    """
    Parse un champ XCN (Extended Composite ID Number and Name for Persons).
    
    Format HL7 XCN: ID^Family^Given^Middle^Suffix^Prefix^Degree^SourceTable^AssigningAuthority...
    
    Composants principaux:
    - XCN-1: ID Number (numéro RPPS ou ADELI)
    - XCN-2: Family Name (nom de famille)
    - XCN-3: Given Name (prénom)
    - XCN-4: Second/Middle Name
    - XCN-5: Suffix (Jr., Sr., III, etc.)
    - XCN-6: Prefix (Dr, Pr, M, Mme, etc.)
    - XCN-9: Assigning Authority (pour identifier le type: RPPS, ADELI)
    
    Exemple PV1-7:
    - "12345678901^DUPONT^Jean^Marie^Dr^RPPS"
    - "123456789^MARTIN^Sophie^^Pr^ADELI"
    
    Returns:
        dict avec les champs extraits
    """
    components = xcn_field.split('^')
    result = {
        'id_number': components[0] if len(components) > 0 and components[0] else None,
        'family_name': components[1] if len(components) > 1 and components[1] else None,
        'given_name': components[2] if len(components) > 2 and components[2] else None,
        'middle_name': components[3] if len(components) > 3 and components[3] else None,
        'suffix': components[4] if len(components) > 4 and components[4] else None,
        'prefix': components[5] if len(components) > 5 and components[5] else None,
        'degree': components[6] if len(components) > 6 and components[6] else None,
        'source_table': components[7] if len(components) > 7 and components[7] else None,
        'assigning_authority': components[8] if len(components) > 8 and components[8] else None,
    }
    
    return result


def identify_id_type(id_number: str, assigning_authority: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Identifie si un numéro est RPPS ou ADELI.
    
    RPPS: 11 chiffres
    ADELI: 9 chiffres
    
    Returns:
        (rpps, adeli) - l'un des deux sera non-None
    """
    if not id_number or not id_number.strip():
        return None, None
    
    id_clean = id_number.strip()
    
    # Vérifier l'autorité d'attribution si fournie
    if assigning_authority:
        auth_upper = assigning_authority.upper()
        if 'RPPS' in auth_upper:
            return id_clean, None
        elif 'ADELI' in auth_upper:
            return None, id_clean
    
    # Sinon, deviner selon la longueur
    if id_clean.isdigit():
        if len(id_clean) == 11:
            return id_clean, None  # RPPS
        elif len(id_clean) == 9:
            return None, id_clean  # ADELI
    
    # Par défaut, considérer comme RPPS si > 9 chiffres, ADELI sinon
    if id_clean.isdigit():
        if len(id_clean) > 9:
            return id_clean, None
        else:
            return None, id_clean
    
    # Si ce n'est pas un numéro pur, on ne peut pas identifier
    logger.warning(f"Unable to identify ID type for: {id_number}")
    return None, None


def extract_medecin_from_pv1_7(pv1_segment: str) -> Optional[dict]:
    """
    Extrait les informations du médecin depuis PV1-7 (Attending Doctor).
    
    Gère les répétitions multiples (séparateur ~) pour capturer RPPS et ADELI
    s'ils sont fournis dans des entrées séparées.
    
    Args:
        pv1_segment: Segment PV1 en string (format: |field1|field2|...|field7|...)
        
    Returns:
        dict avec les informations du médecin ou None si PV1-7 est vide
    """
    try:
        # Parser le segment PV1
        pv1_fields = pv1_segment.split('|')
        
        # PV1-7 est le 7ème champ (index 7 car on compte le segment type au début)
        # Format: PV1|1|field2|...|field6|PV1-7|...
        if len(pv1_fields) < 8:
            return None
        
        attending_doctor = pv1_fields[7].strip()
        
        if not attending_doctor:
            return None
        
        # Si vide ou juste des séparateurs
        if attending_doctor in ('', '~', '^'):
            return None
        
        # Gérer les répétitions (séparées par ~)
        repetitions = attending_doctor.split('~')
        
        # Accumuler les données de toutes les répétitions
        medecin_data = {
            'rpps': None,
            'adeli': None,
            'family_name': None,
            'given_name': None,
            'middle_name': None,
            'prefix': None,
            'suffix': None,
            'specialty': None,
            'active': True,
        }
        
        for xcn_str in repetitions:
            xcn_str = xcn_str.strip()
            if not xcn_str or xcn_str == '^':
                continue
            
            # Parser ce XCN
            xcn_data = parse_xcn_field(xcn_str)
            
            # Identifier RPPS/ADELI
            rpps, adeli = identify_id_type(
                xcn_data['id_number'],
                xcn_data['assigning_authority']
            )
            
            # Accumuler RPPS et ADELI (peut être dans des répétitions différentes)
            if rpps:
                medecin_data['rpps'] = rpps
            if adeli:
                medecin_data['adeli'] = adeli
            
            # Prendre le premier nom/prénom non vide trouvé
            if not medecin_data['family_name'] and xcn_data['family_name']:
                medecin_data['family_name'] = xcn_data['family_name']
            if not medecin_data['given_name'] and xcn_data['given_name']:
                medecin_data['given_name'] = xcn_data['given_name']
            if not medecin_data['middle_name'] and xcn_data['middle_name']:
                medecin_data['middle_name'] = xcn_data['middle_name']
            if not medecin_data['prefix'] and xcn_data['prefix']:
                medecin_data['prefix'] = xcn_data['prefix']
            if not medecin_data['suffix'] and xcn_data['suffix']:
                medecin_data['suffix'] = xcn_data['suffix']
        
        # Ne retourner que si on a au moins un identifiant ou un nom
        if medecin_data['rpps'] or medecin_data['adeli'] or medecin_data['family_name']:
            return medecin_data
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting médecin from PV1-7: {e}")
        return None


def get_or_create_medecin(session: Session, medecin_data: dict) -> Optional[MedecinResponsable]:
    """
    Récupère ou crée un médecin responsable dans la base.
    
    Logique:
    1. Chercher par RPPS (prioritaire)
    2. Sinon chercher par ADELI
    3. Si trouvé, mettre à jour les champs manquants
    4. Si non trouvé, créer
    
    Args:
        session: Session SQLModel
        medecin_data: dict avec les données du médecin
        
    Returns:
        Instance de MedecinResponsable ou None en cas d'erreur
    """
    if not medecin_data:
        return None
    
    try:
        medecin = None
        
        # Chercher par RPPS
        if medecin_data.get('rpps'):
            stmt = select(MedecinResponsable).where(
                MedecinResponsable.rpps == medecin_data['rpps']
            )
            medecin = session.exec(stmt).first()
        
        # Si pas trouvé par RPPS, chercher par ADELI
        if not medecin and medecin_data.get('adeli'):
            stmt = select(MedecinResponsable).where(
                MedecinResponsable.adeli == medecin_data['adeli']
            )
            medecin = session.exec(stmt).first()
        
        # Si pas trouvé et qu'on a au moins un nom, chercher par nom complet
        if not medecin and medecin_data.get('family_name'):
            stmt = select(MedecinResponsable).where(
                MedecinResponsable.family_name == medecin_data['family_name'],
                MedecinResponsable.given_name == medecin_data.get('given_name')
            )
            medecin = session.exec(stmt).first()
        
        if medecin:
            # Mettre à jour les champs manquants
            updated = False
            for key, value in medecin_data.items():
                if key == 'active':
                    continue  # Ne pas écraser le statut actif
                current_value = getattr(medecin, key, None)
                if value and not current_value:
                    setattr(medecin, key, value)
                    updated = True
            
            if updated:
                medecin.updated_at = datetime.now()
                session.add(medecin)
                session.commit()
                session.refresh(medecin)
                logger.info(f"Médecin mis à jour: {medecin}")
        else:
            # Créer nouveau médecin
            medecin = MedecinResponsable(**medecin_data)
            session.add(medecin)
            session.commit()
            session.refresh(medecin)
            logger.info(f"Nouveau médecin créé: {medecin}")
        
        return medecin
        
    except Exception as e:
        logger.error(f"Error in get_or_create_medecin: {e}")
        session.rollback()
        return None


def extract_and_store_medecin_from_pv1(pv1_segment: str, session: Session) -> Optional[MedecinResponsable]:
    """
    Fonction de commodité qui extrait et stocke un médecin depuis PV1-7.
    
    Args:
        pv1_segment: Segment PV1 en string
        session: Session SQLModel
        
    Returns:
        Instance de MedecinResponsable ou None
    """
    medecin_data = extract_medecin_from_pv1_7(pv1_segment)
    if medecin_data:
        return get_or_create_medecin(session, medecin_data)
    return None
