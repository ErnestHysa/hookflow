"""Server-Sent Events endpoint for real-time updates."""

import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from hookflow.services.event_broadcaster import get_broadcaster

router = APIRouter(prefix="/apps", tags=["events"])


@router.get("/{app_id}/events/stream")
async def events_stream(
    app_id: str,
):
    """
    Server-Sent Events stream for real-time webhook updates.

    Client should use EventSource to connect:
    const eventSource = new EventSource('/api/v1/apps/{app_id}/events/stream');
    eventSource.addEventListener('webhook.received', (e) => ...);
    """
    channel = f"app:{app_id}"
    broadcaster = get_broadcaster()

    async def event_generator():
        """Generate SSE events."""
        try:
            async for event in broadcaster.subscribe(channel):
                event_type = event.get("type", "message")
                yield {
                    "event": event_type,
                    "data": json.dumps(event.get("data", {})),
                }
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())
