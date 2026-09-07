from eia_ingest.readers.pdf_reader import get_content_type_for_folder
from eia_ingest.readers.ui_guide_reader import read_guide_chunks
from eia_ingest.readers.catalog_reader import _row_to_chunk_input


def test_pdf_reader_maps_folder_to_content_type():
    assert get_content_type_for_folder("policies") == "POLITICAS"
    assert get_content_type_for_folder("payment") == "PAGOS"
    assert get_content_type_for_folder("support") == "SOPORTE"
    assert get_content_type_for_folder("company") == "INFO_GENERAL"
    assert get_content_type_for_folder("unknown") == "DOCUMENTO"


def test_ui_guide_reader_uses_web_admin_channel(tmp_path):
    guide_path = tmp_path / "guia.md"
    guide_path.write_text("# Título\n\nTexto de prueba", encoding="utf-8")

    guide = {
        "tenant_id": "platform",
        "source_type": "ui_guide_md",
        "source_id": "guia.md",
        "file_path": str(guide_path),
        "filename": "guia",
        "folder": "guides",
    }

    chunks = read_guide_chunks(guide)
    assert chunks
    assert "web_admin" in chunks[0].channels


def test_catalog_deduplicates_channels():
    """Un producto en 2 canales debe generar 1 solo ChunkInput."""
    row = (42, "es", "Panela", "<p>Buena</p>", "panela",
           "Alimentos", "Orgánica", "SKU-001", "")
    channels = [
        {"channel_id": 1, "channel_code": "__default_channel__",
         "channel_token": "tok-default"},
        {"channel_id": 112, "channel_code": "sol-y-luna",
         "channel_token": "sol-y-luna-token"},
    ]

    chunk = _row_to_chunk_input(row, tenant_id="platform", channels_info=channels)

    assert chunk.source_id == "product:42:es"
    assert chunk.metadata["channel_codes"] == ["__default_channel__", "sol-y-luna"]
    assert chunk.metadata["channel_tokens"] == ["tok-default", "sol-y-luna-token"]
    assert chunk.tenant_id == "platform"


def test_catalog_single_channel():
    """Un producto en 1 canal funciona correctamente."""
    row = (99, "es", "Café", "<p>Nice</p>", "cafe",
           "Bebidas", "", "SKU-100", "")
    channels = [
        {"channel_id": 1, "channel_code": "__default_channel__",
         "channel_token": "tok-default"},
    ]

    chunk = _row_to_chunk_input(row, tenant_id="platform", channels_info=channels)

    assert chunk.source_id == "product:99:es"
    assert chunk.metadata["channel_codes"] == ["__default_channel__"]
    assert len(chunk.metadata["channel_tokens"]) == 1
