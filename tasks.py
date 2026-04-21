import logging
import os

from celery.signals import worker_process_init

from celery_app import celery_app
from config import PDF_EXTRACTOR_BACKEND
from documents import embed_document, parse_document_and_enqueue_embedding, warm_docling_pipeline

logger = logging.getLogger(__name__)


@worker_process_init.connect
def warm_parsing_worker_process(**_: object) -> None:
    if os.getenv("WORKER_ROLE", "").strip().lower() != "parsing":
        return

    if PDF_EXTRACTOR_BACKEND != "docling":
        logger.info(
            "Skipping Docling warmup for parsing worker process because "
            "PDF_EXTRACTOR_BACKEND=%s",
            PDF_EXTRACTOR_BACKEND,
        )
        return

    logger.info("Warming Docling pipeline for parsing worker process")
    warm_docling_pipeline()
    logger.info("Docling pipeline warmup complete for parsing worker process")


@celery_app.task(name="tasks.ping")
def ping(username: str) -> str:
    return f"queued by {username}"


@celery_app.task(name="tasks.parse_document")
def parse_document_task(document_id: int, user_id: int, filename: str, object_key: str) -> str:
    return parse_document_and_enqueue_embedding(
        document_id=document_id,
        user_id=user_id,
        filename=filename,
        object_key=object_key,
    )


@celery_app.task(name="tasks.embed_document")
def embed_document_task(document_id: int, user_id: int, filename: str) -> str:
    return embed_document(
        document_id=document_id,
        user_id=user_id,
        filename=filename,
    )
