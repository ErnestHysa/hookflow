"""Tests for circuit breaker implementation."""

import time
import pytest

from hookflow.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    AsyncCircuitBreaker,
    get_circuit_breaker,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_is_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker("test-destination")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0

    def test_allow_request_when_closed(self):
        """Test that requests are allowed when circuit is closed."""
        breaker = CircuitBreaker("test-destination")
        assert breaker.allow_request() is True

    def test_record_success_in_closed_state(self):
        """Test recording success in closed state."""
        breaker = CircuitBreaker("test-destination")
        breaker.record_success()
        assert breaker.success_count == 1
        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_record_failure_in_closed_state(self):
        """Test recording failure in closed state."""
        breaker = CircuitBreaker("test-destination", CircuitBreakerConfig(failure_threshold=3))
        breaker.record_failure()
        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        """Test that circuit opens after failure threshold is reached."""
        breaker = CircuitBreaker("test-destination-opens", CircuitBreakerConfig(failure_threshold=3))

        # Record failures up to threshold
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_blocks_requests_when_open(self):
        """Test that requests are blocked when circuit is open."""
        breaker = CircuitBreaker("test-destination", CircuitBreakerConfig(failure_threshold=2))

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.allow_request() is False

    def test_transitions_to_half_open_after_timeout(self):
        """Test transition to HALF_OPEN after timeout."""
        breaker = CircuitBreaker(
            "test-destination",
            CircuitBreakerConfig(failure_threshold=2, timeout_seconds=0)
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Check if it transitions to half-open immediately (timeout=0)
        assert breaker.allow_request() is True
        assert breaker.state == CircuitState.HALF_OPEN

    def test_closes_after_success_threshold_in_half_open(self):
        """Test that circuit closes after success threshold in half-open."""
        breaker = CircuitBreaker(
            "test-destination",
            CircuitBreakerConfig(
                failure_threshold=2,
                success_threshold=2,
                timeout_seconds=0
            )
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Transition to half-open
        assert breaker.allow_request() is True
        assert breaker.state == CircuitState.HALF_OPEN

        # Record successes
        breaker.record_success()
        assert breaker.state == CircuitState.HALF_OPEN

        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_opens_on_failure_in_half_open(self):
        """Test that circuit opens on failure in half-open state."""
        breaker = CircuitBreaker(
            "test-destination",
            CircuitBreakerConfig(failure_threshold=2, timeout_seconds=0)
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Transition to half-open
        assert breaker.allow_request() is True
        assert breaker.state == CircuitState.HALF_OPEN

        # Record failure
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_half_open_max_calls_limit(self):
        """Test that half-open state has a max call limit."""
        breaker = CircuitBreaker(
            "test-destination-halfopen",
            CircuitBreakerConfig(failure_threshold=2, half_open_max_calls=2, timeout_seconds=0)
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Transition to half-open
        assert breaker.allow_request() is True
        assert breaker.state == CircuitState.HALF_OPEN

        # Use up half-open calls (record_success increments half_open_calls)
        assert breaker.allow_request() is True
        # Note: In half-open state, record_success increments half_open_calls before checking success_threshold
        # After 2 successes, the circuit should close
        breaker.record_success()
        assert breaker._state.half_open_calls == 1

        breaker.record_success()
        # After success_threshold (2) successes, circuit closes
        assert breaker.state == CircuitState.CLOSED
        assert breaker._state.half_open_calls == 0  # Reset on close

    def test_context_manager_success(self):
        """Test context manager records success."""
        breaker = CircuitBreaker("test-destination-context-success")

        with breaker:
            pass  # Simulate successful operation

        assert breaker.success_count == 1
        assert breaker.failure_count == 0

    def test_context_manager_failure(self):
        """Test context manager records failure."""
        breaker = CircuitBreaker("test-destination-context-fail", CircuitBreakerConfig(failure_threshold=3))

        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("Test error")

        assert breaker.failure_count == 1
        assert breaker.success_count == 0

    def test_context_manager_blocks_when_open(self):
        """Test context manager raises error when circuit is open."""
        breaker = CircuitBreaker(
            "test-destination",
            CircuitBreakerConfig(failure_threshold=2, timeout_seconds=10)
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        with pytest.raises(CircuitBreakerError) as exc_info:
            with breaker:
                pass

        assert "Circuit breaker is OPEN" in str(exc_info.value)

    def test_reset(self):
        """Test resetting circuit breaker."""
        breaker = CircuitBreaker("test-destination", CircuitBreakerConfig(failure_threshold=3))

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Reset
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0

    def test_get_stats(self):
        """Test getting circuit breaker statistics."""
        config = CircuitBreakerConfig(failure_threshold=5, timeout_seconds=60)
        breaker = CircuitBreaker("test-destination-stats", config)

        breaker.record_failure()
        breaker.record_success()

        stats = breaker.get_stats()

        assert stats["destination_id"] == "test-destination-stats"
        assert stats["state"] == CircuitState.CLOSED.value
        assert stats["failure_count"] == 0  # Reset to 0 after success
        assert stats["success_count"] == 1
        assert stats["config"]["failure_threshold"] == 5
        assert stats["config"]["timeout_seconds"] == 60

    def test_multiple_independent_breakers(self):
        """Test that multiple destinations have independent breakers."""
        breaker1 = CircuitBreaker("destination-1", CircuitBreakerConfig(failure_threshold=2))
        breaker2 = CircuitBreaker("destination-2", CircuitBreakerConfig(failure_threshold=2))

        # Open breaker1
        breaker1.record_failure()
        breaker1.record_failure()
        assert breaker1.state == CircuitState.OPEN

        # breaker2 should still be closed
        assert breaker2.state == CircuitState.CLOSED

    def test_get_all_breakers(self):
        """Test getting all circuit breakers."""
        CircuitBreaker.reset_all_breakers()

        breaker1 = CircuitBreaker("dest-1")
        breaker2 = CircuitBreaker("dest-2")

        breaker1.record_failure()

        all_breakers = CircuitBreaker.get_all_breakers()

        assert len(all_breakers) == 2
        assert "dest-1" in all_breakers
        assert "dest-2" in all_breakers

    def test_reset_all_breakers(self):
        """Test resetting all circuit breakers."""
        breaker1 = CircuitBreaker("dest-1", CircuitBreakerConfig(failure_threshold=2))
        breaker2 = CircuitBreaker("dest-2", CircuitBreakerConfig(failure_threshold=2))

        # Open both
        breaker1.record_failure()
        breaker1.record_failure()
        breaker2.record_failure()
        breaker2.record_failure()

        assert breaker1.state == CircuitState.OPEN
        assert breaker2.state == CircuitState.OPEN

        # Reset all
        count = CircuitBreaker.reset_all_breakers()
        assert count == 2

        # Create new instances to check
        new_breaker1 = CircuitBreaker("dest-1")
        new_breaker2 = CircuitBreaker("dest-2")

        assert new_breaker1.state == CircuitState.CLOSED
        assert new_breaker2.state == CircuitState.CLOSED

    def test_get_circuit_breaker_factory(self):
        """Test the factory function for getting circuit breakers."""
        breaker1 = get_circuit_breaker("factory-test", failure_threshold=3)
        breaker2 = get_circuit_breaker("factory-test", failure_threshold=5)

        # Should return the same breaker instance (shared state)
        assert breaker1.destination_id == breaker2.destination_id


class TestAsyncCircuitBreaker:
    """Tests for AsyncCircuitBreaker class."""

    @pytest.mark.asyncio
    async def test_async_context_manager_success(self):
        """Test async context manager records success."""
        breaker = AsyncCircuitBreaker("test-destination")

        async with breaker:
            pass  # Simulate successful async operation

        assert breaker.success_count == 1

    @pytest.mark.asyncio
    async def test_async_context_manager_failure(self):
        """Test async context manager records failure."""
        breaker = AsyncCircuitBreaker("test-destination")

        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Test error")

        assert breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_async_context_manager_blocks_when_open(self):
        """Test async context manager raises error when circuit is open."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout_seconds=10)
        breaker = AsyncCircuitBreaker("test-destination", config)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        with pytest.raises(CircuitBreakerError):
            async with breaker:
                pass
