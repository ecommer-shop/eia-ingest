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


def _get_env(name: str, default: str = "", *aliases: str) -> str:
    """Obtiene una variable de entorno, priorizando el valor si está definido.

    Si el nombre principal no existe, prueba cada alias en orden.
    Ej.: _get_env("DB_SSL", "require", "PG_SSL")
    """
    value = os.getenv(name)
    if value is not None:
        return value
    for alias in aliases:
        value = os.getenv(alias)
        if value is not None:
            return value
    return default


# Valores admitidos por psycopg2 en sslmode=.
_VALID_SSLMODES = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}

# Alias tipo booleano que suelen aparecer en .env y NO son válidos en psycopg2.
_SSLMODE_ALIASES = {
    "true": "require",
    "1": "require",
    "yes": "require",
    "on": "require",
    "false": "disable",
    "0": "disable",
    "no": "disable",
    "off": "disable",
}


def _normalize_sslmode(value: str) -> str:
    """Convierte valores tipo booleano a un sslmode válido para psycopg2.

    Evita el error clásico: `psycopg2.OperationalError: invalid sslmode value: "true"`.
    """
    raw = (value or "").strip()
    if not raw:
        return "require"
    mapped = _SSLMODE_ALIASES.get(raw.lower())
    if mapped is not None:
        return mapped
    if raw.lower() not in _VALID_SSLMODES:
        print(
            f"[config] AVISO: sslmode '{raw}' no es válido; "
            f"se usará 'require'. Valores válidos: {sorted(_VALID_SSLMODES)}"
        )
        return "require"
    return raw


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
# Se aceptan ambos prefijos (DB_* y PG_*) para no romper .env.main/.env
PG_HOST: str = _get_env("DB_HOST", "", "PG_HOST")
PG_PORT: int = int(_get_env("DB_PORT", _get_env("PG_PORT", "5432")))
PG_DB: str = _get_env("DB_NAME", "", "PG_DB")
PG_USER: str = _get_env("DB_USERNAME", "", "PG_USER")
PG_PASSWORD: str = _get_env("DB_PASSWORD", "", "PG_PASSWORD")
PG_SSL: str = _normalize_sslmode(_get_env("DB_SSL", _get_env("PG_SSL", "require")))

# Tienda (URLs en el texto vectorizable)
SHOP_BASE_URL: str = _get_env("SHOP_BASE_URL")

# Autenticación de webhooks (JWT HS256)
JWT_SECRET: str = _get_env("JWT_SECRET", "")
JWT_ALGORITHM: str = _get_env("JWT_ALGORITHM", "HS256")

# Pipeline
BATCH_SIZE: int = int(_get_env("BATCH_SIZE", "64"))

# Documentos locales (PDFs, guías)
DATA_FOLDER: str = _get_env("DATA_FOLDER", "./data")
