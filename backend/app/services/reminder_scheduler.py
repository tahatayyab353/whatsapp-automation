import asyncio
from typing import Optional
from app.core.logging import logger
from app.db.database import SessionLocal
from app.services.reminder_service import reminder_service


class ReminderScheduler:
    """
    Periodic background runner that discovers and processes due appointment reminders.
    Runs inside FastAPI lifespan in production and can be paused/triggered deterministically.
    """

    def __init__(self, interval_seconds: float = 60.0):
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False

    async def start(self) -> None:
        """Starts the background periodic reminder processor loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Started Appointment Reminder Scheduler (interval=%.1fs)", self.interval_seconds)

    async def stop(self) -> None:
        """Stops the background periodic reminder processor loop cleanly."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Stopped Appointment Reminder Scheduler")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                db = SessionLocal()
                try:
                    await reminder_service.process_due_reminders(db=db)
                finally:
                    db.close()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Unexpected error in reminder scheduler loop: %s", str(exc), exc_info=True)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break


reminder_scheduler = ReminderScheduler(interval_seconds=60.0)
