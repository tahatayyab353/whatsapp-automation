"""Add handoffs table for human handoff and escalation system

Revision ID: 0004_human_handoff
Revises: 0003_message_external_id_unique
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0004_human_handoff"
down_revision: Union[str, None] = "0003_message_external_id_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "handoffs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("clinics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_to_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "reason",
            sa.String(length=100),
            nullable=False,
            server_default="staff_required",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_handoffs_clinic_status",
        "handoffs",
        ["clinic_id", "status"],
    )
    op.create_index(
        "ix_handoffs_conv_status",
        "handoffs",
        ["conversation_id", "status"],
    )
    op.create_index(
        "ix_handoffs_clinic_requested_at",
        "handoffs",
        ["clinic_id", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_handoffs_clinic_requested_at", table_name="handoffs")
    op.drop_index("ix_handoffs_conv_status", table_name="handoffs")
    op.drop_index("ix_handoffs_clinic_status", table_name="handoffs")
    op.drop_table("handoffs")

