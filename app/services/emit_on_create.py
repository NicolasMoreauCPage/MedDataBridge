import asyncio
import json
from typing import Literal, Sequence, Tuple

from sqlmodel import Session, select

from app.models import Patient, Dossier, Venue, Mouvement
from app.models_endpoints import SystemEndpoint, MessageLog, FHIRConfig
from app.models_identifiers import Identifier, IdentifierType
from app.services.fhir import generate_fhir_bundle_for_dossier
from app.services.fhir_resources import generate_fhir_bundle_for_entity
from app.services.fhir_transport import post_fhir_bundle as send_fhir
from app.services.mllp import send_mllp
from app.services.pam_validation import validate_pam
import json

# Global sanitization helper: coerce None / 'None' / whitespace-only to ''
def _c(val):
    if val is None:
        return ""
    if isinstance(val, str):
        v = val.strip()
        if v.lower() == "none" or v == "":
            return ""
        return v
    return str(val)


def build_pid3_identifiers(
    patient: Patient,
    session: Session,
    forced_system: str | None = None,
    forced_oid: str | None = None,
) -> str:
    """
    Construit PID-3 avec TOUS les identifiants du patient (répétitions avec ~).
    
    Format HL7 v2.5 PID-3: ID1^^^SYSTEM1^TYPE~ID2^^^SYSTEM2^TYPE~...
    
    Ordre des identifiants:
    1. IPP (patient_seq) - identifiant interne principal
    2. External ID si présent
    3. NIR (Sécurité sociale) si présent
    4. Tous les autres identifiants actifs de la table Identifier
    
    Args:
        patient: Instance Patient
        session: Session DB pour requêter les Identifier
        forced_system: Système forcé pour IPP (si None, utilise "HOSP")
    
    Returns:
        String PID-3 avec répétitions ~ entre identifiants
    
    Exemple:
        "1001^^^HOSP^PI~EXT123^^^EXTERNAL_SYS^PI~1234567890123^^^INS-NIR^NH"
    """
    def _auth(system: str | None, oid: str | None) -> str:
        system = (system or "").strip()
        oid = (oid or "").strip()
        return f"{system}&{oid}&ISO" if system and oid else system

    identifiers = []
    
    # 1. IPP (patient_seq) - générer si absent pour éviter 'None'
    # 1. IPP (patient_seq) - si absent ne pas persister, utiliser fallback éphémère pour PID-3
    ipp_value = getattr(patient, "patient_seq", None)
    if not ipp_value:
        ipp_value = patient.id or "TEMP"
    system = forced_system or "HOSP"
    identifiers.append(f"{_c(ipp_value)}^^^{_auth(system, forced_oid)}^PI")
    
    # 2. External ID si présent - chercher dans Identifier pour avoir system/oid
    external_id_clean = _c(getattr(patient, "external_id", None))
    if external_id_clean:  # Only add if not empty after sanitization
        # Chercher si cet external_id est dans la table Identifier
        ext_ident = session.exec(
            select(Identifier)
            .where(Identifier.patient_id == patient.id)
            .where(Identifier.value == external_id_clean)
            .where(Identifier.status == "active")
        ).first()
        
        if ext_ident:
            # Utiliser system/oid/type de l'Identifier
            identifiers.append(
                f"{_c(ext_ident.value)}^^^{_auth(ext_ident.system, ext_ident.oid)}^{getattr(ext_ident.type, 'value', ext_ident.type)}"
            )
        else:
            # Fallback: external_id sans système connu
            identifiers.append(f"{external_id_clean}^^^{_auth('EXTERNAL', None)}^PI")
    
    # 3. NIR (Sécurité sociale) si présent
    nir_clean = _c(getattr(patient, "nir", None))
    if nir_clean:  # Only add if not empty after sanitization
        # NH = National Health ID (HL7 Table 0203)
        identifiers.append(f"{nir_clean}^^^INS-NIR^NH")
    
    # 4. Tous les autres identifiants actifs
    # Exclure ceux déjà ajoutés (patient_seq, external_id, nir)
    already_added_values = set()
    if patient.patient_seq:
        already_added_values.add(str(patient.patient_seq))
    if patient.external_id:
        already_added_values.add(patient.external_id)
    if patient.nir:
        already_added_values.add(patient.nir)
    
    # Charger explicitement les identifiers si pas encore chargés
    if not patient.identifiers:
        patient.identifiers = session.exec(
            select(Identifier).where(Identifier.patient_id == patient.id)
        ).all()
    
    for ident in patient.identifiers:
        if ident.status == "active" and ident.value not in already_added_values:
            # Format: value^^^system^type
            # Si OID présent, on pourrait l'ajouter: value^^^system&OID&ISO^type
            identifiers.append(
                f"{_c(ident.value)}^^^{_auth(ident.system, ident.oid)}^{getattr(ident.type, 'value', ident.type)}"
            )
            already_added_values.add(_c(ident.value))
    
    # Joindre avec ~ (répétition HL7)
    return "~".join(identifiers) if identifiers else ""


def generate_pam_hl7(
    entity,
    entity_type: Literal["patient", "dossier", "venue", "mouvement"],
    session: Session,
    forced_identifier_system: str | None = None,
    forced_identifier_oid: str | None = None,
    operation: str = "insert",
) -> str:
    """Build a minimal HL7 PAM message for the given entity type."""
    if entity_type == "patient":
        # Local helper to coerce any None / 'None' / whitespace-only values to ''
        def _c(val):  # c = clean / coerce
            if val is None:
                return ""
            # Some legacy data may literally contain the string 'None'
            if isinstance(val, str):
                v = val.strip()
                if v.lower() == "none" or v == "":
                    return ""
                return v
            return str(val)
        # Determine event type based on operation
        if operation == "update":
            event_type = "A31"  # ADT^A31 (Update person information)
        else:
            event_type = "A04"  # ADT^A04 (Register patient) - new patient created
        
        # Build timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        control_id = str(getattr(entity, "patient_seq", getattr(entity, "id", "UNKNOWN")))
        
        # MSH segment avec structure de message et version IHE PAM France
        # MSH-8-3: structure (ADT_A01 pour A04, ADT_A31 pour A31)
        msg_structure = "ADT_A01" if event_type == "A04" else f"ADT_{event_type}"
        # MSH-9: ADT^{event_type}^{structure}
        # MSH-11: 2.5^FRA^2.11 (version IHE PAM France 2.11)
        # MSH-16: FRA (pays)
        # MSH-17: 8859/1 (encodage ISO-8859-1)
        msh = f"MSH|^~\\&|POC|HOSP|EXT|HOSP|{timestamp}||ADT^{event_type}^{msg_structure}|{control_id}|P|2.5^FRA^2.11|||||||FRA|8859/1"
        
        # EVN segment
        evn = f"EVN|{event_type}|{timestamp}"
        
        # PID segment - avec identifiants multiples et PID-32
        # PID-3: Identifiants patient (répétitions ~)
        pid3 = build_pid3_identifiers(
            entity,
            session,
            forced_system=forced_identifier_system,
            forced_oid=forced_identifier_oid,
        )
        
        # PID-5: Noms du patient (XPN, multi-valué)
        # Répétition 1 : nom usuel, Répétition 2 : nom de naissance (si différent)
        names = []
        family = _c(getattr(entity, "family", ""))
        given = _c(getattr(entity, "given", ""))
        middle = _c(getattr(entity, "middle", ""))
        # Nom usuel (usage D)
        name_usuel = f"{family}^{given}^{middle}^^^^D" if middle else f"{family}^{given}^^^^D"
        names.append(name_usuel)
        # Nom de naissance (usage L) si présent et différent
        birth_family = _c(getattr(entity, "birth_family", None)) or None
        if birth_family and birth_family != family:
            name_naissance = f"{birth_family}^{given}^{middle}^^^^L" if middle else f"{birth_family}^{given}^^^^L"
            names.append(name_naissance)
        name = "~".join(names)
        
        # PID-7: Date de naissance (format HL7: YYYYMMDD)
        birth_date_raw = _c(getattr(entity, "birth_date", ""))
        if birth_date_raw:
            # Convert YYYY-MM-DD to YYYYMMDD
            birth_date = birth_date_raw.replace("-", "").replace("/", "")[:8]
        else:
            birth_date = ""
        
        # PID-8: Sexe administratif
        # Normalisation du sexe administratif HL7 (PID-8)
        raw_gender = _c(getattr(entity, "gender", ""))
        gender_map_hl7 = {
            "m": "M", "male": "M",
            "f": "F", "female": "F",
            "o": "O", "other": "O",
            "u": "U", "unknown": "U", "undifferentiated": "U", "n": "U"
        }
        gender = gender_map_hl7.get(raw_gender.lower(), raw_gender.upper()) if raw_gender else ""
        
        # PID-11: Adresses du patient (XAD, multi-valué)
        addresses = []
        # Adresse d'habitation
        # XAD components: street^other^city^state^zip^country^type
        # HL7 Table 0190 for type (H=Home, B=Business, M=Mailing, P=Permanent...).
        # We set main address as Home (H).
        addr1 = [
            _c(getattr(entity, "address", "")),
            "",  # other designation
            _c(getattr(entity, "city", "")),
            _c(getattr(entity, "state", "")),
            _c(getattr(entity, "postal_code", "")),
            _c(getattr(entity, "country", "")),
            "H",  # address type
        ]
        addresses.append("^".join(addr1))
        # Adresse de naissance (si présente)
        if _c(getattr(entity, "birth_address", None)) or _c(getattr(entity, "birth_city", None)):
            # Not a standard HL7 address type exists for "birth"; use a custom mnemonic BIR.
            addr2 = [
                _c(getattr(entity, "birth_address", "")),
                "",  # other designation
                _c(getattr(entity, "birth_city", "")),
                _c(getattr(entity, "birth_state", "")),
                _c(getattr(entity, "birth_postal_code", "")),
                _c(getattr(entity, "birth_country", "")),
                "BIR",  # custom type for birth address
            ]
            addresses.append("^".join(addr2))
        patient_address = "~".join(addresses)
        
        # PID-13: Téléphones (XTN, multi-valué)
        # Format XTN: [phone]^[use]^[equipment]^[email]^[country]^[area]^[local]^[extension]...
        # Simplified: ^[use]^[equipment]^^^^[local]
        phones = []
        
        # Téléphone principal (domicile)
        phone = _c(getattr(entity, "phone", ""))
        if phone:
            # Format: ^PRN^PH^^^^local_number
            # PRN = Primary Residence Number, PH = Telephone
            phones.append(f"^PRN^PH^^^^{phone}")
        
        # Mobile
        mobile = _c(getattr(entity, "mobile", ""))
        if mobile:
            # Format: ^ORN^CP^^^^local_number
            # ORN = Other Residence Number, CP = Cell Phone
            phones.append(f"^ORN^CP^^^^{mobile}")
        
        # Téléphone professionnel
        work_phone = _c(getattr(entity, "work_phone", ""))
        if work_phone:
            # Format: ^WPN^PH^^^^local_number
            # WPN = Work Number, PH = Telephone
            phones.append(f"^WPN^PH^^^^{work_phone}")
        
        # Email (XTN.4 pour email dans format XTN)
        email = _c(getattr(entity, "email", ""))
        if email:
            # Format: ^^^email_address (XTN.4 = email address)
            # Ou format complet: ^NET^Internet^^^email_address
            phones.append(f"^NET^Internet^{email}")
        
        phone_field = "~".join(phones)
        
        # PID-23: Lieu de naissance (ville)
        birth_place = _c(getattr(entity, "birth_city", ""))
        
        # PID-16: Statut marital (Marital Status) - HL7 Table 0002
        # S=Single, M=Married, D=Divorced, W=Widowed, P=Domestic partner, A=Separated, U=Unknown
        marital_status = _c(getattr(entity, "marital_status", ""))
        
        # PID-26: Nationalité (Citizenship)
        nationality = _c(getattr(entity, "nationality", ""))
        
        # PID-32: Statut de l'identité (Identity Reliability Code) - HL7 Table 0445
        # VALI=Validée (avec INS qualifié), PROV=Provisoire, VIDE=Non qualifiée, 
        # DOUB=Doublon, DESA=Désactivée, DPOT=Dépôt, IDVER=Vérifiée, CACH=Cachée, ANOM=Anonyme
        identity_code = _c(getattr(entity, "identity_reliability_code", ""))
        
        # Construction du segment PID complet HL7 v2.5
        # Format: PID|SetID|PatientID|PatientIDList|AltPatientID|PatientName|MothersMaidenName|
        #            DateOfBirth|Sex|PatientAlias|Race|PatientAddress|CountryCode|PhoneNumber|
        #            BusinessPhone|PrimaryLanguage|MaritalStatus|Religion|AccountNumber|SSN|
        #            DriversLicense|MothersIdentifier|EthnicGroup|BirthPlace|MultipleBirth|
        #            BirthOrder|Citizenship|VeteranStatus|Nationality|PatientDeathDate|DeathIndicator|
        #            IdentityUnknownIndicator|IdentityReliabilityCode
        # PID-1 à PID-13 remplis, PID-14-15 vides (2 pipes), PID-16 marital_status, PID-17-22 vides (6 pipes), PID-23 birth_place, PID-24-25 vides (2 pipes), PID-26 nationality, PID-27-31 vides (5 pipes), PID-32 identity_code
        # Note: chaque champ est séparé par |
        # Après PID-13: || (14,15) | marital (16) | |||||| (17-22) | birth_place (23) | || (24-25) | nationality (26) | ||||| (27-31) | identity (32)
        pid = f"PID|1||{_c(pid3)}||{_c(name)}||{birth_date}|{gender}|||{_c(patient_address)}||{phone_field}|||{marital_status}|||||||{birth_place}|||{nationality}||||||{identity_code}"
        
        return "\r".join([msh, evn, pid])
        
    if entity_type == "dossier":
        # ⚠️ IMPORTANT : La création d'un dossier ne génère PAS de message IHE PAM
        # car il n'y a pas d'événement patient associé. C'est la création de la VENUE
        # (admission/pre-admit) qui générera le message ADT^A05.
        # En FHIR : Dossier = EpisodeOfCare, Venue = Encounter
        return None  # Pas de message généré pour un dossier seul
    
    if entity_type == "venue":
        # ADT^A05 (Pre-admit) pour création de venue
        # La venue correspond à une admission/encounter en IHE PAM
        assigning_system = forced_identifier_system or "HOSP"
        assigning_oid = forced_identifier_oid
        
        # Charger le dossier et le patient
        dossier = entity.dossier if hasattr(entity, "dossier") else None
        patient = dossier.patient if dossier and hasattr(dossier, "patient") else None
        
        if not dossier:
            # Impossible de générer un message sans dossier
            return None
        
        # Patient info
        if patient:
            patient_seq_val = getattr(patient, "patient_seq", None) or (patient.id or "TEMP")
            patient_id = patient.identifier or patient.external_id or str(patient_seq_val)
            family = patient.family or ""
            given = patient.given or ""
            # Gérer birth_date comme string ou date object
            if patient.birth_date:
                if hasattr(patient.birth_date, 'strftime'):
                    birth_date = patient.birth_date.strftime("%Y%m%d")
                else:
                    birth_date = str(patient.birth_date).replace("-", "")
            else:
                birth_date = ""
            # Map HL7 gender codes
            raw_gender = (patient.gender or "").strip()
            gender_map_hl7 = {
                "m": "M", "male": "M",
                "f": "F", "female": "F",
                "o": "O", "other": "O",
                "u": "U", "unknown": "U", "undifferentiated": "U", "n": "U"
            }
            gender = gender_map_hl7.get(raw_gender.lower(), raw_gender.upper()) if raw_gender else ""
        else:
            patient_id = str(dossier.patient_id)
            family = ""
            given = ""
            birth_date = ""
            gender = ""
        
        # Timestamp et identifiants
        admit_time = entity.start_time.strftime("%Y%m%d%H%M%S") if entity.start_time else ""
        control_id = str(entity.venue_seq)
        visit_number = str(dossier.dossier_seq)  # NDA = numéro du dossier
        
        # Authority pour identifiants
        authority = f"{assigning_system}&{assigning_oid}&ISO" if assigning_oid else assigning_system
        pid3 = f"{patient_id}^^^{authority}^PI"
        
        # MSH / EVN avec structure de message et version IHE PAM France
        # MSH-8-3: ADT_A01 (structure pour A05)
        # MSH-11: 2.5^FRA^2.11 (version IHE PAM France 2.11)
        # MSH-16: FRA (pays)
        # MSH-17: 8859/1 (encodage ISO-8859-1)
        msh = f"MSH|^~\\&|POC|HOSP|EXT|HOSP|{admit_time}||ADT^A05^ADT_A01|{control_id}|P|2.5^FRA^2.11|||||||FRA|8859/1"
        evn = f"EVN|A05|{admit_time}"
        
        # PID segment
        pid_fields = [
            "PID", "1", "", pid3, "", f"{family}^{given}", "", birth_date, gender
        ]
        while len(pid_fields) < 19:
            pid_fields.append("")
        pid_fields[18] = visit_number  # PID-18 = Account Number (NDA)
        
        # Enrichir adresse et télécom si patient disponible
        if patient:
            # PID-11: address
            addr = []
            addr.append(patient.address or "")
            addr.append("")  # other designation
            addr.append(patient.city or "")
            addr.append(patient.state or "")
            addr.append(patient.postal_code or "")
            addr.append(patient.country or "")
            addr.append("H")  # type Home
            pid_fields[11] = "^".join(addr)
            
            # PID-13: phones/email (XTN)
            xtn_parts = []
            if getattr(patient, "phone", None):
                xtn_parts.append(f"^PRN^PH^^^^{patient.phone}")
            if getattr(patient, "mobile", None):
                xtn_parts.append(f"^ORN^CP^^^^{patient.mobile}")
            if getattr(patient, "email", None):
                xtn_parts.append(f"^NET^Internet^{patient.email}")
            if xtn_parts:
                pid_fields[13] = "~".join(xtn_parts)
        
        pid = "|".join(pid_fields)
        
        # PV1 segment avec mapping du patient_class via vocabulary
        # Récupérer encounter_class depuis le dossier pour utiliser le mapping
        from app.services.vocabulary_translate import map_code
        
        dossier_type_val = getattr(dossier, "dossier_type", None)
        if hasattr(dossier_type_val, "value"):
            dossier_type_val = dossier_type_val.value
        
        # Le dossier_type correspond à encounter_class dans notre modèle
        # Utiliser le mapping vocabulaire pour obtenir patient_class (PV1-2)
        encounter_class = str(dossier_type_val) if dossier_type_val else "IMP"
        patient_class = map_code(
            session,
            source_system_name="encounter-class",
            source_code=encounter_class,
            target_system_name="patient-class"
        )
        
        # Fallback si pas de mapping trouvé
        if not patient_class:
            patient_class_map = {"hospitalise": "I", "externe": "O", "urgence": "E", "IMP": "I", "AMB": "O", "EMER": "E"}
            patient_class = patient_class_map.get(encounter_class, "I")
        
        location = entity.uf_responsabilite or ""
        admission_type = getattr(dossier, "admission_type", "") or ""
        attending = entity.attending_provider or dossier.attending_provider or ""
        hospital_service = entity.hospital_service or ""
        admit_source = getattr(dossier, "admission_source", "") or ""
        
        pv1 = (
            f"PV1|1|{patient_class}|{location}|{admission_type}|||{attending}|||{hospital_service}||||{admit_source}|||||{visit_number}"
            f"|||||||||||||||||||||||||{admit_time}"
        )
        
        # ZBE segment (mouvement/UF)
        zbe_id = control_id
        action = "INSERT"
        historic = "N"
        original_trigger = "A05"
        zbe = (
            f"ZBE|{zbe_id}|{admit_time}||{action}|{historic}|{original_trigger}|^^^^^^UF^^^{location}"
            if location
            else f"ZBE|{zbe_id}|{admit_time}||{action}|{historic}|{original_trigger}|"
        )
        
        return "\r".join([msh, evn, pid, pv1, zbe])
    if entity_type == "mouvement":
        # Extract event type from mouvement.type (format: "ADT^A01" or "ADT^A01^ADT_A01")
        msg_type = entity.type if entity.type else "ADT^A99"
        
        # Get venue and patient info
        venue = entity.venue if hasattr(entity, 'venue') else None
        dossier = venue.dossier if venue and hasattr(venue, 'dossier') else None
        patient = dossier.patient if dossier and hasattr(dossier, 'patient') else None
        
        # Build timestamp
        timestamp = entity.when.strftime("%Y%m%d%H%M%S") if entity.when else ""
        
        # Build MSH segment avec structure de message et version IHE PAM France
        control_id = str(entity.mouvement_seq)
        # Extract event code (A01, A02, A03, Z99, etc.)
        event_code = msg_type.split("^")[1] if "^" in msg_type else "A99"
        # Determine message structure based on event code
        # A01/A04 = ADT_A01, A02 = ADT_A02, A03 = ADT_A03, Z99 = ADT_A01
        if event_code in ["A01", "A04", "Z99"]:
            msg_structure = "ADT_A01"
        elif event_code == "A02":
            msg_structure = "ADT_A02"
        elif event_code == "A03":
            msg_structure = "ADT_A03"
        else:
            msg_structure = f"ADT_{event_code}"
        
        # MSH-9: ADT^{event_code}^{structure}
        # MSH-11: 2.5^FRA^2.11 (version IHE PAM France 2.11)
        # MSH-16: FRA (pays)
        # MSH-17: 8859/1 (encodage ISO-8859-1)
        msh = f"MSH|^~\\&|POC|HOSP|EXT|HOSP|{timestamp}||ADT^{event_code}^{msg_structure}|{control_id}|P|2.5^FRA^2.11|||||||FRA|8859/1"
        
        # Build EVN segment
        evn = f"EVN|{event_code}|{timestamp}"
        
        # Build PID segment if we have patient info
        if patient:
            assigning_system = forced_identifier_system or "HOSP"
            assigning_oid = forced_identifier_oid
            patient_id = patient.identifier or patient.external_id or str(patient.id)
            authority = f"{assigning_system}&{assigning_oid}&ISO" if assigning_oid else assigning_system
            pid3 = f"{patient_id}^^^{authority}^PI"
            family = patient.family or ""
            given = patient.given or ""
            birth_date = patient.birth_date or ""
            gender = patient.gender or ""
            pid = f"PID|1||{pid3}||{family}^{given}||{birth_date}|{gender}"
        else:
            # If only OID is provided without system, fallback to HOSP system
            authority = (
                f"HOSP&{forced_identifier_oid}&ISO" if forced_identifier_oid else "HOSP"
            )
            pid = f"PID|1||UNKNOWN^^^{authority}^PI||UNKNOWN^UNKNOWN||||"
        
        # Build PV1 segment avec mapping vocabulaire
        from app.services.vocabulary_translate import map_code
        
        # Déterminer encounter_class depuis le dossier pour mapper vers patient_class
        if dossier:
            dossier_type_val = getattr(dossier, "dossier_type", None)
            if hasattr(dossier_type_val, "value"):
                dossier_type_val = dossier_type_val.value
            encounter_class = str(dossier_type_val) if dossier_type_val else "IMP"
            
            # Utiliser le mapping vocabulaire
            patient_class = map_code(
                session,
                source_system_name="encounter-class",
                source_code=encounter_class,
                target_system_name="patient-class"
            )
            
            # Fallback si pas de mapping
            if not patient_class:
                patient_class_map = {"hospitalise": "I", "externe": "O", "urgence": "E", "IMP": "I", "AMB": "O", "EMER": "E"}
                patient_class = patient_class_map.get(encounter_class, "I")
        else:
            patient_class = "I"  # Inpatient by default
        
        location = entity.location or entity.to_location or ""
        if venue:
            uf_resp = venue.uf_responsabilite or ""
        elif dossier:
            uf_resp = dossier.uf_responsabilite or ""
        else:
            uf_resp = ""
        
        # PV1-19 (Visit Number) - use dossier_seq (NDA)
        visit_number = ""
        if dossier:
            visit_number = str(dossier.dossier_seq)
        elif venue:
            visit_number = str(venue.venue_seq)
        
        pv1 = f"PV1|1|{patient_class}|{location}|||||||||||||||{visit_number}||||||||||||||||||||{uf_resp}||||||{timestamp}"
        
        # ZBE segment
        zbe_id = control_id
        action = "UPDATE" if event_code in ["A08", "A31"] else "TRANSFER" if event_code == "A02" else "DISCHARGE" if event_code == "A03" else "INSERT"
        historic = "N"
        zbe = f"ZBE|{zbe_id}|{timestamp}||{action}|{historic}|{event_code}|^^^^^^UF^^^{uf_resp}" if uf_resp else f"ZBE|{zbe_id}|{timestamp}||{action}|{historic}|{event_code}|"
        
        # Combine all segments with \r separator (HL7 standard)
        return "\r".join([msh, evn, pid, pv1, zbe])
    
    return ""


def generate_fhir(
    entity,
    entity_type: Literal["patient", "dossier", "venue", "mouvement"],
    session: Session,
    forced_identifier_system: str | None = None,
    forced_identifier_oid: str | None = None,
):
    """Build a FHIR Bundle for the entity using the new architecture.
    
    Architecture:
    - Patient → Patient resource
    - Dossier → EpisodeOfCare resource
    - Venue → Encounter resource
    - Mouvement → Encounter resource (nested in venue Encounter)
    """
    # Use new FHIR resource generator
    return generate_fhir_bundle_for_entity(entity, entity_type, session)


def _old_generate_fhir_patient_code():
    """OLD CODE - kept for reference but not used."""
    if False:  # entity_type == "patient":
        # Build identifiers with proper systems
        identifiers = []
        
        # 1. IPP (patient_seq) - always include with system
        if entity.patient_seq:
            ipp_system = forced_identifier_system or "http://example.org/fhir/sid/patient-id"
            ipp_identifier = {
                "system": ipp_system,
                "value": str(entity.patient_seq),
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": "PI",
                        "display": "Patient Internal Identifier"
                    }]
                }
            }
            if forced_identifier_oid:
                ipp_identifier["assigner"] = {"identifier": {"value": forced_identifier_oid}}
            identifiers.append(ipp_identifier)
        
        # 2. External ID if present
        external_id_clean = _c(getattr(entity, "external_id", None))
        if external_id_clean:
            identifiers.append({
                "system": "http://example.org/fhir/sid/external-id",
                "value": external_id_clean,
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": "PI"
                    }]
                }
            })
        
        # 3. NIR (Sécurité sociale) if present
        nir_clean = _c(getattr(entity, "nir", None))
        if nir_clean:
            identifiers.append({
                "system": "urn:oid:1.2.250.1.213.1.4.8",  # OID INS-NIR France
                "value": nir_clean,
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": "NH",
                        "display": "National Health Plan Identifier"
                    }]
                }
            })
        
        # 4. SSN if present (legacy field)
        ssn_clean = _c(getattr(entity, "ssn", None))
        if ssn_clean:
            identifiers.append({
                "system": "http://hl7.org/fhir/sid/us-ssn",
                "value": ssn_clean
            })

        # Sanitize name components using global _c helper
        family = _c(getattr(entity, "family", ""))
        given = _c(getattr(entity, "given", ""))
        
        name = {"family": family or None}  # FHIR requires omitting empty values or use null
        if given:
            name["given"] = [given]
        
        middle = _c(getattr(entity, "middle", ""))
        if middle:
            name.setdefault("given", []).append(middle)
        
        prefix = _c(getattr(entity, "prefix", ""))
        if prefix:
            name["prefix"] = [prefix]
        
        suffix = _c(getattr(entity, "suffix", ""))
        if suffix:
            name["suffix"] = [suffix]
        
        # Build list of names (official name + birth name if different)
        names = [name]
        
        # Add birth name (maiden name) if present and different from current family name
        birth_family = _c(getattr(entity, "birth_family", ""))
        if birth_family and birth_family != family:
            birth_name = {"use": "maiden", "family": birth_family}
            if given:
                birth_name["given"] = [given]
            if middle:
                birth_name.setdefault("given", []).append(middle)
            names.append(birth_name)

        # Sanitize other fields
        gender_hl7 = _c(getattr(entity, "gender", ""))
        birth_date = _c(getattr(entity, "birth_date", "")) or None
        
        # Marital status (HL7 Table 0002 to FHIR marital-status value set)
        marital_status_hl7 = _c(getattr(entity, "marital_status", ""))
        marital_status_fhir = None
        if marital_status_hl7:
            # FHIR uses http://terminology.hl7.org/CodeSystem/v3-MaritalStatus
            # HL7 v2 codes map directly: S, M, D, W, etc.
            marital_status_fhir = {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus",
                    "code": marital_status_hl7.upper()
                }]
            }
        
        # Convert HL7 v2 gender codes to FHIR (M→male, F→female, O→other, U→unknown)
        gender_fhir = None
        if gender_hl7:
            gender_map = {
                "M": "male",
                "F": "female",
                "O": "other",
                "U": "unknown",
                "A": "other",  # Ambiguous
                "N": "unknown"  # Not applicable
            }
            gender_fhir = gender_map.get(gender_hl7.upper(), gender_hl7.lower())
        
        patient_res = {
            "resourceType": "Patient",
            "id": str(entity.id),
            "identifier": identifiers,
            "name": names,
        }
        
        # Only include gender/birthDate/maritalStatus if present
        if gender_fhir:
            patient_res["gender"] = gender_fhir
        if birth_date:
            patient_res["birthDate"] = birth_date
        if marital_status_fhir:
            patient_res["maritalStatus"] = marital_status_fhir
        
        # Telecom contacts with proper use and system
        phone = _c(getattr(entity, "phone", ""))
        if phone:
            patient_res.setdefault("telecom", []).append({
                "system": "phone",
                "value": phone,
                "use": "home"
            })
        
        mobile = _c(getattr(entity, "mobile", ""))
        if mobile:
            patient_res.setdefault("telecom", []).append({
                "system": "phone",
                "value": mobile,
                "use": "mobile"
            })
        
        work_phone = _c(getattr(entity, "work_phone", ""))
        if work_phone:
            patient_res.setdefault("telecom", []).append({
                "system": "phone",
                "value": work_phone,
                "use": "work"
            })
        
        email = _c(getattr(entity, "email", ""))
        if email:
            patient_res.setdefault("telecom", []).append({
                "system": "email",
                "value": email
            })
        
        address = _c(getattr(entity, "address", ""))
        city = _c(getattr(entity, "city", ""))
        state = _c(getattr(entity, "state", ""))
        postal = _c(getattr(entity, "postal_code", ""))
        country = _c(getattr(entity, "country", ""))
        
        if address or city:
            addr = {}
            if address:
                addr["line"] = [address]
            if city:
                addr["city"] = city
            if state:
                addr["state"] = state
            if postal:
                addr["postalCode"] = postal
            if country:
                addr["country"] = country
            patient_res.setdefault("address", []).append(addr)
        
        # Primary care provider extension
        pcp = _c(getattr(entity, "primary_care_provider", ""))
        if pcp:
            patient_res.setdefault("extension", []).append(
                {
                    "url": "http://example.org/fhir/StructureDefinition/primary-care-provider",
                    "valueString": pcp,
                }
            )
        
        # Nationality extension (using standard FHIR patient-nationality extension)
        nationality = _c(getattr(entity, "nationality", ""))
        if nationality:
            patient_res.setdefault("extension", []).append({
                "url": "http://hl7.org/fhir/StructureDefinition/patient-nationality",
                "extension": [{
                    "url": "code",
                    "valueCodeableConcept": {
                        "coding": [{
                            "system": "urn:iso:std:iso:3166",
                            "code": nationality
                        }]
                    }
                }]
            })
        
        return patient_res
    # End of old code


def _build_fhir_targets(endpoint: SystemEndpoint) -> Sequence[Tuple[str, str, str | None]]:
    """Return (base_url, auth_kind, auth_token) tuples for an endpoint."""
    targets: list[Tuple[str, str, str | None]] = []

    # Prioritise explicit FHIR configs
    for cfg in getattr(endpoint, "fhir_configs", []) or []:
        if not isinstance(cfg, FHIRConfig):
            continue
        if not cfg.is_enabled or not cfg.base_url:
            continue
        targets.append((cfg.base_url, cfg.auth_kind or "none", cfg.auth_token))

    if targets:
        return targets

    host = (endpoint.host or "").strip()
    if not host:
        return targets

    if host.startswith(("http://", "https://")):
        base_url = host
        if endpoint.port and ":" not in host.split("//", 1)[1]:
            base_url = f"{host}:{endpoint.port}"
    else:
        scheme = "https" if str(endpoint.port) in {"443", "8443"} else "http"
        base_url = f"{scheme}://{host}"
        if endpoint.port:
            base_url = f"{base_url}:{endpoint.port}"

    targets.append((base_url, "none", None))
    return targets


async def emit_to_senders_async(
    entity,
    entity_type: Literal["patient", "dossier", "venue", "mouvement"],
    session: Session,
    operation: str = "insert",
) -> None:
    """Emit HL7/FHIR notifications for newly created or updated entities."""

    endpoints = session.exec(select(SystemEndpoint).where(SystemEndpoint.role == "sender")).all()
    sent_logs: list[MessageLog] = []

    for endpoint in endpoints:
        hl7_message = generate_pam_hl7(
            entity,
            entity_type,
            session,
            forced_identifier_system=getattr(endpoint, "forced_identifier_system", None),
            forced_identifier_oid=getattr(endpoint, "forced_identifier_oid", None),
            operation=operation,
        )
        
        # Generate FHIR payload
        fhir_payload = generate_fhir(
            entity,
            entity_type,
            session,
            forced_identifier_system=getattr(endpoint, "forced_identifier_system", None),
            forced_identifier_oid=getattr(endpoint, "forced_identifier_oid", None),
        )

        if endpoint.kind == "MLLP":
            status = "generated"
            ack_payload = ""
            # Run PAM validation for outbound HL7 and store on log
            try:
                val = validate_pam(hl7_message, direction="out")
                pam_status = val.level
                pam_issues = json.dumps([i.__dict__ for i in val.issues], ensure_ascii=False)
            except Exception:
                pam_status = "warn"
                pam_issues = json.dumps([{"code": "VALIDATOR_ERROR", "message": "Erreur interne du validateur", "severity": "warn"}], ensure_ascii=False)
            try:
                if not endpoint.host or not endpoint.port:
                    raise ValueError("Endpoint MLLP host/port non configuré")
                ack_payload = await send_mllp(endpoint.host, endpoint.port, hl7_message)
                status = "sent"
            except Exception as exc:  # noqa: BLE001 - we want to log the failure
                status = "error"
                ack_payload = str(exc)
            sent_logs.append(
                MessageLog(
                    direction="out",
                    kind="MLLP",
                    endpoint_id=endpoint.id,
                    payload=hl7_message,
                    ack_payload=ack_payload or "",
                    status=status,
                    pam_validation_status=pam_status,
                    pam_validation_issues=pam_issues,
                )
            )
            continue

        if endpoint.kind == "FHIR":
            targets = _build_fhir_targets(endpoint)
            if not targets:
                payload_str = json.dumps(fhir_payload, default=str)
                sent_logs.append(
                    MessageLog(
                        direction="out",
                        kind="FHIR",
                        endpoint_id=endpoint.id,
                        payload=payload_str,
                        ack_payload="Endpoint FHIR non configuré",
                        status="error",
                    )
                )
                continue

            for base_url, auth_kind, auth_token in targets:
                status = "generated"
                ack_payload = ""
                payload_str = json.dumps(fhir_payload, default=str)
                try:
                    status_code, response_body = await send_fhir(
                        base_url, fhir_payload, auth_kind=auth_kind, auth_token=auth_token
                    )
                    status = "sent" if 200 <= status_code < 300 else "error"
                    ack_payload = json.dumps(response_body or {}, default=str)
                except Exception as exc:  # noqa: BLE001
                    status = "error"
                    ack_payload = str(exc)
                sent_logs.append(
                    MessageLog(
                        direction="out",
                        kind="FHIR",
                        endpoint_id=endpoint.id,
                        payload=payload_str,
                        ack_payload=ack_payload,
                        status=status,
                    )
                )
            continue

    if not endpoints:
        # No sender configured: store generated payloads for audit trail.
        hl7_message = generate_pam_hl7(entity, entity_type, session)
        # Validate PAM for audit
        try:
            val = validate_pam(hl7_message, direction="out")
            pam_status = val.level
            pam_issues = json.dumps([i.__dict__ for i in val.issues], ensure_ascii=False)
        except Exception:
            pam_status = "warn"
            pam_issues = json.dumps([{"code": "VALIDATOR_ERROR", "message": "Erreur interne du validateur", "severity": "warn"}], ensure_ascii=False)
        fhir_payload = generate_fhir(entity, entity_type, session)
        sent_logs.append(
            MessageLog(
                direction="out",
                kind="MLLP",
                endpoint_id=None,
                payload=hl7_message,
                ack_payload="",
                status="generated",
                pam_validation_status=pam_status,
                pam_validation_issues=pam_issues,
            )
        )
        sent_logs.append(
            MessageLog(
                direction="out",
                kind="FHIR",
                endpoint_id=None,
                payload=json.dumps(fhir_payload, default=str),
                ack_payload="",
                status="generated",
            )
        )

    for log in sent_logs:
        session.add(log)

    if sent_logs:
        session.commit()


class _EmitToSendersWrapper:
    """Allow emit_to_senders to be used in sync and async contexts."""

    def __init__(self, async_callable):
        self._async = async_callable

    def __call__(self, entity, entity_type, session: Session):
        coro = self._async(entity, entity_type, session)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        else:
            return coro


emit_to_senders = _EmitToSendersWrapper(emit_to_senders_async)

__all__ = ["emit_to_senders", "emit_to_senders_async"]
