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

