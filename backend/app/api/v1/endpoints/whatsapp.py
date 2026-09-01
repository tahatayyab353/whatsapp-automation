import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, require_admin
from app.core.config import settings
from app.core.logging import logger
from app.db.database import get_db
from app.integrations.whatsapp.security import verify_webhook_signature
from app.schemas.common import MessageResponse
from app.schemas.whatsapp import (
    WhatsAppAccountCreate,
    WhatsAppAccountRead,
    WhatsAppAccountUpdate,
)
from app.schemas.whatsapp_webhook import WebhookPayload, WebhookStatusResponse
from app.services.whatsapp_service import whatsapp_service
from app.services.whatsapp_webhook_service import whatsapp_webhook_service

router = APIRouter()


# ============================================================================
# Meta WhatsApp Cloud API Webhook Endpoints (Public - Meta Verification & HMAC)
# Note: These endpoints are invoked directly by Meta servers and do NOT use JWT/X-Clinic-ID.
# ============================================================================


@router.get(
    "/webhook",
    response_class=PlainTextResponse,
    summary="Verify Meta WhatsApp Webhook",
    description="Endpoint for Meta Webhook setup verification using hub.mode, hub.verify_token, and hub.challenge.",
)
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode", description="Meta verification mode ('subscribe')"),
    hub_verify_token: str = Query(..., alias="hub.verify_token", description="Verification secret token"),
    hub_challenge: str = Query(..., alias="hub.challenge", description="Challenge integer to return on success"),
) -> PlainTextResponse:
    if not settings.WHATSAPP_VERIFY_TOKEN:
        logger.error("WHATSAPP_VERIFY_TOKEN is not configured on the server.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Meta Webhook verification succeeded.")
        return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)

    logger.warning("Meta Webhook verification failed with invalid mode or token.")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden",
    )


@router.post(
    "/webhook",
    response_model=WebhookStatusResponse,
    summary="Receive Meta WhatsApp Webhook Events",
    description="Secure entry point for Meta WhatsApp event notifications validated via X-Hub-Signature-256 HMAC.",
)
async def receive_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db),
) -> WebhookStatusResponse:
    # 1. Read exact raw request body bytes for HMAC computation
    raw_body = await request.body()

    # 2. Validate X-Hub-Signature-256 using constant-time comparison
    is_valid = verify_webhook_signature(
        payload=raw_body,
        signature_header=x_hub_signature_256,
        app_secret=settings.WHATSAPP_APP_SECRET,
    )
    if not is_valid:
        logger.warning("WhatsApp webhook rejected: Invalid or missing X-Hub-Signature-256.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    # 3. Parse JSON ONLY AFTER signature verification
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        logger.warning("WhatsApp webhook body is not valid JSON.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from exc

    # 4. Validate Meta Webhook envelope structure
    try:
        payload = WebhookPayload.model_validate(data)
    except Exception as exc:
        logger.warning("WhatsApp webhook payload does not match expected envelope: %s", str(exc))
        return WebhookStatusResponse(status="ok")

    if payload.object != "whatsapp_business_account":
        logger.info("Ignoring non-WhatsApp webhook event object: %s", payload.object)
        return WebhookStatusResponse(status="ok")

    # 5. Process incoming message events (idempotency, Lead, Conversation, Message, AI reply)
    result = await whatsapp_webhook_service.process_webhook_payload(db=db, payload=payload)
    return WebhookStatusResponse(status=result.get("status", "ok"))


# ============================================================================
# Clinic-Scoped WhatsApp Account Management Endpoints (Owner/Admin Only)
# ============================================================================


@router.post(
    "/accounts",
    response_model=WhatsAppAccountRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register WhatsApp Account",
    description="Configures a Meta WhatsApp Cloud API phone number and credentials for the clinic. Permitted for Owner and Admin.",
)
async def create_whatsapp_account(
    payload: WhatsAppAccountCreate,
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WhatsAppAccountRead:
    account = whatsapp_service.create_account(
        db=db,
        clinic_id=clinic_context.clinic.id,
        payload=payload,
    )
    return WhatsAppAccountRead.model_validate(account)


@router.get(
    "/accounts",
    response_model=List[WhatsAppAccountRead],
    summary="List WhatsApp Accounts",
    description="Retrieves all WhatsApp Cloud API accounts configured for the active clinic. Permitted for Owner and Admin.",
)
async def list_whatsapp_accounts(
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> List[WhatsAppAccountRead]:
    accounts = whatsapp_service.list_accounts(
        db=db,
        clinic_id=clinic_context.clinic.id,
    )
    return [WhatsAppAccountRead.model_validate(acc) for acc in accounts]


@router.get(
    "/accounts/{account_id}",
    response_model=WhatsAppAccountRead,
    summary="Get WhatsApp Account Details",
    description="Fetches details of a specific WhatsApp account belonging to the active clinic. Permitted for Owner and Admin.",
)
async def get_whatsapp_account(
    account_id: uuid.UUID,
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WhatsAppAccountRead:
    account = whatsapp_service.get_account(
        db=db,
        clinic_id=clinic_context.clinic.id,
        account_id=account_id,
    )
    return WhatsAppAccountRead.model_validate(account)


@router.patch(
    "/accounts/{account_id}",
    response_model=WhatsAppAccountRead,
    summary="Update WhatsApp Account",
    description="Updates WhatsApp phone number, display name, or access token. Permitted for Owner and Admin.",
)
async def update_whatsapp_account(
    account_id: uuid.UUID,
    payload: WhatsAppAccountUpdate,
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WhatsAppAccountRead:
    updated = whatsapp_service.update_account(
        db=db,
        clinic_id=clinic_context.clinic.id,
        account_id=account_id,
        payload=payload,
    )
    return WhatsAppAccountRead.model_validate(updated)


@router.delete(
    "/accounts/{account_id}",
    response_model=MessageResponse,
    summary="Deactivate WhatsApp Account",
    description="Soft-deactivates the WhatsApp integration for the clinic, preserving conversation history. Permitted for Owner and Admin.",
)
async def deactivate_whatsapp_account(
    account_id: uuid.UUID,
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    whatsapp_service.deactivate_account(
        db=db,
        clinic_id=clinic_context.clinic.id,
        account_id=account_id,
    )
    return MessageResponse(message="WhatsApp account deactivated successfully.")
