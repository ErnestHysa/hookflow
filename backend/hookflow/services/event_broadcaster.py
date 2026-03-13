"""Server-Sent Events broadcaster for real-time updates."""

import asyncio
import json
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, AsyncIterator

from sse_starlette.sse import EventSourceResponse


class EventBroadcaster(ABC):
    """Abstract base class for event broadcasting."""

    @abstractmethod
    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        """Publish an event to a channel."""
        pass

    @abstractmethod
    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to events on a channel."""
        pass


class InMemoryEventBroadcaster(EventBroadcaster):
    """
    In-memory event broadcaster for development.

    Uses asyncio queues to deliver events to subscribers.
    Not suitable for production with multiple worker processes.
    """

    def __init__(self) -> None:
        # channel -> list of queues
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        """Publish an event to all subscribers of a channel."""
        queues = self._subscribers.get(channel, [])
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop event if queue is full

    async def subscribe(
        self,
        channel: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to events on a channel."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[channel].append(queue)

        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[channel].remove(queue)


# Global broadcaster instance (in production, replace with Redis)
_broadcaster: EventBroadcaster | None = None


def get_broadcaster() -> EventBroadcaster:
    """Get the global event broadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = InMemoryEventBroadcaster()
    return _broadcaster
