"""Carga variables de entorno del archivo .env."""
import os

from dotenv import load_dotenv

load_dotenv()

# Qdrant Cloud
QDRANT_URL: str = os.getenv("QDRANT_URL")
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "ecommerce-catalog")

# Azure OpenAI
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "text-embedding-3-small")
EMBEDDING_MODEL: str = AZURE_OPENAI_DEPLOYMENT
VECTOR_SIZE: int = int(os.getenv("VECTOR_SIZE", "1536"))

# PostgreSQL (Vendure) — usuario de SOLO LECTURA
PG_HOST: str = os.getenv("PG_HOST")
PG_PORT: int = int(os.getenv("PG_PORT"))
PG_DB: str = os.getenv("PG_DB")
PG_USER: str = os.getenv("PG_USER")
PG_PASSWORD: str = os.getenv("PG_PASSWORD")
PG_SSL: str = os.getenv("PG_SSL")

# Tienda (URLs en el texto vectorizable)
SHOP_BASE_URL: str = os.getenv("SHOP_BASE_URL", "https://stg.ecommer.shop")

# Pipeline
BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "64"))

# Celery (sync automatico opcional)
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
