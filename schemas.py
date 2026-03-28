from datetime import datetime

from pydantic import BaseModel, Field


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


class SearchResultResponse(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    content: str
    score: float
