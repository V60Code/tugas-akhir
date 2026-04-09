"""initial_schema

Revision ID: f8eb3f7a8610
Revises: e501214acc4b
Create Date: 2026-03-03 18:43:43.365942

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8eb3f7a8610'
down_revision: Union[str, Sequence[str], None] = 'e501214acc4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add FINALIZED value to the jobstatus enum.
    The initial migration (e501214acc4b) created the enum without FINALIZED,
    but the model already has it. This migration adds it cleanly.
    PostgreSQL requires ALTER TYPE to add enum values.
    """
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'FINALIZED'")


def downgrade() -> None:
    """
    PostgreSQL does not support removing enum values.
    A full downgrade would require recreating the enum type — not done here.
    If rollback is needed, manually recreate the type without FINALIZED.
    """
    pass
