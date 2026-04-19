from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status

from auth import authenticate_user, create_access_token, create_user, get_current_user
from celery_app import enqueue_document_task, enqueue_test_task
from config import DOCUMENT_PROCESSING_QUEUE
from db import get_connection
from documents import (
    create_document,
    delete_document_for_user,
    get_document_for_user,
    list_documents_for_user,
    reset_document_for_retry,
    validate_pdf,
)
from embedding_client import EmbeddingServiceError, is_embedding_service_ready
from schemas import (
    CurrentUserResponse,
    DocumentResponse,
    LoginRequest,
    LoginResponse,
    QueueTestResponse,
    SearchResultResponse,
    SignupRequest,
    SignupResponse,
)
from semantic_search import is_qdrant_ready, search_document_chunks
from storage import save_document_file


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="Distributed Semantic Retrieval System",
    lifespan=lifespan,
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


def is_database_ready() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception:
        return False

    return True


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    ready = (
        is_database_ready()
        and is_qdrant_ready()
        and is_embedding_service_ready()
    )
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service dependencies are not ready",
        )

    return {"status": "ready"}


@app.post(
    "/auth/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(payload: SignupRequest) -> SignupResponse:
    try:
        user = create_user(
            username=payload.username,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return SignupResponse(**user)


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    try:
        user = authenticate_user(
            username=payload.username,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    access_token = create_access_token(
        user_id=int(user["id"]),
        username=str(user["username"]),
    )
    return LoginResponse(access_token=access_token)


@app.get("/me", response_model=CurrentUserResponse)
def get_me(current_user: dict[str, str] = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(**current_user)


@app.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict[str, str] = Depends(get_current_user),
) -> DocumentResponse:
    try:
        validate_pdf(file)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    object_key = await save_document_file(file)
    document = create_document(
        user_id=int(current_user["id"]),
        filename=file.filename or "document.pdf",
        object_key=object_key,
    )

    enqueue_document_task(
        document_id=int(document["id"]),
        user_id=int(current_user["id"]),
        filename=file.filename or "document.pdf",
        object_key=object_key,
    )

    return DocumentResponse(**document)


@app.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    current_user: dict[str, str] = Depends(get_current_user),
) -> list[DocumentResponse]:
    documents = list_documents_for_user(user_id=int(current_user["id"]))
    return [DocumentResponse(**document) for document in documents]


@app.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: dict[str, str] = Depends(get_current_user),
) -> None:
    deleted = delete_document_for_user(
        document_id=document_id,
        user_id=int(current_user["id"]),
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )


@app.post(
    "/documents/{document_id}/retry",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_document(
    document_id: int,
    current_user: dict[str, str] = Depends(get_current_user),
) -> DocumentResponse:
    existing_document = get_document_for_user(
        document_id=document_id,
        user_id=int(current_user["id"]),
    )
    if existing_document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    document = reset_document_for_retry(
        document_id=document_id,
        user_id=int(current_user["id"]),
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed or stale processing documents can be retried",
        )

    enqueue_document_task(
        document_id=int(document["id"]),
        user_id=int(current_user["id"]),
        filename=str(document["filename"]),
        object_key=str(document["object_key"]),
    )

    document.pop("object_key", None)
    return DocumentResponse(**document)


@app.get("/search", response_model=list[SearchResultResponse])
def search_documents(
    q: str = Query(min_length=1),
    current_user: dict[str, str] = Depends(get_current_user),
) -> list[SearchResultResponse]:
    try:
        results = search_document_chunks(
            user_id=int(current_user["id"]),
            query=q,
        )
    except EmbeddingServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return [SearchResultResponse(**result) for result in results]


@app.post("/queue-test", response_model=QueueTestResponse, status_code=status.HTTP_202_ACCEPTED)
def queue_test(
    current_user: dict[str, str] = Depends(get_current_user),
) -> QueueTestResponse:
    task = enqueue_test_task(username=str(current_user["username"]))
    return QueueTestResponse(
        task_id=task.id,
        queue=DOCUMENT_PROCESSING_QUEUE,
        status="queued",
    )
