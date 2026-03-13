"""Tests for Clerk authentication service."""

import pytest
from hookflow.services.auth import ClerkAuthError, ClerkAuthService, get_clerk_auth_service


class TestClerkAuthService:
    """Tests for ClerkAuthService."""

    def test_get_singleton(self):
        """Test that get_clerk_auth_service returns singleton."""
        service1 = get_clerk_auth_service()
        service2 = get_clerk_auth_service()
        assert service1 is service2

    def test_verify_token_without_secret_key(self, monkeypatch):
        """Test token verification fails without secret key."""
        from hookflow.core.config import settings

        monkeypatch.setattr(settings, "clerk_secret_key", None)

        service = ClerkAuthService()
        with pytest.raises(ClerkAuthError, match="CLERK_SECRET_KEY not configured"):
            service.verify_token("invalid_token")

    def test_is_retryable_error_from_status_codes(self):
        """Test determining retryable errors from status codes."""
        from hookflow.utils.retry import is_retryable_error

        # 5xx errors should be retryable
        assert is_retryable_error(500) is True
        assert is_retryable_error(502) is True
        assert is_retryable_error(503) is True
        assert is_retryable_error(504) is True

        # 429 rate limit should be retryable
        assert is_retryable_error(429) is True

        # 408 timeout should be retryable
        assert is_retryable_error(408) is True

        # 4xx client errors (except 429) should NOT be retryable
        assert is_retryable_error(400) is False
        assert is_retryable_error(401) is False
        assert is_retryable_error(403) is False
        assert is_retryable_error(404) is False

        # 2xx success should NOT be retryable
        assert is_retryable_error(200) is False
        assert is_retryable_error(201) is False

    def test_is_retryable_error_from_exceptions(self):
        """Test determining retryable errors from exception types."""
        from hookflow.utils.retry import is_retryable_error

        assert is_retryable_error(None, "ConnectionError") is True
        assert is_retryable_error(None, "TimeoutError") is True
        assert is_retryable_error(None, "ConnectTimeout") is True
        assert is_retryable_error(None, "ReadTimeout") is True
        assert is_retryable_error(None, "ValueError") is False


@pytest.mark.asyncio
async def test_get_or_create_user_new_user(db_session):
    """Test creating a new user."""
    service = ClerkAuthService()

    user = await service.get_or_create_user(
        db_session,
        clerk_id="user_test_123",
        email="test@example.com",
        name="Test User",
    )

    assert user.id == "user_test_123"
    assert user.email == "test@example.com"
    assert user.name == "Test User"
    assert user.is_active is True


@pytest.mark.asyncio
async def test_get_or_create_user_existing_user(db_session):
    """Test getting an existing user."""
    from hookflow.models import User

    service = ClerkAuthService()

    # Create initial user
    user = User(
        id="user_test_456",
        email="existing@example.com",
        name="Original Name",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    # Get existing user with updated info
    updated_user = await service.get_or_create_user(
        db_session,
        clerk_id="user_test_456",
        email="existing@example.com",
        name="Updated Name",
    )

    assert updated_user.id == "user_test_456"
    assert updated_user.name == "Updated Name"


@pytest.mark.asyncio
async def test_handle_user_created_webhook(db_session):
    """Test handling user.created webhook event."""
    from hookflow.models import User

    service = ClerkAuthService()

    payload = {
        "type": "user.created",
        "data": {
            "id": "user_webhook_123",
            "primary_email_address_id": "email_123",
            "email_addresses": [
                {"id": "email_123", "email_address": "webhook@example.com"}
            ],
            "first_name": "Webhook",
            "last_name": "User",
        },
    }

    await service.handle_webhook(db_session, payload)

    # Verify user was created
    from sqlalchemy import select

    result = await db_session.execute(
        select(User).where(User.id == "user_webhook_123")
    )
    user = result.scalar_one_or_none()

    assert user is not None
    assert user.email == "webhook@example.com"
    assert user.name == "Webhook User"


@pytest.mark.asyncio
async def test_handle_user_deleted_webhook(db_session):
    """Test handling user.deleted webhook event."""
    from hookflow.models import User

    service = ClerkAuthService()

    # Create user first
    user = User(
        id="user_delete_123",
        email="delete@example.com",
        name="To Delete",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    # Send delete webhook
    payload = {
        "type": "user.deleted",
        "data": {"id": "user_delete_123"},
    }

    await service.handle_webhook(db_session, payload)

    # Verify user is deactivated
    await db_session.refresh(user)
    assert user.is_active is False
