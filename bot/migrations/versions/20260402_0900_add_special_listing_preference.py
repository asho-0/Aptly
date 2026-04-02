"""add special listing preference

Revision ID: 20260402_0900
Revises: 20260401_2300
Create Date: 2026-04-02 09:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260402_0900"
down_revision: Union[str, Sequence[str], None] = "20260401_2300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "show_special_listings",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user", "show_special_listings")
