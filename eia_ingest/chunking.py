"""Chunking strategies para PDFs y documentos markdown."""
from __future__ import annotations

import re
from typing import List


def chunk_by_paragraphs(
    text: str,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
) -> List[str]:
    """
    Chunking basado en párrafos, con split como fallback.

    Args:
        text: Texto a chunkear
        max_tokens: Máximo de tokens por chunk
        overlap_tokens: Tokens de solapamiento entre chunks

    Returns:
        Lista de chunks de texto
    """
    # Estimación simple: ~4 caracteres por token en promedio
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4

    # Split por párrafos (doble newline o más)
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks: List[str] = []
    current_chunk = ""
    current_chars = 0

    for para in paragraphs:
        para_chars = len(para)

        # Si el párrafo excede max_chars, hacer split duro
        if para_chars > max_chars:
            # Guardar chunk actual si tiene contenido
            if current_chunk:
                chunks.append(current_chunk)
                # Mantener overlap
                if overlap_chars > 0 and len(current_chunk) > overlap_chars:
                    current_chunk = current_chunk[-overlap_chars:]
                    current_chars = len(current_chunk)
                else:
                    current_chunk = ""
                    current_chars = 0

            # Split del párrafo largo
            for i in range(0, para_chars, max_chars - overlap_chars):
                chunk_text = para[i : i + max_chars]
                chunks.append(chunk_text)

        # Si el párrafo entra en el chunk actual
        elif current_chars + para_chars + 1 <= max_chars:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
            current_chars = len(current_chunk)

        # Nuevo chunk necesario
        else:
            chunks.append(current_chunk)
            # Mantener overlap
            if overlap_chars > 0 and len(current_chunk) > overlap_chars:
                current_chunk = current_chunk[-overlap_chars:] + "\n\n" + para
                current_chars = len(current_chunk)
            else:
                current_chunk = para
                current_chars = para_chars

    # Agregar chunk pendiente
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def chunk_markdown_by_headers(
    text: str,
    max_tokens: int = 800,
    min_tokens: int = 100,
) -> List[str]:
    """
    Chunking para markdown basado en headers (##).

    Útil para guías de UI donde cada sección es un chunk natural.

    Args:
        text: Contenido markdown
        max_tokens: Máximo tokens por chunk
        min_tokens: Mínimo tokens para crear un chunk separado

    Returns:
        Lista de chunks
    """
    # Dividir por headers
    sections = re.split(r'(^#{1,6}\s+.+$)', text, flags=re.MULTILINE)

    chunks: List[str] = []
    current_chunk = ""
    current_tokens = 0

    for i, section in enumerate(sections):
        # Section puede ser vacío entre headers
        if not section.strip():
            continue

        # Es un header
        if section.startswith('#'):
            # Si hay contenido pendiente, procesarlo
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = section
            current_tokens = len(section) // 4
        else:
            # Es contenido
            section_tokens = len(section) // 4

            # Si excede max_tokens, partir por párrafos
            if current_tokens + section_tokens > max_tokens:
                if current_tokens > min_tokens:
                    chunks.append(current_chunk.strip())
                    # Mantener overlap con overlap de 1-2 párrafos
                    last_newlines = current_chunk.rfind('\n\n')
                    if last_newlines > len(current_chunk) // 3:
                        overlap = current_chunk[last_newlines + 2:]
                        current_chunk = section + "\n\n" + overlap[:500]
                    else:
                        current_chunk = section[:1000]
                    current_tokens = len(current_chunk) // 4
                else:
                    current_chunk += section
                    current_tokens = len(current_chunk) // 4
            else:
                current_chunk += section
                current_tokens = len(current_chunk) // 4

    # Agregar chunk final
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def estimate_tokens(text: str) -> int:
    """Estimación rápida de tokens."""
    return len(text) // 4