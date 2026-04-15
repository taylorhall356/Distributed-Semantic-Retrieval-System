from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from config import DOCUMENTS_DIR


def ensure_storage_ready() -> None:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


def get_document_path(object_key: str) -> Path:
    return DOCUMENTS_DIR / object_key


async def save_document_file(file: UploadFile) -> str:
    suffix = Path(file.filename or "document.pdf").suffix or ".pdf"
    object_key = f"{uuid4()}{suffix}"
    destination = get_document_path(object_key)

    file_bytes = await file.read()
    destination.write_bytes(file_bytes)

    return object_key


def read_document_bytes(object_key: str) -> bytes:
    return get_document_path(object_key).read_bytes()


def delete_document_file(object_key: str) -> None:
    get_document_path(object_key).unlink(missing_ok=True)
