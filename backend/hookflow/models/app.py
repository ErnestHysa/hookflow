"""Application models for HookFlow."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hookflow.models.base import Base, TimestampMixin, UUIDMixin


class PlanTier(str, Enum):
    """Subscription plan tiers."""

    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class App(Base, UUIDMixin, TimestampMixin):
    """Webhook application/source."""

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Webhook configuration
    webhook_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    verify_signature: Mapped[bool] = mapped_column(Boolean, default=True)

    # Rate limiting
    monthly_limit: Mapped[int] = mapped_column(Integer, default=1000)
    current_month_count: Mapped[int] = mapped_column(Integer, default=0)

    # Retention policy
    retention_hours: Mapped[int] = mapped_column(Integer, default=24)

    # Owner
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="apps")
    webhooks: Mapped[list["Webhook"]] = relationship(
        back_populates="app",
        cascade="all, delete-orphan",
    )
    destinations: Mapped[list["Destination"]] = relationship(
        back_populates="app",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="app",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<App(id={self.id}, name={self.name!r}, user_id={self.user_id})>"


class User(Base, UUIDMixin, TimestampMixin):
    """User account."""

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Subscription
    plan_tier: Mapped[PlanTier] = mapped_column(String(20), default=PlanTier.FREE)

    # Stripe integration
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    apps: Mapped[list["App"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email!r}, plan={self.plan_tier})>"


class Webhook(Base, UUIDMixin, TimestampMixin):
    """Individual webhook event."""

    # Source
    app_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("apps.id"),
        nullable=False,
        index=True,
    )

    # Request metadata
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Content
    content_type: Mapped[str] = mapped_column(String(100), default="application/json")
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    body: Mapped[dict] = mapped_column(JSON, default=dict)

    # Processing status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",  # pending, processing, completed, failed
        index=True,
    )

    # Relationships
    app: Mapped["App"] = relationship(back_populates="webhooks")
    deliveries: Mapped[list["Delivery"]] = relationship(
        back_populates="webhook",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Webhook(id={self.id}, app_id={self.app_id}, status={self.status})>"


class DeliveryStatus(str, Enum):
    """Delivery attempt status."""

    PENDING = "pending"
    SUCCESS = "success"
    RETRYING = "retrying"
    FAILED = "failed"


class Delivery(Base, UUIDMixin, TimestampMixin):
    """Webhook delivery attempt."""

    webhook_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("webhooks.id"),
        nullable=False,
        index=True,
    )
    destination_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("destinations.id"),
        nullable=False,
    )

    # Attempt info
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[DeliveryStatus] = mapped_column(
        String(20),
        default=DeliveryStatus.PENDING,
    )

    # Response
    response_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    webhook: Mapped["Webhook"] = relationship(back_populates="deliveries")
    destination: Mapped["Destination"] = relationship(back_populates="deliveries")

    def __repr__(self) -> str:
        return (
            f"<Delivery(id={self.id}, webhook_id={self.webhook_id}, "
            f"status={self.status}, attempt={self.attempt_number})>"
        )


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


class Destination(Base, UUIDMixin, TimestampMixin):
    """Webhook destination configuration."""

    app_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("apps.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[DestinationType] = mapped_column(String(50), nullable=False)

    # Configuration (encrypted at rest in production)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Transformation rules
    transform_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Retry configuration
    retry_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_backoff_base_ms: Mapped[int] = mapped_column(Integer, default=1000)  # 1 second
    retry_backoff_max_ms: Mapped[int] = mapped_column(Integer, default=60000)  # 60 seconds

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    app: Mapped["App"] = relationship(back_populates="destinations")
    deliveries: Mapped[list["Delivery"]] = relationship(
        back_populates="destination",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Destination(id={self.id}, name={self.name!r}, type={self.type})>"


class ApiKey(Base, UUIDMixin, TimestampMixin):
    """API key for authentication."""

    app_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("apps.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Access control
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Expiration
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Last used
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    app: Mapped["App"] = relationship(back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, name={self.name!r}, prefix={self.key_prefix})>"
