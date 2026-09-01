import hashlib
import hmac
from typing import Optional
from fastapi import HTTPException, status


def generate_webhook_signature(payload: bytes, app_secret: str) -> str:
    """
    Computes Meta-compliant HMAC-SHA256 signature formatted as 'sha256=<hex_digest>'.
    Used for webhook testing and signature generation.
    """
    digest = hmac.new(
        app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def verify_webhook_signature(
    payload: bytes,
    signature_header: Optional[str],
    app_secret: Optional[str],
) -> bool:
    """
    Validates incoming Meta X-Hub-Signature-256 header against the raw request payload bytes.
    Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.

    Args:
        payload: Exact raw request body bytes.
        signature_header: Content of 'X-Hub-Signature-256' header (e.g. 'sha256=abcdef123...').
        app_secret: Server-configured Meta WHATSAPP_APP_SECRET.

    Returns:
        True if the signature matches, False otherwise.

    Raises:
        HTTPException(500) if WHATSAPP_APP_SECRET is not configured on the server.
    """
    if not app_secret or not app_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WhatsApp Webhook verification failed due to missing server configuration.",
        )

    if not signature_header or not signature_header.strip():
        return False

    parts = signature_header.strip().split("=", 1)
    if len(parts) != 2 or parts[0] != "sha256":
        return False

    received_digest = parts[1].strip()
    # A standard SHA256 hex digest is exactly 64 hex characters
    if len(received_digest) != 64:
        return False

    try:
        # Validate that received_digest is valid hex characters
        int(received_digest, 16)
    except ValueError:
        return False

    expected_digest = hmac.new(
        app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_digest, received_digest)

