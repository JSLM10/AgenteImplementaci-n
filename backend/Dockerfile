# ─────────────────────────────────────────────────────────────────────────────
# Backend VAR — FastAPI + LangGraph + embeddings locales
#
# El modelo de embeddings (~118 MB) se descarga en la construcción, no en el
# primer arranque: así el contenedor queda listo para responder desde el
# principio y no depende de que haya red en el momento del despliegue.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/hf_cache

WORKDIR /app

# build-essential hace falta para compilar algunas ruedas que no traen binario
# para esta plataforma; se elimina después para no cargar la imagen.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Se instala con el extra "cloud" (transformers + accelerate) para que la misma
# imagen sirva con LLM_PROVIDER=ollama y con LLM_PROVIDER=huggingface. Pesa
# poco mas, porque torch ya entra como dependencia de sentence-transformers, y
# evita una imagen que arranca y falla al primer mensaje por un import que
# falta.
RUN pip install --upgrade pip && pip install ".[cloud]"

COPY app ./app
COPY seed ./seed
COPY scripts ./scripts

# Precarga del modelo de embeddings dentro de la imagen.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('intfloat/multilingual-e5-small')"

RUN mkdir -p /app/storage

# El puerto se toma del entorno porque cada plataforma impone el suyo:
# Hugging Face Spaces usa 7860, Render y Railway inyectan $PORT, y en local
# vale 8000. Fijarlo en el Dockerfile obligaria a mantener una imagen por sitio.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
