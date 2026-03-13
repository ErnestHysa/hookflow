"""Tests for retry utilities."""

from datetime import datetime, timedelta

import pytest

from hookflow.utils.retry import (
    RetryPolicy,
    calculate_backoff,
    calculate_backoff_with_retry_after,
    is_retryable_error,
    should_retry,
)


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_5xx_status_codes_are_retryable(self):
        """Test that 5xx status codes are retryable."""
        for status in [500, 502, 503, 504]:
            assert is_retryable_error(status) is True

    def test_429_rate_limit_is_retryable(self):
        """Test that 429 rate limit is retryable."""
        assert is_retryable_error(429) is True

    def test_408_timeout_is_retryable(self):
        """Test that 408 timeout is retryable."""
        assert is_retryable_error(408) is True

    def test_4xx_status_codes_are_not_retryable(self):
        """Test that 4xx status codes (except 429) are not retryable."""
        for status in [400, 401, 403, 404, 422]:
            assert is_retryable_error(status) is False

    def test_2xx_status_codes_are_not_retryable(self):
        """Test that 2xx status codes are not retryable."""
        for status in [200, 201, 204]:
            assert is_retryable_error(status) is False

    def test_none_status_code_is_not_retryable(self):
        """Test that None status code is not retryable."""
        assert is_retryable_error(None) is False

    def test_connection_exception_is_retryable(self):
        """Test that ConnectionError exception is retryable."""
        assert is_retryable_error(None, "ConnectionError") is True

    def test_timeout_exception_is_retryable(self):
        """Test that timeout exceptions are retryable."""
        assert is_retryable_error(None, "TimeoutError") is True
        assert is_retryable_error(None, "ConnectTimeout") is True
        assert is_retryable_error(None, "ReadTimeout") is True

    def test_value_error_is_not_retryable(self):
        """Test that ValueError is not retryable."""
        assert is_retryable_error(None, "ValueError") is False


class TestShouldRetry:
    """Tests for should_retry function."""

    def test_should_retry_when_enabled_and_under_limit(self):
        """Test that retry occurs when enabled and under max retries."""
        assert should_retry(1, max_retries=3, retry_enabled=True) is True
        assert should_retry(2, max_retries=3, retry_enabled=True) is True
        assert should_retry(3, max_retries=3, retry_enabled=True) is True

    def test_should_not_retry_when_exceeds_limit(self):
        """Test that retry does not occur when max retries exceeded."""
        assert should_retry(4, max_retries=3, retry_enabled=True) is False
        assert should_retry(5, max_retries=3, retry_enabled=True) is False

    def test_should_not_retry_when_disabled(self):
        """Test that retry does not occur when disabled."""
        assert should_retry(1, max_retries=3, retry_enabled=False) is False

    def test_default_values(self):
        """Test default parameter values."""
        assert should_retry(1, max_retries=3) is True
        assert should_retry(4, max_retries=3) is False


class TestCalculateBackoff:
    """Tests for calculate_backoff function."""

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        # base=1000ms: 1s, 2s, 4s, 8s, 16s, 32s, 64s (capped at 60s)
        now = datetime.utcnow()

        result1 = calculate_backoff(1, base_ms=1000, max_ms=60000)
        delay1 = (result1 - now).total_seconds()
        assert 1 <= delay1 < 1.5  # ~1s + jitter

        result2 = calculate_backoff(2, base_ms=1000, max_ms=60000)
        delay2 = (result2 - now).total_seconds()
        assert 2 <= delay2 < 2.5  # ~2s + jitter

        result3 = calculate_backoff(3, base_ms=1000, max_ms=60000)
        delay3 = (result3 - now).total_seconds()
        assert 4 <= delay3 < 4.5  # ~4s + jitter

    def test_max_backoff_cap(self):
        """Test that backoff is capped at max_ms."""
        now = datetime.utcnow()

        result = calculate_backoff(10, base_ms=1000, max_ms=60000)
        delay = (result - now).total_seconds()
        # 2^9 = 512s, but capped at 60s + jitter
        assert 60 <= delay < 61

    def test_jitter_is_added(self):
        """Test that jitter is added to backoff."""
        now = datetime.utcnow()

        # Multiple calls should give different results due to jitter
        results = [
            (calculate_backoff(1, base_ms=1000, jitter_ms=500) - now).total_seconds()
            for _ in range(10)
        ]

        # Not all results should be the same
        assert len(set(results)) > 1

    def test_zero_jitter(self):
        """Test backoff with zero jitter."""
        now = datetime.utcnow()

        result = calculate_backoff(1, base_ms=1000, jitter_ms=0)
        delay = (result - now).total_seconds()

        # Should be exactly 1 second
        assert 0.999 <= delay <= 1.001


class TestCalculateBackoffWithRetryAfter:
    """Tests for calculate_backoff_with_retry_after function."""

    def test_respects_retry_after_header(self):
        """Test that Retry-After header is respected."""
        now = datetime.utcnow()

        result = calculate_backoff_with_retry_after("60", 1)
        delay = (result - now).total_seconds()

        # Should use 60 seconds from header, not exponential backoff
        assert 59 <= delay <= 61

    def test_invalid_retry_after_falls_back_to_exponential(self):
        """Test that invalid Retry-After falls back to exponential."""
        now = datetime.utcnow()

        result = calculate_backoff_with_retry_after("invalid-date", 1, base_ms=1000)
        delay = (result - now).total_seconds()

        # Should fall back to ~1s exponential backoff
        assert 1 <= delay < 2

    def test_none_retry_after_uses_exponential(self):
        """Test that None Retry-After uses exponential backoff."""
        now = datetime.utcnow()

        result = calculate_backoff_with_retry_after(None, 2, base_ms=1000)
        delay = (result - now).total_seconds()

        # Should use exponential: 2^(2-1) = 2s
        assert 2 <= delay < 3


class TestRetryPolicy:
    """Tests for RetryPolicy class."""

    def test_default_values(self):
        """Test default RetryPolicy values."""
        policy = RetryPolicy()

        assert policy.enabled is True
        assert policy.max_retries == 3
        assert policy.base_ms == 1000
        assert policy.max_ms == 60000
        assert policy.jitter_ms == 500

    def test_custom_values(self):
        """Test RetryPolicy with custom values."""
        policy = RetryPolicy(
            enabled=False,
            max_retries=5,
            base_ms=2000,
            max_ms=120000,
            jitter_ms=1000,
        )

        assert policy.enabled is False
        assert policy.max_retries == 5
        assert policy.base_ms == 2000
        assert policy.max_ms == 120000
        assert policy.jitter_ms == 1000

    def test_should_retry_method(self):
        """Test RetryPolicy.should_retry method."""
        policy = RetryPolicy(max_retries=3)

        assert policy.should_retry(1) is True
        assert policy.should_retry(2) is True
        assert policy.should_retry(3) is True
        assert policy.should_retry(4) is False

    def test_should_retry_when_disabled(self):
        """Test should_retry returns False when disabled."""
        policy = RetryPolicy(enabled=False, max_retries=3)
        assert policy.should_retry(1) is False

    def test_is_retryable_error_method(self):
        """Test RetryPolicy.is_retryable_error method."""
        policy = RetryPolicy()

        assert policy.is_retryable_error(500) is True
        assert policy.is_retryable_error(404) is False
        assert policy.is_retryable_error(None, "ConnectionError") is True

    def test_calculate_next_retry(self):
        """Test RetryPolicy.calculate_next_retry method."""
        policy = RetryPolicy(base_ms=1000, max_ms=60000)
        now = datetime.utcnow()

        result = policy.calculate_next_retry(2)
        delay = (result - now).total_seconds()

        # 2^(2-1) = 2s
        assert 2 <= delay < 3

    def test_from_destination(self):
        """Test RetryPolicy.from_destination factory."""
        config = {
            "retry_enabled": False,
            "max_retries": 5,
            "retry_backoff_base_ms": 2000,
            "retry_backoff_max_ms": 120000,
            "retry_jitter_ms": 1000,
        }

        policy = RetryPolicy.from_destination(config)

        assert policy.enabled is False
        assert policy.max_retries == 5
        assert policy.base_ms == 2000
        assert policy.max_ms == 120000
        assert policy.jitter_ms == 1000

    def test_from_destination_with_defaults(self):
        """Test RetryPolicy.from_destination with missing config."""
        config = {}

        policy = RetryPolicy.from_destination(config)

        # Should use defaults
        assert policy.enabled is True
        assert policy.max_retries == 3
        assert policy.base_ms == 1000
