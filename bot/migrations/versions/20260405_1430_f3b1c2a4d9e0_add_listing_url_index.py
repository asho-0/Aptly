"""add listing url index

Revision ID: f3b1c2a4d9e0
Revises: d5c3a8e11ec7
Create Date: 2026-04-05 14:30:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3b1c2a4d9e0"
down_revision: Union[str, Sequence[str], None] = "d5c3a8e11ec7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_listing_url", "listing", ["url"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_listing_url", table_name="listing")
