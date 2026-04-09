# Tech Stack — SQL Optimizer

> Detailed breakdown of every technology used in this project, rationale for each choice, and version constraints.

---

## Frontend

| Layer | Technology | Version | Reason |
|---|---|---|---|
| Framework | **Next.js** (App Router) | 14+ | Server components, file-based routing, SSR/SSG |
| Language | **TypeScript** | 5+ | Type safety, better IDE support |
| Styling | **Tailwind CSS** | 3+ | Utility-first, fast iteration |
| Components | **Shadcn/UI** | latest | Accessible, unstyled Radix primitives |
| State | **Zustand** | 4+ | Minimal, atomic global state — no boilerplate |
| ERD Visualizer | **React Flow** | 11+ | Interactive node-edge diagrams with auto-layout |
| Graph Layout | **@dagrejs/dagre** | latest | Automatic left-to-right ERD layout |
| Data Fetching | **Axios** + **TanStack Query** | latest | API abstraction layer + cache |

---

## Backend

| Layer | Technology | Version | Reason |
|---|---|---|---|
| Language | **Python** | 3.10+ | Async support, rich AI/ML ecosystem |
| Framework | **FastAPI** | 0.100+ | Async-first, Pydantic-native, automatic OpenAPI |
| Database | **PostgreSQL** | 15+ | JSONB, Enum, advanced index types |
| ORM | **SQLAlchemy** (AsyncSession) | 2+ | Async queries, strong typing |
| Migrations | **Alembic** | 1+ | Schema versioning and rollback |
| Validation | **Pydantic** | V2 | Structured LLM output parsing, request validation |

---

## Async & Infrastructure

| Component | Technology | Reason |
|---|---|---|
| Task Queue | **Celery** + Redis broker | Offload SQL parsing + AI calls from the HTTP thread |
| Cache/Broker | **Redis** | Fast in-memory Celery broker; also used for result backend |
| File Storage | **MinIO** (S3-compatible) | Self-hosted object storage; swap to AWS S3 in production |
| SQL Sandbox | **Docker SDK for Python** | Ephemeral container per validation — never executes on host |

---

## Core Engines (The Brain)

| Engine | Technology | Role |
|---|---|---|
| SQL Parser | **SQLGlot** | Parses DDL to AST — extracts tables, columns, PK/FK/unique flags |
| AI Logic | **LangChain** (Python) | Prompt templates, output parsers, chain composition |
| LLM | **Google Gemini 2.5 Flash Lite** | Schema analysis + SQL self-correction prompts |
| Output Parsing | **PydanticOutputParser** | Forces structured JSON output from LLM |

---

## Architecture Pattern

```
Browser (Next.js)
    │  REST/JSON
    ▼
FastAPI (Python)
    ├── Sync response: 202 Accepted + job_id
    └── Celery task queued
           │
           ▼
     Celery Worker
           ├── 1. Download SQL from MinIO
           ├── 2. Parse with SQLGlot
           ├── 3. Analyze with Gemini (LangChain)
           ├── 4. Save suggestions to PostgreSQL
           └── 5. (On finalize) Validate in Docker sandbox
                     └── Self-correction loop (max 2 retries)
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| No raw SQL execution on host | All SQL runs inside ephemeral Docker containers (strict isolation) |
| Privacy Shield on upload | INSERT/COPY/VALUES stripped by streaming regex before any storage |
| Async by default | FastAPI routes are `async def`; no blocking I/O on the HTTP thread |
| Per-task DB engine | Celery fork workers each create a fresh asyncpg engine to avoid event-loop conflicts |
| Self-correction on sandbox fail | Retries are bounded (`MAX_SELF_CORRECTION_RETRIES = 2`) to prevent infinite loops |
| PydanticOutputParser | Guarantees structured JSON from LLM — no fragile regex parsing |
