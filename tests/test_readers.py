from eia_ingest.readers.catalog_reader import resolve_tenant_id
from eia_ingest.readers.pdf_reader import get_content_type_for_folder
from eia_ingest.readers.ui_guide_reader import read_guide_chunks


def test_pdf_reader_maps_folder_to_content_type():
    assert get_content_type_for_folder("policies") == "POLITICAS"
    assert get_content_type_for_folder("payment") == "PAGOS"
    assert get_content_type_for_folder("support") == "SOPORTE"
    assert get_content_type_for_folder("company") == "INFO_GENERAL"
    assert get_content_type_for_folder("unknown") == "DOCUMENTO"


def test_resolve_tenant_id_uses_channel_token_for_storefront_channels():
    assert resolve_tenant_id("__default_channel__", "alem-token") == "platform"
    assert resolve_tenant_id("storefront", "otanuki-token") == "otanuki-token"


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
