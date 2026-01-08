"""
Système de gestion des tâches en arrière-plan pour MedData Bridge.

Permet d'exécuter des opérations longues (imports, exports, synchronisations)
sans bloquer l'interface utilisateur.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

from config.settings import settings

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """États possibles d'une tâche."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Représente une tâche en arrière-plan."""
    id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0  # 0.0 à 1.0
    progress_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit la tâche en dictionnaire pour l'API."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }


class TaskManager:
    """Gestionnaire centralisé des tâches en arrière-plan."""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.max_concurrent_tasks = settings.max_concurrent_tasks or 3
        self.task_timeout = settings.task_timeout or 3600  # 1 heure par défaut
        self.running_tasks = 0

    def create_task(self, name: str, description: str, **metadata) -> str:
        """Crée une nouvelle tâche et retourne son ID."""
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            name=name,
            description=description,
            metadata=metadata
        )
        self.tasks[task_id] = task
        logger.info(f"Tâche créée: {task_id} - {name}")
        return task_id

    async def execute_task(
        self,
        task_id: str,
        coroutine_func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> None:
        """Exécute une tâche en arrière-plan."""
        if task_id not in self.tasks:
            raise ValueError(f"Tâche {task_id} introuvable")

        task = self.tasks[task_id]

        # Vérifier la limite de tâches concurrentes
        if self.running_tasks >= self.max_concurrent_tasks:
            task.status = TaskStatus.FAILED
            task.error = "Trop de tâches en cours d'exécution"
            return

        self.running_tasks += 1
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        try:
            # Créer une tâche avec timeout
            task_coro = asyncio.create_task(
                self._run_task_with_progress(task, coroutine_func, *args, **kwargs)
            )

            # Attendre avec timeout
            await asyncio.wait_for(task_coro, timeout=self.task_timeout)

        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.error = f"Tâche timeout après {self.task_timeout} secondes"
            logger.error(f"Tâche {task_id} timeout")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"Tâche {task_id} échouée: {e}")

        finally:
            self.running_tasks -= 1
            task.completed_at = datetime.now()

    async def _run_task_with_progress(
        self,
        task: Task,
        coroutine_func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> None:
        """Exécute une coroutine avec suivi de progression."""
        try:
            # Si la fonction accepte un callback de progression
            if 'progress_callback' in kwargs:
                # Remplacer le callback par notre propre fonction
                original_callback = kwargs['progress_callback']

                def progress_wrapper(progress: float, message: str = ""):
                    task.progress = max(0.0, min(1.0, progress))
                    task.progress_message = message
                    if original_callback:
                        original_callback(progress, message)

                kwargs['progress_callback'] = progress_wrapper

            result = await coroutine_func(*args, **kwargs)

            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.progress_message = "Terminé"
            task.result = result

            logger.info(f"Tâche {task.id} terminée avec succès")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise

    def get_task(self, task_id: str) -> Optional[Task]:
        """Récupère une tâche par son ID."""
        return self.tasks.get(task_id)

    def list_tasks(self, status_filter: Optional[TaskStatus] = None) -> list[Task]:
        """Liste toutes les tâches, optionnellement filtrées par statut."""
        tasks = list(self.tasks.values())

        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]

        # Trier par date de création (plus récent en premier)
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def cancel_task(self, task_id: str) -> bool:
        """Annule une tâche en cours."""
        task = self.tasks.get(task_id)
        if not task or task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            return False

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        logger.info(f"Tâche {task_id} annulée")
        return True

    def cleanup_old_tasks(self, max_age_days: int = 7) -> int:
        """Nettoie les anciennes tâches terminées."""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        tasks_to_remove = []

        for task_id, task in self.tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                and task.completed_at and task.completed_at < cutoff_date):
                tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            del self.tasks[task_id]

        if tasks_to_remove:
            logger.info(f"Nettoyé {len(tasks_to_remove)} anciennes tâches")

        return len(tasks_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques des tâches."""
        total = len(self.tasks)
        by_status = {}
        for status in TaskStatus:
            by_status[status.value] = len([t for t in self.tasks.values() if t.status == status])

        return {
            "total_tasks": total,
            "running_tasks": self.running_tasks,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "tasks_by_status": by_status
        }


# Instance globale du gestionnaire de tâches
task_manager = TaskManager()


# Fonctions utilitaires pour créer et suivre des tâches
def create_background_task(name: str, description: str, **metadata) -> str:
    """Crée une tâche en arrière-plan et retourne son ID."""
    return task_manager.create_task(name, description, **metadata)


async def run_background_task(task_id: str, coro_func: Callable[..., Awaitable[Any]], *args, **kwargs):
    """Lance une tâche en arrière-plan."""
    await task_manager.execute_task(task_id, coro_func, *args, **kwargs)


# Décorateur pour transformer une fonction en tâche de fond
def background_task(name: str = None, description: str = None):
    """Décorateur pour exécuter une fonction en tant que tâche de fond."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            task_name = name or f"{func.__name__}"
            task_desc = description or f"Exécution de {func.__name__}"

            task_id = create_background_task(task_name, task_desc)
            asyncio.create_task(run_background_task(task_id, func, *args, **kwargs))

            return {"task_id": task_id, "status": "started"}

        return wrapper
    return decorator


# Tâches prédéfinies courantes
@background_task("Import de données", "Import de données depuis un fichier")
async def import_data_task(file_path: str, data_type: str, progress_callback=None):
    """Tâche d'import de données générique."""
    # Simulation d'import avec progression
    steps = ["Lecture du fichier", "Validation des données", "Import en base", "Finalisation"]

    for i, step in enumerate(steps):
        if progress_callback:
            progress_callback((i + 1) / len(steps), step)

        # Simuler du travail
        await asyncio.sleep(1)

    return {"imported": 100, "errors": 0}


@background_task("Export de données", "Export de données vers un fichier")
async def export_data_task(query: dict, format: str, progress_callback=None):
    """Tâche d'export de données générique."""
    # Simulation d'export
    steps = ["Préparation de la requête", "Exécution", "Formatage", "Sauvegarde"]

    for i, step in enumerate(steps):
        if progress_callback:
            progress_callback((i + 1) / len(steps), step)

        await asyncio.sleep(0.5)

    return {"exported": 500, "file_path": "/tmp/export.json"}


# Nettoyage périodique des tâches anciennes
async def cleanup_task():
    """Tâche de nettoyage périodique des anciennes tâches."""
    while True:
        try:
            removed = task_manager.cleanup_old_tasks()
            if removed > 0:
                logger.info(f"Nettoyé {removed} tâches anciennes")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des tâches: {e}")

        # Nettoyer toutes les 24 heures
        await asyncio.sleep(24 * 3600)