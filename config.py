import os
from pathlib import Path


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

DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR", "storage/documents"))

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "document_chunks")

EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/all-MiniLM-L6-v2",
)
