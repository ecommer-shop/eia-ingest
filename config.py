"""config.py — Configuración unificada del pipeline de ingestión."""
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# ── Qdrant ──────────────────────────────────────────────
QDRANT_URL: str          = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY: str      = os.getenv("QDRANT_API_KEY", "")
COLLECTION_NAME: str     = os.getenv("COLLECTION_NAME", "ecommerce-rag-collection_openAI")
VECTOR_SIZE: int         = 1536  # Tamaño del embedding 
SCORE_THRESHOLD: float   = 0.45

# ── Embedding ───────────────────────────────────────────
# --- Azure OpenAI (IMPORTANTE: Deben estar aquí declaradas) ---
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
# --- OpenAI (oficial) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Modelo de embeddings a usar por defecto (OpenAI)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
# ── Railway PostgreSQL ──────────────────────────────────
PG_HOST: str     = os.getenv("PG_HOST", "tramway.proxy.rlwy.net")
PG_PORT: int     = int(os.getenv("PG_PORT", "46526"))
PG_DB: str       = os.getenv("PG_DB", "railway")
PG_USER: str     = os.getenv("PG_USER", "rag_readonly")
PG_PASSWORD: str = os.getenv("PG_PASSWORD", "")
PG_SSL: str      = "require"

# ── Chunking ────────────────────────────────────────────
PDF_CHUNK_SIZE: int      = 512    # tokens (no caracteres)
PDF_CHUNK_OVERLAP: int   = 64     # ~12% overlap — balance entre contexto y ruido
PRODUCT_CHUNK_SIZE: int  = 400    # productos son más cortos, chunks más pequeños

# ── Pipeline ────────────────────────────────────────────
BATCH_SIZE: int          = 64
DATA_DIR: Path           = Path(__file__).parent / "data"
STORE_ID: str            = os.getenv("STORE_ID", "default")
LANGUAGE_CODE: str       = os.getenv("LANGUAGE_CODE", "es")


