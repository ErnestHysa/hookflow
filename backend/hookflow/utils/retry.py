"""Retry utilities for webhook delivery."""

import random
from datetime import datetime, timedelta
from typing import Any


# Status codes that should trigger a retry
RETRYABLE_STATUS_CODES = {
    # 5xx Server Errors
    500, 502, 503, 504,
    # 429 Rate Limited (with Retry-After header preferred)
    429,
    # 408 Request Timeout
    408,
}

# Exceptions that should trigger a retry
RETRYABLE_EXCEPTIONS = {
    "ConnectionError",
    "TimeoutError",
    "ConnectTimeout",
    "ReadTimeout",
    "TooManyRedirects",
}


def is_retryable_error(status_code: int | None, exception_type: str | None = None) -> bool:
    """Check if an error is retryable based on status code or exception type.

    Args:
        status_code: HTTP status code from response
        exception_type: Type of exception that occurred

    Returns:
        True if the error should be retried
    """
    if status_code in RETRYABLE_STATUS_CODES:
        return True

    if exception_type and any(
        exc in exception_type
        for exc in RETRYABLE_EXCEPTIONS
    ):
        return True

    return False


def calculate_backoff(
    attempt_number: int,
    base_ms: int = 1000,
    max_ms: int = 60000,
    jitter_ms: int = 500,
) -> datetime:
    """Calculate exponential backoff with jitter for next retry.

    Uses the formula: min(max, base * 2^(attempt-1)) + random_jitter

    Args:
        attempt_number: Current attempt number (1-based)
        base_ms: Base backoff time in milliseconds
        max_ms: Maximum backoff time in milliseconds
        jitter_ms: Maximum random jitter to add in milliseconds

    Returns:
        Datetime when the next retry should occur
    """
    # Calculate exponential backoff: base * 2^(attempt-1)
    exponential_delay = min(
        max_ms,
        base_ms * (2 ** (attempt_number - 1))
    )

    # Add random jitter to avoid thundering herd
    jitter = random.randint(0, jitter_ms)

    total_delay_ms = exponential_delay + jitter

    return datetime.utcnow() + timedelta(milliseconds=total_delay_ms)


def calculate_backoff_with_retry_after(
    retry_after_header: str | None,
    attempt_number: int,
    base_ms: int = 1000,
    max_ms: int = 60000,
    jitter_ms: int = 500,
) -> datetime:
    """Calculate backoff time, respecting Retry-After header if present.

    Args:
        retry_after_header: Value of Retry-After header (seconds or HTTP-date)
        attempt_number: Current attempt number (1-based)
        base_ms: Base backoff time in milliseconds
        max_ms: Maximum backoff time in milliseconds
        jitter_ms: Maximum random jitter to add in milliseconds

    Returns:
        Datetime when the next retry should occur
    """
    if retry_after_header:
        try:
            # Try parsing as seconds (most common)
            seconds = int(retry_after_header)
            return datetime.utcnow() + timedelta(seconds=seconds)
        except ValueError:
            # Could be an HTTP-date; for simplicity, fall through to exponential
            pass

    return calculate_backoff(attempt_number, base_ms, max_ms, jitter_ms)


def should_retry(
    attempt_number: int,
    max_retries: int,
    retry_enabled: bool = True,
) -> bool:
    """Determine if a delivery should be retried.

    Args:
        attempt_number: Current attempt number (1-based)
        max_retries: Maximum number of retry attempts
        retry_enabled: Whether retries are enabled for this destination

    Returns:
        True if the delivery should be retried
    """
    if not retry_enabled:
        return False

    # attempt_number is 1-based, so we retry while attempt <= max_retries
    # First delivery is attempt 1, first retry is attempt 2, etc.
    return attempt_number <= max_retries


class RetryPolicy:
    """Configuration for retry behavior."""

    def __init__(
        self,
        enabled: bool = True,
        max_retries: int = 3,
        base_ms: int = 1000,
        max_ms: int = 60000,
        jitter_ms: int = 500,
    ):
        self.enabled = enabled
        self.max_retries = max_retries
        self.base_ms = base_ms
        self.max_ms = max_ms
        self.jitter_ms = jitter_ms

    def should_retry(self, attempt_number: int) -> bool:
        """Check if retry should occur based on attempt number."""
        return should_retry(attempt_number, self.max_retries, self.enabled)

    def calculate_next_retry(
        self,
        attempt_number: int,
        retry_after_header: str | None = None,
    ) -> datetime:
        """Calculate when the next retry should occur."""
        return calculate_backoff_with_retry_after(
            retry_after_header,
            attempt_number,
            self.base_ms,
            self.max_ms,
            self.jitter_ms,
        )

    def is_retryable_error(self, status_code: int | None, exception_type: str | None = None) -> bool:
        """Check if an error is retryable."""
        return is_retryable_error(status_code, exception_type)

    @classmethod
    def from_destination(cls, destination_config: dict[str, Any]) -> "RetryPolicy":
        """Create a RetryPolicy from a destination's config.

        Args:
            destination_config: Destination configuration dict

        Returns:
            RetryPolicy instance
        """
        return cls(
            enabled=destination_config.get("retry_enabled", True),
            max_retries=destination_config.get("max_retries", 3),
            base_ms=destination_config.get("retry_backoff_base_ms", 1000),
            max_ms=destination_config.get("retry_backoff_max_ms", 60000),
            jitter_ms=destination_config.get("retry_jitter_ms", 500),
        )
