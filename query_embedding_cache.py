from __future__ import annotations

import hashlib
import json
import logging

from redis import Redis
from redis.exceptions import RedisError

from config import (
    QUERY_EMBEDDING_CACHE_LOGGING,
    QUERY_EMBEDDING_CACHE_TTL_SECONDS,
    REDIS_DB,
    REDIS_ENABLED,
    REDIS_HOST,
    REDIS_PORT,
)

logger = logging.getLogger(__name__)

_redis_client: Redis | None = None
_redis_disabled = False


def _cache_key(query: str) -> str:
    digest = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
    return f"query-embedding:{digest}"


def _query_digest(query: str) -> str:
    return hashlib.sha256(query.strip().encode("utf-8")).hexdigest()[:12]


def _log_cache_event(event: str, query: str, **extra: object) -> None:
    if not QUERY_EMBEDDING_CACHE_LOGGING:
        return

    details = ", ".join(f"{key}={value}" for key, value in extra.items())
    suffix = f", {details}" if details else ""
    logger.info(
        "Query embedding cache %s: query_hash=%s%s",
        event,
        _query_digest(query),
        suffix,
    )


def _get_redis_client() -> Redis | None:
    global _redis_client, _redis_disabled

    if not REDIS_ENABLED or _redis_disabled:
        return None

    if _redis_client is None:
        try:
            _redis_client = Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
            )
            _redis_client.ping()
            logger.info(
                "Query embedding cache connected to Redis at %s:%s db=%s",
                REDIS_HOST,
                REDIS_PORT,
                REDIS_DB,
            )
        except RedisError:
            logger.warning("Redis is unavailable; query embedding cache disabled")
            _redis_disabled = True
            _redis_client = None
            return None

    return _redis_client


def get_cached_query_embedding(query: str) -> list[float] | None:
    client = _get_redis_client()
    if client is None:
        return None

    try:
        cached_value = client.get(_cache_key(query))
    except RedisError:
        logger.warning("Redis get failed; continuing without query embedding cache")
        return None

    if cached_value is None:
        _log_cache_event("miss", query)
        return None

    try:
        payload = json.loads(cached_value)
    except json.JSONDecodeError:
        logger.warning("Redis returned invalid cached embedding payload")
        return None

    if not isinstance(payload, list):
        logger.warning("Redis returned non-list cached embedding payload")
        return None

    _log_cache_event("hit", query, length=len(payload))
    return [float(value) for value in payload]


def set_cached_query_embedding(query: str, embedding: list[float]) -> None:
    client = _get_redis_client()
    if client is None:
        return

    try:
        client.setex(
            _cache_key(query),
            QUERY_EMBEDDING_CACHE_TTL_SECONDS,
            json.dumps(embedding),
        )
        _log_cache_event(
            "store",
            query,
            ttl=QUERY_EMBEDDING_CACHE_TTL_SECONDS,
            length=len(embedding),
        )
    except RedisError:
        logger.warning("Redis set failed; continuing without query embedding cache")
