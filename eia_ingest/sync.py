"""Orquestador de sincronización: PostgreSQL → Qdrant."""
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

from eia_ingest.catalog_reader import extract_product_catalog, make_point_id
from eia_ingest.config import (
    BATCH_SIZE,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    VECTOR_SIZE,
)
from eia_ingest.embeddings import get_embeddings
from eia_ingest.qdrant_client import get_qdrant_client

logger = logging.getLogger(__name__)

PRODUCT_FILTER = Filter(
    must=[FieldCondition(key="document_type", match=MatchValue(value="product_base"))]
)


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_collection(client: QdrantClient) -> None:
    try:
        client.get_collection(collection_name=COLLECTION_NAME)
        return
    except Exception:
        pass

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    client.create_payload_index(COLLECTION_NAME, "language", PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION_NAME, "product_id", PayloadSchemaType.INTEGER)
    client.create_payload_index(COLLECTION_NAME, "document_type", PayloadSchemaType.KEYWORD)
    logger.info("Coleccion '%s' creada (%d dims, %s)", COLLECTION_NAME, VECTOR_SIZE, EMBEDDING_MODEL)


def scroll_product_hashes(client: QdrantClient) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    offset = None

    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=PRODUCT_FILTER,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            hashes[str(point.id)] = (point.payload or {}).get("content_hash", "")
        if offset is None:
            break

    return hashes


def scroll_product_point_ids(client: QdrantClient) -> Set[str]:
    return set(scroll_product_hashes(client).keys())


def prepare_product(item: dict) -> Tuple[str, str, dict]:
    content_hash = compute_content_hash(item["text"])
    payload = {
        **item["payload"],
        "content_hash": content_hash,
        "embedding_model": EMBEDDING_MODEL,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    point_id = make_point_id(payload["product_id"], payload["language"])
    return point_id, content_hash, payload


def build_points(batch: List[dict]) -> List[PointStruct]:
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
    Sincroniza el catálogo SQL -> Qdrant.

    - Nuevo producto       -> upsert
    - Producto modificado  -> re-upsert si cambió el contenido
    - Sin cambios          -> omitido
    - Eliminado en SQL     -> borrado en Qdrant
    """
    started = datetime.now(timezone.utc)
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "deleted": 0, "failed": 0, "total": 0}

    products = extract_product_catalog(product_id=product_id, verbose=True)
    if not products:
        logger.warning("No hay productos para sincronizar")
        return {"status": "no_products", "stats": stats, "collection": COLLECTION_NAME}

    stats["total"] = len(products)
    qdrant = get_qdrant_client()
    ensure_collection(qdrant)
    existing_hashes = scroll_product_hashes(qdrant)

    to_sync: List[dict] = []
    pending_stats: List[str] = []
    active_point_ids: Set[str] = set()

    for item in products:
        point_id, content_hash, payload = prepare_product(item)
        active_point_ids.add(point_id)

        stored_hash = existing_hashes.get(point_id)
        if stored_hash is None:
            to_sync.append({"point_id": point_id, "text": item["text"], "payload": payload})
            pending_stats.append("inserted")
        elif stored_hash != content_hash:
            to_sync.append({"point_id": point_id, "text": item["text"], "payload": payload})
            pending_stats.append("updated")
        else:
            stats["skipped"] += 1

    for i in range(0, len(to_sync), BATCH_SIZE):
        batch = to_sync[i : i + BATCH_SIZE]
        try:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=build_points(batch))

            for action in pending_stats[i : i + len(batch)]:
                stats[action] += 1

            logger.info("Batch %d: %d puntos sincronizados", i // BATCH_SIZE + 1, len(batch))
        except Exception:
            logger.exception("Error en batch %d", i // BATCH_SIZE + 1)
            stats["failed"] += len(batch)

    if product_id is None:
        stale_ids = scroll_product_point_ids(qdrant) - active_point_ids
        if stale_ids:
            qdrant.delete(
                collection_name=COLLECTION_NAME,
                points_selector=PointIdsList(points=list(stale_ids)),
            )
            stats["deleted"] = len(stale_ids)
            logger.info("Eliminados %d vectores obsoletos", len(stale_ids))

    duration = (datetime.now(timezone.utc) - started).total_seconds()
    result = {
        "status": "completed",
        "collection": COLLECTION_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "vector_size": VECTOR_SIZE,
        "stats": stats,
        "duration_seconds": duration,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Sync completado: %s", stats)
    return result
