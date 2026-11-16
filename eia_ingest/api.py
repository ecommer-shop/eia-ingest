"""API REST para controlar la sincronización."""
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from eia_ingest.config import (
    COLLECTION_NAME,
    PG_DB,
    PG_HOST,
    PG_PASSWORD,
    PG_PORT,
    PG_SSL,
    PG_USER,
)
from eia_ingest.scheduler import sync_scheduler
from eia_ingest.security import require_valid_token
from eia_ingest.sync import delete_product, sync_catalog, sync_documents, sync_ui_guides

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


def run_delete_product(product_id: int):
    """Ejecutor de eliminación de producto en Qdrant."""
    try:
        logger.info("Iniciando delete (product_id=%s)", product_id)
        result = delete_product(product_id)
        logger.info("Delete completado: %s", result)
    except Exception as e:
        logger.exception("Error eliminando producto product_id=%s: %s", product_id, e)


@app.post("/sync", status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(
    background_tasks: BackgroundTasks,
    _token: dict = Depends(require_valid_token),
):
    """Sincroniza de forma incremental todo el catálogo."""
    background_tasks.add_task(run_sync_catalog)
    return {
        "status": "processing",
        "message": "Sincronización incremental del catálogo iniciada."
    }


@app.post("/sync/product/{product_id}", status_code=status.HTTP_202_ACCEPTED)
def trigger_product_sync(
    product_id: int,
    background_tasks: BackgroundTasks,
    _token: dict = Depends(require_valid_token),
):
    """Sincroniza un producto en específico."""
    background_tasks.add_task(run_sync_catalog, product_id)
    return {
        "status": "processing",
        "message": f"Sincronización del producto #{product_id} iniciada."
    }


# ============================================================================
# Nuevos endpoints: Documents (PDFs) y UI Guides
# ============================================================================

def run_sync_documents(tenant_id: str = "platform", folder: str = "policies"):
    """Ejecutor de sincronización de PDFs."""
    try:
        logger.info("Iniciando sync documents: tenant=%s, folder=%s", tenant_id, folder)
        result = sync_documents(tenant_id=tenant_id, folder=folder)
        logger.info("Sync documents completado: %s", result)
    except Exception as e:
        logger.exception("Error ejecutando sync documents: %s", e)


def run_sync_ui_guides(tenant_id: str = "platform", folder: str = "guides"):
    """Ejecutor de sincronización de guías UI."""
    try:
        logger.info("Iniciando sync ui-guides: tenant=%s, folder=%s", tenant_id, folder)
        result = sync_ui_guides(tenant_id=tenant_id, folder=folder)
        logger.info("Sync ui-guides completado: %s", result)
    except Exception as e:
        logger.exception("Error ejecutando sync ui-guides: %s", e)


@app.post("/sync/documents", status_code=status.HTTP_202_ACCEPTED)
def trigger_documents_sync(
    tenant_id: str = "platform",
    folder: str = "policies",
    background_tasks: BackgroundTasks = None,
    _token: dict = Depends(require_valid_token),
):
    """
    Sincroniza PDFs desde ./data/{tenant_id}/{folder}/

    Query params:
        - tenant_id: Nombre de la carpeta del tenant (default: platform)
        - folder: Subcarpeta dentro del tenant (default: policies, también: docs)
    """
    background_tasks.add_task(run_sync_documents, tenant_id, folder)
    return {
        "status": "processing",
        "message": f"Sincronización de documentos ({tenant_id}/{folder}) iniciada."
    }


@app.post("/sync/ui-guides", status_code=status.HTTP_202_ACCEPTED)
def trigger_ui_guides_sync(
    tenant_id: str = "platform",
    folder: str = "guides",
    background_tasks: BackgroundTasks = None,
    _token: dict = Depends(require_valid_token),
):
    """
    Sincroniza guías markdown desde ./data/{tenant_id}/{folder}/

    Query params:
        - tenant_id: Nombre de la carpeta del tenant (default: platform)
        - folder: Subcarpeta dentro del tenant (default: guides)
    """
    background_tasks.add_task(run_sync_ui_guides, tenant_id, folder)
    return {
        "status": "processing",
        "message": f"Sincronización de guías UI ({tenant_id}/{folder}) iniciada."
    }


# ============================================================================
# Webhook: eventos de producto (Vendure / admin externo) -> Qdrant
# ============================================================================

class ProductWebhookPayload(BaseModel):
    """Payload del webhook de eventos de producto."""

    event: Literal["created", "updated", "deleted"] = Field(
        ..., description="Tipo de evento: created | updated | deleted"
    )
    product_id: int = Field(..., gt=0, description="ID del producto en Vendure")
    tenant_id: str = Field(
        default="platform",
        description="Tenant destino (solo informativo; el sync usa el catálogo)",
    )


@app.post(
    "/webhooks/product",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_valid_token)],
)
def receive_product_webhook(
    payload: ProductWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """Recibe eventos de producto autenticados con JWT y ejecuta la acción en Qdrant.

    - created / updated -> re-sincroniza el producto desde PostgreSQL a Qdrant
    - deleted           -> elimina los puntos del producto en Qdrant
    """
    logger.info(
        "Webhook recibido: event=%s, product_id=%s, tenant_id=%s",
        payload.event,
        payload.product_id,
        payload.tenant_id,
    )

    if payload.event == "deleted":
        background_tasks.add_task(run_delete_product, payload.product_id)
        message = f"Eliminación del producto #{payload.product_id} iniciada."
    else:
        background_tasks.add_task(run_sync_catalog, payload.product_id)
        message = f"Sincronización del producto #{payload.product_id} iniciada."

    return {
        "status": "processing",
        "event": payload.event,
        "product_id": payload.product_id,
        "message": message,
    }


def run_dev():
    """Ejecuta el servidor de desarrollo de uvicorn."""
    import uvicorn
    uvicorn.run("eia_ingest.api:app", host="127.0.0.1", port=8000, reload=True)
