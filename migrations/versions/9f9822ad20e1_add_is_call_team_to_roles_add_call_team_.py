"""Add is_call_team flag to roles.

Revision ID: 9f9822ad20e1
Revises: f4e519dcd753
Create Date: 2026-03-08
"""

import sqlalchemy as sa
from alembic import op

revision = "9f9822ad20e1"
down_revision = "f4e519dcd753"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_call_team", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("roles", schema=None) as batch_op:
        batch_op.drop_column("is_call_team")
