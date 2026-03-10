"""Add first_name and last_name fields to residents.

Revision ID: 9229ffa7599f
Revises: 9f9822ad20e1
Create Date: 2026-03-08
"""

import sqlalchemy as sa
from alembic import op

revision = "9229ffa7599f"
down_revision = "9f9822ad20e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("residents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("first_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("last_name", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("residents", schema=None) as batch_op:
        batch_op.drop_column("last_name")
        batch_op.drop_column("first_name")
