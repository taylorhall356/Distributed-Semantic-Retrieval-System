from io import BytesIO
from pathlib import Path
from time import sleep
from uuid import uuid4

from fastapi import UploadFile
from minio import Minio

from config import (
    DOCUMENTS_DIR,
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECRET_KEY,
    MINIO_SECURE,
    STORAGE_BACKEND,
)

_minio_client: Minio | None = None
MINIO_READY_MAX_ATTEMPTS = 10
MINIO_READY_DELAY_SECONDS = 2


class FilesystemStorage:
    def ensure_ready(self) -> None:
        DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, object_key: str, content: bytes) -> None:
        self.get_document_path(object_key).write_bytes(content)

    def read_bytes(self, object_key: str) -> bytes:
        return self.get_document_path(object_key).read_bytes()

    def delete_file(self, object_key: str) -> None:
        self.get_document_path(object_key).unlink(missing_ok=True)

    def get_document_path(self, object_key: str) -> Path:
        return DOCUMENTS_DIR / object_key


class MinioStorage:
    def ensure_ready(self) -> None:
        last_error: Exception | None = None

        for _ in range(MINIO_READY_MAX_ATTEMPTS):
            try:
                client = get_minio_client()
                if not client.bucket_exists(MINIO_BUCKET):
                    client.make_bucket(MINIO_BUCKET)
                return
            except Exception as exc:
                last_error = exc
                sleep(MINIO_READY_DELAY_SECONDS)

        raise RuntimeError("MinIO readiness check failed") from last_error

    def save_bytes(self, object_key: str, content: bytes, content_type: str) -> None:
        client = get_minio_client()
        client.put_object(
            bucket_name=MINIO_BUCKET,
            object_name=object_key,
            data=BytesIO(content),
            length=len(content),
            content_type=content_type,
        )

    def read_bytes(self, object_key: str) -> bytes:
        client = get_minio_client()
        response = client.get_object(MINIO_BUCKET, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_file(self, object_key: str) -> None:
        client = get_minio_client()
        client.remove_object(MINIO_BUCKET, object_key)


def get_minio_client() -> Minio:
    global _minio_client

    if _minio_client is None:
        _minio_client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )

    return _minio_client


def get_storage_backend() -> FilesystemStorage | MinioStorage:
    if STORAGE_BACKEND == "filesystem":
        return FilesystemStorage()
    if STORAGE_BACKEND == "minio":
        return MinioStorage()

    raise ValueError(f"Unsupported storage backend: {STORAGE_BACKEND}")


def ensure_storage_ready() -> None:
    get_storage_backend().ensure_ready()


async def save_document_file(file: UploadFile) -> str:
    suffix = Path(file.filename or "document.pdf").suffix or ".pdf"
    object_key = f"{uuid4()}{suffix}"
    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"

    backend = get_storage_backend()
    if isinstance(backend, MinioStorage):
        backend.save_bytes(object_key=object_key, content=file_bytes, content_type=content_type)
    else:
        backend.save_bytes(object_key=object_key, content=file_bytes)

    return object_key


def read_document_bytes(object_key: str) -> bytes:
    return get_storage_backend().read_bytes(object_key)


def delete_document_file(object_key: str) -> None:
    get_storage_backend().delete_file(object_key)
