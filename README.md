# EIA Ingest

Pipeline de sincronización incremental: PostgreSQL (Vendure) → Qdrant para búsquedas semánticas.

## Uso

```bash
# Instalar
pip install -e .

# Sincronizar todo el catálogo
eia-sync

# Sincronizar un producto específico
eia-sync --product-id 123

# Ejecutar API en modo desarrollo
dev
```

## API Endpoints

- `GET /` - Información de la API
- `GET /health` - Estado de servicios
- `POST /sync` - Sincronización incremental en background
- `POST /sync/product/{id}` - Sincronizar producto específico

## Estructura

```
eia_ingest/
├── __init__.py
├── __main__.py      # Entry point: eia-sync
├── api.py           # FastAPI
├── config.py        # Configuración desde .env
├── embeddings.py    # OpenAI embeddings
├── catalog_reader.py  # Extracción PostgreSQL
├── qdrant_client.py   # Cliente Qdrant
├── sync.py            # Orquestador de sincronización
└── worker.py          # Tareas Celery
```

## Deployment Railway

1. Conectar repositorio en Railway
2. Agregar servicios: PostgreSQL, Redis, Qdrant Cloud
3. Configurar variables en `.env`
4. Railway usará el `Dockerfile`

## Tareas Automáticas (Celery Beat)

- Sync cada 30 minutos
- Health check cada 5 minutos