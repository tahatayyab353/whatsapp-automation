"""Add appointment_reminders table for 24h and 2h appointment notification subsystem

Revision ID: 0006_appointment_reminders
Revises: 0005_appointment_fields
Create Date: 2026-09-05 17:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0006_appointment_reminders"
down_revision: Union[str, None] = "0005_appointment_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appointment_reminders",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("clinics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "appointment_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reminder_type", sa.String(length=32), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "appointment_id",
            "reminder_type",
            name="uq_appointment_reminders_appt_type",
        ),
    )
    op.create_index(
        "ix_reminders_due_lookup",
        "appointment_reminders",
        ["clinic_id", "status", "scheduled_for"],
    )
    op.create_index(
        "ix_reminders_appointment_type",
        "appointment_reminders",
        ["appointment_id", "reminder_type"],
    )
    op.create_index(
        "ix_appointment_reminders_clinic_id",
        "appointment_reminders",
        ["clinic_id"],
    )
    op.create_index(
        "ix_appointment_reminders_appointment_id",
        "appointment_reminders",
        ["appointment_id"],
    )
    op.create_index(
        "ix_appointment_reminders_status",
        "appointment_reminders",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_appointment_reminders_status", table_name="appointment_reminders")
    op.drop_index("ix_appointment_reminders_appointment_id", table_name="appointment_reminders")
    op.drop_index("ix_appointment_reminders_clinic_id", table_name="appointment_reminders")
    op.drop_index("ix_reminders_appointment_type", table_name="appointment_reminders")
    op.drop_index("ix_reminders_due_lookup", table_name="appointment_reminders")
    op.drop_table("appointment_reminders")
