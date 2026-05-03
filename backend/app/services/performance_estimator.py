from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models.suggestion import AISuggestion


@dataclass
class _Buckets:
    index_related: int = 0
    over_indexing_fix: int = 0
    normalization_fix: int = 0
    datatype_fix: int = 0
    constraint_fix: int = 0
    json_fix: int = 0


def _norm(text: str) -> str:
    return (text or "").lower()


def _classify_suggestions(suggestions: Iterable[AISuggestion]) -> _Buckets:
    buckets = _Buckets()
    for s in suggestions:
        text = f"{s.issue} {s.suggestion} {s.sql_patch}"
        t = _norm(text)

        if "index" in t:
            buckets.index_related += 1
        if "over-index" in t or "over index" in t or "drop index" in t:
            buckets.over_indexing_fix += 1
        if "normaliz" in t:
            buckets.normalization_fix += 1
        if "varchar" in t or "text" in t or "data type" in t or "datatype" in t:
            buckets.datatype_fix += 1
        if "constraint" in t or "not null" in t or "check (" in t:
            buckets.constraint_fix += 1
        if "json" in t or "generated column" in t:
            buckets.json_fix += 1
    return buckets


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def estimate_performance_impact(
    suggestions: list[AISuggestion],
    app_context: str,
    db_dialect: str | None,
    table_count: int,
) -> dict:
    """
    Build a lightweight predictive performance report from accepted AI findings.

    This is intentionally heuristic (rule-based) so it is deterministic, fast,
    and does not require an additional paid LLM call during result rendering.
    """
    buckets = _classify_suggestions(suggestions)
    total = len(suggestions)
    context = (app_context or "READ_HEAVY").upper()
    dialect = (db_dialect or "mysql").lower()
    safe_tables = max(1, table_count)

    # Base scoring from issue categories
    read_score = (
        buckets.index_related * 1.8
        + buckets.json_fix * 1.2
        + buckets.datatype_fix * 0.9
        + buckets.normalization_fix * 1.1
        + buckets.constraint_fix * 0.3
    )
    write_score = (
        buckets.over_indexing_fix * 1.6
        + buckets.datatype_fix * 0.6
        + buckets.normalization_fix * 0.8
        + buckets.index_related * (-0.35)
    )
    maintenance_score = (
        buckets.index_related * 0.7
        + buckets.constraint_fix * 0.3
        + buckets.over_indexing_fix * (-0.6)
    )

    # Workload weighting
    if context == "READ_HEAVY":
        read_score *= 1.25
        write_score *= 0.9
    else:
        read_score *= 0.9
        write_score *= 1.25

    # Scale down optimistic estimates for very large schemas
    scale = _clamp(20 / safe_tables, 0.45, 1.0)
    read_score *= scale
    write_score *= scale
    maintenance_score *= scale

    # Convert to % ranges
    read_min = _clamp(read_score * 1.8, -8, 45)
    read_max = _clamp(read_min + max(3, read_score * 1.7), -2, 60)

    write_min = _clamp(write_score * 1.4, -25, 35)
    write_max = _clamp(write_min + max(2, abs(write_score) * 1.2), -20, 45)

    maint_min = _clamp(maintenance_score * 1.1, -20, 25)
    maint_max = _clamp(maint_min + max(1, abs(maintenance_score) * 0.8), -15, 35)

    confidence = _clamp(0.45 + (min(total, 8) * 0.06) + (buckets.index_related * 0.02), 0.4, 0.92)

    summary = (
        f"Prediksi untuk workload {context}: optimasi berpotensi menurunkan latency baca sekitar "
        f"{read_min:.1f}%–{read_max:.1f}% dan mengubah performa tulis sekitar "
        f"{write_min:.1f}%–{write_max:.1f}%."
    )

    assumptions = [
        f"Estimasi berbasis {total} AI suggestion yang dipilih/tersedia.",
        "Nilai aktual dipengaruhi ukuran data, cardinality, pola query, dan hardware.",
        "Angka diasumsikan pada beban aplikasi stabil setelah query plan cache warm-up.",
        f"Dialect terdeteksi: {dialect}.",
    ]

    return {
        "method": "heuristic_from_ai_suggestions",
        "summary": summary,
        "read_latency_improvement_pct": {
            "min": round(read_min, 2),
            "max": round(read_max, 2),
        },
        "write_throughput_change_pct": {
            "min": round(write_min, 2),
            "max": round(write_max, 2),
        },
        "maintenance_cost_change_pct": {
            "min": round(maint_min, 2),
            "max": round(maint_max, 2),
        },
        "estimated_query_patterns_improved": max(1, min(50, buckets.index_related + buckets.json_fix + buckets.normalization_fix)),
        "confidence": round(confidence, 2),
        "assumptions": assumptions,
    }
