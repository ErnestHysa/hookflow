"""Authentication routes for Clerk integration."""

from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.core.database import get_db
from hookflow.models import User
from hookflow.schemas.auth import (
    ClerkWebhookResponse,
    SubscriptionStatusResponse,
    UserInfoResponse,
)
from hookflow.services.auth import ClerkAuthError, get_clerk_auth_service
from hookflow.services.billing import BillingError, get_billing_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> UserInfoResponse:
    """Get current user info from Clerk JWT token.

    Args:
        authorization: Authorization header with Bearer token
        db: Database session

    Returns:
        User info

    Raises:
        HTTPException: If authentication fails
    """
    from fastapi import HTTPException

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]  # Remove "Bearer " prefix

    auth_service = get_clerk_auth_service()

    try:
        payload = auth_service.verify_token(token)

        # Get user ID from token
        clerk_id = payload.get("sub")
        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")

        # Get or create user
        email = payload.get("email", "")
        name = payload.get("name", payload.get("preferred_username", ""))

        user = await auth_service.get_or_create_user(db, clerk_id, email, name)

        return UserInfoResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            plan_tier=user.plan_tier,
            email_verified=user.email_verified,
        )

    except ClerkAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.post("/webhook/clerk", response_model=ClerkWebhookResponse)
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ClerkWebhookResponse:
    """Handle Clerk webhook events.

    Args:
        request: FastAPI request
        db: Database session

    Returns:
        Webhook response
    """
    from fastapi import HTTPException

    # Get Svix signature headers
    svix_id = request.headers.get("svix-id")
    svix_timestamp = request.headers.get("svix-timestamp")
    svix_signature = request.headers.get("svix-signature")

    if not all([svix_id, svix_timestamp, svix_signature]):
        raise HTTPException(status_code=401, detail="Missing signature headers")

    # Get raw payload
    payload = await request.body()

    auth_service = get_clerk_auth_service()

    try:
        # Verify signature (note: Clerk uses Svix, which has different headers)
        # For now, we'll skip detailed verification in dev mode
        # In production, verify with svix library

        # Parse JSON payload
        import json

        data = json.loads(payload.decode())
        await auth_service.handle_webhook(db, data)

        return ClerkWebhookResponse(success=True, message="Webhook processed")

    except ClerkAuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/subscription", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionStatusResponse:
    """Get current user's subscription status.

    Args:
        authorization: Authorization header with Bearer token
        db: Database session

    Returns:
        Subscription status
    """
    from fastapi import HTTPException

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]

    auth_service = get_clerk_auth_service()

    try:
        payload = auth_service.verify_token(token)
        clerk_id = payload.get("sub")

        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        billing_service = get_billing_service()

        if not billing_service:
            # Billing not configured, return free tier
            return SubscriptionStatusResponse(
                status="none",
                plan_tier="free",
                cancel_at_period_end=False,
            )

        status = await billing_service.get_subscription_status(db, clerk_id)

        return SubscriptionStatusResponse(
            status=status.get("status", "none"),
            plan_tier=status.get("plan", "free"),
            cancel_at_period_end=status.get("cancel_at_period_end", False),
            current_period_end=status.get("current_period_end"),
        )

    except (ClerkAuthError, BillingError) as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.post("/billing/checkout")
async def create_checkout_session(
    request: Request,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Create a Stripe checkout session for a subscription.

    Args:
        request: FastAPI request with price_id in body
        authorization: Authorization header with Bearer token
        db: Database session

    Returns:
        Checkout session URL
    """
    from fastapi import HTTPException

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    body = await request.json()
    price_id = body.get("price_id")

    if not price_id:
        raise HTTPException(status_code=400, detail="price_id is required")

    auth_service = get_clerk_auth_service()
    billing_service = get_billing_service()

    if not billing_service:
        raise HTTPException(status_code=501, detail="Billing not configured")

    try:
        payload = auth_service.verify_token(token)
        clerk_id = payload.get("sub")

        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Get base URL for redirects
        host = request.headers.get("host", "localhost:3000")
        scheme = "https" if request.url.scheme == "https" else "http"
        base_url = f"{scheme}://{host}"

        success_url = f"{base_url}/dashboard?checkout=success"
        cancel_url = f"{base_url}/dashboard?checkout=canceled"

        session = await billing_service.create_subscription(
            db,
            clerk_id,
            price_id,
            success_url,
            cancel_url,
        )

        return {"url": session.url}

    except (ClerkAuthError, BillingError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/billing/portal")
async def create_billing_portal_session(
    request: Request,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Create a Stripe billing portal session.

    Args:
        request: FastAPI request
        authorization: Authorization header with Bearer token
        db: Database session

    Returns:
        Billing portal URL
    """
    from fastapi import HTTPException

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    auth_service = get_clerk_auth_service()
    billing_service = get_billing_service()

    if not billing_service:
        raise HTTPException(status_code=501, detail="Billing not configured")

    try:
        payload = auth_service.verify_token(token)
        clerk_id = payload.get("sub")

        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Get base URL for redirect
        host = request.headers.get("host", "localhost:3000")
        scheme = "https" if request.url.scheme == "https" else "http"
        base_url = f"{scheme}://{host}"

        session = await billing_service.create_billing_portal_session(
            db,
            clerk_id,
            f"{base_url}/dashboard",
        )

        return {"url": session.url}

    except (ClerkAuthError, BillingError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Handle Stripe webhook events.

    Args:
        request: FastAPI request
        db: Database session

    Returns:
        Webhook response
    """
    from fastapi import HTTPException

    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature header")

    payload = await request.body()
    billing_service = get_billing_service()

    if not billing_service:
        raise HTTPException(status_code=501, detail="Billing not configured")

    try:
        # Verify signature
        billing_service.verify_webhook_signature(payload, signature)

        # Parse JSON
        import json

        data = json.loads(payload.decode())
        await billing_service.handle_webhook(db, data)

        return {"status": "success"}

    except BillingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
