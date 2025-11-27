"""
Système d'événements pour l'émission automatique de messages HL7/FHIR.

Ce module met en place un système de "webhooks" basé sur la base de données.
Il écoute les modifications sur les entités principales (Patient, Dossier, etc.)
et déclenche des actions asynchrones (comme l'envoi de messages) après
que les transactions de base de données ont été confirmées avec succès.

Le flux de travail est le suivant :
1.  **Enregistrement :** Au démarrage de l'application, `register_entity_events()` attache
    des écouteurs SQLAlchemy aux événements `after_insert` et `after_update` des modèles.
2.  **Planification :** Lorsqu'une entité est modifiée dans une session, l'écouteur
    appelle `_schedule_emission()`, qui ajoute une tâche à un dictionnaire
    `_pending_emissions` lié à la session en cours. Une protection empêche les
    émissions en chaîne (une émission qui déclenche une autre émission).
3.  **Commit :** Une fois la transaction de base de données validée (`commit`),
    l'écouteur `after_commit` s'exécute.
4.  **Exécution en arrière-plan :** La fonction `after_commit` récupère les tâches
    planifiées pour la session terminée et les soumet à un `ThreadPoolExecutor`.
    Chaque tâche s'exécute dans un thread séparé, appelant `_emit_in_new_session`.
5.  **Émission :** `_emit_in_new_session` s'exécute dans son propre thread, ouvre une
    nouvelle session de base de données pour récupérer une vue à jour de l'entité,
    et effectue l'émission réelle via `emit_to_senders_async`. Un sémaphore
    limite le nombre d'émissions concurrentes pour éviter d'épuiser les ressources.

Ce mécanisme garantit que les émissions ne se produisent que pour les données
validées et ne bloquent pas le thread principal de l'application.
"""

import asyncio
import logging
import threading
from typing import Any, Dict, Set
from sqlalchemy import event
from sqlalchemy.orm import Session  # Use SQLAlchemy Session for event listeners

from app.models import Patient, Dossier, Venue, Mouvement
from app.services.emit_on_create import emit_to_senders_async

logger = logging.getLogger(__name__)

# --- Gestion d'état du système d'événements ---

# _pending_emissions: Dictionnaire pour suivre les entités à émettre après la
# validation (commit) de la transaction. La clé est l'ID de la session SQLAlchemy,
# et la valeur est un ensemble de tuples (id_entité, type_entité, opération)
# pour éviter les doublons.
_pending_emissions: Dict[int, Set[tuple]] = {}

# _emission_context: Un objet "thread-local" utilisé comme drapeau pour savoir
# si le thread courant est déjà en train d'exécuter une émission. C'est une
# sécurité cruciale pour empêcher les boucles d'émission infinies (une émission
# qui modifie une entité, déclenchant ainsi une autre émission).
_emission_context = threading.local()

# _emission_semaphore: Un sémaphore pour limiter le nombre d'émissions simultanées
# s'exécutant en arrière-plan. Protège contre l'épuisement des ressources
# (par exemple, le pool de connexions à la base de données) en cas d'un grand
# nombre de modifications rapides.
_emission_semaphore = threading.Semaphore(5)


def _get_session_id(session: Session) -> int:
    """Get unique ID for session to track pending emissions."""
    return id(session)


def _schedule_emission(session: Session, entity: Any, entity_type: str, operation: str):
    """
    Planifie une émission pour qu'elle s'exécute après la validation (commit)
    de la transaction en cours.
    """
    # Vérifie si nous sommes déjà dans un contexte d'émission pour éviter les boucles.
    if getattr(_emission_context, 'active', False):
        logger.debug(f"[entity_events] Skipping emission during emission: {entity_type} id={entity.id}")
        return
    
    session_id = _get_session_id(session)
    
    if session_id not in _pending_emissions:
        _pending_emissions[session_id] = set()
    
    # Utilise une clé (id, type, op) pour éviter de planifier plusieurs fois
    # la même émission au sein d'une même transaction.
    entity_id = entity.id
    emission_key = (entity_id, entity_type, operation)
    
    if emission_key not in _pending_emissions[session_id]:
        _pending_emissions[session_id].add(emission_key)
        logger.debug(f"[entity_events] Scheduled emission: {entity_type} id={entity_id} op={operation}")


@event.listens_for(Session, "after_commit")
def after_commit(session: Session):
    """
    Déclenché après la validation d'une transaction.
    Lance les émissions pour toutes les entités modifiées dans cette transaction.

    Cette fonction agit comme un pont entre le monde synchrone des événements
    SQLAlchemy et le monde asynchrone des fonctions d'émission. Elle utilise un
    ThreadPoolExecutor pour lancer chaque émission dans un thread d'arrière-plan,
    évitant ainsi de bloquer le thread principal de l'application qui a déclenché
    le commit.
    """
    session_id = _get_session_id(session)
    
    if session_id not in _pending_emissions:
        return
    
    pending = _pending_emissions.pop(session_id)
    
    if not pending:
        return
    
    logger.info(f"[entity_events] Processing {len(pending)} pending emission(s)")
    
    for entity_id, entity_type, operation in pending:
        try:
            # Récupère la classe de l'entité à partir de son type (str)
            entity_class = {
                "patient": Patient,
                "dossier": Dossier,
                "venue": Venue,
                "mouvement": Mouvement,
            }.get(entity_type)
            
            if not entity_class:
                logger.error(f"[entity_events] Unknown entity type: {entity_type}")
                continue
            
            # Planifie l'émission en arrière-plan via un pool de threads.
            # `after_commit` est synchrone, mais l'émission est asynchrone.
            # Le pool de threads permet de lancer une nouvelle boucle d'événements
            # asyncio pour chaque émission.
            import concurrent.futures
            if not hasattr(after_commit, "_executor"):
                after_commit._executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

            def run_emission():
                import asyncio
                try:
                    # Crée une nouvelle boucle d'événements asyncio et exécute la coroutine.
                    asyncio.run(_emit_in_new_session(entity_class, entity_id, entity_type, operation))
                except Exception as exc:
                    logger.error(f"[entity_events] Emission failed in executor: {exc}", exc_info=True)

            after_commit._executor.submit(run_emission)
        
        except Exception as exc:
            logger.error(f"[entity_events] Failed to schedule emission {entity_type} id={entity_id}: {exc}")


async def _emit_in_new_session(entity_class: type, entity_id: int, entity_type: str, operation: str):
    """
    Exécute l'émission pour une entité donnée dans une nouvelle session.

    Cette fonction est le cœur du worker d'arrière-plan. Elle est conçue pour
    être robuste et thread-safe.
    
    Points importants :
    - Nouvelle Session : Elle crée une session de base de données éphémère pour
      s'assurer que les données de l'entité sont à jour et pour éviter les
      problèmes de thread-safety avec la session d'origine (qui est fermée).
    - Sémaphore : Elle utilise `_emission_semaphore` pour limiter la concurrence.
    - Contexte d'Émission : Elle active le drapeau `_emission_context.active` pour
      prévenir toute émission récursive.
    """
    from app.db import engine
    from sqlmodel import Session as SQLModelSession
    
    # Acquiert le sémaphore pour limiter le nombre d'émissions concurrentes.
    with _emission_semaphore:
        # Active le drapeau pour indiquer qu'une émission est en cours dans ce thread.
        _emission_context.active = True
        
        try:
            with SQLModelSession(engine) as emit_session:
                entity = emit_session.get(entity_class, entity_id)
                if not entity:
                    logger.warning(f"[entity_events] Entity not found in new session: {entity_type} id={entity_id}")
                    return
                
                await emit_to_senders_async(entity, entity_type, emit_session, operation)
            
            logger.info(f"[entity_events] ✓ Emitted {entity_type} id={entity_id} op={operation}")
        except Exception as exc:
            logger.error(f"[entity_events] ✗ Emission failed for {entity_type} id={entity_id}: {exc}", exc_info=True)
        finally:
            # Libère toujours le drapeau, même en cas d'erreur.
            _emission_context.active = False


# --- Callbacks pour les événements SQLAlchemy ---

def _entity_after_insert(mapper, connection, target):
    """Callback générique pour les insertions d'entités."""
    session = Session.object_session(target)
    if not session:
        return
    
    entity_type = {
        Patient: "patient",
        Dossier: "dossier",
        Venue: "venue",
        Mouvement: "mouvement",
    }.get(type(target))
    
    if entity_type:
        _schedule_emission(session, target, entity_type, "insert")


def _entity_after_update(mapper, connection, target):
    """Callback générique pour les mises à jour d'entités."""
    session = Session.object_session(target)
    if not session:
        return
    
    entity_type = {
        Patient: "patient",
        Dossier: "dossier",
        Venue: "venue",
        Mouvement: "mouvement",
    }.get(type(target))
    
    if entity_type:
        _schedule_emission(session, target, entity_type, "update")


def register_entity_events():
    """
    Enregistre tous les écouteurs d'événements sur les entités.
    Doit être appelée au démarrage de l'application pour activer l'émission automatique.
    """
    listeners = [
        (Patient, "after_insert", _entity_after_insert),
        (Dossier, "after_insert", _entity_after_insert),
        (Venue, "after_insert", _entity_after_insert),
        (Mouvement, "after_insert", _entity_after_insert),
        (Patient, "after_update", _entity_after_update),
        (Dossier, "after_update", _entity_after_update),
        (Venue, "after_update", _entity_after_update),
        (Mouvement, "after_update", _entity_after_update),
    ]
    
    for model, event_name, func in listeners:
        event.listen(model, event_name, func)
    
    logger.info("[entity_events] ✓ Entity event listeners registered for Patient, Dossier, Venue, Mouvement")
