from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    ClinicContext,
    get_db,
    require_admin,
    require_staff,
)
from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.schemas.calendar import (
    CalendarConnectResponse,
    CalendarConnectionResponse,
    CalendarItemResponse,
    CalendarSelectRequest,
    CalendarSyncResponse,
)
from app.services.calendar_service import calendar_service

router = APIRouter()


@router.get(
    "/connections",
    response_model=List[CalendarConnectionResponse],
    summary="List clinic calendar connections",
    description="Returns all external calendar connections and statuses for the active clinic.",
)
def list_calendar_connections(
    ctx: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> List[CalendarConnectionResponse]:
    connections = calendar_service.get_clinic_connections(db, ctx.clinic.id)
    return [CalendarConnectionResponse.model_validate(c) for c in connections]


@router.post(
    "/{provider}/connect",
    response_model=CalendarConnectResponse,
    summary="Initiate calendar OAuth authorization",
    description="Generates an OAuth authorization URL with a secure, CSRF-protected state parameter.",
)
def connect_calendar(
    provider: str,
    ctx: ClinicContext = Depends(require_staff),
) -> CalendarConnectResponse:
    auth_url = calendar_service.initiate_oauth(
        clinic_id=ctx.clinic.id,
        user_id=ctx.user.id,
        provider_name=provider,
    )
    return CalendarConnectResponse(
        authorization_url=auth_url,
        provider=provider.lower().strip(),
    )


@router.get(
    "/{provider}/callback",
    summary="Handle OAuth callback",
    description="Exchanges authorization code for tokens, securely stores credentials, and activates connection.",
)
async def calendar_oauth_callback(
    provider: str,
    code: str = Query(..., description="OAuth authorization code"),
    state: str = Query(..., description="CSRF state parameter"),
    db: Session = Depends(get_db),
) -> Any:
    connection = await calendar_service.handle_oauth_callback(
        db=db,
        provider_name=provider,
        code=code,
        state=state,
    )

    # Return a clean HTML redirect page back to the frontend settings
    html_content = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <title>Calendar Connected</title>
        <meta http-equiv="refresh" content="2;url=/settings/calendar?connected={provider}" />
      </head>
      <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
        <h2>Successfully Connected to {provider.capitalize()} Calendar!</h2>
        <p>Redirecting you back to your clinic dashboard...</p>
        <p><a href="/settings/calendar?connected={provider}">Click here if not redirected automatically.</a></p>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)


@router.post(
    "/{provider}/disconnect",
    response_model=CalendarConnectionResponse,
    summary="Disconnect calendar provider",
    description="Invalidates and securely clears OAuth credentials for the specified provider without deleting appointment records.",
)
async def disconnect_calendar(
    provider: str,
    ctx: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> CalendarConnectionResponse:
    connection = await calendar_service.disconnect(db, ctx.clinic.id, provider)
    return CalendarConnectionResponse.model_validate(connection)


@router.get(
    "/calendars",
    response_model=List[CalendarItemResponse],
    summary="List available calendars from connected provider",
    description="Discovers available user/clinic calendars on the connected external provider.",
)
async def list_available_calendars(
    provider: str = Query(..., description="Provider name ('google' or 'microsoft')"),
    ctx: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> List[CalendarItemResponse]:
    calendars = await calendar_service.list_available_calendars(
        db=db,
        clinic_id=ctx.clinic.id,
        provider_name=provider,
    )
    return [CalendarItemResponse(**c) for c in calendars]


@router.post(
    "/select",
    response_model=CalendarConnectionResponse,
    summary="Select target calendar",
    description="Sets the destination calendar identifier where clinic appointments will be synchronized.",
)
def select_calendar(
    payload: CalendarSelectRequest,
    ctx: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> CalendarConnectionResponse:
    connection = calendar_service.select_calendar(
        db=db,
        clinic_id=ctx.clinic.id,
        provider_name=payload.provider,
        calendar_identifier=payload.calendar_identifier,
        calendar_name=payload.calendar_name,
    )
    return CalendarConnectionResponse.model_validate(connection)


@router.post(
    "/sync",
    response_model=CalendarSyncResponse,
    summary="Trigger immediate calendar synchronization",
    description="Processes pending appointment synchronizations immediately.",
)
async def trigger_calendar_sync(
    ctx: ClinicContext = Depends(require_staff),
    db: Session = Depends(get_db),
) -> CalendarSyncResponse:
    count = await calendar_service.process_due_calendar_syncs(db=db)
    return CalendarSyncResponse(processed_count=count, status="ok")

