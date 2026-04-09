"""Add performance indexes on frequently-queried columns

Revision ID: c1d2e3f4a5b6
Revises: b9c1f2e3a4d5
Create Date: 2026-03-12

Rationale:
    PostgreSQL does NOT automatically index foreign key columns (unlike MySQL).
    All FK columns used in WHERE or JOIN clauses will cause full table scans
    without explicit indexes. This migration adds the missing indexes identified
    by reviewing every SELECT query in the application.

    Index strategy:
        - Single-column indexes for FK lookups (project_id, job_id)
        - Single-column index on status for future monitoring queries
        - Composite index on (job_id, artifact_type) for job_artifacts because
          every query on that table filters on both columns simultaneously
        - created_at indexes for ORDER BY in listing endpoints
"""
from alembic import op


# revision identifiers
revision: str = "c1d2e3f4a5b6"
down_revision: str = "b9c1f2e3a4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── projects ──────────────────────────────────────────────────────────────
    # GET /projects/ filters by user_id and orders by created_at DESC
    op.create_index("ix_projects_user_id",    "projects", ["user_id"])
    op.create_index("ix_projects_created_at", "projects", ["created_at"])

    # ── analysis_jobs ─────────────────────────────────────────────────────────
    # GET /projects/{id}/jobs filters by project_id and orders by created_at DESC
    # status is indexed for future monitoring / admin queries
    op.create_index("ix_analysis_jobs_project_id", "analysis_jobs", ["project_id"])
    op.create_index("ix_analysis_jobs_status",     "analysis_jobs", ["status"])
    op.create_index("ix_analysis_jobs_created_at", "analysis_jobs", ["created_at"])

    # ── ai_suggestions ────────────────────────────────────────────────────────
    # Every suggestions query filters by job_id; finalize also reads action_status
    op.create_index("ix_ai_suggestions_job_id",        "ai_suggestions", ["job_id"])
    op.create_index("ix_ai_suggestions_action_status", "ai_suggestions", ["action_status"])

    # ── job_artifacts ─────────────────────────────────────────────────────────
    # All artifact lookups use both job_id AND artifact_type — composite is optimal
    op.create_index(
        "ix_job_artifacts_job_id_type",
        "job_artifacts",
        ["job_id", "artifact_type"],
    )

    # ── sandbox_logs ──────────────────────────────────────────────────────────
    # Logs are looked up by job_id when debugging/reporting
    op.create_index("ix_sandbox_logs_job_id", "sandbox_logs", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_sandbox_logs_job_id",        table_name="sandbox_logs")
    op.drop_index("ix_job_artifacts_job_id_type",  table_name="job_artifacts")
    op.drop_index("ix_ai_suggestions_action_status", table_name="ai_suggestions")
    op.drop_index("ix_ai_suggestions_job_id",      table_name="ai_suggestions")
    op.drop_index("ix_analysis_jobs_created_at",   table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_status",       table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_project_id",   table_name="analysis_jobs")
    op.drop_index("ix_projects_created_at",        table_name="projects")
    op.drop_index("ix_projects_user_id",           table_name="projects")
