# EIA Ingest

Pipeline de sincronización incremental multi-fuente hacia Qdrant para búsquedas semánticas: catálogo de productos (PostgreSQL), PDFs de políticas, y guías UI (markdown).

## Uso

```bash
# Instalar dependencias
pip install -e .

# Sincronizar catálogo de productos
eia-sync

# Sincronizar PDFs (desde ./data/{tenant}/policies/)
POST /sync/documents?tenant_id=platform&folder=policies

# Sincronizar guías UI (desde ./data/{tenant}/guides/)
POST /sync/ui-guides?tenant_id=platform&folder=guides

# Ejecutar API en modo desarrollo (scheduler automático cada 24h)
dev
```

## API Endpoints

| Endpoint | Descripción |
|----------|-------------|
| `GET /` | Información de la API y estado del scheduler |
| `GET /health` | Estado de servicios (PostgreSQL y Qdrant) |
| `POST /sync` | Sincronización incremental del catálogo |
| `POST /sync/product/{id}` | Sincronizar producto específico |
| `POST /sync/documents` | Sincronizar PDFs (tenant/folder opcionales) |
| `POST /sync/ui-guides` | Sincronizar guías markdown (tenant/folder opcionales) |

## Estructura

```
eia_ingest/
├── __init__.py
├── __main__.py              # Entry point: eia-sync
├── api.py                   # FastAPI REST endpoints
├── config.py                # Configuración desde .env
├── embeddings.py            # OpenAI embeddings
├── point_builder.py         # Constructor de payloads común
├── chunking.py              # Chunking para PDFs/markdown
├── qdrant_client.py         # Cliente Qdrant
├── sync.py                  # Orquestador de sincronización
├── scheduler.py             # Scheduler periódico (24h)
└── readers/
    ├── __init__.py
    ├── catalog_reader.py    # Extracción PostgreSQL (catálogo)
    ├── pdf_reader.py        # Lectura de PDFs locales
    └── ui_guide_reader.py   # Lectura de guías markdown

data/
└── {tenant_id}/
    ├── policies/            # PDFs de políticas
    ├── docs/                # PDFs adicionales
    └── guides/              # Guías markdown (.md)
```

## Estructura de Payload Unificado

Todos los tipos de contenido usan el mismo payload en Qdrant:

```python
{
    "tenant_id": "platform",           # Identificador del tenant
    "content_type": "POLITICAS",       # CATALOGO | POLITICAS | GUIA_UI | etc
    "audience": "CLIENTE",             # CLIENTE | COMERCIANTE
    "channels": ["web", "whatsapp"],   # Canales de distribución
    "text": "Texto del chunk...",      # Contenido vectorizable
    "source_type": "pdf",              # vendure_product | pdf | ui_guide_md
    "source_id": "politica-dev.pdf#chunk_3",
    "metadata": {...},                 # Datos adicionales
    "content_hash": "sha256...",       # Detección de cambios
    "synced_at": "2026-01-15T10:30:00Z"
}
```

## Deployment Railway

1. Conectar repositorio en Railway
2. Agregar servicios: PostgreSQL y Qdrant Cloud
3. Configurar variables en `.env`
4. Railway usará el `Dockerfile`

## Scheduler Automático

La API inicia un scheduler que ejecuta la sincronización del catálogo **cada 24 horas**.

## Configuración

```env
# PostgreSQL (solo lectura)
PG_HOST=...
PG_PORT=...
PG_DB=...
PG_USER=...
PG_PASSWORD=...
PG_SSL=require

# Qdrant Cloud
QDRANT_URL=...
QDRANT_API_KEY=...
COLLECTION_NAME=ecommerce-catalog

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=text-embedding-3-small
VECTOR_SIZE=1536

# Documentos locales (opcional, default: ./data)
DATA_FOLDER=./data

# Opcional
SHOP_BASE_URL=https://stg.ecommer.shop
BATCH_SIZE=64
```

## Cómo funciona

1. **Fuentes múltiples** → Catálogo (PostgreSQL), PDFs (./data), Guías (./data)
2. **Readers** → Extraen contenido según el tipo de fuente
3. **Point Builder** → Normaliza todo a `ChunkInput` único
4. **Chunking** → Divide PDFs por párrafos, guías por headers
5. **Azure OpenAI** → Genera embeddings vectoriales
6. **Qdrant** → Almacena con hash de contenido para detección de cambios
7. **Incremental** → Solo sincroniza lo que cambió (por `content_hash`)