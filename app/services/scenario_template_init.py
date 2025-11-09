"""Initialisation des templates de scénarios IHE / Démo.

Ces templates représentent des suites sémantiques d'événements (admission, transferts,
sortie...) indépendantes de tout contexte concret. Ils peuvent être matérialisés
à la volée en InteropScenario + Steps adaptés à un GHT / EJ / Patient.
"""
from pathlib import Path
from typing import List
from sqlmodel import Session, select

from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep

# Dossier contenant les extraits XML de référence (IHE hospitSimple)
HOSPIT_SIMPLE_DIR = Path("Doc/interfaces.integration_src/interfaces.integration/target/classes/data/standalone_nonregr/hospitSimple")

# Mapping fichier -> (semantic_code, hl7_event, message_role, narrative)
HOSPIT_SIMPLE_SEQUENCE = [
    ("01_createParcours.xml", "PARCOURS_START", None, "lifecycle", "Début de parcours"),
    ("02_createAdmissionEnAttente.xml", "ADMISSION_PLANNED", "ADT^A05", "admission", "Admission attendue"),
    ("03_createAdmissionHospit.xml", "ADMISSION_CONFIRMED", "ADT^A01", "admission", "Admission hospitalisation"),
    ("04_createSortieMutation.xml", "TRANSFER_OUT", "ADT^A02", "transfer", "Sortie vers mutation"),
    ("05_createEntreeMutation.xml", "TRANSFER_IN", "ADT^A02", "transfer", "Entrée mutation"),
    ("06_createSortieDefinitive.xml", "DISCHARGE", "ADT^A03", "discharge", "Sortie définitive"),
    ("07_createFinParcours.xml", "PARCOURS_END", None, "lifecycle", "Fin de parcours"),
]


def _read_reference_payload(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def create_ihe_hospit_simple_template(session: Session) -> ScenarioTemplate:
    key = "ihe.hospitSimple"
    existing = session.exec(select(ScenarioTemplate).where(ScenarioTemplate.key == key)).first()
    if existing:
        return existing

    template = ScenarioTemplate(
        key=key,
        name="IHE PAM - Hospitalisation simple",
        description="Parcours admission -> transferts -> sortie d'un patient hospitalisé (IHE PAM abstrait)",
        category="IHE",
        protocols_supported="HL7v2,FHIR",
        tags="pam,hospitalisation,transfer",
    )
    session.add(template)
    session.flush()  # id pour FK steps

    order_index = 1
    for filename, semantic_code, hl7_event, role, narrative in HOSPIT_SIMPLE_SEQUENCE:
        file_path = HOSPIT_SIMPLE_DIR / filename
        reference_xml = _read_reference_payload(file_path)
        step = ScenarioTemplateStep(
            template_id=template.id,
            order_index=order_index,
            semantic_event_code=semantic_code,
            narrative=narrative,
            hl7_event_code=hl7_event,
            message_role=role,
            reference_payload_xml=reference_xml if reference_xml else None,
        )
        session.add(step)
        order_index += 1

    session.commit()
    session.refresh(template)
    return template


def init_scenario_templates(session: Session) -> List[ScenarioTemplate]:
    """Initialise l'ensemble des templates standards (idempotent)."""
    templates: List[ScenarioTemplate] = []
    # Template manuel hospitSimple (7 étapes)
    templates.append(create_ihe_hospit_simple_template(session))
    
    # Import automatique depuis fichiers IHE PAM existants
    try:
        from app.services.scenario_ihe_importer import import_all_ihe_pam_scenarios
        ihe_base = Path("Doc/interfaces.integration_src/interfaces.integration/target/classes/data/entrant/hl7")
        if ihe_base.exists():
            imported = import_all_ihe_pam_scenarios(session, ihe_base)
            templates.extend(imported)
    except Exception as e:
        # Silencieux si fichiers absents (environnement différent)
        pass
    
    return templates
