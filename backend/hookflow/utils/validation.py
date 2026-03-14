"""Payload validation utilities for webhook processing.

Validates webhook payload size, content type, and structure
before processing to prevent resource exhaustion.
"""

import json
from typing import Any

from hookflow.core.config import settings


class PayloadValidationError(Exception):
    """Raised when payload validation fails."""
    pass


class PayloadTooLargeError(PayloadValidationError):
    """Raised when payload exceeds size limit."""

    def __init__(self, size: int, limit: int):
        self.size = size
        self.limit = limit
        super().__init__(
            f"Payload size ({size} bytes) exceeds maximum allowed size ({limit} bytes)"
        )


class InvalidContentTypeError(PayloadValidationError):
    """Raised when content type is not supported."""

    def __init__(self, content_type: str):
        self.content_type = content_type
        super().__init__(
            f"Content type '{content_type}' is not supported. "
            f"Expected 'application/json' or 'text/plain'."
        )


class InvalidJSONError(PayloadValidationError):
    """Raised when payload cannot be parsed as JSON."""

    def __init__(self, detail: str):
        super().__init__(f"Invalid JSON payload: {detail}")


class PayloadValidator:
    """Validates webhook payloads before processing.

    Checks:
    - Payload size limits
    - Content type
    - JSON structure
    - Required fields (optional, per configuration)
    """

    # Default size limits (can be overridden per app)
    DEFAULT_MAX_SIZE = 10_000_000  # 10MB
    DEFAULT_MIN_SIZE = 1  # 1 byte

    # Allowed content types
    ALLOWED_CONTENT_TYPES = {
        "application/json",
        "application/json; charset=utf-8",
        "text/plain",
        "text/plain; charset=utf-8",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    }

    def __init__(
        self,
        max_size: int | None = None,
        min_size: int | None = None,
        require_json: bool = True,
    ):
        """Initialize payload validator.

        Args:
            max_size: Maximum payload size in bytes
            min_size: Minimum payload size in bytes
            require_json: Whether payload must be valid JSON
        """
        self.max_size = max_size or self.DEFAULT_MAX_SIZE
        self.min_size = min_size or self.DEFAULT_MIN_SIZE
        self.require_json = require_json

    def validate_size(self, payload: bytes | str, content_length: int | None = None) -> int:
        """Validate payload size.

        Args:
            payload: The payload data
            content_length: Content-Length header value if available

        Returns:
            Actual payload size in bytes

        Raises:
            PayloadTooLargeError: If payload exceeds size limit
        """
        # Use content-length if available (more efficient for large payloads)
        if content_length is not None:
            size = content_length
        else:
            size = len(payload) if isinstance(payload, (str, bytes)) else 0

        if size > self.max_size:
            raise PayloadTooLargeError(size, self.max_size)

        if size < self.min_size:
            raise PayloadValidationError(
                f"Payload size ({size} bytes) is below minimum required ({self.min_size} bytes)"
            )

        return size

    def validate_content_type(self, content_type: str | None) -> None:
        """Validate content type.

        Args:
            content_type: Content-Type header value

        Raises:
            InvalidContentTypeError: If content type is not allowed
        """
        if not content_type:
            if self.require_json:
                raise InvalidContentTypeError("missing")
            return

        # Normalize content type
        content_type_normalized = content_type.strip().lower()

        # Check if allowed
        # For JSON, we allow various charset encodings
        if "application/json" in content_type_normalized:
            return

        # For exact match
        if content_type_normalized in [ct.lower() for ct in self.ALLOWED_CONTENT_TYPES]:
            return

        # If we require JSON and didn't get it
        if self.require_json and "application/json" not in content_type_normalized:
            raise InvalidContentTypeError(content_type)

    def validate_json(self, payload: bytes | str) -> dict[str, Any]:
        """Validate and parse JSON payload.

        Args:
            payload: The payload data

        Returns:
            Parsed JSON as dictionary

        Raises:
            InvalidJSONError: If payload is not valid JSON
        """
        if isinstance(payload, dict):
            return payload

        if isinstance(payload, bytes):
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError as e:
                raise InvalidJSONError(f"Invalid UTF-8 encoding: {e}")
        else:
            text = payload

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise InvalidJSONError(f"Syntax error at line {e.lineno}, column {e.colno}: {e.msg}")

        if not isinstance(data, dict):
            raise InvalidJSONError("Payload must be a JSON object (dictionary)")

        return data

    def validate(
        self,
        payload: bytes | str | dict[str, Any],
        content_type: str | None = None,
        content_length: int | None = None,
    ) -> dict[str, Any]:
        """Perform all validations on a payload.

        Args:
            payload: The payload data
            content_type: Content-Type header value
            content_length: Content-Length header value

        Returns:
            Validated and parsed payload as dictionary

        Raises:
            PayloadValidationError: If validation fails
        """
        # Validate size
        if isinstance(payload, dict):
            # For dict payloads, estimate size from JSON
            json_str = json.dumps(payload)
            size = len(json_str.encode("utf-8"))
            if size > self.max_size:
                raise PayloadTooLargeError(size, self.max_size)
            parsed = payload
        else:
            size = self.validate_size(payload, content_length)

            # Validate content type
            if self.require_json or content_type:
                self.validate_content_type(content_type)

            # Parse JSON
            if self.require_json:
                parsed = self.validate_json(payload)
            else:
                parsed = {"data": payload}

        return parsed

    def validate_request(
        self,
        body: bytes | str,
        content_type: str | None = None,
        content_length: str | None = None,
    ) -> dict[str, Any]:
        """Validate a webhook request (FastAPI compatible).

        Args:
            body: Raw request body
            content_type: Content-Type header value
            content_length: Content-Length header value as string

        Returns:
            Validated and parsed payload

        Raises:
            PayloadValidationError: If validation fails
        """
        # Parse content length
        length = None
        if content_length:
            try:
                length = int(content_length)
            except ValueError:
                pass

        return self.validate(body, content_type, length)


# Convenience functions
def validate_webhook_payload(
    payload: bytes | str | dict[str, Any],
    content_type: str | None = None,
    max_size: int | None = None,
) -> dict[str, Any]:
    """Validate a webhook payload with default settings.

    Args:
        payload: The payload data
        content_type: Content-Type header value
        max_size: Maximum size in bytes (uses default if None)

    Returns:
        Validated and parsed payload

    Raises:
        PayloadValidationError: If validation fails
    """
    validator = PayloadValidator(max_size=max_size)
    return validator.validate(payload, content_type)


def check_rate_limit_size(
    current_size: int,
    app_max_size: int | None = None,
) -> bool:
    """Check if payload size is within app-specific limits.

    Args:
        current_size: Current payload size in bytes
        app_max_size: App-specific maximum, or None for default

    Returns:
        True if size is acceptable
    """
    limit = app_max_size or PayloadValidator.DEFAULT_MAX_SIZE
    return current_size <= limit


def get_payload_stats(payload: dict[str, Any] | bytes | str) -> dict[str, Any]:
    """Get statistics about a payload.

    Args:
        payload: The payload data

    Returns:
        Dictionary with payload statistics
    """
    if isinstance(payload, dict):
        json_str = json.dumps(payload)
        size_bytes = len(json_str.encode("utf-8"))
        size_json = len(json_str)
    elif isinstance(payload, bytes):
        size_bytes = len(payload)
        size_json = len(payload)  # Approximate
        json_str = payload.decode("utf-8", errors="ignore")
    else:
        size_bytes = len(payload.encode("utf-8"))
        size_json = len(payload)
        json_str = payload

    # Try to count keys if it's JSON
    key_count = None
    depth = None
    try:
        if isinstance(payload, dict):
            data = payload
        else:
            data = json.loads(json_str)

        if isinstance(data, dict):
            key_count = len(data)
            depth = _calculate_depth(data)
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "size_bytes": size_bytes,
        "size_json": size_json,
        "key_count": key_count,
        "depth": depth,
    }


def _calculate_depth(data: Any, current_depth: int = 0) -> int:
    """Calculate maximum nesting depth of a structure.

    Args:
        data: The data to analyze
        current_depth: Current depth level

    Returns:
        Maximum depth
    """
    if not isinstance(data, (dict, list)):
        return current_depth

    if isinstance(data, list):
        if not data:
            return current_depth
        return max(_calculate_depth(item, current_depth + 1) for item in data)

    # dict
    if not data:
        return current_depth
    return max(_calculate_depth(value, current_depth + 1) for value in data.values())
