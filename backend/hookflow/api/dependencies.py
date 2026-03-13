"""API dependencies for authentication and authorization."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from hookflow.core.database import get_db
from hookflow.models import User
from hookflow.services.auth import ClerkAuthError, get_clerk_auth_service


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


async def get_current_user(
    authorization: Annotated[str, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Verify Clerk JWT token and return current user.

    This dependency extracts the Bearer token from the Authorization header,
    verifies it using Clerk's JWKS, and returns the authenticated User.

    Args:
        authorization: Authorization header (format: "Bearer <token>")
        db: Database session

    Returns:
        Authenticated User instance

    Raises:
        HTTPException: 401 if authentication fails or user is inactive
    """
    from hookflow.core.config import settings

    # Allow no auth in development mode for testing
    if settings.debug and not authorization:
        # Return a demo user for local development
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user:
            return user
        # Create demo user if none exists
        from hookflow.models.base import Base, UUIDMixin
        demo_user = User(
            id="demo-user-id",
            email="demo@example.com",
            name="Demo User",
            password_hash="demo",
            email_verified=True,
            is_active=True,
        )
        db.add(demo_user)
        await db.commit()
        await db.refresh(demo_user)
        return demo_user

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    auth_service = get_clerk_auth_service()

    try:
        # Verify JWT token
        payload = auth_service.verify_token(token)

        # Get user ID from token
        clerk_id = payload.get("sub")
        if not clerk_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject claim",
            )

        # Get user from database
        result = await db.execute(select(User).where(User.id == clerk_id))
        user = result.scalar_one_or_none()

        if not user:
            # Get email and name from token to create user
            email = payload.get("email", "")
            name = payload.get(
                "name",
                payload.get("preferred_username", email.split("@")[0] if email else ""),
            )

            user = await auth_service.get_or_create_user(db, clerk_id, email, name)

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
            )

        return user

    except HTTPException:
        raise
    except ClerkAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {e}",
        ) from e


async def get_current_user_optional(
    authorization: Annotated[str, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    Optionally verify Clerk JWT token and return current user.

    Similar to get_current_user but returns None instead of raising
    an exception if authentication fails. Useful for endpoints that
    have different behavior for authenticated vs anonymous users.

    Args:
        authorization: Authorization header (format: "Bearer <token>")
        db: Database session

    Returns:
        Authenticated User instance or None
    """
    if not authorization:
        return None

    try:
        return await get_current_user(authorization, db)
    except HTTPException:
        return None


async def require_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    """
    Ensure the current user is active.

    Args:
        user: Current user from get_current_user

    Returns:
        Active user

    Raises:
        HTTPException: 403 if user is inactive
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return user


# Type aliases for commonly used dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
ActiveUser = Annotated[User, Depends(require_active_user)]
