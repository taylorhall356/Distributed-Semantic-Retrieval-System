from celery import Celery

from config import CELERY_BROKER_URL, DOCUMENT_PROCESSING_QUEUE


celery_app = Celery(
    "distributed_semantic_retrieval_system",
    broker=CELERY_BROKER_URL,
)

celery_app.conf.update(
    task_default_queue=DOCUMENT_PROCESSING_QUEUE,
    task_ignore_result=True,
)


def enqueue_test_task(username: str):
    return celery_app.send_task(
        "tasks.ping",
        kwargs={"username": username},
        queue=DOCUMENT_PROCESSING_QUEUE,
    )
