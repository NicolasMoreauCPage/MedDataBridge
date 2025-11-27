"""
Fonctions helper pour créer/mettre à jour Patient depuis données PID parsées.
Gère les champs multi-valués (PID-5, PID-11, PID-13) et les nouveaux champs.
"""
from typing import Dict, Optional
from sqlmodel import Session
from app.models import Patient
import logging
from app.services.identifier_manager import map_hl7_type_to_identifier_type

logger = logging.getLogger(__name__)


def update_patient_from_pid_data(
    patient: Patient,
    pid_data: Dict,
    session: Session,
    create_mode: bool = False
) -> Patient:
    """
    Met à jour un Patient existant (ou nouveau) avec les données PID parsées.
    
    Gère les champs multi-valués:
    - PID-5: noms (usuel, naissance)
    - PID-11: adresses (habitation, naissance)
    - PID-13: téléphones (fixe, mobile, travail)
    - PID-23: lieu de naissance
    - PID-32: identity reliability code
    
    Args:
        patient: Instance Patient à mettre à jour
        pid_data: Dict retourné par _parse_pid()
        session: Session DB
        create_mode: Si True, c'est une création (ne pas écraser champs vides)
    
    Returns:
        Patient mis à jour
    """
    # Noms (PID-5) - multi-valué
    if pid_data.get("family"):
        patient.family = pid_data["family"]
    if pid_data.get("given"):
        patient.given = pid_data["given"]
    if pid_data.get("middle"):
        patient.middle = pid_data["middle"]
    if pid_data.get("prefix"):
        patient.prefix = pid_data["prefix"]
    if pid_data.get("suffix"):
        patient.suffix = pid_data["suffix"]
    
    # Nom de naissance si présent (2e répétition PID-5)
    if pid_data.get("birth_family"):
        patient.birth_family = pid_data["birth_family"]
    
    # Date de naissance (PID-7)
    if pid_data.get("birth_date"):
        birth_date_raw = pid_data["birth_date"]
        birth_date_obj = None
        from datetime import datetime, date
        if isinstance(birth_date_raw, str):
            try:
                if len(birth_date_raw) == 8 and birth_date_raw.isdigit():
                    birth_date_obj = datetime.strptime(birth_date_raw, "%Y%m%d").date()
                else:
                    birth_date_obj = datetime.strptime(birth_date_raw, "%Y-%m-%d").date()
            except Exception:
                birth_date_obj = None
        elif isinstance(birth_date_raw, date):
            birth_date_obj = birth_date_raw
        patient.birth_date = birth_date_obj
    
    # Genre (PID-8)
    if pid_data.get("gender"):
        patient.gender = pid_data["gender"]
    
    # Adresse habitation (PID-11, 1ère répétition)
    if pid_data.get("address"):
        patient.address = pid_data["address"]
    if pid_data.get("city"):
        patient.city = pid_data["city"]
    if pid_data.get("state"):
        patient.state = pid_data["state"]
    if pid_data.get("postal_code"):
        patient.postal_code = pid_data["postal_code"]
    if pid_data.get("country"):
        patient.country = pid_data["country"]
    
    # Adresse de naissance (PID-11, 2e répétition)
    if pid_data.get("birth_address"):
        patient.birth_address = pid_data["birth_address"]
    if pid_data.get("birth_city"):
        patient.birth_city = pid_data["birth_city"]
    if pid_data.get("birth_state"):
        patient.birth_state = pid_data["birth_state"]
    if pid_data.get("birth_postal_code"):
        patient.birth_postal_code = pid_data["birth_postal_code"]
    if pid_data.get("birth_country"):
        patient.birth_country = pid_data["birth_country"]
    
    # Téléphones (PID-13) - multi-valué
    if pid_data.get("phone"):
        patient.phone = pid_data["phone"]
    if pid_data.get("mobile"):
        patient.mobile = pid_data["mobile"]
    if pid_data.get("work_phone"):
        patient.work_phone = pid_data["work_phone"]
    
    # Email
    if pid_data.get("email"):
        patient.email = pid_data["email"]
    
    # Statut marital (PID-16)
    if pid_data.get("marital_status"):
        patient.marital_status = pid_data["marital_status"]
    
    # PID-23: Lieu de naissance
    if pid_data.get("birth_place"):
        # Si birth_city pas déjà renseigné, utiliser birth_place
        if not patient.birth_city:
            patient.birth_city = pid_data["birth_place"]
    
    # PID-32: Identity Reliability Code
    if pid_data.get("identity_reliability_code"):
        patient.identity_reliability_code = pid_data["identity_reliability_code"]
    
    # SSN / NIR
    if pid_data.get("ssn"):
        patient.ssn = pid_data["ssn"]
    
    # Account number (PID-18) - stocké dans external_id si vide
    if pid_data.get("account_number") and not patient.external_id:
        patient.external_id = pid_data["account_number"]
    
    return patient


def create_patient_from_pid_data(
    pid_data: Dict,
    session: Session,
    identifier: Optional[str] = None,
    external_id: Optional[str] = None,
    ej_id: Optional[int] = None
) -> Patient:
    """
    Crée un nouveau Patient depuis les données PID parsées.
    
    Args:
        pid_data: Dict retourné par _parse_pid()
        session: Session DB
        identifier: Identifiant principal (si None, extrait de pid_data)
        external_id: ID externe (si None, extrait de pid_data)
        ej_id: ID de l'Entité Juridique pour classification des namespaces
    
    Returns:
        Nouveau Patient (non encore ajouté à la session)
    """
    from app.db import get_next_sequence
    from app.services.identifier_namespace_classifier import classify_incoming_identifiers
    from app.models_identifiers import IdentifierType
    
    # Si identifier et external_id sont fournis explicitement, les utiliser
    if identifier is not None and external_id is not None:
        # Récupérer le contexte GHT depuis l'EJ si fournie
        ght_context_id = None
        if ej_id:
            from app.models_structure import EntiteJuridique
            ej = session.get(EntiteJuridique, ej_id)
            if ej:
                ght_context_id = ej.ght_context_id
        
        patient = Patient(
            patient_seq=get_next_sequence(session, "patient"),
            identifier=identifier,
            external_id=external_id,
            family=pid_data.get("family") or "",
            given=pid_data.get("given") or "",
            ght_context_id=ght_context_id,
            entite_juridique_id=ej_id
        )
        
        # Mettre à jour tous les autres champs via la fonction commune
        update_patient_from_pid_data(patient, pid_data, session, create_mode=True)
        return patient
    
    # Sinon, classifier les identifiants selon les namespaces EJ
    identifiers_data = pid_data.get("identifiers", [])
    
    # Convertir les données d'identifiants pour le classifier
    classifier_input = []
    for cx_value, system, type_code in identifiers_data:
        id_type = map_hl7_type_to_identifier_type(type_code) or IdentifierType.IPP
        
        # Extraire la valeur de l'identifiant du CX
        value = cx_value.split("^")[0] if "^" in cx_value else cx_value
        classifier_input.append((value, system, id_type))
    
    # Classifier les identifiants
    classification = classify_incoming_identifiers(
        session, classifier_input, 'patient', ej_id
    )
    
    # Créer le patient avec les identifiants classifiés
    # Récupérer le contexte GHT depuis l'EJ si fournie
    ght_context_id = None
    if ej_id:
        from app.models_structure import EntiteJuridique
        ej = session.get(EntiteJuridique, ej_id)
        if ej:
            ght_context_id = ej.ght_context_id
    
    patient = Patient(
        patient_seq=get_next_sequence(session, "patient"),
        identifier=classification.get('main_identifier'),
        external_id=classification.get('external_id'),
        family=pid_data.get("family") or "",
        given=pid_data.get("given") or "",
        ght_context_id=ght_context_id,
        entite_juridique_id=ej_id
    )
    
    # Créer les identifiants externes dans la table Identifier
    from app.models_identifiers import Identifier
    for ext_id in classification.get('external_identifiers', []):
        identifier_obj = Identifier(
            value=ext_id['value'],
            system=ext_id['system'],
            type=ext_id['type'],
            status="active"
        )
        identifier_obj.patient_id = patient.id  # Sera défini après ajout à la session
        session.add(identifier_obj)
    
    # Mettre à jour tous les autres champs via la fonction commune
    update_patient_from_pid_data(patient, pid_data, session, create_mode=True)
    
    return patient
