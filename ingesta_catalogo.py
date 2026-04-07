import uuid
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, PayloadSchemaType
from openai import AzureOpenAI
from scrip_postgreSQL import extract_product_catalog
# IMPORTANTE: Agregamos las variables de Azure aquí
from config import (
    AZURE_OPENAI_API_KEY,      # <--- Falta esto
    AZURE_OPENAI_ENDPOINT,     # <--- Y esto
    EMBEDDING_MODEL,
    QDRANT_URL,
    QDRANT_API_KEY,
    COLLECTION_NAME,
)

print("🔌 Conectando a Qdrant...")
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)

# Cliente Azure OpenAI corregido
openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version="2024-02-01",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

print(f"🧠 Usando modelo de embeddings: {EMBEDDING_MODEL}")

# 1. COMPROBACIÓN Y CREACIÓN DE COLECCIÓN (Simplificado)
collection_exists = True
try:
    client.get_collection(collection_name=COLLECTION_NAME)
    print(f"✅ La colección '{COLLECTION_NAME}' ya existe. Procediendo con UPSERTs.")
except Exception:
    collection_exists = False
    print(f"⚠️ La colección '{COLLECTION_NAME}' no existe. Se creará dinámicamente con el primer batch.")

# 2. EXTRAER DATOS DE POSTGRESQL
print("\n📦 Extrayendo catálogo de la base de datos...")
products_data = extract_product_catalog() 

if not products_data:
    print("❌ No hay datos para procesar.")
else:
    BATCH_SIZE = 64
    print(f"\n🚀 Procesando y subiendo {len(products_data)} vectores a Qdrant...")

    # 3. BATCH ENCODING E INGESTA
    for i in range(0, len(products_data), BATCH_SIZE):
        batch_data = products_data[i:i+BATCH_SIZE]
        
        # Obtener textos del batch
        texts_batch = [item["text"] for item in batch_data]
        
        # Llamada a Azure OpenAI
        resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts_batch)
        vectors_batch = [d.embedding for d in resp.data]

        # Crear colección si no existe (usando el tamaño real del vector de Azure)
        if not collection_exists:
            vector_size = len(vectors_batch[0]) 
            print(f"📐 Creando colección '{COLLECTION_NAME}' con tamaño: {vector_size}")
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            # Índices
            client.create_payload_index(COLLECTION_NAME, "language", PayloadSchemaType.KEYWORD)
            client.create_payload_index(COLLECTION_NAME, "product_id", PayloadSchemaType.INTEGER)
            collection_exists = True
        
        points = []
        for j, item in enumerate(batch_data):
            # ID determinista para evitar duplicados
            unique_string = f"{item['payload']['product_id']}_{item['payload']['language']}"
            deterministic_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))
            
            points.append(
                PointStruct(
                    id=deterministic_id,
                    vector=vectors_batch[j],
                    payload=item["payload"]
                )
            )

        # Upsert
        print(f"📦 Subiendo Batch {i//BATCH_SIZE + 1}...")
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print("\n🎉 INGESTIÓN DEL CATÁLOGO COMPLETADA.")