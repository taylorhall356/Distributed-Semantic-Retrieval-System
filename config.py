import os
from pathlib import Path


def get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "semantic_retrieval")
DB_USER = os.getenv("DB_USER", "semantic_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "semantic_password")

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "development-secret-key-at-least-32-bytes",
)
JWT_ALGORITHM = "HS256"

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "filesystem").strip().lower()
DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR", "storage/documents"))
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "document-storage")
MINIO_SECURE = get_bool_env("MINIO_SECURE", False)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
DOCUMENT_PROCESSING_QUEUE = os.getenv("DOCUMENT_PROCESSING_QUEUE", "document_processing")
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}//",
)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "document_chunks")

EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/all-MiniLM-L6-v2",
)
EMBEDDING_VECTOR_SIZE = int(os.getenv("EMBEDDING_VECTOR_SIZE", "384"))
EMBEDDING_SERVICE_URL = os.getenv(
    "EMBEDDING_SERVICE_URL",
    "http://localhost:8090",
).rstrip("/")
EMBEDDING_REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("EMBEDDING_REQUEST_TIMEOUT_SECONDS", "120")
)
REDIS_ENABLED = get_bool_env("REDIS_ENABLED", True)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
QUERY_EMBEDDING_CACHE_TTL_SECONDS = int(
    os.getenv("QUERY_EMBEDDING_CACHE_TTL_SECONDS", "3600")
)
QUERY_EMBEDDING_CACHE_LOGGING = get_bool_env(
    "QUERY_EMBEDDING_CACHE_LOGGING",
    True,
)

DOCUMENT_PROCESSING_STALE_SECONDS = int(
    os.getenv("DOCUMENT_PROCESSING_STALE_SECONDS", "900")
)
