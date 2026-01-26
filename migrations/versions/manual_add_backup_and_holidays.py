"""Add backup role and holiday support

Revision ID: manual_add_backup_holidays
Revises: f8edb2b59c6a
Create Date: 2026-01-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'manual_add_backup_holidays'
down_revision = 'f8edb2b59c6a'
branch_labels = None
depends_on = None


def upgrade():
    # Create holidays table
    op.create_table('holidays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_federal', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('holidays', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_holidays_date'), ['date'], unique=True)

    # Add is_backup column to roles
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_backup', sa.Boolean(), nullable=True, server_default='0'))

    # Add start_time column to time_entries
    with op.batch_alter_table('time_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('start_time', sa.Time(), nullable=True))


def downgrade():
    # Remove start_time from time_entries
    with op.batch_alter_table('time_entries', schema=None) as batch_op:
        batch_op.drop_column('start_time')

    # Remove is_backup from roles
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.drop_column('is_backup')

    # Drop holidays table
    with op.batch_alter_table('holidays', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_holidays_date'))

    op.drop_table('holidays')
