import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Enum, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum

class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    FINALIZED = "FINALIZED"

class AppContext(str, enum.Enum):
    READ_HEAVY = "READ_HEAVY"
    WRITE_HEAVY = "WRITE_HEAVY"

class ArtifactType(str, enum.Enum):
    RAW_UPLOAD = "RAW_UPLOAD"
    SANITIZED_JSON = "SANITIZED_JSON"
    OPTIMIZED_SQL = "OPTIMIZED_SQL"

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    original_filename = Column(String(255), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED)
    app_context = Column(Enum(AppContext), nullable=False)
    db_dialect = Column(String(50), nullable=True)
    ai_model_used = Column(String(50), nullable=True)
    tokens_used = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

class JobArtifact(Base):
    __tablename__ = "job_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id"))
    artifact_type = Column(Enum(ArtifactType), nullable=False)
    storage_path = Column(String(512), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
