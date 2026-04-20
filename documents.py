import html
import logging
import re
from tempfile import NamedTemporaryFile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from config import DOCUMENT_PROCESSING_STALE_SECONDS, PDF_EXTRACTOR_BACKEND
from db import get_connection
from semantic_search import delete_document_vectors, index_document_chunks
from storage import delete_document_file, read_document_bytes
from celery_app import enqueue_document_embedding_task

MAX_PARAGRAPH_CHARS = 1200
MIN_INDEXABLE_CHARS = 80
MIN_PYMUPDF_WORDS = 8
MAX_PYMUPDF_NON_ALPHA_RATIO = 0.35
SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]?$")
STUDENT_ID_RE = re.compile(r"\bV\d{6,}\b")
DATE_RE = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}$")
MAJOR_SECTION_RE = re.compile(
    r"^(Introduction and Background|Methodology|Research Findings and Evidence|Policy Recommendations|Risk Mitigation Plan|Conclusion)$",
    re.IGNORECASE,
)
LIST_MARKER_RE = re.compile(r"(?:^|\s)[a-zA-Z]\)")
_docling_converter: Any | None = None
_docling_warmed = False
_torch_runtime_configured = False
logger = logging.getLogger(__name__)
DOCLING_WARMUP_PDF_BYTES = b"""%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 40 >>
stream
BT
/F1 18 Tf
72 72 Td
(Docling warmup) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000063 00000 n 
0000000122 00000 n 
0000000248 00000 n 
0000000338 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
408
%%EOF
"""


def configure_torch_runtime() -> None:
    global _torch_runtime_configured

    if _torch_runtime_configured:
        return

    import torch

    cpu_capability_getter = getattr(torch._C, "_get_cpu_capability", None)
    cpu_capability = cpu_capability_getter() if callable(cpu_capability_getter) else "unknown"

    if cpu_capability == "NO AVX" and torch.backends.mkldnn.enabled:
        torch.backends.mkldnn.enabled = False
        logger.warning(
            "Disabled torch MKLDNN backend for Docling because the host CPU capability "
            "is %s",
            cpu_capability,
        )

    _torch_runtime_configured = True


def validate_pdf(file: UploadFile) -> None:
    is_pdf_content_type = file.content_type == "application/pdf"
    has_pdf_extension = file.filename is not None and file.filename.lower().endswith(".pdf")

    if not (is_pdf_content_type or has_pdf_extension):
        raise ValueError("Only PDF files are supported")


def create_document(user_id: int, filename: str, object_key: str) -> dict[str, str | int | datetime]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (user_id, filename, object_key, status, error_message)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, filename, status, error_message, created_at, updated_at
                """,
                (user_id, filename, object_key, "processing", None),
            )
            document_id, stored_filename, status, error_message, created_at, updated_at = cur.fetchone()
        conn.commit()

    return {
        "id": document_id,
        "filename": stored_filename,
        "status": status,
        "error_message": error_message,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def list_documents_for_user(user_id: int) -> list[dict[str, str | int | datetime]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, status, error_message, created_at, updated_at
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
            "error_message": error_message,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        for document_id, filename, status, error_message, created_at, updated_at in rows
    ]


def get_document_for_user(document_id: int, user_id: int) -> dict[str, str | int | datetime] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, object_key, status, error_message, created_at, updated_at
                FROM documents
                WHERE id = %s AND user_id = %s
                """,
                (document_id, user_id),
            )
            row = cur.fetchone()

    if row is None:
        return None

    (
        stored_document_id,
        filename,
        object_key,
        status,
        error_message,
        created_at,
        updated_at,
    ) = row
    return {
        "id": stored_document_id,
        "filename": filename,
        "object_key": object_key,
        "status": status,
        "error_message": error_message,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def is_document_stale(document: dict[str, str | int | datetime]) -> bool:
    if document["status"] != "processing":
        return False

    updated_at = document.get("updated_at")
    if not isinstance(updated_at, datetime):
        return False

    stale_cutoff = datetime.now(timezone.utc) - timedelta(seconds=DOCUMENT_PROCESSING_STALE_SECONDS)
    return updated_at <= stale_cutoff


def extract_pdf_text(object_key: str) -> str:
    document_bytes = read_document_bytes(object_key)

    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(document_bytes)
        document_path = Path(temp_file.name)

    try:
        if PDF_EXTRACTOR_BACKEND == "pymupdf_blocks":
            return extract_pdf_text_with_pymupdf(document_path)
        return extract_pdf_text_with_docling(document_path)
    finally:
        document_path.unlink(missing_ok=True)


def get_docling_converter() -> Any:
    global _docling_converter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    configure_torch_runtime()

    if _docling_converter is None:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = False

        _docling_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )

    return _docling_converter


def warm_docling_pipeline() -> None:
    global _docling_warmed

    if _docling_warmed:
        return

    converter = get_docling_converter()

    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(DOCLING_WARMUP_PDF_BYTES)
        warmup_path = Path(temp_file.name)

    try:
        try:
            converter.convert(str(warmup_path))
        except Exception as exc:
            if "could not create a primitive" not in str(exc).lower():
                raise
            logger.warning(
                "Docling warmup hit a non-fatal inference error after asset load; "
                "continuing with warmed converter",
                exc_info=True,
            )
        _docling_warmed = True
    finally:
        warmup_path.unlink(missing_ok=True)


def extract_pdf_text_with_docling(document_path: Path) -> str:
    converter = get_docling_converter()
    result = converter.convert(str(document_path))
    return result.document.export_to_markdown().strip()


def extract_pdf_text_with_pymupdf(document_path: Path) -> str:
    import fitz

    paragraphs: list[str] = []

    with fitz.open(document_path) as document:
        for page in document:
            for block in page.get_text("blocks"):
                if len(block) < 5:
                    continue

                raw_text = str(block[4])
                cleaned_text = clean_pymupdf_paragraph_text(raw_text)
                if not is_valid_pymupdf_paragraph(cleaned_text):
                    continue

                paragraphs.extend(split_large_paragraph(cleaned_text))

    return "\n\n".join(paragraphs)


def clean_pymupdf_paragraph_text(text: str) -> str:
    return clean_text(text.replace("\n", " "))


def is_valid_pymupdf_paragraph(text: str) -> bool:
    if not text:
        return False

    if len(text) < MIN_INDEXABLE_CHARS:
        return False

    if len(text.split()) < MIN_PYMUPDF_WORDS:
        return False

    if text.isupper():
        return False

    if should_skip_chunk(text):
        return False

    non_space_chars = [char for char in text if not char.isspace()]
    if not non_space_chars:
        return False

    alpha_chars = sum(char.isalpha() for char in non_space_chars)
    non_alpha_chars = len(non_space_chars) - alpha_chars
    non_alpha_ratio = non_alpha_chars / len(non_space_chars)

    return non_alpha_ratio <= MAX_PYMUPDF_NON_ALPHA_RATIO


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
        if not SENTENCE_END_RE.search(text) and not is_short_indexable_text(text):
            return True

    if is_probable_front_matter(text):
        return True

    if is_probable_bibliography_entry(text):
        return True

    return False


def is_short_indexable_text(text: str) -> bool:
    words = text.split()
    if len(text) < 40 or len(words) < 6:
        return False

    alpha_words = sum(1 for word in words if any(char.isalpha() for char in word))
    if alpha_words < 4:
        return False

    list_marker_count = len(LIST_MARKER_RE.findall(text))
    has_technical_structure = any(marker in text for marker in ("=", ":", ";"))

    return list_marker_count >= 2 or has_technical_structure


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
        conn.commit()

    return stored_chunks


def get_stored_document_chunks(document_id: int, user_id: int) -> list[dict[str, str | int]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, chunk_index, content
                FROM document_chunks
                WHERE document_id = %s AND user_id = %s
                ORDER BY chunk_index ASC
                """,
                (document_id, user_id),
            )
            rows = cur.fetchall()

    return [
        {
            "id": chunk_id,
            "chunk_index": chunk_index,
            "content": content,
        }
        for chunk_id, chunk_index, content in rows
    ]


def update_document_status(document_id: int, status: str, error_message: str | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET status = %s,
                    error_message = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, error_message, document_id),
            )
        conn.commit()


def reset_document_for_retry(document_id: int, user_id: int) -> dict[str, str | int | datetime] | None:
    document = get_document_for_user(document_id=document_id, user_id=user_id)
    if document is None:
        return None

    can_retry = document["status"] == "failed" or is_document_stale(document)
    if not can_retry:
        return None

    delete_document_vectors(document_id=document_id, user_id=user_id)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM document_chunks
                WHERE document_id = %s AND user_id = %s
                """,
                (document_id, user_id),
            )
            cur.execute(
                """
                UPDATE documents
                SET status = %s,
                    error_message = NULL,
                    updated_at = NOW()
                WHERE id = %s AND user_id = %s
                RETURNING id, filename, status, error_message, created_at, updated_at, object_key
                """,
                ("processing", document_id, user_id),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        return None

    (
        retried_document_id,
        filename,
        status,
        error_message,
        created_at,
        updated_at,
        object_key,
    ) = row
    return {
        "id": retried_document_id,
        "filename": filename,
        "status": status,
        "error_message": error_message,
        "created_at": created_at,
        "updated_at": updated_at,
        "object_key": object_key,
    }


def parse_document_and_enqueue_embedding(
    document_id: int,
    user_id: int,
    filename: str,
    object_key: str,
) -> str:
    try:
        if PDF_EXTRACTOR_BACKEND != "pymupdf_blocks":
            warm_docling_pipeline()

        text = extract_pdf_text(object_key)
        if PDF_EXTRACTOR_BACKEND == "pymupdf_blocks":
            chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
        else:
            chunks = split_docling_markdown_into_chunks(text)

        if not chunks:
            raise ValueError("No extractable text found in PDF")

        stored_chunks = store_document_chunks(
            document_id=document_id,
            user_id=user_id,
            chunks=chunks,
        )
        if not stored_chunks:
            raise ValueError("No document chunks were stored for embedding")

        enqueue_document_embedding_task(
            document_id=document_id,
            user_id=user_id,
            filename=filename,
        )
        return "parsed"
    except Exception as exc:
        update_document_status(document_id=document_id, status="failed", error_message=str(exc))
        raise


def embed_document(document_id: int, user_id: int, filename: str) -> str:
    try:
        stored_chunks = get_stored_document_chunks(
            document_id=document_id,
            user_id=user_id,
        )
        if not stored_chunks:
            raise ValueError("No stored chunks found for embedding")

        index_document_chunks(
            document_id=document_id,
            user_id=user_id,
            filename=filename,
            chunks=stored_chunks,
        )
        update_document_status(document_id=document_id, status="ready")
        return "ready"
    except Exception as exc:
        update_document_status(document_id=document_id, status="failed", error_message=str(exc))
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
        conn.commit()

    delete_document_file(object_key)
    delete_document_vectors(document_id=document_id, user_id=user_id)

    return True
