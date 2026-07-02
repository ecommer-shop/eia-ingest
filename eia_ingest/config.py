"""Carga variables de entorno del archivo .env."""
import os

from dotenv import load_dotenv

load_dotenv()


def _get_env(name: str, default: str = "") -> str:
    """Obtiene una variable de entorno, priorizando el valor si está definido."""
    value = os.getenv(name)
    if value is not None:
        return value
    return default


# Qdrant Cloud
QDRANT_URL: str = _get_env("QDRANT_URL", "")
QDRANT_API_KEY: str = _get_env("QDRANT_API_KEY", "")
COLLECTION_NAME: str = _get_env("COLLECTION_NAME", "ecommerce-catalog")

# Azure OpenAI
AZURE_OPENAI_ENDPOINT: str = _get_env("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY: str = _get_env("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT: str = _get_env("AZURE_OPENAI_DEPLOYMENT", "text-embedding-3-small")
EMBEDDING_MODEL: str = AZURE_OPENAI_DEPLOYMENT
VECTOR_SIZE: int = int(_get_env("VECTOR_SIZE", "1536"))

# PostgreSQL (Vendure) - usuario de solo lectura
PG_HOST: str = _get_env("PG_HOST", "")
PG_PORT: int = int(_get_env("PG_PORT"))
PG_DB: str = _get_env("PG_DB", "")
PG_USER: str = _get_env("PG_USER", "")
PG_PASSWORD: str = _get_env("PG_PASSWORD", "")
PG_SSL: str = _get_env("PG_SSL", "require")

# Tienda (URLs en el texto vectorizable)
SHOP_BASE_URL: str = _get_env("SHOP_BASE_URL", "https://stg.ecommer.shop")

# Pipeline
BATCH_SIZE: int = int(_get_env("BATCH_SIZE", "64"))
