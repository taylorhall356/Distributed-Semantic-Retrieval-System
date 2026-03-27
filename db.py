import time
from pathlib import Path

import psycopg

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def wait_for_database(max_attempts: int = 10, delay_seconds: int = 2) -> None:
    last_error: Exception | None = None

    for _ in range(max_attempts):
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return
        except psycopg.OperationalError as exc:
            last_error = exc
            time.sleep(delay_seconds)

    raise RuntimeError("Database connection check failed") from last_error


def initialize_database() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
