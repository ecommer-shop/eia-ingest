"""Carga variables de entorno del archivo .env."""
import os
import subprocess

from dotenv import load_dotenv

# Cada rama usa su propio archivo de llaves (ver .githooks/sync-env.sh).
# main -> .env.main (stage/producción); dev/Kevin -> .env.dev; resto -> .env.dev
BRANCH_ENV = {
    "main": ".env.main",
    "dev": ".env.dev",
    "Kevin": ".env.dev",
}
DEFAULT_ENV_FILE = ".env.dev"


def _current_branch() -> str:
    """Devuelve la rama actual de git o '' si no está en un repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except OSError:
        pass
    return ""


def _env_file_for_branch() -> str:
    """Resuelve el archivo .env correspondiente a la rama actual."""
    return BRANCH_ENV.get(_current_branch(), DEFAULT_ENV_FILE)


_branch_env_file = _env_file_for_branch()
if os.path.exists(_branch_env_file):
    load_dotenv(_branch_env_file, override=True)
else:
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
COLLECTION_NAME: str = _get_env("COLLECTION_NAME", "ecommerce")

# Azure OpenAI
AZURE_OPENAI_ENDPOINT: str = _get_env("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY: str = _get_env("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT: str = _get_env("AZURE_OPENAI_DEPLOYMENT", "text-embedding-3-small")
EMBEDDING_MODEL: str = AZURE_OPENAI_DEPLOYMENT
VECTOR_SIZE: int = int(_get_env("VECTOR_SIZE", "1536"))

# PostgreSQL (Vendure) - usuario de solo lectura
PG_HOST: str = _get_env("DB_HOST", "")
PG_PORT: int = int(_get_env("DB_PORT", "5432"))
PG_DB: str = _get_env("DB_NAME", "")
PG_USER: str = _get_env("DB_USERNAME", "")
PG_PASSWORD: str = _get_env("DB_PASSWORD", "")
PG_SSL: str = _get_env("DB_SSL", "require")

# Tienda (URLs en el texto vectorizable)
SHOP_BASE_URL: str = _get_env("SHOP_BASE_URL")

# Pipeline
BATCH_SIZE: int = int(_get_env("BATCH_SIZE", "64"))

# Documentos locales (PDFs, guías)
DATA_FOLDER: str = _get_env("DATA_FOLDER", "./data")
