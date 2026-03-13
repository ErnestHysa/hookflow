"""Authentication and billing schemas."""

from pydantic import BaseModel, Field


class UserInfoResponse(BaseModel):
    """User information response."""

    id: str
    email: str
    name: str
    plan_tier: str = "free"
    email_verified: bool = False

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "id": "user_123",
                "email": "user@example.com",
                "name": "John Doe",
                "plan_tier": "pro",
                "email_verified": True,
            }
        }


class ClerkWebhookResponse(BaseModel):
    """Clerk webhook response."""

    success: bool
    message: str = ""


class SubscriptionStatusResponse(BaseModel):
    """Subscription status response."""

    status: str = Field(
        description="Subscription status: active, past_due, canceled, trialing, incomplete, none"
    )
    plan_tier: str = Field(description="Current plan tier: free, pro, team, enterprise")
    cancel_at_period_end: bool = False
    current_period_end: int | None = Field(
        None, description="Unix timestamp of period end"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status": "active",
                "plan_tier": "pro",
                "cancel_at_period_end": False,
                "current_period_end": 1735689600,
            }
        }


class CheckoutRequest(BaseModel):
    """Request to create checkout session."""

    price_id: str = Field(..., description="Stripe price ID")


class PlanFeaturesResponse(BaseModel):
    """Plan features response."""

    tier: str
    name: str
    monthly_webhooks: int | str
    retention_days: int
    max_destinations: int | str
    max_retry_attempts: int | str
    price_monthly: int | None = Field(None, description="Price in cents")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "tier": "pro",
                "name": "Pro",
                "monthly_webhooks": 50000,
                "retention_days": 30,
                "max_destinations": 10,
                "max_retry_attempts": 5,
                "price_monthly": 2900,
            }
        }
