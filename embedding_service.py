from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL_NAME

_embedding_model: SentenceTransformer | None = None


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


@app.post("/embed", response_model=EmbedResponse)
def embed(payload: EmbedRequest) -> EmbedResponse:
    model = get_embedding_model()
    embeddings = model.encode(payload.texts).tolist()
    return EmbedResponse(
        embeddings=[[float(value) for value in embedding] for embedding in embeddings]
    )
