"""Webhook schemas for request/response validation."""

import json
import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, field_validator


class WebhookStatus(str, Enum):
    """Webhook processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DestinationType(str, Enum):
    """Destination types."""

    HTTP = "http"
    DATABASE = "database"
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    EMAIL = "email"
    NOTION = "notion"
    AIRTABLE = "airtable"
    GOOGLE_SHEETS = "google_sheets"


class PlanTier(str, Enum):
    """Subscription plan tiers."""

    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


# Request schemas


class WebhookReceive(BaseModel):
    """Webhook receive request (any JSON body accepted)."""

    # Any JSON data is accepted - the model is dynamic
    pass


class WebhookHeaders(BaseModel):
    """Webhook headers."""

    content_type: str = Field(default="application/json", alias="content-type")
    user_agent: str | None = Field(default=None, alias="user-agent")
    x_forwarded_for: str | None = Field(default=None, alias="x-forwarded-for")
    x_webhook_signature: str | None = Field(default=None, alias="x-webhook-signature")
    x_idempotency_key: str | None = Field(default=None, alias="x-idempotency-key")

    model_config = ConfigDict(populate_by_name=True)


class AppCreate(BaseModel):
    """Create a new app."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class AppUpdate(BaseModel):
    """Update an app."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    verify_signature: bool | None = None


class DestinationCreate(BaseModel):
    """Create a destination."""

    name: str = Field(..., min_length=1, max_length=255)
    type: DestinationType
    config: dict = Field(default_factory=dict)
    transform_rules: dict | None = None


class DestinationUpdate(BaseModel):
    """Update a destination."""

    name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None
    config: dict | None = None
    transform_rules: dict | None = None


class WebhookReplay(BaseModel):
    """Replay a webhook."""

    destination_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Specific destinations to replay to, or all if not specified",
    )


class BatchWebhookItem(BaseModel):
    """A single webhook in a batch request."""

    id: str | None = Field(
        None,
        description="Optional client-provided ID for this webhook (for tracking in response)",
    )
    body: dict = Field(..., description="Webhook payload")
    idempotency_key: str | None = Field(
        None,
        description="Optional idempotency key for deduplication",
    )


class BatchWebhookRequest(BaseModel):
    """Batch webhook request."""

    webhooks: list[BatchWebhookItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of webhooks to process (max 100 per batch)",
    )
    parallel: bool = Field(
        default=True,
        description="Process webhooks in parallel (default) or sequentially",
    )


class BatchWebhookItemResponse(BaseModel):
    """Response for a single webhook in a batch."""

    index: int
    id: str | None
    client_id: str | None
    status: str
    webhook_id: str | None
    error: str | None


class BatchWebhookResponse(BaseModel):
    """Batch webhook response."""

    success_count: int
    failure_count: int
    total_count: int
    items: list[BatchWebhookItemResponse]


# Response schemas


class WebhookResponse(BaseModel):
    """Webhook response."""

    id: str
    app_id: str
    status: WebhookStatus
    created_at: datetime
    updated_at: datetime

    @field_serializer('status')
    def serialize_status(self, value: WebhookStatus) -> str:
        """Convert enum to string."""
        return value.value if isinstance(value, WebhookStatus) else str(value)

    model_config = ConfigDict(from_attributes=True)


class DeliveryResponse(BaseModel):
    """Delivery attempt response."""

    id: str
    webhook_id: str
    destination_id: str
    attempt_number: int
    status: str
    response_status_code: int | None
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DestinationResponse(BaseModel):
    """Destination response."""

    id: str
    app_id: str
    name: str
    type: DestinationType
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Config is excluded for security (may contain secrets)
    model_config = ConfigDict(from_attributes=True)


class AppResponse(BaseModel):
    """App response."""

    id: str
    name: str
    description: str | None
    verify_signature: bool
    monthly_limit: int
    current_month_count: int
    webhook_secret: str  # Only shown on creation
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppListResponse(BaseModel):
    """App list response (without secret)."""

    id: str
    name: str
    description: str | None
    monthly_limit: int
    current_month_count: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookDetailResponse(BaseModel):
    """Detailed webhook response with deliveries."""

    id: str
    app_id: str
    status: WebhookStatus
    idempotency_key: str | None
    source_ip: str | None
    content_type: str
    body: dict
    headers: dict
    created_at: datetime
    deliveries: list[DeliveryResponse] = []

    @field_serializer('body')
    def serialize_body(self, value: dict | str) -> dict:
        """Handle JSON string from database."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return {}
        return value

    model_config = ConfigDict(from_attributes=True)


# Error schemas


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: str | None = None
    code: str | None = None


class ValidationErrorResponse(BaseModel):
    """Validation error response."""

    error: str = "validation_error"
    detail: list[dict] = Field(..., description="List of validation errors")
