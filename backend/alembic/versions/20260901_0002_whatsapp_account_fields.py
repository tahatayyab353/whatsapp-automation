"""Add display_name and access_token to whatsapp_accounts, and unique constraint on phone_number_id

Revision ID: 0002_whatsapp_account_fields
Revises: 0001_initial_schema
Create Date: 2026-09-01 10:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0002_whatsapp_account_fields"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_accounts",
        sa.Column("display_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "whatsapp_accounts",
        sa.Column("access_token", sa.String(length=512), nullable=True),
    )
    op.create_unique_constraint(
        "uq_whatsapp_accounts_phone_number_id",
        "whatsapp_accounts",
        ["phone_number_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_whatsapp_accounts_phone_number_id",
        "whatsapp_accounts",
        type_="unique",
    )
    op.drop_column("whatsapp_accounts", "access_token")
    op.drop_column("whatsapp_accounts", "display_name")
