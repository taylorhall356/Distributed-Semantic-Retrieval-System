FROM python:3.10

WORKDIR /app

ARG PRELOAD_DOCLING_ASSETS=true

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface \
    HUGGINGFACE_HUB_CACHE=/opt/huggingface \
    TRANSFORMERS_CACHE=/opt/huggingface \
    XDG_CACHE_HOME=/opt/.cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /opt/huggingface /opt/.cache \
    && if [ "$PRELOAD_DOCLING_ASSETS" = "true" ]; then python scripts/warm_docling_assets.py; fi

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
