"""Lectura de PDFs desde carpeta local."""
from __future__ import annotations

import logging
from pathlib import Path

import pypdf

from eia_ingest.chunking import chunk_by_paragraphs
from eia_ingest.config import DATA_FOLDER
from eia_ingest.point_builder import ChunkInput

logger = logging.getLogger(__name__)


def extract_pending_documents(
    tenant_id: str,
    folder: str = "policies",
) -> list[dict]:
    """
    Extrae PDFs pendientes de ./data/{tenant_id}/{folder}/

    Estructura esperada:
        data/
            {tenant_id}/
                policies/
                    politica-devoluciones.pdf
                    guia-tallas.pdf
                docs/
                    manual-usuario.pdf
    """
    base_path = Path(DATA_FOLDER) / tenant_id / folder

    if not base_path.exists():
        logger.warning("Carpeta no encontrada: %s", base_path)
        return []

    documents: list[dict] = []
    for path in base_path.glob("*.pdf"):
        documents.append({
            "tenant_id": tenant_id,
            "source_type": "pdf",
            "source_id": str(path.relative_to(base_path)),
            "file_path": str(path),
            "filename": path.stem,
            "folder": folder,
        })

    if documents:
        logger.info("Encontrados %d PDFs en %s", len(documents), base_path)

    return documents


def extract_text_from_pdf(file_path: str) -> str:
    """Extrae texto plano de un PDF."""
    try:
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            return text
    except Exception:
        logger.exception("Error extrayendo texto de %s", file_path)
        return ""


def read_pdf_chunks(document: dict) -> list[ChunkInput]:
    """
    Convierte un PDF en chunks procesables.

    Args:
        document: Dict con keys del extract_pending_documents

    Returns:
        Lista de ChunkInput, uno por cada chunk
    """
    text = extract_text_from_pdf(document["file_path"])

    if not text.strip():
        logger.warning("PDF vacío o ilegible: %s", document["file_path"])
        return []

    # Chunking con parámetros conservadores para PDFs de políticas
    chunks = chunk_by_paragraphs(
        text,
        max_tokens=500,
        overlap_tokens=50,
    )

    chunk_inputs = []
    for i, chunk_text in enumerate(chunks):
        chunk_input = ChunkInput(
            tenant_id=document["tenant_id"],
            content_type="POLITICAS" if document["folder"] == "policies" else "DOCUMENTOS",
            audience="CLIENTE",
            channels=["web","whatsapp","instagram","messenger"],
            text=chunk_text,
            source_type="pdf",
            source_id=f"{document['source_id']}#chunk_{i}",
            metadata={
                "filename": document["filename"],
                "chunk_index": i,
                "total_chunks": len(chunks),
                "folder": document["folder"],
            },
        )
        chunk_inputs.append(chunk_input)

    logger.info("PDF '%s' dividido en %d chunks", document["filename"], len(chunks))
    return chunk_inputs