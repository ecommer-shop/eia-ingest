"""API REST para controlar la sincronización."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, status
from fastapi.responses import JSONResponse

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
)
from eia_ingest.scheduler import sync_scheduler
from eia_ingest.sync import sync_catalog

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Maneja eventos de inicio y fin de vida de la aplicación."""
    logger.info("Starting periodic sync scheduler...")
    sync_scheduler.start()
    yield
    logger.info("Stopping periodic sync scheduler...")
    sync_scheduler.stop()


app = FastAPI(
    title="EIA Ingest API",
    description="API para orquestar la sincronización de catálogo PostgreSQL a Qdrant con Azure OpenAI",
    version="0.5.0",
    lifespan=lifespan,
)


@app.get("/")
def read_root():
    """Retorna información general de la API."""
    return {
        "name": "eia-ingest-api",
        "status": "online",
        "version": "0.5.0",
        "documentation": "/docs",
        "scheduler": {
            "interval_hours": 24,
            "last_run": sync_scheduler.last_run.isoformat() if sync_scheduler.last_run else None
        }
    }


@app.get("/health")
def get_health():
    """
    Endpoint de salud para Railway u orquestadores.
    
    Verifica la conexión a PostgreSQL y Qdrant.
    """
    services = {"postgres": False, "qdrant": False}

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
        services["postgres"] = True
    except Exception:
        pass

    try:
        from eia_ingest.qdrant_client import get_qdrant_client

        get_qdrant_client().get_collection(COLLECTION_NAME)
        services["qdrant"] = True
    except Exception:
        pass

    if not all(services.values()):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "details": services}
        )
    return {"status": "healthy", "details": services}


def run_sync_catalog(product_id: int | None = None):
    """Ejecutor de sincronización."""
    try:
        logger.info("Iniciando sync (product_id=%s)", product_id)
        result = sync_catalog(product_id=product_id)
        logger.info("Sync completado: %s", result)
    except Exception as e:
        logger.exception("Error ejecutando sync para product_id=%s: %s", product_id, e)


@app.post("/sync", status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(background_tasks: BackgroundTasks):
    """Sincroniza de forma incremental todo el catálogo."""
    background_tasks.add_task(run_sync_catalog)
    return {
        "status": "processing",
        "message": "Sincronización incremental del catálogo iniciada."
    }


@app.post("/sync/product/{product_id}", status_code=status.HTTP_202_ACCEPTED)
def trigger_product_sync(product_id: int, background_tasks: BackgroundTasks):
    """Sincroniza un producto en específico."""
    background_tasks.add_task(run_sync_catalog, product_id)
    return {
        "status": "processing",
        "message": f"Sincronización del producto #{product_id} iniciada."
    }


def run_dev():
    """Ejecuta el servidor de desarrollo de uvicorn."""
    import uvicorn
    uvicorn.run("eia_ingest.api:app", host="127.0.0.1", port=8000, reload=True)

hola=""