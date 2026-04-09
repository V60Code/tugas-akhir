"""Remove unused tier and credits_balance columns from users table

Revision ID: b9c1f2e3a4d5
Revises: add_self_correction_cols
Create Date: 2026-03-10

Rationale:
    UserTier and credits_balance were planned for a freemium billing system
    that was explicitly excluded from PRD v1.0 scope. The columns have never
    been read or written by any live endpoint. Removing them keeps the schema
    aligned with the code and avoids misleading future contributors.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "b9c1f2e3a4d5"
down_revision: str = "add_self_correction_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "credits_balance")
    op.drop_column("users", "tier")
    # Drop the enum type that was exclusively used by the tier column.
    # IF EXISTS guards against running on a DB that was created from the
    # latest model (where the type was never created in the first place).
    op.execute("DROP TYPE IF EXISTS usertier")


def downgrade() -> None:
    # Recreate the enum type before re-adding the column that references it.
    op.execute("CREATE TYPE usertier AS ENUM ('FREE', 'PRO', 'ENTERPRISE')")
    op.add_column(
        "users",
        sa.Column(
            "tier",
            sa.Enum("FREE", "PRO", "ENTERPRISE", name="usertier"),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column("credits_balance", sa.Integer(), nullable=True),
    )
