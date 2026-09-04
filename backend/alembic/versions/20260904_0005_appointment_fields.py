"""Add title, description, duration, timezone, created_by, and cancelled_at to appointments

Revision ID: 0005_appointment_fields
Revises: 0004_human_handoff
Create Date: 2026-09-04 11:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0005_appointment_fields"
down_revision: Union[str, None] = "0004_human_handoff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("title", sa.String(length=255), server_default="Consultation", nullable=False),
    )
    op.add_column(
        "appointments",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("duration_minutes", sa.Integer(), server_default="30", nullable=False),
    )
    op.add_column(
        "appointments",
        sa.Column("timezone", sa.String(length=50), server_default="Asia/Karachi", nullable=False),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "created_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "appointments",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_appointments_clinic_lead",
        "appointments",
        ["clinic_id", "lead_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_appointments_clinic_lead", table_name="appointments")
    op.drop_column("appointments", "cancelled_at")
    op.drop_column("appointments", "created_by_user_id")
    op.drop_column("appointments", "timezone")
    op.drop_column("appointments", "duration_minutes")
    op.drop_column("appointments", "description")
    op.drop_column("appointments", "title")

