from celery_app import celery_app


@celery_app.task(name="tasks.ping")
def ping(username: str) -> str:
    return f"queued by {username}"
