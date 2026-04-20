# Distributed Semantic Retrieval System

This project is a semantic search system for PDF documents. Users can sign up, upload PDFs, wait for background processing, and run semantic search queries against the indexed content.

## What is included

- FastAPI API service
- Dedicated embedding service
- PostgreSQL for users and document metadata
- RabbitMQ for background task queues
- Redis for query embedding cache
- Qdrant for vector search
- MinIO for object storage
- Ten parsing workers and two embedding workers
- Three embedding-service replicas behind an internal router
- Nginx reverse proxy on `http://localhost:8080`

All required services are containerized and started by a single `docker-compose up`.

## TA Quick Start

From a fresh clone:

```bash
cp .env.example .env
docker-compose up --build
```

Wait for the API to become ready:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

Expected responses:

```json
{"status":"ok"}
{"status":"ready"}
```

The automated tests can then target `http://localhost:8080`.

If `8080` is already in use on a shared machine, set a different host port before starting:

```bash
cp .env.example .env
sed -i 's/^NGINX_HOST_PORT=.*/NGINX_HOST_PORT=18080/' .env
docker-compose up --build
```

Then use `http://localhost:18080` for manual testing on that shared host. Keep the default `8080` for TA grading on a clean machine.

## First Run Notes

- The first build is the slowest because the image installs Python dependencies and embedding service assets.
- Later restarts are much faster because the Docker image layers and named volumes are reused.
- No local Python environment, database, or filesystem path setup is required.
- The runtime images are split by role so parsing, embedding, and API services can scale independently while keeping builds deterministic.
- The default parsing backend is `pymupdf_blocks`, which avoids the heavy Docling warmup path for normal PDF ingestion.

## Common Commands

Start the full system:

```bash
docker-compose up --build
```

Stop the system:

```bash
docker-compose down
```

Stop the system and remove named volumes:

```bash
docker-compose down -v
```

View container status:

```bash
docker-compose ps
```

View logs:

```bash
docker-compose logs -f nginx api worker embedding-worker embedding-router
```

## API Smoke Test

Create a user:

```bash
curl -X POST http://localhost:8080/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"123456789"}'
```

Log in:

```bash
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"123456789"}'
```

Upload a PDF after replacing `<TOKEN>` and `/path/to/file.pdf`:

```bash
curl -X POST http://localhost:8080/documents \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@/path/to/file.pdf;type=application/pdf"
```

List documents:

```bash
curl -X GET http://localhost:8080/documents \
  -H "Authorization: Bearer <TOKEN>"
```

Run search:

```bash
curl -G http://localhost:8080/search \
  -H "Authorization: Bearer <TOKEN>" \
  --data-urlencode "q=example query"
```

## Services

- `nginx` exposes the public API on port `8080`
- `api` through `api5` run the FastAPI application behind nginx
- `worker` through `worker4` process PDF parsing tasks by default
- `worker5` through `worker10` are available behind the optional `scale` compose profile
- `embedding-worker` and `embedding-worker2` handle embedding/indexing tasks
- `embedding-service`, `embedding-service2`, and `embedding-service3` serve embeddings behind `embedding-router`

## Environment Configuration

All required environment variables are listed in `.env.example`. The default values are set for local Docker Compose usage, so the standard workflow is:

```bash
cp .env.example .env
docker-compose up --build
```

If you need to change the public port, update `NGINX_HOST_PORT` in `.env`.

## Scale Notes

This branch is tuned for higher throughput rather than the smallest possible footprint:

- parsing workers default to `PARSE_WORKER_CONCURRENCY=1` so PDF parsing jobs do not overcommit CPU/RAM per container
- embedding workers default to `EMBEDDING_WORKER_CONCURRENCY=2`
- Celery uses `worker_prefetch_multiplier=1` so long-running parse tasks are distributed more evenly
- the app points to `embedding-router`, which load-balances across three embedding-service replicas
- `PDF_EXTRACTOR_BACKEND` defaults to `pymupdf_blocks`; set it to `docling` only if you explicitly want the older parser path
