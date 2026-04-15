from datetime import datetime

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class SignupResponse(BaseModel):
    message: str = "User created successfully"
    user_id: int


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: int


class CurrentUserResponse(BaseModel):
    id: str
    username: str


class DocumentResponse(BaseModel):
    document_id: int
    filename: str
    upload_date: datetime
    status: str
    page_count: int | None = None


class SearchResultResponse(BaseModel):
    text: str
    score: float
    document_id: int
    filename: str


class QueueTestResponse(BaseModel):
    task_id: str
    queue: str
    status: str
