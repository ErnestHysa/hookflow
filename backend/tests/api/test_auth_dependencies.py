"""Tests for API authentication dependencies."""

import pytest
from fastapi import HTTPException, status
from unittest.mock import MagicMock

from hookflow.api.dependencies import (
    get_current_user,
    get_current_user_optional,
    require_active_user,
)
from hookflow.models import User
from hookflow.services.auth import ClerkAuthError


@pytest.mark.asyncio
async def test_get_current_user_with_valid_token(db_session, monkeypatch):
    """Test get_current_user with valid Clerk JWT token."""
    from hookflow.core.config import settings

    # Set debug to False to ensure real auth flow
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_secret_key", "test_secret_key_32_characters_long!!")

    # Mock the auth service
    mock_payload = {
        "sub": "user_123",
        "email": "test@example.com",
        "name": "Test User",
    }

    def mock_verify_token(token):
        if token == "valid_token":
            return mock_payload
        raise ClerkAuthError("Invalid token")

    # Create user in database
    user = User(
        id="user_123",
        email="test@example.com",
        name="Test User",
        password_hash="hash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    # Patch the auth service
    from hookflow.api import dependencies
    original_get_service = dependencies.get_clerk_auth_service

    mock_service = MagicMock()
    mock_service.verify_token = mock_verify_token

    def mock_get_clerk_auth_service():
        return mock_service

    dependencies.get_clerk_auth_service = mock_get_clerk_auth_service

    try:
        result = await get_current_user("Bearer valid_token", db_session)

        assert result.id == "user_123"
        assert result.email == "test@example.com"
    finally:
        dependencies.get_clerk_auth_service = original_get_service


@pytest.mark.asyncio
async def test_get_current_user_creates_user_if_not_exists(db_session, monkeypatch):
    """Test that get_current_user creates user if not in database."""
    from hookflow.core.config import settings

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_secret_key", "test_secret_key_32_characters_long!!")

    mock_payload = {
        "sub": "user_new_456",
        "email": "newuser@example.com",
        "name": "New User",
    }

    def mock_verify_token(token):
        return mock_payload

    async def mock_get_or_create_user(db, clerk_id, email, name):
        user = User(
            id=clerk_id,
            email=email,
            name=name,
            password_hash="",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    from hookflow.api import dependencies
    original_get_service = dependencies.get_clerk_auth_service

    mock_service = MagicMock()
    mock_service.verify_token = mock_verify_token
    mock_service.get_or_create_user = mock_get_or_create_user

    def mock_get_clerk_auth_service():
        return mock_service

    dependencies.get_clerk_auth_service = mock_get_clerk_auth_service

    try:
        result = await get_current_user("Bearer valid_token", db_session)

        assert result.id == "user_new_456"
        assert result.email == "newuser@example.com"
    finally:
        dependencies.get_clerk_auth_service = original_get_service


@pytest.mark.asyncio
async def test_get_current_user_fails_without_auth_header(db_session, monkeypatch):
    """Test get_current_user raises 401 without authorization header."""
    from hookflow.core.config import settings

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_secret_key", "test_secret_key_32_characters_long!!")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(None, db_session)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Authorization header required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_fails_with_invalid_format(db_session, monkeypatch):
    """Test get_current_user raises 401 with invalid auth format."""
    from hookflow.core.config import settings

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_secret_key", "test_secret_key_32_characters_long!!")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user("InvalidFormat token", db_session)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid authorization header format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_fails_for_inactive_user(db_session, monkeypatch):
    """Test get_current_user raises 401 for inactive users."""
    from hookflow.core.config import settings

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_secret_key", "test_secret_key_32_characters_long!!")

    mock_payload = {
        "sub": "user_inactive",
        "email": "inactive@example.com",
        "name": "Inactive User",
    }

    def mock_verify_token(token):
        return mock_payload

    # Create inactive user
    user = User(
        id="user_inactive",
        email="inactive@example.com",
        name="Inactive User",
        password_hash="hash",
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    from hookflow.api import dependencies
    original_get_service = dependencies.get_clerk_auth_service

    mock_service = MagicMock()
    mock_service.verify_token = mock_verify_token

    def mock_get_clerk_auth_service():
        return mock_service

    dependencies.get_clerk_auth_service = mock_get_clerk_auth_service

    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Bearer valid_token", db_session)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "inactive" in exc_info.value.detail.lower()
    finally:
        dependencies.get_clerk_auth_service = original_get_service


@pytest.mark.asyncio
async def test_get_current_user_optional_returns_none_without_auth(db_session, monkeypatch):
    """Test get_current_user_optional returns None without authorization."""
    from hookflow.core.config import settings

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_secret_key", "test_secret_key_32_characters_long!!")

    result = await get_current_user_optional(None, db_session)

    assert result is None


@pytest.mark.asyncio
async def test_get_current_user_optional_returns_user_with_valid_auth(
    db_session, monkeypatch
):
    """Test get_current_user_optional returns user with valid auth."""
    from hookflow.core.config import settings

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_secret_key", "test_secret_key_32_characters_long!!")

    mock_payload = {
        "sub": "user_optional",
        "email": "optional@example.com",
        "name": "Optional User",
    }

    def mock_verify_token(token):
        return mock_payload

    user = User(
        id="user_optional",
        email="optional@example.com",
        name="Optional User",
        password_hash="hash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    from hookflow.api import dependencies
    original_get_service = dependencies.get_clerk_auth_service

    mock_service = MagicMock()
    mock_service.verify_token = mock_verify_token

    def mock_get_clerk_auth_service():
        return mock_service

    dependencies.get_clerk_auth_service = mock_get_clerk_auth_service

    try:
        result = await get_current_user_optional("Bearer valid_token", db_session)

        assert result is not None
        assert result.id == "user_optional"
    finally:
        dependencies.get_clerk_auth_service = original_get_service


@pytest.mark.asyncio
async def test_require_active_user_passes_for_active_user():
    """Test require_active_user passes for active users."""
    user = User(
        id="user_active",
        email="active@example.com",
        name="Active User",
        password_hash="hash",
        is_active=True,
    )

    result = await require_active_user(user)

    assert result.id == "user_active"
    assert result.is_active is True


@pytest.mark.asyncio
async def test_require_active_user_fails_for_inactive_user():
    """Test require_active_user raises 403 for inactive users."""
    user = User(
        id="user_inactive_req",
        email="inactive_req@example.com",
        name="Inactive Req User",
        password_hash="hash",
        is_active=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_active_user(user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "inactive" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_in_debug_mode(db_session, monkeypatch):
    """Test get_current_user allows demo user in debug mode."""
    from hookflow.core.config import settings

    monkeypatch.setattr(settings, "debug", True)

    # Create a demo user
    demo_user = User(
        id="demo-user-id",
        email="demo@example.com",
        name="Demo User",
        password_hash="demo",
        is_active=True,
    )
    db_session.add(demo_user)
    await db_session.commit()

    result = await get_current_user(None, db_session)

    assert result is not None
    assert result.email == "demo@example.com"
