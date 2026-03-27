from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from auth import authenticate_user, create_access_token, create_user, get_current_user
from db import initialize_database, wait_for_database
from documents import (
    create_document,
    ensure_documents_directory,
    list_documents_for_user,
    save_document_file,
    validate_pdf,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    wait_for_database()
    initialize_database()
    ensure_documents_directory()
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


class CurrentUserResponse(BaseModel):
    id: str
    username: str


class DocumentResponse(BaseModel):
    id: int
    filename: str
    status: str
    created_at: datetime


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
    return DocumentResponse(**document)


@app.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    current_user: dict[str, str] = Depends(get_current_user),
) -> list[DocumentResponse]:
    documents = list_documents_for_user(user_id=int(current_user["id"]))
    return [DocumentResponse(**document) for document in documents]
