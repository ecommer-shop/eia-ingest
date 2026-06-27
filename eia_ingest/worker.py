"""Tasks de Celery para sincronización automática."""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded

from eia_ingest.config import (
    COLLECTION_NAME,
    PG_DB,
    PG_HOST,
    PG_PASSWORD,
    PG_PORT,
    PG_SSL,
    PG_USER,
    QDRANT_API_KEY,
    QDRANT_URL,
    REDIS_URL,
)

logs_dir = Path(__file__).resolve().parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(logs_dir / "celery.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

celery_app = Celery(
    "eia-ingest",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["eia_ingest.worker"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Bogota",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    task_soft_time_limit=1800,
    task_time_limit=1900,
    result_expires=3600,
    worker_send_task_events=True,
    task_track_started=True,
    task_routes={
        "eia_ingest.worker.sync_catalog_task": {"queue": "default"},
        "eia_ingest.worker.sync_single_product": {"queue": "processing"},
    },
)

celery_app.conf.beat_schedule = {
    "sync-catalog-every-30-min": {
        "task": "eia_ingest.worker.sync_catalog_task",
        "schedule": 30 * 60,
        "options": {"queue": "default"},
    },
    "health-check-every-5-min": {
        "task": "eia_ingest.worker.health_check",
        "schedule": 5 * 60,
        "options": {"queue": "default"},
    },
}


@celery_app.task(bind=True, name="eia_ingest.worker.sync_catalog_task")
def sync_catalog_task(self):
    from eia_ingest.sync import sync_catalog

    try:
        logger.info("Iniciando sync de catálogo (tarea %s)", self.request.id)
        result = sync_catalog()
        logger.info("Sync completado: %s", json.dumps(result))
        return result
    except SoftTimeLimitExceeded:
        logger.error("Sync excedió el límite de tiempo")
        return {"status": "timeout"}
    except Exception as exc:
        logger.exception("Error en sync_catalog_task")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="eia_ingest.worker.sync_single_product")
def sync_single_product(self, product_id: int):
    from eia_ingest.sync import sync_catalog

    try:
        logger.info("Sync producto %s (tarea %s)", product_id, self.request.id)
        return sync_catalog(product_id=product_id)
    except Exception as exc:
        logger.exception("Error sincronizando producto %s", product_id)
        raise self.retry(exc=exc)


@celery_app.task(name="eia_ingest.worker.health_check")
def health_check():
    status = {"postgres": False, "qdrant": False, "redis": False}

    try:
        import psycopg2

        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD,
            sslmode=PG_SSL,
        )
        conn.set_session(readonly=True, autocommit=True)
        conn.close()
        status["postgres"] = True
    except Exception:
        pass

    try:
        from eia_ingest.qdrant_client import get_qdrant_client

        get_qdrant_client().get_collection(COLLECTION_NAME)
        status["qdrant"] = True
    except Exception:
        pass

    try:
        from redis import Redis

        Redis.from_url(REDIS_URL).ping()
        status["redis"] = True
    except Exception:
        pass

    return {
        "healthy": all(status.values()),
        "services": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
