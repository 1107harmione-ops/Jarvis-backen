"""
Redis client initialization and connection management.
"""
from typing import Optional
from redis.asyncio import Redis, ConnectionPool
from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

_redis: Optional[Redis] = None
_pool: Optional[ConnectionPool] = None


async def init_redis() -> Redis:
    """Initialize Redis connection pool."""
    global _redis, _pool
    settings = get_settings()

    if not settings.redis_url:
        logger.warning("No REDIS_URL configured — skipping Redis initialization")
        return None

    try:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            socket_timeout=settings.redis_socket_timeout,
            decode_responses=True,
        )
        _redis = Redis(connection_pool=_pool)

        # Test connection
        await _redis.ping()
        logger.info(f"Redis connected: {settings.redis_url}")
        return _redis

    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        _redis = None
        return None


async def get_redis() -> Optional[Redis]:
    """Get the Redis client instance."""
    global _redis
    if _redis is None:
        await init_redis()
    return _redis


async def close_redis():
    """Close Redis connection pool."""
    global _redis, _pool
    if _pool:
        await _pool.disconnect()
    _redis = None
    _pool = None
    logger.info("Redis connection closed")


async def rate_limit_check(key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
    """
    Check rate limit using Redis sliding window.
    Returns (allowed: bool, current_count: int).
    Falls back to allowing request if Redis is unavailable.
    """
    redis = await get_redis()
    if redis is None:
        return True, 0

    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)

        if current > max_requests:
            ttl = await redis.ttl(key)
            return False, current

        return True, current
    except Exception as e:
        logger.warning(f"Rate limit check failed: {e}")
        return True, 0
