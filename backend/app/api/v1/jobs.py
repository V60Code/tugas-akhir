from typing import List, Optional
import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

# --- Imports Internal ---
from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.job import AnalysisJob, JobArtifact, Project, JobStatus, AppContext, ArtifactType
from app.models.suggestion import AISuggestion, ActionStatus
from app.services.storage import minio_service
from app.services.parser import sanitize_sql_stream, parse_sql_to_erd_schema, parse_sql_to_schema
from app.schemas.job import (
    AISuggestionResponse, JobSummaryResponse, ERDSchemaResponse,
    ERDTable, ERDColumn, ERDForeignKey, FinalizeRequest, JobSuggestionsResponse,
    UploadResponse, JobStatusResponse, FinalizeResponse, DownloadResponse,
)
from app.core.config import settings
from app.core.limiter import limiter
from app.worker import process_analysis_job, finalize_job

router = APIRouter()


# ── 1. POST /upload ──────────────────────────────────────────────────────────────────
@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=UploadResponse)
@limiter.limit("20/hour")
async def upload_sql_file(
    request: Request,
    file: UploadFile = File(...),
    project_id: uuid.UUID = Form(...),
    app_context: AppContext = Form(...),
    db_dialect: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """
    Upload SQL file, sanitize it, save to MinIO, and queue analysis job.
    Accepts an optional db_dialect ('mysql', 'postgres') for dialect-aware parsing.
    """
    # A. Validate file extension
    if not file.filename.lower().endswith('.sql'):
        raise HTTPException(
            status_code=400,
            detail="Only .sql files are allowed."
        )

    # B. Validate file size (max 10 MB)
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
    file_data_raw = await file.read()
    if len(file_data_raw) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum allowed size is 10 MB."
        )
    # Wrap bytes back into a file-like object for the sanitizer
    file.file = io.BytesIO(file_data_raw)

    # C. Validate project ownership
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    project = result.scalars().first()
    
    if not project:
        # Project exists but belongs to a different user — return 403, not 404
        result_exists = await db.execute(select(Project).where(Project.id == project_id))
        if result_exists.scalars().first():
             raise HTTPException(status_code=403, detail="Not authorized to access this project.")
        raise HTTPException(status_code=404, detail="Project not found.")

    # D. Sanitize file (Privacy Shield): strip INSERT/COPY rows
    try:
        sanitized_content = sanitize_sql_stream(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")
    
    # E. Upload sanitized SQL to MinIO
    job_id = uuid.uuid4()
    object_name = f"{current_user.id}/{job_id}/clean.sql"
    
    try:
        minio_service.upload_file(sanitized_content, object_name, content_type="application/sql")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to storage: {str(e)}")

    # F. Persist job metadata
    job = AnalysisJob(
        id=job_id,
        project_id=project_id,
        original_filename=file.filename,
        status=JobStatus.QUEUED,
        app_context=app_context,
        db_dialect=db_dialect,
        tokens_used=0
    )
    db.add(job)
    
    # G. Persist artifact reference
    artifact = JobArtifact(
        job_id=job_id,
        artifact_type=ArtifactType.RAW_UPLOAD,
        storage_path=object_name,
        file_size_bytes=len(sanitized_content)
    )
    db.add(artifact)
    
    # H. Commit and dispatch Celery task
    await db.commit()
    await db.refresh(job)
    
    process_analysis_job.delay(str(job.id))

    return UploadResponse(
        job_id=str(job.id),
        status=job.status.value,
        message="File uploaded successfully. Analysis queued.",
    )


# ── 2. GET /{job_id}/status ─────────────────────────────────────────────────────────────────
@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Check analysis status (QUEUED -> PROCESSING -> COMPLETED/FAILED).
    """
    result = await db.execute(
        select(AnalysisJob, Project)
        .join(Project, AnalysisJob.project_id == Project.id)
        .where(AnalysisJob.id == job_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    job, project = row

    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")

    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status.value,
        progress_step="AI_ANALYSIS" if job.status == JobStatus.PROCESSING else None,
        error=job.error_message,
        created_at=job.created_at,
    )


# ── 3. GET /{job_id}/suggestions ──────────────────────────────────────────────────────────
@router.get("/{job_id}/suggestions", response_model=JobSuggestionsResponse)
async def get_job_suggestions(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI suggestions after job is COMPLETED.
    """
    result = await db.execute(
        select(AnalysisJob, Project)
        .join(Project, AnalysisJob.project_id == Project.id)
        .where(AnalysisJob.id == job_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    job, project = row

    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Return empty results for jobs not yet complete.
    # FINALIZED is also valid — suggestions remain in the DB after finalization.
    if job.status not in (JobStatus.COMPLETED, JobStatus.FINALIZED):
        return JobSuggestionsResponse(original_sql="", suggestions=[])

    # 1. Fetch Original SQL from Artifacts
    result_artifact = await db.execute(
        select(JobArtifact).where(
            JobArtifact.job_id == job.id,
            JobArtifact.artifact_type == ArtifactType.RAW_UPLOAD
        )
    )
    artifact = result_artifact.scalars().first()
    
    original_sql = ""
    if artifact:
        try:
            response = minio_service.client.get_object(
                settings.MINIO_BUCKET_NAME, artifact.storage_path
            )
            original_sql = response.read().decode("utf-8")
            response.close()
            response.release_conn()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch original SQL: {e}")

    # 2. Detect missing FK references via quick ERD parse
    missing_fk_warnings: list[str] = []
    has_missing_references: bool = False
    if original_sql:
        try:
            erd_data = parse_sql_to_erd_schema(original_sql)
            missing_fk_warnings = erd_data.get("missing_fk_warnings", [])
            has_missing_references = erd_data.get("has_missing_references", False)
        except Exception:
            pass  # Non-critical: warnings are best-effort

    suggestions_result = await db.execute(
        select(AISuggestion).where(AISuggestion.job_id == job_id)
    )
    suggestions = suggestions_result.scalars().all()

    # Serialize ORM objects to Pydantic response models
    return JobSuggestionsResponse(
        original_sql=original_sql,
        suggestions=[AISuggestionResponse.model_validate(s) for s in suggestions],
        missing_fk_warnings=missing_fk_warnings,
        has_missing_references=has_missing_references,
    )


# ── 4. POST /{job_id}/finalize ───────────────────────────────────────────────────────────────
@router.post("/{job_id}/finalize", status_code=200, response_model=FinalizeResponse)
async def finalize_analysis_job(
    job_id: uuid.UUID,
    request: FinalizeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply accepted suggestions, run validation in Sandbox, and generate final SQL.
    """
    result = await db.execute(select(AnalysisJob, Project).join(Project).where(AnalysisJob.id == job_id))
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job, project = row
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Reset all suggestions to REJECTED, then mark the selected ones ACCEPTED.
    await db.execute(
        update(AISuggestion)
        .where(AISuggestion.job_id == job_id)
        .values(action_status=ActionStatus.REJECTED)
    )
    
    if request.accepted_suggestion_ids:
        await db.execute(
            update(AISuggestion)
            .where(AISuggestion.job_id == job_id)
            .where(AISuggestion.id.in_(request.accepted_suggestion_ids))
            .values(action_status=ActionStatus.ACCEPTED)
        )
    
    await db.commit()
    
    finalize_job.delay(str(job.id))

    return FinalizeResponse(message="Finalization started. Check status for updates.")


# ── 5. GET /{job_id}/download ────────────────────────────────────────────────────────────────
@router.get("/{job_id}/download", response_model=DownloadResponse)
async def download_optimized_sql(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get temporary download URL for the optimized SQL file.
    """
    result = await db.execute(select(AnalysisJob, Project).join(Project).where(AnalysisJob.id == job_id))
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job, project = row
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if job.status != JobStatus.FINALIZED:
        raise HTTPException(status_code=400, detail="Job is not finalized yet. Please trigger finalization first.")
    
    result_artifact = await db.execute(
        select(JobArtifact).where(
            JobArtifact.job_id == job.id,
            JobArtifact.artifact_type == ArtifactType.OPTIMIZED_SQL
        )
    )
    artifact = result_artifact.scalars().first()

    if not artifact:
        raise HTTPException(status_code=404, detail="Optimized artifact not found. Please finalize the job first.")

    # Generate presigned URL via storage service (valid 1 hour)
    try:
        url = minio_service.get_presigned_url(artifact.storage_path)
        if not url:
            raise Exception("Presigned URL generation returned None")
        return DownloadResponse(download_url=url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download link: {str(e)}")


# ── 6. GET /{job_id}/schema ───────────────────────────────────────────────────────────────────
@router.get("/{job_id}/schema", response_model=ERDSchemaResponse)
async def get_job_schema(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ERDSchemaResponse:
    """
    Parse the uploaded SQL file and return a full ERD-ready schema
    (tables, columns with PK/FK/nullable flags, and FK relationships).

    The SQL is re-parsed on demand from MinIO — fast enough for DDL-only files.
    Available for any job that has a RAW_UPLOAD artifact (status >= QUEUED).
    """
    # Validate job ownership
    result = await db.execute(
        select(AnalysisJob, Project)
        .join(Project, AnalysisJob.project_id == Project.id)
        .where(AnalysisJob.id == job_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    job, project = row
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch the raw SQL artifact from MinIO
    result_artifact = await db.execute(
        select(JobArtifact).where(
            JobArtifact.job_id == job.id,
            JobArtifact.artifact_type == ArtifactType.RAW_UPLOAD,
        )
    )
    artifact = result_artifact.scalars().first()
    if not artifact:
        raise HTTPException(
            status_code=404,
            detail="No SQL artifact found for this job. Upload may still be in progress.",
        )

    # Download + parse SQL
    try:
        response = minio_service.client.get_object(
            settings.MINIO_BUCKET_NAME, artifact.storage_path
        )
        sql_content = response.read().decode("utf-8")
        response.close()
        response.release_conn()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve SQL from storage: {str(e)}",
        )

    # Full ERD-aware parse (PK · FK · nullable · unique)
    raw_schema = parse_sql_to_erd_schema(sql_content)

    # Map raw dicts → typed Pydantic models
    erd_tables: list[ERDTable] = []
    for tbl in raw_schema.get("tables", []):
        erd_tables.append(
            ERDTable(
                name=tbl["name"],
                columns=[ERDColumn(**col) for col in tbl.get("columns", [])],
                foreign_keys=[ERDForeignKey(**fk) for fk in tbl.get("foreign_keys", [])],
            )
        )

    total_relationships = sum(len(t.foreign_keys) for t in erd_tables)

    return ERDSchemaResponse(
        job_id=job_id,
        tables=erd_tables,
        errors=raw_schema.get("errors", []),
        missing_fk_warnings=raw_schema.get("missing_fk_warnings", []),
        has_missing_references=raw_schema.get("has_missing_references", False),
        table_count=len(erd_tables),
        relationship_count=total_relationships,
    )

