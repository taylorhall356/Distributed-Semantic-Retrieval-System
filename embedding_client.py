import json
from urllib import error, request

from config import EMBEDDING_SERVICE_URL


def embed_texts(texts: list[str]) -> list[list[float]]:
    payload = json.dumps({"texts": texts}).encode("utf-8")
    req = request.Request(
        url=f"{EMBEDDING_SERVICE_URL}/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError("Embedding service request failed") from exc

    embeddings = body.get("embeddings")
    if not isinstance(embeddings, list):
        raise RuntimeError("Embedding service returned an invalid response")

    return [[float(value) for value in embedding] for embedding in embeddings]


def embed_text(text: str) -> list[float]:
    embeddings = embed_texts([text])
    if not embeddings:
        raise RuntimeError("Embedding service returned no embeddings")
    return embeddings[0]
