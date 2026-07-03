"""Scheduler simple para sincronización periódica."""
import logging
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PeriodicScheduler:
    """Ejecuta una tarea periódicamente en un hilo separado."""

    def __init__(self, interval_seconds: int, task_func):
        self.interval_seconds = interval_seconds
        self.task_func = task_func
        self._thread = None
        self._stop_event = threading.Event()
        self._last_run = None

    def start(self):
        """Inicia el scheduler en un hilo separado."""
        if self._thread and self._thread.is_alive():
            logger.warning("Scheduler already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.name = "periodic_scheduler"
        self._thread.start()
        logger.info("Scheduler started (interval: %d seconds)", self.interval_seconds)

    def stop(self):
        """Detiene el scheduler."""
        if not self._thread or not self._thread.is_alive():
            logger.warning("Scheduler not running")
            return

        logger.info("Scheduler stopping...")
        self._stop_event.set()
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            logger.error("Scheduler did not stop gracefully")
        else:
            logger.info("Scheduler stopped")

    def _run_loop(self):
        """Bucle principal del scheduler."""
        while not self._stop_event.is_set():
            try:
                logger.info("Running scheduled task at %s", datetime.now(timezone.utc).isoformat())
                self.task_func()
                self._last_run = datetime.now(timezone.utc)
            except Exception:
                logger.exception("Error running scheduled task")

            # Esperar el intervalo o hasta que se detenga
            self._stop_event.wait(timeout=self.interval_seconds)

    @property
    def last_run(self) -> datetime | None:
        """Fecha y hora de la última ejecución."""
        return self._last_run


# Instancia global para sincronización diaria (24 horas = 86400 segundos)
sync_scheduler = PeriodicScheduler(
    interval_seconds=86400,  # 24 horas
    task_func=lambda: __import__("eia_ingest.sync", fromlist=["sync_catalog"]).sync_catalog()
)
