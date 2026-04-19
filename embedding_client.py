import json
import logging
from time import perf_counter
from urllib import error, request

from config import EMBEDDING_REQUEST_TIMEOUT_SECONDS, EMBEDDING_SERVICE_URL

logger = logging.getLogger(__name__)


class EmbeddingServiceError(RuntimeError):
    pass


def is_embedding_service_ready() -> bool:
    req = request.Request(
        url=f"{EMBEDDING_SERVICE_URL}/ready",
        method="GET",
    )

    try:
        with request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except error.URLError:
        return False


def embed_texts(texts: list[str]) -> list[list[float]]:
    payload = json.dumps({"texts": texts}).encode("utf-8")
    req = request.Request(
        url=f"{EMBEDDING_SERVICE_URL}/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = perf_counter()
    try:
        with request.urlopen(req, timeout=EMBEDDING_REQUEST_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise EmbeddingServiceError(
            f"Embedding service returned HTTP {exc.code}"
        ) from exc
    except error.URLError as exc:
        raise EmbeddingServiceError("Embedding service request failed") from exc
    finally:
        duration_ms = (perf_counter() - started) * 1000
        logger.info(
            "Embedding request completed",
            extra={
                "text_count": len(texts),
                "duration_ms": round(duration_ms, 2),
            },
        )

    embeddings = body.get("embeddings")
    if not isinstance(embeddings, list):
        raise EmbeddingServiceError("Embedding service returned an invalid response")

    return [[float(value) for value in embedding] for embedding in embeddings]


def embed_text(text: str) -> list[float]:
    embeddings = embed_texts([text])
    if not embeddings:
        raise EmbeddingServiceError("Embedding service returned no embeddings")
    return embeddings[0]
