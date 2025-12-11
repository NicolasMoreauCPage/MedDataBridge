"""Orchestration des serveurs MLLP.

Rôle
- Démarrer/arrêter/recharger les serveurs MLLP déclarés dans la base
  (modèle `SystemEndpoint`).
- Éviter les conflits d'adresse (host:port) et assurer l'idempotence.
- Offrir des méthodes pratiques: `start_endpoint`, `stop_endpoint`,
  `stop_all`, `reload_all`.

Concurrence
- Un verrou asyncio protège la table interne lorsque plusieurs tâches
  demandent un start/stop simultané.
"""

 # app/services/mllp_manager.py
import asyncio
from typing import Dict, List, Tuple
from contextlib import suppress
from sqlmodel import select
from app.models_endpoints import SystemEndpoint
from app.services.mllp import start_mllp_server, stop_mllp_server

class MLLPManager:
    """Gestionnaire de serveurs MLLP.

    Args:
        session_factory: Callable retournant une session DB courte.
        on_message: Callback asynchrone appelé pour chaque message entrant.
    """
    def __init__(self, session_factory, on_message):
        self.session_factory = session_factory
        self.on_message = on_message
        self.servers: Dict[int, asyncio.base_events.Server] = {}
        self._by_addr: Dict[Tuple[str,int], int] = {}
        self._lock = asyncio.Lock()

    def running_ids(self) -> List[int]:
        """Retourne la liste des endpoint_ids actuellement en écoute."""
        return list(self.servers.keys())

    async def start_endpoint(self, endpoint: SystemEndpoint):
        """Démarre un endpoint MLLP s'il est éligible et non déjà démarré."""
        if endpoint.kind != "MLLP" or endpoint.role not in ("receiver","both"):
            return
        if not endpoint.host or not endpoint.port:
            return
        async with self._lock:
            if endpoint.id in self.servers:
                return
            key = (endpoint.host, endpoint.port)
            if key in self._by_addr:
                return
            try:
                server = await start_mllp_server(
                    host=endpoint.host,
                    port=endpoint.port,
                    on_message=self.on_message,
                    endpoint_name=endpoint.name,
                    session_factory=self.session_factory,
                )
            except OSError as e:
                # Ne pas faire échouer le démarrage de l'application si le
                # bind échoue pour un endpoint particulier (par ex. address
                # already in use). Loggons le problème et continuons.
                import logging
                logger = logging.getLogger("mllp.manager")
                logger.warning(
                    "Cannot start MLLP endpoint %s on %s:%s — %s; skipping",
                    getattr(endpoint, "name", endpoint.id), endpoint.host, endpoint.port, e
                )
                return
            self.servers[endpoint.id] = server
            self._by_addr[key] = endpoint.id

    async def stop_endpoint(self, endpoint_id: int):
        """Arrête proprement le serveur associé à `endpoint_id`. Idempotent."""
        async with self._lock:
            server = self.servers.pop(endpoint_id, None)
            if server:
                await stop_mllp_server(server)
            with suppress(KeyError):
                for k, eid in list(self._by_addr.items()):
                    if eid == endpoint_id:
                        del self._by_addr[k]

    async def stop_all(self):
        """Arrête tous les serveurs en cours."""
        async with self._lock:
            servers = list(self.servers.values())
            self.servers.clear()
            self._by_addr.clear()
        for s in servers:
            await stop_mllp_server(s)

    async def reload_all(self, session):
        """Re-scanne la base et démarre les endpoints MLLP actifs.

        Arrête d'abord les serveurs existants, puis démarre tous les
        endpoints MLLP ayant `is_enabled=True`.
        """
        await self.stop_all()
        eps = session.exec(
            select(SystemEndpoint).where(
                SystemEndpoint.is_enabled == True,
                SystemEndpoint.kind == "MLLP"
            )
        ).all()
        for e in eps:
            await self.start_endpoint(e)
