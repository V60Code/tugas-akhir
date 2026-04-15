from typing import List, NamedTuple
import json
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from app.core.config import settings
from app.models.suggestion import RiskLevel

logger = logging.getLogger(__name__)


def _is_transient_llm_error(exc: BaseException) -> bool:
    """Return True for errors that are clearly transient and safe to retry."""
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    # Match Gemini / Google API error classes by name to avoid a hard import.
    return type(exc).__name__ in {
        "ResourceExhausted",   # 429 — rate limit
        "ServiceUnavailable",  # 503
        "InternalServerError", # 500
        "DeadlineExceeded",    # timeout
    }


# ── Constants ─────────────────────────────────────────────────────────────────

# Max tables sent to AI in a single call to prevent context overflow.
# For large schemas (>MAX_TABLES), we sample intelligently.
MAX_TABLES_PER_ANALYSIS = 25

# Max number of times the LLM is asked to self-correct a failing SQL patch.
MAX_SELF_CORRECTION_RETRIES = 2


class AnalysisUsage(NamedTuple):
    """Token usage and model metadata captured from a single LLM call."""
    suggestions: List["AISuggestionSchema"]
    tokens_used: int
    model_name: str

# ── Pydantic Schemas for Structured LLM Output ───────────────────────────────

class AISuggestionSchema(BaseModel):
    table_name: str = Field(description="Name of the table this suggestion applies to. Use 'GLOBAL' for schema-wide issues.")
    issue: str = Field(description="Short, specific title of the issue (max 80 chars)")
    suggestion: str = Field(description="Detailed explanation of WHY it is a problem and how to solve it")
    risk_level: RiskLevel = Field(description="Risk of applying the change: LOW, MEDIUM, or HIGH")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0 that this is a real issue")
    sql_patch: str = Field(description="Concrete, runnable SQL DDL/DML to fix or improve the issue. Never leave this empty.")


class AIAnalysisResult(BaseModel):
    suggestions: List[AISuggestionSchema]


class SelfCorrectionResult(BaseModel):
    """Structured output returned by the self-correction prompt."""
    corrected_sql: str = Field(
        description="The corrected SQL patch that resolves the validation error. Must be valid, runnable SQL."
    )
    explanation: str = Field(
        description="Brief explanation of what was wrong and what was changed."
    )


# ── LLM Engine ────────────────────────────────────────────────────────────────

class LLMEngine:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            temperature=0.1,    # slight creativity to find non-obvious issues
            convert_system_message_to_human=True,
            google_api_key=settings.GOOGLE_API_KEY,
        )

        self.parser = PydanticOutputParser(pydantic_object=AIAnalysisResult)

        self.prompt = PromptTemplate(
            template="""
You are a senior MySQL Database Architect and performance tuning expert.
Your task is to deeply analyze the database schema below and find REAL, ACTIONABLE optimization opportunities.

=== TARGET DIALECT ===
{db_dialect}

=== WORKLOAD CONTEXT ===
{app_context}
- READ_HEAVY: Prioritize indexes for SELECT performance (composite indexes, covering indexes, filtered access patterns)
- WRITE_HEAVY: Identify indexes that hurt INSERT/UPDATE performance, suggest index consolidation

=== DATABASE SCHEMA ===
{schema_json}

=== YOUR ANALYSIS MANDATE ===
You MUST find between 3 and 8 real issues. Even well-designed schemas have optimization opportunities.

Look for ALL of the following (not just obvious ones):
1. **Missing composite indexes** — columns frequently used together in WHERE/JOIN but only indexed individually
2. **Low-cardinality predicate optimization** — use index design that helps common filters (status, is_active, deleted_at)
3. **UUID primary key tradeoff** — if schema uses UUID PKs, note random write amplification and suggest MySQL-friendly alternatives if needed
4. **Covering indexes in MySQL** — indexes that reduce extra lookups for common query patterns
5. **JSON column optimization** — suggest generated columns + indexes when JSON fields are filtered frequently
6. **Soft-delete performance** — tables with deleted_at that lack indexes aligned with active-row query patterns
7. **Over-indexing** — tables with too many single-column indexes that slow down writes
8. **Missing CHECK constraints or NOT NULL** — columns that should be constrained but aren't
9. **Normalization opportunities** — repeated patterns that could be extracted to reference tables
10. **Large TEXT columns** — TEXT/LONGTEXT on frequently-filtered columns that should be VARCHAR(N) or separate lookup design

CRITICAL RULES:
- You MUST generate at least 3 suggestions. If the schema looks clean, find micro-optimizations.
- Every suggestion MUST include a concrete, runnable SQL patch (not a comment, actual SQL).
- Do NOT return empty sql_patch strings.
- Do NOT make up tables or columns that don't exist in the schema.
- Use MySQL 8-compatible SQL syntax.
- Do NOT use PostgreSQL-only features (GIN, BRIN, INCLUDE, partial index WHERE clause, PostgreSQL-specific operators).

{format_instructions}
""",
            input_variables=["app_context", "schema_json", "db_dialect"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )

    def _prepare_schema_for_llm(self, schema: dict) -> str:
        """
        Smart schema serialization for LLM context.

        For large schemas (>MAX_TABLES_PER_ANALYSIS tables), we sample
        intelligently rather than dumping all 600+ columns which overwhelms
        the LLM context window and degrades response quality.

        Strategy:
        - Always include the first N tables (core entities)
        - Add schema stats at the top so AI has full picture
        """
        tables = schema.get("tables", [])
        total_tables = len(tables)
        total_columns = sum(len(t.get("columns", [])) for t in tables)

        # Build a compact representation
        schema_lines = [
            f"-- Schema Summary: {total_tables} tables, {total_columns} columns total",
            f"-- Analyzing sample of up to {MAX_TABLES_PER_ANALYSIS} tables",
            "",
        ]

        # Sample tables: if too many, take first MAX + a few from the middle/end
        if total_tables > MAX_TABLES_PER_ANALYSIS:
            step = total_tables // MAX_TABLES_PER_ANALYSIS
            sampled = tables[::step][:MAX_TABLES_PER_ANALYSIS]
            schema_lines.append(f"-- NOTE: Showing {len(sampled)} of {total_tables} tables for analysis")
        else:
            sampled = tables

        for tbl in sampled:
            schema_lines.append(f"\nTABLE: {tbl['name']}")
            for col in tbl.get("columns", []):
                flags = []
                if col.get("is_primary_key"):    flags.append("PK")
                if col.get("is_foreign_key"):     flags.append("FK")
                if not col.get("is_nullable", True): flags.append("NOT NULL")
                if col.get("is_unique"):          flags.append("UNIQUE")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                schema_lines.append(f"  {col['name']} {col['type']}{flag_str}")

            fks = tbl.get("foreign_keys", [])
            if fks:
                for fk in fks:
                    schema_lines.append(
                        f"  FK: {fk['column']} -> {fk['references_table']}.{fk['references_column']}"
                    )

        return "\n".join(schema_lines)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_transient_llm_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _invoke_llm(self, prompt_str: str):
        """Single LLM network hop — isolated so tenacity retries only this call."""
        return self.llm.invoke(prompt_str)

    def analyze_schema(self, schema: dict, app_context: str, db_dialect: str = "mysql") -> AnalysisUsage:
        """
        Send schema to Gemini for analysis and return structured suggestions
        together with token usage and the model name used.

        Errors propagate to worker.py which marks the Job as FAILED.
        """
        logger.info(f"Sending schema to Gemini ({self.llm.model}), "
                    f"tables={len(schema.get('tables', []))}, context={app_context}")

        schema_text = self._prepare_schema_for_llm(schema)

        _input = self.prompt.format_prompt(
            app_context=app_context,
            schema_json=schema_text,
            db_dialect=db_dialect or "mysql",
        )

        output = self._invoke_llm(_input.to_string())
        content = output.content

        # Strip markdown fences if Gemini wraps output anyway
        if "```json" in content:
            content = content.replace("```json", "").replace("```", "").strip()
        elif "```" in content:
            content = content.split("```")[1].strip()

        parsed_result = self.parser.parse(content)

        # Extract token usage — usage_metadata may be None on some model versions
        usage = getattr(output, "usage_metadata", None) or {}
        tokens_used = usage.get("total_tokens", 0)

        logger.info(
            f"Gemini returned {len(parsed_result.suggestions)} suggestions, "
            f"tokens_used={tokens_used}, model={self.llm.model}"
        )
        return AnalysisUsage(
            suggestions=parsed_result.suggestions,
            tokens_used=tokens_used,
            model_name=self.llm.model,
        )

    def self_correct_sql(
        self,
        original_sql_patch: str,
        error_log: str,
        table_name: str,
        attempt: int,
        db_dialect: str = "mysql",
    ) -> str:
        """
        Ask the LLM to fix a SQL patch that failed sandbox validation.

        Args:
            original_sql_patch: The SQL that failed.
            error_log:          The sandbox error output (stdout/stderr).
            table_name:         Table the patch targets (for context).
            attempt:            Current retry number (1-based, for log clarity).

        Returns:
            Corrected SQL string. On LLM failure, re-raises so the caller
            can decide whether to exhaust retries and mark the job FAILED.
        """
        logger.info(
            f"[Self-Correction] attempt={attempt}/{MAX_SELF_CORRECTION_RETRIES} "
            f"for table='{table_name}'"
        )

        correction_parser = PydanticOutputParser(pydantic_object=SelfCorrectionResult)

        correction_prompt = PromptTemplate(
            template="""
You are a MySQL 8 SQL expert performing a SQL self-correction task.

A SQL patch generated for optimization failed database validation.
Your job is to output a corrected version of the SQL that will pass validation.

=== TABLE CONTEXT ===
Table: {table_name}

=== ORIGINAL SQL PATCH (FAILED) ===
{original_sql}

=== SANDBOX ERROR LOG ===
{error_log}

=== TARGET DIALECT ===
{db_dialect}

=== INSTRUCTIONS ===
- Analyze the error log carefully.
- Fix ONLY what is causing the failure — do not rewrite the entire patch.
- Return valid, runnable MySQL 8 DDL/DML.
- If the patch cannot be fixed (e.g., references a table that doesn't exist), return an empty corrected_sql.
- Do NOT wrap the SQL in markdown fences.
- Do NOT use PostgreSQL-only syntax/features.

{format_instructions}
""",
            input_variables=["table_name", "original_sql", "error_log", "db_dialect"],
            partial_variables={"format_instructions": correction_parser.get_format_instructions()},
        )

        _input = correction_prompt.format_prompt(
            table_name=table_name,
            original_sql=original_sql_patch,
            error_log=error_log[:3000],    # Truncate huge logs to avoid context overflow
            db_dialect=db_dialect or "mysql",
        )

        try:
            output = self._invoke_llm(_input.to_string())
            content = output.content

            # Strip markdown fences if any
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "").strip()
            elif "```" in content:
                content = content.split("```")[1].strip()

            result = correction_parser.parse(content)
            logger.info(
                f"[Self-Correction] attempt={attempt} — explanation: {result.explanation[:120]}"
            )
            return result.corrected_sql.strip()

        except Exception as e:
            logger.error(f"[Self-Correction] LLM call failed on attempt={attempt}: {e}")
            raise


# Singleton instance
llm_engine = LLMEngine()
