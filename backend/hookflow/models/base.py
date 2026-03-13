"""Base database models and utilities."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        return cls.__name__.lower() + "s"

    def __repr__(self) -> str:
        """String representation of model."""
        class_name = self.__class__.__name__
        attrs = []
        for key in self.__mapper__.columns.keys():
            value = getattr(self, key)
            if key == "password_hash":
                value = "***"
            attrs.append(f"{key}={value!r}")
        return f"{class_name}({', '.join(attrs)})"


class TimestampMixin:
    """Mixin for adding timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """Mixin for UUID primary key (works with SQLite and PostgreSQL)."""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
