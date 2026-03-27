from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import psycopg

from config import JWT_ALGORITHM, JWT_SECRET
from db import get_connection


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_password.decode("utf-8")


def create_user(username: str, password: str) -> dict[str, str | int]:
    password_hash = hash_password(password)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (username, password_hash)
                    VALUES (%s, %s)
                    RETURNING id, username
                    """,
                    (username, password_hash),
                )
                user_id, created_username = cur.fetchone()
        return {"id": user_id, "username": created_username}
    except psycopg.errors.UniqueViolation as exc:
        raise ValueError("Username already exists") from exc


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def authenticate_user(username: str, password: str) -> dict[str, str | int]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, password_hash
                FROM users
                WHERE username = %s
                """,
                (username,),
            )
            row = cur.fetchone()

    if row is None:
        raise ValueError("Invalid username or password")

    user_id, stored_username, password_hash = row

    if not verify_password(password, password_hash):
        raise ValueError("Invalid username or password")

    return {"id": user_id, "username": stored_username}


def create_access_token(user_id: int, username: str, expires_in_minutes: int = 60) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_in_minutes)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
