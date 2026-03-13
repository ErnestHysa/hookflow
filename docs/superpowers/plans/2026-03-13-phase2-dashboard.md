# Phase 2: Dashboard & Core Features - Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build complete webhook management dashboard with analytics, real-time status, destination management, and API key management.

**Architecture:**
- Frontend: Next.js 14 App Router with TypeScript, shadcn/ui components, recharts for visualization
- Backend: FastAPI with new analytics service, API key service, SSE event broadcaster
- Real-time: Server-Sent Events (SSE) with Redis pub/sub (production) or in-memory (dev)
- Authentication: Unauthenticated demo mode (full auth comes in Phase 5)

**Tech Stack:**
- Frontend: Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui, recharts
- Backend: FastAPI, SQLAlchemy, PostgreSQL, Redis (for SSE), sse-starlette
- Testing: pytest, Playwright (E2E)

---

## File Structure

### Backend Files to Create
```
backend/hookflow/
├── services/
│   ├── analytics.py          # AnalyticsService with aggregation queries
│   ├── api_key.py            # ApiKeyService for CRUD operations
│   └── event_broadcaster.py  # SSE event broadcasting (Redis + in-memory)
├── api/
│   ├── analytics.py          # Analytics endpoints
│   ├── api_keys.py           # API key endpoints
│   ├── destinations.py       # Destination management + test endpoint
│   └── events.py             # SSE stream endpoint
├── schemas/
│   └── analytics.py          # Analytics response schemas
├── scripts/
│   └── migrate_to_clerk.py   # Placeholder for Phase 5 (create directory now)
└── api/
    └── dependencies.py       # Auth middleware placeholder for Phase 5
```

### Frontend Files to Create
```
frontend/src/
├── app/dashboard/
│   ├── page.tsx              # Dashboard overview
│   ├── app/
│   │   ├── [id]/
│   │   │   ├── page.tsx      # App detail
│   │   │   ├── webhooks/
│   │   │   │   ├── page.tsx  # Webhook list
│   │   │   │   └── [webhookId]/
│   │   │   │       └── page.tsx  # Webhook detail
│   │   │   ├── destinations/
│   │   │   │   └── page.tsx  # Destination management
│   │   │   └── settings/
│   │   │       └── page.tsx  # App settings + API keys
├── components/dashboard/
│   ├── stat-card.tsx
│   ├── webhook-table.tsx
│   ├── webhook-detail.tsx
│   ├── delivery-timeline.tsx
│   ├── destination-list.tsx
│   ├── destination-form.tsx
│   ├── api-key-list.tsx
│   └── event-stream.tsx
├── components/charts/
│   ├── webhook-chart.tsx
│   └── status-donut.tsx
├── components/ui/
│   ├── json-viewer.tsx
│   └── status-badge.tsx
└── lib/
    └── api-clients.ts        # API client functions
```

---

## Chunk 1: Prerequisites & Backend Foundation

### Task 1: Initialize Alembic for database migrations

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/.gitkeep`

- [ ] **Step 1: Install Alembic**

```bash
cd backend
pip install alembic
```

- [ ] **Step 2: Initialize Alembic**

```bash
alembic init alembic
```

- [ ] **Step 3: Configure alembic.ini for async database**

Edit `backend/alembic.ini`, set sqlalchemy.url:
```ini
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost/hookflow
```

- [ ] **Step 4: Configure env.py for AsyncSession**

Replace `backend/alembic/env.py` with async-compatible version:
```python
from asyncio import run
from sqlalchemy.ext.asyncio import async_engine_from_config

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        future=True,
    )

    async def do_run_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_alembic_upgrade)
            await connection.commit()

    run(do_run_migrations())
```

- [ ] **Step 5: Commit**

```bash
git add backend/alembic.ini backend/alembic/ backend/pyproject.toml
git commit -m "feat: initialize Alembic for database migrations"
```

### Task 2: Create directory structure

**Files:**
- Create: `backend/hookflow/scripts/.gitkeep`
- Create: `backend/hookflow/api/dependencies.py`

- [ ] **Step 1: Create scripts directory**

```bash
mkdir -p backend/hookflow/scripts
touch backend/hookflow/scripts/.gitkeep
```

- [ ] **Step 2: Create dependencies.py with placeholder auth**

```python
# backend/hookflow/api/dependencies.py
"""API dependencies for authentication and authorization."""

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.core.database import get_db


async def get_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> str | None:
    """
    Validate API key and return app_id.

    Placeholder for Phase 2. In Phase 5, this will:
    1. Hash the provided key and look up in ApiKey table
    2. Update last_used_at timestamp
    3. Return the associated app_id

    For now, returns None (no auth in Phase 2).
    """
    # TODO: Implement API key validation in Phase 2c
    return None


async def require_auth(app_id: str | None = None) -> str:
    """
    Require authentication. Returns app_id.

    Placeholder for Phase 5 (Clerk integration).
    For Phase 2, this is a no-op.
    """
    if app_id is None:
        # In Phase 2, allow unauthenticated access for demo
        return "demo"
    return app_id
```

- [ ] **Step 3: Commit**

```bash
git add backend/hookflow/scripts/ backend/hookflow/api/dependencies.py
git commit -m "feat: add placeholder auth dependencies for Phase 2"
```

### Task 3: Analytics Service and API

**Files:**
- Create: `backend/hookflow/schemas/analytics.py`
- Create: `backend/hookflow/services/analytics.py`
- Create: `backend/hookflow/api/analytics.py`

- [ ] **Step 1: Write analytics schemas**

```python
# backend/hookflow/schemas/analytics.py
"""Analytics schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


class AnalyticsResponse(BaseModel):
    """Analytics overview response."""

    total_webhooks: int
    success_rate: float
    avg_response_time_ms: float
    webhooks_by_status: dict[str, int]
    webhooks_over_time: list[dict[str, int | str]]
    top_destinations: list[dict[str, int | float | str]]


class TimeSeriesDataPoint(BaseModel):
    """Time series data point."""

    timestamp: str
    count: int


class DestinationStats(BaseModel):
    """Destination statistics."""

    name: str
    count: int
    success_rate: float
```

- [ ] **Step 2: Write analytics service**

```python
# backend/hookflow/services/analytics.py
"""Analytics service for webhook statistics."""

from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.models import Delivery, Webhook
from hookflow.schemas.analytics import AnalyticsResponse


class AnalyticsService:
    """Service for computing webhook analytics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_analytics(
        self,
        app_id: str,
        period: str = "24h",
    ) -> AnalyticsResponse:
        """
        Get analytics for an app over a time period.

        Args:
            app_id: Application ID
            period: Time period (24h, 7d, 30d)

        Returns:
            AnalyticsResponse with aggregated statistics
        """
        # Calculate time range
        now = datetime.utcnow()
        if period == "24h":
            start_time = now - timedelta(hours=24)
            bucket = "hour"
        elif period == "7d":
            start_time = now - timedelta(days=7)
            bucket = "day"
        else:  # 30d
            start_time = now - timedelta(days=30)
            bucket = "day"

        # Total webhooks
        total_result = await self.db.execute(
            select(func.count())
            .select_from(Webhook)
            .where(Webhook.app_id == app_id)
            .where(Webhook.created_at >= start_time)
        )
        total_webhooks = total_result.scalar() or 0

        # Success rate (completed vs total)
        completed_result = await self.db.execute(
            select(func.count())
            .select_from(Webhook)
            .where(Webhook.app_id == app_id)
            .where(Webhook.created_at >= start_time)
            .where(Webhook.status == "completed")
        )
        completed = completed_result.scalar() or 0
        success_rate = (completed / total_webhooks * 100) if total_webhooks > 0 else 0

        # Avg response time
        avg_time_result = await self.db.execute(
            select(func.avg(Delivery.response_time_ms))
            .join(Webhook, Webhook.id == Delivery.webhook_id)
            .where(Webhook.app_id == app_id)
            .where(Delivery.response_time_ms.isnot(None))
            .where(Webhook.created_at >= start_time)
        )
        avg_response_time = avg_time_result.scalar() or 0

        # Webhooks by status
        status_result = await self.db.execute(
            select(Webhook.status, func.count())
            .where(Webhook.app_id == app_id)
            .where(Webhook.created_at >= start_time)
            .group_by(Webhook.status)
        )
        webhooks_by_status = {status: count for status, count in status_result.all()}

        # Webhooks over time
        time_series_result = await self.db.execute(
            select(
                func.date_trunc(bucket, Webhook.created_at).label("time"),
                func.count(),
            )
            .where(Webhook.app_id == app_id)
            .where(Webhook.created_at >= start_time)
            .group_by("time")
            .order_by("time")
        )
        webhooks_over_time = [
            {"timestamp": str(ts), "count": count}
            for ts, count in time_series_result.all()
        ]

        # Top destinations (by delivery count)
        dest_result = await self.db.execute(
            select(
                Destination.name,
                func.count(Delivery.id).label("count"),
                func.sum(
                    case(
                        (Delivery.status == "success", 1),
                        else_=0,
                    )
                )
                / cast(func.count(Delivery.id), Float)
                * 100,
            )
            .join(Delivery, Delivery.destination_id == Destination.id)
            .join(Webhook, Webhook.id == Delivery.webhook_id)
            .where(Webhook.app_id == app_id)
            .where(Webhook.created_at >= start_time)
            .group_by(Destination.name)
            .order_by(func.count(Delivery.id).desc())
            .limit(5)
        )
        top_destinations = [
            {"name": name, "count": count, "success_rate": rate}
            for name, count, rate in dest_result.all()
        ]

        return AnalyticsResponse(
            total_webhooks=total_webhooks,
            success_rate=round(success_rate, 2),
            avg_response_time_ms=round(avg_response_time, 2),
            webhooks_by_status=webhooks_by_status,
            webhooks_over_time=webhooks_over_time,
            top_destinations=top_destinations,
        )
```

- [ ] **Step 3: Write analytics API endpoint**

```python
# backend/hookflow/api/analytics.py
"""Analytics API endpoints."""

from fastapi import APIRouter, Depends

from hookflow.core.database import get_db
from hookflow.schemas.analytics import AnalyticsResponse
from hookflow.services.analytics import AnalyticsService

router = APIRouter(prefix="/apps", tags=["analytics"])


async def get_analytics_service(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsService:
    """Get analytics service instance."""
    return AnalyticsService(db)


@router.get(
    "/{app_id}/analytics",
    response_model=AnalyticsResponse,
    summary="Get analytics for an app",
)
async def get_analytics(
    app_id: str,
    period: str = "24h",
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Get webhook analytics for an app."""
    if period not in ("24h", "7d", "30d"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 24h, 7d, or 30d")

    return await service.get_analytics(app_id, period)
```

- [ ] **Step 4: Register analytics router in main.py**

Edit `backend/hookflow/main.py`, add:
```python
from hookflow.api.analytics import router as analytics_router

app.include_router(analytics_router, prefix="/api/v1")
```

- [ ] **Step 5: Commit**

```bash
git add backend/hookflow/schemas/analytics.py backend/hookflow/services/analytics.py backend/hookflow/api/analytics.py backend/hookflow/main.py
git commit -m "feat: add analytics service and API endpoint"
```

### Task 4: API Key Service and API

**Files:**
- Create: `backend/hookflow/services/api_key.py`
- Create: `backend/hookflow/api/api_keys.py`

- [ ] **Step 1: Write API key service**

```python
# backend/hookflow/services/api_key.py
"""API key management service."""

import hashlib
import secrets
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.models import ApiKey, App


class ApiKeyService:
    """Service for managing API keys."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_api_key(
        self,
        app_id: str,
        name: str,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[ApiKey, str]:
        """
        Create a new API key.

        Returns:
            Tuple of (ApiKey model, plain_text_key)
            The plain text key is only returned once!
        """
        # Generate key
        plain_key = f"hf_{secrets.token_urlsafe(32)}"
        key_prefix = plain_key[:10]
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()

        api_key = ApiKey(
            app_id=app_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes or [],
            expires_at=expires_at,
        )

        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)

        return api_key, plain_key

    async def list_api_keys(self, app_id: str) -> list[ApiKey]:
        """List all API keys for an app (without full keys)."""
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.app_id == app_id)
            .where(ApiKey.is_active == True)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke_api_key(self, api_key_id: str, app_id: str) -> bool:
        """Revoke an API key."""
        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.id == api_key_id,
                ApiKey.app_id == app_id,
            )
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            return False

        api_key.is_active = False
        await self.db.commit()
        return True

    async def validate_api_key(self, plain_key: str) -> ApiKey | None:
        """
        Validate an API key and update last_used_at.

        Returns:
            ApiKey if valid, None otherwise
        """
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()

        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,
            )
        )
        api_key = result.scalar_one_or_none()

        if api_key:
            # Check expiration
            if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                return None

            # Update last used
            api_key.last_used_at = datetime.utcnow()
            await self.db.commit()

        return api_key
```

- [ ] **Step 2: Write API key endpoints**

```python
# backend/hookflow/api/api_keys.py
"""API key management endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.core.database import get_db
from hookflow.services.api_key import ApiKeyService

router = APIRouter(prefix="/apps", tags=["api-keys"])


class ApiKeyCreateRequest(BaseModel):
    """Request to create API key."""

    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class ApiKeyCreateResponse(BaseModel):
    """Response when creating API key (includes full key)."""

    id: str
    name: str
    key: str  # Full key - only shown once!
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime


class ApiKeyResponse(BaseModel):
    """Response when listing API keys (no full key)."""

    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime


async def get_api_key_service(
    db: AsyncSession = Depends(get_db),
) -> ApiKeyService:
    """Get API key service instance."""
    return ApiKeyService(db)


@router.post(
    "/{app_id}/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    app_id: str,
    request: ApiKeyCreateRequest,
    service: ApiKeyService = Depends(get_api_key_service),
):
    """Create a new API key. Returns the full key - save it now!"""
    api_key, plain_key = await service.create_api_key(
        app_id=app_id,
        name=request.name,
        scopes=request.scopes,
        expires_at=request.expires_at,
    )

    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=plain_key,  # Only shown once!
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("/{app_id}/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    app_id: str,
    service: ApiKeyService = Depends(get_api_key_service),
):
    """List all API keys for an app (full keys not shown)."""
    api_keys = await service.list_api_keys(app_id)

    return [
        ApiKeyResponse(
            id=key.id,
            name=key.name,
            key_prefix=key.key_prefix,
            scopes=key.scopes,
            last_used_at=key.last_used_at,
            expires_at=key.expires_at,
            created_at=key.created_at,
        )
        for key in api_keys
    ]


@router.delete("/{app_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    app_id: str,
    key_id: str,
    service: ApiKeyService = Depends(get_api_key_service),
):
    """Revoke an API key."""
    success = await service.revoke_api_key(key_id, app_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
```

- [ ] **Step 3: Register router in main.py**

Edit `backend/hookflow/main.py`:
```python
from hookflow.api.api_keys import router as api_keys_router

app.include_router(api_keys_router, prefix="/api/v1")
```

- [ ] **Step 4: Commit**

```bash
git add backend/hookflow/services/api_key.py backend/hookflow/api/api_keys.py backend/hookflow/main.py
git commit -m "feat: add API key management service and endpoints"
```

### Task 5: SSE Event Broadcaster

**Files:**
- Create: `backend/hookflow/services/event_broadcaster.py`
- Install: `sse-starlette`

- [ ] **Step 1: Install sse-starlette**

```bash
cd backend
pip install sse-starlette
```

- [ ] **Step 2: Write event broadcaster**

```python
# backend/hookflow/services/event_broadcaster.py
"""Server-Sent Events broadcaster for real-time updates."""

import asyncio
import json
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any

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
```

- [ ] **Step 3: Write SSE events endpoint**

```python
# backend/hookflow/api/events.py
"""Server-Sent Events endpoint for real-time updates."""

from fastapi import APIRouter, Query
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
```

- [ ] **Step 4: Update webhook service to publish events**

Edit `backend/hookflow/services/webhook.py`, add to imports:
```python
from hookflow.services.event_broadcaster import get_broadcaster
```

In `receive_webhook` method, after creating webhook:
```python
# Publish event
broadcaster = get_broadcaster()
await broadcaster.publish(
    f"app:{app_id}",
    {
        "type": "webhook.received",
        "data": {
            "webhook_id": str(webhook.id),
            "status": webhook.status,
            "timestamp": webhook.created_at.isoformat(),
        },
    },
)
```

In `deliver_webhook` method, after successful delivery:
```python
await broadcaster.publish(
    f"app:{webhook.app_id}",
    {
        "type": "delivery.success",
        "data": {
            "webhook_id": str(webhook_id),
            "destination_id": str(destination_id),
            "response_time_ms": result.get("response_time_ms", 0),
        },
    },
)
```

After failed delivery:
```python
await broadcaster.publish(
    f"app:{webhook.app_id}",
    {
        "type": "delivery.failed",
        "data": {
            "webhook_id": str(webhook_id),
            "destination_id": str(destination_id),
            "error": str(e),
        },
    },
)
```

- [ ] **Step 5: Register router in main.py**

```python
from hookflow.api.events import router as events_router

app.include_router(events_router, prefix="/api/v1")
```

- [ ] **Step 6: Commit**

```bash
git add backend/hookflow/services/event_broadcaster.py backend/hookflow/api/events.py backend/hookflow/services/webhook.py backend/hookflow/main.py backend/pyproject.toml
git commit -m "feat: add SSE event broadcaster for real-time updates"
```

---

## Chunk 2: Destination Management Enhancements

### Task 6: Test Destination Endpoint

**Files:**
- Modify: `backend/hookflow/api/webhooks.py` (add test endpoint)

- [ ] **Step 1: Add test destination endpoint**

Edit `backend/hookflow/api/webhooks.py`, add:

```python
@router.post(
    "/apps/{app_id}/destinations/{destination_id}/test",
    summary="Test a destination",
    tags=["destinations"],
)
async def test_destination(
    app_id: str,
    destination_id: str,
    test_payload: dict | None = None,
    service: WebhookService = Depends(get_webhook_service),
):
    """
    Test a destination with a sample webhook payload.

    Sends a test webhook to the destination and returns the result.
    """
    from hookflow.models import Destination

    # Get destination
    result = await service.db.execute(
        select(Destination).where(
            Destination.id == destination_id,
            Destination.app_id == app_id,
        )
    )
    destination = result.scalar_one_or_none()

    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")

    # Create test webhook
    test_webhook = Webhook(
        app_id=app_id,
        body=test_payload or {"event": "test", "message": "This is a test webhook"},
        headers={"user-agent": "HookFlow-Test"},
        status="processing",
    )

    import time
    start = time.time()

    try:
        result = await service._deliver_to_destination(test_webhook, destination)
        elapsed = (time.time() - start) * 1000

        return {
            "success": True,
            "response_time_ms": int(elapsed),
            "status_code": result.get("status_code"),
        }
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return {
            "success": False,
            "response_time_ms": int(elapsed),
            "error": str(e),
        }
```

- [ ] **Step 2: Commit**

```bash
git add backend/hookflow/api/webhooks.py
git commit -m "feat: add test destination endpoint"
```

---

## Chunk 3: Frontend Foundation

### Task 7: Install frontend dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install recharts and additional dependencies**

```bash
cd frontend
npm install recharts
```

- [ ] **Step 2: Create API client utilities**

```typescript
// frontend/src/lib/api-clients.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface Webhook {
  id: string;
  app_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  body?: Record<string, unknown>;
  headers?: Record<string, string>;
}

export interface Delivery {
  id: string;
  webhook_id: string;
  destination_id: string;
  attempt_number: number;
  status: string;
  response_status_code?: number;
  error_message?: string;
  response_time_ms?: number;
  created_at: string;
}

export interface Analytics {
  total_webhooks: number;
  success_rate: number;
  avg_response_time_ms: number;
  webhooks_by_status: Record<string, number>;
  webhooks_over_time: Array<{ timestamp: string; count: number }>;
  top_destinations: Array<{ name: string; count: number; success_rate: number }>;
}

export interface Destination {
  id: string;
  app_id: string;
  name: string;
  type: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  last_used_at?: string;
  expires_at?: string;
  created_at: string;
}

// API Client functions
async function apiRequest(path: string, options?: RequestInit) {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "API request failed");
  }

  return response.json();
}

export const api = {
  // Apps
  getApps: () => apiRequest("/apps"),
  getApp: (id: string) => apiRequest(`/apps/${id}`),
  createApp: (data: { name: string; description?: string }) =>
    apiRequest("/apps", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Analytics
  getAnalytics: (appId: string, period: string = "24h") =>
    apiRequest(`/apps/${appId}/analytics?period=${period}`),

  // Webhooks
  getWebhooks: (appId: string, limit = 50, offset = 0) =>
    apiRequest(`/webhooks/${appId}?limit=${limit}&offset=${offset}`),
  getWebhook: (webhookId: string) =>
    apiRequest(`/webhooks/detail/${webhookId}`),
  replayWebhook: (webhookId: string, destinationIds?: string[]) =>
    apiRequest(`/webhooks/${webhookId}/replay`, {
      method: "POST",
      body: JSON.stringify({ destination_ids: destinationIds }),
    }),

  // Destinations
  getDestinations: (appId: string) =>
    apiRequest(`/apps/${appId}/destinations`),
  createDestination: (appId: string, data: unknown) =>
    apiRequest(`/apps/${appId}/destinations`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  testDestination: (appId: string, destinationId: string, payload?: unknown) =>
    apiRequest(`/apps/${appId}/destinations/${destinationId}/test`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteDestination: (appId: string, destinationId: string) =>
    apiRequest(`/apps/${appId}/destinations/${destinationId}`, {
      method: "DELETE",
    }),

  // API Keys
  getApiKeys: (appId: string) =>
    apiRequest(`/apps/${appId}/api-keys`),
  createApiKey: (appId: string, data: { name: string; scopes?: string[]; expires_at?: string }) =>
    apiRequest(`/apps/${appId}/api-keys`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  revokeApiKey: (appId: string, keyId: string) =>
    apiRequest(`/apps/${appId}/api-keys/${keyId}`, {
      method: "DELETE",
    }),
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/src/lib/api-clients.ts
git commit -m "feat: add frontend dependencies and API client"
```

### Task 8: Create reusable UI components

**Files:**
- Create: `frontend/src/components/ui/status-badge.tsx`
- Create: `frontend/src/components/ui/json-viewer.tsx`

- [ ] **Step 1: Create status badge component**

```typescript
// frontend/src/components/ui/status-badge.tsx
interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    processing: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
    success: "bg-green-100 text-green-800",
    retrying: "bg-orange-100 text-orange-800",
  };

  const defaultColor = "bg-gray-100 text-gray-800";

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        colors[status] || defaultColor
      }`}
    >
      {status}
    </span>
  );
}
```

- [ ] **Step 2: Create JSON viewer component**

```typescript
// frontend/src/components/ui/json-viewer.tsx
"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";

interface JsonViewerProps {
  data: unknown;
  initialExpand?: boolean;
}

function JsonNode({ data, level = 0 }: { data: unknown; level?: number }) {
  const [expanded, setExpanded] = useState(level < 2);

  if (data === null) {
    return <span className="text-gray-500">null</span>;
  }

  if (data === undefined) {
    return <span className="text-gray-500">undefined</span>;
  }

  if (typeof data === "boolean" || typeof data === "number") {
    return <span className="text-blue-600">{String(data)}</span>;
  }

  if (typeof data === "string") {
    return <span className="text-green-600">"{data}"</span>;
  }

  if (Array.isArray(data)) {
    if (data.length === 0) return <span>[]</span>;

    return (
      <div className="ml-4">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-gray-400 hover:text-gray-600 mr-1"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <span className="text-gray-500">[</span>
        {expanded && (
          <div className="ml-4">
            {data.map((item, i) => (
              <div key={i} className="border-l border-gray-200 pl-2">
                <JsonNode data={item} level={level + 1} />
                {i < data.length - 1 && <span className="text-gray-500">,</span>}
              </div>
            ))}
          </div>
        )}
        <span className="text-gray-500">]</span>
      </div>
    );
  }

  if (typeof data === "object") {
    const entries = Object.entries(data as Record<string, unknown>);
    if (entries.length === 0) return <span>{"{}"}</span>;

    return (
      <div className="ml-4">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-gray-400 hover:text-gray-600 mr-1"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <span className="text-gray-500">{"{"}</span>
        {expanded && (
          <div className="ml-4">
            {entries.map(([key, value], i) => (
              <div key={key} className="border-l border-gray-200 pl-2">
                <span className="text-purple-600">"{key}"</span>
                <span className="text-gray-500">: </span>
                <JsonNode data={value} level={level + 1} />
                {i < entries.length - 1 && <span className="text-gray-500">,</span>}
              </div>
            ))}
          </div>
        )}
        <span className="text-gray-500">{"}"}</span>
      </div>
    );
  }
}

export function JsonViewer({ data, initialExpand = false }: JsonViewerProps) {
  return (
    <div className="font-mono text-sm bg-gray-50 p-3 rounded-lg overflow-auto max-h-96">
      <JsonNode data={data} />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/status-badge.tsx frontend/src/components/ui/json-viewer.tsx
git commit -m "feat: add reusable UI components (status badge, JSON viewer)"
```

### Task 9: Create chart components

**Files:**
- Create: `frontend/src/components/charts/webhook-chart.tsx`
- Create: `frontend/src/components/charts/status-donut.tsx`

- [ ] **Step 1: Create webhook chart component**

```typescript
// frontend/src/components/charts/webhook-chart.tsx
"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface WebhookChartProps {
  data: Array<{ timestamp: string; count: number }>;
}

export function WebhookChart({ data }: WebhookChartProps) {
  // Format timestamp for display
  const formattedData = data.map((d) => ({
    ...d,
    time: new Date(d.timestamp).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={formattedData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 12 }}
          stroke="#64748b"
        />
        <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1e293b",
            border: "none",
            borderRadius: "8px",
            color: "#fff",
          }}
        />
        <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: Create status donut chart**

```typescript
// frontend/src/components/charts/status-donut.tsx
"use client";

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";

interface StatusDonutProps {
  data: Record<string, number>;
}

const COLORS: Record<string, string> = {
  completed: "#22c55e",
  success: "#22c55e",
  pending: "#eab308",
  processing: "#3b82f6",
  failed: "#ef4444",
};

const STATUS_LABELS: Record<string, string> = {
  completed: "Completed",
  success: "Success",
  pending: "Pending",
  processing: "Processing",
  failed: "Failed",
};

export function StatusDonut({ data }: StatusDonutProps) {
  const chartData = Object.entries(data)
    .filter(([_, count]) => count > 0)
    .map(([status, count]) => ({
      name: STATUS_LABELS[status] || status,
      value: count,
      color: COLORS[status] || "#64748b",
    }));

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400">
        No data
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={2}
          dataKey="value"
        >
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: "#1e293b",
            border: "none",
            borderRadius: "8px",
            color: "#fff",
          }}
        />
        <Legend
          verticalAlign="bottom"
          height={36}
          iconType="circle"
          formatter={(value) => <span className="text-gray-600">{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/charts/
git commit -m "feat: add chart components (webhook chart, status donut)"
```

---

## Chunk 4: Dashboard Pages

### Task 10: Dashboard overview page

**Files:**
- Create: `frontend/src/app/dashboard/page.tsx`
- Create: `frontend/src/components/dashboard/stat-card.tsx`

- [ ] **Step 1: Create stat card component**

```typescript
// frontend/src/components/dashboard/stat-card.tsx
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  change?: string;
  changePositive?: boolean;
}

export function StatCard({
  icon: Icon,
  label,
  value,
  change,
  changePositive,
}: StatCardProps) {
  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-slate-100 rounded-lg">
          <Icon className="w-5 h-5 text-slate-700" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-slate-500">{label}</p>
          <p className="text-2xl font-semibold text-slate-900">{value}</p>
        </div>
        {change && (
          <span
            className={`text-sm ${
              changePositive ? "text-green-600" : "text-red-600"
            }`}
          >
            {change}
          </span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create dashboard page**

```typescript
// frontend/src/app/dashboard/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Webhook, Activity, Target, TrendingUp } from "lucide-react";
import { api, type Analytics } from "@/lib/api-clients";
import { StatCard } from "@/components/dashboard/stat-card";
import { WebhookChart } from "@/components/charts/webhook-chart";
import { StatusDonut } from "@/components/charts/status-donut";

export default function DashboardPage() {
  const params = useParams();
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

  // For now, just show the first app's analytics
  // In Phase 5, this will be the user's apps
  useEffect(() => {
    async function loadAnalytics() {
      try {
        const apps = await api.getApps();
        if (apps.length > 0) {
          const appId = (apps[0] as { id: string }).id;
          const data = await api.getAnalytics(appId, "7d");
          setAnalytics(data);
        }
      } catch (error) {
        console.error("Failed to load analytics:", error);
      } finally {
        setLoading(false);
      }
    }

    loadAnalytics();
  }, []);

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  if (!analytics) {
    return (
      <div className="p-8">
        <p className="text-gray-500">No apps found. Create an app to get started.</p>
      </div>
    );
  }

  const successRate = analytics.success_rate.toFixed(1);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
          <h1 className="text-xl font-semibold">Dashboard</h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={Webhook}
            label="Webhooks (7d)"
            value={analytics.total_webhooks.toLocaleString()}
          />
          <StatCard
            icon={Activity}
            label="Success Rate"
            value={`${successRate}%`}
            changePositive={analytics.success_rate >= 90}
          />
          <StatCard
            icon={Target}
            label="Avg Response Time"
            value={`${Math.round(analytics.avg_response_time_ms)}ms`}
          />
          <StatCard
            icon={TrendingUp}
            label="Active Destinations"
            value={analytics.top_destinations.length}
          />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <div className="bg-white rounded-lg border p-6">
            <h2 className="text-lg font-semibold mb-4">Webhooks Over Time</h2>
            <WebhookChart data={analytics.webhooks_over_time} />
          </div>
          <div className="bg-white rounded-lg border p-6">
            <h2 className="text-lg font-semibold mb-4">Delivery Status</h2>
            <StatusDonut data={analytics.webhooks_by_status} />
          </div>
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/dashboard/page.tsx frontend/src/components/dashboard/stat-card.tsx
git commit -m "feat: add dashboard overview page"
```

### Task 11: App detail and webhook list

**Files:**
- Create: `frontend/src/app/dashboard/app/[id]/page.tsx`
- Create: `frontend/src/app/dashboard/app/[id]/webhooks/page.tsx`
- Create: `frontend/src/components/dashboard/webhook-table.tsx`

- [ ] **Step 1: Create webhook table component**

```typescript
// frontend/src/components/dashboard/webhook-table.tsx
"use client";

import { StatusBadge } from "@/components/ui/status-badge";
import { type Webhook } from "@/lib/api-clients";
import { useRouter } from "next/navigation";

interface WebhookTableProps {
  webhooks: Webhook[];
  loading?: boolean;
}

export function WebhookTable({ webhooks, loading }: WebhookTableProps) {
  const router = useRouter();

  if (loading) {
    return <div className="p-4">Loading webhooks...</div>;
  }

  if (webhooks.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No webhooks received yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Timestamp</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Status</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Source</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Summary</th>
          </tr>
        </thead>
        <tbody>
          {webhooks.map((webhook) => (
            <tr
              key={webhook.id}
              onClick={() => router.push(`/dashboard/app/${webhook.app_id}/webhooks/${webhook.id}`)}
              className="border-b hover:bg-gray-50 cursor-pointer"
            >
              <td className="px-4 py-3 text-sm">
                {new Date(webhook.created_at).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-sm">
                <StatusBadge status={webhook.status} />
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {webhook.headers?.["x-forwarded-for"] || webhook.headers?.["user-agent"]?.substring(0, 30) || "-"}
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {webhook.body ? JSON.stringify(webhook.body).substring(0, 50) + "..." : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Create app detail page**

```typescript
// frontend/src/app/dashboard/app/[id]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Copy, Plus } from "lucide-react";
import { api, type App, type Analytics, type Webhook } from "@/lib/api-clients";
import { StatCard } from "@/components/dashboard/stat-card";
import { WebhookTable } from "@/components/dashboard/webhook-table";
import { Webhook, Activity } from "lucide-react";

export default function AppDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [app, setApp] = useState<App | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);

  const appId = params.id as string;

  useEffect(() => {
    async function loadData() {
      try {
        const [appData, analyticsData, webhooksData] = await Promise.all([
          api.getApp(appId),
          api.getAnalytics(appId, "24h"),
          api.getWebhooks(appId, 10),
        ]);
        setApp(appData);
        setAnalytics(analyticsData);
        setWebhooks(webhooksData);
      } catch (error) {
        console.error("Failed to load app data:", error);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [appId]);

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  if (!app) {
    return <div className="p-8">App not found</div>;
  }

  const webhookUrl = `${window.location.origin}/api/v1/webhook/${appId}`;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <h1 className="text-xl font-semibold">{app.name}</h1>
          <div className="flex gap-2">
            <button
              onClick={() => router.push(`/dashboard/app/${appId}/destinations`)}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 flex items-center gap-1"
            >
              <Plus className="w-4 h-4" />
              Add Destination
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* App Info */}
        <div className="bg-white rounded-lg border p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Webhook URL</h2>
          <div className="flex items-center gap-2 p-3 bg-slate-100 rounded-lg">
            <code className="flex-1 text-sm font-mono">{webhookUrl}</code>
            <button
              onClick={() => navigator.clipboard.writeText(webhookUrl)}
              className="p-2 hover:bg-slate-200 rounded"
            >
              <Copy className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Stats */}
        {analytics && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <StatCard icon={Webhook} label="Total Webhooks" value={analytics.total_webhooks} />
            <StatCard icon={Activity} label="Success Rate" value={`${analytics.success_rate.toFixed(1)}%`} />
            <StatCard icon={Activity} label="Avg Response" value={`${Math.round(analytics.avg_response_time_ms)}ms`} />
          </div>
        )}

        {/* Recent Webhooks */}
        <div className="bg-white rounded-lg border">
          <div className="px-6 py-4 border-b flex justify-between items-center">
            <h2 className="text-lg font-semibold">Recent Webhooks</h2>
            <button
              onClick={() => router.push(`/dashboard/app/${appId}/webhooks`)}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              View All
            </button>
          </div>
          <WebhookTable webhooks={webhooks} />
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Create webhooks list page**

```typescript
// frontend/src/app/dashboard/app/[id]/webhooks/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type Webhook } from "@/lib/api-clients";
import { WebhookTable } from "@/components/dashboard/webhook-table";

export default function WebhooksPage() {
  const params = useParams();
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);

  const appId = params.id as string;
  const limit = 50;

  useEffect(() => {
    async function loadWebhooks() {
      try {
        setLoading(true);
        const data = await api.getWebhooks(appId, limit, page * limit);
        setWebhooks(data);
      } catch (error) {
        console.error("Failed to load webhooks:", error);
      } finally {
        setLoading(false);
      }
    }

    loadWebhooks();
  }, [appId, page]);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
          <h1 className="text-xl font-semibold">Webhooks</h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg border">
          <WebhookTable webhooks={webhooks} loading={loading} />

          {/* Pagination */}
          <div className="px-6 py-4 border-t flex justify-between items-center">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-4 py-2 text-sm border rounded-lg disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-gray-600">Page {page + 1}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={webhooks.length < limit}
              className="px-4 py-2 text-sm border rounded-lg disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/dashboard/app/ frontend/src/components/dashboard/webhook-table.tsx
git commit -m "feat: add app detail and webhooks list pages"
```

### Task 12: Webhook detail page

**Files:**
- Create: `frontend/src/app/dashboard/app/[id]/webhooks/[webhookId]/page.tsx`
- Create: `frontend/src/components/dashboard/webhook-detail.tsx`
- Create: `frontend/src/components/dashboard/delivery-timeline.tsx`

- [ ] **Step 1: Create delivery timeline component**

```typescript
// frontend/src/components/dashboard/delivery-timeline.tsx
import { CheckCircle, XCircle, Clock } from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";

interface Delivery {
  id: string;
  destination_id: string;
  attempt_number: number;
  status: string;
  response_status_code?: number;
  error_message?: string;
  response_time_ms?: number;
  created_at: string;
}

interface DeliveryTimelineProps {
  deliveries: Delivery[];
}

export function DeliveryTimeline({ deliveries }: DeliveryTimelineProps) {
  if (deliveries.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No delivery attempts yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {deliveries.map((delivery, index) => {
        const isSuccess = delivery.status === "success";
        const isFailed = delivery.status === "failed";
        const isPending = delivery.status === "pending" || delivery.status === "retrying";

        return (
          <div key={delivery.id} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                isSuccess ? "bg-green-100" : isFailed ? "bg-red-100" : "bg-gray-100"
              }`}>
                {isSuccess && <CheckCircle className="w-4 h-4 text-green-600" />}
                {isFailed && <XCircle className="w-4 h-4 text-red-600" />}
                {isPending && <Clock className="w-4 h-4 text-gray-400" />}
              </div>
              {index < deliveries.length - 1 && (
                <div className="w-0.5 flex-1 bg-gray-200 my-1" />
              )}
            </div>

            <div className="flex-1 pb-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-medium">Attempt {delivery.attempt_number}</span>
                <StatusBadge status={delivery.status} />
              </div>

              {delivery.response_status_code && (
                <p className="text-sm text-gray-600">
                  Status: {delivery.response_status_code}
                </p>
              )}

              {delivery.response_time_ms && (
                <p className="text-sm text-gray-600">
                  Response time: {delivery.response_time_ms}ms
                </p>
              )}

              {delivery.error_message && (
                <p className="text-sm text-red-600 mt-1">
                  Error: {delivery.error_message}
                </p>
              )}

              <p className="text-xs text-gray-400 mt-1">
                {new Date(delivery.created_at).toLocaleString()}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Create webhook detail component**

```typescript
// frontend/src/components/dashboard/webhook-detail.tsx
import { type Webhook, type Delivery } from "@/lib/api-clients";
import { JsonViewer } from "@/components/ui/json-viewer";

interface WebhookDetailProps {
  webhook: Webhook;
  deliveries: Delivery[];
  onReplay: (destinationIds?: string[]) => void;
}

export function WebhookDetail({ webhook, deliveries, onReplay }: WebhookDetailProps) {
  return (
    <div className="space-y-6">
      {/* Headers */}
      <div className="bg-white rounded-lg border p-6">
        <h3 className="text-lg font-semibold mb-4">Request Headers</h3>
        <JsonViewer data={webhook.headers || {}} />
      </div>

      {/* Body */}
      <div className="bg-white rounded-lg border p-6">
        <h3 className="text-lg font-semibold mb-4">Request Body</h3>
        <JsonViewer data={webhook.body || {}} />
      </div>

      {/* Deliveries */}
      <div className="bg-white rounded-lg border p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold">Delivery Attempts</h3>
          <button
            onClick={() => onReplay()}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Replay Webhook
          </button>
        </div>
        <DeliveryTimeline deliveries={deliveries} />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create webhook detail page**

```typescript
// frontend/src/app/dashboard/app/[id]/webhooks/[webhookId]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type Webhook, type Delivery } from "@/lib/api-clients";
import { WebhookDetail } from "@/components/dashboard/webhook-detail";
import { StatusBadge } from "@/components/ui/status-badge";

export default function WebhookDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [webhook, setWebhook] = useState<Webhook | null>(null);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [replaying, setReplaying] = useState(false);

  const webhookId = params.webhookId as string;
  const appId = params.id as string;

  useEffect(() => {
    async function loadWebhook() {
      try {
        const data = await api.getWebhook(webhookId);
        setWebhook(data);
        setDeliveries(data.deliveries || []);
      } catch (error) {
        console.error("Failed to load webhook:", error);
      } finally {
        setLoading(false);
      }
    }

    loadWebhook();
  }, [webhookId]);

  const handleReplay = async (destinationIds?: string[]) => {
    try {
      setReplaying(true);
      await api.replayWebhook(webhookId, destinationIds);
      // Reload webhook after replay
      const data = await api.getWebhook(webhookId);
      setWebhook(data);
      setDeliveries(data.deliveries || []);
    } catch (error) {
      console.error("Failed to replay webhook:", error);
      alert("Failed to replay webhook");
    } finally {
      setReplaying(false);
    }
  };

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  if (!webhook) {
    return <div className="p-8">Webhook not found</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <button
            onClick={() => router.push(`/dashboard/app/${appId}/webhooks`)}
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            ← Back to Webhooks
          </button>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">Status:</span>
            <StatusBadge status={webhook.status} />
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Webhook Details</h1>
          <p className="text-sm text-gray-500 mt-1">
            ID: {webhookId} • Received: {new Date(webhook.created_at).toLocaleString()}
          </p>
        </div>

        <WebhookDetail
          webhook={webhook}
          deliveries={deliveries}
          onReplay={handleReplay}
        />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/dashboard/app/[id]/webhooks/[webhookId]/ frontend/src/components/dashboard/webhook-detail.tsx frontend/src/components/dashboard/delivery-timeline.tsx
git commit -m "feat: add webhook detail page with delivery timeline"
```

---

## Chunk 5: Remaining Dashboard Pages

### Task 13: Destinations management page

**Files:**
- Create: `frontend/src/app/dashboard/app/[id]/destinations/page.tsx`
- Create: `frontend/src/components/dashboard/destination-list.tsx`
- Create: `frontend/src/components/dashboard/destination-form.tsx`

- [ ] **Step 1: Create destination form component**

```typescript
// frontend/src/components/dashboard/destination-form.tsx
"use client";

import { useState } from "react";
import { X } from "lucide-react";

interface DestinationFormProps {
  appId: string;
  onSuccess: () => void;
  onCancel: () => void;
}

export function DestinationForm({ appId, onSuccess, onCancel }: DestinationFormProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState("http");
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      await api.createDestination(appId, {
        name,
        type,
        config,
      });
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create destination");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">Add Destination</h2>
          <button onClick={onCancel} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg"
            >
              <option value="http">HTTP</option>
              <option value="slack">Slack</option>
              <option value="discord">Discord</option>
              <option value="telegram">Telegram</option>
              <option value="database">Database</option>
              <option value="email">Email</option>
            </select>
          </div>

          {type === "http" && (
            <div>
              <label className="block text-sm font-medium mb-1">URL</label>
              <input
                type="url"
                value={(config.url as string) || ""}
                onChange={(e) => setConfig({ ...config, url: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg"
                placeholder="https://example.com/webhook"
                required
              />
            </div>
          )}

          {type === "slack" && (
            <div>
              <label className="block text-sm font-medium mb-1">Webhook URL</label>
              <input
                type="url"
                value={(config.webhook_url as string) || ""}
                onChange={(e) => setConfig({ ...config, webhook_url: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg"
                placeholder="https://hooks.slack.com/services/..."
                required
              />
            </div>
          )}

          {type === "discord" && (
            <div>
              <label className="block text-sm font-medium mb-1">Webhook URL</label>
              <input
                type="url"
                value={(config.webhook_url as string) || ""}
                onChange={(e) => setConfig({ ...config, webhook_url: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg"
                placeholder="https://discord.com/api/webhooks/..."
                required
              />
            </div>
          )}

          {type === "telegram" && (
            <>
              <div>
                <label className="block text-sm font-medium mb-1">Bot Token</label>
                <input
                  type="text"
                  value={(config.bot_token as string) || ""}
                  onChange={(e) => setConfig({ ...config, bot_token: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                  placeholder="123456:ABC-DEF..."
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Chat ID</label>
                <input
                  type="text"
                  value={(config.chat_id as string) || ""}
                  onChange={(e) => setConfig({ ...config, chat_id: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                  placeholder="-100..."
                  required
                />
              </div>
            </>
          )}

          {type === "database" && (
            <div>
              <label className="block text-sm font-medium mb-1">Table Name (optional)</label>
              <input
                type="text"
                value={(config.table_name as string) || ""}
                onChange={(e) => setConfig({ ...config, table_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg"
                placeholder="Auto-generated if empty"
              />
            </div>
          )}

          {type === "email" && (
            <>
              <div>
                <label className="block text-sm font-medium mb-1">To (comma-separated)</label>
                <input
                  type="text"
                  value={(config.to as string[])?.join(", ") || ""}
                  onChange={(e) => setConfig({ ...config, to: e.target.value.split(",") })}
                  className="w-full px-3 py-2 border rounded-lg"
                  placeholder="user1@example.com, user2@example.com"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Subject (optional)</label>
                <input
                  type="text"
                  value={(config.subject as string) || ""}
                  onChange={(e) => setConfig({ ...config, subject: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                  placeholder="New webhook received"
                />
              </div>
            </>
          )}

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {error}
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create destination list component**

```typescript
// frontend/src/components/dashboard/destination-list.tsx
import { Trash2, TestTube } from "lucide-react";
import { type Destination } from "@/lib/api-clients";
import { StatusBadge } from "@/components/ui/status-badge";

interface DestinationListProps {
  destinations: Destination[];
  onDelete: (id: string) => void;
  onTest: (id: string) => void;
}

export function DestinationList({ destinations, onDelete, onTest }: DestinationListProps) {
  if (destinations.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No destinations configured. Add one to start receiving webhooks.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {destinations.map((dest) => (
        <div key={dest.id} className="flex items-center justify-between p-4 border rounded-lg">
          <div>
            <h3 className="font-medium">{dest.name}</h3>
            <p className="text-sm text-gray-500 capitalize">{dest.type}</p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={dest.is_active ? "active" : "inactive"} />
            <button
              onClick={() => onTest(dest.id)}
              className="p-2 hover:bg-gray-100 rounded"
              title="Test destination"
            >
              <TestTube className="w-4 h-4" />
            </button>
            <button
              onClick={() => onDelete(dest.id)}
              className="p-2 hover:bg-red-50 text-red-600 rounded"
              title="Delete destination"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create destinations page**

```typescript
// frontend/src/app/dashboard/app/[id]/destinations/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { api, type Destination } from "@/lib/api-clients";
import { DestinationList } from "@/components/dashboard/destination-list";
import { DestinationForm } from "@/components/dashboard/destination-form";

export default function DestinationsPage() {
  const params = useParams();
  const router = useRouter();
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  const appId = params.id as string;

  useEffect(() => {
    async function loadDestinations() {
      try {
        const data = await api.getDestinations(appId);
        setDestinations(data);
      } catch (error) {
        console.error("Failed to load destinations:", error);
      } finally {
        setLoading(false);
      }
    }

    loadDestinations();
  }, [appId]);

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this destination?")) {
      return;
    }

    try {
      await api.deleteDestination(appId, id);
      setDestinations(destinations.filter((d) => d.id !== id));
    } catch (error) {
      console.error("Failed to delete destination:", error);
      alert("Failed to delete destination");
    }
  };

  const handleTest = async (id: string) => {
    try {
      const result = await api.testDestination(appId, id);
      if (result.success) {
        alert(`Test successful! Response time: ${result.response_time_ms}ms`);
      } else {
        alert(`Test failed: ${result.error || "Unknown error"}`);
      }
    } catch (error) {
      console.error("Failed to test destination:", error);
      alert("Failed to test destination");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <h1 className="text-xl font-semibold">Destinations</h1>
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Destination
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg border p-6">
          <DestinationList
            destinations={destinations}
            onDelete={handleDelete}
            onTest={handleTest}
          />
        </div>
      </main>

      {showForm && (
        <DestinationForm
          appId={appId}
          onSuccess={() => {
            setShowForm(false);
            // Reload destinations
            api.getDestinations(appId).then(setDestinations);
          }}
          onCancel={() => setShowForm(false)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/dashboard/app/[id]/destinations/ frontend/src/components/dashboard/destination-list.tsx frontend/src/components/dashboard/destination-form.tsx
git commit -m "feat: add destinations management page"
```

### Task 14: Settings and API keys page

**Files:**
- Create: `frontend/src/app/dashboard/app/[id]/settings/page.tsx`
- Create: `frontend/src/components/dashboard/api-key-list.tsx`

- [ ] **Step 1: Create API key list component**

```typescript
// frontend/src/components/dashboard/api-key-list.tsx
"use client";

import { useState } from "react";
import { Plus, Trash2, Copy, Eye, EyeOff } from "lucide-react";
import { api, type ApiKey } from "@/lib/api-clients";

interface ApiKeyListProps {
  appId: string;
  apiKeys: ApiKey[];
  onRefresh: () => void;
}

export function ApiKeyList({ appId, apiKeys, onRefresh }: ApiKeyListProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [newKey, setNewKey] = useState<ApiKey | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    setLoading(true);
    try {
      const created = await api.createApiKey(appId, { name });
      setNewKey(created);
      setShowKey(true);
      onRefresh();
      setName("");
      setShowCreate(false);
    } catch (error) {
      console.error("Failed to create API key:", error);
      alert("Failed to create API key");
    } finally {
      setLoading(false);
    }
  };

  const handleRevoke = async (keyId: string) => {
    if (!confirm("Are you sure you want to revoke this API key?")) {
      return;
    }

    try {
      await api.revokeApiKey(appId, keyId);
      onRefresh();
    } catch (error) {
      console.error("Failed to revoke API key:", error);
      alert("Failed to revoke API key");
    }
  };

  return (
    <div className="space-y-4">
      {newKey && showKey && (
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <h3 className="font-semibold text-yellow-900 mb-2">Save Your API Key</h3>
          <p className="text-sm text-yellow-700 mb-3">
            This key will only be shown once. Copy it now!
          </p>
          <div className="flex gap-2">
            <code className="flex-1 px-3 py-2 bg-white rounded text-sm font-mono">
              {newKey.key}
            </code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(newKey.key);
                alert("Copied to clipboard");
              }}
              className="px-3 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700"
            >
              <Copy className="w-4 h-4" />
            </button>
            <button
              onClick={() => {
                setNewKey(null);
                setShowKey(false);
              }}
              className="px-3 py-2 border rounded hover:bg-yellow-100"
            >
              I've Saved It
            </button>
          </div>
        </div>
      )}

      <div className="flex justify-between items-center">
        <h3 className="font-semibold">API Keys</h3>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="text-sm px-3 py-1 border rounded hover:bg-gray-50 flex items-center gap-1"
        >
          <Plus className="w-4 h-4" />
          New Key
        </button>
      </div>

      {showCreate && (
        <div className="p-4 bg-gray-50 rounded-lg space-y-3">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Key name (e.g., 'Production API')"
            className="w-full px-3 py-2 border rounded-lg"
          />
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={!name || loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create"}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 border rounded-lg hover:bg-gray-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {apiKeys.length === 0 ? (
        <p className="text-sm text-gray-500">No API keys yet.</p>
      ) : (
        <div className="space-y-2">
          {apiKeys.map((key) => (
            <div
              key={key.id}
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
            >
              <div>
                <p className="font-medium">{key.name}</p>
                <p className="text-xs text-gray-500 font-mono">{key.key_prefix}***</p>
                <p className="text-xs text-gray-400">
                  Last used: {key.last_used_at
                    ? new Date(key.last_used_at).toLocaleDateString()
                    : "Never"}
                </p>
              </div>
              <button
                onClick={() => handleRevoke(key.id)}
                className="p-2 hover:bg-red-50 text-red-600 rounded"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create settings page**

```typescript
// frontend/src/app/dashboard/app/[id]/settings/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type App, type ApiKey } from "@/lib/api-clients";
import { ApiKeyList } from "@/components/dashboard/api-key-list";

export default function SettingsPage() {
  const params = useParams();
  const [app, setApp] = useState<App | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);

  const appId = params.id as string;

  useEffect(() => {
    async function loadData() {
      try {
        const [appData, keysData] = await Promise.all([
          api.getApp(appId),
          api.getApiKeys(appId),
        ]);
        setApp(appData);
        setApiKeys(keysData);
      } catch (error) {
        console.error("Failed to load settings:", error);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [appId]);

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  if (!app) {
    return <div className="p-8">App not found</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
          <h1 className="text-xl font-semibold">Settings</h1>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* App Info */}
        <div className="bg-white rounded-lg border p-6">
          <h2 className="text-lg font-semibold mb-4">App Information</h2>
          <div className="space-y-3">
            <div>
              <label className="text-sm text-gray-500">App Name</label>
              <p className="font-medium">{app.name}</p>
            </div>
            <div>
              <label className="text-sm text-gray-500">Description</label>
              <p className="text-sm">{app.description || "No description"}</p>
            </div>
            <div>
              <label className="text-sm text-gray-500">App ID</label>
              <p className="text-sm font-mono">{app.id}</p>
            </div>
          </div>
        </div>

        {/* Signature Verification */}
        <div className="bg-white rounded-lg border p-6">
          <h2 className="text-lg font-semibold mb-4">Security</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Signature Verification</p>
              <p className="text-sm text-gray-500">
                Verify HMAC signatures on incoming webhooks
              </p>
            </div>
            <span className={`px-2 py-1 text-xs rounded ${
              app.verify_signature ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-800"
            }`}>
              {app.verify_signature ? "Enabled" : "Disabled"}
            </span>
          </div>
        </div>

        {/* API Keys */}
        <div className="bg-white rounded-lg border p-6">
          <ApiKeyList
            appId={appId}
            apiKeys={apiKeys}
            onRefresh={() => api.getApiKeys(appId).then(setApiKeys)}
          />
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/dashboard/app/[id]/settings/ frontend/src/components/dashboard/api-key-list.tsx
git commit -m "feat: add settings page with API key management"
```

---

## Chunk 6: Testing & Completion

### Task 15: Write tests for new backend services

**Files:**
- Create: `backend/tests/test_analytics.py`
- Create: `backend/tests/test_api_key.py`

- [ ] **Step 1: Write analytics service tests**

```python
# backend/tests/test_analytics.py
"""Tests for analytics service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.models import App, Webhook, Delivery, Destination
from hookflow.services.analytics import AnalyticsService


@pytest.mark.asyncio
async def test_get_analytics_empty(db: AsyncSession, test_app: App):
    """Test analytics with no webhooks."""
    service = AnalyticsService(db)
    analytics = await service.get_analytics(test_app.id, "24h")

    assert analytics.total_webhooks == 0
    assert analytics.success_rate == 0
    assert analytics.avg_response_time_ms == 0
    assert analytics.webhooks_by_status == {}
    assert analytics.webhooks_over_time == []


@pytest.mark.asyncio
async def test_get_analytics_with_data(
    db: AsyncSession,
    test_app: App,
    test_webhook: Webhook,
    test_destination: Destination,
    test_delivery: Delivery,
):
    """Test analytics with existing data."""
    service = AnalyticsService(db)
    analytics = await service.get_analytics(test_app.id, "24h")

    assert analytics.total_webhooks >= 1
    assert 0 <= analytics.success_rate <= 100
```

- [ ] **Step 2: Write API key service tests**

```python
# backend/tests/test_api_key.py
"""Tests for API key service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.models import App
from hookflow.services.api_key import ApiKeyService


@pytest.mark.asyncio
async def test_create_api_key(db: AsyncSession, test_app: App):
    """Test creating an API key."""
    service = ApiKeyService(db)
    api_key, plain_key = await service.create_api_key(
        app_id=test_app.id,
        name="Test Key",
        scopes=["read", "write"],
    )

    assert api_key.name == "Test Key"
    assert api_key.app_id == test_app.id
    assert api_key.key_prefix == plain_key[:10]
    assert plain_key.startswith("hf_")
    assert len(plain_key) > 40


@pytest.mark.asyncio
async def test_list_api_keys(db: AsyncSession, test_app: App):
    """Test listing API keys."""
    service = ApiKeyService(db)

    # Create a key
    await service.create_api_key(test_app.id, "Test Key")

    # List keys
    keys = await service.list_api_keys(test_app.id)

    assert len(keys) >= 1
    assert any(k.name == "Test Key" for k in keys)


@pytest.mark.asyncio
async def test_validate_api_key(db: AsyncSession, test_app: App):
    """Test API key validation."""
    service = ApiKeyService(db)

    # Create a key
    _, plain_key = await service.create_api_key(test_app.id, "Test Key")

    # Validate correct key
    validated = await service.validate_api_key(plain_key)
    assert validated is not None
    assert validated.name == "Test Key"

    # Validate incorrect key
    validated = await service.validate_api_key("invalid_key")
    assert validated is None


@pytest.mark.asyncio
async def test_revoke_api_key(db: AsyncSession, test_app: App):
    """Test revoking an API key."""
    service = ApiKeyService(db)

    # Create a key
    api_key, _ = await service.create_api_key(test_app.id, "Test Key")

    # Revoke it
    success = await service.revoke_api_key(api_key.id, test_app.id)
    assert success is True

    # Key should no longer be active
    validated = await service.validate_api_key("hf_anything")
    assert validated is None or validated.id != api_key.id
```

- [ ] **Step 3: Run tests**

```bash
cd backend
pytest tests/test_analytics.py tests/test_api_key.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: add tests for analytics and API key services"
```

### Task 16: E2E testing with Playwright

**Files:**
- Create: `frontend/tests/e2e/dashboard.spec.ts`

- [ ] **Step 1: Install Playwright**

```bash
cd frontend
npm install -D @playwright/test
npx playwright install
```

- [ ] **Step 2: Write E2E test**

```typescript
// frontend/tests/e2e/dashboard.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    // TODO: Set up test database with seed data
    await page.goto("http://localhost:3000/dashboard");
  });

  test("shows overview stats", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Dashboard");

    // Should show stat cards
    await expect(page.locator("text=Webhooks")).toBeVisible();
    await expect(page.locator("text=Success Rate")).toBeVisible();
  });

  test("navigates to app detail", async ({ page }) => {
    // Click on first app card if exists
    const appCard = page.locator(".bg-white.rounded-lg.border").first();
    if (await appCard.isVisible()) {
      await appCard.click();
      await expect(page).toHaveURL(/\/dashboard\/app\/\w+/);
    }
  });
});

test.describe("Webhooks", () => {
  test("displays webhook list", async ({ page }) => {
    await page.goto("http://localhost:3000/dashboard/app/test-app/webhooks");

    await expect(page.locator("h1")).toContainText("Webhooks");
  });

  test("shows webhook detail", async ({ page }) => {
    // Navigate to webhook detail
    await page.goto("http://localhost:3000/dashboard/app/test-app/webhooks");

    // Click first webhook row
    const firstRow = page.locator("table tbody tr").first();
    if (await firstRow.isVisible()) {
      await firstRow.click();
      await expect(page).toHaveURL(/\/webhooks\/\w+/);
    }
  });
});
```

- [ ] **Step 3: Add test script to package.json**

```json
{
  "scripts": {
    "test:e2e": "playwright test"
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/ frontend/package.json frontend/playwright.config.ts
git commit -m "test: add E2E tests with Playwright"
```

### Task 17: Final verification

- [ ] **Step 1: Run all tests**

```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend type check
cd ../frontend
npm run tsc -- --noEmit

# E2E tests (optional - requires running services)
# npm run test:e2e
```

- [ ] **Step 2: Start services locally**

```bash
# Terminal 1: Backend
cd backend
uvicorn hookflow.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

- [ ] **Step 3: Manual verification checklist**

- [ ] Dashboard loads at http://localhost:3000/dashboard
- [ ] Analytics charts display data
- [ ] App detail page shows webhook URL
- [ ] Webhooks list paginates correctly
- [ ] Webhook detail shows delivery timeline
- [ ] Replay button triggers redelivery
- [ ] Destination form submits successfully
- [ ] Test destination button works
- [ ] API key creates and displays full key once
- [ ] API key revoke works
- [ ] SSE events stream on webhook receive

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: complete Phase 2 dashboard and core features

Phase 2 implementation complete:
- Analytics service with time-series aggregation
- API key management (create, list, revoke)
- SSE event broadcaster for real-time updates
- Dashboard overview with stats and charts
- App detail and webhooks list pages
- Webhook detail with delivery timeline
- Destinations management with test endpoint
- Settings page with API key UI
- Unit tests for new services
- E2E tests with Playwright

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 2 Success Criteria Verification

- [ ] User can view all webhooks with pagination
- [ ] User can see delivery status for each webhook
- [ ] User can replay failed webhooks
- [ ] Real-time delivery updates visible on dashboard
- [ ] API keys can be created/revoked
- [ ] Analytics show delivery rates and trends
- [ ] All new code has 80%+ test coverage

---

## Notes for Implementation

- **Timezone handling:** Always use `datetime.now(timezone.utc)` for new code
- **PostgreSQL required:** Analytics uses `date_trunc()` and JSONB
- **Phase 2 is unauthenticated:** Full auth comes in Phase 5 with Clerk
- **SSE in dev:** Uses in-memory broadcaster, Redis for production
- **Recharts:** Already in frontend dependencies
- **shadcn/ui:** Use existing components where possible
