"""
Background task scheduler for file endpoint polling.

Runs periodic tasks like scanning file-based endpoints.
"""
import asyncio
import logging
from typing import Optional
from app.db import session_factory
from app.services.file_poller import scan_file_endpoints
from app.services.outbox_service import process_due_messages
from app.services.scenario_campaign_service import process_queued_campaigns
from sqlmodel import select
from app.models_shared import SystemEndpoint
from config.settings import settings

logger = logging.getLogger(__name__)

# Les deux transports sont lus par ``FileEndpointPoller``. FTP reste un
# transport de dépôt sortant : il n'a pas de poller entrant dans l'application.
POLLABLE_FILE_ENDPOINT_KINDS = ("FILE", "SFTP")


class BackgroundScheduler:
    """
    Background task scheduler for periodic jobs.
    
    Handles:
    - file endpoint polling (configurable interval);
    - persistent outgoing messages whose retry date has elapsed.
    """
    
    def __init__(self, poll_interval_seconds: int = 60):
        """
        Initialize the scheduler.
        
        Args:
            poll_interval_seconds: Interval between file polls (default: 60s = 1 minute)
        """
        self.poll_interval_seconds = poll_interval_seconds
        self.running = False
        self.task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the background scheduler"""
        import os
        if "PYTEST_CURRENT_TEST" in os.environ:
            logger.info("Scheduler not started: running under pytest")
            return
        if self.running:
            logger.warning("Scheduler already running")
            return
        self.running = True
        self.task = asyncio.create_task(self._poll_loop())
        logger.info(f"Background scheduler started (poll interval: {self.poll_interval_seconds}s)")
    
    async def stop(self):
        """Stop the background scheduler"""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("Background scheduler stopped")
    
    async def _poll_loop(self):
        """Main polling loop"""
        while self.running:
            # Les travaux sont indépendants : une erreur de lecture FILE ne
            # doit pas empêcher les reprises d'outbox ou les campagnes.
            for label, job in (
                ("file endpoint polling", self._scan_file_endpoints),
                ("outbox processing", self._process_due_outbox),
                ("campaign processing", self._process_queued_campaigns),
            ):
                try:
                    await job()
                except Exception as e:
                    logger.error("Error in %s: %s", label, e, exc_info=True)
            
            # Wait for next poll
            try:
                await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                break
    
    async def _scan_file_endpoints(self):
        """Scan all file endpoints"""
        # Create a session for this scan using the explicit factory
        with session_factory() as session:
            # Quick check: if there are no enabled file-polling endpoints, skip
            # the expensive scan. SFTP uses the same poller as local FILE.
            stmt = select(SystemEndpoint).where(
                SystemEndpoint.kind.in_(POLLABLE_FILE_ENDPOINT_KINDS),
                SystemEndpoint.is_enabled.is_(True)
            ).limit(1)
            any_ep = session.exec(stmt).first()
            if not any_ep:
                logger.debug("No enabled FILE/SFTP endpoints configured; skipping file scan")
                return

            logger.debug("Scanning file endpoints...")
            stats = await scan_file_endpoints(session)
            if stats['files_processed'] > 0 or stats['errors']:
                logger.info(
                    f"File scan complete: {stats['endpoints_scanned']} endpoints, "
                    f"{stats['files_processed']} files processed, "
                    f"{stats['mfn_messages']} MFN, {stats['adt_messages']} ADT, "
                    f"{len(stats['errors'])} errors"
                )
                
                if stats['errors']:
                    for error in stats['errors']:
                        logger.error(f"  - {error}")
        # context manager ensures session closed/rolled back correctly

    async def _process_due_outbox(self):
        """Reprend automatiquement les émissions persistées après un échec.

        L'outbox n'est ainsi plus dépendante d'un appel HTTP manuel. La ligne
        conserve son payload et son identifiant de corrélation, ce qui garantit
        qu'une reprise technique ne crée pas un nouveau jeu de scénario.
        """
        with session_factory() as session:
            result = await process_due_messages(session, limit=100)
            if result["processed"]:
                logger.info(
                    "Outbox processed %(processed)s message(s): %(sent)s sent, %(retry)s retry, %(failed)s failed",
                    result,
                )

    async def _process_queued_campaigns(self):
        """Fait avancer les campagnes une étape à la fois, de façon reprise-safe."""
        with session_factory() as session:
            result = await process_queued_campaigns(session, limit=5)
            if result["processed"]:
                logger.info("Qualification campaigns: %(processed)s progressed, %(completed)s completed", result)


# Global scheduler instance
_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler(poll_interval_seconds: int = 60) -> BackgroundScheduler:
    """
    Get or create the global scheduler instance.
    
    Args:
        poll_interval_seconds: Polling interval (default: 60s)
    
    Returns:
        BackgroundScheduler instance
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(poll_interval_seconds)
    return _scheduler


async def start_scheduler(poll_interval_seconds: int = 60):
    """
    Start the background scheduler.
    
    Args:
        poll_interval_seconds: Polling interval (default: 60s = 1 minute)
    """
    scheduler = get_scheduler(poll_interval_seconds)
    # During tests we avoid starting background tasks
    if getattr(settings, "testing", False):
        logger.info("Skipping scheduler start in testing mode")
        return

    await scheduler.start()


async def stop_scheduler():
    """Stop the background scheduler"""
    global _scheduler
    if getattr(settings, "testing", False):
        logger.info("Skipping scheduler stop in testing mode")
        _scheduler = None
        return

    if _scheduler:
        await _scheduler.stop()
        _scheduler = None
