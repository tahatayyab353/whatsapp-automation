import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ClinicContext, require_admin
from app.db.database import get_db
from app.schemas.common import MessageResponse
from app.schemas.membership import ClinicMembershipRead, MemberRead, MemberRoleUpdate
from app.services.member_service import member_service

router = APIRouter()


@router.get(
    "",
    response_model=List[MemberRead],
    summary="List Clinic Members",
    description="Returns all staff and administrators associated with the active clinic tenant. Permitted for Owner and Admin.",
)
async def list_members(
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> List[MemberRead]:
    return member_service.list_members(db, clinic_context.clinic.id)


@router.patch(
    "/{user_id}/role",
    response_model=ClinicMembershipRead,
    summary="Update Member Role",
    description="Modifies a member's role within the clinic. Permitted for Owner (all roles) and Admin (staff only).",
)
async def update_member_role(
    user_id: uuid.UUID,
    payload: MemberRoleUpdate,
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ClinicMembershipRead:
    updated_membership = member_service.update_member_role(
        db=db,
        clinic_id=clinic_context.clinic.id,
        actor_role=clinic_context.role,
        target_user_id=user_id,
        payload=payload,
    )
    return ClinicMembershipRead.model_validate(updated_membership)


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Remove Member from Clinic",
    description="Revokes a user's membership in the active clinic. Does not delete the platform user.",
)
async def remove_member(
    user_id: uuid.UUID,
    clinic_context: ClinicContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    member_service.remove_member(
        db=db,
        clinic_id=clinic_context.clinic.id,
        actor_role=clinic_context.role,
        actor_user_id=clinic_context.user.id,
        target_user_id=user_id,
    )
    return MessageResponse(message="Member removed successfully from clinic.")

