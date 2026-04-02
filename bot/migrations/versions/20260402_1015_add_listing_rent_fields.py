"""add listing rent fields

Revision ID: 20260402_1015
Revises: 20260402_0900
Create Date: 2026-04-02 10:15:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260402_1015"
down_revision: Union[str, Sequence[str], None] = "20260402_0900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("listing", sa.Column("cold_rent", sa.Numeric(12, 2), nullable=True))
    op.add_column("listing", sa.Column("extra_costs", sa.Numeric(12, 2), nullable=True))
    op.alter_column(
        "listing",
        "floor",
        existing_type=sa.SmallInteger(),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="floor::text",
    )


def downgrade() -> None:
    op.alter_column(
        "listing",
        "floor",
        existing_type=sa.Text(),
        type_=sa.SmallInteger(),
        existing_nullable=True,
        postgresql_using="NULLIF(floor, '')::smallint",
    )
    op.drop_column("listing", "extra_costs")
    op.drop_column("listing", "cold_rent")
