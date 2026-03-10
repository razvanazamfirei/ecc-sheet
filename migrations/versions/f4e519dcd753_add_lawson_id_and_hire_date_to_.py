"""Add payroll settings table plus Lawson ID and hire date fields.

Revision ID: f4e519dcd753
Revises:
Create Date: 2026-03-08
"""

import sqlalchemy as sa
from alembic import op

revision = "f4e519dcd753"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payroll_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program", sa.String(length=50), nullable=True),
        sa.Column("company", sa.String(length=50), nullable=True),
        sa.Column("batch", sa.Integer(), nullable=True),
        sa.Column("pay_code", sa.Integer(), nullable=True),
        sa.Column("dept", sa.Integer(), nullable=True),
        sa.Column("expense", sa.Integer(), nullable=True),
        sa.Column("acct_unit", sa.Integer(), nullable=True),
        sa.Column("label_suffix", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("residents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lawson_id", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("hire_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("residents", schema=None) as batch_op:
        batch_op.drop_column("hire_date")
        batch_op.drop_column("lawson_id")

    op.drop_table("payroll_settings")
