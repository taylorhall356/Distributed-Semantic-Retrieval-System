from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from auth import authenticate_user, create_access_token, create_user
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


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
