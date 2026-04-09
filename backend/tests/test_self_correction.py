"""
Unit tests for the AI Self-Correction mechanism in llm_engine.py

Tests cover:
  - Happy path: self_correct_sql returns fixed SQL when LLM responds correctly.
  - Empty patch: LLM returns empty corrected_sql → caller should stop retrying.
  - LLM failure: exception propagates so the worker can break the retry loop.
  - MAX_SELF_CORRECTION_RETRIES constant value (prevents unlimited loops).

All LLM calls are fully mocked; no real API calls are made.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.services.llm_engine import (
    LLMEngine,
    SelfCorrectionResult,
    MAX_SELF_CORRECTION_RETRIES,
)


# ── Constants ─────────────────────────────────────────────────────────────────

class TestSelfCorrectionRetryLimit:
    """Ensure the retry ceiling is safe (not infinite)."""

    def test_max_retries_is_positive(self):
        assert MAX_SELF_CORRECTION_RETRIES >= 1

    def test_max_retries_is_reasonable(self):
        # Prevent accidental explosion to 100+ retries
        assert MAX_SELF_CORRECTION_RETRIES <= 5


# ── self_correct_sql ──────────────────────────────────────────────────────────

ORIGINAL_PATCH = "ALTER TABLE orders ADD INDEX idx_user (user_id);"
ERROR_LOG = "ERROR:  syntax error at or near \"INDEX\"\nHINT: Use CREATE INDEX instead."
CORRECTED_PATCH = "CREATE INDEX idx_user ON orders(user_id);"


def _make_engine_with_mock_llm(corrected_sql: str, explanation: str = "Fixed syntax.") -> LLMEngine:
    """
    Build an LLMEngine instance whose internal LLM is replaced with a mock
    that returns the given corrected SQL via a SelfCorrectionResult payload.
    """
    engine = LLMEngine.__new__(LLMEngine)  # skip __init__ (avoids real API key check)

    # Simulate the LLM returning a JSON-serialised SelfCorrectionResult
    fake_result = SelfCorrectionResult(
        corrected_sql=corrected_sql,
        explanation=explanation,
    )
    # PydanticOutputParser.parse() is what turns the LLM string → model
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content=fake_result.model_dump_json()   # valid JSON, no fences
    )
    engine.llm = mock_llm
    return engine


class TestSelfCorrectSql:

    def test_returns_corrected_sql_string(self):
        engine = _make_engine_with_mock_llm(CORRECTED_PATCH)

        with patch.object(engine, "_LLMEngine__class__", LLMEngine, create=True):
            # Patch the parser so it returns our known result
            mock_parser = MagicMock()
            mock_parser.get_format_instructions.return_value = ""
            mock_parser.parse.return_value = SelfCorrectionResult(
                corrected_sql=CORRECTED_PATCH,
                explanation="Fixed syntax.",
            )

            with patch("app.services.llm_engine.PydanticOutputParser", return_value=mock_parser):
                result = engine.self_correct_sql(
                    original_sql_patch=ORIGINAL_PATCH,
                    error_log=ERROR_LOG,
                    table_name="orders",
                    attempt=1,
                )

        assert result == CORRECTED_PATCH

    def test_empty_corrected_sql_is_returned_as_empty_string(self):
        """
        When LLM decides the patch is uncorrectable it returns empty corrected_sql.
        The worker checks for falsy and breaks the loop — so we just verify the
        method propagates the empty string faithfully.
        """
        engine = _make_engine_with_mock_llm("")

        mock_parser = MagicMock()
        mock_parser.get_format_instructions.return_value = ""
        mock_parser.parse.return_value = SelfCorrectionResult(
            corrected_sql="",
            explanation="Patch references non-existent table.",
        )

        with patch("app.services.llm_engine.PydanticOutputParser", return_value=mock_parser):
            result = engine.self_correct_sql(
                original_sql_patch=ORIGINAL_PATCH,
                error_log=ERROR_LOG,
                table_name="orders",
                attempt=1,
            )

        assert result == ""

    def test_llm_exception_propagates(self):
        """If the LLM call itself raises, the exception must bubble up so the
        worker can catch it and break the retry loop."""
        engine = LLMEngine.__new__(LLMEngine)
        engine.llm = MagicMock()
        engine.llm.invoke.side_effect = RuntimeError("API rate limit exceeded")

        mock_parser = MagicMock()
        mock_parser.get_format_instructions.return_value = ""

        with patch("app.services.llm_engine.PydanticOutputParser", return_value=mock_parser):
            with pytest.raises(RuntimeError, match="API rate limit exceeded"):
                engine.self_correct_sql(
                    original_sql_patch=ORIGINAL_PATCH,
                    error_log=ERROR_LOG,
                    table_name="orders",
                    attempt=1,
                )

    def test_error_log_is_truncated_to_3000_chars(self):
        """
        Very long error logs must be truncated before being sent to the LLM
        to avoid exceeding the context window.
        """
        long_log = "E" * 10_000
        engine = LLMEngine.__new__(LLMEngine)
        captured_inputs: list[str] = []

        mock_llm = MagicMock()

        def capture_invoke(prompt_str: str) -> MagicMock:
            captured_inputs.append(prompt_str)
            return MagicMock(content='{"corrected_sql": "SELECT 1;", "explanation": "ok"}')

        mock_llm.invoke.side_effect = capture_invoke
        engine.llm = mock_llm

        mock_parser = MagicMock()
        mock_parser.get_format_instructions.return_value = ""
        mock_parser.parse.return_value = SelfCorrectionResult(
            corrected_sql="SELECT 1;",
            explanation="ok",
        )

        with patch("app.services.llm_engine.PydanticOutputParser", return_value=mock_parser):
            engine.self_correct_sql(
                original_sql_patch="SELECT 1;",
                error_log=long_log,
                table_name="test_table",
                attempt=1,
            )

        # The prompt sent to LLM must NOT contain the full 10 000-char log
        assert len(captured_inputs) == 1
        prompt_sent = captured_inputs[0]
        # 3000 chars of log + surrounding prompt text — total must be well under 15 000
        assert long_log[:3001] not in prompt_sent          # truncation applied
        assert long_log[:3000] in prompt_sent or "E" * 3000 in prompt_sent  # 3000 chars included

    def test_markdown_fences_stripped_from_llm_response(self):
        """If Gemini wraps its JSON in ```json fences, we strip them before parsing."""
        engine = LLMEngine.__new__(LLMEngine)
        payload = '```json\n{"corrected_sql": "SELECT 1;", "explanation": "test"}\n```'

        engine.llm = MagicMock()
        engine.llm.invoke.return_value = MagicMock(content=payload)

        mock_parser = MagicMock()
        mock_parser.get_format_instructions.return_value = ""
        mock_parser.parse.return_value = SelfCorrectionResult(
            corrected_sql="SELECT 1;",
            explanation="test",
        )

        with patch("app.services.llm_engine.PydanticOutputParser", return_value=mock_parser):
            result = engine.self_correct_sql(
                original_sql_patch="BAD SQL",
                error_log="Error",
                table_name="t",
                attempt=1,
            )

        # Verify the parser received the stripped content (not the raw fenced payload)
        call_args = mock_parser.parse.call_args[0][0]
        assert "```" not in call_args
        assert result == "SELECT 1;"
