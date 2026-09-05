"""Add calendar_connections table and appointment calendar sync columns

Revision ID: 0007_calendar_integration
Revises: 0006_appointment_reminders
Create Date: 2026-09-05 20:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0007_calendar_integration"
down_revision: Union[str, None] = "0006_appointment_reminders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create calendar_connections table
    op.create_table(
        "calendar_connections",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("clinics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("account_identifier", sa.String(length=255), nullable=True),
        sa.Column("calendar_identifier", sa.String(length=255), server_default="primary", nullable=True),
        sa.Column("calendar_name", sa.String(length=255), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="connected", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("clinic_id", "provider", name="uq_clinic_calendar_provider"),
    )
    op.create_index(
        "ix_calendar_connections_clinic_provider",
        "calendar_connections",
        ["clinic_id", "provider"],
    )
    op.create_index(
        "ix_calendar_connections_clinic_id",
        "calendar_connections",
        ["clinic_id"],
    )
    op.create_index(
        "ix_calendar_connections_status",
        "calendar_connections",
        ["status"],
    )

    # 2. Add calendar synchronization columns to appointments table
    op.add_column(
        "appointments",
        sa.Column("external_event_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "calendar_connection_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("calendar_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "calendar_sync_status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "appointments",
        sa.Column("calendar_last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("calendar_sync_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("calendar_retry_count", sa.Integer(), server_default="0", nullable=False),
    )

    op.create_index(
        "ix_appointments_external_event_id",
        "appointments",
        ["external_event_id"],
    )
    op.create_index(
        "ix_appointments_calendar_sync_status",
        "appointments",
        ["calendar_sync_status"],
    )
    op.create_index(
        "ix_appointments_calendar_connection_id",
        "appointments",
        ["calendar_connection_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_appointments_calendar_connection_id", table_name="appointments")
    op.drop_index("ix_appointments_calendar_sync_status", table_name="appointments")
    op.drop_index("ix_appointments_external_event_id", table_name="appointments")
    op.drop_column("appointments", "calendar_retry_count")
    op.drop_column("appointments", "calendar_sync_error")
    op.drop_column("appointments", "calendar_last_synced_at")
    op.drop_column("appointments", "calendar_sync_status")
    op.drop_column("appointments", "calendar_connection_id")
    op.drop_column("appointments", "external_event_id")

    op.drop_index("ix_calendar_connections_status", table_name="calendar_connections")
    op.drop_index("ix_calendar_connections_clinic_id", table_name="calendar_connections")
    op.drop_index("ix_calendar_connections_clinic_provider", table_name="calendar_connections")
    op.drop_table("calendar_connections")

