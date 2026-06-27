"""Lectura del catálogo desde PostgreSQL (solo SELECT)."""
from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid
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

logger = logging.getLogger(__name__)

CATALOG_QUERY = """
    SELECT
        p.id AS product_id,
        pt."languageCode" AS language,
        pt.name AS product_name,
        pt.description AS product_description,
        COALESCE(string_agg(DISTINCT ct.name, ', '), 'Sin categoría') AS categories,
        COALESCE(string_agg(DISTINCT fvt.name, ', '), 'Sin atributos') AS attributes,
        COALESCE(string_agg(DISTINCT pv.sku, ', '), '') AS skus,
        COALESCE(string_agg(DISTINCT pot.name, ', '), '') AS options
    FROM product p
    JOIN product_translation pt ON p.id = pt."baseId" AND pt."languageCode" IN ('es', 'en')
    LEFT JOIN product_facet_values_facet_value pfv ON p.id = pfv."productId"
    LEFT JOIN facet_value_translation fvt ON pfv."facetValueId" = fvt."baseId" AND fvt."languageCode" = pt."languageCode"
    LEFT JOIN product_variant pv ON p.id = pv."productId"
    LEFT JOIN collection_product_variants_product_variant cpv ON pv.id = cpv."productVariantId"
    LEFT JOIN collection_translation ct ON cpv."collectionId" = ct."baseId" AND ct."languageCode" = pt."languageCode"
    LEFT JOIN product_variant_options_product_option pv_opt ON pv.id = pv_opt."productVariantId"
    LEFT JOIN product_option_translation pot ON pv_opt."productOptionId" = pot."baseId" AND pot."languageCode" = pt."languageCode"
    WHERE p."deletedAt" IS NULL
    {product_filter}
    GROUP BY p.id, pt."languageCode", pt.name, pt.description
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


def generate_product_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("utf-8")
    normalized = normalized.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized)
    return slug.strip("-")


def make_point_id(product_id: int, language: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{product_id}_{language}"))


def _format_product_row(row) -> dict:
    product_id, language, name, description, categories, attributes, skus, options = row

    slug = generate_product_slug(name)
    product_url = f"{SHOP_BASE_URL}/{language}/product/{slug}"

    text_to_embed = f"[{language.upper()}] Producto: {name}. "
    text_to_embed += f"URL de compra: {product_url}. "

    if categories != "Sin categoría":
        text_to_embed += f"Categorías: {categories}. "
    if attributes != "Sin atributos":
        text_to_embed += f"Atributos generales: {attributes}. "
    if options:
        text_to_embed += f"Opciones disponibles (Tallas/Tipos): {options}. "

    text_to_embed += f"Descripción: {description}"

    payload = {
        "product_id": product_id,
        "language": language,
        "document_type": "product_base",
        "name": name,
        "url": product_url,
        "categories": categories.split(", ") if categories != "Sin categoría" else [],
        "attributes": attributes.split(", ") if attributes != "Sin atributos" else [],
        "skus": skus.split(", ") if skus else [],
        "options": options.split(", ") if options else [],
    }

    return {"text": text_to_embed, "payload": payload}


def extract_product_catalog(
    product_id: Optional[int] = None,
    verbose: bool = False,
) -> List[dict]:
    """Extrae productos activos del catálogo. Solo lectura."""
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

        extracted = [_format_product_row(row) for row in rows]

        if verbose and extracted:
            logger.info("Extraidos %d productos/idiomas.", len(extracted))
            logger.debug("Muestra: %s", json.dumps(extracted[0]["payload"], ensure_ascii=False))

        return extracted

    except Exception:
        logger.exception("Error leyendo catálogo desde PostgreSQL")
        return []
