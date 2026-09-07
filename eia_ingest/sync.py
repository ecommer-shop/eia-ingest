"""Orquestador de sincronización: fuentes → Qdrant (catálogo, PDFs, guías).

Flujo general:
    1. Extraer contenido desde la fuente (PostgreSQL, PDF, Markdown)
    2. Normalizar a ChunkInput (dataclass unificada)
    3. Detectar cambios via doble hash (content_hash + payload_hash)
    4. Generar embeddings y upsert a Qdrant
    5. Limpiar puntos obsoletos (solo catálogo en sync completo)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointIdsList,
    VectorParams,
)

from eia_ingest.config import (
    BATCH_SIZE,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    VECTOR_SIZE,
)
from eia_ingest.embeddings import get_embeddings
from eia_ingest.point_builder import (
    build_payload,
    ChunkInput,
    content_hash,
    make_point_id,
    payload_hash,
)
from eia_ingest.qdrant_client import get_qdrant_client
from eia_ingest.readers.catalog_reader import extract_product_catalog
from eia_ingest.readers.pdf_reader import (
    extract_pending_documents,
    read_pdf_chunks,
)
from eia_ingest.readers.ui_guide_reader import (
    extract_ui_guides,
    read_guide_chunks,
)

logger = logging.getLogger(__name__)

# Filtros Qdrant para cada tipo de fuente
PRODUCT_FILTER = Filter(
    must=[FieldCondition(key="source_type", match=MatchValue(value="vendure_product"))]
)
DOCUMENT_FILTER = Filter(
    must=[FieldCondition(key="source_type", match=MatchValue(value="pdf"))]
)
GUIDE_FILTER = Filter(
    must=[FieldCondition(key="source_type", match=MatchValue(value="ui_guide_md"))]
)


# =============================================================================
# FUNCIONES INTERNAS
# =============================================================================


def _ensure_collection(client: QdrantClient) -> None:
    """Crea la colección si no existe y agrega índices faltantes."""
    required_indices = [
        "tenant_id",
        "content_type",
        "audience",
        "channels",
        "source_type",
    ]

    try:
        client.get_collection(collection_name=COLLECTION_NAME)
        collection_exists = True
    except Exception:
        collection_exists = False

    if not collection_exists:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info("Colección '%s' creada", COLLECTION_NAME)

    for field in required_indices:
        try:
            client.create_payload_index(
                COLLECTION_NAME, field, PayloadSchemaType.KEYWORD
            )
            logger.info("Índice '%s' agregado", field)
        except Exception:
            pass  # Índice ya existe

    logger.info("Colección '%s' lista con todos los índices", COLLECTION_NAME)


def _scroll_hashes_by_source_type(
    client: QdrantClient, source_type: str
) -> Dict[str, dict]:
    """Obtiene hashes de puntos existentes por tipo de fuente.

    Retorna dict mapeando point_id → {content_hash, payload_hash}.
    Se usa para detectar qué puntos cambiaron entre sincronizaciones.
    """
    hashes: Dict[str, dict] = {}
    offset = None
    source_filter = Filter(
        must=[FieldCondition(key="source_type", match=MatchValue(value=source_type))]
    )

    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=source_filter,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            hashes[str(point.id)] = {
                "payload_hash": payload.get("payload_hash", ""),
                "content_hash": payload.get("content_hash", ""),
            }
        if offset is None:
            break

    return hashes


def _scroll_point_ids_by_source_type(
    client: QdrantClient, source_type: str
) -> Set[str]:
    """Obtiene solo los IDs de puntos por tipo de fuente."""
    return set(_scroll_hashes_by_source_type(client, source_type).keys())


def _build_points_from_chunks(chunks: List[ChunkInput]) -> List[PointStruct]:
    """Genera embeddings y construye PointStructs listos para upsert."""
    if not chunks:
        return []

    texts = [chunk.text for chunk in chunks]
    vectors = get_embeddings(texts)

    return [
        PointStruct(
            id=make_point_id(chunk.tenant_id, chunk.source_id),
            payload=build_payload(chunk),
            vector=vector,
        )
        for chunk, vector in zip(chunks, vectors)
    ]


def _sync_chunks(
    chunks: List[ChunkInput],
    client: QdrantClient,
    stats: dict,
    source_type: str,
) -> Set[str]:
    """Sincroniza chunks a Qdrant con detección de cambios por hash.

    Lógica por cada chunk:
        - Nuevo point_id → INSERT (requiere embedding)
        - point_id existe + payload_hash cambió + content_hash cambió → UPDATE (requiere embedding)
        - point_id existe + payload_hash cambió + content_hash igual → META_ONLY (sin embedding)
        - point_id existe + sin cambios → SKIP

    Returns:
        Set de point IDs activos (para cleanup posterior de puntos obsoletos)
    """
    if not chunks:
        return set()

    active_ids: Set[str] = set()
    existing_hashes = _scroll_hashes_by_source_type(client, source_type)

    to_sync: List[ChunkInput] = []
    pending_stats: List[str] = []

    for chunk in chunks:
        point_id = make_point_id(chunk.tenant_id, chunk.source_id)
        active_ids.add(point_id)

        stored_state = existing_hashes.get(point_id)
        if stored_state is None:
            to_sync.append(chunk)
            pending_stats.append("inserted")
            continue

        current_content = content_hash(chunk.text)
        current_payload = payload_hash(chunk.text, chunk.metadata)
        stored_content = stored_state.get("content_hash", "")
        stored_payload = stored_state.get("payload_hash", "")

        if stored_payload == current_payload:
            stats["skipped"] += 1
            continue

        if stored_content != current_content:
            # Texto cambió → re-embedding necesario
            to_sync.append(chunk)
            pending_stats.append("updated")
        else:
            # Solo metadata cambió → actualizar payload sin re-embedding
            payload_only = build_payload(chunk)
            payload_only["content_hash"] = current_content
            payload_only["payload_hash"] = current_payload
            client.set_payload(
                collection_name=COLLECTION_NAME,
                points=[point_id],
                payload=payload_only,
            )
            stats["updated"] += 1
            logger.info("Metadata-only update: %s (%s)", point_id, source_type)

    # Procesar upserts en batches
    for i in range(0, len(to_sync), BATCH_SIZE):
        batch = to_sync[i : i + BATCH_SIZE]
        try:
            points = _build_points_from_chunks(batch)
            client.upsert(collection_name=COLLECTION_NAME, points=points)

            for action in pending_stats[i : i + len(batch)]:
                stats[action] += 1

            logger.info(
                "Batch %d: %d puntos sincronizados (%s)",
                i // BATCH_SIZE + 1,
                len(batch),
                source_type,
            )
        except Exception:
            logger.exception("Error en batch %d (%s)", i // BATCH_SIZE + 1, source_type)
            stats["failed"] += len(batch)

    return active_ids


# =============================================================================
# API PÚBLICA — CATÁLOGO
# =============================================================================


def sync_catalog(product_id: Optional[int] = None) -> dict:
    """Sincroniza el catálogo de productos desde PostgreSQL hacia Qdrant.

    Args:
        product_id: Si se especifica, sinc solo ese producto.
                    Si es None, sincronización completa con cleanup de obsoletos.
    """
    started = datetime.now(timezone.utc)
    stats = {
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "deleted": 0,
        "failed": 0,
        "total": 0,
    }

    products = extract_product_catalog(product_id=product_id, verbose=True)
    if not products:
        logger.warning("No hay productos para sincronizar")
        return {"status": "no_products", "stats": stats, "collection": COLLECTION_NAME}

    stats["total"] = len(products)
    client = get_qdrant_client()
    _ensure_collection(client)

    active_ids = _sync_chunks(products, client, stats, "vendure_product")

    # Cleanup solo en sync completo (product_id=None)
    if product_id is None:
        stale_ids = (
            _scroll_point_ids_by_source_type(client, "vendure_product") - active_ids
        )
        if stale_ids:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=PointIdsList(points=list(stale_ids)),
            )
            stats["deleted"] = len(stale_ids)
            logger.info("Eliminados %d vectores obsoletos", len(stale_ids))

    duration = (datetime.now(timezone.utc) - started).total_seconds()
    return {
        "status": "completed",
        "collection": COLLECTION_NAME,
        "source_type": "vendure_product",
        "embedding_model": EMBEDDING_MODEL,
        "vector_size": VECTOR_SIZE,
        "stats": stats,
        "duration_seconds": duration,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# API PÚBLICA — PDFs
# =============================================================================


def sync_documents(tenant_id: str = "platform", folder: str = "policies") -> dict:
    """Sincroniza PDFs desde ./data/{tenant_id}/{folder}/ hacia Qdrant.

    Args:
        tenant_id: Identificador del tenant (carpeta en data/).
        folder: Subcarpeta (policies, docs, company, etc.).
    """
    started = datetime.now(timezone.utc)
    stats = {
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "total_files": 0,
        "total_chunks": 0,
    }

    documents = extract_pending_documents(tenant_id, folder)
    stats["total_files"] = len(documents)

    if not documents:
        logger.warning("No hay PDFs para sincronizar en %s/%s", tenant_id, folder)
        return {"status": "no_documents", "stats": stats, "collection": COLLECTION_NAME}

    all_chunks: List[ChunkInput] = []
    for doc in documents:
        chunks = read_pdf_chunks(doc)
        all_chunks.extend(chunks)
        stats["total_chunks"] += len(chunks)

    if not all_chunks:
        return {"status": "no_chunks", "stats": stats, "collection": COLLECTION_NAME}

    client = get_qdrant_client()
    _ensure_collection(client)
    _sync_chunks(all_chunks, client, stats, "pdf")

    duration = (datetime.now(timezone.utc) - started).total_seconds()
    return {
        "status": "completed",
        "collection": COLLECTION_NAME,
        "source_type": "pdf",
        "tenant_id": tenant_id,
        "folder": folder,
        "stats": stats,
        "duration_seconds": duration,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# API PÚBLICA — GUÍAS UI
# =============================================================================


def sync_ui_guides(tenant_id: str = "platform", folder: str = "guides") -> dict:
    """Sincroniza guías markdown desde ./data/{tenant_id}/{folder}/ hacia Qdrant.

    Args:
        tenant_id: Identificador del tenant (carpeta en data/).
        folder: Subcarpeta (guides).
    """
    started = datetime.now(timezone.utc)
    stats = {
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "total_files": 0,
        "total_sections": 0,
    }

    guides = extract_ui_guides(tenant_id, folder)
    stats["total_files"] = len(guides)

    if not guides:
        logger.warning("No hay guías para sincronizar en %s/%s", tenant_id, folder)
        return {"status": "no_guides", "stats": stats, "collection": COLLECTION_NAME}

    all_chunks: List[ChunkInput] = []
    for guide in guides:
        chunks = read_guide_chunks(guide)
        all_chunks.extend(chunks)
        stats["total_sections"] += len(chunks)

    if not all_chunks:
        return {"status": "no_chunks", "stats": stats, "collection": COLLECTION_NAME}

    client = get_qdrant_client()
    _ensure_collection(client)
    _sync_chunks(all_chunks, client, stats, "ui_guide_md")

    duration = (datetime.now(timezone.utc) - started).total_seconds()
    return {
        "status": "completed",
        "collection": COLLECTION_NAME,
        "source_type": "ui_guide_md",
        "tenant_id": tenant_id,
        "folder": folder,
        "stats": stats,
        "duration_seconds": duration,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
