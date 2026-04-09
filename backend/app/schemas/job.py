from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class JobSummaryResponse(BaseModel):
    """Lightweight job info for project history listing."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    status: str
    app_context: str
    created_at: datetime
    error_message: Optional[str] = None


class AISuggestionResponse(BaseModel):
    """Full AI suggestion with SQL patch — returned by GET /jobs/{id}/suggestions."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    table_name: str
    issue: str
    suggestion: str
    risk_level: str
    confidence: float
    sql_patch: str
    action_status: str


class JobSuggestionsResponse(BaseModel):
    """Response containing original uploaded SQL, AI suggestions, and any missing FK warnings."""
    original_sql: str
    suggestions: List[AISuggestionResponse]
    missing_fk_warnings: List[str] = []
    has_missing_references: bool = False


class FinalizeRequest(BaseModel):
    """Payload for triggering job finalization with selected suggestions."""
    accepted_suggestion_ids: List[UUID]



# ── ERD / Schema Visualization Schemas ────────────────────────────────────────

class ERDForeignKey(BaseModel):
    """A single foreign key relationship extracted from a table."""
    column: str
    references_table: str
    references_column: str


class ERDColumn(BaseModel):
    """A single column definition in an ERD table node."""
    name: str
    type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_nullable: bool = True
    is_unique: bool = False


class ERDTable(BaseModel):
    """A single table node in the ERD diagram."""
    name: str
    columns: List[ERDColumn]
    foreign_keys: List[ERDForeignKey] = []


class ERDSchemaResponse(BaseModel):
    """
    Full schema response for GET /jobs/{id}/schema.
    Consumed by the React Flow ERD Visualizer on the frontend.
    """
    job_id: UUID
    tables: List[ERDTable]
    errors: List[str] = []
    missing_fk_warnings: List[str] = []
    has_missing_references: bool = False
    table_count: int
    relationship_count: int


# ── Endpoint response schemas ───────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Returned immediately after a file is uploaded and the analysis job is queued."""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Current status of an analysis job — used for frontend polling."""
    job_id: str
    status: str
    progress_step: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime


class FinalizeResponse(BaseModel):
    """Confirmation that finalization has been triggered."""
    message: str


class DownloadResponse(BaseModel):
    """Presigned download URL for the optimized SQL artifact."""
    download_url: str
