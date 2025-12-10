# app/runners.py
from typing import Dict, List, Optional
from datetime import datetime, timezone
import asyncio
import threading
from app.services.mllp_manager import MLLPManager
from app.db_session_factory import session_factory
from app.services.transport_inbound import on_message_inbound

# Manager used to start/stop endpoints from the web UI
manager = MLLPManager(session_factory, on_message_inbound)

# Optional reference to the main asyncio event loop used by the ASGI server.
# Provided by `app.app` at startup via `runners.set_event_loop(loop)` so that
# synchronous request handlers (executed in threadpool) can schedule coroutines
# on the running loop using `asyncio.run_coroutine_threadsafe`.
_main_event_loop: Optional[asyncio.AbstractEventLoop] = None

def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_event_loop
    _main_event_loop = loop

class RunnerRegistry:
    def __init__(self):
        self._runners: Dict[int, object] = {}

    def running_ids(self) -> List[int]:
        return list(self._runners.keys())

    def is_running(self, endpoint_id: int) -> bool:
        return endpoint_id in self._runners

    def start(self, endpoint, session):
        if endpoint.kind == "MLLP" and endpoint.role in ("receiver","both"):
            # If the main ASGI event loop was provided, schedule the coroutine
            # thread-safely on that loop (this is required when called from a
            # synchronous thread via FastAPI's threadpool). Otherwise attempt a
            # best-effort create_task on the current loop.
            if _main_event_loop is not None:
                asyncio.run_coroutine_threadsafe(manager.start_endpoint(endpoint), _main_event_loop)
            else:
                try:
                    asyncio.create_task(manager.start_endpoint(endpoint))
                except RuntimeError:
                    # No running loop in this thread — spawn a new background
                    # task by creating a new loop in a separate thread to avoid
                    # crashing the request. This is a fallback and should be
                    # avoided by wiring the main loop from app.app.
                    def _runner():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(manager.start_endpoint(endpoint))
                        loop.close()
                    t = threading.Thread(target=_runner, daemon=True)
                    t.start()
        self._runners[endpoint.id] = object()
        endpoint.updated_at = datetime.now(timezone.utc)
        session.add(endpoint)

    def stop(self, endpoint, session):
        self._runners.pop(endpoint.id, None)
        endpoint.updated_at = datetime.now(timezone.utc)
        session.add(endpoint)

registry = RunnerRegistry()
