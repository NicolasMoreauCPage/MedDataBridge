"""
Service de capture d'un dossier existant vers ScenarioTemplate réutilisable.

Principe :
- Lit un Dossier + Venues + Mouvements existants
- Extrait la séquence sémantique des événements (ADMISSION, TRANSFER, DISCHARGE...)
- Crée un ScenarioTemplate SNAPSHOT indépendant (copie des données, pas de référence FK)
- Le template reste intact même si le dossier source est modifié/supprimé
- Les templates capturés peuvent être rejoués comme les templates IHE importés

Architecture :
1. capture_dossier_as_template() : Dossier → ScenarioTemplate (snapshot)
2. Indépendance totale : pas de FK vers Dossier/Venue/Mouvement
3. Matérialisation : utilise scenario_template_materializer.py (comme templates IHE)
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select

from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep
from app.models import Dossier, Venue, Mouvement


def _infer_semantic_event(mouvement: Mouvement, venue: Venue) -> tuple[str, str, str]:
    """
    Infère le code sémantique, HL7 event et rôle depuis un Mouvement.
    
    Returns: (semantic_code, hl7_event_code, message_role)
    """
    # Logique simplifiée : adapter selon vos codes UF/types mouvement
    mvt_type = (mouvement.movement_type or mouvement.type or "").upper()
    
    if "ENTREE" in mvt_type or "ADMISSION" in mvt_type or "A01" in mvt_type:
        if venue.operational_status == "EN_COURS":
            return ("ADMISSION_CONFIRMED", "ADT^A01", "inbound")
        else:
            return ("PRE_ADMISSION", "ADT^A05", "inbound")
    
    elif "SORTIE" in mvt_type or "DISCHARGE" in mvt_type or "A03" in mvt_type:
        return ("DISCHARGE", "ADT^A03", "inbound")
    
    elif "TRANSFERT" in mvt_type or "MUTATION" in mvt_type or "A02" in mvt_type:
        return ("TRANSFER", "ADT^A02", "inbound")
    
    elif "ANNULATION" in mvt_type or "A11" in mvt_type:
        return ("CANCEL_ADMIT", "ADT^A11", "inbound")
    
    # Défaut
    return ("OTHER_EVENT", "ADT^A01", "inbound")


def capture_dossier_as_template(
    db: Session,
    dossier_id: int,
    template_name: Optional[str] = None,
    template_description: Optional[str] = None,
    category: str = "captured",
) -> ScenarioTemplate:
    """
    Capture un dossier existant comme ScenarioTemplate réutilisable.
    
    Principe :
    1. Lit Dossier + Venues + Mouvements
    2. Extrait la séquence des événements (ordonnés par date/heure)
    3. Crée ScenarioTemplate + Steps avec données SNAPSHOT (copie, pas référence)
    4. Le template est indépendant : modification/suppression du dossier source n'affecte pas le template
    
    Args:
        db: Session SQLModel
        dossier_id: ID du dossier à capturer
        template_name: Nom du template (auto si None)
        template_description: Description (auto si None)
        category: Catégorie ("captured" par défaut)
    
    Returns:
        ScenarioTemplate créé et persisté
    
    Raises:
        ValueError: Si dossier inexistant ou sans mouvements
    """
    # 1. Charger le dossier + venues + mouvements
    dossier = db.get(Dossier, dossier_id)
    if not dossier:
        raise ValueError(f"Dossier {dossier_id} introuvable")
    
    stmt = select(Venue).where(Venue.dossier_id == dossier_id)
    venues = db.exec(stmt).all()
    
    if not venues:
        raise ValueError(f"Dossier {dossier_id} sans venues")
    
    # Collecter tous les mouvements de toutes les venues
    all_mouvements = []
    for venue in venues:
        stmt_mvt = select(Mouvement).where(Mouvement.venue_id == venue.id)
        mouvements = db.exec(stmt_mvt).all()
        for mvt in mouvements:
            all_mouvements.append((mvt, venue))
    
    if not all_mouvements:
        raise ValueError(f"Dossier {dossier_id} sans mouvements")
    
    # Trier par date/heure mouvement (chrono)
    all_mouvements.sort(key=lambda x: x[0].when or datetime(1900, 1, 1))
    
    # 2. Générer template_key unique
    template_key = f"captured.dossier_{dossier_id}_{int(datetime.now().timestamp())}"
    
    # 3. Créer ScenarioTemplate SNAPSHOT
    template = ScenarioTemplate(
        key=template_key,
        name=template_name or f"Dossier {dossier.dossier_seq or dossier_id} capturé",
        description=template_description or (
            f"Capturé depuis dossier {dossier.dossier_seq or dossier_id} "
            f"le {datetime.now().strftime('%Y-%m-%d %H:%M')}. "
            f"Contient {len(all_mouvements)} mouvements."
        ),
        category=category,
        protocols_supported="HL7v2,FHIR",  # On peut rejouer en HL7 et FHIR
        tags=["captured", "real-data", f"dossier-{dossier_id}"],
        is_active=True,
    )
    db.add(template)
    db.flush()  # Générer template.id
    
    # 4. Créer ScenarioTemplateStep pour chaque mouvement (SNAPSHOT)
    for order_idx, (mvt, venue) in enumerate(all_mouvements, start=1):
        semantic_code, hl7_event, role = _infer_semantic_event(mvt, venue)
        
        # Calculer délai suggéré entre steps (en secondes)
        delay_seconds = 0
        if order_idx > 1:
            prev_mvt = all_mouvements[order_idx - 2][0]
            if mvt.when and prev_mvt.when:
                delta = mvt.when - prev_mvt.when
                delay_seconds = int(delta.total_seconds())
        
        step = ScenarioTemplateStep(
            template_id=template.id,
            order_index=order_idx,
            semantic_event_code=semantic_code,
            narrative=f"{mvt.movement_type or mvt.type or 'Mouvement'} vers {venue.hospital_service or 'service'} "
                      f"le {mvt.when.strftime('%Y-%m-%d %H:%M') if mvt.when else 'N/A'}",
            hl7_event_code=hl7_event,
            fhir_profile_hint="Bundle",
            message_role=role,
            # SNAPSHOT : on stocke les données à l'instant T (pas de FK vers Mouvement/Venue)
            reference_payload_hl7=f"# Mouvement ID {mvt.id}\n# Type: {mvt.movement_type or mvt.type}\n# Service: {venue.hospital_service}",
            delay_suggested_seconds=delay_seconds,
        )
        db.add(step)
    
    db.commit()
    db.refresh(template)
    
    return template


def list_captured_templates(db: Session) -> list[ScenarioTemplate]:
    """
    Liste tous les templates capturés depuis des dossiers réels.
    """
    stmt = select(ScenarioTemplate).where(ScenarioTemplate.category == "captured")
    return list(db.exec(stmt).all())


# ============================================================================
# FONCTION DE COMPATIBILITÉ AVEC ANCIEN SYSTÈME InteropScenario
# ============================================================================

def capture_dossier_as_scenario(
    session: Session,
    dossier: Dossier,
    *,
    key: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
):
    """
    Fonction de compatibilité ascendante pour ancien système InteropScenario.
    
    DEPRECATED: Utilisez capture_dossier_as_template() pour le nouveau système ScenarioTemplate.
    
    Cette fonction maintient la compatibilité avec:
    - app/routers/scenarios.py (POST /scenarios/capture)
    - tests/test_scenario_capture.py
    - tests/test_scenario_roundtrip.py
    - tests/test_scenario_integration.py
    """
    from app.models_scenarios import InteropScenario, InteropScenarioStep
    
    # Générer métadonnées
    key = key or f"capture/dossier/{dossier.id}/{datetime.now().isoformat()}"
    name = name or f"Capture Dossier {dossier.dossier_seq or dossier.id}"
    description = description or f"Scénario capturé depuis dossier {dossier.dossier_seq or dossier.id}"
    
    # Créer InteropScenario (ancien modèle)
    scenario = InteropScenario(
        key=key,
        name=name,
        description=description,
        protocol="HL7",
        category="capture",
        tags="capture,auto",
    )
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    
    # Récupérer mouvements via venues
    stmt = select(Venue).where(Venue.dossier_id == dossier.id)
    venues = session.exec(stmt).all()
    
    all_mouvements = []
    for venue in venues:
        stmt_mvt = select(Mouvement).where(Mouvement.venue_id == venue.id)
        mouvements = session.exec(stmt_mvt).all()
        all_mouvements.extend(mouvements)
    
    # Trier par date
    all_mouvements.sort(key=lambda m: m.when or datetime(1900, 1, 1))
    
    # Créer steps
    prev_when: Optional[datetime] = None
    for order_idx, mvt in enumerate(all_mouvements, start=1):
        trigger = mvt.trigger_event or "A01"
        
        # Générer payload HL7 minimal
        ts = (mvt.when or datetime.now()).strftime("%Y%m%d%H%M%S")
        control_id = f"CAP{mvt.id}{trigger}"
        payload = (
            f"MSH|^~\\&|CAP|LOCAL|REC|LOCAL|{ts}||ADT^{trigger}|{control_id}|P|2.5\r"
            f"EVN|{trigger}|{ts}\r"
            f"PID|1||PLACEHOLDER-IPP^^^CAPTURE&1.2.3&ISO^PI||Doe^John\r"
            f"PV1|1|I|||||||||||||||||PLACEHOLDER-NDA^^^CAPTURE&1.2.3&ISO^VN\r"
        )
        
        # Calculer délai
        delay_seconds = None
        if prev_when:
            diff = (mvt.when - prev_when).total_seconds()
            delay_seconds = int(diff) if diff > 0 else 0
        
        step = InteropScenarioStep(
            scenario_id=scenario.id,
            order_index=order_idx,
            message_format="hl7",
            message_type=f"ADT^{trigger}",
            payload=payload,
            delay_seconds=delay_seconds,
            name=f"{trigger} mouvement #{mvt.id}",
        )
        session.add(step)
        prev_when = mvt.when
    
    session.commit()
    return scenario
