"""API de gestion des tâches asynchrones."""

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.tasks import (
	TaskStatus,
	create_background_task,
	task_manager,
)

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


class TaskLaunchRequest(BaseModel):
	"""Requête de lancement d'une tâche de démonstration."""

	file_path: Optional[str] = Field(default=None, description="Chemin du fichier à importer")
	data_type: str = Field(default="hl7", description="Type de données à importer")


class ExportLaunchRequest(BaseModel):
	"""Requête de lancement d'une exportation de démonstration."""

	query: dict = Field(default_factory=dict, description="Critères d'export")
	format: str = Field(default="json", description="Format cible")


@router.get("/stats")
def get_task_stats():
	"""Retourne les statistiques globales des tâches."""
	return task_manager.get_stats()


@router.get("")
def list_tasks(status: Optional[str] = Query(default=None, description="Filtre de statut")):
	"""Liste les tâches avec filtre optionnel de statut."""
	status_filter = None
	if status:
		try:
			status_filter = TaskStatus(status)
		except ValueError as exc:
			allowed = ", ".join([s.value for s in TaskStatus])
			raise HTTPException(status_code=400, detail=f"Statut invalide '{status}'. Valeurs autorisées: {allowed}") from exc

	tasks = task_manager.list_tasks(status_filter=status_filter)
	return {
		"count": len(tasks),
		"tasks": [task.to_dict() for task in tasks],
	}


@router.get("/{task_id}")
def get_task(task_id: str):
	"""Récupère une tâche par son identifiant."""
	task = task_manager.get_task(task_id)
	if not task:
		raise HTTPException(status_code=404, detail=f"Tâche {task_id} introuvable")
	return task.to_dict()


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str):
	"""Annule une tâche en cours (pending/running)."""
	task = task_manager.get_task(task_id)
	if not task:
		raise HTTPException(status_code=404, detail=f"Tâche {task_id} introuvable")

	if not task_manager.cancel_task(task_id):
		raise HTTPException(
			status_code=409,
			detail=f"La tâche {task_id} ne peut pas être annulée (statut: {task.status.value})",
		)

	return {"status": "cancelled", "task_id": task_id}


@router.post("/launch/import")
async def launch_import_task(payload: TaskLaunchRequest):
	"""Lance une tâche asynchrone d'import (outil opérationnel API)."""
	async def _import_job(file_path: str, data_type: str, progress_callback=None):
		steps = [
			"Lecture du fichier source",
			"Contrôle de conformité interop",
			"Chargement des entités métier",
			"Finalisation",
		]
		for idx, step in enumerate(steps, start=1):
			if progress_callback:
				progress_callback(idx / len(steps), step)
			await asyncio.sleep(0.25)
		return {"file_path": file_path, "data_type": data_type, "imported": True}

	task_id = create_background_task(
		name="Import de données",
		description="Import manuel déclenché via API",
		source="api",
		data_type=payload.data_type,
	)
	asyncio.create_task(
		task_manager.execute_task(
			task_id,
			_import_job,
			payload.file_path or "uploaded_file",
			payload.data_type,
		)
	)
	task = task_manager.get_task(task_id)
	return {
		"status": "started",
		"task_id": task_id,
		"task": task.to_dict() if task else None,
	}


@router.post("/launch/export")
async def launch_export_task(payload: ExportLaunchRequest):
	"""Lance une tâche asynchrone d'export (outil opérationnel API)."""
	async def _export_job(query: dict, format_name: str, progress_callback=None):
		steps = [
			"Préparation de l'extraction",
			"Agrégation des données",
			"Génération du format cible",
			"Archivage du fichier",
		]
		for idx, step in enumerate(steps, start=1):
			if progress_callback:
				progress_callback(idx / len(steps), step)
			await asyncio.sleep(0.2)
		return {"query": query, "format": format_name, "exported": True}

	task_id = create_background_task(
		name="Export de données",
		description="Export manuel déclenché via API",
		source="api",
		format=payload.format,
	)
	asyncio.create_task(
		task_manager.execute_task(
			task_id,
			_export_job,
			payload.query,
			payload.format,
		)
	)
	task = task_manager.get_task(task_id)
	return {
		"status": "started",
		"task_id": task_id,
		"task": task.to_dict() if task else None,
	}
