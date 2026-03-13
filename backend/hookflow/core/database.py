"""Database configuration and session management."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from hookflow.core.config import settings

# Use SQLite for local development if no PostgreSQL available
if "sqlite" not in settings.database_url.lower():
    # PostgreSQL
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        echo=settings.debug,
        pool_pre_ping=True,
    )
else:
    # SQLite - create data directory
    db_path = Path(settings.database_url.replace("sqlite+aiosqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
    )

# Create async session factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for use outside of FastAPI dependencies."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database connection and create tables."""
    # Import models and create tables
    from hookflow.models import Base
    from sqlalchemy import text

    async with engine.begin() as conn:
        # For SQLite, enable foreign keys
        if "sqlite" in str(engine.url):
            await conn.execute(text("PRAGMA foreign_keys=ON"))

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connection."""
    await engine.dispose()
