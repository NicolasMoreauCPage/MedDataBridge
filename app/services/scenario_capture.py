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
from app.models_shared import Dossier, Venue, Mouvement


def _infer_semantic_event(mouvement: Mouvement, venue: Venue) -> tuple[str, str, str]:
    """
    Infère le code sémantique, HL7 event et rôle depuis un Mouvement.
    
    Returns: (semantic_code, hl7_event_code, message_role)
    """
    # Logique simplifiée : adapter selon vos codes UF/types mouvement
    mvt_type = (mouvement.type_mouvement or "").upper()
    
    if "ENTREE" in mvt_type or "ADMISSION" in mvt_type:
        if venue.statut == "EN_COURS":
            return ("ADMISSION_CONFIRMED", "ADT^A01", "inbound")
        else:
            return ("PRE_ADMISSION", "ADT^A05", "inbound")
    
    elif "SORTIE" in mvt_type or "DISCHARGE" in mvt_type:
        return ("DISCHARGE", "ADT^A03", "inbound")
    
    elif "TRANSFERT" in mvt_type or "MUTATION" in mvt_type:
        return ("TRANSFER", "ADT^A02", "inbound")
    
    elif "ANNULATION" in mvt_type:
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
    all_mouvements.sort(key=lambda x: x[0].date_heure_mouvement or datetime(1900, 1, 1))
    
    # 2. Générer template_key unique
    template_key = f"captured.dossier_{dossier_id}_{int(datetime.now().timestamp())}"
    
    # 3. Créer ScenarioTemplate SNAPSHOT
    template = ScenarioTemplate(
        key=template_key,
        name=template_name or f"Dossier {dossier.numero_dossier or dossier_id} capturé",
        description=template_description or (
            f"Capturé depuis dossier {dossier.numero_dossier or dossier_id} "
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
            if mvt.date_heure_mouvement and prev_mvt.date_heure_mouvement:
                delta = mvt.date_heure_mouvement - prev_mvt.date_heure_mouvement
                delay_seconds = int(delta.total_seconds())
        
        step = ScenarioTemplateStep(
            template_id=template.id,
            order_index=order_idx,
            semantic_event_code=semantic_code,
            narrative=f"{mvt.type_mouvement or 'Mouvement'} vers {venue.service_code or 'service'} "
                      f"le {mvt.date_heure_mouvement.strftime('%Y-%m-%d %H:%M') if mvt.date_heure_mouvement else 'N/A'}",
            hl7_event_code=hl7_event,
            fhir_profile_hint="Bundle",
            message_role=role,
            # SNAPSHOT : on stocke les données à l'instant T (pas de FK vers Mouvement/Venue)
            reference_payload_hl7=f"# Mouvement ID {mvt.id}\n# Type: {mvt.type_mouvement}\n# Service: {venue.service_code}",
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
