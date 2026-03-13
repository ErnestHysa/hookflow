"""Webhook API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.core.database import get_db
from hookflow.schemas import (
    AppCreate,
    AppListResponse,
    AppResponse,
    DestinationCreate,
    DestinationResponse,
    WebhookDetailResponse,
    WebhookReplay,
    WebhookResponse,
)
from hookflow.services import WebhookService

router = APIRouter(tags=["webhooks"])


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
    description="Receive a webhook event for the specified app. Returns immediately with 202 Accepted.",
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

        return WebhookResponse(
            id=webhook.id,
            app_id=webhook.app_id,
            status=webhook.status,  # type: ignore
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
        )

    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
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
