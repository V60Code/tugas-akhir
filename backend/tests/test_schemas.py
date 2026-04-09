"""
Unit tests for the Pydantic schemas defined in app/schemas/job.py

Validates:
  - Field defaults and required fields
  - Serialisation / deserialisation round-trips
  - ERDSchemaResponse correctness including new missing-FK fields
"""
from __future__ import annotations

import uuid
import pytest
from pydantic import ValidationError

from app.schemas.job import (
    AISuggestionResponse,
    JobSuggestionsResponse,
    ERDSchemaResponse,
    ERDTable,
    ERDColumn,
    ERDForeignKey,
    FinalizeRequest,
    JobSummaryResponse,
)


# ─────────────────────────────────────────────────────────────────────────────
# ERDSchemaResponse
# ─────────────────────────────────────────────────────────────────────────────

class TestERDSchemaResponse:

    def test_missing_fk_defaults_to_empty(self):
        schema = ERDSchemaResponse(
            job_id=uuid.uuid4(),
            tables=[],
            table_count=0,
            relationship_count=0,
        )
        assert schema.missing_fk_warnings == []
        assert schema.has_missing_references is False

    def test_missing_fk_fields_set_correctly(self):
        schema = ERDSchemaResponse(
            job_id=uuid.uuid4(),
            tables=[],
            table_count=0,
            relationship_count=0,
            missing_fk_warnings=["Missing ref: 'orders.user_id' → 'users'"],
            has_missing_references=True,
        )
        assert schema.has_missing_references is True
        assert len(schema.missing_fk_warnings) == 1

    def test_erd_table_serialises(self):
        col = ERDColumn(
            name="id",
            type="INT",
            is_primary_key=True,
            is_foreign_key=False,
            is_nullable=False,
            is_unique=False,
        )
        fk = ERDForeignKey(column="user_id", references_table="users", references_column="id")
        tbl = ERDTable(name="orders", columns=[col], foreign_keys=[fk])
        assert tbl.name == "orders"
        assert tbl.columns[0].is_primary_key is True
        assert tbl.foreign_keys[0].references_table == "users"

    def test_errors_default_empty(self):
        schema = ERDSchemaResponse(
            job_id=uuid.uuid4(),
            tables=[],
            table_count=0,
            relationship_count=0,
        )
        assert schema.errors == []


# ─────────────────────────────────────────────────────────────────────────────
# JobSuggestionsResponse
# ─────────────────────────────────────────────────────────────────────────────

class TestJobSuggestionsResponse:

    def _make_suggestion(self) -> AISuggestionResponse:
        return AISuggestionResponse(
            id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            table_name="orders",
            issue="Missing index on user_id",
            suggestion="Add CREATE INDEX",
            risk_level="HIGH",
            confidence=0.9,
            sql_patch="CREATE INDEX idx_orders_user_id ON orders(user_id);",
            action_status="PENDING",
        )

    def test_default_missing_fk_fields(self):
        resp = JobSuggestionsResponse(original_sql="SELECT 1;", suggestions=[])
        assert resp.missing_fk_warnings == []
        assert resp.has_missing_references is False

    def test_with_suggestions(self):
        s = self._make_suggestion()
        resp = JobSuggestionsResponse(
            original_sql="CREATE TABLE orders (id INT);",
            suggestions=[s],
        )
        assert len(resp.suggestions) == 1
        assert resp.suggestions[0].risk_level == "HIGH"

    def test_with_missing_fk_warnings(self):
        resp = JobSuggestionsResponse(
            original_sql="CREATE TABLE orders (id INT);",
            suggestions=[],
            missing_fk_warnings=["Missing ref: orders.user_id → users"],
            has_missing_references=True,
        )
        assert resp.has_missing_references is True


# ─────────────────────────────────────────────────────────────────────────────
# FinalizeRequest
# ─────────────────────────────────────────────────────────────────────────────

class TestFinalizeRequest:

    def test_accepts_list_of_uuids(self):
        ids = [uuid.uuid4(), uuid.uuid4()]
        req = FinalizeRequest(accepted_suggestion_ids=ids)
        assert len(req.accepted_suggestion_ids) == 2

    def test_accepts_empty_list(self):
        req = FinalizeRequest(accepted_suggestion_ids=[])
        assert req.accepted_suggestion_ids == []

    def test_rejects_invalid_uuid_string(self):
        with pytest.raises(ValidationError):
            FinalizeRequest(accepted_suggestion_ids=["not-a-uuid"])


# ─────────────────────────────────────────────────────────────────────────────
# JobSummaryResponse
# ─────────────────────────────────────────────────────────────────────────────

class TestJobSummaryResponse:

    def test_error_message_defaults_to_none(self):
        from datetime import datetime, timezone
        summary = JobSummaryResponse(
            id=uuid.uuid4(),
            original_filename="schema.sql",
            status="QUEUED",
            app_context="READ_HEAVY",
            created_at=datetime.now(timezone.utc),
        )
        assert summary.error_message is None
