import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader

from config import DOCUMENTS_DIR
from db import get_connection
from semantic_search import delete_document_vectors, index_document_chunks

MIN_PARAGRAPH_CHARS = 120
MAX_PARAGRAPH_CHARS = 1200
SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]?$")


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


def extract_pdf_text(object_key: str) -> str:
    document_path = DOCUMENTS_DIR / object_key
    reader = PdfReader(str(document_path))
    page_text = []

    for page in reader.pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            page_text.append(extracted)

    return "\n\n".join(page_text).strip()


def is_heading_like(line: str) -> bool:
    words = line.split()
    if not words:
        return False

    if len(words) <= 8 and not SENTENCE_END_RE.search(line):
        alpha_words = [word for word in words if any(char.isalpha() for char in word)]
        title_case_words = [word for word in alpha_words if word[:1].isupper()]
        if alpha_words and len(title_case_words) >= max(1, len(alpha_words) - 1):
            return True

    return False


def split_large_paragraph(paragraph: str) -> list[str]:
    if len(paragraph) <= MAX_PARAGRAPH_CHARS:
        return [paragraph]

    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    chunks: list[str] = []
    current_chunk: list[str] = []

    for sentence in sentences:
        if not sentence:
            continue

        candidate = " ".join(current_chunk + [sentence]).strip()
        if current_chunk and len(candidate) > MAX_PARAGRAPH_CHARS:
            chunks.append(" ".join(current_chunk).strip())
            current_chunk = [sentence]
        else:
            current_chunk.append(sentence)

    if current_chunk:
        chunks.append(" ".join(current_chunk).strip())

    return chunks


def reconstruct_paragraphs(block: str) -> list[str]:
    lines = [line.strip() for line in block.split("\n") if line.strip()]
    if not lines:
        return []

    paragraphs: list[str] = []
    current_lines: list[str] = []

    for line in lines:
        if not current_lines:
            current_lines.append(line)
            continue

        current_text = " ".join(current_lines).strip()
        previous_line = current_lines[-1]
        previous_ended_sentence = bool(SENTENCE_END_RE.search(previous_line))
        current_is_heading = is_heading_like(line)
        should_start_new = False

        if current_is_heading and current_text:
            should_start_new = True
        elif previous_ended_sentence and len(current_text) >= MIN_PARAGRAPH_CHARS:
            should_start_new = True

        if should_start_new:
            paragraphs.append(current_text)
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        paragraphs.append(" ".join(current_lines).strip())

    return paragraphs


def split_text_into_chunks(text: str) -> list[str]:
    normalized_text = text.replace("\r\n", "\n")
    blocks = re.split(r"\n\s*\n", normalized_text)

    chunks: list[str] = []
    for block in blocks:
        for paragraph in reconstruct_paragraphs(block):
            cleaned = " ".join(paragraph.split())
            if cleaned:
                chunks.extend(split_large_paragraph(cleaned))

    return chunks


def store_document_chunks(document_id: int, user_id: int, chunks: list[str]) -> list[dict[str, str | int]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM document_chunks WHERE document_id = %s",
                (document_id,),
            )

            stored_chunks = []
            for index, chunk in enumerate(chunks):
                cur.execute(
                    """
                    INSERT INTO document_chunks (document_id, user_id, chunk_index, content)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, chunk_index, content
                    """,
                    (document_id, user_id, index, chunk),
                )
                chunk_id, chunk_index, content = cur.fetchone()
                stored_chunks.append(
                    {
                        "id": chunk_id,
                        "chunk_index": chunk_index,
                        "content": content,
                    }
                )

    return stored_chunks


def update_document_status(document_id: int, status: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET status = %s
                WHERE id = %s
                """,
                (status, document_id),
            )


def process_document(document_id: int, user_id: int, filename: str, object_key: str) -> str:
    try:
        text = extract_pdf_text(object_key)
        chunks = split_text_into_chunks(text)

        if not chunks:
            raise ValueError("No extractable text found in PDF")

        stored_chunks = store_document_chunks(
            document_id=document_id,
            user_id=user_id,
            chunks=chunks,
        )
        index_document_chunks(
            document_id=document_id,
            user_id=user_id,
            filename=filename,
            chunks=stored_chunks,
        )
        update_document_status(document_id=document_id, status="ready")
        return "ready"
    except Exception:
        update_document_status(document_id=document_id, status="failed")
        raise


def delete_document_for_user(document_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT object_key
                FROM documents
                WHERE id = %s AND user_id = %s
                """,
                (document_id, user_id),
            )
            row = cur.fetchone()

            if row is None:
                return False

            object_key = row[0]

            cur.execute(
                """
                DELETE FROM documents
                WHERE id = %s AND user_id = %s
                """,
                (document_id, user_id),
            )

    document_path = DOCUMENTS_DIR / object_key
    document_path.unlink(missing_ok=True)
    delete_document_vectors(document_id=document_id, user_id=user_id)

    return True
