from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import wait_for_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    wait_for_database()
    yield


app = FastAPI(
    title="Distributed Semantic Retrieval System",
    lifespan=lifespan,
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
