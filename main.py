from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from auth import create_user
from db import initialize_database, wait_for_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    wait_for_database()
    initialize_database()
    yield


app = FastAPI(
    title="Distributed Semantic Retrieval System",
    lifespan=lifespan,
)


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class SignupResponse(BaseModel):
    id: int
    username: str


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


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
