import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

# Best-effort speed layer in front of Postgres. Every operation degrades to a
# no-op (→ DB read) if Redis is slow or down — a cache outage must NEVER fail a
# request. A short connect timeout plus a cooldown circuit breaker stop us from
# blocking on (and hammering) a dead Redis on every single request.
_CONNECT_TIMEOUT = 0.5
_COOLDOWN_SECONDS = 30.0

_client: aioredis.Redis | None = None
_disabled_until = 0.0


def _enabled() -> bool:
    return settings.cache_enabled and time.monotonic() >= _disabled_until


def _trip(exc: Exception) -> None:
    global _disabled_until
    _disabled_until = time.monotonic() + _COOLDOWN_SECONDS
    logger.warning("cache disabled for %ss after error: %s", _COOLDOWN_SECONDS, exc)


def _get_client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=_CONNECT_TIMEOUT,
            socket_timeout=_CONNECT_TIMEOUT,
        )
    return _client


async def get_json(key: str) -> Any | None:
    if not _enabled():
        return None
    try:
        raw = await _get_client().get(key)
        return json.loads(raw) if raw is not None else None
    except (RedisError, OSError) as e:
        _trip(e)
        return None


async def set_json(key: str, value: Any, ttl: int) -> None:
    if not _enabled():
        return
    try:
        await _get_client().set(key, json.dumps(value), ex=ttl)
    except (RedisError, OSError) as e:
        _trip(e)


async def delete(*keys: str) -> None:
    if not _enabled() or not keys:
        return
    try:
        await _get_client().delete(*keys)
    except (RedisError, OSError) as e:
        _trip(e)


async def get_int(key: str) -> int:
    if not _enabled():
        return 0
    try:
        raw = await _get_client().get(key)
        return int(raw) if raw is not None else 0
    except (RedisError, OSError, ValueError) as e:
        _trip(e)
        return 0


async def bump(key: str) -> None:
    """Increment a generation counter — invalidates every key tagged with it."""
    if not _enabled():
        return
    try:
        await _get_client().incr(key)
    except (RedisError, OSError) as e:
        _trip(e)


async def close() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:
            pass
        _client = None
