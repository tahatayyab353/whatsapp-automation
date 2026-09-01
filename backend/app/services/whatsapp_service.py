import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WhatsAppAccount
from app.schemas.whatsapp import WhatsAppAccountCreate, WhatsAppAccountUpdate


class WhatsAppService:
    @staticmethod
    def create_account(
        db: Session,
        clinic_id: uuid.UUID,
        payload: WhatsAppAccountCreate,
    ) -> WhatsAppAccount:
        # Check if phone_number_id is already in use globally
        existing_phone_id = db.scalar(
            select(WhatsAppAccount).where(
                WhatsAppAccount.phone_number_id == payload.phone_number_id
            )
        )
        if existing_phone_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WhatsApp Phone Number ID is already registered.",
            )

        account = WhatsAppAccount(
            clinic_id=clinic_id,
            phone_number=payload.phone_number,
            phone_number_id=payload.phone_number_id,
            business_account_id=payload.business_account_id,
            display_name=payload.display_name,
            access_token=payload.access_token,
            is_active=True,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def list_accounts(
        db: Session,
        clinic_id: uuid.UUID,
    ) -> List[WhatsAppAccount]:
        stmt = (
            select(WhatsAppAccount)
            .where(WhatsAppAccount.clinic_id == clinic_id)
            .order_by(WhatsAppAccount.created_at.desc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_account(
        db: Session,
        clinic_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> WhatsAppAccount:
        account = db.scalar(
            select(WhatsAppAccount).where(
                WhatsAppAccount.id == account_id,
                WhatsAppAccount.clinic_id == clinic_id,
            )
        )
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WhatsApp account not found.",
            )
        return account

    @staticmethod
    def update_account(
        db: Session,
        clinic_id: uuid.UUID,
        account_id: uuid.UUID,
        payload: WhatsAppAccountUpdate,
    ) -> WhatsAppAccount:
        account = WhatsAppService.get_account(db, clinic_id, account_id)

        # If updating phone_number_id, check uniqueness
        if payload.phone_number_id and payload.phone_number_id != account.phone_number_id:
            existing = db.scalar(
                select(WhatsAppAccount).where(
                    WhatsAppAccount.phone_number_id == payload.phone_number_id,
                    WhatsAppAccount.id != account_id,
                )
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="WhatsApp Phone Number ID is already registered by another account.",
                )
            account.phone_number_id = payload.phone_number_id

        if payload.phone_number is not None:
            account.phone_number = payload.phone_number
        if payload.business_account_id is not None:
            account.business_account_id = payload.business_account_id
        if payload.display_name is not None:
            account.display_name = payload.display_name
        if payload.is_active is not None:
            account.is_active = payload.is_active

        # Token update semantics: only replace if explicitly provided and non-empty
        if payload.access_token is not None and payload.access_token.strip():
            account.access_token = payload.access_token.strip()

        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def deactivate_account(
        db: Session,
        clinic_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> WhatsAppAccount:
        """
        Soft deactivates the WhatsApp account. Preserves historical leads, conversations, and messages.
        """
        account = WhatsAppService.get_account(db, clinic_id, account_id)
        account.is_active = False
        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def get_account_by_phone_number_id(
        db: Session,
        phone_number_id: str,
    ) -> Optional[WhatsAppAccount]:
        """
        INTERNAL LOOKUP: Resolves Meta WhatsApp Phone Number ID to the owning WhatsAppAccount & Clinic.
        Used for routing incoming webhooks to the correct tenant.
        """
        return db.scalar(
            select(WhatsAppAccount).where(
                WhatsAppAccount.phone_number_id == phone_number_id,
                WhatsAppAccount.is_active == True,  # noqa: E712
            )
        )


whatsapp_service = WhatsAppService()

