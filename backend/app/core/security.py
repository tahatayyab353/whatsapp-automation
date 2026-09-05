import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
import jwt

from app.core.config import settings
from app.core.exceptions import BadRequestException, AppException

# Initialize Argon2id password hasher
ph = PasswordHasher()


def validate_password_strength(password: str) -> None:
    """
    Validates minimum password requirements before hashing.
    Enforces minimum 8 characters.
    """
    if not password or len(password) < 8:
        raise BadRequestException("Password must be at least 8 characters long.")


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using Argon2id.
    """
    validate_password_strength(password)
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against an Argon2id hash.
    Returns False if hash is invalid or password does not match.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generates a secure JWT access token containing standard claims (sub, iat, exp, jti).
    Contains zero sensitive business data or credentials.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    encoded_jwt = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT access token.
    Raises PyJWT exceptions on expiration, invalid signature, or malformed format.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "iat", "exp", "jti"]},
    )


def _get_fernet_key() -> bytes:
    """
    Derives a standard 32-byte URL-safe base64 key for Fernet symmetric encryption.
    Uses CALENDAR_ENCRYPTION_KEY or falls back to JWT_SECRET_KEY.
    """
    import base64
    import hashlib
    raw_secret = settings.CALENDAR_ENCRYPTION_KEY or settings.JWT_SECRET_KEY
    key_hash = hashlib.sha256(raw_secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(key_hash)


def encrypt_token(plaintext: str) -> str:
    """
    Encrypts sensitive OAuth access and refresh tokens at rest using Fernet (AES-128-CBC + HMAC-SHA256).
    """
    if not plaintext:
        return ""
    from cryptography.fernet import Fernet
    f = Fernet(_get_fernet_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """
    Decrypts sensitive OAuth tokens from database storage.
    """
    if not ciphertext:
        return ""
    from cryptography.fernet import Fernet
    f = Fernet(_get_fernet_key())
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def generate_oauth_state(
    clinic_id: uuid.UUID,
    user_id: uuid.UUID,
    provider: str,
    expires_minutes: int = 15,
) -> str:
    """
    Generates a secure, signed, single-use, expiring OAuth CSRF state parameter.
    Tied to clinic_id, user_id, provider, and random nonce.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)
    secret = settings.CALENDAR_OAUTH_STATE_SECRET or settings.JWT_SECRET_KEY

    payload = {
        "clinic_id": str(clinic_id),
        "user_id": str(user_id),
        "provider": provider,
        "nonce": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_oauth_state(state: str, expected_provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Validates and decodes an OAuth state token.
    Raises BadRequestException on expiration, signature tampering, or provider mismatch.
    """
    if not state:
        raise BadRequestException("Missing OAuth state parameter.")
    secret = settings.CALENDAR_OAUTH_STATE_SECRET or settings.JWT_SECRET_KEY
    try:
        payload = jwt.decode(state, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise BadRequestException("OAuth state has expired. Please initiate calendar connection again.")
    except jwt.InvalidTokenError:
        raise BadRequestException("Invalid OAuth state parameter.")

    if expected_provider and payload.get("provider") != expected_provider:
        raise BadRequestException(f"OAuth state provider mismatch. Expected '{expected_provider}'.")

    return payload


