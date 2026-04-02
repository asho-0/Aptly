"""normalize user profile fields

Revision ID: 20260402_2200
Revises: 20260402_1900
Create Date: 2026-04-02 22:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260402_2200"
down_revision: Union[str, Sequence[str], None] = "20260402_1900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("street", sa.String(length=255), nullable=True))
    op.add_column("user", sa.Column("house_number", sa.String(length=64), nullable=True))
    op.add_column("user", sa.Column("city", sa.String(length=128), nullable=True))
    op.add_column("user", sa.Column("persons_total", sa.SmallInteger(), nullable=True))
    op.add_column(
        "user",
        sa.Column("wbs_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.drop_column("user", "address")


def downgrade() -> None:
    op.add_column("user", sa.Column("address", sa.String(length=255), nullable=True))
    op.drop_column("user", "wbs_available")
    op.drop_column("user", "persons_total")
    op.drop_column("user", "city")
    op.drop_column("user", "house_number")
    op.drop_column("user", "street")
