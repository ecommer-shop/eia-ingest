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

# Ejecutar API en modo desarrollo (scheduler automático cada 24h)
dev
```

## API Endpoints

- `GET /` - Información de la API y estado del scheduler
- `GET /health` - Estado de servicios (PostgreSQL y Qdrant)
- `POST /sync` - Sincronización incremental manual
- `POST /sync/product/{id}` - Sincronizar producto específico

## Estructura

```
eia_ingest/
├── __init__.py
├── __main__.py      # Entry point: eia-sync
├── api.py           # FastAPI (con scheduler automático)
├── config.py        # Configuración desde .env
├── embeddings.py    # OpenAI embeddings
├── catalog_reader.py  # Extracción PostgreSQL
├── qdrant_client.py   # Cliente Qdrant
├── sync.py            # Orquestador de sincronización
└── scheduler.py       # Scheduler periódico
```

## Deployment Railway

1. Conectar repositorio en Railway
2. Agregar servicios: PostgreSQL y Qdrant Cloud
3. Configurar variables en `.env`
4. Railway usará el `Dockerfile`

## Scheduler Automático

La API inicia un scheduler que ejecuta la sincronización **cada 24 horas**:

- **Inicio**: Cuando se ejecuta `dev` o la API arranca
- **Intervalo**: 24 horas (86400 segundos)
- **Comportamiento**: Solo sincroniza productos nuevos o modificados

## Configuración

Las siguientes variables de entorno son necesarias en `.env`:

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

# Opcional
SHOP_BASE_URL=https://stg.ecommer.shop
BATCH_SIZE=64
```

## Cómo funciona

1. **PostgreSQL** → Se extraen productos activos (solo lectura)
2. **Azure OpenAI** → Se generan embeddings vectoriales
3. **Qdrant** → Se almacenan con hash de contenido para detección de cambios
4. **Incremental** → Solo se actualizan productos modificados o nuevos
