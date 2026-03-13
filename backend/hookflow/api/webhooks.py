"""Webhook API endpoints."""

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.core.database import get_db
from hookflow.schemas import (
    AppCreate,
    AppListResponse,
    AppResponse,
    BatchWebhookItem,
    BatchWebhookRequest,
    BatchWebhookItemResponse,
    BatchWebhookResponse,
    DestinationCreate,
    DestinationResponse,
    WebhookDetailResponse,
    WebhookReplay,
    WebhookResponse,
)
from hookflow.services import WebhookService, RateLimitService
from hookflow.services.templates import TemplateProvider, WebhookTemplates

router = APIRouter(
    tags=["webhooks"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing API key"},
        429: {"description": "Too Many Requests - Rate limit exceeded"},
    },
)


async def get_webhook_service(
    db: AsyncSession = Depends(get_db),
) -> WebhookService:
    """Get webhook service instance."""
    return WebhookService(db)


# ==================== App Management Routes ====================
# These must come first to avoid conflicts with /{app_id}

@router.post(
    "/apps",
    response_model=AppResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new app",
    tags=["apps"],
)
async def create_app(
    app: AppCreate,
    service: WebhookService = Depends(get_webhook_service),
):
    """Create a new webhook app."""

    import secrets

    from hookflow.models import App, User
    from sqlalchemy import select

    # Generate webhook secret
    webhook_secret = secrets.token_urlsafe(32)

    # Get or create default user for demo purposes
    result = await service.db.execute(
        select(User).limit(1)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Create default user
        user = User(
            id=str(uuid.uuid4()),
            email="demo@hookflow.dev",
            name="Demo User",
            password_hash="demo",  # In production, use proper hashing
        )
        service.db.add(user)
        await service.db.commit()

    # Create app
    db_app = App(
        name=app.name,
        description=app.description,
        webhook_secret=webhook_secret,
        user_id=user.id,
    )

    service.db.add(db_app)
    await service.db.commit()
    await service.db.refresh(db_app)

    return AppResponse(
        id=db_app.id,
        name=db_app.name,
        description=db_app.description,
        verify_signature=db_app.verify_signature,
        monthly_limit=db_app.monthly_limit,
        current_month_count=db_app.current_month_count,
        webhook_secret=db_app.webhook_secret,
        is_active=db_app.is_active,
        created_at=db_app.created_at,
        updated_at=db_app.updated_at,
    )


@router.get(
    "/apps",
    response_model=list[AppListResponse],
    summary="List apps",
    tags=["apps"],
)
async def list_apps(
    service: WebhookService = Depends(get_webhook_service),
):
    """List all apps for the authenticated user."""

    # Simplified - in real app, filter by user
    from hookflow.models import App
    from sqlalchemy import select

    result = await service.db.execute(select(App).limit(100))
    apps = list(result.scalars().all())

    return [
        AppListResponse(
            id=app.id,
            name=app.name,
            description=app.description,
            monthly_limit=app.monthly_limit,
            current_month_count=app.current_month_count,
            is_active=app.is_active,
            created_at=app.created_at,
        )
        for app in apps
    ]


@router.get(
    "/apps/{app_id}",
    response_model=AppResponse,
    summary="Get app details",
    tags=["apps"],
)
async def get_app(
    app_id: str,
    service: WebhookService = Depends(get_webhook_service),
):
    """Get app details."""

    app = await service._get_app(app_id)

    if not app:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App not found",
        )

    return AppResponse(
        id=app.id,
        name=app.name,
        description=app.description,
        verify_signature=app.verify_signature,
        monthly_limit=app.monthly_limit,
        current_month_count=app.current_month_count,
        webhook_secret=app.webhook_secret,
        is_active=app.is_active,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


# ==================== Webhook Receiving Routes ====================

@router.post(
    "/webhook/{app_id}",
    response_model=WebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive a webhook",
    description="""
Receive a webhook event for the specified app.

The webhook is processed asynchronously in the background. This endpoint returns
immediately with `202 Accepted` once the webhook is stored.

**Rate Limiting**: Each app has a monthly webhook limit. When exceeded, returns `429 Too Many Requests`.

**Signature Verification**: If the app has signature verification enabled, include the
`X-Webhook-Signature` header with the HMAC signature.

**Idempotency**: To prevent duplicate processing, include an `X-Idempotency-Key` header.
If a webhook with the same key has already been received, the original webhook is returned.

### Request Headers

- `X-Webhook-Signature`: HMAC signature (if verification enabled)
- `X-Idempotency-Key`: Unique idempotency key (optional)
- `Content-Type`: Application/json (default)

### Response Headers

- `X-RateLimit-Limit`: Monthly webhook limit
- `X-RateLimit-Remaining`: Remaining webhooks this month
- `X-RateLimit-Reset`: Unix timestamp when limit resets

### Example

```bash
curl -X POST https://api.hookflow.dev/api/v1/webhook/{app_id} \\
  -H "Content-Type: application/json" \\
  -H "X-Webhook-Signature: t=1234567890,v1=abc123..." \\
  -d '{"event": "user.created", "data": {"id": 123, "name": "Alice"}}'
```
    """,
    responses={
        202: {"description": "Webhook accepted for processing"},
        400: {"description": "Invalid request or signature verification failed"},
        404: {"description": "App not found"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def receive_webhook(
    app_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WebhookService = Depends(get_webhook_service),
    x_webhook_signature: str | None = Header(None, alias="x-webhook-signature"),
    x_idempotency_key: str | None = Header(None, alias="x-idempotency-key"),
):
    """Receive a webhook event."""

    # Get request body
    body = await request.json()

    # Get headers
    headers = {
        "content-type": request.headers.get("content-type", "application/json"),
        "user-agent": request.headers.get("user-agent"),
        "x-forwarded-for": request.headers.get("x-forwarded-for"),
    }
    if x_webhook_signature:
        headers["x-webhook-signature"] = x_webhook_signature
    if x_idempotency_key:
        headers["x-idempotency-key"] = x_idempotency_key

    # Get source IP
    source_ip = request.client.host if request.client else None
    if headers["x-forwarded-for"]:
        source_ip = headers["x-forwarded-for"].split(",")[0].strip()

    try:
        webhook = await service.receive_webhook(
            app_id=app_id,
            body=body,
            headers=headers,
            source_ip=source_ip,
        )

        # Process in background
        background_tasks.add_task(service.process_webhook, webhook.id)

        # Get rate limit headers
        rate_limit_service = RateLimitService(service.db)
        rate_limit_headers = await rate_limit_service.get_rate_limit_headers(app_id)

        response_data = WebhookResponse(
            id=webhook.id,
            app_id=webhook.app_id,
            status=webhook.status,  # type: ignore
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
        )

        return Response(
            content=response_data.model_dump_json(),
            status_code=status.HTTP_202_ACCEPTED,
            media_type="application/json",
            headers=rate_limit_headers,
        )

    except ValueError as e:
        from fastapi import HTTPException

        # Check if this is a rate limit error
        if "Rate limit exceeded" in str(e) or "rate_limit_exceeded" in str(e):
            rate_limit_service = RateLimitService(service.db)
            rate_limit_headers = await rate_limit_service.get_rate_limit_headers(app_id)

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e),
                headers=rate_limit_headers,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/webhook/{app_id}/batch",
    response_model=BatchWebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive multiple webhooks in a single request",
    description="""
Receive multiple webhook events in a single batch request.

This endpoint is optimized for high-volume scenarios where sending multiple
webhooks individually would incur too much latency.

**Processing**: Webhooks are processed asynchronously in the background.
By default, they are processed in parallel. Set `parallel=false` for sequential processing.

**Rate Limiting**: Each webhook counts against your monthly limit.

**Idempotency**: You can provide an `idempotency_key` for each webhook to
prevent duplicate processing.

**Limits**: Maximum 100 webhooks per batch request.

### Example Request

```json
{
  "webhooks": [
    {"id": "evt1", "body": {"event": "user.created", "data": {"id": 1}}},
    {"id": "evt2", "body": {"event": "user.updated", "data": {"id": 2}}}
  ],
  "parallel": true
}
```

### Example Response

```json
{
  "success_count": 2,
  "failure_count": 0,
  "total_count": 2,
  "items": [
    {
      "index": 0,
      "id": "evt1",
      "client_id": "evt1",
      "status": "accepted",
      "webhook_id": "uuid",
      "error": null
    }
  ]
}
```
    """,
    responses={
        202: {"description": "All webhooks accepted for processing"},
        400: {"description": "Invalid request (too many webhooks, etc.)"},
        404: {"description": "App not found"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def receive_batch_webhooks(
    app_id: str,
    batch: BatchWebhookRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WebhookService = Depends(get_webhook_service),
    x_webhook_signature: str | None = Header(None, alias="x-webhook-signature"),
):
    """Receive multiple webhook events in a single request."""

    from fastapi import HTTPException

    # Get app first for rate limit checking
    app = await service._get_app(app_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App not found",
        )

    # Check rate limit for total batch size
    rate_limit_service = RateLimitService(service.db)
    try:
        await rate_limit_service.check_and_increment(
            app_id,
            count=len(batch.webhooks),
        )
    except Exception as e:
        if "Rate limit" in str(e):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e),
            )
        raise

    # Get headers for all webhooks
    headers = {
        "content-type": request.headers.get("content-type", "application/json"),
        "user-agent": request.headers.get("user-agent"),
        "x-forwarded-for": request.headers.get("x-forwarded-for"),
    }
    if x_webhook_signature:
        headers["x-webhook-signature"] = x_webhook_signature

    source_ip = request.client.host if request.client else None
    if headers["x-forwarded-for"]:
        source_ip = headers["x-forwarded-for"].split(",")[0].strip()

    # Process each webhook
    results = []
    success_count = 0
    failure_count = 0

    async def process_single_webhook(
        index: int,
        item: BatchWebhookItem,
    ) -> BatchWebhookItemResponse:
        """Process a single webhook from the batch."""
        nonlocal success_count, failure_count

        item_headers = headers.copy()
        if item.idempotency_key:
            item_headers["x-idempotency-key"] = item.idempotency_key

        try:
            webhook = await service.receive_webhook(
                app_id=app_id,
                body=item.body,
                headers=item_headers,
                source_ip=source_ip,
            )

            # Process in background
            background_tasks.add_task(service.process_webhook, webhook.id)

            success_count += 1
            return BatchWebhookItemResponse(
                index=index,
                id=str(webhook.id),
                client_id=item.id,
                status="accepted",
                webhook_id=str(webhook.id),
                error=None,
            )

        except ValueError as e:
            failure_count += 1
            return BatchWebhookItemResponse(
                index=index,
                id=None,
                client_id=item.id,
                status="rejected",
                webhook_id=None,
                error=str(e),
            )

    if batch.parallel:
        # Process in parallel
        tasks = [
            process_single_webhook(i, item)
            for i, item in enumerate(batch.webhooks)
        ]
        results = await asyncio.gather(*tasks)
    else:
        # Process sequentially
        results = []
        for i, item in enumerate(batch.webhooks):
            result = await process_single_webhook(i, item)
            results.append(result)

    # Get updated rate limit headers
    rate_limit_headers = await rate_limit_service.get_rate_limit_headers(app_id)

    return Response(
        content=BatchWebhookResponse(
            success_count=success_count,
            failure_count=failure_count,
            total_count=len(batch.webhooks),
            items=results,
        ).model_dump_json(),
        status_code=status.HTTP_202_ACCEPTED,
        media_type="application/json",
        headers=rate_limit_headers,
    )


# ==================== Webhook Log Routes ====================

@router.get(
    "/webhooks/{app_id}",
    summary="List webhooks for an app with full details",
    tags=["webhooks"],
)
async def list_webhooks(
    app_id: str,
    service: WebhookService = Depends(get_webhook_service),
    limit: int = 100,
    offset: int = 0,
):
    """List webhooks for an app with full details."""

    import json

    webhooks, total = await service.get_webhooks(
        app_id=app_id,
        limit=limit,
        offset=offset,
    )

    result = []
    for w in webhooks:
        # Parse JSON body if it's a string
        body_data = w.body
        print(f"DEBUG: webhook_id={w.id}, body_type={type(w.body)}, body_value={repr(w.body)[:200]}")
        if isinstance(w.body, str):
            try:
                body_data = json.loads(w.body)
            except:
                body_data = {}

        webhook_data = {
            "id": w.id,
            "app_id": w.app_id,
            "status": w.status,
            "created_at": w.created_at.isoformat() if w.created_at else None,
            "updated_at": w.updated_at.isoformat() if w.updated_at else None,
        }

        # Only add body if it exists
        if body_data is not None:
            webhook_data["body"] = body_data

        # Only add headers if they exist
        if w.headers is not None:
            webhook_data["headers"] = w.headers

        result.append(webhook_data)
        print(f"DEBUG: webhook_data keys={webhook_data.keys()}")

    return result


@router.get(
    "/webhooks/detail/{webhook_id}",
    summary="Get webhook details",
    tags=["webhooks"],
)
async def get_webhook_detail(
    webhook_id: str,
    service: WebhookService = Depends(get_webhook_service),
):
    """Get webhook details with delivery information."""

    webhook, deliveries = await service.get_webhook_detail(webhook_id)

    if not webhook:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    import json

    # Parse body if it's a string
    body_data = webhook.body
    if isinstance(webhook.body, str):
        try:
            body_data = json.loads(webhook.body)
        except:
            body_data = {}

    result = {
        "id": webhook.id,
        "app_id": webhook.app_id,
        "status": webhook.status,
        "idempotency_key": webhook.idempotency_key,
        "source_ip": webhook.source_ip,
        "content_type": webhook.content_type,
        "body": body_data,
        "headers": webhook.headers,
        "created_at": webhook.created_at.isoformat() if webhook.created_at else None,
        "updated_at": webhook.updated_at.isoformat() if webhook.updated_at else None,
        "deliveries": [
            {
                "id": d.id,
                "webhook_id": d.webhook_id,
                "destination_id": d.destination_id,
                "attempt_number": d.attempt_number,
                "status": d.status,
                "response_status_code": d.response_status_code,
                "error_message": d.error_message,
                "response_time_ms": d.response_time_ms,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in deliveries
        ],
    }

    return result


@router.post(
    "/webhooks/{webhook_id}/replay",
    response_model=list[dict],
    summary="Replay a webhook",
    tags=["webhooks"],
)
async def replay_webhook(
    webhook_id: str,
    replay: WebhookReplay,
    service: WebhookService = Depends(get_webhook_service),
):
    """Replay a webhook to destinations."""

    try:
        deliveries = await service.replay_webhook(
            webhook_id=webhook_id,
            destination_ids=replay.destination_ids,
        )

        return [
            {
                "id": str(d.id),
                "webhook_id": str(d.webhook_id),
                "destination_id": str(d.destination_id),
                "status": d.status,
            }
            for d in deliveries
        ]

    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ==================== Destination Routes ====================

@router.post(
    "/apps/{app_id}/destinations",
    response_model=DestinationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a destination",
    tags=["destinations"],
)
async def create_destination(
    app_id: str,
    destination: DestinationCreate,
    service: WebhookService = Depends(get_webhook_service),
):
    """Create a new destination for an app."""

    from hookflow.models import Destination

    db_destination = Destination(
        app_id=app_id,
        name=destination.name,
        type=destination.type,  # type: ignore
        config=destination.config,
        transform_rules=destination.transform_rules,
    )

    service.db.add(db_destination)
    await service.db.commit()
    await service.db.refresh(db_destination)

    return DestinationResponse(
        id=db_destination.id,
        app_id=db_destination.app_id,
        name=db_destination.name,
        type=db_destination.type,  # type: ignore
        is_active=db_destination.is_active,
        created_at=db_destination.created_at,
        updated_at=db_destination.updated_at,
    )


@router.get(
    "/apps/{app_id}/destinations",
    response_model=list[DestinationResponse],
    summary="List destinations",
    tags=["destinations"],
)
async def list_destinations(
    app_id: str,
    service: WebhookService = Depends(get_webhook_service),
):
    """List destinations for an app."""

    destinations = await service._get_destinations(app_id)

    return [
        DestinationResponse(
            id=d.id,
            app_id=d.app_id,
            name=d.name,
            type=d.type,  # type: ignore
            is_active=d.is_active,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in destinations
    ]


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
    from hookflow.models import Destination, Webhook, WebhookStatus

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
        content_type="application/json",
        status=WebhookStatus.PROCESSING,
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


# ==================== Dead Letter Queue Routes ====================

@router.get(
    "/apps/{app_id}/dlq",
    summary="List failed deliveries (Dead Letter Queue)",
    tags=["dead-letter-queue"],
)
async def list_failed_deliveries(
    app_id: str,
    service: WebhookService = Depends(get_webhook_service),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, description="Filter by status (failed, retrying)"),
):
    """List failed webhook deliveries for an app (Dead Letter Queue)."""

    from hookflow.models import Delivery
    from sqlalchemy import select, and_, desc

    # Build query for failed deliveries
    # We need to join with webhooks to filter by app_id
    query = (
        select(Delivery)
        .join(Webhook, Delivery.webhook_id == Webhook.id)
        .where(Webhook.app_id == app_id)
        .where(Delivery.status.in_(["failed", "retrying"]))
    )

    if status:
        query = query.where(Delivery.status == status)

    # Get total count
    from sqlalchemy import func
    count_query = select(func.count()).select_from(query.subquery())
    total = (await service.db.execute(count_query)).scalar() or 0

    # Get paginated results
    query = query.order_by(desc(Delivery.created_at)).offset(offset).limit(limit)
    result = await service.db.execute(query)
    deliveries = list(result.scalars().all())

    # Get related webhooks and destinations for details
    delivery_ids = [d.id for d in deliveries]
    webhook_ids = list({d.webhook_id for d in deliveries})
    destination_ids = list({d.destination_id for d in deliveries})

    # Fetch webhooks
    webhooks_result = await service.db.execute(
        select(Webhook).where(Webhook.id.in_(webhook_ids))
    )
    webhooks = {w.id: w for w in webhooks_result.scalars().all()}

    # Fetch destinations
    from hookflow.models import Destination
    dests_result = await service.db.execute(
        select(Destination).where(Destination.id.in_(destination_ids))
    )
    destinations = {d.id: d for d in dests_result.scalars().all()}

    # Build response
    result_data = []
    for d in deliveries:
        webhook = webhooks.get(d.webhook_id)
        dest = destinations.get(d.destination_id)

        result_data.append({
            "id": str(d.id),
            "webhook_id": str(d.webhook_id),
            "destination_id": str(d.destination_id),
            "destination_name": dest.name if dest else "Unknown",
            "destination_type": dest.type if dest else "unknown",
            "attempt_number": d.attempt_number,
            "status": d.status,
            "error_message": d.error_message,
            "response_status_code": d.response_status_code,
            "response_time_ms": d.response_time_ms,
            "retry_after": d.retry_after.isoformat() if d.retry_after else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "webhook": {
                "id": str(webhook.id) if webhook else None,
                "body": webhook.body if webhook else None,
                "headers": webhook.headers if webhook else None,
            } if webhook else None,
        })

    return {
        "items": result_data,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post(
    "/dlq/{delivery_id}/replay",
    summary="Replay a failed delivery",
    description="""
Replay a failed webhook delivery from the Dead Letter Queue.

Resets the delivery status to `pending` and queues it for immediate retry.
The retry count is reset to 1.

### Example Response

```json
{
  "id": "uuid",
  "status": "pending",
  "message": "Delivery queued for retry"
}
```
    """,
    responses={
        200: {"description": "Delivery queued for replay"},
        400: {"description": "Cannot replay delivery (wrong status)"},
        404: {"description": "Delivery not found"},
    },
    tags=["dead-letter-queue"],
)
async def replay_failed_delivery(
    delivery_id: str,
    service: WebhookService = Depends(get_webhook_service),
):
    """Replay a failed webhook delivery from the Dead Letter Queue."""

    from hookflow.models import Delivery

    # Get the delivery
    result = await service.db.execute(
        select(Delivery).where(Delivery.id == delivery_id)
    )
    delivery = result.scalar_one_or_none()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    # Only allow replay of failed or retrying deliveries
    if delivery.status not in ["failed", "retrying"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot replay delivery with status: {delivery.status}",
        )

    # Reset the delivery for retry
    delivery.status = "pending"
    delivery.attempt_number = 1  # Reset to first attempt
    delivery.error_message = None
    delivery.retry_after = None
    await service.db.commit()

    # Enqueue for delivery
    await service._enqueue_delivery(delivery.webhook_id, delivery.destination_id)

    return {
        "id": str(delivery.id),
        "status": "pending",
        "message": "Delivery queued for retry",
    }


@router.delete(
    "/dlq/{delivery_id}",
    summary="Delete a failed delivery",
    description="""
Permanently delete a failed delivery from the Dead Letter Queue.

This action cannot be undone. The delivery will be removed from the database.

### Example Response

```json
{
  "message": "Delivery deleted"
}
```
    """,
    responses={
        200: {"description": "Delivery deleted successfully"},
        400: {"description": "Cannot delete delivery (wrong status)"},
        404: {"description": "Delivery not found"},
    },
    tags=["dead-letter-queue"],
)
async def delete_failed_delivery(
    delivery_id: str,
    service: WebhookService = Depends(get_webhook_service),
):
    """Delete a failed delivery from the Dead Letter Queue."""

    from hookflow.models import Delivery

    # Get the delivery
    result = await service.db.execute(
        select(Delivery).where(Delivery.id == delivery_id)
    )
    delivery = result.scalar_one_or_none()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    # Only allow deletion of failed deliveries
    if delivery.status not in ["failed", "retrying"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete delivery with status: {delivery.status}",
        )

    await service.db.delete(delivery)
    await service.db.commit()

    return {"message": "Delivery deleted"}


@router.post(
    "/apps/{app_id}/dlq/bulk-replay",
    summary="Bulk replay failed deliveries",
    tags=["dead-letter-queue"],
)
async def bulk_replay_failed_deliveries(
    app_id: str,
    delivery_ids: list[str],
    service: WebhookService = Depends(get_webhook_service),
):
    """Replay multiple failed deliveries at once."""

    from hookflow.models import Delivery

    if not delivery_ids:
        raise HTTPException(status_code=400, detail="No delivery IDs provided")

    if len(delivery_ids) > 100:
        raise HTTPException(status_code=400, detail="Cannot replay more than 100 deliveries at once")

    # Get deliveries
    result = await service.db.execute(
        select(Delivery).where(Delivery.id.in_(delivery_ids))
    )
    deliveries = list(result.scalars().all())

    if not deliveries:
        raise HTTPException(status_code=404, detail="No deliveries found")

    # Verify all deliveries belong to the app
    webhook_ids = [d.webhook_id for d in deliveries]
    webhooks_result = await service.db.execute(
        select(Webhook).where(Webhook.id.in_(webhook_ids))
    )
    webhooks = list(webhooks_result.scalars().all())

    for wh in webhooks:
        if wh.app_id != app_id:
            raise HTTPException(status_code=403, detail="Delivery does not belong to this app")

    # Reset and enqueue for retry
    results = []
    for delivery in deliveries:
        if delivery.status in ["failed", "retrying"]:
            delivery.status = "pending"
            delivery.attempt_number = 1
            delivery.error_message = None
            delivery.retry_after = None

            await service._enqueue_delivery(delivery.webhook_id, delivery.destination_id)

            results.append({
                "id": str(delivery.id),
                "status": "pending",
            })

    await service.db.commit()

    return {
        "replayed": len(results),
        "deliveries": results,
    }


@router.delete(
    "/apps/{app_id}/dlq/bulk-delete",
    summary="Bulk delete failed deliveries",
    tags=["dead-letter-queue"],
)
async def bulk_delete_failed_deliveries(
    app_id: str,
    delivery_ids: list[str],
    service: WebhookService = Depends(get_webhook_service),
):
    """Delete multiple failed deliveries at once."""

    from hookflow.models import Delivery

    if not delivery_ids:
        raise HTTPException(status_code=400, detail="No delivery IDs provided")

    if len(delivery_ids) > 100:
        raise HTTPException(status_code=400, detail="Cannot delete more than 100 deliveries at once")

    # Get deliveries
    result = await service.db.execute(
        select(Delivery).where(Delivery.id.in_(delivery_ids))
    )
    deliveries = list(result.scalars().all())

    if not deliveries:
        raise HTTPException(status_code=404, detail="No deliveries found")

    # Verify all deliveries belong to the app
    webhook_ids = [d.webhook_id for d in deliveries]
    webhooks_result = await service.db.execute(
        select(Webhook).where(Webhook.id.in_(webhook_ids))
    )
    webhooks = list(webhooks_result.scalars().all())

    for wh in webhooks:
        if wh.app_id != app_id:
            raise HTTPException(status_code=403, detail="Delivery does not belong to this app")

    # Delete failed deliveries
    deleted_count = 0
    for delivery in deliveries:
        if delivery.status in ["failed", "retrying"]:
            await service.db.delete(delivery)
            deleted_count += 1

    await service.db.commit()

    return {
        "deleted": deleted_count,
    }


@router.get(
    "/apps/{app_id}/dlq/stats",
    summary="Get Dead Letter Queue statistics",
    description="""
Get statistics about failed webhook deliveries for an app.

Returns summary information about:
- Total failed/retrying deliveries
- Breakdown by status
- Most common error messages

Use this to monitor the health of your webhook deliveries and identify
recurring issues.

### Example Response

```json
{
  "total_failed": 15,
  "by_status": {
    "failed": 12,
    "retrying": 3
  },
  "top_errors": [
    {"error": "Connection timeout", "count": 8},
    {"error": "HTTP 500 Internal Server Error", "count": 4}
  ]
}
```
    """,
    responses={
        200: {"description": "Statistics retrieved successfully"},
        404: {"description": "App not found"},
    },
    tags=["dead-letter-queue"],
)
async def get_dlq_stats(
    app_id: str,
    service: WebhookService = Depends(get_webhook_service),
):
    """Get statistics about failed deliveries for an app."""

    from hookflow.models import Delivery
    from sqlalchemy import select, and_, func, case

    # Get failed/retrying deliveries for this app
    query = (
        select(func.count())
        .select_from(Delivery)
        .join(Webhook, Delivery.webhook_id == Webhook.id)
        .where(Webhook.app_id == app_id)
        .where(Delivery.status.in_(["failed", "retrying"]))
    )
    total_failed = (await service.db.execute(query)).scalar() or 0

    # Get count by status
    status_query = (
        select(Delivery.status, func.count())
        .select_from(Delivery)
        .join(Webhook, Delivery.webhook_id == Webhook.id)
        .where(Webhook.app_id == app_id)
        .where(Delivery.status.in_(["failed", "retrying"]))
        .group_by(Delivery.status)
    )
    status_result = await service.db.execute(status_query)
    by_status = {row[0]: row[1] for row in status_result.all()}

    # Get count by error type (using error_message prefix)
    error_query = (
        select(
            func.substr(Delivery.error_message, 1, 50).label("error"),
            func.count()
        )
        .select_from(Delivery)
        .join(Webhook, Delivery.webhook_id == Webhook.id)
        .where(Webhook.app_id == app_id)
        .where(Delivery.status == "failed")
        .where(Delivery.error_message.isnot(None))
        .group_by(func.substr(Delivery.error_message, 1, 50))
        .order_by(func.count().desc())
        .limit(10)
    )
    error_result = await service.db.execute(error_query)
    top_errors = [{"error": row[0], "count": row[1]} for row in error_result.all()]

    return {
        "total_failed": total_failed,
        "by_status": by_status,
        "top_errors": top_errors,
    }


# ==================== Webhook Templates Routes ====================

@router.get(
    "/templates",
    summary="List webhook templates",
    description="""
List all available webhook templates.

Templates provide pre-configured formats for popular services like
Stripe, GitHub, Shopify, etc. Use templates to quickly set up
webhook integrations with proper event parsing.

Each template includes:
- Sample payload for testing
- Transformation rules to extract relevant fields
- Event type filtering

### Example Response

```json
[
  {
    "provider": "stripe",
    "event_type": "payment_intent.succeeded",
    "name": "Stripe Payment Succeeded",
    "description": "Sent when a payment intent succeeds"
  }
]
```
    """,
    tags=["webhooks"],
)
async def list_webhook_templates(
    provider: TemplateProvider | None = Query(
        None,
        description="Filter by provider (stripe, github, shopify, etc.)",
    ),
):
    """List all available webhook templates."""

    templates = WebhookTemplates.list_templates(provider)
    return templates


@router.get(
    "/templates/{provider}/{event_type}",
    summary="Get webhook template details",
    description="""
Get details for a specific webhook template.

Returns the sample payload and transformation rules for a template.
Use this to understand the structure of webhooks from a provider.

### Example Response

```json
{
  "name": "Stripe Payment Succeeded",
  "description": "Sent when a payment intent succeeds",
  "sample_payload": {...},
  "transformation_rules": {
    "extract": {...},
    "cast": {...}
  }
}
```
    """,
    tags=["webhooks"],
)
async def get_webhook_template(
    provider: TemplateProvider,
    event_type: str,
):
    """Get details for a specific webhook template."""

    template = WebhookTemplates.get_template(provider, event_type)

    if not template or "name" not in template:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {provider}/{event_type}",
        )

    return template


@router.post(
    "/templates/{provider}/{event_type}/test",
    summary="Send test webhook from template",
    description="""
Send a test webhook using a template.

This creates and sends a test webhook using the sample payload
from the specified template. Useful for testing integrations
before going live.

### Example Response

```json
{
  "id": "uuid",
  "app_id": "app_uuid",
  "status": "pending",
  "created_at": "2023-03-01T12:00:00Z"
}
```
    """,
    response_model=WebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["webhooks"],
)
async def test_webhook_template(
    app_id: str,
    provider: TemplateProvider,
    event_type: str,
    background_tasks: BackgroundTasks,
    service: WebhookService = Depends(get_webhook_service),
):
    """Send a test webhook from a template."""

    # Get the sample payload
    sample_payload = WebhookTemplates.create_sample_webhook(provider, event_type)

    if not sample_payload:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {provider}/{event_type}",
        )

    # Create webhook
    webhook = await service.receive_webhook(
        app_id=app_id,
        body=sample_payload,
        headers={
            "content-type": "application/json",
            "user-agent": f"HookFlow-Template/{provider.value}",
            "x-webhook-template": f"{provider.value}/{event_type}",
        },
        source_ip=None,
    )

    # Process in background
    background_tasks.add_task(service.process_webhook, webhook.id)

    return WebhookResponse(
        id=webhook.id,
        app_id=webhook.app_id,
        status=webhook.status,  # type: ignore
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
    )
