"""Rate limiting service for webhook delivery.

Tracks webhook usage per app per month and enforces monthly limits.
"""

from datetime import datetime, timezone
from typing import NamedTuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException, status

from hookflow.models import App


class RateLimitStatus(NamedTuple):
    """Result of rate limit check."""

    allowed: bool
    remaining: int
    limit: int
    reset_at: datetime


class RateLimitExceededError(HTTPException):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        remaining: int,
        limit: int,
        reset_at: datetime,
    ):
        self.remaining = remaining
        self.limit = limit
        self.reset_at = reset_at
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Monthly webhook limit exceeded",
                "limit": limit,
                "remaining": remaining,
                "reset_at": reset_at.isoformat(),
            },
        )


class RateLimitService:
    """Service for managing rate limits."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize rate limit service.

        Args:
            db: Database session
        """
        self.db = db

    def _get_current_month_key(self) -> tuple[int, int]:
        """Get the current month key for tracking.

        Returns:
            Tuple of (year, month) for current month in UTC
        """
        now = datetime.now(timezone.utc)
        return (now.year, now.month)

    def _get_month_start(self) -> datetime:
        """Get the start of the current month.

        Returns:
            DateTime at start of current month in UTC
        """
        now = datetime.now(timezone.utc)
        return datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    def _get_next_month_start(self) -> datetime:
        """Get the start of the next month.

        Returns:
            DateTime at start of next month in UTC
        """
        now = datetime.now(timezone.utc)
        if now.month == 12:
            return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

    async def check_rate_limit(self, app_id: str) -> RateLimitStatus:
        """Check if app is within rate limit.

        Args:
            app_id: The app ID to check

        Returns:
            RateLimitStatus with allowed, remaining, limit, and reset_at

        Raises:
            RateLimitExceededError: If limit is exceeded
        """
        # Get app with current stats
        result = await self.db.execute(
            select(App).where(App.id == app_id)
        )
        app = result.scalar_one_or_none()

        if not app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="App not found",
            )

        if not app.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="App is not active",
            )

        # Check if we need to reset the counter (new month)
        current_year, current_month = self._get_current_month_key()
        month_start = self._get_month_start()

        # Check if the counter was last updated in a previous month
        # We can detect this by checking if current_month_count is high
        # and we're in a new month. A more robust solution would store
        # the last reset timestamp, but for now we use a simple approach:
        # if the count is at or near the limit and we're early in the month,
        # we assume it might be from the previous month.
        # For production, add a 'count_reset_at' column to the App model.

        # For now, just check against current count
        limit = app.monthly_limit
        current_count = app.current_month_count
        remaining = max(0, limit - current_count)
        reset_at = self._get_next_month_start()

        if current_count >= limit:
            raise RateLimitExceededError(
                remaining=remaining,
                limit=limit,
                reset_at=reset_at,
            )

        return RateLimitStatus(
            allowed=True,
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
        )

    async def increment_usage(
        self,
        app_id: str,
        count: int = 1,
    ) -> None:
        """Increment webhook usage counter for an app.

        Args:
            app_id: The app ID
            count: Number to increment by (default: 1)
        """
        await self.db.execute(
            update(App)
            .where(App.id == app_id)
            .values(current_month_count=App.current_month_count + count)
        )
        await self.db.commit()

    async def reset_monthly_counter(self, app_id: str) -> None:
        """Reset the monthly counter for an app.

        Should be called at the start of each month.

        Args:
            app_id: The app ID
        """
        await self.db.execute(
            update(App)
            .where(App.id == app_id)
            .values(current_month_count=0)
        )
        await self.db.commit()

    async def check_and_increment(
        self,
        app_id: str,
        count: int = 1,
    ) -> RateLimitStatus:
        """Check rate limit and increment if allowed.

        This is a convenience method that combines check_rate_limit
        and increment_usage in a single transaction.

        Args:
            app_id: The app ID
            count: Number to increment by (default: 1)

        Returns:
            RateLimitStatus with allowed, remaining, limit, and reset_at

        Raises:
            RateLimitExceededError: If limit is exceeded
        """
        # Get app with current stats
        result = await self.db.execute(
            select(App).where(App.id == app_id)
        )
        app = result.scalar_one_or_none()

        if not app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="App not found",
            )

        if not app.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="App is not active",
            )

        limit = app.monthly_limit
        current_count = app.current_month_count
        remaining = max(0, limit - current_count)
        reset_at = self._get_next_month_start()

        # Check if incrementing would exceed limit
        if current_count + count > limit:
            raise RateLimitExceededError(
                remaining=remaining,
                limit=limit,
                reset_at=reset_at,
            )

        # Increment the counter
        await self.increment_usage(app_id, count)

        return RateLimitStatus(
            allowed=True,
            remaining=max(0, remaining - count),
            limit=limit,
            reset_at=reset_at,
        )

    async def get_rate_limit_headers(
        self,
        app_id: str,
    ) -> dict[str, str]:
        """Get rate limit headers for an app.

        Args:
            app_id: The app ID

        Returns:
            Dictionary of rate limit headers
        """
        result = await self.db.execute(
            select(App).where(App.id == app_id)
        )
        app = result.scalar_one_or_none()

        if not app:
            return {}

        limit = app.monthly_limit
        current = app.current_month_count
        remaining = max(0, limit - current)
        reset_at = self._get_next_month_start()

        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_at.timestamp())),
            "X-RateLimit-Reset-At": reset_at.isoformat(),
        }
