import logging
import time

import httpcore
import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import ResponseHandlingException

from config import (
    EMBEDDING_VECTOR_SIZE,
    QDRANT_COLLECTION,
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_QUERY_MAX_RETRIES,
    QDRANT_QUERY_RETRY_DELAY_SECONDS,
    QDRANT_QUERY_TIMEOUT_SECONDS,
)
from embedding_client import embed_text, embed_texts
from query_embedding_cache import get_cached_query_embedding, set_cached_query_embedding

_qdrant_client: QdrantClient | None = None
UPSERT_BATCH_SIZE = 32
logger = logging.getLogger(__name__)


class SearchBackendUnavailableError(RuntimeError):
    pass


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client

    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            timeout=QDRANT_QUERY_TIMEOUT_SECONDS,
        )

    return _qdrant_client


def reset_qdrant_client() -> None:
    global _qdrant_client
    _qdrant_client = None


def _is_retryable_qdrant_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            ResponseHandlingException,
            httpx.RemoteProtocolError,
            httpx.ReadTimeout,
            httpcore.RemoteProtocolError,
            httpcore.ReadTimeout,
        ),
    )


def query_points_with_retry(**kwargs: object) -> qdrant_models.QueryResponse:
    last_error: Exception | None = None

    for attempt in range(1, QDRANT_QUERY_MAX_RETRIES + 1):
        client = get_qdrant_client()
        try:
            return client.query_points(**kwargs)
        except Exception as exc:
            last_error = exc
            if not _is_retryable_qdrant_error(exc) or attempt >= QDRANT_QUERY_MAX_RETRIES:
                break

            logger.warning(
                "Retrying Qdrant query after transient error on attempt %s/%s: %s",
                attempt,
                QDRANT_QUERY_MAX_RETRIES,
                exc,
            )
            reset_qdrant_client()
            time.sleep(QDRANT_QUERY_RETRY_DELAY_SECONDS)

    raise SearchBackendUnavailableError("Search backend temporarily unavailable") from last_error


def ensure_qdrant_collection() -> None:
    client = get_qdrant_client()

    existing_collections = client.get_collections().collections
    if any(collection.name == QDRANT_COLLECTION for collection in existing_collections):
        return

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=qdrant_models.VectorParams(
            size=EMBEDDING_VECTOR_SIZE,
            distance=qdrant_models.Distance.COSINE,
        ),
    )


def is_qdrant_ready() -> bool:
    try:
        get_qdrant_client().get_collections()
    except Exception:
        return False

    return True


def index_document_chunks(
    document_id: int,
    user_id: int,
    filename: str,
    chunks: list[dict[str, str | int]],
) -> None:
    if not chunks:
        return

    client = get_qdrant_client()

    for start_index in range(0, len(chunks), UPSERT_BATCH_SIZE):
        batch = chunks[start_index : start_index + UPSERT_BATCH_SIZE]
        texts = [str(chunk["content"]) for chunk in batch]
        vectors = embed_texts(texts)

        points = []
        for chunk, vector in zip(batch, vectors):
            points.append(
                qdrant_models.PointStruct(
                    id=int(chunk["id"]),
                    vector=vector,
                    payload={
                        "document_id": document_id,
                        "user_id": user_id,
                        "filename": filename,
                        "chunk_index": int(chunk["chunk_index"]),
                        "content": str(chunk["content"]),
                    },
                )
            )

        client.upsert(collection_name=QDRANT_COLLECTION, points=points)


def delete_document_vectors(document_id: int, user_id: int) -> None:
    client = get_qdrant_client()
    client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=qdrant_models.FilterSelector(
            filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="document_id",
                        match=qdrant_models.MatchValue(value=document_id),
                    ),
                    qdrant_models.FieldCondition(
                        key="user_id",
                        match=qdrant_models.MatchValue(value=user_id),
                    ),
                ]
            )
        ),
    )


def search_document_chunks(user_id: int, query: str, limit: int = 5) -> list[dict[str, str | int | float]]:
    query_vector = get_cached_query_embedding(query)
    if query_vector is None:
        query_vector = embed_text(query)
        set_cached_query_embedding(query, query_vector)

    response = query_points_with_retry(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        query_filter=qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="user_id",
                    match=qdrant_models.MatchValue(value=user_id),
                )
            ]
        ),
        limit=limit,
        with_payload=True,
    )

    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append(
            {
                "document_id": int(payload["document_id"]),
                "filename": str(payload["filename"]),
                "chunk_index": int(payload["chunk_index"]),
                "content": str(payload["content"]),
                "score": float(point.score),
            }
        )

    return results
