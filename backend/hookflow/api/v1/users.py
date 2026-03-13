"""User management routes with Clerk JWT authentication."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.api.dependencies import CurrentUser, OptionalUser
from hookflow.core.database import get_db
from hookflow.models import App, User, Webhook, Delivery
from hookflow.schemas.auth import UserInfoResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserInfoResponse)
async def get_user_profile(current_user: CurrentUser) -> UserInfoResponse:
    """Get current user profile.

    This endpoint requires authentication via Clerk JWT token.

    Authentication: Bearer token required in Authorization header
    """
    return UserInfoResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        plan_tier=current_user.plan_tier,
        email_verified=current_user.email_verified,
    )


@router.get("/me/apps")
async def get_user_apps(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    """Get all apps for the current user.

    This endpoint requires authentication and returns only apps
    owned by the authenticated user.
    """
    # Get total count
    count_query = select(func.count()).select_from(App).where(App.user_id == current_user.id)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get paginated apps
    query = select(App).where(App.user_id == current_user.id).offset(skip).limit(limit)
    result = await db.execute(query)
    apps = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            {
                "id": str(app.id),
                "name": app.name,
                "description": app.description,
                "is_active": app.is_active,
                "monthly_limit": app.monthly_limit,
                "current_month_count": app.current_month_count,
                "created_at": app.created_at.isoformat() if app.created_at else None,
            }
            for app in apps
        ],
    }


@router.get("/me/stats")
async def get_user_stats(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get usage statistics for the current user.

    This endpoint requires authentication and returns aggregated
    statistics for all apps owned by the user.
    """
    # Get total webhooks count
    webhooks_query = (
        select(func.count())
        .select_from(Webhook)
        .join(App, App.id == Webhook.app_id)
        .where(App.user_id == current_user.id)
    )
    webhooks_result = await db.execute(webhooks_query)
    total_webhooks = webhooks_result.scalar() or 0

    # Get total deliveries count
    deliveries_query = (
        select(func.count())
        .select_from(Delivery)
        .join(Webhook, Webhook.id == Delivery.webhook_id)
        .join(App, App.id == Webhook.app_id)
        .where(App.user_id == current_user.id)
    )
    deliveries_result = await db.execute(deliveries_query)
    total_deliveries = deliveries_result.scalar() or 0

    # Get successful deliveries
    success_query = (
        select(func.count())
        .select_from(Delivery)
        .join(Webhook, Webhook.id == Delivery.webhook_id)
        .join(App, App.id == Webhook.app_id)
        .where(App.user_id == current_user.id)
        .where(Delivery.status == "success")
    )
    success_result = await db.execute(success_query)
    successful_deliveries = success_result.scalar() or 0

    # Get failed deliveries
    failed_query = (
        select(func.count())
        .select_from(Delivery)
        .join(Webhook, Webhook.id == Delivery.webhook_id)
        .join(App, App.id == Webhook.app_id)
        .where(App.user_id == current_user.id)
        .where(Delivery.status == "failed")
    )
    failed_result = await db.execute(failed_query)
    failed_deliveries = failed_result.scalar() or 0

    return {
        "total_webhooks": total_webhooks,
        "total_deliveries": total_deliveries,
        "successful_deliveries": successful_deliveries,
        "failed_deliveries": failed_deliveries,
        "success_rate": (
            round(successful_deliveries / total_deliveries * 100, 2)
            if total_deliveries > 0
            else 0
        ),
    }


@router.get("/public-info")
async def get_public_info(
    current_user: OptionalUser,
) -> dict:
    """Get public information with optional authentication.

    This endpoint demonstrates optional authentication - it returns
    different data based on whether the user is authenticated.

    - Unauthenticated: Returns public information only
    - Authenticated: Returns public info plus user-specific data
    """
    public_data = {
        "service": "HookFlow",
        "version": "0.1.0",
        "features": [
            "Reliable webhook delivery",
            "Event transformation",
            "Dead letter queue",
            "Multiple destination types",
        ],
    }

    if current_user:
        public_data["authenticated"] = True
        public_data["user"] = {
            "email": current_user.email,
            "plan_tier": current_user.plan_tier,
        }
    else:
        public_data["authenticated"] = False
        public_data["message"] = "Sign in to access personalized features"

    return public_data


@router.patch("/me/profile")
async def update_user_profile(
    current_user: CurrentUser,
    name: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> UserInfoResponse:
    """Update current user profile.

    This endpoint requires authentication and allows users to
    update their profile information.
    """
    if name is not None:
        current_user.name = name

    await db.commit()
    await db.refresh(current_user)

    return UserInfoResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        plan_tier=current_user.plan_tier,
        email_verified=current_user.email_verified,
    )
