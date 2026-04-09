"""
Unit tests for the Celery worker business logic.

Tests exercise _process_analysis_job_async and _finalize_job_async directly,
bypassing the Celery machinery and mocking all external services
(PostgreSQL, MinIO, LLM, Docker sandbox) so they run fully offline.
"""
from __future__ import annotations

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.worker import _process_analysis_job_async, _finalize_job_async
from app.models.job import JobStatus
from app.models.suggestion import RiskLevel, ActionStatus
from app.services.llm_engine import AnalysisUsage


# ── Mock-builder helpers ──────────────────────────────────────────────────────

def _scalars_first(value: object) -> MagicMock:
    """Mock execute() result whose .scalars().first() returns *value*."""
    m = MagicMock()
    m.scalars.return_value.first.return_value = value
    return m


def _scalars_all(items: list) -> MagicMock:
    """Mock execute() result whose .scalars().all() returns *items*."""
    m = MagicMock()
    m.scalars.return_value.all.return_value = items
    return m


def _make_session_factory(mock_db: AsyncMock) -> MagicMock:
    """
    Return a callable that mimics sessionmaker() for use inside worker functions.

    The worker calls it as:
        async with session_factory() as db:

    So session_factory() must return an async context manager that yields mock_db.
    """
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_db)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


def _make_mock_db() -> AsyncMock:
    """Fresh async DB session mock; add() is synchronous (matches SQLAlchemy)."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _minio_response(content: bytes = b"CREATE TABLE t (id INT PRIMARY KEY);") -> MagicMock:
    """Minimal mock of a MinIO get_object() response object."""
    resp = MagicMock()
    resp.read.return_value = content
    return resp


# ── _process_analysis_job_async ───────────────────────────────────────────────

class TestProcessAnalysisJobAsync:
    """Unit tests for the core analysis workflow."""

    @pytest.mark.asyncio
    async def test_unknown_job_id_exits_silently(self):
        """If the job row is not found the function returns without committing."""
        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(return_value=_scalars_first(None))

        await _process_analysis_job_async(
            str(uuid.uuid4()), _make_session_factory(mock_db)
        )

        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_artifact_marks_job_failed(self):
        """If the RAW_UPLOAD artifact is absent the job must be marked FAILED."""
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.db_dialect = "postgresql"
        mock_job.app_context.value = "READ_HEAVY"

        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(
            side_effect=[
                _scalars_first(mock_job),  # job found
                _scalars_first(None),       # artifact missing → exception raised
            ]
        )

        with patch("app.worker.minio_service"):
            await _process_analysis_job_async(
                str(mock_job.id), _make_session_factory(mock_db)
            )

        assert mock_job.status == JobStatus.FAILED
        assert mock_job.error_message is not None

    @pytest.mark.asyncio
    async def test_happy_path_saves_suggestions_and_completes(self):
        """
        End-to-end happy path:
        - Job and artifact found
        - MinIO returns SQL content
        - Parser + LLM return one suggestion
        - That suggestion is persisted and job is marked COMPLETED
        """
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.db_dialect = "postgresql"
        mock_job.app_context.value = "READ_HEAVY"

        mock_artifact = MagicMock()
        mock_artifact.storage_path = "uid/jid/clean.sql"

        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(
            side_effect=[
                _scalars_first(mock_job),
                _scalars_first(mock_artifact),
            ]
        )

        mock_suggestion = MagicMock()
        mock_suggestion.table_name = "t"
        mock_suggestion.issue = "Missing index on foreign key"
        mock_suggestion.suggestion = "Add an index on t.user_id"
        mock_suggestion.risk_level = RiskLevel.MEDIUM
        mock_suggestion.confidence = 0.9
        mock_suggestion.sql_patch = "CREATE INDEX idx_t_user ON t(user_id);"

        mock_minio = MagicMock()
        mock_minio.client.get_object.return_value = _minio_response()

        with (
            patch("app.worker.minio_service", mock_minio),
            patch("app.worker.parse_sql_to_schema", return_value={"tables": [], "errors": []}),
            patch("app.worker.llm_engine") as mock_llm,
        ):
            mock_llm.analyze_schema.return_value = AnalysisUsage(
                suggestions=[mock_suggestion],
                tokens_used=150,
                model_name="gemini-2.5-flash-lite",
            )
            await _process_analysis_job_async(
                str(mock_job.id), _make_session_factory(mock_db)
            )

        assert mock_job.status == JobStatus.COMPLETED
        assert mock_db.add.call_count == 1    # one AISuggestion persisted
        assert mock_db.commit.call_count == 2  # PROCESSING commit + COMPLETED commit


# ── _finalize_job_async ───────────────────────────────────────────────────────

class TestFinalizeJobAsync:
    """Unit tests for the sandbox validation + self-correction workflow."""

    def _build_db(
        self,
        mock_job: MagicMock,
        suggestions: list,
        mock_artifact: MagicMock,
        mock_project: MagicMock | None = None,
    ) -> AsyncMock:
        """
        Configure mock_db.execute side_effect for the standard finalize sequence:
          1. job lookup (scalars first)
          2. accepted suggestions (scalars all)
          3. artifact lookup (scalars first)
          4. project lookup (scalars first) — only in the success path
        """
        mock_db = _make_mock_db()
        side_effects = [
            _scalars_first(mock_job),
            _scalars_all(suggestions),
            _scalars_first(mock_artifact),
        ]
        if mock_project is not None:
            side_effects.append(_scalars_first(mock_project))
        mock_db.execute = AsyncMock(side_effect=side_effects)
        return mock_db

    def _make_artifacts(self) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Return (mock_job, mock_suggestion, mock_artifact) with sensible defaults."""
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.project_id = uuid.uuid4()
        mock_job.db_dialect = "postgresql"

        mock_suggestion = MagicMock()
        mock_suggestion.issue = "Missing index"
        mock_suggestion.sql_patch = "CREATE INDEX idx_t ON t(id);"
        mock_suggestion.table_name = "t"
        mock_suggestion.action_status = ActionStatus.ACCEPTED

        mock_artifact = MagicMock()
        mock_artifact.storage_path = "uid/jid/clean.sql"

        return mock_job, mock_suggestion, mock_artifact

    @pytest.mark.asyncio
    async def test_unknown_job_id_exits_silently(self):
        """If the job row is not found the function returns without committing."""
        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(return_value=_scalars_first(None))

        await _finalize_job_async(
            str(uuid.uuid4()), _make_session_factory(mock_db)
        )

        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_sandbox_success_finalizes_job_and_uploads_result(self):
        """Happy path: sandbox passes on first attempt → job FINALIZED, file uploaded."""
        mock_job, mock_suggestion, mock_artifact = self._make_artifacts()
        mock_project = MagicMock()
        mock_project.user_id = uuid.uuid4()

        mock_db = self._build_db(mock_job, [mock_suggestion], mock_artifact, mock_project)

        mock_minio = MagicMock()
        mock_minio.client.get_object.return_value = _minio_response()

        with (
            patch("app.worker.minio_service", mock_minio),
            patch("app.worker.sandbox_service") as mock_sandbox,
        ):
            mock_sandbox.run_sql_validation.return_value = {"success": True, "logs": ""}
            await _finalize_job_async(str(mock_job.id), _make_session_factory(mock_db))

        assert mock_job.status == JobStatus.FINALIZED
        mock_minio.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_sandbox_fail_then_self_correction_succeeds(self):
        """
        First sandbox run fails → LLM self-corrects → second sandbox run passes
        → job FINALIZED and self-corrected file uploaded.
        """
        mock_job, mock_suggestion, mock_artifact = self._make_artifacts()
        mock_project = MagicMock()
        mock_project.user_id = uuid.uuid4()

        mock_db = self._build_db(mock_job, [mock_suggestion], mock_artifact, mock_project)

        mock_minio = MagicMock()
        mock_minio.client.get_object.return_value = _minio_response()

        with (
            patch("app.worker.minio_service", mock_minio),
            patch("app.worker.sandbox_service") as mock_sandbox,
            patch("app.worker.llm_engine") as mock_llm,
        ):
            mock_sandbox.run_sql_validation.side_effect = [
                {"success": False, "logs": "ERROR: syntax error near BAD"},
                {"success": True, "logs": ""},
            ]
            mock_llm.self_correct_sql.return_value = "CREATE INDEX idx_t ON t(id);"
            await _finalize_job_async(str(mock_job.id), _make_session_factory(mock_db))

        assert mock_job.status == JobStatus.FINALIZED
        mock_llm.self_correct_sql.assert_called_once()
        mock_minio.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_exhausted_retries_marks_job_failed_without_upload(self):
        """
        All self-correction retries exhausted → job FAILED and no file uploaded.
        The project lookup is skipped because we never reach the success branch.
        """
        mock_job, mock_suggestion, mock_artifact = self._make_artifacts()

        # No mock_project: project is only fetched in the success path
        mock_db = self._build_db(mock_job, [mock_suggestion], mock_artifact)

        mock_minio = MagicMock()
        mock_minio.client.get_object.return_value = _minio_response()

        with (
            patch("app.worker.minio_service", mock_minio),
            patch("app.worker.sandbox_service") as mock_sandbox,
            patch("app.worker.llm_engine") as mock_llm,
        ):
            # Every sandbox attempt fails
            mock_sandbox.run_sql_validation.return_value = {
                "success": False,
                "logs": "persistent syntax error",
            }
            mock_llm.self_correct_sql.return_value = "ATTEMPT FIX"
            await _finalize_job_async(str(mock_job.id), _make_session_factory(mock_db))

        assert mock_job.status == JobStatus.FAILED
        mock_minio.upload_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_exception_during_correction_marks_failed(self):
        """LLM self_correct_sql raises → worker breaks out of loop → job FAILED."""
        mock_job, mock_suggestion, mock_artifact = self._make_artifacts()
        mock_db = self._build_db(mock_job, [mock_suggestion], mock_artifact)

        mock_minio = MagicMock()
        mock_minio.client.get_object.return_value = _minio_response()

        with (
            patch("app.worker.minio_service", mock_minio),
            patch("app.worker.sandbox_service") as mock_sandbox,
            patch("app.worker.llm_engine") as mock_llm,
        ):
            mock_sandbox.run_sql_validation.return_value = {
                "success": False, "logs": "syntax error"
            }
            mock_llm.self_correct_sql.side_effect = Exception("LLM API down")
            await _finalize_job_async(str(mock_job.id), _make_session_factory(mock_db))

        assert mock_job.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_empty_corrected_sql_breaks_correction_loop(self):
        """LLM returns empty corrected_sql → uncorrectable, loop breaks → job FAILED."""
        mock_job, mock_suggestion, mock_artifact = self._make_artifacts()
        mock_db = self._build_db(mock_job, [mock_suggestion], mock_artifact)

        mock_minio = MagicMock()
        mock_minio.client.get_object.return_value = _minio_response()

        with (
            patch("app.worker.minio_service", mock_minio),
            patch("app.worker.sandbox_service") as mock_sandbox,
            patch("app.worker.llm_engine") as mock_llm,
        ):
            mock_sandbox.run_sql_validation.return_value = {
                "success": False, "logs": "unknown table"
            }
            mock_llm.self_correct_sql.return_value = ""  # empty → uncorrectable
            await _finalize_job_async(str(mock_job.id), _make_session_factory(mock_db))

        assert mock_job.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_missing_artifact_in_finalize_marks_failed(self):
        """Artifact not found in finalize → raise inside try → outer except → job FAILED."""
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.project_id = uuid.uuid4()
        mock_job.db_dialect = "postgresql"

        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(side_effect=[
            _scalars_first(mock_job),
            _scalars_all([]),           # no suggestions
            _scalars_first(None),       # artifact not found → raises Exception
        ])

        with patch("app.worker.minio_service"):
            await _finalize_job_async(str(mock_job.id), _make_session_factory(mock_db))

        assert mock_job.status == JobStatus.FAILED


class TestProcessAnalysisJobErrorPaths:
    """Additional error-path coverage for _process_analysis_job_async."""

    @pytest.mark.asyncio
    async def test_llm_failure_marks_job_failed(self):
        """LLM analyze_schema raises → job status set to FAILED with error message."""
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.db_dialect = "postgresql"
        mock_job.app_context.value = "READ_HEAVY"

        mock_artifact = MagicMock()
        mock_artifact.storage_path = "uid/jid/clean.sql"

        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(side_effect=[
            _scalars_first(mock_job),
            _scalars_first(mock_artifact),
        ])

        mock_minio = MagicMock()
        mock_minio.client.get_object.return_value = _minio_response()

        with (
            patch("app.worker.minio_service", mock_minio),
            patch("app.worker.parse_sql_to_schema", return_value={"tables": [], "errors": []}),
            patch("app.worker.llm_engine") as mock_llm,
        ):
            mock_llm.analyze_schema.side_effect = Exception("Gemini rate limit exceeded")
            await _process_analysis_job_async(
                str(mock_job.id), _make_session_factory(mock_db)
            )

        assert mock_job.status == JobStatus.FAILED
        assert "Gemini rate limit" in mock_job.error_message


class TestCeleryWrappers:
    """Tests for the Celery sync wrapper tasks (process_analysis_job, finalize_job)."""

    def test_process_analysis_job_calls_async_function(self):
        """process_analysis_job creates a loop, runs async function, then closes loop."""
        from app.worker import process_analysis_job

        mock_engine = MagicMock()
        with (
            patch("app.worker._make_session_factory", return_value=(mock_engine, MagicMock())),
            patch("app.worker._process_analysis_job_async", new=MagicMock()),
            patch("app.worker.asyncio") as mock_asyncio,
        ):
            mock_loop = MagicMock()
            mock_asyncio.new_event_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = None

            process_analysis_job("test-job-id")

            mock_asyncio.new_event_loop.assert_called_once()
            mock_loop.close.assert_called_once()

    def test_process_analysis_job_handles_critical_exception(self):
        """Exception from async function is logged; loop.close() is always called."""
        from app.worker import process_analysis_job

        call_count = [0]

        def _run(coro):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("database unreachable")

        mock_engine = MagicMock()
        with (
            patch("app.worker._make_session_factory", return_value=(mock_engine, MagicMock())),
            patch("app.worker._process_analysis_job_async", new=MagicMock()),
            patch("app.worker.asyncio") as mock_asyncio,
        ):
            mock_loop = MagicMock()
            mock_asyncio.new_event_loop.return_value = mock_loop
            mock_loop.run_until_complete.side_effect = _run

            process_analysis_job("bad-job-id")  # must NOT propagate exception

            mock_loop.close.assert_called_once()

    def test_finalize_job_calls_async_function(self):
        """finalize_job creates a loop, runs async function, then closes loop."""
        from app.worker import finalize_job

        mock_engine = MagicMock()
        with (
            patch("app.worker._make_session_factory", return_value=(mock_engine, MagicMock())),
            patch("app.worker._finalize_job_async", new=MagicMock()),
            patch("app.worker.asyncio") as mock_asyncio,
        ):
            mock_loop = MagicMock()
            mock_asyncio.new_event_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = None

            finalize_job("test-job-id")

            mock_asyncio.new_event_loop.assert_called_once()
            mock_loop.close.assert_called_once()

    def test_finalize_job_handles_critical_exception(self):
        """Exception from async function is logged; loop.close() is always called."""
        from app.worker import finalize_job

        call_count = [0]

        def _run(coro):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("sandbox service down")

        mock_engine = MagicMock()
        with (
            patch("app.worker._make_session_factory", return_value=(mock_engine, MagicMock())),
            patch("app.worker._finalize_job_async", new=MagicMock()),
            patch("app.worker.asyncio") as mock_asyncio,
        ):
            mock_loop = MagicMock()
            mock_asyncio.new_event_loop.return_value = mock_loop
            mock_loop.run_until_complete.side_effect = _run

            finalize_job("bad-job-id")  # must NOT propagate exception

            mock_loop.close.assert_called_once()
