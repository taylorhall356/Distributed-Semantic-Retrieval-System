from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from config import DOCUMENTS_DIR
from db import get_connection


def ensure_documents_directory() -> None:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


def validate_pdf(file: UploadFile) -> None:
    is_pdf_content_type = file.content_type == "application/pdf"
    has_pdf_extension = file.filename is not None and file.filename.lower().endswith(".pdf")

    if not (is_pdf_content_type or has_pdf_extension):
        raise ValueError("Only PDF files are supported")


async def save_document_file(file: UploadFile) -> str:
    suffix = Path(file.filename or "document.pdf").suffix or ".pdf"
    object_key = f"{uuid4()}{suffix}"
    destination = DOCUMENTS_DIR / object_key

    file_bytes = await file.read()
    destination.write_bytes(file_bytes)

    return object_key


def create_document(user_id: int, filename: str, object_key: str) -> dict[str, str | int | datetime]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (user_id, filename, object_key, status)
                VALUES (%s, %s, %s, %s)
                RETURNING id, filename, status, created_at
                """,
                (user_id, filename, object_key, "processing"),
            )
            document_id, stored_filename, status, created_at = cur.fetchone()

    return {
        "id": document_id,
        "filename": stored_filename,
        "status": status,
        "created_at": created_at,
    }


def list_documents_for_user(user_id: int) -> list[dict[str, str | int | datetime]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, status, created_at
                FROM documents
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()

    return [
        {
            "id": document_id,
            "filename": filename,
            "status": status,
            "created_at": created_at,
        }
        for document_id, filename, status, created_at in rows
    ]
