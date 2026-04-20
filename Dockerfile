FROM python:3.10-slim-bookworm AS base

WORKDIR /app

ARG PRELOAD_MODEL_ASSETS=false

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/opt/huggingface \
    HUGGINGFACE_HUB_CACHE=/opt/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HUB_DISABLE_XET=1 \
    HF_HUB_OFFLINE=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    SENTENCE_TRANSFORMERS_HOME=/opt/huggingface \
    TRANSFORMERS_CACHE=/opt/huggingface \
    TRANSFORMERS_OFFLINE=0 \
    XDG_CACHE_HOME=/opt/.cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libpq5 \
    && rm -rf /var/lib/apt/lists/*

FROM base AS deps-base

COPY requirements.base.txt .
RUN pip install --no-cache-dir -r requirements.base.txt

FROM deps-base AS deps-parse

COPY requirements.parse.txt .
RUN PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu \
    pip install --no-cache-dir -r requirements.parse.txt

FROM deps-base AS deps-embedding

COPY requirements.embedding.txt .
RUN PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu \
    pip install --no-cache-dir -r requirements.embedding.txt

FROM deps-base AS app-runtime

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM deps-parse AS parse-runtime

COPY . .

RUN mkdir -p /opt/huggingface /opt/.cache \
    && if [ "$PRELOAD_MODEL_ASSETS" = "true" ]; then HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 python scripts/warm_docling_assets.py; fi

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM deps-embedding AS embedding-runtime

COPY . .

RUN mkdir -p /opt/huggingface /opt/.cache \
    && if [ "$PRELOAD_MODEL_ASSETS" = "true" ]; then HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 python scripts/warm_embedding_assets.py; fi

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
