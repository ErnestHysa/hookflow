"""Core modules."""

from hookflow.core.config import settings, get_settings
from hookflow.core.database import get_db, init_db, close_db
from hookflow.core.queue import queue_client

# Try to use Redis if available, otherwise use in-memory queue
try:
    from hookflow.core.redis import redis_client as _redis_client
    import asyncio

    # Test Redis connection
    async def test_redis():
        try:
            await _redis_client.connect()
            await _redis_client.disconnect()
            return True
        except:
            return False

    # Use Redis if available, otherwise fall back to in-memory
    # For now, always use in-memory for simplicity
    redis_client = queue_client
except:
    redis_client = queue_client

__all__ = [
    "settings",
    "get_settings",
    "get_db",
    "init_db",
    "close_db",
    "redis_client",
    "queue_client",
]
