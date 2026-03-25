# Project goal

Build a Dockerized semantic PDF search system where users can sign up, log in, upload PDFs, and search only their own documents using natural-language queries. Upload processing must be asynchronous, and the API must stay stateless.

## Chosen stack

### FastAPI
Used for the REST API because it is clean, fast to build with, and a good fit for typed endpoints, auth, and file upload.

### JWT
Used for authentication so the API tier stays stateless and can scale horizontally.

### PostgreSQL
Used for structured application data such as users, document metadata, ownership, and processing status.

### Raw SQL with psycopg
Used instead of an ORM so query design, indexing, and performance tuning stay explicit and easy to control.

### MinIO
Used for PDF storage so files are not stored on API containers and can be accessed by both API and worker services.

### RabbitMQ + Celery
Used for asynchronous processing. Upload requests return quickly, while PDF parsing, chunking, and embedding generation happen in background workers.

###Qdrant
Used as the vector database for semantic similarity search over paragraph embeddings.

### sentence-transformers (all-MiniLM-L6-v2)
Used as the local embedding model because it is lightweight, fast, and good enough for semantic retrieval.

### Redis
Included for caching and short-lived shared state if needed later.

### Nginx
Used as the reverse proxy and load balancer in front of the API.

### Locust
Used for load testing concurrent uploads, searches, and mixed workloads.

## Core architecture
User authenticates with JWT.
User uploads a PDF through the API.
API stores the file in MinIO, stores metadata in PostgreSQL, queues a background task, and returns 202 Accepted.
Worker extracts text, splits into paragraphs, generates embeddings, and stores them in Qdrant.
Search endpoint embeds the query, searches Qdrant, filters by user, and returns the top 5 relevant paragraphs with scores.
## Why this stack

This stack cleanly separates responsibilities:

Postgres for structured data
MinIO for files
Qdrant for vector search
RabbitMQ/Celery for async work
Nginx for scaling
FastAPI for the API

It is simple enough to finish, but strong enough to defend as a scalable architecture.