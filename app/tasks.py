"""Compatibilité historique du gestionnaire de tâches.

Le runtime des tâches est désormais dans :mod:`app.runtime.tasks`.
"""

from app.runtime.tasks import (
    Task,
    TaskManager,
    TaskStatus,
    background_task,
    cleanup_task,
    create_background_task,
    export_data_task,
    import_data_task,
    run_background_task,
    task_manager,
)

__all__ = [
    "Task",
    "TaskManager",
    "TaskStatus",
    "background_task",
    "cleanup_task",
    "create_background_task",
    "export_data_task",
    "import_data_task",
    "run_background_task",
    "task_manager",
]
