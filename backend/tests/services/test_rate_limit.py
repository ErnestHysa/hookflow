"""Tests for rate limiting service."""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from hookflow.models import App, User, PlanTier
from hookflow.services.rate_limit import (
    RateLimitService,
    RateLimitStatus,
    RateLimitExceededError,
)
from fastapi import HTTPException


@pytest_asyncio.fixture
async def test_app_with_limit(db_session: AsyncSession) -> App:
    """Create a test app with a low rate limit for testing."""
    # Create user
    import uuid
    user = User(
        id=str(uuid.uuid4()),
        email="ratelimit@test.com",
        name="Rate Limit Test User",
        password_hash="test",
    )
    db_session.add(user)
    await db_session.commit()

    # Create app with low limit
    app = App(
        name="Rate Limit Test App",
        webhook_secret="test_secret",
        user_id=user.id,
        monthly_limit=10,  # Low limit for testing
        current_month_count=0,
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    return app


@pytest_asyncio.fixture
async def test_app_at_limit(db_session: AsyncSession) -> App:
    """Create a test app already at its rate limit."""
    import uuid
    user = User(
        id=str(uuid.uuid4()),
        email="ratelimitfull@test.com",
        name="Rate Limit Full User",
        password_hash="test",
    )
    db_session.add(user)
    await db_session.commit()

    # Create app at limit
    app = App(
        name="Rate Limit Full App",
        webhook_secret="test_secret",
        user_id=user.id,
        monthly_limit=5,
        current_month_count=5,  # Already at limit
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    return app


class TestRateLimitService:
    """Tests for RateLimitService."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_within_limit(
        self,
        db_session: AsyncSession,
        test_app_with_limit: App,
    ):
        """Test checking rate limit when within allowed quota."""
        service = RateLimitService(db_session)

        status = await service.check_rate_limit(test_app_with_limit.id)

        assert status.allowed is True
        assert status.limit == 10
        assert status.remaining == 10
        assert isinstance(status.reset_at, datetime)

    @pytest.mark.asyncio
    async def test_check_rate_limit_at_limit(
        self,
        db_session: AsyncSession,
        test_app_at_limit: App,
    ):
        """Test checking rate limit when quota is exceeded."""
        service = RateLimitService(db_session)

        with pytest.raises(RateLimitExceededError) as exc_info:
            await service.check_rate_limit(test_app_at_limit.id)

        error = exc_info.value
        assert error.status_code == 429
        assert error.remaining == 0
        assert error.limit == 5
        assert isinstance(error.reset_at, datetime)

    @pytest.mark.asyncio
    async def test_check_rate_limit_app_not_found(
        self,
        db_session: AsyncSession,
    ):
        """Test checking rate limit for non-existent app."""
        service = RateLimitService(db_session)

        import uuid
        with pytest.raises(HTTPException) as exc_info:
            await service.check_rate_limit(str(uuid.uuid4()))

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_increment_usage(
        self,
        db_session: AsyncSession,
        test_app_with_limit: App,
    ):
        """Test incrementing usage counter."""
        service = RateLimitService(db_session)

        await service.increment_usage(test_app_with_limit.id, count=3)

        # Refresh app from database
        await db_session.refresh(test_app_with_limit)
        assert test_app_with_limit.current_month_count == 3

    @pytest.mark.asyncio
    async def test_reset_monthly_counter(
        self,
        db_session: AsyncSession,
        test_app_with_limit: App,
    ):
        """Test resetting monthly counter."""
        service = RateLimitService(db_session)

        # Increment first
        await service.increment_usage(test_app_with_limit.id, count=5)
        await db_session.refresh(test_app_with_limit)
        assert test_app_with_limit.current_month_count == 5

        # Reset
        await service.reset_monthly_counter(test_app_with_limit.id)
        await db_session.refresh(test_app_with_limit)
        assert test_app_with_limit.current_month_count == 0

    @pytest.mark.asyncio
    async def test_check_and_increment_within_limit(
        self,
        db_session: AsyncSession,
        test_app_with_limit: App,
    ):
        """Test check_and_increment when within limit."""
        service = RateLimitService(db_session)

        status = await service.check_and_increment(test_app_with_limit.id, count=3)

        assert status.allowed is True
        assert status.remaining == 7  # 10 - 3

        # Verify counter was incremented
        await db_session.refresh(test_app_with_limit)
        assert test_app_with_limit.current_month_count == 3

    @pytest.mark.asyncio
    async def test_check_and_increment_exceeds_limit(
        self,
        db_session: AsyncSession,
        test_app_with_limit: App,
    ):
        """Test check_and_increment when it would exceed limit."""
        service = RateLimitService(db_session)

        # Set count to near limit
        test_app_with_limit.current_month_count = 9
        await db_session.commit()

        # Try to increment by 2 (would exceed limit of 10)
        with pytest.raises(RateLimitExceededError):
            await service.check_and_increment(test_app_with_limit.id, count=2)

        # Counter should not have been incremented
        await db_session.refresh(test_app_with_limit)
        assert test_app_with_limit.current_month_count == 9

    @pytest.mark.asyncio
    async def test_get_rate_limit_headers(
        self,
        db_session: AsyncSession,
        test_app_with_limit: App,
    ):
        """Test getting rate limit headers."""
        service = RateLimitService(db_session)

        headers = await service.get_rate_limit_headers(test_app_with_limit.id)

        assert "X-RateLimit-Limit" in headers
        assert headers["X-RateLimit-Limit"] == "10"
        assert "X-RateLimit-Remaining" in headers
        assert headers["X-RateLimit-Remaining"] == "10"
        assert "X-RateLimit-Reset" in headers
        assert "X-RateLimit-Reset-At" in headers

    @pytest.mark.asyncio
    async def test_get_rate_limit_headers_with_usage(
        self,
        db_session: AsyncSession,
        test_app_with_limit: App,
    ):
        """Test rate limit headers reflect current usage."""
        service = RateLimitService(db_session)

        # Add some usage
        await service.increment_usage(test_app_with_limit.id, count=4)

        headers = await service.get_rate_limit_headers(test_app_with_limit.id)

        assert headers["X-RateLimit-Limit"] == "10"
        assert headers["X-RateLimit-Remaining"] == "6"

    @pytest.mark.asyncio
    async def test_check_and_increment_single(
        self,
        db_session: AsyncSession,
        test_app_with_limit: App,
    ):
        """Test check_and_increment with default count of 1."""
        service = RateLimitService(db_session)

        status = await service.check_and_increment(test_app_with_limit.id)

        assert status.allowed is True
        assert status.remaining == 9  # 10 - 1

        await db_session.refresh(test_app_with_limit)
        assert test_app_with_limit.current_month_count == 1


class TestRateLimitServiceIntegration:
    """Integration tests for rate limiting with webhook flow."""

    @pytest.mark.asyncio
    async def test_multiple_webhooks_until_limit(
        self,
        db_session: AsyncSession,
        test_app_with_limit: App,
    ):
        """Test processing multiple webhooks until limit is hit."""
        service = RateLimitService(db_session)

        # Process 10 webhooks (at limit)
        for i in range(10):
            status = await service.check_and_increment(test_app_with_limit.id)
            assert status.allowed is True

        # 11th should fail
        with pytest.raises(RateLimitExceededError):
            await service.check_and_increment(test_app_with_limit.id)

    @pytest.mark.asyncio
    async def test_inactive_app_rejected(
        self,
        db_session: AsyncSession,
        test_app_with_limit: App,
    ):
        """Test that inactive apps are rejected."""
        service = RateLimitService(db_session)

        # Deactivate app
        test_app_with_limit.is_active = False
        await db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await service.check_rate_limit(test_app_with_limit.id)

        assert exc_info.value.status_code == 403
