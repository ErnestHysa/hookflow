"""Tests for payload validation utilities."""

import pytest

from hookflow.utils.validation import (
    PayloadValidator,
    PayloadValidationError,
    PayloadTooLargeError,
    InvalidContentTypeError,
    InvalidJSONError,
    validate_webhook_payload,
    get_payload_stats,
)


class TestPayloadValidator:
    """Tests for PayloadValidator class."""

    def test_default_max_size(self):
        """Test default max size is 10MB."""
        validator = PayloadValidator()
        assert validator.max_size == 10_000_000

    def test_custom_max_size(self):
        """Test custom max size."""
        validator = PayloadValidator(max_size=1000)
        assert validator.max_size == 1000

    def test_validate_size_within_limits(self):
        """Test size validation for payloads within limits."""
        validator = PayloadValidator(max_size=1000)
        payload = b"x" * 500

        size = validator.validate_size(payload)
        assert size == 500

    def test_validate_size_exceeds_max(self):
        """Test size validation rejects oversized payloads."""
        validator = PayloadValidator(max_size=100)
        payload = b"x" * 200

        with pytest.raises(PayloadTooLargeError) as exc_info:
            validator.validate_size(payload)

        assert exc_info.value.size == 200
        assert exc_info.value.limit == 100

    def test_validate_size_below_min(self):
        """Test size validation rejects undersized payloads."""
        validator = PayloadValidator(min_size=10)
        payload = b"x" * 5

        with pytest.raises(PayloadValidationError) as exc_info:
            validator.validate_size(payload)

        assert "below minimum" in str(exc_info.value)

    def test_validate_content_type_json_allowed(self):
        """Test that JSON content type is allowed."""
        validator = PayloadValidator()
        validator.validate_content_type("application/json")  # Should not raise

    def test_validate_content_type_json_with_charset(self):
        """Test that JSON with charset is allowed."""
        validator = PayloadValidator()
        validator.validate_content_type("application/json; charset=utf-8")

    def test_validate_content_type_invalid(self):
        """Test that invalid content types are rejected."""
        validator = PayloadValidator(require_json=True)

        with pytest.raises(InvalidContentTypeError):
            validator.validate_content_type("text/html")

    def test_validate_content_type_missing_when_required(self):
        """Test that missing content type is rejected when required."""
        validator = PayloadValidator(require_json=True)

        with pytest.raises(InvalidContentTypeError) as exc_info:
            validator.validate_content_type(None)

        assert "missing" in str(exc_info.value)

    def test_validate_json_valid(self):
        """Test validation of valid JSON."""
        validator = PayloadValidator()
        payload = '{"key": "value"}'

        result = validator.validate_json(payload)
        assert result == {"key": "value"}

    def test_validate_json_invalid_syntax(self):
        """Test validation of invalid JSON syntax."""
        validator = PayloadValidator()
        payload = '{"key": invalid}'

        with pytest.raises(InvalidJSONError):
            validator.validate_json(payload)

    def test_validate_json_not_object(self):
        """Test validation rejects JSON that is not an object."""
        validator = PayloadValidator()
        payload = '["array", "values"]'

        with pytest.raises(InvalidJSONError) as exc_info:
            validator.validate_json(payload)

        assert "must be a JSON object" in str(exc_info.value)

    def test_validate_json_bytes(self):
        """Test JSON validation from bytes."""
        validator = PayloadValidator()
        payload = b'{"key": "value"}'

        result = validator.validate_json(payload)
        assert result == {"key": "value"}

    def test_validate_full_success(self):
        """Test full validation pipeline with valid payload."""
        validator = PayloadValidator(max_size=1000)
        payload = '{"test": "data"}'

        result = validator.validate(payload, "application/json")
        assert result == {"test": "data"}

    def test_validate_dict_payload(self):
        """Test validation with dict input."""
        validator = PayloadValidator(max_size=1000)
        payload = {"test": "data"}

        result = validator.validate(payload)
        assert result == {"test": "data"}

    def test_validate_dict_payload_too_large(self):
        """Test that dict payloads are size-checked."""
        validator = PayloadValidator(max_size=10)

        # Create a dict that's larger than 10 bytes when serialized
        payload = {"x": "y" * 50}

        with pytest.raises(PayloadTooLargeError):
            validator.validate(payload)


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_validate_webhook_payload(self):
        """Test validate_webhook_payload function."""
        payload = '{"test": "value"}'

        result = validate_webhook_payload(payload, "application/json")
        assert result == {"test": "value"}

    def test_validate_webhook_payload_with_max_size(self):
        """Test validate_webhook_payload with custom max size."""
        payload = b"x" * 200

        with pytest.raises(PayloadTooLargeError):
            validate_webhook_payload(payload, max_size=100)


class TestGetPayloadStats:
    """Tests for get_payload_stats function."""

    def test_stats_for_dict(self):
        """Test getting stats for dict payload."""
        payload = {"key1": "value1", "key2": "value2"}

        stats = get_payload_stats(payload)

        assert stats["size_bytes"] > 0
        assert stats["size_json"] > 0
        assert stats["key_count"] == 2
        assert stats["depth"] >= 1

    def test_stats_for_bytes(self):
        """Test getting stats for bytes payload."""
        payload = b'{"test": "data"}'

        stats = get_payload_stats(payload)

        assert stats["size_bytes"] == len(payload)
        assert stats["size_json"] == len(payload)

    def test_stats_for_string(self):
        """Test getting stats for string payload."""
        payload = '{"test": "data"}'

        stats = get_payload_stats(payload)

        assert stats["size_bytes"] > 0
        assert stats["size_json"] == len(payload)

    def test_stats_calculates_depth(self):
        """Test that depth is calculated correctly."""
        payload = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }

        stats = get_payload_stats(payload)

        assert stats["depth"] == 3

    def test_stats_handles_invalid_json(self):
        """Test that invalid JSON doesn't crash stats."""
        payload = "not valid json"

        stats = get_payload_stats(payload)

        assert stats["size_bytes"] > 0
        assert stats["key_count"] is None  # Can't parse


class TestCalculateDepth:
    """Tests for _calculate_depth helper function."""

    def test_depth_flat_dict(self):
        """Test depth calculation for flat dict."""
        from hookflow.utils.validation import _calculate_depth

        assert _calculate_depth({"a": 1, "b": 2}) == 1

    def test_depth_nested_dict(self):
        """Test depth calculation for nested dict."""
        from hookflow.utils.validation import _calculate_depth

        assert _calculate_depth({"a": {"b": {"c": 1}}}) == 3

    def test_depth_with_list(self):
        """Test depth calculation with lists."""
        from hookflow.utils.validation import _calculate_depth

        assert _calculate_depth({"a": [1, 2, 3]}) == 2

    def test_depth_with_nested_list(self):
        """Test depth calculation with nested lists."""
        from hookflow.utils.validation import _calculate_depth

        assert _calculate_depth({"a": [{"b": 1}]}) == 3

    def test_depth_empty_structures(self):
        """Test depth calculation for empty structures."""
        from hookflow.utils.validation import _calculate_depth

        assert _calculate_depth({}) == 0
        assert _calculate_depth([]) == 0

    def test_depth_mixed_structure(self):
        """Test depth calculation for mixed structures."""
        from hookflow.utils.validation import _calculate_depth

        data = {
            "users": [
                {"name": "Alice", "profile": {"age": 30}},
                {"name": "Bob", "profile": {"age": 25}}
            ],
            "metadata": {"count": 2}
        }

        # Depth is: metadata:1, users:1, list items:1, profile:2, age:3
        # Max is 3 (metadata -> count)
        # Or users -> list -> profile -> age = 4
        # The actual max depth is 4
        assert _calculate_depth(data) == 4
