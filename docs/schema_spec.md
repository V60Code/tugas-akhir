# Schema Specification — SQL Optimizer

> Database schema reference for all PostgreSQL tables used by the backend.  
> ORM: SQLAlchemy (AsyncSession) · Migrations: Alembic

---

## Table of Contents

- [users](#users)
- [projects](#projects)
- [analysis_jobs](#analysis_jobs)
- [job_artifacts](#job_artifacts)
- [ai_suggestions](#ai_suggestions)
- [sandbox_logs](#sandbox_logs)
- [Entity Relationship Diagram](#entity-relationship-diagram)
- [Cascade Rules](#cascade-rules)

---

## `users`

Stores authenticated user accounts.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default `uuid4` | Unique user ID |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Login identifier |
| `password_hash` | VARCHAR(255) | NOT NULL | Bcrypt hash of the password |
| `full_name` | VARCHAR(100) | NULL | Display name |
| `created_at` | TIMESTAMP | default `now()` | Account creation time |

---

## `projects`

Logical grouping of analysis jobs per user.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default `uuid4` | Unique project ID |
| `user_id` | UUID | FK → `users.id` ON DELETE CASCADE | Project owner |
| `name` | VARCHAR(255) | NOT NULL | Project name (non-blank) |
| `description` | TEXT | NULL | Optional description |
| `created_at` | TIMESTAMP | default `now()` | Creation timestamp |

---

## `analysis_jobs`

Represents a single SQL file upload + analysis workflow.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default `uuid4` | Job ID (used as Celery task reference) |
| `project_id` | UUID | FK → `projects.id` ON DELETE CASCADE | Parent project |
| `original_filename` | VARCHAR(255) | NOT NULL | Name of the uploaded `.sql` file |
| `status` | ENUM(`JobStatus`) | NOT NULL, default `QUEUED` | Current lifecycle state |
| `app_context` | ENUM(`AppContext`) | NOT NULL | `READ_HEAVY` or `WRITE_HEAVY` |
| `db_dialect` | VARCHAR(50) | NULL | `postgres` (default) or `mysql` |
| `error_message` | TEXT | NULL | Populated when `status = FAILED` |
| `tokens_used` | INTEGER | default `0` | LLM token consumption (for monitoring) |
| `created_at` | TIMESTAMP | default `now()` | Upload timestamp |
| `updated_at` | TIMESTAMP | auto-updated | Last status change |

**`JobStatus` enum values:** `QUEUED · PROCESSING · COMPLETED · FAILED · FINALIZED`  
**`AppContext` enum values:** `READ_HEAVY · WRITE_HEAVY`

---

## `job_artifacts`

Tracks file artifacts stored in MinIO. A job may have multiple artifacts.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default `uuid4` | Artifact ID |
| `job_id` | UUID | FK → `analysis_jobs.id` | Parent job |
| `artifact_type` | ENUM(`ArtifactType`) | NOT NULL | Type of artifact |
| `storage_path` | VARCHAR(500) | NOT NULL | MinIO object path: `{user_id}/{job_id}/{filename}` |
| `file_size_bytes` | INTEGER | NULL | File size in bytes |
| `created_at` | TIMESTAMP | default `now()` | Upload time |

**`ArtifactType` enum values:**

| Value | Description |
|---|---|
| `RAW_UPLOAD` | Original uploaded `.sql` file after Privacy Shield sanitization |
| `OPTIMIZED_SQL` | Final `.sql` file after sandbox validation of accepted AI patches |

---

## `ai_suggestions`

AI-generated optimization suggestions for an analysis job.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default `uuid4` | Suggestion ID |
| `job_id` | UUID | FK → `analysis_jobs.id` | Parent job |
| `table_name` | VARCHAR(100) | NOT NULL | Target table (`"GLOBAL"` for schema-wide issues) |
| `issue` | VARCHAR(255) | NOT NULL | Short issue title (≤ 80 chars) |
| `suggestion` | TEXT | NOT NULL | Detailed explanation and remediation steps |
| `risk_level` | ENUM(`RiskLevel`) | NOT NULL | `LOW · MEDIUM · HIGH` |
| `confidence` | FLOAT | NULL | LLM confidence score (0.0 – 1.0) |
| `action_status` | ENUM(`ActionStatus`) | default `PENDING` | User's decision on this suggestion |
| `sql_patch` | TEXT | NOT NULL | Concrete SQL DDL/DML to apply the fix |

**`RiskLevel` enum:** `LOW · MEDIUM · HIGH`  
**`ActionStatus` enum:** `PENDING · ACCEPTED · REJECTED`

---

## `sandbox_logs`

Records the result of each Docker sandbox validation attempt, including self-correction history.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default `uuid4` | Log entry ID |
| `job_id` | UUID | FK → `analysis_jobs.id` | Parent job |
| `attempt_number` | INTEGER | default `1` | Which attempt produced this log |
| `is_success` | BOOLEAN | NOT NULL | `true` if validation passed |
| `container_log` | TEXT | NULL | Combined stdout/stderr from the Docker container (max 100 000 chars). Includes self-correction history prefix when applicable. |
| `execution_time_ms` | INTEGER | NULL | Container runtime in milliseconds |
| `was_self_corrected` | BOOLEAN | NOT NULL, default `false` | `true` if the LLM self-correction was invoked at least once |
| `self_correction_count` | INTEGER | NOT NULL, default `0` | Number of self-correction iterations performed |
| `created_at` | TIMESTAMP | default `now()` | Log creation time |

> **Note:** `container_log` follows this format when `was_self_corrected = true`:
> ```
> === SELF-CORRECTION HISTORY ===
> [Self-Correction] Attempt 1: ...
> [Self-Correction] Attempt 2: ...
>
> === FINAL SANDBOX LOG ===
> ERROR: ...
> ```

---

## Entity Relationship Diagram

```
users
 └─── projects (user_id → users.id)
       └─── analysis_jobs (project_id → projects.id)
             ├─── job_artifacts (job_id → analysis_jobs.id)
             ├─── ai_suggestions (job_id → analysis_jobs.id)
             └─── sandbox_logs (job_id → analysis_jobs.id)
```

---

## Cascade Rules

| Parent | Child | On Delete |
|---|---|---|
| `users` | `projects` | CASCADE |
| `projects` | `analysis_jobs` | CASCADE |
| `analysis_jobs` | `job_artifacts` | CASCADE |
| `analysis_jobs` | `ai_suggestions` | CASCADE |
| `analysis_jobs` | `sandbox_logs` | CASCADE |

> All cascades are defined at the **database level** (not only ORM level) to ensure referential integrity even if rows are deleted via raw SQL.

---

## MinIO Storage Layout

```
sql-jobs/                          ← bucket name (from MINIO_BUCKET_NAME env)
  {user_id}/
    {job_id}/
      clean.sql                    ← RAW_UPLOAD artifact (sanitized DDL)
      optimized.sql                ← OPTIMIZED_SQL artifact (after finalization)
```

Storage paths are stored in `job_artifacts.storage_path` and used to generate presigned URLs on download.
