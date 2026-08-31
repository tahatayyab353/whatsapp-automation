from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    ClinicContext,
    get_current_clinic,
    get_current_user,
    require_admin,
    require_owner,
)
from app.core.audit import log_auth_event
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.database import get_db
from app.models import User
from app.schemas.auth import (
    AuthenticatedTestResponse,
    ClinicContextTestResponse,
    LoginRequest,
    RoleTestResponse,
    TokenResponse,
)
from app.schemas.user import UserRead

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login",
    description="Authenticates user with email and password, returning a JWT access token.",
)
async def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))

    # Generic authentication error for any invalid condition to prevent user enumeration
    if not user or not user.is_active or not user.password_hash:
        log_auth_event("login_failure", email=payload.email, detail="Unknown user or inactive account")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(payload.password, user.password_hash):
        log_auth_event("login_failure", email=payload.email, user_id=str(user.id), detail="Incorrect password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue JWT token
    expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=expires_minutes),
    )

    log_auth_event("login_success", email=user.email, user_id=str(user.id))

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Current User Profile",
    description="Returns profile information for the authenticated user without exposing sensitive credentials.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    return UserRead.model_validate(current_user)


# ==============================================================================
# TEMPORARY TEST ENDPOINTS (Used solely for authorization system verification)
# ==============================================================================

@router.get(
    "/test-authenticated",
    response_model=AuthenticatedTestResponse,
    summary="[TEST] Verify User Authentication",
    description="Temporary endpoint verifying that user authentication succeeds.",
)
async def test_authenticated(
    current_user: User = Depends(get_current_user),
) -> AuthenticatedTestResponse:
    return AuthenticatedTestResponse(
        authenticated=True,
        user_id=str(current_user.id),
        email=current_user.email,
    )


@router.get(
    "/test-clinic",
    response_model=ClinicContextTestResponse,
    summary="[TEST] Verify Clinic Context Authorization",
    description="Temporary endpoint verifying that the user has an active membership in the clinic specified by X-Clinic-ID.",
)
async def test_clinic_context(
    clinic_context: ClinicContext = Depends(get_current_clinic),
) -> ClinicContextTestResponse:
    return ClinicContextTestResponse(
        authorized=True,
        clinic_id=str(clinic_context.clinic.id),
        role=clinic_context.role,
    )


@router.get(
    "/test-admin",
    response_model=RoleTestResponse,
    summary="[TEST] Verify Admin Role Authorization",
    description="Temporary endpoint verifying that the user holds Admin or Owner role in the clinic.",
)
async def test_admin_role(
    clinic_context: ClinicContext = Depends(require_admin),
) -> RoleTestResponse:
    return RoleTestResponse(
        authorized=True,
        role=clinic_context.role,
        user_id=str(clinic_context.user.id),
    )


@router.get(
    "/test-owner",
    response_model=RoleTestResponse,
    summary="[TEST] Verify Owner Role Authorization",
    description="Temporary endpoint verifying that the user holds Owner role in the clinic.",
)
async def test_owner_role(
    clinic_context: ClinicContext = Depends(require_owner),
) -> RoleTestResponse:
    return RoleTestResponse(
        authorized=True,
        role=clinic_context.role,
        user_id=str(clinic_context.user.id),
    )

