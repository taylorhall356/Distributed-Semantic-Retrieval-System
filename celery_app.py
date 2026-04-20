from celery import Celery

from config import (
    CELERY_BROKER_URL,
    DOCUMENT_EMBEDDING_QUEUE,
    DOCUMENT_PARSING_QUEUE,
)


celery_app = Celery(
    "distributed_semantic_retrieval_system",
    broker=CELERY_BROKER_URL,
)

celery_app.conf.update(
    task_default_queue=DOCUMENT_PARSING_QUEUE,
    task_ignore_result=True,
)


def enqueue_test_task(username: str):
    return celery_app.send_task(
        "tasks.ping",
        kwargs={"username": username},
        queue=DOCUMENT_PARSING_QUEUE,
    )


def enqueue_document_task(document_id: int, user_id: int, filename: str, object_key: str):
    return celery_app.send_task(
        "tasks.parse_document",
        kwargs={
            "document_id": document_id,
            "user_id": user_id,
            "filename": filename,
            "object_key": object_key,
        },
        queue=DOCUMENT_PARSING_QUEUE,
    )


def enqueue_document_embedding_task(document_id: int, user_id: int, filename: str):
    return celery_app.send_task(
        "tasks.embed_document",
        kwargs={
            "document_id": document_id,
            "user_id": user_id,
            "filename": filename,
        },
        queue=DOCUMENT_EMBEDDING_QUEUE,
    )
