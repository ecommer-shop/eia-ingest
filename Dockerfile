FROM python:3.13-slim

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instalar Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copiar código
COPY eia_ingest ./eia_ingest

# Directorios necesarios
RUN mkdir -p logs

# Usuario no root
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Por defecto ejecuta API
CMD ["uvicorn", "eia_ingest.api:app", "--host", "0.0.0.0", "--port", "8000"]