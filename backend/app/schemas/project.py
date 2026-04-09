from typing import Optional, Annotated
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, AfterValidator


# ── Shared name validator — used only in WRITE schemas (Create/Update) ──────
# The validator is intentionally absent from read schemas (ProjectInDBBase and
# descendants) to avoid validation errors when serializing existing DB rows that
# may not meet current constraints (e.g. data migrated before this rule existed).
def _validate_project_name(v: str) -> str:
    """Reject blank or whitespace-only project names."""
    if not v or not v.strip():
        raise ValueError('Project name cannot be blank.')
    return v.strip()


# Annotated type — validator runs automatically on fields typed with this
ValidatedProjectName = Annotated[str, AfterValidator(_validate_project_name)]


# ── Write schemas (user input) — validation applied ─────────────────────────

class ProjectCreate(BaseModel):
    name: ValidatedProjectName
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: ValidatedProjectName
    description: Optional[str] = None


# ── Read schemas (DB → API response) — NO validators, safe for any data ─────

class ProjectInDBBase(BaseModel):
    """Base for read-only project responses. No write validators."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    user_id: UUID
    created_at: datetime


class ProjectResponse(ProjectInDBBase):
    pass


class ProjectListItemResponse(ProjectInDBBase):
    """
    Extended response for GET /projects/ list.
    Includes job_count populated via a single JOIN query (no N+1 problem).
    """
    job_count: int = 0
