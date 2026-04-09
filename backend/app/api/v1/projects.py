from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.job import Project, AnalysisJob
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListItemResponse
from app.schemas.job import JobSummaryResponse

router = APIRouter()


async def get_project_or_404(
    project_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Project:
    """
    Shared helper: fetch project by ID and validate ownership.
    Raises 404 if not found, 403 if not owned by current_user.
    Centralizes security logic to avoid repetition across endpoints.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project.")
    return project


@router.get("/", response_model=List[ProjectListItemResponse])
async def read_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
) -> List[ProjectListItemResponse]:
    """
    Retrieve all projects with job count.
    Uses a single LEFT JOIN + GROUP BY — avoids N+1 query problem.
    """
    stmt = (
        select(Project, func.count(AnalysisJob.id).label("job_count"))
        .outerjoin(AnalysisJob, AnalysisJob.project_id == Project.id)
        .where(Project.user_id == current_user.id)
        .group_by(Project.id)
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        ProjectListItemResponse(
            id=proj.id,
            name=proj.name,
            description=proj.description,
            user_id=proj.user_id,
            created_at=proj.created_at,
            job_count=count,
        )
        for proj, count in rows
    ]


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Create a new project. Name is validated (no blank) by the Pydantic schema."""
    project = Project(
        name=project_in.name,
        description=project_in.description,
        user_id=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    # Explicitly serialize to Pydantic to avoid returning raw ORM state
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def read_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """
    Get a single project by ID.
    Used by the frontend project detail page to restore state after page refresh.
    """
    project = await get_project_or_404(project_id, current_user, db)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """
    Update project name and/or description.
    Name validation (no blank) is enforced by ProjectUpdate schema.
    Only fields explicitly provided in the request body are updated (partial update).
    """
    project = await get_project_or_404(project_id, current_user, db)
    # Use model_fields_set to only update fields that were actually sent in the request
    update_data = project_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Delete project and all related data (jobs, artifacts).
    Cascade deletes are handled at the database level via ON DELETE CASCADE.
    Returns 204 No Content — FastAPI will NOT serialize any return value.
    """
    project = await get_project_or_404(project_id, current_user, db)
    await db.delete(project)
    await db.commit()
    # Explicit return None — no response body for 204


@router.get("/{project_id}/jobs", response_model=List[JobSummaryResponse])
async def read_project_jobs(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
) -> List[JobSummaryResponse]:
    """
    Get all analysis jobs for a project, most recent first.
    Ownership is validated via get_project_or_404 before querying jobs.
    """
    # Security: verify ownership before returning any job data
    await get_project_or_404(project_id, current_user, db)

    result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.project_id == project_id)
        .order_by(AnalysisJob.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    jobs = result.scalars().all()

    # Explicitly serialize each ORM object to Pydantic — prevents raw ORM leakage
    return [JobSummaryResponse.model_validate(job) for job in jobs]
