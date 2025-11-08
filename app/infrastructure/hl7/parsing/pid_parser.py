"""PID segment parsing for HL7v2.

This module handles parsing of Patient Identification (PID) segments,
including support for multi-valued fields (names, addresses, phones) per HL7v2.5.
"""

from datetime import datetime
import re
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def parse_patient_identifiers(pid_segment: str) -> List[Tuple[str, str]]:
    """Parse patient identifiers from PID segment.
    
    Args:
        pid_segment: Complete PID segment string
        
    Returns:
        List of (cx_value, identifier_type) tuples
    """
    identifiers = []
    try:
        parts = pid_segment.split("|")
        if len(parts) <= 3:
            return []
            
        # PID-3 contains list of identifiers separated by ~
        id_list = parts[3].split("~")
        for cx in id_list:
            if not cx:
                continue
            # Detect identifier type
            id_type = "PI"  # Default: Patient Internal
            if "^" in cx:
                cx_parts = cx.split("^")
                if len(cx_parts) > 4:
                    id_type = cx_parts[4]
            identifiers.append((cx, id_type))
            
    except Exception as e:
        logger.error(f"Error parsing patient identifiers from PID: {str(e)}")
        
    return identifiers


def parse_pid(message: str) -> dict:
    """Parse PID segment with full identifier support.
    
    Extracts patient demographics including:
    - Multiple identifiers (PID-3)
    - Multiple names (PID-5) with type codes (L=legal, D=usual)
    - Multiple addresses (PID-11) with type codes (H=home, O=office)
    - Multiple phones (PID-13) with use codes (HOME, WORK, CELL)
    - Birth date, gender, marital status
    - Birth place and birth family name
    - Identity reliability code (PID-32)
    
    Args:
        message: Complete HL7v2 message
        
    Returns:
        Dictionary with parsed PID fields
    """
    out = {
        "identifiers": [],
        "external_id": None,
        "account_number": None,
        "family": "",
        "given": "",
        "middle": None,
        "prefix": None,
        "suffix": None,
        "birth_date": None,
        "gender": None,
        "address": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "country": None,
        "phone": None,
        "email": None,
        "ssn": None,
        "marital_status": None,
        # Multi-valued fields
        "names": [],
        "addresses": [],
        "phones": [],
        # Birth address fields
        "birth_family": None,
        "birth_address": None,
        "birth_city": None,
        "birth_state": None,
        "birth_postal_code": None,
        "birth_country": None,
        "birth_place": None,
        # Additional phones
        "mobile": None,
        "work_phone": None,
        # PID-32: Identity Reliability Code
        "identity_reliability_code": None
    }
    
    try:
        lines = re.split(r"\r|\n", message)
        pid = next((l for l in lines if l.startswith("PID")), None)
        if not pid:
            return out
            
        parts = pid.split("|")
        
        # Identifiers (PID-3)
        out["identifiers"] = parse_patient_identifiers(pid)
        
        # Name (PID-5) - XPN multi-valued (repetitions ~)
        if len(parts) > 5 and parts[5]:
            # Parse all name repetitions
            name_repetitions = parts[5].split("~")
            all_names = []
            for name_rep in name_repetitions:
                name_parts = name_rep.split("^")
                name_data = {
                    "family": name_parts[0] if len(name_parts) > 0 else "",
                    "given": name_parts[1] if len(name_parts) > 1 else "",
                    "middle": name_parts[2] if len(name_parts) > 2 else None,
                    "suffix": name_parts[3] if len(name_parts) > 3 else None,
                    "prefix": name_parts[4] if len(name_parts) > 4 else None,
                    # XPN: family^given^middle^suffix^prefix^degree^type
                    "type": name_parts[6] if len(name_parts) > 6 else None  # D=usual, L=legal
                }
                all_names.append(name_data)
            
            # Store all repetitions
            out["names"] = all_names
            
            # For compatibility, keep first name in simple fields
            if all_names:
                out["family"] = all_names[0]["family"]
                out["given"] = all_names[0]["given"]
                out["middle"] = all_names[0]["middle"]
                out["prefix"] = all_names[0]["prefix"]
                out["suffix"] = all_names[0]["suffix"]
                
                # Look for legal name (type L) if present
                birth_name = next((n for n in all_names if n.get("type") == "L"), None)
                if birth_name:
                    out["birth_family"] = birth_name["family"]
                
        # Birth date (PID-7)
        if len(parts) > 7 and parts[7]:
            # Keep raw HL7 date string and provide parsed datetime
            out["birth_date"] = parts[7]
            try:
                out["birth_date_dt"] = datetime.strptime(parts[7], "%Y%m%d")
            except Exception:
                out["birth_date_dt"] = None

        # External id: first CX in PID-3 (raw value before component separators)
        if len(parts) > 3 and parts[3]:
            out["external_id"] = parts[3].split("^")[0]

        # Gender (PID-8)
        if len(parts) > 8:
            out["gender"] = parts[8]
            
        # Address (PID-11) - XAD multi-valued (repetitions ~)
        if len(parts) > 11 and parts[11]:
            # Parse all address repetitions
            addr_repetitions = parts[11].split("~")
            all_addresses = []
            for addr_rep in addr_repetitions:
                addr_parts = addr_rep.split("^")
                addr_data = {
                    "street": addr_parts[0] if len(addr_parts) > 0 else None,
                    "other": addr_parts[1] if len(addr_parts) > 1 else None,
                    "city": addr_parts[2] if len(addr_parts) > 2 else None,
                    "state": addr_parts[3] if len(addr_parts) > 3 else None,
                    "postal_code": addr_parts[4] if len(addr_parts) > 4 else None,
                    "country": addr_parts[5] if len(addr_parts) > 5 else None,
                    "type": addr_parts[6] if len(addr_parts) > 6 else None  # H=home, O=office
                }
                all_addresses.append(addr_data)
            
            # Store all repetitions
            out["addresses"] = all_addresses
            
            # For compatibility, keep first address in simple fields
            if all_addresses:
                out["address"] = all_addresses[0]["street"]
                out["city"] = all_addresses[0]["city"]
                out["state"] = all_addresses[0]["state"]
                out["postal_code"] = all_addresses[0]["postal_code"]
                out["country"] = all_addresses[0].get("country")
                
                # If 2nd address present, treat as birth address
                if len(all_addresses) > 1:
                    birth_addr = all_addresses[1]
                    out["birth_address"] = birth_addr["street"]
                    out["birth_city"] = birth_addr["city"]
                    out["birth_state"] = birth_addr["state"]
                    out["birth_postal_code"] = birth_addr["postal_code"]
                    out["birth_country"] = birth_addr.get("country")
            
        # Phone (PID-13) - XTN multi-valued (repetitions ~)
        if len(parts) > 13 and parts[13]:
            # Parse all phone repetitions
            phone_repetitions = parts[13].split("~")
            all_phones = []
            for phone_rep in phone_repetitions:
                phone_parts = phone_rep.split("^")
                phone_data = {
                    "number": phone_parts[0] if len(phone_parts) > 0 else None,
                    "type": phone_parts[2] if len(phone_parts) > 2 else None,  # PRN=primary, ORN=other
                    "use": phone_parts[1] if len(phone_parts) > 1 else None   # HOME, WORK, CELL
                }
                all_phones.append(phone_data)
            
            # Store all repetitions
            out["phones"] = all_phones
            
            # For compatibility, keep first phone in simple field
            if all_phones:
                out["phone"] = all_phones[0]["number"]
                
                # Store additional phones in dedicated fields
                for phone_data in all_phones[1:]:
                    if phone_data.get("use") == "CELL" or phone_data.get("type") == "CP":
                        out["mobile"] = phone_data["number"]
                    elif phone_data.get("use") == "WORK" or phone_data.get("type") == "WP":
                        out["work_phone"] = phone_data["number"]
            
        # Marital status (PID-16)
        if len(parts) > 16 and parts[16]:
            out["marital_status"] = parts[16]
        
        # Account number (PID-18) - often references dossier
        if len(parts) > 18 and parts[18]:
            out["account_number"] = parts[18]
        
        # Birth place (PID-23)
        if len(parts) > 23 and parts[23]:
            out["birth_place"] = parts[23]
            # Use as birth_city if not already set by address
            if not out.get("birth_city"):
                out["birth_city"] = parts[23]
        
        # Identity Reliability Code (PID-32) - HL7 Table 0445
        if len(parts) > 32 and parts[32]:
            out["identity_reliability_code"] = parts[32]
            
    except Exception as e:
        logger.error(f"Error parsing PID segment: {str(e)}")
        
    return out


def parse_pd1(message: str) -> dict:
    """Parse PD1 segment for patient demographics.
    
    PD1 is optional and extends PID with additional fields.
    
    Args:
        message: Complete HL7v2 message
        
    Returns:
        Dictionary with keys: primary_care_provider, religion, language
    """
    out = {"primary_care_provider": None, "religion": None, "language": None}
    try:
        lines = re.split(r"\r|\n", message)
        pd1 = next((l for l in lines if l.startswith("PD1")), None)
        if not pd1:
            return out
        parts = pd1.split("|")
        # PD1-3 = patient primary care provider
        if len(parts) > 3 and parts[3]:
            out["primary_care_provider"] = parts[3].split("^")[0]
        # PD1-4 = religion
        if len(parts) > 4 and parts[4]:
            out["religion"] = parts[4]
        # PD1-6 = language
        if len(parts) > 6 and parts[6]:
            out["language"] = parts[6]
    except Exception:
        pass
    return out
