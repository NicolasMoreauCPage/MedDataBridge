from typing import List
from dataclasses import asdict
from app.services.pam_validation import ValidationIssue

# Mapping code -> French message template. Use {detail} for contextual parts.
MESSAGES_FR = {
    "STRUCTURE": "Message invalide : segment MSH manquant",
    "MSH_PARSE": "Impossible d'analyser le segment MSH",
    "MSH1_INVALID": "Séparateur MSH-1 invalide (doit être '|')",
    "MSH2_NONSTANDARD": "MSH-2 (caractères d'encodage) non standard",
    "MSH9_FORMAT": "Format MSH-9 invalide (devrait être type^trigger[^structure])",
    "MSH10_EMPTY": "MSH-10 (Message Control ID) est requis",
    "EVN_MISSING": "Segment EVN manquant",
    "PID_MISSING": "Segment PID manquant",
    "PID3_EMPTY": "PID-3 (identifiant patient) est requis",
    "ZBE_REF_NOT_FOUND": "ZBE référence un mouvement introuvable en base",
    "ZBE_REF_ALREADY_CANCELLED": "Le mouvement référencé est déjà annulé",
    "ZBE6_TRIGGER_MISMATCH": "ZBE-6 (événement d'origine) ne correspond pas à l'événement du mouvement référencé",
    "TRANSITION_NOT_ALLOWED": "Transition IHE non autorisée selon la politique (événements précédents)",
    "BED_OCCUPIED": "Le lit/chambre demandé(e) semble déjà occupé(e)",
    # Fallbacks
}


def translate_issues_to_fr(issues: List[ValidationIssue]) -> List[ValidationIssue]:
    out = []
    for it in issues:
        code = getattr(it, "code", None)
        msg = getattr(it, "message", "")
        sev = getattr(it, "severity", "error")
        if code and code in MESSAGES_FR:
            fr = MESSAGES_FR[code]
            # If original message contains detail after ':' keep it
            out.append(ValidationIssue(code, fr, severity=sev))
        else:
            # Try minimal translation for common English words
            fr_msg = msg.replace("references movement", "référence le mouvement")
            fr_msg = fr_msg.replace("not found", "introuvable en base")
            fr_msg = fr_msg.replace("already cancelled", "déjà annulé")
            out.append(ValidationIssue(code or "UNKNOWN", fr_msg, severity=sev))
    return out
