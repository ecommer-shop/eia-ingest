"""Lectura del catálogo desde PostgreSQL (solo SELECT).

La SQL retorna una fila por canal Vendure (product_channels_channel).
Antes de crear ChunkInputs, se agrupan por (product_id, language) para
que el mismo producto en múltiples canales genere UN solo punto en Qdrant.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import List, Optional

import psycopg2
import psycopg2.extensions

from eia_ingest.config import (
    PG_DB,
    PG_HOST,
    PG_PASSWORD,
    PG_PORT,
    PG_SSL,
    PG_USER,
    SHOP_BASE_URL,
)
from eia_ingest.constants import AUDIENCE_CLIENTE
from eia_ingest.point_builder import ChunkInput

logger = logging.getLogger(__name__)

CATALOG_QUERY = """
    SELECT
        p.id AS product_id,
        c.id AS channel_id,
        c.code AS channel_code,
        c.token AS channel_token,
        pt."languageCode" AS language,
        pt.name AS product_name,
        pt.description AS product_description,
        pt.slug AS product_slug,
        COALESCE(string_agg(DISTINCT ct.name, ', '), 'Sin categoría') AS categories,
        COALESCE(string_agg(DISTINCT fvt.name, ', '), 'Sin atributos') AS attributes,
        COALESCE(string_agg(DISTINCT pv.sku, ', '), '') AS skus,
        COALESCE(string_agg(DISTINCT pot.name, ', '), '') AS options
    FROM product p
    JOIN product_translation pt ON p.id = pt."baseId" AND pt."languageCode" IN ('es', 'en')
    JOIN product_channels_channel pcc ON pcc."productId" = p.id
    JOIN channel c ON c.id = pcc."channelId"
    LEFT JOIN product_facet_values_facet_value pfv ON p.id = pfv."productId"
    LEFT JOIN facet_value_translation fvt ON pfv."facetValueId" = fvt."baseId" AND fvt."languageCode" = pt."languageCode"
    LEFT JOIN product_variant pv ON p.id = pv."productId"
    LEFT JOIN collection_product_variants_product_variant cpv ON pv.id = cpv."productVariantId"
    LEFT JOIN collection_translation ct ON cpv."collectionId" = ct."baseId" AND ct."languageCode" = pt."languageCode"
    LEFT JOIN product_variant_options_product_option pv_opt ON pv.id = pv_opt."productVariantId"
    LEFT JOIN product_option_translation pot ON pv_opt."productOptionId" = pot."baseId" AND pot."languageCode" = pt."languageCode"
    WHERE p."deletedAt" IS NULL
        AND p.enabled = true
    {product_filter}
    GROUP BY p.id, c.id, c.code, c.token, pt."languageCode", pt.name, pt.description, pt.slug
"""


def _assert_readonly_query(query: str) -> None:
    normalized = query.strip().upper()
    if not normalized.startswith("SELECT"):
        raise ValueError("Solo se permiten consultas SELECT en la base de datos.")


def _readonly_connection() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        sslmode=PG_SSL,
    )
    conn.set_session(readonly=True, autocommit=True)
    return conn


DEFAULT_CHANNEL_CODE = "__default_channel__"
PLATFORM_TENANT_ID = "platform"


def generate_product_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("utf-8")
    normalized = normalized.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized)
    return slug.strip("-")


def _row_to_chunk_input(
    row,
    tenant_id: str = "platform",
    channels_info: Optional[List[dict]] = None,
) -> ChunkInput:
    """Convierte datos de producto (agrupados por canal) a ChunkInput unificado.

    Args:
        row: Tupla con los campos del producto (sin canal).
        tenant_id: Identificador del tenant.
        channels_info: Lista de dicts con info de cada canal:
            [{"channel_id": 1, "channel_code": "sol-y-luna",
              "channel_token": "sol-y-luna-token"}, ...]
    """
    (
        product_id,
        language,
        name,
        description,
        slug,
        categories,
        attributes,
        skus,
        options,
    ) = row

    if channels_info is None:
        channels_info = []

    product_slug = slug if slug else generate_product_slug(name)
    product_url = f"{SHOP_BASE_URL}/{language}/product/{product_slug}"

    # Texto para embedding
    text_to_embed = f"[{language.upper()}] Producto: {name}. "
    text_to_embed += f"URL de compra: {product_url}. "

    if categories != "Sin categoría":
        text_to_embed += f"Categorías: {categories}. "
    if attributes != "Sin atributos":
        text_to_embed += f"Atributos generales: {attributes}. "
    if options:
        text_to_embed += f"Opciones disponibles (Tallas/Tipos): {options}. "

    text_to_embed += f"Descripción: {description}"

    # Metadata — incluye info de todos los canales del producto
    channel_codes = [c["channel_code"] for c in channels_info]
    channel_tokens = [c["channel_token"] for c in channels_info]
    channel_ids = [c["channel_id"] for c in channels_info]

    metadata = {
        "product_id": product_id,
        "name": name,
        "url": product_url,
        "categories": [] if not categories or categories == "Sin categoría" else categories.split(", "),
        "attributes": [] if not attributes or attributes == "Sin atributos" else attributes.split(", "),
        "skus": [] if not skus else skus.split(", "),
        "options": [] if not options else options.split(", "),
        "language": language,
        "channel_ids": channel_ids,
        "channel_codes": channel_codes,
        "channel_tokens": channel_tokens,
    }

    # source_id channel-agnostic: mismo ID sin importar el canal
    source_id = f"product:{product_id}:{language}"

    return ChunkInput(
        tenant_id=tenant_id,
        content_type="CATALOGO",
        audience=AUDIENCE_CLIENTE,
        channels=["web", "whatsapp", "instagram", "messenger"],
        text=text_to_embed,
        source_type="vendure_product",
        source_id=source_id,
        metadata=metadata,
    )


def extract_product_catalog(
    product_id: Optional[int] = None,
    verbose: bool = False,
    tenant_id: str = "platform",
) -> List[ChunkInput]:
    """Extrae productos activos del catálogo y los retorna como ChunkInputs.

    La SQL retorna una fila por canal Vendure. Esta función agrupa por
    (product_id, language) para que cada producto genere UN solo punto
    en Qdrant, con la info de todos los canales en metadata.

    Args:
        product_id: Filtrar por producto específico (opcional).
        verbose: Loggear información adicional.
        tenant_id: Identificador del tenant (default: platform).

    Returns:
        Lista de ChunkInput listos para sincronizar.
    """
    product_filter = ""
    params: tuple = ()
    if product_id is not None:
        product_filter = "AND p.id = %s"
        params = (product_id,)

    query = CATALOG_QUERY.format(product_filter=product_filter)
    _assert_readonly_query(query)

    try:
        with _readonly_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        # Agrupar por (product_id, language) para deduplicar canales
        grouped: dict = {}
        for row in rows:
            (
                pid, channel_id, channel_code, channel_token,
                language, name, description, slug,
                categories, attributes, skus, options,
            ) = row

            key = (pid, language)
            if key not in grouped:
                grouped[key] = {
                    "product_row": (pid, language, name, description, slug,
                                    categories, attributes, skus, options),
                    "channels": [],
                }
            grouped[key]["channels"].append({
                "channel_id": channel_id,
                "channel_code": channel_code,
                "channel_token": channel_token,
            })

        chunks = [
            _row_to_chunk_input(
                data["product_row"],
                tenant_id=tenant_id,
                channels_info=data["channels"],
            )
            for data in grouped.values()
        ]

        if verbose and chunks:
            logger.info("Extraídos %d productos/idiomas (de %d filas SQL).",
                        len(chunks), len(rows))
            first = chunks[0]
            logger.debug("Muestra: tenant=%s, source=%s, canales=%s",
                         first.tenant_id, first.source_id,
                         first.metadata.get("channel_codes"))

        return chunks

    except Exception:
        logger.exception("Error leyendo catálogo desde PostgreSQL")
        return []