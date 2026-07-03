"""Orquestador de sincronización: PostgreSQL → Qdrant (catálogo, PDFs, guías)."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

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
    content_hash as compute_content_hash_from_text,
    make_point_id,
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

# Filtros para cada tipo de contenido
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
# UTILIDADES
# =============================================================================

def content_hash(text: str) -> str:
    """Hash del texto para embedding."""
    return compute_content_hash_from_text(text)


def payload_hash(text: str, metadata: dict) -> str:
    """
    Hash del texto + metadata.
    Se usa para detectar cambios en el contenido O en los metadatos.
    """
    import json
    payload_for_hash = {
        "text": text,
        "metadata": metadata,
    }
    payload_json = json.dumps(payload_for_hash, sort_keys=True, default=str)
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


# =============================================================================
# CATÁLOGO (mantiene compatibilidad hacia atrás)
# =============================================================================

def _ensure_collection(client: QdrantClient) -> None:
    """
    Crea la colección si no existe, y asegura que todos los índices estén presentes.
    Si la colección ya existe, agrega los índices faltantes.
    """
    required_indices = [
        "tenant_id",
        "content_type",
        "audience",
        "channels",
        "source_type",
    ]

    # Verificar si la colección existe
    try:
        client.get_collection(collection_name=COLLECTION_NAME)
        collection_exists = True
    except Exception:
        collection_exists = False

    if not collection_exists:
        # Crear colección nueva
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info("Colección '%s' creada", COLLECTION_NAME)

    # Agregar índices faltantes (si la colección ya existía)
    for field in required_indices:
        try:
            # Intentar crear el índice - si ya existe lanza excepción
            client.create_payload_index(COLLECTION_NAME, field, PayloadSchemaType.KEYWORD)
            logger.info("Índice '%s' agregado", field)
        except Exception:
            # El índice ya existe, continuar
            pass

    logger.info("Colección '%s' lista con todos los índices", COLLECTION_NAME)


def _scroll_hashes_by_source_type(client: QdrantClient, source_type: str) -> Dict[str, str]:
    """Obtiene hashes de puntos por tipo de fuente."""
    hashes: Dict[str, str] = {}
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
            # Usar payload_hash para detectar cambios en texto O metadata
            hashes[str(point.id)] = (point.payload or {}).get("payload_hash", "")
        if offset is None:
            break

    return hashes


def _scroll_point_ids_by_source_type(client: QdrantClient, source_type: str) -> Set[str]:
    """Obtiene IDs de puntos por tipo de fuente."""
    return set(_scroll_hashes_by_source_type(client, source_type).keys())


def _build_points_from_chunks(chunks: List[ChunkInput]) -> List[PointStruct]:
    """Construye PointStructs desde ChunkInputs."""
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
    """
    Sincroniza chunks a Qdrant, detectando cambios por hash.

    Returns:
        Set de IDs activos para cleanup posterior
    """
    if not chunks:
        return set()

    active_ids: Set[str] = set()
    existing_hashes = _scroll_hashes_by_source_type(client, source_type)

    to_sync: List[ChunkInput] = []
    pending_stats: List[str] = []

    for chunk in chunks:
        point_id = make_point_id(chunk.tenant_id, chunk.source_id)
        # Usar payload_hash para detectar cambios en texto O metadata
        chunk_hash = payload_hash(chunk.text, chunk.metadata)
        active_ids.add(point_id)

        stored_hash = existing_hashes.get(point_id)
        if stored_hash is None:
            to_sync.append(chunk)
            pending_stats.append("inserted")
        elif stored_hash != chunk_hash:
            to_sync.append(chunk)
            pending_stats.append("updated")
        else:
            stats["skipped"] += 1

    for i in range(0, len(to_sync), BATCH_SIZE):
        batch = to_sync[i : i + BATCH_SIZE]
        try:
            points = _build_points_from_chunks(batch)
            client.upsert(collection_name=COLLECTION_NAME, points=points)

            for action in pending_stats[i : i + len(batch)]:
                stats[action] += 1

            logger.info("Batch %d: %d puntos sincronizados (%s)", i // BATCH_SIZE + 1, len(batch), source_type)
        except Exception:
            logger.exception("Error en batch %d (%s)", i // BATCH_SIZE + 1, source_type)
            stats["failed"] += len(batch)

    return active_ids


# =============================================================================
# API PÚBLICA - CATÁLOGO (mantiene compatibilidad exacta)
# =============================================================================

def compute_content_hash(text: str) -> str:
    """Mantiene compatibilidad hacia atrás."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_collection() -> None:
    """Mantiene compatibilidad hacia atrás."""
    client = get_qdrant_client()
    _ensure_collection(client)


def scroll_product_hashes(client: Optional[QdrantClient] = None) -> Dict[str, str]:
    """Mantiene compatibilidad hacia atrás."""
    if client is None:
        client = get_qdrant_client()
    return _scroll_hashes_by_source_type(client, "vendure_product")


def scroll_product_point_ids(client: Optional[QdrantClient] = None) -> Set[str]:
    """Mantiene compatibilidad hacia atrás."""
    if client is None:
        client = get_qdrant_client()
    return set(scroll_product_hashes(client).keys())


def prepare_product(item: dict) -> Tuple[str, str, dict]:
    """Mantiene compatibilidad hacia atrás."""
    content_hash_val = compute_content_hash(item["text"])
    payload = {
        **item["payload"],
        "content_hash": content_hash_val,
        "embedding_model": EMBEDDING_MODEL,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    point_id = make_point_id(payload.get("product_id", 0), payload.get("language", "es"))
    return point_id, content_hash_val, payload


def build_points(batch: List[dict]) -> List[PointStruct]:
    """Mantiene compatibilidad hacia atrás."""
    texts = [entry["text"] for entry in batch]
    vectors = get_embeddings(texts)
    return [
        PointStruct(
            id=entry["point_id"],
            payload=entry["payload"],
            vector=vector,
        )
        for entry, vector in zip(batch, vectors)
    ]


def sync_catalog(product_id: Optional[int] = None) -> dict:
    """
    Sincroniza el catálogo SQL → Qdrant.
    Usa ChunkInput unificado para mantener estructura consistente.
    """
    started = datetime.now(timezone.utc)
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "deleted": 0, "failed": 0, "total": 0}

    # Extraer como ChunkInputs
    products = extract_product_catalog(product_id=product_id, verbose=True)
    if not products:
        logger.warning("No hay productos para sincronizar")
        return {"status": "no_products", "stats": stats, "collection": COLLECTION_NAME}

    stats["total"] = len(products)
    client = get_qdrant_client()
    _ensure_collection(client)
    existing_hashes = scroll_product_hashes(client)

    to_sync: List[ChunkInput] = []
    pending_stats: List[str] = []
    active_point_ids: Set[str] = set()

    for chunk in products:
        point_id = make_point_id(chunk.tenant_id, chunk.source_id)
        # Use payload_hash for consistency with stored hashes
        chunk_hash = payload_hash(chunk.text, chunk.metadata)
        active_point_ids.add(point_id)

        stored_hash = existing_hashes.get(point_id)
        if stored_hash is None:
            to_sync.append(chunk)
            pending_stats.append("inserted")
        elif stored_hash != chunk_hash:
            to_sync.append(chunk)
            pending_stats.append("updated")
        else:
            stats["skipped"] += 1

    for i in range(0, len(to_sync), BATCH_SIZE):
        batch = to_sync[i : i + BATCH_SIZE]
        try:
            points = _build_points_from_chunks(batch)
            client.upsert(collection_name=COLLECTION_NAME, points=points)

            for action in pending_stats[i : i + len(batch)]:
                stats[action] += 1

            logger.info("Batch %d: %d productos sincronizados", i // BATCH_SIZE + 1, len(batch))
        except Exception:
            logger.exception("Error en batch %d", i // BATCH_SIZE + 1)
            stats["failed"] += len(batch)

    if product_id is None:
        stale_ids = scroll_product_point_ids(client) - active_point_ids
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
# API PÚBLICA - PDFs y GUÍAS UI
# =============================================================================

def sync_documents(tenant_id: str = "platform", folder: str = "policies") -> dict:
    """
    Sincroniza PDFs desde ./data/{tenant_id}/{folder}/

    Args:
        tenant_id: Identificador del tenant (carpeta en data/)
        folder: Subcarpeta (policies, docs)

    Returns:
        Estadísticas de la sincronización
    """
    started = datetime.now(timezone.utc)
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0, "total_files": 0, "total_chunks": 0}

    # Extraer documentos
    documents = extract_pending_documents(tenant_id, folder)
    stats["total_files"] = len(documents)

    if not documents:
        logger.warning("No hay PDFs para sincronizar en %s/%s", tenant_id, folder)
        return {"status": "no_documents", "stats": stats, "collection": COLLECTION_NAME}

    # Convertir a chunks
    all_chunks: List[ChunkInput] = []
    for doc in documents:
        chunks = read_pdf_chunks(doc)
        all_chunks.extend(chunks)
        stats["total_chunks"] += len(chunks)

    if not all_chunks:
        return {"status": "no_chunks", "stats": stats, "collection": COLLECTION_NAME}

    # Sincronizar
    client = get_qdrant_client()
    _ensure_collection(client)

    active_ids = _sync_chunks(all_chunks, client, stats, "pdf")

    # Cleanup de PDFs eliminados (opcional)
    # stale_ids = _scroll_point_ids_by_source_type(client, "pdf") - active_ids

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


def sync_ui_guides(tenant_id: str = "platform", folder: str = "guides") -> dict:
    """
    Sincroniza guías markdown desde ./data/{tenant_id}/{folder}/

    Args:
        tenant_id: Identificador del tenant (carpeta en data/)
        folder: Subcarpeta (guides)

    Returns:
        Estadísticas de la sincronización
    """
    started = datetime.now(timezone.utc)
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0, "total_files": 0, "total_sections": 0}

    # Extraer guías
    guides = extract_ui_guides(tenant_id, folder)
    stats["total_files"] = len(guides)

    if not guides:
        logger.warning("No hay guías para sincronizar en %s/%s", tenant_id, folder)
        return {"status": "no_guides", "stats": stats, "collection": COLLECTION_NAME}

    # Convertir a chunks
    all_chunks: List[ChunkInput] = []
    for guide in guides:
        chunks = read_guide_chunks(guide)
        all_chunks.extend(chunks)
        stats["total_sections"] += len(chunks)

    if not all_chunks:
        return {"status": "no_chunks", "stats": stats, "collection": COLLECTION_NAME}

    # Sincronizar
    client = get_qdrant_client()
    _ensure_collection(client)

    active_ids = _sync_chunks(all_chunks, client, "ui_guide_md")

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