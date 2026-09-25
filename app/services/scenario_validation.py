"""Validation de scénarios IHE PAM (plusieurs messages séquentiels).

Ce module valide un scénario complet constitué de plusieurs messages HL7 v2.5
pour un même patient et dossier, en vérifiant :
1. La validité structurelle de chaque message (via pam_validation)
2. La cohérence du workflow de transitions d'état (via state_transitions)
3. La cohérence des identifiants patient/dossier entre messages
4. La chronologie des événements (timestamps)

Usage:
    result = validate_scenario(messages_text, direction="inbound", profile="IHE_PAM_FR")
    print(f"Scénario valide: {result.is_valid}")
    for msg_result in result.messages:
        print(f"Message {msg_result.message_number}: {msg_result.validation.level}")
    for issue in result.workflow_issues:
        print(f"Workflow: {issue.message}")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

from app.services.pam_validation import validate_pam, ValidationResult, ValidationIssue
from app.services.mllp import parse_msh_fields
from app.services.siu import validate_siu
from app.workflows.transitions import IDENTITY_ONLY_TRIGGERS, is_valid_transition, INITIAL_EVENTS


@dataclass
class MessageValidationResult:
    """Résultat de validation d'un message individuel dans le scénario."""
    message_number: int  # Position dans le scénario (1-based)
    message: str  # Message HL7 brut
    validation: ValidationResult  # Validation structurelle (PAM)
    message_type: str  # Type de message (ex: ADT^A01)
    event_code: str  # Code d'événement (ex: A01)
    timestamp: Optional[str] = None  # MSH-7 ou EVN-2
    patient_id: Optional[str] = None  # PID-3.1
    visit_id: Optional[str] = None  # PV1-19.1


@dataclass
class ScenarioValidationResult:
    """Résultat complet de validation d'un scénario."""
    is_valid: bool  # True si tous les messages sont valides ET workflow OK
    level: str  # "ok", "warn", "error"
    messages: List[MessageValidationResult] = field(default_factory=list)
    workflow_issues: List[ValidationIssue] = field(default_factory=list)
    coherence_issues: List[ValidationIssue] = field(default_factory=list)
    
    @property
    def total_messages(self) -> int:
        return len(self.messages)
    
    @property
    def valid_messages(self) -> int:
        return sum(1 for m in self.messages if m.validation.is_valid)
    
    @property
    def total_issues(self) -> int:
        """Nombre total d'issues (messages + workflow + cohérence)."""
        msg_issues = sum(len(m.validation.issues) for m in self.messages)
        return msg_issues + len(self.workflow_issues) + len(self.coherence_issues)


def _split_hl7_lines(message: str) -> List[str]:
    """Découpe un message HL7 v2 en segments.

    Les messages réels (MLLP) séparent leurs segments par \\r (parfois \\r\\n),
    pas par \\n seul. Un split naïf sur "\\n" laisse alors le message entier
    comme une seule "ligne" commençant par MSH, et aucun segment PID/PV1/EVN
    n'est jamais retrouvé par les extracteurs ci-dessous.
    """
    normalized = (
        message.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    return normalized.strip().split("\n")


def _extract_event_code(message: str) -> Optional[str]:
    """Extrait le code d'événement (trigger) depuis MSH-9.2 ou EVN-1."""
    lines = _split_hl7_lines(message)
    
    # Chercher MSH-9.2
    for line in lines:
        if line.startswith("MSH"):
            fields = line.split("|")
            if len(fields) > 9:
                msg_type = fields[8]  # MSH-9
                components = msg_type.split("^")
                if len(components) > 1:
                    return components[1]  # Trigger (A01, A02, etc.)
    
    # Solution de repli: chercher EVN-1
    for line in lines:
        if line.startswith("EVN"):
            fields = line.split("|")
            if len(fields) > 1:
                return fields[1].strip()
    
    return None


def _extract_patient_id(message: str) -> Optional[str]:
    """Extrait l'identifiant patient depuis PID-3.1."""
    lines = _split_hl7_lines(message)
    for line in lines:
        if line.startswith("PID"):
            fields = line.split("|")
            if len(fields) > 3:
                pid_3 = fields[3]  # PID-3
                # Format: 123456^^^HOSP ou 123456~789^^^OTHER
                components = pid_3.split("^")
                if components:
                    # Prendre le premier identifiant (avant ~)
                    return components[0].split("~")[0].strip()
    return None


def _extract_visit_id(message: str) -> Optional[str]:
    """Extrait l'identifiant de dossier depuis PV1-19.1."""
    lines = _split_hl7_lines(message)
    for line in lines:
        if line.startswith("PV1"):
            fields = line.split("|")
            if len(fields) > 19:
                pv1_19 = fields[19]  # PV1-19
                components = pv1_19.split("^")
                if components:
                    return components[0].strip()
    return None


def _extract_timestamp(message: str) -> Optional[str]:
    """Extrait le timestamp du message (MSH-7 ou EVN-2)."""
    lines = _split_hl7_lines(message)
    
    # Préférer EVN-2 (datetime of event)
    for line in lines:
        if line.startswith("EVN"):
            fields = line.split("|")
            if len(fields) > 2 and fields[2].strip():
                return fields[2].strip()
    
    # Solution de repli: MSH-7 (datetime of message)
    for line in lines:
        if line.startswith("MSH"):
            fields = line.split("|")
            if len(fields) > 7:
                return fields[6].strip()  # MSH-7 (index 6 car MSH-1 = "|")
    
    return None


def _parse_hl7_timestamp(ts: str) -> Optional[datetime]:
    """Parse un timestamp HL7 (YYYYMMDD[HHMM[SS[.S+]]]) vers datetime."""
    if not ts:
        return None
    
    # Nettoyer le timestamp (enlever timezone si présente)
    clean_ts = ts.split("+")[0].split("-")[0]
    
    # Essayer différents formats
    for fmt, length in [
        ("%Y%m%d%H%M%S", 14),
        ("%Y%m%d%H%M", 12),
        ("%Y%m%d", 8),
    ]:
        try:
            return datetime.strptime(clean_ts[:length], fmt)
        except (ValueError, IndexError):
            continue
    
    return None


def validate_scenario(
    messages_text: str,
    direction: str = "inbound",
    profile: str = "IHE_PAM_FR"
) -> ScenarioValidationResult:
    """Valide un scénario complet (plusieurs messages séparés par sauts de ligne).
    
    Args:
        messages_text: Texte contenant plusieurs messages HL7 séparés par des sauts
                      de ligne vides. Chaque message doit commencer par MSH|
        direction: Direction de validation ("inbound" ou "outbound")
        profile: Profil de validation ("IHE_PAM_FR" ou "IHE_PAM")
    
    Returns:
        ScenarioValidationResult avec validation de chaque message + workflow
    """
    result = ScenarioValidationResult(is_valid=True, level="ok")
    
    # Séparer les messages (on cherche les MSH|)
    raw_messages = []
    current_message = []
    
    normalized_messages_text = (
        messages_text.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    for line in normalized_messages_text.split("\n"):
        line = line.strip()
        if line.startswith("MSH|"):
            # Début d'un nouveau message
            if current_message:
                raw_messages.append("\n".join(current_message))
            current_message = [line]
        elif line and current_message:
            # Suite du message courant
            current_message.append(line)
    
    # Ajouter le dernier message
    if current_message:
        raw_messages.append("\n".join(current_message))
    
    if not raw_messages:
        result.is_valid = False
        result.level = "error"
        result.coherence_issues.append(
            ValidationIssue(
                code="SCENARIO_EMPTY",
                message="Aucun message HL7 trouvé dans le scénario",
                severity="error"
            )
        )
        return result
    
    # Valider chaque message individuellement
    # Un scénario peut couvrir plusieurs entités (p. ex. mère et nouveau-né).
    # L'automate PAM doit donc suivre chaque patient/venue indépendamment.
    previous_events: dict[str, Optional[str]] = {}
    patient_ids = set()
    visit_ids = set()
    timestamps = []
    
    for idx, message in enumerate(raw_messages, start=1):
        # Validation structurelle : SIU est un flux Scheduling HL7 v2 et ne
        # doit pas être validé par les règles IHE PAM/ADT.
        validation = validate_siu(message, direction) if parse_msh_fields(message).get("type") == "SIU" else validate_pam(message, direction, profile)
        
        # Extraction métadonnées
        event_code = _extract_event_code(message)
        patient_id = _extract_patient_id(message)
        visit_id = _extract_visit_id(message)
        timestamp = _extract_timestamp(message)
        
        msg_result = MessageValidationResult(
            message_number=idx,
            message=message,
            validation=validation,
            message_type=validation.message_type or "UNKNOWN",
            event_code=event_code or "UNKNOWN",
            timestamp=timestamp,
            patient_id=patient_id,
            visit_id=visit_id
        )
        result.messages.append(msg_result)
        
        # Agréger les identifiants pour cohérence
        if patient_id:
            patient_ids.add(patient_id)
        if visit_id:
            visit_ids.add(visit_id)
        if timestamp:
            timestamps.append((idx, timestamp))
        
        # Vérifier le workflow de transitions
        if event_code and event_code not in IDENTITY_ONLY_TRIGGERS and not event_code.startswith("S"):
            entity_key = patient_id or visit_id or "__default__"
            previous_event = previous_events.get(entity_key)
            # Premier message : doit être un événement initial
            # Le premier *mouvement* peut être précédé de transactions
            # d'identité (A28/A31/A40/A47) ou de rendez-vous SIU. Celles-ci
            # n'entrent pas dans l'automate PAM des venues.
            if previous_event is None:
                if event_code not in INITIAL_EVENTS:
                    result.workflow_issues.append(
                        ValidationIssue(
                            code="WORKFLOW_INVALID_INITIAL",
                            message=f"Message #{idx} ({event_code}): Premier message doit être un événement initial ({', '.join(sorted(INITIAL_EVENTS))})",
                            severity="error"
                        )
                    )
                    result.is_valid = False
                    result.level = "error"
            # Messages suivants : vérifier la transition
            else:
                if not is_valid_transition(previous_event, event_code):
                    result.workflow_issues.append(
                        ValidationIssue(
                            code="WORKFLOW_INVALID_TRANSITION",
                            message=f"Message #{idx}: Transition invalide {previous_event} -> {event_code}",
                            severity="error"
                        )
                    )
                    result.is_valid = False
                    result.level = "error"
            
            previous_events[entity_key] = event_code
        
        # Agréger le niveau de validation
        if not validation.is_valid:
            result.is_valid = False
            if validation.level == "error":
                result.level = "error"
            elif validation.level == "warn" and result.level != "error":
                result.level = "warn"
    
    # Vérifications de cohérence globale
    
    # 1. Identifiant patient unique
    if len(patient_ids) > 1:
        result.coherence_issues.append(
            ValidationIssue(
                code="SCENARIO_MULTIPLE_PATIENTS",
                message=f"Le scénario contient plusieurs identifiants patient différents: {', '.join(sorted(patient_ids))}. Les séquences sont contrôlées séparément par patient.",
                severity="warn"
            )
        )
    elif len(patient_ids) == 0:
        result.coherence_issues.append(
            ValidationIssue(
                code="SCENARIO_NO_PATIENT",
                message="Aucun identifiant patient trouvé dans le scénario",
                severity="warn"
            )
        )
        if result.level == "ok":
            result.level = "warn"
    
    # 2. Identifiant dossier unique
    if len(visit_ids) > 1:
        result.coherence_issues.append(
            ValidationIssue(
                code="SCENARIO_MULTIPLE_VISITS",
                message=f"Le scénario contient plusieurs identifiants de dossier différents: {', '.join(sorted(visit_ids))}",
                severity="warn"
            )
        )
        if result.level == "ok":
            result.level = "warn"
    
    # 3. Chronologie des timestamps
    parsed_timestamps = []
    for msg_num, ts in timestamps:
        dt = _parse_hl7_timestamp(ts)
        if dt:
            parsed_timestamps.append((msg_num, ts, dt))
    
    for i in range(1, len(parsed_timestamps)):
        prev_num, prev_ts, prev_dt = parsed_timestamps[i-1]
        curr_num, curr_ts, curr_dt = parsed_timestamps[i]
        if curr_dt < prev_dt:
            result.coherence_issues.append(
                ValidationIssue(
                    code="SCENARIO_TIMESTAMP_ORDER",
                    message=f"Message #{curr_num} ({curr_ts}) a un timestamp antérieur au message #{prev_num} ({prev_ts})",
                    severity="warn"
                )
            )
            if result.level == "ok":
                result.level = "warn"
    
    return result
