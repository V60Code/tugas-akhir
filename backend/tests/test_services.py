"""
Unit tests for MinioService (storage.py) and SandboxService (sandbox.py).

All external I/O (Minio client, Docker) is mocked at the client level.
These tests run completely offline — no infrastructure required.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from app.services.storage import MinioService
from app.services.sandbox import SandboxService
from app.core.config import settings
from app.models.suggestion import RiskLevel


# ── MinioService ──────────────────────────────────────────────────────────────

class TestMinioService:

    def test_client_property_lazy_initializes_on_first_access(self):
        """_client is None at construction; first access creates the Minio client."""
        service = MinioService()
        assert service._client is None

        with patch("app.services.storage.Minio") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            client = service.client

        mock_cls.assert_called_once_with(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
        )
        assert client is mock_instance

    def test_client_property_returns_cached_instance(self):
        """Second access returns the same object without re-initialising."""
        service = MinioService()
        mock_client = MagicMock()
        service._client = mock_client
        assert service.client is mock_client

    def test_ensure_bucket_creates_when_missing(self):
        service = MinioService()
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        service._client = mock_client

        service.ensure_bucket_exists()

        mock_client.bucket_exists.assert_called_once_with(settings.MINIO_BUCKET_NAME)
        mock_client.make_bucket.assert_called_once_with(settings.MINIO_BUCKET_NAME)

    def test_ensure_bucket_skips_create_when_already_exists(self):
        service = MinioService()
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        service._client = mock_client

        service.ensure_bucket_exists()

        mock_client.make_bucket.assert_not_called()

    def test_upload_file_returns_object_name_on_success(self):
        service = MinioService()
        mock_client = MagicMock()
        service._client = mock_client

        data = b"CREATE TABLE t (id INT);"
        result = service.upload_file(data, "user/job/clean.sql", "application/sql")

        mock_client.put_object.assert_called_once()
        call_args = mock_client.put_object.call_args[0]
        assert call_args[0] == settings.MINIO_BUCKET_NAME
        assert call_args[1] == "user/job/clean.sql"
        assert result == "user/job/clean.sql"

    def test_upload_file_propagates_exception_on_failure(self):
        service = MinioService()
        mock_client = MagicMock()
        mock_client.put_object.side_effect = Exception("connection refused")
        service._client = mock_client

        with pytest.raises(Exception, match="connection refused"):
            service.upload_file(b"data", "path/file.sql")

    def test_get_presigned_url_returns_url_on_success(self):
        service = MinioService()
        mock_client = MagicMock()
        mock_client.presigned_get_object.return_value = "http://minio:9000/bucket/path?sig=abc"
        service._client = mock_client

        url = service.get_presigned_url("path/to/file.sql")

        assert url == "http://minio:9000/bucket/path?sig=abc"
        mock_client.presigned_get_object.assert_called_once()

    def test_get_presigned_url_returns_none_on_failure(self):
        """S3Error (or any exception) during presign → returns None, does not raise."""
        service = MinioService()
        mock_client = MagicMock()
        mock_client.presigned_get_object.side_effect = Exception("key not found")
        service._client = mock_client

        url = service.get_presigned_url("missing/file.sql")

        assert url is None

    def test_ensure_bucket_raises_s3error_on_check(self):
        """If bucket_exists raises S3Error the exception is re-raised after logging."""
        service = MinioService()
        with patch("app.services.storage.Minio") as mock_cls, \
             patch("app.services.storage.S3Error", Exception):
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.bucket_exists.side_effect = Exception("bucket check failed")
            with pytest.raises(Exception, match="bucket check failed"):
                service.ensure_bucket_exists()

    def test_upload_file_raises_s3error_on_put(self):
        """If put_object raises S3Error the exception is re-raised after logging."""
        service = MinioService()
        with patch("app.services.storage.Minio") as mock_cls, \
             patch("app.services.storage.S3Error", Exception):
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.put_object.side_effect = Exception("s3 upload failed")
            with pytest.raises(Exception, match="s3 upload failed"):
                service.upload_file(b"data", "test.sql")


# ── SandboxService ────────────────────────────────────────────────────────────

class TestSandboxService:

    def test_client_property_returns_none_when_docker_unavailable(self):
        from docker.errors import DockerException

        service = SandboxService()
        with patch("docker.from_env", side_effect=DockerException("socket not found")):
            client = service.client

        assert client is None

    def test_client_property_returns_docker_client_when_available(self):
        service = SandboxService()
        mock_docker_client = MagicMock()

        with patch("docker.from_env", return_value=mock_docker_client):
            client = service.client

        assert client is mock_docker_client

    def test_run_sql_no_docker_client_returns_failure(self):
        """When the Docker socket is unavailable the service reports failure cleanly."""
        service = SandboxService()
        with patch.object(SandboxService, "client", new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = None
            result = service.run_sql_validation("CREATE TABLE t (id INT);")

        assert result["success"] is False
        assert "Docker client not available" in result["logs"]

    def test_run_sql_validation_success(self):
        """Full happy path: pg_isready returns 0, psql exits 0."""
        service = SandboxService()
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.run.return_value = mock_container

        # exec_run #1: pg_isready check — Docker SDK returns (exit_code, output) tuple
        # exec_run #2: psql execution — uses attribute access (.exit_code, .output)
        mock_container.exec_run.side_effect = [
            (0, b""),
            MagicMock(exit_code=0, output=b"CREATE TABLE"),
        ]

        with patch.object(SandboxService, "client", new_callable=PropertyMock) as mock_prop, \
             patch("app.services.sandbox.time.sleep"), \
             patch("app.services.sandbox.time.monotonic", return_value=0.0):
            mock_prop.return_value = mock_client
            result = service.run_sql_validation("CREATE TABLE t (id INT);")

        assert result["success"] is True
        mock_container.stop.assert_called_once_with(timeout=5)
        mock_container.remove.assert_called_once_with(force=True)

    def test_run_sql_validation_sql_error_returns_failure(self):
        """psql exits non-zero → success=False with error in logs."""
        service = SandboxService()
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.run.return_value = mock_container

        mock_container.exec_run.side_effect = [
            (0, b""),
            MagicMock(exit_code=1, output=b"ERROR:  syntax error at or near"),
        ]

        with patch.object(SandboxService, "client", new_callable=PropertyMock) as mock_prop, \
             patch("app.services.sandbox.time.sleep"), \
             patch("app.services.sandbox.time.monotonic", return_value=0.0):
            mock_prop.return_value = mock_client
            result = service.run_sql_validation("INVALID SQL;;")

        assert result["success"] is False
        assert "ERROR" in result["logs"]

    def test_run_sql_validation_exception_returns_failure(self):
        """Unexpected Docker exception (e.g. image pull fails) → graceful failure."""
        service = SandboxService()
        mock_client = MagicMock()
        mock_client.containers.run.side_effect = Exception("image pull failed")

        with patch.object(SandboxService, "client", new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = mock_client
            result = service.run_sql_validation("CREATE TABLE t (id INT);")

        assert result["success"] is False
        assert "Sandbox error" in result["logs"]

    def test_mysql_dialect_uses_mysql_image(self):
        """mysql dialect selects mysql:8 container image."""
        service = SandboxService()
        mock_client = MagicMock()
        mock_client.containers.run.side_effect = Exception("no image")

        with patch.object(SandboxService, "client", new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = mock_client
            service.run_sql_validation("CREATE TABLE t (id INT);", db_dialect="mysql")

        assert mock_client.containers.run.call_args[0][0] == "mysql:8"

    def test_pg_isready_retries_exhausted_returns_not_ready(self):
        """All pg_isready retries fail → 'Database container failed to become ready'."""
        service = SandboxService()
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_container.exec_run.return_value = (1, b"not ready")

        with patch.object(SandboxService, "client", new_callable=PropertyMock) as mock_prop, \
             patch("app.services.sandbox.time.sleep"), \
             patch("app.services.sandbox.time.monotonic", return_value=0.0):
            mock_prop.return_value = mock_client
            result = service.run_sql_validation("SELECT 1;")

        assert result["success"] is False
        assert "failed to become ready" in result["logs"]

    def test_global_timeout_in_pg_isready_loop(self):
        """Global timeout fires inside the pg_isready retry loop → timeout failure."""
        from app.services.sandbox import SANDBOX_TIMEOUT_SECONDS
        service = SandboxService()
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.run.return_value = mock_container

        calls = iter([0.0, float(SANDBOX_TIMEOUT_SECONDS)])

        with patch.object(SandboxService, "client", new_callable=PropertyMock) as mock_prop, \
             patch("app.services.sandbox.time.sleep"), \
             patch("app.services.sandbox.time.monotonic", side_effect=lambda: next(calls)):
            mock_prop.return_value = mock_client
            result = service.run_sql_validation("CREATE TABLE t (id INT);")

        assert result["success"] is False
        assert "timeout" in result["logs"].lower()

    def test_global_timeout_before_sql_execution(self):
        """Global timeout fires after DB is ready but before SQL runs → timeout failure."""
        from app.services.sandbox import SANDBOX_TIMEOUT_SECONDS
        service = SandboxService()
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_container.exec_run.return_value = (0, b"")  # pg_isready succeeds

        calls = iter([0.0, 0.0, float(SANDBOX_TIMEOUT_SECONDS + 1)])

        with patch.object(SandboxService, "client", new_callable=PropertyMock) as mock_prop, \
             patch("app.services.sandbox.time.sleep"), \
             patch("app.services.sandbox.time.monotonic", side_effect=lambda: next(calls)):
            mock_prop.return_value = mock_client
            result = service.run_sql_validation("CREATE TABLE t (id INT);")

        assert result["success"] is False
        assert "timeout" in result["logs"].lower()

    def test_cleanup_failure_does_not_propagate(self):
        """Container cleanup failure is caught and logged — main result is still returned."""
        service = SandboxService()
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_container.exec_run.side_effect = [
            (0, b""),                                          # pg_isready
            MagicMock(exit_code=0, output=b"CREATE TABLE"),   # psql
        ]
        mock_container.stop.side_effect = Exception("already stopped")

        with patch.object(SandboxService, "client", new_callable=PropertyMock) as mock_prop, \
             patch("app.services.sandbox.time.sleep"), \
             patch("app.services.sandbox.time.monotonic", return_value=0.0):
            mock_prop.return_value = mock_client
            result = service.run_sql_validation("CREATE TABLE t (id INT);")

        assert result["success"] is True


# ── LLMEngine.self_correct_sql ────────────────────────────────────────────────

class TestLLMEngineSelfCorrect:
    """Unit tests for the self-correction LLM call in llm_engine.py."""

    def _make_engine(self):
        """Build an LLMEngine without hitting Google API at init time."""
        with patch("app.services.llm_engine.ChatGoogleGenerativeAI"):
            from app.services.llm_engine import LLMEngine
            return LLMEngine()

    def test_self_correct_returns_corrected_sql(self):
        """Happy path: LLM returns valid JSON → corrected SQL is returned."""
        from app.services.llm_engine import SelfCorrectionResult
        engine = self._make_engine()

        mock_output = MagicMock()
        mock_output.content = '{"corrected_sql": "CREATE INDEX idx ON t(id);", "explanation": "Fixed syntax."}'
        engine._invoke_llm = MagicMock(return_value=mock_output)

        mock_result = SelfCorrectionResult(
            corrected_sql="CREATE INDEX idx ON t(id);", explanation="Fixed."
        )
        with patch("app.services.llm_engine.PydanticOutputParser") as mock_parser_cls:
            mock_parser_cls.return_value.get_format_instructions.return_value = ""
            mock_parser_cls.return_value.parse.return_value = mock_result
            result = engine.self_correct_sql(
                original_sql_patch="CREATE BAD INDEX;",
                error_log="ERROR: syntax error",
                table_name="t",
                attempt=1,
            )

        assert result == "CREATE INDEX idx ON t(id);"

    def test_self_correct_strips_markdown_json_fences(self):
        """LLM wraps output in ```json fences → they are stripped before parsing."""
        from app.services.llm_engine import SelfCorrectionResult
        engine = self._make_engine()

        mock_output = MagicMock()
        mock_output.content = '```json\n{"corrected_sql": "SELECT 1;", "explanation": "ok"}\n```'
        engine._invoke_llm = MagicMock(return_value=mock_output)

        mock_result = SelfCorrectionResult(corrected_sql="SELECT 1;", explanation="ok")
        with patch("app.services.llm_engine.PydanticOutputParser") as mock_parser_cls:
            mock_parser_cls.return_value.get_format_instructions.return_value = ""
            mock_parser_cls.return_value.parse.return_value = mock_result
            result = engine.self_correct_sql("BAD;", "err", "t", 1)

        assert result == "SELECT 1;"

    def test_self_correct_strips_plain_markdown_fences(self):
        """LLM wraps output in plain ``` fences → second block is extracted."""
        from app.services.llm_engine import SelfCorrectionResult
        engine = self._make_engine()

        mock_output = MagicMock()
        mock_output.content = '```\n{"corrected_sql": "SELECT 2;", "explanation": "ok"}\n```'
        engine._invoke_llm = MagicMock(return_value=mock_output)

        mock_result = SelfCorrectionResult(corrected_sql="SELECT 2;", explanation="ok")
        with patch("app.services.llm_engine.PydanticOutputParser") as mock_parser_cls:
            mock_parser_cls.return_value.get_format_instructions.return_value = ""
            mock_parser_cls.return_value.parse.return_value = mock_result
            result = engine.self_correct_sql("BAD;", "err", "t", 2)

        assert result == "SELECT 2;"

    def test_self_correct_reraises_on_llm_failure(self):
        """If _invoke_llm raises, self_correct_sql re-raises the same exception."""
        engine = self._make_engine()
        engine._invoke_llm = MagicMock(side_effect=Exception("LLM unavailable"))

        with patch("app.services.llm_engine.PydanticOutputParser") as mock_parser_cls:
            mock_parser_cls.return_value.get_format_instructions.return_value = ""
            with pytest.raises(Exception, match="LLM unavailable"):
                engine.self_correct_sql("BAD;", "err", "t", 1)


# ── _is_transient_llm_error ───────────────────────────────────────────────────

class TestIsTransientLlmError:
    """Unit tests for the module-level _is_transient_llm_error predicate."""

    def _fn(self):
        from app.services.llm_engine import _is_transient_llm_error
        return _is_transient_llm_error

    def test_connection_error_is_transient(self):
        assert self._fn()(ConnectionError("socket closed")) is True

    def test_timeout_error_is_transient(self):
        assert self._fn()(TimeoutError()) is True

    def test_os_error_is_transient(self):
        assert self._fn()(OSError("broken pipe")) is True

    def test_resource_exhausted_by_class_name_is_transient(self):
        class ResourceExhausted(Exception):
            pass
        assert self._fn()(ResourceExhausted("rate limit")) is True

    def test_service_unavailable_by_class_name_is_transient(self):
        class ServiceUnavailable(Exception):
            pass
        assert self._fn()(ServiceUnavailable()) is True

    def test_deadline_exceeded_by_class_name_is_transient(self):
        class DeadlineExceeded(Exception):
            pass
        assert self._fn()(DeadlineExceeded()) is True

    def test_value_error_is_not_transient(self):
        assert self._fn()(ValueError("bad input")) is False

    def test_generic_exception_is_not_transient(self):
        assert self._fn()(Exception("unknown")) is False


# ── LLMEngine._prepare_schema_for_llm ────────────────────────────────────────

class TestPrepareSchemaForLlm:
    """Tests for the smart schema serialization method in LLMEngine."""

    def _make_engine(self):
        with patch("app.services.llm_engine.ChatGoogleGenerativeAI"):
            from app.services.llm_engine import LLMEngine
            return LLMEngine()

    def _make_tables(self, n: int) -> list:
        return [
            {"name": f"table_{i}", "columns": [{"name": "id", "type": "INT",
             "is_primary_key": True, "is_nullable": False, "is_unique": False,
             "is_foreign_key": False}], "foreign_keys": []}
            for i in range(n)
        ]

    def test_small_schema_includes_all_tables(self):
        engine = self._make_engine()
        schema = {"tables": self._make_tables(3)}
        output = engine._prepare_schema_for_llm(schema)
        for i in range(3):
            assert f"table_{i}" in output

    def test_large_schema_samples_tables(self):
        from app.services.llm_engine import MAX_TABLES_PER_ANALYSIS
        engine = self._make_engine()
        schema = {"tables": self._make_tables(MAX_TABLES_PER_ANALYSIS + 5)}
        output = engine._prepare_schema_for_llm(schema)
        assert "NOTE: Showing" in output

    def test_column_flags_appear_in_output(self):
        engine = self._make_engine()
        schema = {"tables": [{
            "name": "users",
            "columns": [
                {"name": "id", "type": "INT", "is_primary_key": True,
                 "is_nullable": False, "is_unique": False, "is_foreign_key": False},
                {"name": "email", "type": "VARCHAR", "is_primary_key": False,
                 "is_nullable": True, "is_unique": True, "is_foreign_key": True},
            ],
            "foreign_keys": [{"column": "email", "references_table": "orgs",
                              "references_column": "id"}],
        }]}
        output = engine._prepare_schema_for_llm(schema)
        assert "PK" in output
        assert "UNIQUE" in output
        assert "FK: email -> orgs.id" in output

    def test_empty_schema_summary_line(self):
        engine = self._make_engine()
        output = engine._prepare_schema_for_llm({"tables": []})
        assert "0 tables" in output


# ── LLMEngine.analyze_schema ──────────────────────────────────────────────────

class TestAnalyzeSchema:
    """Tests for LLMEngine.analyze_schema with mocked LLM call."""

    def _mock_result(self):
        from app.services.llm_engine import AIAnalysisResult
        return AIAnalysisResult(suggestions=[])

    def _make_engine(self):
        """Engine with both ChatGoogleGenerativeAI and PydanticOutputParser mocked."""
        from app.services.llm_engine import LLMEngine
        mock_parser = MagicMock()
        mock_parser.get_format_instructions.return_value = ""
        with patch("app.services.llm_engine.ChatGoogleGenerativeAI"), \
             patch("app.services.llm_engine.PydanticOutputParser", return_value=mock_parser):
            engine = LLMEngine()
        engine.llm.model = "gemini-2.5-flash"
        return engine, mock_parser

    def test_happy_path_returns_analysis_usage(self):
        engine, mock_parser = self._make_engine()
        mock_parser.parse.return_value = self._mock_result()

        mock_output = MagicMock()
        mock_output.content = '{"suggestions": []}'
        mock_output.usage_metadata = {"total_tokens": 300}
        engine._invoke_llm = MagicMock(return_value=mock_output)

        result = engine.analyze_schema({"tables": []}, "READ_HEAVY")

        assert result.tokens_used == 300
        assert result.model_name == "gemini-2.5-flash"
        assert result.suggestions == []

    def test_json_fence_stripped_before_parsing(self):
        """```json ... ``` fences are stripped; parser receives clean JSON."""
        engine, mock_parser = self._make_engine()
        mock_parser.parse.return_value = self._mock_result()

        mock_output = MagicMock()
        mock_output.content = '```json\n{"suggestions": []}\n```'
        mock_output.usage_metadata = None  # → tokens_used == 0
        engine._invoke_llm = MagicMock(return_value=mock_output)

        result = engine.analyze_schema({"tables": []}, "WRITE_HEAVY")

        assert result.tokens_used == 0
        call_arg = mock_parser.parse.call_args[0][0]
        assert "```" not in call_arg

    def test_plain_fence_stripped_before_parsing(self):
        """Plain ``` ... ``` fences are stripped; parser receives the inner block."""
        engine, mock_parser = self._make_engine()
        mock_parser.parse.return_value = self._mock_result()

        mock_output = MagicMock()
        mock_output.content = '```\n{"suggestions": []}\n```'
        mock_output.usage_metadata = {}
        engine._invoke_llm = MagicMock(return_value=mock_output)

        result = engine.analyze_schema({"tables": []}, "READ_HEAVY")

        assert result.tokens_used == 0
        call_arg = mock_parser.parse.call_args[0][0]
        assert "```" not in call_arg
