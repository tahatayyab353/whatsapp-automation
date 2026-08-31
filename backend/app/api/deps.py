import uuid
from dataclasses import dataclass
from typing import Callable, List, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_auth_event
from app.core.security import decode_access_token
from app.db.database import get_db
from app.models import Clinic, ClinicMembership, User

# HTTP Bearer security scheme
security_bearer = HTTPBearer(auto_error=False)


@dataclass
class ClinicContext:
    """
    Resolved authenticated tenant context.
    Provides the active clinic, authenticated user, and verified membership role.
    """
    clinic: Clinic
    user: User
    membership: ClinicMembership
    role: str


async def get_current_user(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates JWT access token and returns the authenticated active User.
    Raises HTTP 401 on missing, expired, or invalid token.
    """
    if not auth_credentials or not auth_credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            log_auth_event("login_failure", detail="JWT missing subject claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload. Missing user ID.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError) as exc:
        log_auth_event("login_failure", detail=f"JWT validation failed: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        log_auth_event("login_failure", user_id=user_id_str, detail="User not found for token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or credentials invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        log_auth_event("login_failure", user_id=user_id_str, email=user.email, detail="Inactive user account")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_clinic(
    x_clinic_id: Optional[str] = Header(None, alias="X-Clinic-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClinicContext:
    """
    Resolves the active clinic context from the X-Clinic-ID header.
    Verifies that the authenticated user holds an active membership for the requested clinic.
    Raises HTTP 400 if header is missing/invalid, or HTTP 403 if unauthorized.
    """
    if not x_clinic_id or not x_clinic_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required header 'X-Clinic-ID'.",
        )

    try:
        clinic_uuid = uuid.UUID(x_clinic_id.strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format for 'X-Clinic-ID'.",
        )

    # Verify membership exists for this user and clinic
    membership = db.scalar(
        select(ClinicMembership).where(
            ClinicMembership.clinic_id == clinic_uuid,
            ClinicMembership.user_id == current_user.id,
        )
    )

    if not membership:
        log_auth_event(
            "authorization_failure",
            email=current_user.email,
            user_id=str(current_user.id),
            clinic_id=str(clinic_uuid),
            detail="User is not a member of the requested clinic",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have membership in this clinic.",
        )

    clinic = db.scalar(select(Clinic).where(Clinic.id == clinic_uuid))
    if not clinic or not clinic.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Clinic is inactive or unavailable.",
        )

    return ClinicContext(
        clinic=clinic,
        user=current_user,
        membership=membership,
        role=membership.role,
    )


def require_role(allowed_roles: List[str]) -> Callable[[ClinicContext], ClinicContext]:
    """
    Role-based authorization dependency factory.
    Enforces that the user's role in the active clinic matches one of the allowed roles.
    """
    async def role_checker(
        clinic_context: ClinicContext = Depends(get_current_clinic),
    ) -> ClinicContext:
        user_role = clinic_context.role.lower()
        valid_roles = [r.lower() for r in allowed_roles]

        if user_role not in valid_roles:
            log_auth_event(
                "authorization_failure",
                email=clinic_context.user.email,
                user_id=str(clinic_context.user.id),
                clinic_id=str(clinic_context.clinic.id),
                detail=f"Role '{user_role}' insufficient for required roles: {valid_roles}",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: Requires one of {allowed_roles} roles.",
            )
        return clinic_context

    return role_checker


# Role hierarchy convenience dependencies
require_owner = require_role(["owner"])
require_admin = require_role(["owner", "admin"])
require_staff = require_role(["owner", "admin", "staff"])

