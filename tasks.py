from celery_app import celery_app
from documents import process_document, warm_docling_pipeline

warm_docling_pipeline()


@celery_app.task(name="tasks.ping")
def ping(username: str) -> str:
    return f"queued by {username}"


@celery_app.task(name="tasks.process_document")
def process_document_task(document_id: int, user_id: int, filename: str, object_key: str) -> str:
    return process_document(
        document_id=document_id,
        user_id=user_id,
        filename=filename,
        object_key=object_key,
    )
