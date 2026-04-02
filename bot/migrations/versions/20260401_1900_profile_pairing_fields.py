"""profile pairing fields

Revision ID: 20260401_1900
Revises: 20260401_1200
Create Date: 2026-04-01 19:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260401_1900"
down_revision: Union[str, Sequence[str], None] = "20260401_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("salutation", sa.String(length=16), nullable=True))
    op.add_column("user", sa.Column("wbs_rooms", sa.SmallInteger(), nullable=True))
    op.add_column("user", sa.Column("wbs_income", sa.SmallInteger(), nullable=True))
    op.add_column("user", sa.Column("wbs_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "wbs_date")
    op.drop_column("user", "wbs_income")
    op.drop_column("user", "wbs_rooms")
    op.drop_column("user", "salutation")
