"""Lectura de guías UI desde markdown."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from eia_ingest.chunking import chunk_markdown_by_headers
from eia_ingest.config import DATA_FOLDER
from eia_ingest.constants import AUDIENCE_COMERCIANTE
from eia_ingest.point_builder import ChunkInput

logger = logging.getLogger(__name__)


def extract_ui_guides(
    tenant_id: str,
    folder: str = "guides",
) -> list[dict]:
    """
    Extrae guías markdown de ./data/{tenant_id}/{folder}/

    Estructura esperada:
        data/
            {tenant_id}/
                guides/
                    guia-crear-producto.md
                    guia-configurar-pagos.md
    """
    base_path = Path(DATA_FOLDER) / tenant_id / folder

    if not base_path.exists():
        logger.warning("Carpeta de guías no encontrada: %s", base_path)
        return []

    guides: list[dict] = []
    for path in base_path.glob("*.md"):
        guides.append({
            "tenant_id": tenant_id,
            "source_type": "ui_guide_md",
            "source_id": str(path.relative_to(base_path)),
            "file_path": str(path),
            "filename": path.stem,
            "folder": folder,
        })

    if guides:
        logger.info("Encontradas %d guías en %s", len(guides), base_path)

    return guides


def read_guide_chunks(guide: dict) -> list[ChunkInput]:
    """
    Convierte una guía markdown en chunks basados en headers.

    Args:
        guide: Dict con keys del extract_ui_guides

    Returns:
        Lista de ChunkInput, uno por cada sección
    """
    try:
        content = Path(guide["file_path"]).read_text(encoding="utf-8")
    except Exception:
        logger.exception("Error leyendo guía: %s", guide["file_path"])
        return []

    if not content.strip():
        logger.warning("Guía vacía: %s", guide["file_path"])
        return []

    # Chunking por headers (cada ## es un chunk natural)
    chunks = chunk_markdown_by_headers(
        content,
        max_tokens=800,
        min_tokens=100,
    )

    chunk_inputs = []
    for i, chunk_text in enumerate(chunks):
        # Determinar el título de la sección del primer header
        first_line = chunk_text.split("\n")[0]
        section_title = first_line.replace("#", "").strip() if "#" in first_line else "General"

        chunk_input = ChunkInput(
            tenant_id=guide["tenant_id"],
            content_type="GUIA_UI",
            audience=AUDIENCE_COMERCIANTE,
            channels=["web", "web_admin"],
            text=chunk_text,
            source_type="ui_guide_md",
            source_id=f"{guide['source_id']}#section_{i}",
            metadata={
                "filename": guide["filename"],
                "section_title": section_title,
                "section_index": i,
                "total_sections": len(chunks),
            },
        )
        chunk_inputs.append(chunk_input)

    logger.info("Guía '%s' dividida en %d secciones", guide["filename"], len(chunks))
    return chunk_inputs