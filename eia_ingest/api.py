"""API REST para controlar la sincronización."""
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse

from eia_ingest.sync import sync_catalog
from eia_ingest.worker import health_check

logger = logging.getLogger(__name__)

app = FastAPI(
    title="EIA Ingest API",
    description="API para orquestar la sincronización de catálogo PostgreSQL a Qdrant con Azure OpenAI",
    version="0.3.0",
)


@app.get("/")
def read_root():
    """Retorna información general de la API."""
    return {
        "name": "eia-ingest-api",
        "status": "online",
        "version": "0.3.0",
        "documentation": "/docs"
    }


@app.get("/health")
def get_health():
    """
    Endpoint de salud para Railway u orquestadores.
    
    Verifica la conexión a PostgreSQL, Qdrant y Redis.
    """
    check = health_check()
    if not check["healthy"]:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "details": check}
        )
    return {"status": "healthy", "details": check}


def run_sync_catalog(product_id: int | None = None):
    """Ejecutor de sincronización en segundo plano."""
    try:
        logger.info("Iniciando sync en background (product_id=%s)", product_id)
        sync_catalog(product_id=product_id)
    except Exception as e:
        logger.exception("Error ejecutando sync en background para product_id=%s: %s", product_id, e)


@app.post("/sync", status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(background_tasks: BackgroundTasks):
    """Sincroniza de forma incremental todo el catálogo en segundo plano."""
    background_tasks.add_task(run_sync_catalog)
    return {
        "status": "processing",
        "message": "Sincronización incremental del catálogo iniciada en segundo plano."
    }


@app.post("/sync/product/{product_id}", status_code=status.HTTP_202_ACCEPTED)
def trigger_product_sync(product_id: int, background_tasks: BackgroundTasks):
    """Sincroniza un producto en específico en segundo plano."""
    background_tasks.add_task(run_sync_catalog, product_id)
    return {
        "status": "processing",
        "message": f"Sincronización del producto #{product_id} iniciada en segundo plano."
    }


def run_dev():
    """Ejecuta el servidor de desarrollo de uvicorn."""
    import uvicorn
    uvicorn.run("eia_ingest.api:app", host="127.0.0.1", port=8000, reload=True)

hola=""