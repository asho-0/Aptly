"""add user pairing pin

Revision ID: 20260402_1900
Revises: 20260402_1015
Create Date: 2026-04-02 19:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260402_1900"
down_revision: Union[str, Sequence[str], None] = "20260402_1015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("pairing_pin", sa.String(length=6), nullable=True))
    op.create_index(op.f("ix_user_pairing_pin"), "user", ["pairing_pin"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_pairing_pin"), table_name="user")
    op.drop_column("user", "pairing_pin")
