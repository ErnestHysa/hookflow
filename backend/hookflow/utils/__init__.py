"""Utility modules for HookFlow."""

from hookflow.utils.retry import (
    RetryPolicy,
    calculate_backoff,
    calculate_backoff_with_retry_after,
    is_retryable_error,
    should_retry,
)
from hookflow.utils.signature import (
    WebhookSignatureError,
    DEFAULT_ALGORITHM,
    DEFAULT_TOLERANCE,
    generate_signature,
    generate_signature_headers,
    generate_webhook_secret,
    get_signature_algorithm_from_headers,
    verify_signature,
    verify_signature_from_headers,
    verify_webhook_request,
)
from hookflow.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    AsyncCircuitBreaker,
    get_circuit_breaker,
)
from hookflow.utils.observability import (
    WebhookMetrics,
    DestinationHealth,
    get_metrics,
)
from hookflow.utils.validation import (
    PayloadValidator,
    PayloadValidationError,
    PayloadTooLargeError,
    InvalidContentTypeError,
    InvalidJSONError,
    validate_webhook_payload,
    get_payload_stats,
)

__all__ = [
    # Retry
    "RetryPolicy",
    "calculate_backoff",
    "calculate_backoff_with_retry_after",
    "is_retryable_error",
    "should_retry",
    # Signature
    "WebhookSignatureError",
    "DEFAULT_ALGORITHM",
    "DEFAULT_TOLERANCE",
    "generate_signature",
    "generate_signature_headers",
    "generate_webhook_secret",
    "get_signature_algorithm_from_headers",
    "verify_signature",
    "verify_signature_from_headers",
    "verify_webhook_request",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitState",
    "AsyncCircuitBreaker",
    "get_circuit_breaker",
    # Observability
    "WebhookMetrics",
    "DestinationHealth",
    "get_metrics",
    # Validation
    "PayloadValidator",
    "PayloadValidationError",
    "PayloadTooLargeError",
    "InvalidContentTypeError",
    "InvalidJSONError",
    "validate_webhook_payload",
    "get_payload_stats",
]
