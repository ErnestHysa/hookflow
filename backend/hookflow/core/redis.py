"""Redis connection and utilities."""

import json
from contextlib import asynccontextmanager

import redis.asyncio as redis
from tenacity import retry, stop_after_attempt, wait_exponential

from hookflow.core.config import settings


class RedisClient:
    """Async Redis client with connection pooling."""

    def __init__(self) -> None:
        self._pool: redis.ConnectionPool | None = None
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        """Create Redis connection pool."""
        self._pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._client = redis.Redis(connection_pool=self._pool)

    async def disconnect(self) -> None:
        """Close Redis connections."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()

    @property
    def client(self) -> redis.Redis:
        """Get Redis client (raises if not connected)."""
        if self._client is None:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    # Queue operations
    async def enqueue(self, queue_name: str, value: dict | str) -> int:
        """Add item to queue."""
        if isinstance(value, dict):
            value = json.dumps(value)
        return await self.client.lpush(queue_name, value)  # type: ignore

    async def dequeue(self, queue_name: str, timeout: int = 5) -> str | None:
        """Remove item from queue (blocking)."""
        result = await self.client.brpop(queue_name, timeout=timeout)
        if result:
            return result[1]  # (queue_name, value)
        return None

    async def queue_size(self, queue_name: str) -> int:
        """Get queue size."""
        return await self.client.llen(queue_name)  # type: ignore

    # Cache operations
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def get(self, key: str) -> str | None:
        """Get value from cache."""
        return await self.client.get(key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def set(
        self,
        key: str,
        value: str | dict | bytes,
        expire: int | None = None,
    ) -> bool:
        """Set value in cache."""
        if isinstance(value, dict):
            value = json.dumps(value)
        return await self.client.set(key, value, ex=expire)  # type: ignore

    async def delete(self, *keys: str) -> int:
        """Delete keys from cache."""
        return await self.client.delete(*keys)  # type: ignore

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self.client.exists(key) > 0  # type: ignore

    # Rate limiting
    async def incr_limit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Check and increment rate limit counter.
        Returns (allowed, current_count).
        """
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        results = await pipe.execute()
        current = results[0]  # type: ignore
        return current <= limit, current

    # Dead letter queue
    async def add_to_deadletter(
        self,
        app_id: str,
        webhook_id: str,
        error: str,
        payload: dict,
    ) -> None:
        """Add failed webhook to dead letter queue."""
        key = f"deadletter:{app_id}"
        value = json.dumps({
            "webhook_id": webhook_id,
            "error": error,
            "payload": payload,
            "timestamp": None,  # Will be set by worker
        })

        # Add to dead letter list
        await self.client.lpush(key, value)

        # Trim to max size
        await self.client.ltrim(key, 0, settings.webhook_max_deadletter - 1)

    async def get_deadletter_count(self, app_id: str) -> int:
        """Get dead letter queue size for app."""
        return await self.client.llen(f"deadletter:{app_id}")  # type: ignore


# Global Redis client
redis_client = RedisClient()


@asynccontextmanager
async def get_redis():
    """Context manager for Redis connection."""
    await redis_client.connect()
    try:
        yield redis_client
    finally:
        await redis_client.disconnect()
