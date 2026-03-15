"""In-memory queue for development (replaces Redis)."""

import asyncio
import json
from collections import deque
from datetime import datetime, timedelta, UTC
from typing import Any

from hookflow.core.config import settings


class InMemoryQueue:
    """Simple in-memory queue for development."""

    def __init__(self) -> None:
        self.queues: dict[str, deque] = {}
        self.dead_letters: dict[str, list[dict]] = {}
        self.rate_limits: dict[str, tuple[int, datetime]] = {}

    async def enqueue(self, queue_name: str, value: dict | str) -> int:
        """Add item to queue."""
        if queue_name not in self.queues:
            self.queues[queue_name] = deque()

        if isinstance(value, dict):
            value = json.dumps(value)

        self.queues[queue_name].append(value)
        return len(self.queues[queue_name])

    async def dequeue(self, queue_name: str, timeout: int = 5) -> str | None:
        """Remove item from queue (blocking simulation)."""
        if queue_name not in self.queues or not self.queues[queue_name]:
            await asyncio.sleep(0.1)  # Small delay to simulate blocking
            return None

        return self.queues[queue_name].popleft()

    async def queue_size(self, queue_name: str) -> int:
        """Get queue size."""
        return len(self.queues.get(queue_name, deque()))

    # Cache operations
    async def get(self, key: str) -> str | None:
        """Get value from cache."""
        return None  # Not implemented for in-memory

    async def set(
        self,
        key: str,
        value: str | dict | bytes,
        expire: int | None = None,
    ) -> bool:
        """Set value in cache."""
        return True  # Not implemented for in-memory

    async def delete(self, *keys: str) -> int:
        """Delete keys from cache."""
        return len(keys)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return False

    # Rate limiting
    async def incr_limit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Check and increment rate limit counter."""
        now = datetime.now(UTC)

        if key in self.rate_limits:
            count, reset_time = self.rate_limits[key]
            if now > reset_time:
                count = 0

        count = self.rate_limits.get(key, (0, now))[0] + 1
        reset_time = now + timedelta(seconds=window)

        self.rate_limits[key] = (count, reset_time)
        return count <= limit, count

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
        if key not in self.dead_letters:
            self.dead_letters[key] = []

        value = {
            "webhook_id": webhook_id,
            "error": error,
            "payload": payload,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        self.dead_letters[key].append(value)

        # Trim to max size
        if len(self.dead_letters[key]) > settings.webhook_max_deadletter:
            self.dead_letters[key] = self.dead_letters[key][-settings.webhook_max_deadletter :]

    async def get_deadletter_count(self, app_id: str) -> int:
        """Get dead letter queue size for app."""
        key = f"deadletter:{app_id}"
        return len(self.dead_letters.get(key, []))

    async def connect(self) -> None:
        """Connect (no-op for in-memory)."""
        pass

    async def disconnect(self) -> None:
        """Disconnect (no-op for in-memory)."""
        pass

    @property
    def client(self) -> "InMemoryQueue":
        """Get client (self for in-memory)."""
        return self


# Global queue instance
queue_client = InMemoryQueue()
