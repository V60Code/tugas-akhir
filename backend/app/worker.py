import asyncio
import uuid
import logging
import traceback
from celery import Celery
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# --- Imports Internal ---
from app.core.config import settings
from app.models.job import AnalysisJob, JobStatus, JobArtifact, ArtifactType, Project
from app.models.suggestion import AISuggestion, RiskLevel, ActionStatus, SandboxLog
from app.services.storage import minio_service
from app.services.parser import parse_sql_to_schema
from app.services.llm_engine import llm_engine, MAX_SELF_CORRECTION_RETRIES
from app.services.sandbox import sandbox_service

# --- Logging Setup ---
# Configure logging to output to stdout so it shows in Docker logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- Celery Initialization ---
celery = Celery(
    "app.worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# --- Celery Configuration ---
celery.conf.update(
    task_default_queue='celery',
    task_routes={
        'app.worker.process_analysis_job': {'queue': 'celery'},
        'app.worker.finalize_job': {'queue': 'celery'},
    },
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Delimiter inserted between the original DDL and the AI-generated patch section.
# Also used by the self-correction loop to locate and replace the patch block.
_AI_SECTION_MARKER = "/* --- AI OPTIMIZATIONS --- */"


def _make_session_factory():
    """
    Create a brand-new async engine + session factory.

    WHY: asyncpg connections are bound to the event loop that created them.
    Celery uses multiprocessing (fork), so each task invocation may run on a
    different OS process with a fresh event loop. Reusing the module-level
    engine (which holds asyncpg connections from the parent loop) causes:
      - RuntimeError: Future attached to a different loop
      - InterfaceError: another operation is in progress

    Solution: create a disposable engine per task, then dispose it after use.
    The overhead is tiny (one TCP connection open/close) vs the correctness gain.
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,          # Reduce noise in worker logs
        pool_size=1,         # Single connection is enough per task
        max_overflow=0,
    )
    factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, factory

# --- Business Logic: Process Analysis Job ---
async def _process_analysis_job_async(job_id: str, session_factory):
    logger.info(f"Starting async processing for Job ID: {job_id}")
    
    async with session_factory() as db:
        job = None
        try:
            # Step 1: Fetch Job
            logger.info("Step 1: Fetching Job...")
            result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id)))
            job = result.scalars().first()
            
            if not job:
                logger.error(f"Job {job_id} not found in database.")
                return

            # Step 2: Update Status -> PROCESSING
            logger.info(f"Step 2: Updating Status to PROCESSING for {job_id}")
            job.status = JobStatus.PROCESSING
            await db.commit()

            # Step 3: Download File
            logger.info("Step 3: Fetching Artifact and Downloading File...")
            result_artifact = await db.execute(
                select(JobArtifact).where(
                    JobArtifact.job_id == job.id, 
                    JobArtifact.artifact_type == ArtifactType.RAW_UPLOAD
                )
            )
            artifact = result_artifact.scalars().first()
            
            if not artifact:
                raise Exception("Raw upload artifact not found for this job.")

            logger.info(f"Downloading from MinIO path: {artifact.storage_path}")
            response = minio_service.client.get_object(settings.MINIO_BUCKET_NAME, artifact.storage_path)
            sql_content = response.read().decode('utf-8')
            response.close()
            response.release_conn()
            
            # Step 4: Parse SQL
            logger.info("Step 4: Parsing SQL Content...")
            schema = parse_sql_to_schema(sql_content, dialect=job.db_dialect)
            logger.info(f"Parsed schema with {len(schema.get('tables', []))} tables, {len(schema.get('errors', []))} warnings.")

            # Step 5: AI Analysis
            logger.info(f"Step 5: Analyzing with AI (Context: {job.app_context.value})...")
            analysis = llm_engine.analyze_schema(
                schema,
                job.app_context.value,
                db_dialect=job.db_dialect or "mysql",
            )
            suggestions = analysis.suggestions
            logger.info(f"AI returned {len(suggestions)} suggestions.")

            # Step 6: Save Results
            logger.info("Step 6: Saving Suggestions to Database...")
            for s in suggestions:
                suggestion_record = AISuggestion(
                    job_id=job.id,
                    table_name=s.table_name,
                    issue=s.issue,
                    suggestion=s.suggestion,
                    risk_level=s.risk_level,
                    confidence=s.confidence,
                    sql_patch=s.sql_patch
                )
                db.add(suggestion_record)

            # Step 7: Complete
            logger.info("Step 7: Completing Job...")
            job.status = JobStatus.COMPLETED
            job.tokens_used = analysis.tokens_used
            job.ai_model_used = analysis.model_name
            await db.commit()
            logger.info(f"Job {job_id} COMPLETED successfully.")

        except Exception as e:
            logger.error(f"Job {job_id} FAILED during processing: {str(e)}")
            logger.error(traceback.format_exc())
            
            if job:
                job.status = JobStatus.FAILED
                job.error_message = f"{str(e)}"
                await db.commit()

# --- Business Logic: Finalize Job (Sandbox) ---
async def _finalize_job_async(job_id: str, session_factory):
    logger.info(f"Starting async finalization for Job ID: {job_id}")
    
    async with session_factory() as db:
        job = None
        try:
            # 1. Fetch Job
            result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id)))
            job = result.scalars().first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            # 2. Fetch Suggestions
            logger.info("Fetching accepted suggestions...")
            suggestions_result = await db.execute(
                select(AISuggestion).where(
                    AISuggestion.job_id == job.id,
                    AISuggestion.action_status == ActionStatus.ACCEPTED
                )
            )
            suggestions = suggestions_result.scalars().all()

            # 3. Get Original SQL
            logger.info("Fetching original SQL artifact...")
            result_artifact = await db.execute(
                select(JobArtifact).where(
                    JobArtifact.job_id == job.id, 
                    JobArtifact.artifact_type == ArtifactType.RAW_UPLOAD
                )
            )
            artifact = result_artifact.scalars().first()
            if not artifact:
                raise Exception("Original artifact not found")
                
            response = minio_service.client.get_object(settings.MINIO_BUCKET_NAME, artifact.storage_path)
            original_sql = response.read().decode('utf-8')
            response.close()
            response.release_conn()

            # 4. Patch SQL
            logger.info(f"Patching SQL with {len(suggestions)} suggestions...")
            optimized_sql = original_sql + f"\n\n{_AI_SECTION_MARKER}\n"
            for s in suggestions:
                optimized_sql += f"\n-- Issue: {s.issue}\n"
                optimized_sql += f"{s.sql_patch}\n"
            
            # 5. Sandbox Validation with Self-Correction loop
            # ─────────────────────────────────────────────────────────────────
            # Strategy:
            #   1. Run sandbox on the full optimized_sql.
            #   2. If it passes → FINALIZED.
            #   3. If it fails  → ask LLM to self-correct the *failing patches* (not
            #      the original DDL) up to MAX_SELF_CORRECTION_RETRIES times.
            #   4. If still failing after all retries → FAILED with a full error log.
            # ─────────────────────────────────────────────────────────────────
            dialect = job.db_dialect or "mysql"
            current_sql = optimized_sql
            validation_result = None
            self_correction_attempted = False
            correction_log: list[str] = []

            for attempt in range(MAX_SELF_CORRECTION_RETRIES + 1):
                logger.info(
                    f"[Sandbox] Running validation "
                    f"(attempt {attempt + 1}/{MAX_SELF_CORRECTION_RETRIES + 1}) for Job {job_id}..."
                )
                validation_result = sandbox_service.run_sql_validation(current_sql, dialect)
                logger.info(f"[Sandbox] Result: success={validation_result.get('success')}")

                if validation_result["success"]:
                    break  # Validation passed — exit retry loop

                if attempt >= MAX_SELF_CORRECTION_RETRIES:
                    # All retries exhausted — do not attempt another LLM call
                    logger.warning(
                        f"[Sandbox] Job {job_id} exhausted {MAX_SELF_CORRECTION_RETRIES} "
                        f"self-correction retries. Marking FAILED."
                    )
                    break

                # ── Self-Correction ───────────────────────────────────────────
                error_log = validation_result.get("logs", "")[:5000]
                logger.info(
                    f"[Self-Correction] Sandbox failed — invoking LLM correction "
                    f"(attempt {attempt + 1}/{MAX_SELF_CORRECTION_RETRIES})..."
                )
                self_correction_attempted = True

                try:
                    # Build a combined patch string representing the "AI section" only
                    ai_section_start = current_sql.find(_AI_SECTION_MARKER)
                    ai_patch_section = (
                        current_sql[ai_section_start:] if ai_section_start != -1 else current_sql
                    )

                    corrected_patch = llm_engine.self_correct_sql(
                        original_sql_patch=ai_patch_section,
                        error_log=error_log,
                        table_name=", ".join(s.table_name for s in suggestions),
                        attempt=attempt + 1,
                        db_dialect=dialect,
                    )

                    if not corrected_patch:
                        log_entry = (
                            f"[Self-Correction] Attempt {attempt + 1}: LLM returned empty patch — "
                            f"patch deemed uncorrectable."
                        )
                        logger.warning(log_entry)
                        correction_log.append(log_entry)
                        break   # Empty corrected SQL means LLM gave up

                    # Rebuild full SQL: keep original DDL + corrected AI section
                    if ai_section_start != -1:
                        original_ddl_section = current_sql[:ai_section_start]
                        current_sql = (
                            original_ddl_section
                            + "/* --- AI OPTIMIZATIONS (self-corrected) --- */\n\n"
                            + corrected_patch
                        )
                    else:
                        current_sql = corrected_patch

                    log_entry = f"[Self-Correction] Attempt {attempt + 1}: new SQL built ({len(current_sql)} chars)"
                    logger.info(log_entry)
                    correction_log.append(log_entry)

                except Exception as correction_err:
                    log_entry = f"[Self-Correction] Attempt {attempt + 1}: LLM call failed — {correction_err}"
                    logger.error(log_entry)
                    correction_log.append(log_entry)
                    break  # Don't retry further if LLM itself is broken

            # ── End of retry loop ─────────────────────────────────────────────

            # 6. Save Sandbox Log (records final attempt + any correction history)
            combined_log = validation_result.get("logs", "")
            if correction_log:
                combined_log = (
                    "=== SELF-CORRECTION HISTORY ===\n"
                    + "\n".join(correction_log)
                    + "\n\n=== FINAL SANDBOX LOG ===\n"
                    + combined_log
                )

            sandbox_log = SandboxLog(
                job_id=job.id,
                is_success=validation_result["success"],
                container_log=combined_log[:100000],
                was_self_corrected=self_correction_attempted,
                self_correction_count=len(correction_log),
            )
            db.add(sandbox_log)

            # 7. Decision
            if validation_result["success"]:
                proj_res = await db.execute(select(Project).where(Project.id == job.project_id))
                project = proj_res.scalars().first()
                user_id_str = str(project.user_id) if project else "unknown"

                object_name = f"{user_id_str}/{job.id}/optimized.sql"

                # Flag in filename if self-correction was needed
                suffix = " (self-corrected)" if self_correction_attempted else ""
                logger.info(f"Uploading optimized SQL{suffix} to {object_name}...")
                minio_service.upload_file(
                    current_sql.encode("utf-8"), object_name, content_type="application/sql"
                )

                opt_artifact = JobArtifact(
                    job_id=job.id,
                    artifact_type=ArtifactType.OPTIMIZED_SQL,
                    storage_path=object_name,
                    file_size_bytes=len(current_sql),
                )
                db.add(opt_artifact)

                job.status = JobStatus.FINALIZED
                logger.info(
                    f"Job {job_id} FINALIZED{suffix} successfully."
                )

            else:
                error_summary = validation_result.get("logs", "")[:500]
                job.status = JobStatus.FAILED
                job.error_message = (
                    f"Sandbox validation failed after "
                    f"{MAX_SELF_CORRECTION_RETRIES} self-correction attempt(s). "
                    f"Last error: {error_summary}"
                )
                logger.warning(f"Job {job_id} FAILED after all correction attempts.")

            await db.commit()

        except Exception as e:
            logger.error(f"Finalize Job {job_id} Error: {e}")
            logger.error(traceback.format_exc())
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                await db.commit()


# --- Celery Task Wrappers ---

@celery.task(name="app.worker.process_analysis_job")
def process_analysis_job(job_id: str):
    """
    Celery sync wrapper for processing analysis job.

    Creates a fresh event loop + DB engine per invocation to avoid asyncpg
    connection pool conflicts across Celery fork workers.
    """
    logger.info(f"Received Analysis Task for Job: {job_id}")
    engine, factory = _make_session_factory()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_process_analysis_job_async(job_id, factory))
    except Exception as e:
        logger.critical(f"CRITICAL WORKER FAILURE: {e}")
        logger.critical(traceback.format_exc())
    finally:
        # Dispose engine to close all DB connections cleanly before loop closes
        loop.run_until_complete(engine.dispose())
        loop.close()


@celery.task(name="app.worker.finalize_job")
def finalize_job(job_id: str):
    """
    Celery sync wrapper for finalizing job.

    Creates a fresh event loop + DB engine per invocation to avoid asyncpg
    connection pool conflicts across Celery fork workers.
    """
    logger.info(f"Received Finalize Task for Job: {job_id}")
    engine, factory = _make_session_factory()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_finalize_job_async(job_id, factory))
    except Exception as e:
        logger.critical(f"CRITICAL WORKER FAILURE: {e}")
        logger.critical(traceback.format_exc())
    finally:
        # Dispose engine to close all DB connections cleanly before loop closes
        loop.run_until_complete(engine.dispose())
        loop.close()