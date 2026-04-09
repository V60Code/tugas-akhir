/**
 * Single Source of Truth for all project-related TypeScript types.
 *
 * All types are defined here and re-exported from @/lib/api.ts so that
 * existing import paths continue to work. Centralising definitions here
 * prevents type divergence between the API layer and the rest of the app.
 */

// ── Project types ────────────────────────────────────────────────────────────

export interface ProjectResponse {
    id: string;
    name: string;
    description: string | null;
    user_id: string;
    created_at: string;
}

/** Returned by GET /projects/ — includes job_count from backend JOIN query */
export interface ProjectListItem extends ProjectResponse {
    job_count: number;
}

export interface ProjectCreate {
    name: string;
    description?: string;
}

export interface ProjectUpdate {
    name: string;
    description?: string;
}

// ── Job summary type (for project history listing) ───────────────────────────

export interface JobSummary {
    id: string;
    original_filename: string;
    status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'FINALIZED';
    app_context: 'READ_HEAVY' | 'WRITE_HEAVY';
    created_at: string;
    error_message: string | null;
}

// ── Shared enum ──────────────────────────────────────────────────────────────

export type AppContext = 'READ_HEAVY' | 'WRITE_HEAVY';

// ── ERD Schema types (for React Flow visualizer) ─────────────────────────────

export interface ERDColumn {
    name: string;
    type: string;
    is_primary_key: boolean;
    is_foreign_key: boolean;
    is_nullable: boolean;
    is_unique: boolean;
}

export interface ERDForeignKey {
    column: string;
    references_table: string;
    references_column: string;
}

export interface ERDTable {
    name: string;
    columns: ERDColumn[];
    foreign_keys: ERDForeignKey[];
}

export interface ERDSchemaResponse {
    job_id: string;
    tables: ERDTable[];
    errors: string[];
    missing_fk_warnings: string[];
    has_missing_references: boolean;
    table_count: number;
    relationship_count: number;
}

