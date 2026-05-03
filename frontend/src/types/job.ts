/**
 * Single Source of Truth for all job-related TypeScript types.
 *
 * All types are defined here and re-exported through @/lib/api so that
 * existing import paths continue to work. Centralising definitions here
 * prevents type divergence across the application.
 */

/** Immediate response after a file is uploaded and queued. */
export interface JobResponse {
    job_id: string;
    status: string;
    message: string;
}

/** Polling response for GET /jobs/:id/status */
export interface JobStatusResponse {
    job_id: string;
    status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'FINALIZED';
    progress_step: string | null;
    error: string | null;
    created_at: string;
}

/** A single AI-generated optimization suggestion. */
export interface AISuggestion {
    id: string;
    table_name: string;
    issue: string;
    suggestion: string;
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
    confidence: number;
    sql_patch: string;
    action_status: 'PENDING' | 'ACCEPTED' | 'REJECTED';
}

export interface MetricRange {
    min: number;
    max: number;
}

export interface PerformanceEstimate {
    method: string;
    summary: string;
    read_latency_improvement_pct: MetricRange;
    write_throughput_change_pct: MetricRange;
    maintenance_cost_change_pct: MetricRange;
    estimated_query_patterns_improved: number;
    confidence: number;
    assumptions: string[];
}

/** Response payload for GET /jobs/:id/suggestions */
export interface JobSuggestionsResponse {
    original_sql: string;
    suggestions: AISuggestion[];
    performance_estimate?: PerformanceEstimate | null;
    missing_fk_warnings: string[];
    has_missing_references: boolean;
}
