import os


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
