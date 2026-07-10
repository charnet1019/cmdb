"""Async Redis client for presence tracking"""
import redis.asyncio as aioredis
from app.config import settings

_client: aioredis.Redis | None = None

# Presence key pattern and TTL
ONLINE_KEY_PREFIX = "user:online:"
ONLINE_TTL_SECONDS = 300  # 5 minutes


def get_redis() -> aioredis.Redis:
    """Get singleton async Redis client"""
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            health_check_interval=30,
            retry_on_timeout=False,
        )
    return _client
