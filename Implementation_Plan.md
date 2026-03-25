# Implementation Plan

## Goal

Implement the required API and supporting services so the system can:

- Sign up and log in users
- Upload PDFs
- Process PDFs in the background
- List and delete documents
- Search semantically over a user's own PDFs
- Run fully through Docker Compose

## Build Order

### 1. Project Skeleton

Set up:

- FastAPI service
- Worker service
- PostgreSQL
- MinIO
- RabbitMQ
- Qdrant
- Redis
- Nginx
- Docker Compose

Add a `/health` endpoint and make sure everything starts with `docker compose up`.

### 2. Database

Create PostgreSQL schema for:

- `users`
- `documents`

Add indexes for:

- `users(username)`
- `documents(user_id, created_at)`
- `documents(user_id, status)`

Use raw SQL with `psycopg`.

### 3. Auth

Implement:

- `POST /auth/signup`
- `POST /auth/login`

Add password hashing and JWT generation/validation.

### 4. Upload Flow

Implement:

- `POST /documents`

Flow:

1. Validate PDF
2. Upload file to MinIO
3. Insert document row in Postgres with `processing` status
4. Enqueue Celery task
5. Return `202 Accepted`

### 5. Worker Pipeline

Worker should:

1. Load PDF from MinIO
2. Extract text
3. Split into paragraphs
4. Generate embeddings
5. Store vectors in Qdrant
6. Update document status to `ready`
7. Mark as `failed` on error

### 6. Document Management

Implement:

- `GET /documents`
- `DELETE /documents/{id}`

Users must only see and delete their own documents.

### 7. Search

Implement:

- `GET /search?q=...`

Flow:

1. Embed query
2. Search Qdrant
3. Filter by `user_id`
4. Return top 5 paragraph matches with score and filename

### 8. Scaling Support

Add Nginx in front of the API and make sure the API is stateless so multiple API containers can run behind it.

### 9. Observability

Add:

- Request timing
- Worker timing
- DB/query timing
- Logs for failures and processing state

### 10. Load Testing

Use Locust to test:

- Concurrent uploads
- Concurrent searches
- Mixed traffic

Measure:

- Latency
- Throughput
- Error rate
- Bottlenecks

## Final Endpoint List

- `POST /auth/signup`
- `POST /auth/login`
- `POST /documents`
- `GET /documents`
- `DELETE /documents/{id}`
- `GET /search?q=...`

## Final Status Model

Use:

- `processing`
- `ready`
- `failed`

## Implementation Priority

Prioritize a clean, modular implementation that works end-to-end first. After that, improve observability, scaling behavior, and performance.
