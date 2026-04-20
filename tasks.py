from celery_app import celery_app
from documents import embed_document, parse_document_and_enqueue_embedding


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
