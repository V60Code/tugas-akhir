"""
Unit tests for app/services/parser.py

Tests cover:
  - sanitize_sql_stream  (Privacy Shield)
  - parse_sql_to_schema  (Celery worker schema feed)
  - parse_sql_to_erd_schema  (ERD visualizer + FK cross-reference)

All tests are pure unit tests — no database, MinIO, or Docker required.
"""
from __future__ import annotations

import io
import pytest
from unittest.mock import patch

from app.services.parser import (
    sanitize_sql_stream,
    parse_sql_to_schema,
    parse_sql_to_erd_schema,
    _extract_fk_from_reference,
)


# ─────────────────────────────────────────────────────────────────────────────
# sanitize_sql_stream — Privacy Shield
# ─────────────────────────────────────────────────────────────────────────────

class TestSanitizeSqlStream:
    """Ensures that INSERT / COPY / VALUES lines are stripped but DDL is kept."""

    def _stream(self, content: str) -> io.BytesIO:
        return io.BytesIO(content.encode("utf-8"))

    def test_preserves_create_table(self):
        sql = "CREATE TABLE users (id SERIAL PRIMARY KEY);\n"
        result = sanitize_sql_stream(self._stream(sql)).decode()
        assert "CREATE TABLE users" in result

    def test_strips_insert_statement(self):
        sql = "INSERT INTO users (email) VALUES ('a@b.com');\n"
        result = sanitize_sql_stream(self._stream(sql)).decode()
        assert "INSERT" not in result

    def test_strips_values_line(self):
        sql = "VALUES (1, 'hello', NOW());\n"
        result = sanitize_sql_stream(self._stream(sql)).decode()
        assert "VALUES" not in result

    def test_strips_copy_statement(self):
        sql = "COPY users FROM '/tmp/data.csv' CSV HEADER;\n"
        result = sanitize_sql_stream(self._stream(sql)).decode()
        assert "COPY" not in result

    def test_preserves_comments_and_indexes(self):
        sql = (
            "-- this is a safe comment\n"
            "CREATE INDEX idx_email ON users(email);\n"
            "INSERT INTO users VALUES (1);\n"
        )
        result = sanitize_sql_stream(self._stream(sql)).decode()
        assert "-- this is a safe comment" in result
        assert "CREATE INDEX" in result
        assert "INSERT" not in result

    def test_case_insensitive_stripping(self):
        sql = (
            "insert into orders (total) values (99.9);\n"
            "copy orders from '/tmp/x';\n"
            "values (1,2,3);\n"
        )
        result = sanitize_sql_stream(self._stream(sql)).decode()
        assert result.strip() == ""

    def test_empty_stream_returns_empty_bytes(self):
        result = sanitize_sql_stream(self._stream(""))
        assert result == b""

    def test_latin1_encoded_bytes_handled_without_crash(self):
        """Lines with bytes invalid in UTF-8 fall back to latin-1 decode."""
        # 0xe9 = é in latin-1 — cannot be decoded as UTF-8
        latin1_line = b"CREATE TABLE caf\xe9 (id INT);\n"
        result = sanitize_sql_stream(io.BytesIO(latin1_line))
        # The line does NOT start with INSERT/COPY/VALUES so it must be kept
        assert len(result) > 0

    def test_mixed_content_only_ddl_survives(self, ddl_with_data_statements: bytes):
        result = sanitize_sql_stream(io.BytesIO(ddl_with_data_statements)).decode()
        assert "CREATE TABLE" in result
        assert "INSERT" not in result
        assert "COPY" not in result
        assert "VALUES" not in result
        # Index creation should remain
        assert "CREATE INDEX" in result


# ─────────────────────────────────────────────────────────────────────────────
# parse_sql_to_schema — Celery worker schema feed
# ─────────────────────────────────────────────────────────────────────────────

class TestParseSqlToSchema:
    """Tests for the simplified schema dict used by the Celery AI worker."""

    def test_returns_dict_with_tables_key(self, sample_ddl: str):
        result = parse_sql_to_schema(sample_ddl)
        assert "tables" in result

    def test_parses_correct_number_of_tables(self, sample_ddl: str):
        # sample_ddl has 3 CREATE TABLE statements
        result = parse_sql_to_schema(sample_ddl)
        assert len(result["tables"]) == 3

    def test_table_name_extracted(self, sample_ddl: str):
        result = parse_sql_to_schema(sample_ddl)
        names = [t["name"] for t in result["tables"]]
        assert "users" in names
        assert "orders" in names

    def test_columns_extracted(self, sample_ddl: str):
        result = parse_sql_to_schema(sample_ddl)
        users_table = next(t for t in result["tables"] if t["name"] == "users")
        col_names = [c["name"] for c in users_table["columns"]]
        assert "id" in col_names
        assert "email" in col_names

    def test_column_types_are_strings(self, sample_ddl: str):
        result = parse_sql_to_schema(sample_ddl)
        for table in result["tables"]:
            for col in table["columns"]:
                assert isinstance(col["type"], str)
                assert col["type"] != ""

    def test_partial_success_on_broken_ddl(self, broken_ddl: str):
        """If one table is malformed, others should still be parsed (no crash)."""
        result = parse_sql_to_schema(broken_ddl)
        names = [t["name"] for t in result["tables"]]
        # 'products' and 'categories' should survive even if @@BROKEN fails
        assert "products" in names or "categories" in names
        # Result must always contain both keys
        assert "errors" in result

    def test_empty_sql_returns_empty_tables(self):
        result = parse_sql_to_schema("")
        assert result["tables"] == []

    def test_dialect_postgres_is_accepted(self, sample_ddl: str):
        """dialect parameter should not raise for valid DDL."""
        result = parse_sql_to_schema(sample_ddl, dialect="postgres")
        assert len(result["tables"]) > 0

    def test_dialect_mysql_is_accepted(self):
        mysql_ddl = """
        CREATE TABLE products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            price DECIMAL(10,2)
        );
        """
        result = parse_sql_to_schema(mysql_ddl, dialect="mysql")
        assert len(result["tables"]) == 1
        assert result["tables"][0]["name"] == "products"

    def test_top_level_parse_exception_returns_empty(self):
        """If sqlglot.parse raises a top-level exception, return empty tables + error."""
        with patch("app.services.parser.sqlglot.parse", side_effect=Exception("parse crash")):
            result = parse_sql_to_schema("NOT SQL AT ALL")
        assert result["tables"] == []
        assert any("parse crash" in e for e in result["errors"])


# ─────────────────────────────────────────────────────────────────────────────
# parse_sql_to_erd_schema — Full ERD schema with FK cross-reference check
# ─────────────────────────────────────────────────────────────────────────────

class TestParseSqlToErdSchema:
    """Tests for the rich ERD schema parser used by the React Flow visualizer."""

    def test_returns_required_keys(self, sample_ddl: str):
        result = parse_sql_to_erd_schema(sample_ddl)
        assert "tables" in result
        assert "errors" in result
        assert "missing_fk_warnings" in result
        assert "has_missing_references" in result

    def test_parses_correct_number_of_tables(self, sample_ddl: str):
        result = parse_sql_to_erd_schema(sample_ddl)
        assert len(result["tables"]) == 3

    def test_primary_key_flag(self, sample_ddl: str):
        result = parse_sql_to_erd_schema(sample_ddl)
        users = next(t for t in result["tables"] if t["name"] == "users")
        pk_cols = [c for c in users["columns"] if c["is_primary_key"]]
        assert len(pk_cols) >= 1
        assert pk_cols[0]["name"] == "id"

    def test_foreign_key_extracted(self, sample_ddl: str):
        result = parse_sql_to_erd_schema(sample_ddl)
        orders = next(t for t in result["tables"] if t["name"] == "orders")
        assert len(orders["foreign_keys"]) >= 1
        fk = orders["foreign_keys"][0]
        assert "column" in fk
        assert "references_table" in fk
        assert fk["references_table"] == "users"

    def test_missing_fk_detected(self, sample_ddl: str):
        """
        sample_ddl has order_items.product_id REFERENCES products(id)
        but 'products' table is NOT defined → should flag as missing reference.
        """
        result = parse_sql_to_erd_schema(sample_ddl)
        assert result["has_missing_references"] is True
        assert len(result["missing_fk_warnings"]) >= 1
        # Check warning mentions the missing table name
        combined = " ".join(result["missing_fk_warnings"])
        assert "products" in combined

    def test_no_missing_fk_when_all_tables_present(self):
        self_contained_ddl = """
        CREATE TABLE teams (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL
        );
        CREATE TABLE players (
            id SERIAL PRIMARY KEY,
            team_id INT NOT NULL REFERENCES teams(id),
            name VARCHAR(100)
        );
        """
        result = parse_sql_to_erd_schema(self_contained_ddl)
        assert result["has_missing_references"] is False
        assert result["missing_fk_warnings"] == []

    def test_unique_flag_detected(self, sample_ddl: str):
        result = parse_sql_to_erd_schema(sample_ddl)
        users = next(t for t in result["tables"] if t["name"] == "users")
        unique_cols = [c for c in users["columns"] if c.get("is_unique")]
        col_names = [c["name"] for c in unique_cols]
        assert "email" in col_names

    def test_nullable_defaults(self, sample_ddl: str):
        """Columns without NOT NULL should be nullable."""
        result = parse_sql_to_erd_schema(sample_ddl)
        users = next(t for t in result["tables"] if t["name"] == "users")
        full_name_col = next((c for c in users["columns"] if c["name"] == "full_name"), None)
        assert full_name_col is not None
        assert full_name_col["is_nullable"] is True

    def test_not_null_column_is_not_nullable(self, sample_ddl: str):
        result = parse_sql_to_erd_schema(sample_ddl)
        users = next(t for t in result["tables"] if t["name"] == "users")
        email_col = next(c for c in users["columns"] if c["name"] == "email")
        assert email_col["is_nullable"] is False

    def test_partial_success_on_broken_table(self, broken_ddl: str):
        """Malformed table should be skipped; valid tables should still appear."""
        result = parse_sql_to_erd_schema(broken_ddl)
        names = [t["name"] for t in result["tables"]]
        assert "products" in names or "categories" in names

    def test_empty_sql_returns_empty_structure(self):
        result = parse_sql_to_erd_schema("")
        assert result["tables"] == []
        assert result["errors"] == []
        assert result["missing_fk_warnings"] == []
        assert result["has_missing_references"] is False

    def test_fk_is_foreign_key_flag_set_on_column(self, sample_ddl: str):
        result = parse_sql_to_erd_schema(sample_ddl)
        orders = next(t for t in result["tables"] if t["name"] == "orders")
        user_id_col = next((c for c in orders["columns"] if c["name"] == "user_id"), None)
        assert user_id_col is not None
        assert user_id_col["is_foreign_key"] is True

    def test_create_view_is_skipped(self):
        """CREATE VIEW produces a non-Schema node → skipped by the parser."""
        ddl = """
        CREATE TABLE users (id SERIAL PRIMARY KEY, name VARCHAR(100));
        CREATE VIEW active_users AS SELECT id, name FROM users;
        """
        result = parse_sql_to_erd_schema(ddl)
        names = [t["name"] for t in result["tables"]]
        assert "users" in names
        assert "active_users" not in names
        assert len(result["tables"]) == 1

    def test_table_level_primary_key_constraint(self):
        """Table-level PRIMARY KEY (...) marks the referenced column as is_primary_key."""
        ddl = """
        CREATE TABLE roles (
            id INTEGER,
            name VARCHAR(50) NOT NULL,
            PRIMARY KEY (id)
        );
        """
        result = parse_sql_to_erd_schema(ddl)
        roles = next(t for t in result["tables"] if t["name"] == "roles")
        pk_cols = [c for c in roles["columns"] if c["is_primary_key"]]
        assert len(pk_cols) == 1
        assert pk_cols[0]["name"] == "id"

    def test_table_level_foreign_key_constraint(self):
        """Table-level FOREIGN KEY ... REFERENCES ... creates FK entry in foreign_keys list."""
        ddl = """
        CREATE TABLE departments (id SERIAL PRIMARY KEY, name VARCHAR(100));
        CREATE TABLE employees (
            id SERIAL PRIMARY KEY,
            dept_id INT NOT NULL,
            FOREIGN KEY (dept_id) REFERENCES departments(id)
        );
        """
        result = parse_sql_to_erd_schema(ddl)
        employees = next(t for t in result["tables"] if t["name"] == "employees")
        # Verify the table-level FK entry was created (covers L184-191)
        assert len(employees["foreign_keys"]) >= 1
        fk = employees["foreign_keys"][0]
        assert fk["column"] == "dept_id"

    def test_erd_top_level_parse_exception(self):
        """If sqlglot.parse raises, return empty structure with errors populated."""
        with patch("app.services.parser.sqlglot.parse", side_effect=Exception("fatal error")):
            result = parse_sql_to_erd_schema("NOT SQL")
        assert result["tables"] == []
        assert any("fatal error" in e for e in result["errors"])


# ── _extract_fk_from_reference ────────────────────────────────────────────────

class TestExtractFkFromReference:
    """Unit tests for the low-level FK AST helper."""

    def test_schema_node_extracts_table_and_column(self):
        """Standard `REFERENCES table(col)` → Schema node path (already covered by ERD tests)."""
        from sqlglot import exp
        # Parse a real inline-FK DDL and verify helper result via parse_sql_to_erd_schema
        ddl = "CREATE TABLE a (x INT REFERENCES b(id));"
        result = parse_sql_to_erd_schema(ddl)
        a_table = next(t for t in result["tables"] if t["name"] == "a")
        assert a_table["foreign_keys"][0]["references_table"] == "b"

    def test_table_node_extracts_table_name(self):
        """Reference where .this is an exp.Table node (no column)."""
        from sqlglot import exp
        ref_target = exp.Table(this=exp.Identifier(this="products"))
        from unittest.mock import MagicMock
        ref = MagicMock()
        ref.this = ref_target
        ref.expressions = []
        table_name, col_name = _extract_fk_from_reference(ref)
        assert table_name == "products"
        assert col_name == ""

    def test_fallback_node_uses_getattr_name(self):
        """Reference where .this is an unknown node type → fallback path."""
        from unittest.mock import MagicMock

        class UnknownNode:
            name = "fallback_table"

        ref = MagicMock()
        ref.this = UnknownNode()
        ref.expressions = []
        table_name, col_name = _extract_fk_from_reference(ref)
        assert table_name == "fallback_table"
        assert col_name == ""
