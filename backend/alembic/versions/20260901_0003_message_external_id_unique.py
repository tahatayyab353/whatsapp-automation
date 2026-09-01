"""Add unique constraint on messages (clinic_id, external_message_id) for webhook idempotency

Revision ID: 0003_message_external_id_unique
Revises: 0002_whatsapp_account_fields
Create Date: 2026-09-01 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0003_message_external_id_unique"
down_revision: Union[str, None] = "0002_whatsapp_account_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_messages_clinic_external_id",
        "messages",
        ["clinic_id", "external_message_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_messages_clinic_external_id",
        "messages",
        type_="unique",
    )

