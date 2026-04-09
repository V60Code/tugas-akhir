# API Contract — SQL Optimizer

> **Version:** 1.0  
> **Base URL:** `http://localhost:8000/api/v1`  
> **Auth:** Bearer JWT (obtained from `/auth/login`)  
> **Content-Type:** `application/json` (unless stated otherwise)

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Projects](#2-projects)
3. [Jobs — Core Flow](#3-jobs--core-flow)
4. [Jobs — Results & ERD](#4-jobs--results--erd)
5. [Health](#5-health)
6. [Error Reference](#6-error-reference)
7. [Enums & Constants](#7-enums--constants)
8. [Data Models](#8-data-models)

---

## 1. Authentication

All protected endpoints require the header:

```
Authorization: Bearer <access_token>
```

---

### POST `/auth/register`

Creates a new user account.

**Request Body (`application/json`)**

| Field | Type | Required | Description |
|---|---|---|---|
| `email` | string | ✅ | Valid email address (unique) |
| `password` | string | ✅ | Plain-text password (hashed by server) |
| `full_name` | string | ✅ | Display name |

**Response `201 Created`**

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Alice",
  "created_at": "2026-03-08T00:00:00Z"
}
```

**Errors**

| Code | Reason |
|---|---|
| `400` | Email already registered |
| `422` | Validation error (missing fields, invalid email) |

---

### POST `/auth/login`

Exchanges credentials for a JWT token.

**Request Body (`application/x-www-form-urlencoded`)**

| Field | Type | Required |
|---|---|---|
| `username` | string | ✅ (email address) |
| `password` | string | ✅ |

**Response `200 OK`**

```json
{
  "access_token": "eyJhbG...",
  "token_type": "bearer"
}
```

**Errors**

| Code | Reason |
|---|---|
| `400` | Incorrect email or password |
| `422` | Missing form fields |

---

### GET `/auth/me`

Returns the currently authenticated user's profile.

> 🔒 Requires auth

**Response `200 OK`**

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Alice",
  "created_at": "2026-03-08T00:00:00Z"
}
```

---

## 2. Projects

> 🔒 All project endpoints require auth. Users can only access their own projects.

---

### GET `/projects/`

List all projects belonging to the authenticated user.

**Query Parameters**

| Param | Type | Default | Description |
|---|---|---|---|
| `skip` | int | `0` | Pagination offset |
| `limit` | int | `100` | Max results |

**Response `200 OK`**

```json
[
  {
    "id": "uuid",
    "name": "My E-commerce Schema",
    "description": "PostgreSQL schema for order management",
    "user_id": "uuid",
    "created_at": "2026-03-08T00:00:00Z",
    "job_count": 3
  }
]
```

---

### POST `/projects/`

Create a new project.

**Request Body**

```json
{
  "name": "My E-commerce Schema",
  "description": "Optional description"
}
```

| Field | Type | Required | Constraint |
|---|---|---|---|
| `name` | string | ✅ | Non-blank |
| `description` | string | ❌ | Optional |

**Response `201 Created`** — Returns `ProjectResponse` (same as GET by ID).

---

### GET `/projects/{project_id}`

Get a single project by ID.

**Response `200 OK`**

```json
{
  "id": "uuid",
  "name": "My E-commerce Schema",
  "description": "...",
  "user_id": "uuid",
  "created_at": "2026-03-08T00:00:00Z"
}
```

**Errors:** `404` Project not found · `403` Not authorized

---

### PATCH `/projects/{project_id}`

Partially update a project (name and/or description). Only provided fields are updated.

**Request Body**

```json
{
  "name": "Renamed Project",
  "description": "Updated description"
}
```

**Response `200 OK`** — Returns updated `ProjectResponse`.

---

### DELETE `/projects/{project_id}`

Delete a project and all related jobs/artifacts (cascade).

**Response `204 No Content`**

---

### GET `/projects/{project_id}/jobs`

List all analysis jobs for a project, most recent first.

**Query Parameters:** `skip`, `limit` (same as project list)

**Response `200 OK`**

```json
[
  {
    "id": "uuid",
    "original_filename": "schema.sql",
    "status": "COMPLETED",
    "app_context": "READ_HEAVY",
    "error_message": null,
    "created_at": "2026-03-08T00:00:00Z"
  }
]
```

---

## 3. Jobs — Core Flow

> 🔒 All job endpoints require auth.

The typical lifecycle of a job:

```
UPLOAD → QUEUED → PROCESSING → COMPLETED → [FINALIZE] → FINALIZED
                                    ↓                        ↓
                                  FAILED                   FAILED (after retries)
```

---

### POST `/jobs/upload`

Upload a SQL file, sanitize it (strips INSERT/COPY/VALUES), store it in MinIO, and queue an analysis job via Celery.

> ⚠️ **Privacy Shield:** INSERT, COPY, and VALUES statements are stripped **before** any processing. Raw data never touches the analysis engine.

**Request** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | ✅ | `.sql` file only |
| `project_id` | UUID | ✅ | Project this job belongs to |
| `app_context` | enum | ✅ | `READ_HEAVY` or `WRITE_HEAVY` |
| `db_dialect` | string | ❌ | `postgres` (default) or `mysql` |

**Response `202 Accepted`**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "QUEUED",
  "message": "File uploaded successfully. Analysis queued."
}
```

**Errors**

| Code | Reason |
|---|---|
| `400` | File extension is not `.sql` |
| `403` | Project belongs to another user |
| `404` | Project not found |
| `500` | MinIO upload failed |

---

### GET `/jobs/{job_id}/status`

Poll this endpoint until status is `COMPLETED` or `FAILED`.

**Response `200 OK`**

```json
{
  "job_id": "uuid",
  "status": "PROCESSING",
  "progress_step": "AI_ANALYSIS",
  "error": null,
  "created_at": "2026-03-08T00:00:00Z"
}
```

| Field | Description |
|---|---|
| `status` | `QUEUED` · `PROCESSING` · `COMPLETED` · `FAILED` · `FINALIZED` |
| `progress_step` | `"AI_ANALYSIS"` when processing, `null` otherwise |
| `error` | Error message when `status == FAILED` |

**Errors:** `404` · `403`

---

### POST `/jobs/{job_id}/finalize`

Apply accepted AI suggestions, run SQL validation in an ephemeral Docker sandbox, and generate the optimized SQL file.

> 🔐 The AI-generated SQL is **never executed on the production database.** It runs in an isolated Docker container that is destroyed after validation.

> ♻️ **Self-Correction:** If sandbox validation fails, the system automatically asks the LLM to fix the failing patch (up to `MAX_SELF_CORRECTION_RETRIES = 2` times) before marking the job as `FAILED`.

**Request Body**

```json
{
  "accepted_suggestion_ids": [
    "uuid-of-suggestion-1",
    "uuid-of-suggestion-2"
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `accepted_suggestion_ids` | `UUID[]` | IDs of suggestions the user accepts. All others are automatically set to `REJECTED`. |

**Response `200 OK`**

```json
{
  "message": "Finalization started. Check status for updates."
}
```

> Poll `GET /jobs/{job_id}/status` afterwards. Final status will be `FINALIZED` or `FAILED`.

---

## 4. Jobs — Results & ERD

---

### GET `/jobs/{job_id}/suggestions`

Retrieve AI-generated optimization suggestions. Only available when `status` is `COMPLETED` or `FINALIZED`.

**Response `200 OK`**

```json
{
  "original_sql": "CREATE TABLE orders (...);",
  "suggestions": [
    {
      "id": "uuid",
      "job_id": "uuid",
      "table_name": "orders",
      "issue": "Missing index on user_id FK column",
      "suggestion": "An unindexed FK column causes full table scans on JOIN queries...",
      "risk_level": "HIGH",
      "confidence": 0.95,
      "sql_patch": "CREATE INDEX idx_orders_user_id ON orders(user_id);",
      "action_status": "PENDING"
    }
  ],
  "missing_fk_warnings": [
    "Missing reference: 'order_items.product_id' → 'products' (table not found in uploaded file)"
  ],
  "has_missing_references": true
}
```

| Field | Description |
|---|---|
| `original_sql` | The sanitized DDL that was analyzed |
| `suggestions` | List of AI suggestions (empty if job not yet `COMPLETED`) |
| `missing_fk_warnings` | FK references pointing to tables absent from the uploaded file |
| `has_missing_references` | `true` if the upload was partial (some referenced tables missing) |

**`AISuggestion` fields**

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Suggestion ID (used in finalize request) |
| `table_name` | string | Table the suggestion applies to (`"GLOBAL"` for schema-wide issues) |
| `issue` | string | Short title (≤ 80 chars) |
| `suggestion` | string | Detailed explanation |
| `risk_level` | enum | `LOW` · `MEDIUM` · `HIGH` |
| `confidence` | float | 0.0 – 1.0 confidence score |
| `sql_patch` | string | Concrete, runnable SQL to apply the optimization |
| `action_status` | enum | `PENDING` · `ACCEPTED` · `REJECTED` |

---

### GET `/jobs/{job_id}/schema`

Parse the uploaded SQL file and return a full ERD-ready schema.

> Available for any job with status `>= QUEUED` (SQL is re-parsed on demand from MinIO).

**Response `200 OK`**

```json
{
  "job_id": "uuid",
  "tables": [
    {
      "name": "orders",
      "columns": [
        {
          "name": "id",
          "type": "INT",
          "is_primary_key": true,
          "is_foreign_key": false,
          "is_nullable": false,
          "is_unique": false
        },
        {
          "name": "user_id",
          "type": "INT",
          "is_primary_key": false,
          "is_foreign_key": true,
          "is_nullable": false,
          "is_unique": false
        }
      ],
      "foreign_keys": [
        {
          "column": "user_id",
          "references_table": "users",
          "references_column": "id"
        }
      ]
    }
  ],
  "errors": [],
  "missing_fk_warnings": [],
  "has_missing_references": false,
  "table_count": 1,
  "relationship_count": 1
}
```

| Field | Description |
|---|---|
| `tables` | Full list of parsed tables with column metadata |
| `errors` | Non-fatal parse warnings (table skipped due to syntax error) |
| `missing_fk_warnings` | FK references with no matching table in the file |
| `has_missing_references` | Convenience boolean for partial upload detection |
| `table_count` | Number of successfully parsed tables |
| `relationship_count` | Total FK relationships across all tables |

---

### GET `/jobs/{job_id}/download`

Get a presigned MinIO URL to download the optimized SQL file.

> Job must have `status == FINALIZED`.

**Response `200 OK`**

```json
{
  "download_url": "http://minio:9000/sql-jobs/user-id/job-id/optimized.sql?X-Amz-Signature=..."
}
```

The URL is valid for **1 hour**.

**Errors**

| Code | Reason |
|---|---|
| `400` | Job not yet finalized |
| `404` | Optimized artifact not found |
| `500` | Presigned URL generation failed |

---

## 5. Health

### GET `/`

```json
{ "message": "SQL Optimizer API is running", "version": "1.0.0" }
```

### GET `/health`

Docker/K8s liveness probe.

```json
{ "status": "ok" }
```

---

## 6. Error Reference

All error responses follow the FastAPI standard:

```json
{
  "detail": "Human-readable error description."
}
```

| HTTP Code | Meaning |
|---|---|
| `400` | Bad request (invalid input, wrong file type) |
| `401` | Missing or malformed Authorization header |
| `403` | Valid token but insufficient permissions |
| `404` | Resource not found |
| `422` | Request body / form validation failed (Pydantic) |
| `500` | Internal server error (storage, database, etc.) |

---

## 7. Enums & Constants

### `AppContext`

| Value | Description |
|---|---|
| `READ_HEAVY` | AI prioritizes indexes for SELECT performance |
| `WRITE_HEAVY` | AI identifies indexes that hurt INSERT/UPDATE speed |

### `JobStatus`

| Value | Description |
|---|---|
| `QUEUED` | Job created, waiting for Celery worker |
| `PROCESSING` | AI analysis in progress |
| `COMPLETED` | Analysis done, suggestions available |
| `FINALIZED` | Sandbox validation passed, optimized SQL ready |
| `FAILED` | Unrecoverable error (see `error_message`) |

### `RiskLevel`

| Value | Meaning |
|---|---|
| `LOW` | Safe to apply without downtime |
| `MEDIUM` | May require brief maintenance window |
| `HIGH` | Requires careful planning and testing |

### `ActionStatus`

| Value | Meaning |
|---|---|
| `PENDING` | User has not yet reviewed this suggestion |
| `ACCEPTED` | User accepted — included in finalized SQL |
| `REJECTED` | User rejected — excluded from finalized SQL |

### Self-Correction

| Constant | Value | Description |
|---|---|---|
| `MAX_SELF_CORRECTION_RETRIES` | `2` | Number of times the LLM is asked to fix a failing sandbox validation before the job is marked `FAILED` |

---

## 8. Data Models

### `ProjectResponse`

```json
{
  "id": "uuid",
  "name": "string",
  "description": "string | null",
  "user_id": "uuid",
  "created_at": "datetime"
}
```

### `JobSummaryResponse`

```json
{
  "id": "uuid",
  "original_filename": "string",
  "status": "JobStatus",
  "app_context": "AppContext",
  "error_message": "string | null",
  "created_at": "datetime"
}
```

### `ERDColumn`

```json
{
  "name": "string",
  "type": "string",
  "is_primary_key": "boolean",
  "is_foreign_key": "boolean",
  "is_nullable": "boolean",
  "is_unique": "boolean"
}
```

### `ERDForeignKey`

```json
{
  "column": "string",
  "references_table": "string",
  "references_column": "string"
}
```

### `ERDTable`

```json
{
  "name": "string",
  "columns": ["ERDColumn"],
  "foreign_keys": ["ERDForeignKey"]
}
```
