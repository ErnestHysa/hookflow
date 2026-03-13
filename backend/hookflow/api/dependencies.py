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

    Placeholder for Phase 2. In Phase 2c, this will:
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
