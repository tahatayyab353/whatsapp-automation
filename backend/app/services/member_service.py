import uuid
from typing import List
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ClinicMembership, User
from app.schemas.membership import MemberRead, MemberRoleUpdate


class MemberService:
    @staticmethod
    def list_members(db: Session, clinic_id: uuid.UUID) -> List[MemberRead]:
        stmt = (
            select(ClinicMembership, User)
            .join(User, ClinicMembership.user_id == User.id)
            .where(ClinicMembership.clinic_id == clinic_id)
            .order_by(ClinicMembership.created_at.asc())
        )
        results = db.execute(stmt).all()
        members: List[MemberRead] = []
        for membership, user in results:
            members.append(
                MemberRead(
                    id=membership.id,
                    user_id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=membership.role,
                    is_active=user.is_active,
                    created_at=membership.created_at,
                )
            )
        return members

    @staticmethod
    def update_member_role(
        db: Session,
        clinic_id: uuid.UUID,
        actor_role: str,
        target_user_id: uuid.UUID,
        payload: MemberRoleUpdate,
    ) -> ClinicMembership:
        membership = db.scalar(
            select(ClinicMembership).where(
                ClinicMembership.clinic_id == clinic_id,
                ClinicMembership.user_id == target_user_id,
            )
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clinic member not found.",
            )

        new_role = payload.role.lower()
        current_target_role = membership.role.lower()

        if actor_role == "admin":
            if current_target_role == "owner":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins cannot modify owner roles.",
                )
            if new_role == "owner":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins cannot promote members to owner.",
                )

        if current_target_role == "owner" and new_role != "owner":
            owner_count = db.scalar(
                select(func.count(ClinicMembership.id)).where(
                    ClinicMembership.clinic_id == clinic_id,
                    ClinicMembership.role == "owner",
                )
            )
            if (owner_count or 0) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change role: Clinic must have at least one owner.",
                )

        membership.role = new_role
        db.add(membership)
        db.commit()
        db.refresh(membership)
        return membership

    @staticmethod
    def remove_member(
        db: Session,
        clinic_id: uuid.UUID,
        actor_role: str,
        actor_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
    ) -> None:
        membership = db.scalar(
            select(ClinicMembership).where(
                ClinicMembership.clinic_id == clinic_id,
                ClinicMembership.user_id == target_user_id,
            )
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clinic member not found.",
            )

        target_role = membership.role.lower()

        if actor_role == "admin" and target_role == "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot remove clinic owners.",
            )

        if target_role == "owner":
            owner_count = db.scalar(
                select(func.count(ClinicMembership.id)).where(
                    ClinicMembership.clinic_id == clinic_id,
                    ClinicMembership.role == "owner",
                )
            )
            if (owner_count or 0) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove the sole owner of the clinic.",
                )

        db.delete(membership)
        db.commit()


member_service = MemberService()

