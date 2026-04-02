"""add user profile fields

Revision ID: 20260401_1200
Revises: 52ad749421f4
Create Date: 2026-04-01 12:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260401_1200"
down_revision: Union[str, Sequence[str], None] = "52ad749421f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("first_name", sa.String(length=128), nullable=True))
    op.add_column("user", sa.Column("last_name", sa.String(length=128), nullable=True))
    op.add_column("user", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("user", sa.Column("phone", sa.String(length=64), nullable=True))
    op.add_column("user", sa.Column("address", sa.String(length=255), nullable=True))
    op.add_column("user", sa.Column("zip_code", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "zip_code")
    op.drop_column("user", "address")
    op.drop_column("user", "phone")
    op.drop_column("user", "email")
    op.drop_column("user", "last_name")
    op.drop_column("user", "first_name")
