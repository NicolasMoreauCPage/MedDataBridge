"""Scanner et parseur de scénarios IHE PAM depuis fichiers existants.

Analyse les fichiers XML / HL7 dans Doc/interfaces.integration_src/ et crée
des ScenarioTemplate réutilisables.
"""
import re
from pathlib import Path
from typing import List, Tuple, Optional
from sqlmodel import Session, select

from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep


# Mapping événement HL7 -> semantic_event_code + narrative
HL7_EVENT_MAPPING = {
    "ADT^A28": ("PATIENT_CREATE", "Création identité patient", "lifecycle"),
    "ADT^A31": ("PATIENT_UPDATE", "Mise à jour identité patient", "update"),
    "ADT^A05": ("ADMISSION_PLANNED", "Pré-admission / Admission attendue", "admission"),
    "ADT^A01": ("ADMISSION_CONFIRMED", "Admission confirmée", "admission"),
    "ADT^A02": ("TRANSFER", "Transfert / Mutation", "transfer"),
    "ADT^A03": ("DISCHARGE", "Sortie définitive", "discharge"),
    "ADT^A04": ("ADMISSION_EXTERNAL", "Enregistrement patient externe", "admission"),
    "ADT^A06": ("TRANSFER_OUT_TO_IN", "Changement externe->hospit", "transfer"),
    "ADT^A07": ("TRANSFER_IN_TO_OUT", "Changement hospit->externe", "transfer"),
    "ADT^A08": ("UPDATE_PATIENT_INFO", "Mise à jour informations patient", "update"),
    "ADT^A11": ("CANCEL_ADMISSION", "Annulation admission", "lifecycle"),
    "ADT^A12": ("CANCEL_TRANSFER", "Annulation transfert", "lifecycle"),
    "ADT^A13": ("CANCEL_DISCHARGE", "Annulation sortie", "lifecycle"),
    "ADT^A21": ("LEAVE_OF_ABSENCE_OUT", "Absence temporaire départ", "transfer"),
    "ADT^A22": ("LEAVE_OF_ABSENCE_RETURN", "Retour absence temporaire", "transfer"),
    "ADT^A38": ("CANCEL_PRE_ADMISSION", "Annulation pré-admission", "lifecycle"),
    "ADT^Z99": ("VENUE_UPDATE", "Mise à jour venue (custom)", "update"),
}


def _extract_hl7_events(content: str) -> List[Tuple[str, str]]:
    """Extrait les événements HL7 (type + timestamp) d'un fichier HL7."""
    events = []
    lines = content.split("\n")
    for line in lines:
        if line.startswith("MSH"):
            match = re.search(r"\|ADT\^([A-Z0-9]+)\^", line)
            ts_match = re.search(r"\|\d{14}\|", line)
            if match:
                event_code = f"ADT^{match.group(1)}"
                ts = ts_match.group(0).strip("|") if ts_match else ""
                events.append((event_code, ts))
    return events


def _extract_xml_event_code(xml_content: str) -> Optional[str]:
    """Extrait codeEvenement depuis XML pivot."""
    match = re.search(r"<pivot:codeEvenement>(\w+)</pivot:codeEvenement>", xml_content)
    return match.group(1) if match else None


def _scan_hl7_files(base_dir: Path) -> List[Tuple[Path, List[Tuple[str, str]]]]:
    """Scan tous les fichiers HL7 IHE PAM."""
    results = []
    for fpath in base_dir.rglob("*.hl7"):
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            events = _extract_hl7_events(content)
            if events:
                results.append((fpath, events))
        except Exception:
            pass
    return results


def create_template_from_hl7_file(
    session: Session, file_path: Path, events: List[Tuple[str, str]]
) -> Optional[ScenarioTemplate]:
    """Crée un ScenarioTemplate depuis un fichier HL7 multi-messages."""
    scenario_name = file_path.stem.replace("TestHL7", "").replace("_", " ").strip()
    key = f"ihe.{file_path.stem.lower()}"
    
    existing = session.exec(select(ScenarioTemplate).where(ScenarioTemplate.key == key)).first()
    if existing:
        return existing
    
    template = ScenarioTemplate(
        key=key,
        name=f"IHE PAM - {scenario_name}",
        description=f"Scénario IHE PAM extrait depuis {file_path.name}",
        category="IHE",
        protocols_supported="HL7v2,FHIR",
        tags="pam,extracted",
    )
    session.add(template)
    session.flush()
    
    order_index = 1
    for hl7_event, ts in events:
        mapping = HL7_EVENT_MAPPING.get(hl7_event)
        if not mapping:
            continue
        semantic_code, narrative, role = mapping
        step = ScenarioTemplateStep(
            template_id=template.id,
            order_index=order_index,
            semantic_event_code=semantic_code,
            narrative=narrative,
            hl7_event_code=hl7_event,
            message_role=role,
        )
        session.add(step)
        order_index += 1
    
    session.commit()
    session.refresh(template)
    return template


def import_all_ihe_pam_scenarios(session: Session, base_dir: Path) -> List[ScenarioTemplate]:
    """Importe tous les scénarios IHE PAM trouvés."""
    templates: List[ScenarioTemplate] = []
    hl7_files = _scan_hl7_files(base_dir)
    for fpath, events in hl7_files:
        template = create_template_from_hl7_file(session, fpath, events)
        if template:
            templates.append(template)
    return templates
