"""persist extension pairing

Revision ID: 20260401_2300
Revises: 20260401_1900
Create Date: 2026-04-01 23:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260401_2300"
down_revision: Union[str, Sequence[str], None] = "20260401_1900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "extension_pairing",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column("pin_code", sa.String(length=6), nullable=False),
        sa.Column("pin_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chat_id"], ["user.chat_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_extension_pairing_chat_id"),
        "extension_pairing",
        ["chat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extension_pairing_pin_code"),
        "extension_pairing",
        ["pin_code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_extension_pairing_pin_expires_at"),
        "extension_pairing",
        ["pin_expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extension_pairing_token"), "extension_pairing", ["token"], unique=True
    )
    op.create_index(
        op.f("ix_extension_pairing_token_expires_at"),
        "extension_pairing",
        ["token_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_extension_pairing_token_expires_at"), table_name="extension_pairing"
    )
    op.drop_index(op.f("ix_extension_pairing_token"), table_name="extension_pairing")
    op.drop_index(
        op.f("ix_extension_pairing_pin_expires_at"), table_name="extension_pairing"
    )
    op.drop_index(op.f("ix_extension_pairing_pin_code"), table_name="extension_pairing")
    op.drop_index(op.f("ix_extension_pairing_chat_id"), table_name="extension_pairing")
    op.drop_table("extension_pairing")
