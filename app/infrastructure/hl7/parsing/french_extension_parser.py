"""Parsing des segments d'extension nationale française IHE PAM non couverts ailleurs :
ZFD (complément démographique), ZFA (statut DMP/Espace Santé), ZFP (situation
professionnelle), ZFV (compléments sur la rencontre), et ROL (rôle praticien, standard
HL7 mais profilé par l'extension France pour ODRP/SUBS notamment).

Référence : docs/SpecIHEPAM/Publication-IHE_FRANCE_PAM_National_Extension_v2.11.1.txt,
sections 6.8 (ROL), 6.14 (ZFA), 6.15 (ZFP), 6.16 (ZFV), 6.18 (ZFD).

Ces segments sont fréquents dans les flux réels (ZFD ~55%, ROL ~38%, ZFP ~26%, ZFV ~16%,
ZFA ~12% des messages IHE PAM France observés en production) mais n'étaient parsés nulle
part dans le code avant l'ajout de ce module.
"""
import re
from typing import List, Optional

import logging

logger = logging.getLogger(__name__)


def _segment_lines(message: str, seg_id: str) -> List[str]:
    lines = re.split(r"\r|\n", message)
    return [line for line in lines if line.startswith(seg_id)]


def parse_zfd(message: str) -> Optional[dict]:
    """Parse le segment ZFD (Complément démographique).

    Champs : ZFD-3 consentement SMS, ZFD-4 indicateur date de naissance modifiée,
    ZFD-5 mode d'obtention de l'identité, ZFD-6 date interrogation INSi,
    ZFD-7 justificatif d'identité, ZFD-8 date de fin de validité du justificatif.
    """
    lines = _segment_lines(message, "ZFD")
    if not lines:
        return None
    parts = lines[0].split("|")
    out = {
        "sms_consent": None,
        "birth_date_modified_indicator": None,
        "identity_capture_mode": None,
        "ins_last_query_date": None,
        "identity_proof_type": None,
        "identity_proof_expiry_date": None,
    }
    try:
        if len(parts) > 3 and parts[3]:
            out["sms_consent"] = parts[3].strip().upper()
        if len(parts) > 4 and parts[4]:
            out["birth_date_modified_indicator"] = parts[4].strip().upper()
        if len(parts) > 5 and parts[5]:
            out["identity_capture_mode"] = parts[5].strip().upper()
        if len(parts) > 6 and parts[6]:
            out["ins_last_query_date"] = parts[6].strip()
        if len(parts) > 7 and parts[7]:
            out["identity_proof_type"] = parts[7].strip().upper()
        if len(parts) > 8 and parts[8]:
            out["identity_proof_expiry_date"] = parts[8].strip()
    except Exception as e:
        logger.error(f"Error parsing ZFD segment: {e}")
    return out


def parse_zfa(message: str) -> Optional[dict]:
    """Parse le segment ZFA (Statut DMP / Espace Santé du patient).

    ZFA-4 à ZFA-8 sont obsolètes dans la version courante du profil (accès
    établissement au DMP) et ne sont pas extraits.
    """
    lines = _segment_lines(message, "ZFA")
    if not lines:
        return None
    parts = lines[0].split("|")
    out = {
        "dmp_status": None,
        "dmp_status_date": None,
        "dmp_closure_date": None,
        "dmp_feed_opposition": None,
        "dmp_consultation_consent": None,
    }
    try:
        if len(parts) > 1 and parts[1]:
            out["dmp_status"] = parts[1].strip().upper()
        if len(parts) > 2 and parts[2]:
            out["dmp_status_date"] = parts[2].strip()
        if len(parts) > 3 and parts[3]:
            out["dmp_closure_date"] = parts[3].strip()
        if len(parts) > 9 and parts[9]:
            out["dmp_feed_opposition"] = parts[9].split("^")[0].strip().upper()
        if len(parts) > 11 and parts[11]:
            out["dmp_consultation_consent"] = parts[11].split("^")[0].strip().upper()
    except Exception as e:
        logger.error(f"Error parsing ZFA segment: {e}")
    return out


def parse_zfp(message: str) -> Optional[dict]:
    """Parse le segment ZFP (Situation professionnelle, nomenclature INSEE)."""
    lines = _segment_lines(message, "ZFP")
    if not lines:
        return None
    parts = lines[0].split("|")
    out = {
        "socio_professional_activity": None,
        "socio_professional_category": None,
    }
    try:
        if len(parts) > 1 and parts[1]:
            out["socio_professional_activity"] = parts[1].strip()
        if len(parts) > 2 and parts[2]:
            out["socio_professional_category"] = parts[2].strip()
    except Exception as e:
        logger.error(f"Error parsing ZFP segment: {e}")
    return out


def parse_zfv(message: str) -> Optional[dict]:
    """Parse le segment ZFV (Compléments sur la rencontre).

    ZFV-3 est interdit par le profil (utiliser PV1-2/4/21) et n'est pas extrait.
    ZFV-6/7/8/9 (adresses de provenance, NDA provenance, archives, sortie personnalisée)
    sont hors du périmètre initial de ce parseur — champs les plus fréquemment utiles
    (origine, transport, mode légal de soin RIM-P) couverts en priorité.
    """
    lines = _segment_lines(message, "ZFV")
    if not lines:
        return None
    parts = lines[0].split("|")
    out = {
        "origin_facility_finess": None,
        "origin_stay_date": None,
        "discharge_transport_mode": None,
        "legal_care_mode_code": None,
        "transport_care_level": None,
    }
    try:
        if len(parts) > 1 and parts[1]:
            dld_comps = parts[1].split("^")
            out["origin_facility_finess"] = dld_comps[0] if dld_comps and dld_comps[0] else None
            if len(dld_comps) > 1 and dld_comps[1]:
                out["origin_stay_date"] = dld_comps[1]
        if len(parts) > 2 and parts[2]:
            out["discharge_transport_mode"] = parts[2].split("^")[0].strip().upper()
        if len(parts) > 10 and parts[10]:
            out["legal_care_mode_code"] = parts[10].split("^")[0].strip().upper()
        if len(parts) > 11 and parts[11]:
            out["transport_care_level"] = parts[11].split("^")[0].strip().upper()
    except Exception as e:
        logger.error(f"Error parsing ZFV segment: {e}")
    return out


# ROL-3 (HL70443, étendu IHE France) : rôles reconnus.
ROL_ROLE_ODRP = "ODRP"  # Officiellement Déclaré médecin Référent/traitant Patient (ajout FR)
ROL_ROLE_SUBSTITUTE = "SUBS"  # Remplaçant du médecin traitant (ajout FR)
ROL_ROLE_ATTENDING = "AT"
ROL_ROLE_ADMITTING = "AD"


def parse_rol_segments(message: str) -> List[dict]:
    """Parse tous les segments ROL du message (répétable au niveau message).

    Retourne une liste de dicts : action_code (ROL-2), role_code (ROL-3),
    et l'identité du praticien extraite de ROL-4 (XCN) : id, family_name, given_name,
    middle_name, prefix, suffix, id_type_code (ex: RPPS/ADELI en composant 9/13 XCN).
    """
    results = []
    for line in _segment_lines(message, "ROL"):
        parts = line.split("|")
        entry = {
            "action_code": None,
            "role_code": None,
            "practitioner_id": None,
            "family_name": None,
            "given_name": None,
            "middle_name": None,
            "prefix": None,
            "suffix": None,
            "id_type_code": None,
        }
        try:
            if len(parts) > 2 and parts[2]:
                entry["action_code"] = parts[2].strip().upper()
            if len(parts) > 3 and parts[3]:
                entry["role_code"] = parts[3].split("^")[0].strip().upper()
            if len(parts) > 4 and parts[4]:
                # ROL-4 is repeatable (XCN~XCN~...) — le même praticien peut être
                # identifié plusieurs fois avec des jeux d'identifiants différents
                # (ADELI, RPPS...). On préfère la répétition RPPS (identifiant
                # national moderne) si présente, sinon la première répétition.
                reps = [r.split("^") for r in parts[4].split("~") if r]
                chosen = next(
                    (r for r in reps if len(r) > 12 and r[12] and r[12].strip().upper() == "RPPS"),
                    reps[0] if reps else [],
                )
                entry["practitioner_id"] = chosen[0] if len(chosen) > 0 and chosen[0] else None
                entry["family_name"] = chosen[1] if len(chosen) > 1 and chosen[1] else None
                entry["given_name"] = chosen[2] if len(chosen) > 2 and chosen[2] else None
                entry["middle_name"] = chosen[3] if len(chosen) > 3 and chosen[3] else None
                entry["suffix"] = chosen[4] if len(chosen) > 4 and chosen[4] else None
                entry["prefix"] = chosen[5] if len(chosen) > 5 and chosen[5] else None
                if len(chosen) > 12 and chosen[12]:
                    entry["id_type_code"] = chosen[12].strip().upper()
        except Exception as e:
            logger.error(f"Error parsing ROL segment: {e}")
            continue
        results.append(entry)
    return results
