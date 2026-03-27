import bcrypt
import psycopg

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
