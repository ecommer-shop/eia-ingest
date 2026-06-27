"""Generador de embeddings con Azure OpenAI."""
from openai import AzureOpenAI
from eia_ingest import config

_client = None


def get_azure_client() -> AzureOpenAI:
    """Inicializa y retorna el cliente de Azure OpenAI (Singleton)."""
    global _client
    if _client is None:
        _client = AzureOpenAI(
            api_key=config.AZURE_OPENAI_API_KEY,
            api_version="2024-02-01",
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        )
    return _client


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Genera embeddings para una lista de textos usando Azure OpenAI en lote.
    
    Aplica limpieza básica de saltos de línea y envía la petición con las 
    dimensiones especificadas en la configuración.
    """
    if not texts:
        return []

    cleaned_texts = [t.replace("\n", " ") for t in texts]
    client = get_azure_client()
    
    response = client.embeddings.create(
        input=cleaned_texts,
        model=config.AZURE_OPENAI_DEPLOYMENT,
        dimensions=config.VECTOR_SIZE,
    )
    return [data.embedding for data in response.data]
