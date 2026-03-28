from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer

from config import (
    EMBEDDING_MODEL_NAME,
    QDRANT_COLLECTION,
    QDRANT_HOST,
    QDRANT_PORT,
)

_embedding_model: SentenceTransformer | None = None
_qdrant_client: QdrantClient | None = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    return _embedding_model


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client

    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    return _qdrant_client


def ensure_qdrant_collection() -> None:
    client = get_qdrant_client()
    model = get_embedding_model()
    vector_size = model.get_sentence_embedding_dimension()

    existing_collections = client.get_collections().collections
    if any(collection.name == QDRANT_COLLECTION for collection in existing_collections):
        return

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=qdrant_models.VectorParams(
            size=vector_size,
            distance=qdrant_models.Distance.COSINE,
        ),
    )


def index_document_chunks(
    document_id: int,
    user_id: int,
    filename: str,
    chunks: list[dict[str, str | int]],
) -> None:
    if not chunks:
        return

    model = get_embedding_model()
    client = get_qdrant_client()
    texts = [str(chunk["content"]) for chunk in chunks]
    vectors = model.encode(texts).tolist()

    points = []
    for chunk, vector in zip(chunks, vectors):
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
