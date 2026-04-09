import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Enum, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base
import enum

class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ActionStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

class AISuggestion(Base):
    __tablename__ = "ai_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id"))
    table_name = Column(String(100), nullable=False)
    issue = Column(String(255), nullable=False)
    suggestion = Column(Text, nullable=False)
    risk_level = Column(Enum(RiskLevel), nullable=False)
    confidence = Column(Float, nullable=True)
    action_status = Column(Enum(ActionStatus), default=ActionStatus.PENDING)
    sql_patch = Column(Text, nullable=False)

class SandboxLog(Base):
    __tablename__ = "sandbox_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id"))
    attempt_number = Column(Integer, default=1)
    is_success = Column(Boolean, nullable=False)
    container_log = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    # Tracks whether AI self-correction was used and how many iterations it took
    was_self_corrected = Column(Boolean, default=False, nullable=False)
    self_correction_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
