from contextlib import asynccontextmanager
import logging
from time import perf_counter

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL_NAME

_embedding_model: SentenceTransformer | None = None
logger = logging.getLogger(__name__)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    return _embedding_model


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_embedding_model()
    yield


app = FastAPI(
    title="Embedding Service",
    lifespan=lifespan,
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready_check() -> dict[str, str]:
    if _embedding_model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding model is not loaded",
        )

    return {"status": "ready"}


@app.post("/embed", response_model=EmbedResponse)
def embed(payload: EmbedRequest) -> EmbedResponse:
    model = get_embedding_model()
    started = perf_counter()
    embeddings = model.encode(payload.texts).tolist()
    duration_ms = (perf_counter() - started) * 1000
    logger.info(
        "Generated embeddings",
        extra={
            "text_count": len(payload.texts),
            "duration_ms": round(duration_ms, 2),
        },
    )
    return EmbedResponse(
        embeddings=[[float(value) for value in embedding] for embedding in embeddings]
    )
