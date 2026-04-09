import re
import io
import logging
from typing import BinaryIO
import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)


def _extract_fk_from_reference(ref: exp.Reference) -> tuple[str, str]:
    """
    Extract (references_table, references_column) from a SQLGlot Reference node.

    SQLGlot AST shape for  `INT REFERENCES customers(id)`:
        Reference(
          this=Schema(
            this=Table(this=Identifier('customers')),
            expressions=[Column(this=Identifier('id'))]
          )
        )

    So the referenced table is  ref.this.this.name
    and the referenced column is ref.this.expressions[0].name  (may be empty).
    """
    ref_table: str = ""
    ref_col: str = ""

    ref_target = ref.this  # Schema or Table node
    if isinstance(ref_target, exp.Schema):
        # Schema wraps both the table and the column list
        tbl_node = ref_target.this
        ref_table = tbl_node.name if hasattr(tbl_node, "name") else str(tbl_node)
        col_exprs = ref_target.expressions
        if col_exprs:
            ref_col = col_exprs[0].name if hasattr(col_exprs[0], "name") else str(col_exprs[0])
    elif isinstance(ref_target, exp.Table):
        ref_table = ref_target.name
        col_exprs = ref.expressions
        if col_exprs:
            ref_col = col_exprs[0].name if hasattr(col_exprs[0], "name") else str(col_exprs[0])
    else:
        # Fallback: try .name directly
        ref_table = str(getattr(ref_target, "name", ref_target))
        col_exprs = ref.expressions
        if col_exprs:
            ref_col = col_exprs[0].name if hasattr(col_exprs[0], "name") else str(col_exprs[0])

    return ref_table, ref_col


def sanitize_sql_stream(file_stream: BinaryIO) -> bytes:
    """
    Reads a file stream line by line and removes lines starting with
    INSERT, COPY, or VALUES (Privacy Shield — no raw data reaches the engine).
    Returns the sanitized content as bytes.
    """
    sanitized_content = io.BytesIO()
    forbidden_pattern = re.compile(r'^\s*(INSERT|COPY|VALUES)', re.IGNORECASE)

    for line in file_stream:
        try:
            line_str = line.decode('utf-8')
        except UnicodeDecodeError:
            line_str = line.decode('latin-1', errors='ignore')

        if not forbidden_pattern.match(line_str):
            sanitized_content.write(line)

    return sanitized_content.getvalue()


def parse_sql_to_schema(sql_content: str, dialect: str | None = None) -> dict:
    """
    Parses SQL content using SQLGlot and returns a simplified schema dict.
    Used by the Celery worker to feed the AI engine.

    Partial-success: if one table fails to parse, it is skipped with a warning
    and parsing continues on the remaining statements — mirroring the behaviour
    of parse_sql_to_erd_schema.

    Args:
        sql_content: Raw DDL SQL string.
        dialect: Optional SQLGlot dialect name ('mysql', 'postgres', etc.).

    Returns:
        {"tables": [...], "errors": [str]}
    """
    tables = []
    errors = []

    try:
        parsed = sqlglot.parse(
            sql_content,
            dialect=dialect,
            error_level=sqlglot.ErrorLevel.IGNORE,
        )
    except Exception as e:
        logger.error(f"SQLGlot top-level parse error in parse_sql_to_schema: {e}")
        return {"tables": [], "errors": [str(e)]}

    for expression in parsed:
        if not isinstance(expression, exp.Create):
            continue

        table_name = ""
        try:
            # expression.this may be a Schema (table-with-columns) or Table node.
            # Use find() to reliably get the Table node in all cases.
            tbl_node = expression.find(exp.Table)
            table_name = tbl_node.name if tbl_node else expression.this.name
            columns = []

            col_container = expression.this  # Schema or Table
            if hasattr(col_container, "expressions") and col_container.expressions:
                for col_def in col_container.expressions:
                    if isinstance(col_def, exp.ColumnDef):
                        col_name = col_def.this.name
                        col_type = col_def.kind.sql() if col_def.kind else "UNKNOWN"
                        columns.append({"name": col_name, "type": col_type})

            tables.append({"name": table_name, "columns": columns})

        except Exception as e:
            err_msg = f"Skipped table '{table_name or '?'}': {e}"
            logger.warning(err_msg)
            errors.append(err_msg)
            # Partial success: continue with remaining tables

    logger.info(f"parse_sql_to_schema: {len(tables)} tables parsed, {len(errors)} warnings")
    return {"tables": tables, "errors": errors}


def parse_sql_to_erd_schema(sql_content: str) -> dict:
    """
    Full ERD-aware schema parser using SQLGlot.

    Extracts per table:
      - columns: name, type, is_primary_key, is_nullable, is_unique
      - foreign_keys: column, references_table, references_column
      - indexes: name, columns, is_unique

    Returns a structured dict ready to be consumed by the React Flow ERD renderer.
    """
    tables: list[dict] = []
    errors: list[str] = []

    try:
        parsed = sqlglot.parse(sql_content, error_level=sqlglot.ErrorLevel.IGNORE)
    except Exception as e:
        logger.error(f"SQLGlot top-level parse error: {e}")
        return {"tables": [], "errors": [str(e)]}

    for statement in parsed:
        if not isinstance(statement, exp.Create):
            continue

        # Only process CREATE TABLE statements (skip VIEW, INDEX, etc.)
        if not isinstance(statement.this, exp.Schema):
            continue

        table_name: str = ""
        try:
            table_name = statement.this.this.name
        except AttributeError:
            continue

        columns: list[dict] = []
        foreign_keys: list[dict] = []
        primary_key_columns: set[str] = set()

        try:
            schema_expressions = statement.this.expressions or []

            # ── First pass: find table-level PRIMARY KEY and FOREIGN KEY constraints ──
            for expr in schema_expressions:
                # Table-level PRIMARY KEY constraint
                if isinstance(expr, exp.PrimaryKey):
                    for pk_col in expr.expressions:
                        primary_key_columns.add(pk_col.name)

                # Table-level FOREIGN KEY constraint
                elif isinstance(expr, exp.ForeignKey):
                    fk_cols = [c.name for c in expr.expressions]
                    ref = expr.args.get("reference")
                    if ref:
                        ref_table = ref.this.name if hasattr(ref.this, "name") else str(ref.this)
                        ref_cols_expr = ref.expressions
                        ref_cols = [c.name for c in ref_cols_expr] if ref_cols_expr else []
                        for i, fk_col in enumerate(fk_cols):
                            foreign_keys.append({
                                "column": fk_col,
                                "references_table": ref_table,
                                "references_column": ref_cols[i] if i < len(ref_cols) else "",
                            })

            # ── Second pass: extract individual column definitions ──────────────────
            for col_def in schema_expressions:
                if not isinstance(col_def, exp.ColumnDef):
                    continue

                col_name: str = col_def.this.name
                col_type_expr = col_def.kind
                col_type: str = col_type_expr.sql() if col_type_expr else "UNKNOWN"

                is_pk = col_name in primary_key_columns
                is_nullable = True
                is_unique = False
                inline_fk: dict | None = None

                # Inspect column-level constraints
                for constraint in (col_def.constraints or []):
                    kind = constraint.kind

                    if isinstance(kind, exp.PrimaryKeyColumnConstraint):
                        is_pk = True
                        primary_key_columns.add(col_name)

                    elif isinstance(kind, exp.NotNullColumnConstraint):
                        is_nullable = False

                    elif isinstance(kind, exp.UniqueColumnConstraint):
                        is_unique = True

                    elif isinstance(kind, exp.Reference):
                        # Inline REFERENCES table(column) — delegate to helper
                        # that correctly handles SQLGlot's Schema AST wrapping
                        ref_table, ref_col = _extract_fk_from_reference(kind)
                        inline_fk = {
                            "column": col_name,
                            "references_table": ref_table,
                            "references_column": ref_col,
                        }

                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "is_primary_key": is_pk,
                    "is_nullable": is_nullable,
                    "is_unique": is_unique,
                    # FK flag for quick lookup in frontend
                    "is_foreign_key": inline_fk is not None,
                })

                if inline_fk:
                    foreign_keys.append(inline_fk)

        except Exception as e:
            err_msg = f"Error parsing table '{table_name}': {e}"
            logger.warning(err_msg)
            errors.append(err_msg)
            # Partial success: keep the table even if columns partially failed

        tables.append({
            "name": table_name,
            "columns": columns,
            "foreign_keys": foreign_keys,
        })

    # ── Post-parse: cross-reference FK targets ─────────────────────────────
    # Collect all defined table names (normalised to lower-case for comparison)
    defined_table_names: set[str] = {t["name"].lower() for t in tables}
    missing_fk_warnings: list[str] = []

    for tbl in tables:
        for fk in tbl["foreign_keys"]:
            ref = fk.get("references_table", "")
            if ref and ref.lower() not in defined_table_names:
                warn = (
                    f"Missing reference: '{tbl['name']}.{fk['column']}' "
                    f"→ '{ref}' (table not found in uploaded file)"
                )
                if warn not in missing_fk_warnings:
                    missing_fk_warnings.append(warn)
                    logger.warning(warn)

    all_errors = errors + missing_fk_warnings

    logger.info(
        f"ERD parse complete: {len(tables)} tables, "
        f"{sum(len(t['foreign_keys']) for t in tables)} FK relationships, "
        f"{len(errors)} parse errors, {len(missing_fk_warnings)} missing FK warnings"
    )

    return {
        "tables": tables,
        "errors": errors,
        "missing_fk_warnings": missing_fk_warnings,
        "has_missing_references": len(missing_fk_warnings) > 0,
    }
