# SQL Optimizer — Product Requirements Document (PRD)

> **Project:** SQL Optimizer — AI-Powered Database Schema Analyzer  
> **Version:** 1.0  
> **Date:** 2026-03-08  
> **Status:** In Development

---

## 1. Problem Statement

Database developers and DBAs frequently write SQL schemas that are functionally correct but contain hidden performance bottlenecks — missing indexes, poorly designed foreign keys, bloated index sets, and JSONB columns without GIN indexes. Identifying these issues requires deep PostgreSQL expertise and manual inspection, which is time-consuming and error-prone.

**SQL Optimizer** automates this process by:
1. Accepting an uploaded SQL DDL file
2. Parsing the schema to understand its structure
3. Sending the schema to an AI model for analysis
4. Returning concrete, runnable SQL patches to fix the identified issues
5. Validating those patches in a sandboxed environment before delivery

---

## 2. Core Features

### F-01 — SQL Upload with Privacy Shield

- Users upload `.sql` files via the web interface.
- The backend **strips all INSERT, COPY, and VALUES statements** via streaming regex before any analysis.
- No raw user data ever reaches the AI engine or the database.

### F-02 — AI Schema Analysis

- The sanitized DDL is parsed by **SQLGlot** into a structured schema representation.
- The schema (tables, columns, PK/FK/nullable/unique flags) is sent to **Gemini** via LangChain.
- The AI returns 3–8 structured suggestions per job with:
  - Issue title
  - Explanation
  - Risk level (LOW / MEDIUM / HIGH)
  - Confidence score
  - Concrete SQL patch

### F-03 — ERD Visualizer

- Users can view an interactive Entity-Relationship Diagram rendered with **React Flow**.
- Nodes are color-coded by AI risk level (red = HIGH, amber = MEDIUM, green = LOW).
- Edges represent FK relationships; orphan FKs (missing referenced tables) are flagged.
- Warning banners alert users when the upload is partial (referenced tables missing).

### F-04 — Accept / Reject Suggestions

- Users review AI suggestions one by one.
- Each suggestion can be accepted (checkbox) or rejected.
- Only accepted suggestions are included in the finalized SQL.

### F-05 — Sandbox Validation with AI Self-Correction

- Accepted suggestions are combined with the original DDL into an "optimized SQL" file.
- The combined SQL is validated in an **ephemeral Docker container** (never on the production DB).
- If validation fails:
  - The LLM is asked to self-correct the failing patch (up to **2 retries**).
  - If the patch is uncorrectable, the job is marked `FAILED` with a detailed error log.
- If validation passes, the final SQL is stored in MinIO and available for download.

### F-06 — Download Optimized SQL

- After finalization, users can download the validated, optimized SQL via a presigned MinIO URL.
- The URL is valid for 1 hour.

---

## 3. User Roles

| Role | Capabilities |
|---|---|
| **Authenticated User** | Upload SQL, view analysis results, manage projects, download artifacts |
| *(Admin — future)* | View all projects, revoke access, monitor job queues |

---

## 4. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Privacy** | No raw INSERT/data statements ever stored or analyzed |
| **Performance** | API routes return in < 200 ms (heavy work offloaded to Celery) |
| **Scalability** | Celery workers are horizontally scalable |
| **Isolation** | All SQL execution in ephemeral Docker containers (30 s timeout) |
| **Reliability** | Partial schema parse success — one broken table does not fail the entire job |
| **Type Safety** | Strict TypeScript on frontend, full Python type hints on backend |

---

## 5. Out of Scope (v1.0)

- Real-time SQL execution against user's production database
- Multi-user project collaboration / sharing
- Support for non-PostgreSQL/MySQL dialects beyond basic parsing
- Automatic application of optimizations to a live database
- Admin dashboard
- Email notifications on job completion

---

## 6. Tech Stack Summary

See [`tech_stack.md`](./tech_stack.md) for the full breakdown.

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 + TypeScript + Tailwind + Zustand + React Flow |
| Backend | FastAPI + SQLAlchemy + PostgreSQL + Alembic |
| Workers | Celery + Redis |
| Storage | MinIO (S3-compatible) |
| AI | Gemini 2.5 Flash Lite via LangChain |
| SQL Parsing | SQLGlot |
| Sandboxing | Docker SDK for Python |

---

## 7. Success Metrics

| Metric | Target |
|---|---|
| Job completion rate | > 90% of submitted jobs reach `COMPLETED` |
| Self-correction success rate | > 50% of failed sandbox runs correctable by LLM |
| Average analysis time | < 60 seconds end-to-end |
| Privacy shield effectiveness | 0% of data statements reaching the analysis layer |
