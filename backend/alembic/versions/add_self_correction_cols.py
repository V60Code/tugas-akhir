"""Add self_correction tracking to sandbox_logs

Revision ID: add_self_correction_cols
Revises: f8eb3f7a8610
Create Date: 2026-03-08

Adds was_self_corrected (BOOLEAN) and self_correction_count (INTEGER)
to the sandbox_logs table so the application can record when
the AI self-correction mechanism was used and how many iterations it took.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_self_correction_cols'
down_revision = 'f8eb3f7a8610'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'sandbox_logs',
        sa.Column('was_self_corrected', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column(
        'sandbox_logs',
        sa.Column('self_correction_count', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('sandbox_logs', 'self_correction_count')
    op.drop_column('sandbox_logs', 'was_self_corrected')
