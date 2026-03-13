"""Webhook signature utilities for HMAC signing."""

import hashlib
import hmac
import time
from typing import Literal

from hookflow.core.config import settings


class WebhookSignatureError(Exception):
    """Error raised when webhook signature verification fails."""

    pass


def generate_signature(
    payload: bytes | str,
    secret: str,
    algorithm: Literal["sha256", "sha512"] = "sha256",
) -> str:
    """Generate HMAC signature for webhook payload.

    Args:
        payload: The webhook payload (bytes or string)
        secret: The webhook secret key
        algorithm: Hash algorithm to use (sha256 or sha512)

    Returns:
        Hex-encoded HMAC signature

    Raises:
        ValueError: If algorithm is not supported
    """
    if algorithm not in ("sha256", "sha512"):
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    # Use the constructor directly, not an instance
    if algorithm == "sha256":
        signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    elif algorithm == "sha512":
        signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha512)
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    return signature.hexdigest()


def generate_signature_headers(
    payload: bytes | str,
    secret: str,
    algorithm: Literal["sha256", "sha512"] = "sha256",
) -> dict[str, str]:
    """Generate signature headers for webhook delivery.

    Args:
        payload: The webhook payload
        secret: The webhook secret key
        algorithm: Hash algorithm to use

    Returns:
        Dictionary with timestamp and signature headers
    """
    timestamp = str(int(time.time()))
    signature = generate_signature(payload, secret, algorithm)

    return {
        "X-Webhook-Id": f"wh_{int(time.time() * 1000)}_{hash(payload) % 1000000:06d}",
        "X-Webhook-Timestamp": timestamp,
        f"X-Webhook-Signature-{algorithm}": signature,
        "X-Webhook-Signature": f"t={timestamp},v1={signature}",
    }


def verify_signature(
    payload: bytes | str,
    signature: str,
    timestamp: str | int,
    secret: str,
    algorithm: Literal["sha256", "sha512"] = "sha256",
    tolerance: int = 300,
) -> bool:
    """Verify webhook signature.

    Args:
        payload: The webhook payload
        signature: The signature from X-Webhook-Signature header
        timestamp: The timestamp from X-Webhook-Timestamp header
        secret: The webhook secret key
        algorithm: Hash algorithm used
        tolerance: Maximum allowed timestamp difference in seconds (default: 5min)

    Returns:
        True if signature is valid

    Raises:
        WebhookSignatureError: If signature verification fails
    """
    try:
        # Check timestamp freshness
        current_time = int(time.time())
        try:
            msg_time = int(timestamp)
        except (ValueError, TypeError):
            raise WebhookSignatureError("Invalid timestamp format")

        time_diff = abs(current_time - msg_time)
        if time_diff > tolerance:
            raise WebhookSignatureError(
                f"Timestamp too old or too far in the future (diff: {time_diff}s, tolerance: {tolerance}s)"
            )

        # Parse signature header (supports multiple formats)
        if "," in signature:
            # Svix-style format: t=123456,v1=abc123...
            parts = {}
            for part in signature.split(","):
                key, value = part.split("=", 1)
                parts[key] = value

            if "v1" not in parts:
                raise WebhookSignatureError("Invalid signature format")

            provided_signature = parts["v1"]
        elif "=" in signature:
            # GitHub-style format: sha256=abc123... or sha1=abc123...
            # Extract the signature part after the algorithm name
            algorithm_name, provided_signature = signature.split("=", 1)
            # Validate the algorithm prefix is one we expect
            if algorithm_name not in ("sha1", "sha256", "sha512"):
                raise WebhookSignatureError(f"Unsupported signature algorithm: {algorithm_name}")
        else:
            # Simple signature format (just the hex signature)
            provided_signature = signature

        # Generate expected signature
        expected_signature = generate_signature(payload, secret, algorithm)

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise WebhookSignatureError("Signature verification failed: signatures do not match")

        return True

    except WebhookSignatureError:
        raise
    except Exception as e:
        raise WebhookSignatureError(f"Signature verification failed: {e}") from e


def verify_signature_from_headers(
    payload: bytes | str,
    headers: dict[str, str],
    secret: str,
    algorithm: Literal["sha256", "sha512"] = "sha256",
    tolerance: int = 300,
) -> bool:
    """Verify webhook signature from headers dictionary.

    Args:
        payload: The webhook payload
        headers: Dictionary of HTTP headers
        secret: The webhook secret key
        algorithm: Hash algorithm used
        tolerance: Maximum allowed timestamp difference

    Returns:
        True if signature is valid

    Raises:
        WebhookSignatureError: If signature verification fails
    """
    # Try multiple header formats
    signature_header = (
        headers.get("X-Webhook-Signature") or
        headers.get("x-webhook-signature") or
        headers.get("webhook-signature") or
        headers.get("X-Hub-Signature-256") or  # GitHub style
        ""
    )

    if not signature_header:
        raise WebhookSignatureError("Missing signature header")

    timestamp_header = (
        headers.get("X-Webhook-Timestamp") or
        headers.get("x-webhook-timestamp") or
        headers.get("X-Hub-Signature-256-timestamp") or  # GitHub style
        ""
    )

    # If no timestamp header, check if signature contains it
    if not timestamp_header and "," in signature_header:
        # Extract timestamp from t=... part
        for part in signature_header.split(","):
            if part.startswith("t="):
                timestamp_header = part[2:]
                break

    return verify_signature(
        payload,
        signature_header,
        timestamp_header,
        secret,
        algorithm,
        tolerance,
    )


def generate_webhook_secret() -> str:
    """Generate a secure random webhook secret.

    Returns:
        Base64-encoded random secret key
    """
    import secrets
    import base64

    random_bytes = secrets.token_bytes(32)
    return base64.b64encode(random_bytes).decode("utf-8")


def verify_webhook_request(
    payload: bytes | str,
    headers: dict[str, str],
    app_secret: str,
) -> dict[str, bool | str]:
    """Verify a webhook request and return verification result.

    Args:
        payload: The webhook payload
        headers: Request headers
        app_secret: The app's webhook secret

    Returns:
        Dictionary with verification status and details
    """
    try:
        verify_signature_from_headers(payload, headers, app_secret)
        return {
            "valid": True,
            "message": "Signature verified",
        }
    except WebhookSignatureError as e:
        return {
            "valid": False,
            "message": str(e),
        }


# Signature algorithm constants
DEFAULT_ALGORITHM = "sha256"
DEFAULT_TOLERANCE = 300  # 5 minutes


def get_signature_algorithm_from_headers(headers: dict[str, str]) -> str:
    """Extract signature algorithm from headers.

    Args:
        headers: Request headers

    Returns:
        Algorithm name (sha256 or sha512)
    """
    # Check for algorithm-specific header
    if headers.get("X-Webhook-Signature-Sha512"):
        return "sha512"
    if headers.get("X-Webhook-Signature-Sha256"):
        return "sha256"

    return DEFAULT_ALGORITHM
