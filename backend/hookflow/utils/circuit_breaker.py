"""Circuit breaker pattern for preventing cascade failures.

The circuit breaker pattern prevents cascade failures by stopping requests
to a service that is repeatedly failing. After a threshold of failures,
the circuit "opens" and requests are blocked for a cooldown period.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Circuit is tripped, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5      # Number of failures before opening
    success_threshold: int = 2      # Number of successes to close after half-open
    timeout_seconds: int = 60       # How long to stay open before half-open
    half_open_max_calls: int = 3    # Max calls allowed in half-open state


@dataclass
class CircuitBreakerState:
    """Current state of a circuit breaker."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float | None = None
    last_state_change: float = field(default_factory=time.time)
    half_open_calls: int = 0


class CircuitBreakerError(Exception):
    """Raised when circuit is open and request is rejected."""
    pass


class CircuitBreaker:
    """Circuit breaker implementation for preventing cascade failures.

    The circuit breaker has three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is tripped, requests are blocked
    - HALF_OPEN: Testing if service has recovered

    State transitions:
    - CLOSED → OPEN: After failure_threshold consecutive failures
    - OPEN → HALF_OPEN: After timeout_seconds have passed
    - HALF_OPEN → CLOSED: After success_threshold consecutive successes
    - HALF_OPEN → OPEN: On any failure or after half_open_max_calls without success

    Usage:
        breaker = CircuitBreaker("api-destination", failure_threshold=5, timeout_seconds=60)

        try:
            with breaker:
                result = await make_request()
        except CircuitBreakerError:
            # Circuit is open, request rejected
            handle_open_circuit()
        except Exception:
            # Request failed, breaker will record failure
            raise
    """

    # Class-level storage for circuit breaker states (shared across instances)
    # In production, use Redis or similar for distributed systems
    _breakers: dict[str, CircuitBreakerState] = {}

    def __init__(
        self,
        destination_id: str,
        config: CircuitBreakerConfig | None = None,
    ):
        """Initialize circuit breaker for a destination.

        Args:
            destination_id: Unique identifier for the destination (e.g., URL or ID)
            config: Circuit breaker configuration, uses defaults if None
        """
        self.destination_id = destination_id
        self.config = config or CircuitBreakerConfig()

        # Get or create state for this destination
        if destination_id not in self._breakers:
            self._breakers[destination_id] = CircuitBreakerState()
        self._state = self._breakers[destination_id]

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state.state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._state.failure_count

    @property
    def success_count(self) -> int:
        """Get current success count."""
        return self._state.success_count

    def is_open(self) -> bool:
        """Check if circuit is currently open."""
        if self._state.state == CircuitState.OPEN:
            # Check if we should transition to half-open
            if time.time() - self._state.last_state_change >= self.config.timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
                return False
            return True
        return False

    def allow_request(self) -> bool:
        """Check if a request should be allowed through the circuit.

        Returns:
            True if request is allowed, False if circuit is open
        """
        state = self._state.state

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            # Check if timeout has passed
            if time.time() - self._state.last_state_change >= self.config.timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False

        if state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open state for testing
            return self._state.half_open_calls < self.config.half_open_max_calls

        return False

    def record_success(self) -> None:
        """Record a successful request."""
        state = self._state.state

        if state == CircuitState.CLOSED:
            # Reset failure count on success in closed state
            self._state.failure_count = 0
            self._state.success_count += 1

        elif state == CircuitState.HALF_OPEN:
            self._state.success_count += 1
            self._state.half_open_calls += 1

            # Check if we should close the circuit
            if self._state.success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

        elif state == CircuitState.OPEN:
            # Shouldn't happen, but handle gracefully
            pass

    def record_failure(self, error: Exception | None = None) -> None:
        """Record a failed request.

        Args:
            error: The exception that caused the failure
        """
        self._state.last_failure_time = time.time()
        self._state.failure_count += 1
        self._state.success_count = 0

        state = self._state.state

        if state == CircuitState.CLOSED:
            # Check if we should open the circuit
            if self._state.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)

        elif state == CircuitState.HALF_OPEN:
            # Any failure in half-open opens the circuit immediately
            self._transition_to(CircuitState.OPEN)

        # OPEN state remains OPEN

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state.

        Args:
            new_state: The state to transition to
        """
        old_state = self._state.state
        self._state.state = new_state
        self._state.last_state_change = time.time()

        # Reset counters on state transitions
        if new_state == CircuitState.CLOSED:
            self._state.failure_count = 0
            self._state.success_count = 0
            self._state.half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._state.success_count = 0
            self._state.half_open_calls = 0
        elif new_state == CircuitState.OPEN:
            self._state.half_open_calls = 0

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self._transition_to(CircuitState.CLOSED)

    def get_stats(self) -> dict[str, Any]:
        """Get current circuit breaker statistics.

        Returns:
            Dictionary with current state and counts
        """
        return {
            "destination_id": self.destination_id,
            "state": self._state.state.value,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "last_failure_time": self._state.last_failure_time,
            "last_state_change": self._state.last_state_change,
            "half_open_calls": self._state.half_open_calls,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout_seconds,
                "half_open_max_calls": self.config.half_open_max_calls,
            },
        }

    def __enter__(self) -> "CircuitBreaker":
        """Context manager entry - check if request is allowed."""
        if not self.allow_request():
            raise CircuitBreakerError(
                f"Circuit breaker is OPEN for destination '{self.destination_id}'. "
                f"Rejecting request to prevent cascade failure."
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - record success or failure."""
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure(exc_val)

    @classmethod
    def get_all_breakers(cls) -> dict[str, dict[str, Any]]:
        """Get statistics for all circuit breakers.

        Returns:
            Dictionary mapping destination IDs to their stats
        """
        return {
            dest_id: CircuitBreaker(dest_id).get_stats()
            for dest_id in cls._breakers.keys()
        }

    @classmethod
    def reset_breaker(cls, destination_id: str) -> bool:
        """Reset a specific circuit breaker.

        Args:
            destination_id: The destination ID to reset

        Returns:
            True if breaker was found and reset, False otherwise
        """
        if destination_id in cls._breakers:
            cls._breakers[destination_id] = CircuitBreakerState()
            return True
        return False

    @classmethod
    def reset_all_breakers(cls) -> int:
        """Reset all circuit breakers.

        Returns:
            Number of breakers reset
        """
        count = len(cls._breakers)
        cls._breakers.clear()
        return count


# Destination-specific circuit breaker factory
def get_circuit_breaker(
    destination_id: str,
    failure_threshold: int = 5,
    timeout_seconds: int = 60,
) -> CircuitBreaker:
    """Get or create a circuit breaker for a destination.

    Args:
        destination_id: Unique identifier for the destination
        failure_threshold: Number of failures before opening circuit
        timeout_seconds: How long to stay open before testing recovery

    Returns:
        CircuitBreaker instance for the destination
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        timeout_seconds=timeout_seconds,
    )
    return CircuitBreaker(destination_id, config)


# Async context manager for use with async functions
class AsyncCircuitBreaker(CircuitBreaker):
    """Async version of circuit breaker for use with async functions."""

    async def __aenter__(self) -> "AsyncCircuitBreaker":
        """Async context manager entry."""
        if not self.allow_request():
            raise CircuitBreakerError(
                f"Circuit breaker is OPEN for destination '{self.destination_id}'. "
                f"Rejecting request to prevent cascade failure."
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure(exc_val)
