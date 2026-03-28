import html
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from docling.document_converter import DocumentConverter

from config import DOCUMENTS_DIR
from db import get_connection
from semantic_search import delete_document_vectors, index_document_chunks

MAX_PARAGRAPH_CHARS = 1200
MIN_INDEXABLE_CHARS = 80
SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]?$")
STUDENT_ID_RE = re.compile(r"\bV\d{6,}\b")
DATE_RE = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}$")
MAJOR_SECTION_RE = re.compile(
    r"^(Introduction and Background|Methodology|Research Findings and Evidence|Policy Recommendations|Risk Mitigation Plan|Conclusion)$",
    re.IGNORECASE,
)
_docling_converter: DocumentConverter | None = None


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
    return extract_pdf_text_with_docling(document_path)


def get_docling_converter() -> DocumentConverter:
    global _docling_converter

    if DocumentConverter is None:
        raise RuntimeError("Docling is not installed")

    if _docling_converter is None:
        _docling_converter = DocumentConverter()

    return _docling_converter


def extract_pdf_text_with_docling(document_path: Path) -> str:
    converter = get_docling_converter()
    result = converter.convert(str(document_path))
    return result.document.export_to_markdown().strip()


def normalize_markdown_line(line: str) -> str:
    normalized = re.sub(r"^#+\s*", "", line).strip()
    normalized = re.sub(r"^[-*+]\s+", "", normalized).strip()
    normalized = re.sub(r"^\d+[.)]\s+", "", normalized).strip()
    return clean_text(normalized)


def is_markdown_heading(line: str) -> bool:
    return line.lstrip().startswith("#")


def is_list_item(line: str) -> bool:
    stripped = line.lstrip()
    return bool(re.match(r"^([-*+]\s+|\d+[.)]\s+)", stripped))


def clean_text(text: str) -> str:
    replacements = {
        "\u00a0": " ",
        "\u200b": "",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "â": "'",
        "â": '"',
        "â": '"',
        "â": "-",
        "â": "-",
        "â¦": "...",
        "â": "",
    }
    cleaned = html.unescape(text)
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = cleaned.replace("Â·", "-")
    cleaned = cleaned.replace("&amp;", "&")
    cleaned = cleaned.replace("&nbsp;", " ")
    cleaned = cleaned.replace("&quot;", '"')
    cleaned = cleaned.replace("&#39;", "'")
    cleaned = cleaned.replace("Â", "")
    return " ".join(cleaned.split()).strip()


def should_skip_block(text: str) -> bool:
    if not text:
        return True

    if len(text) == 1 and not text.isalnum():
        return True

    words = text.split()
    if not words:
        return True

    if len(words) == 1 and len(text) <= 3 and text.isdigit():
        return True

    if len(words) == 1 and len(text) <= 2:
        return True

    if DATE_RE.fullmatch(text):
        return True

    if STUDENT_ID_RE.search(text) and len(text) < MIN_INDEXABLE_CHARS:
        return True

    if text.lower() in {"contents", "bibliography", "references"}:
        return True

    if MAJOR_SECTION_RE.fullmatch(text) and len(text) < MIN_INDEXABLE_CHARS:
        return True

    return False


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


def split_docling_markdown_into_chunks(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    chunks: list[str] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    skipping_contents = False

    def flush_chunk() -> None:
        nonlocal current_lines
        if not current_lines:
            return

        paragraph = clean_text(" ".join(current_lines))
        current_lines = []

        if not paragraph or should_skip_chunk(paragraph):
            return

        if current_heading and not is_probable_front_matter(current_heading):
            paragraph = clean_text(f"{current_heading}: {paragraph}")

        if not should_skip_chunk(paragraph):
            chunks.extend(split_large_paragraph(paragraph))

    for raw_line in lines:
        stripped = raw_line.strip()
        normalized = normalize_markdown_line(stripped)

        if not stripped:
            flush_chunk()
            continue

        if is_markdown_heading(stripped):
            flush_chunk()
            heading = normalized
            if is_bibliography_heading(heading):
                break
            if heading.lower() == "contents":
                skipping_contents = True
                current_heading = None
                continue
            if skipping_contents and is_body_heading(heading):
                skipping_contents = False
            if skipping_contents or should_skip_block(heading):
                current_heading = None
                continue
            current_heading = heading
            continue

        if skipping_contents:
            continue

        if is_markdown_table_line(stripped) or is_page_number_line(normalized):
            continue

        if not normalized or should_skip_docling_line(normalized):
            continue

        if is_list_item(stripped):
            flush_chunk()
            bullet_text = normalized
            if current_heading and not is_probable_front_matter(current_heading):
                bullet_text = clean_text(f"{current_heading}: {bullet_text}")
            if not should_skip_chunk(bullet_text):
                chunks.extend(split_large_paragraph(bullet_text))
            continue

        current_lines.append(normalized)

    flush_chunk()
    return chunks


def is_bibliography_heading(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {"bibliography", "references", "works cited"}


def is_body_heading(text: str) -> bool:
    lowered = text.strip().lower()
    return any(
        phrase in lowered
        for phrase in (
            "executive summary",
            "introduction",
            "background",
            "methodology",
            "findings",
            "discussion",
            "policy",
            "conclusion",
            "technical requirements",
            "api specification",
            "system architecture",
            "performance evaluation",
            "deliverables",
        )
    )


def should_skip_chunk(text: str) -> bool:
    if len(text) < MIN_INDEXABLE_CHARS:
        if is_heading_like(text):
            return True
        if not SENTENCE_END_RE.search(text):
            return True

    if is_probable_front_matter(text):
        return True

    if is_probable_bibliography_entry(text):
        return True

    return False


def is_probable_front_matter(text: str) -> bool:
    lowered = text.lower()
    if lowered.startswith("white paper draft:"):
        return True

    if STUDENT_ID_RE.search(text):
        return True

    if DATE_RE.fullmatch(text):
        return True

    return False


def is_probable_table_of_contents(text: str) -> bool:
    lowered = text.lower()
    section_hits = sum(
        phrase in lowered
        for phrase in (
            "executive summary",
            "contents",
            "introduction and background",
            "methodology",
            "bibliography",
        )
    )
    digit_count = sum(char.isdigit() for char in text)
    return section_hits >= 3 and digit_count >= 4


def is_probable_bibliography_entry(text: str) -> bool:
    lowered = text.lower()

    if "doi.org/" in lowered or "vol." in lowered:
        return True

    if '"' in text and len(text) < 400:
        return True

    return False


def is_markdown_table_line(line: str) -> bool:
    return line.startswith("|") and line.endswith("|")


def is_page_number_line(text: str) -> bool:
    return text.isdigit() and len(text) <= 3


def should_skip_docling_line(text: str) -> bool:
    lowered = text.lower()

    if should_skip_block(text):
        return True

    if is_probable_table_of_contents(text):
        return True

    if lowered.startswith("released:") or lowered.startswith("instructor:"):
        return True

    if lowered in {"team size:", "total points:"}:
        return True

    return False


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
        chunks = split_docling_markdown_into_chunks(text)

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
