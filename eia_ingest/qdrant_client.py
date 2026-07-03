"""Cliente Qdrant."""
from qdrant_client import QdrantClient

from eia_ingest.config import QDRANT_API_KEY, QDRANT_URL


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=120,
    )

