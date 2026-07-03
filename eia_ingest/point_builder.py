"""Constructor de payloads unificado para todas las fuentes de contenido."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


@dataclass
class ChunkInput:
    """Input unificado para cualquier tipo de contenido a ingestar."""
    tenant_id: str          # "tienda-camisetas-xyz" o "platform"
    content_type: str       # CATALOGO | POLITICAS | PAGOS | SOPORTE | GUIA_UI
    audience: str           # CLIENTE | COMERCIANTE
    channels: list[str]     # ["web", "whatsapp", ...]
    text: str
    source_type: str        # vendure_product | pdf | ui_guide_md
    source_id: str          # product:123 | politica_devoluciones.pdf#chunk_3
    metadata: dict = None  # arbitrary additional data

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def content_hash(text: str) -> str:
    """Hash del texto (para embedding)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def payload_hash(text: str, metadata: dict) -> str:
    """
    Hash del texto + metadata.
    Se usa para detectar cambios en contenido O metadatos.
    """
    payload_for_hash = {
        "text": text,
        "metadata": metadata,
    }
    payload_json = json.dumps(payload_for_hash, sort_keys=True, default=str)
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def make_point_id(tenant_id: str, source_id: str) -> str:
    """Genera ID determinista basado en tenant + source."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{tenant_id}:{source_id}"))


def build_payload(chunk: ChunkInput) -> dict:
    """
    Construye el payload final para Qdrant.
    Este es el único formato que espera el pipeline de ingesta.
    """
    return {
        "tenant_id": chunk.tenant_id,
        "content_type": chunk.content_type,
        "audience": chunk.audience,
        "channels": chunk.channels,
        "text": chunk.text,
        "source_type": chunk.source_type,
        "source_id": chunk.source_id,
        "metadata": chunk.metadata,
        "content_hash": content_hash(chunk.text),
        "payload_hash": payload_hash(chunk.text, chunk.metadata),
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }