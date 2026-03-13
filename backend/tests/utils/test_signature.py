"""Tests for webhook signature verification."""

import pytest

from hookflow.utils.signature import (
    WebhookSignatureError,
    generate_signature,
    generate_signature_headers,
    generate_webhook_secret,
    verify_signature,
    verify_signature_from_headers,
)


class TestGenerateSignature:
    """Tests for generate_signature function."""

    def test_generate_signature_sha256(self):
        """Test generating SHA256 HMAC signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        signature = generate_signature(payload, secret, "sha256")

        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 produces 64 hex chars

    def test_generate_signature_sha512(self):
        """Test generating SHA512 HMAC signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        signature = generate_signature(payload, secret, "sha512")

        assert isinstance(signature, str)
        assert len(signature) == 128  # SHA512 produces 128 hex chars

    def test_generate_signature_string_payload(self):
        """Test signature generation with string payload."""
        payload = "test payload"
        secret = "secret"

        signature = generate_signature(payload, secret)
        assert isinstance(signature, str)

    def test_generate_signature_is_deterministic(self):
        """Test that signature generation is deterministic."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        sig1 = generate_signature(payload, secret)
        sig2 = generate_signature(payload, secret)

        assert sig1 == sig2

    def test_generate_signature_different_payloads(self):
        """Test that different payloads produce different signatures."""
        secret = "test_secret"

        sig1 = generate_signature("payload1", secret)
        sig2 = generate_signature("payload2", secret)

        assert sig1 != sig2


class TestGenerateSignatureHeaders:
    """Tests for generate_signature_headers function."""

    def test_generate_signature_headers(self):
        """Test generating signature headers."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        headers = generate_signature_headers(payload, secret)

        assert "X-Webhook-Timestamp" in headers
        assert "X-Webhook-Signature" in headers
        assert "X-Webhook-Signature-sha256" in headers
        assert "X-Webhook-Id" in headers

    def test_signature_header_format(self):
        """Test signature header format matches industry standard."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        headers = generate_signature_headers(payload, secret)

        # Check standard Svix-style format: t=timestamp,v1=signature
        signature = headers["X-Webhook-Signature"]
        assert signature.startswith("t=")
        assert ",v1=" in signature


class TestVerifySignature:
    """Tests for verify_signature function."""

    def test_verify_valid_signature(self):
        """Test verifying a valid signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        # Generate signature
        signature = generate_signature(payload, secret)
        timestamp = "1234567890"

        # Verify (within tolerance)
        result = verify_signature(
            payload,
            f"t={timestamp},v1={signature}",
            timestamp,
            secret,
            tolerance=999999999,  # Large tolerance for test
        )

        assert result is True

    def test_verify_invalid_signature(self):
        """Test verifying an invalid signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        with pytest.raises(WebhookSignatureError):
            verify_signature(
                payload,
                "t=1234567890,v1=invalid",
                "1234567890",
                secret,
                tolerance=999999999,
            )

    def test_verify_expired_timestamp(self):
        """Test that expired timestamps are rejected."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        signature = generate_signature(payload, secret)
        # Old timestamp (more than tolerance)
        old_timestamp = "1000000000"  # Year 2001

        with pytest.raises(WebhookSignatureError, match="too old"):
            verify_signature(
                payload,
                f"t={old_timestamp},v1={signature}",
                old_timestamp,
                secret,
                tolerance=300,  # 5 minutes
            )

    def test_verify_future_timestamp(self):
        """Test that future timestamps are rejected."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        signature = generate_signature(payload, secret)
        # Future timestamp (more than tolerance)
        future_timestamp = "9999999999"  # Year 2286

        with pytest.raises(WebhookSignatureError, match="too far in the future"):
            verify_signature(
                payload,
                f"t={future_timestamp},v1={signature}",
                future_timestamp,
                secret,
                tolerance=300,
            )

    def test_verify_simple_signature_format(self):
        """Test verifying simple signature format (no t= prefix)."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        signature = generate_signature(payload, secret)
        timestamp = "1234567890"

        # Simple format (just the signature)
        result = verify_signature(
            payload,
            signature,
            timestamp,
            secret,
            tolerance=999999999,
        )

        assert result is True


class TestVerifySignatureFromHeaders:
    """Tests for verify_signature_from_headers function."""

    def test_verify_from_headers_standard_format(self):
        """Test verification with standard headers."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        headers = generate_signature_headers(payload, secret)

        result = verify_signature_from_headers(
            payload,
            headers,
            secret,
            tolerance=999999999,
        )

        assert result is True

    def test_verify_from_headers_case_insensitive(self):
        """Test that header names are case-insensitive."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        headers = generate_signature_headers(payload, secret)
        # Convert to lowercase
        lowercase_headers = {k.lower(): v for k, v in headers.items()}

        result = verify_signature_from_headers(
            payload,
            lowercase_headers,
            secret,
            tolerance=999999999,
        )

        assert result is True

    def test_verify_from_headers_missing_signature(self):
        """Test verification with missing signature header."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        headers = {"X-Webhook-Timestamp": "1234567890"}

        with pytest.raises(WebhookSignatureError, match="Missing signature"):
            verify_signature_from_headers(payload, headers, secret)

    def test_verify_from_headers_github_style(self):
        """Test verification with GitHub-style headers."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        signature = generate_signature(payload, secret)
        timestamp = "1234567890"

        headers = {
            "X-Hub-Signature-256": f"sha256={signature}",
            "X-Hub-Signature-256-timestamp": timestamp,
        }

        result = verify_signature_from_headers(
            payload,
            headers,
            secret,
            tolerance=999999999,
        )

        assert result is True


class TestGenerateWebhookSecret:
    """Tests for generate_webhook_secret function."""

    def test_generate_secret_length(self):
        """Test that generated secret has reasonable length."""
        secret = generate_webhook_secret()

        # Base64 of 32 bytes should be 44 chars
        assert len(secret) == 44

    def test_generate_secret_is_different(self):
        """Test that each call generates a different secret."""
        secret1 = generate_webhook_secret()
        secret2 = generate_webhook_secret()

        assert secret1 != secret2


class TestVerifyWebhookRequest:
    """Tests for verify_webhook_request function."""

    def test_verify_valid_request(self):
        """Test verifying a valid webhook request."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        headers = generate_signature_headers(payload, secret)

        result = verify_signature_from_headers(
            payload,
            headers,
            secret,
            tolerance=999999999,
        )

        assert result is True

    def test_verify_invalid_request(self):
        """Test verifying an invalid webhook request."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        headers = {
            "X-Webhook-Signature": "t=1234567890,v1=badsignature",
            "X-Webhook-Timestamp": "1234567890",
        }

        with pytest.raises(WebhookSignatureError):
            verify_signature_from_headers(
                payload,
                headers,
                secret,
                tolerance=999999999,
            )
