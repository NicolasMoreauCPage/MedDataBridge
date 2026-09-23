"""Snapshots détachés utilisés par les émetteurs de messages.

Le snapshot matérialise uniquement les scalaires nécessaires aux générateurs.
Il évite qu'un transport différé déclenche des chargements ORM après la fin de
la transaction qui a créé ou modifié l'entité.
"""

import logging

from sqlmodel import Session, select

from app.models_identifiers import Identifier

logger = logging.getLogger(__name__)


def snapshot_entity(entity, entity_type: str, session: Session) -> dict:
    """Retourne une vue sérialisable de l'entité, sans relations lazy ORM."""
    snapshot: dict = {}
    try:
        if entity_type == "patient":
            snapshot.update({
                "id": getattr(entity, "id", None),
                "patient_seq": getattr(entity, "patient_seq", None),
                "family": getattr(entity, "family", None),
                "given": getattr(entity, "given", None),
                "gender": getattr(entity, "gender", None),
                "birth_date": getattr(entity, "birth_date", None),
                "external_id": getattr(entity, "external_id", None),
                "nir": getattr(entity, "nir", None),
                "entite_juridique_id": getattr(entity, "entite_juridique_id", None),
            })
            identifiers = []
            try:
                identifier_models = getattr(entity, "identifiers", None)
                if not identifier_models:
                    identifier_models = session.exec(
                        select(Identifier).where(Identifier.patient_id == getattr(entity, "id", None))
                    ).all()
                for identifier in identifier_models or []:
                    identifiers.append({
                        "value": identifier.value,
                        "system": identifier.system,
                        "oid": getattr(identifier, "oid", None),
                        "status": identifier.status,
                        "type": getattr(identifier, "type", None),
                    })
            except Exception:
                logger.exception("Impossible de matérialiser les identifiants du patient")
            snapshot["identifiers"] = identifiers
        elif entity_type == "dossier":
            snapshot.update({
                "id": getattr(entity, "id", None),
                "dossier_seq": getattr(entity, "dossier_seq", None),
                "patient_id": getattr(entity, "patient_id", None),
                "entite_juridique_id": getattr(entity, "entite_juridique_id", None),
                "dossier_type": getattr(entity, "dossier_type", None),
                "uf_responsabilite": getattr(entity, "uf_responsabilite", None),
            })
        elif entity_type == "venue":
            snapshot.update({
                "id": getattr(entity, "id", None),
                "venue_seq": getattr(entity, "venue_seq", None),
                "dossier_id": getattr(entity, "dossier_id", None),
                "start_time": getattr(entity, "start_time", None),
                "uf_responsabilite": getattr(entity, "uf_responsabilite", None),
            })
        elif entity_type == "mouvement":
            snapshot.update({
                "id": getattr(entity, "id", None),
                "mouvement_seq": getattr(entity, "mouvement_seq", None),
                "venue_id": getattr(entity, "venue_id", None),
                "when": getattr(entity, "when", None),
                "type": getattr(entity, "type", None),
                "trigger_event": getattr(entity, "trigger_event", None),
                "uf_responsabilite": getattr(entity, "uf_responsabilite", None),
                "location": getattr(entity, "location", None),
            })
        else:
            snapshot.update({key: getattr(entity, key, None) for key in dir(entity) if not key.startswith("_")})
    except Exception:
        logger.exception("Impossible de créer le snapshot de l'entité %s", entity)
    return snapshot
