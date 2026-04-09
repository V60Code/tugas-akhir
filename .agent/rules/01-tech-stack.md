---
trigger: always_on
---

# Tech Stack & Architecture Constraints

You are strictly required to use the following technology stack. Do not deviate or suggest alternatives unless explicitly asked.

## Frontend
- **Framework:** Next.js 14+ (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS + Shadcn/UI
- **State Management:** Zustand (Strictly no Redux/Context API for global state)
- **Visualization:** React Flow (Preferred for interactive ERD) or Mermaid.js
- **Data Fetching:** TanStack Query (React Query) or Axios

## Backend
- **Language:** Python 3.10+
- **Framework:** FastAPI (Async)
- **Database Engine:** PostgreSQL 15+ (Strictly required for JSONB/Enum support)
- **Database ORM:** SQLAlchemy (AsyncSession) or SQLModel
- **Migrations:** Alembic
- **Validation:** Pydantic V2

## Async & Infrastructure
- **Task Queue:** Celery (using Redis as Broker)
- **Storage:** MinIO or AWS S3 Compatible
- **Sandbox:** Docker SDK for Python (strictly for running Dry-Run SQL)

## Core Engines (The Brain)
- **SQL Parsing:** SQLGlot (Must be used for parsing SQL to AST)
- **AI Logic:** LangChain (Python version)
- **LLM Models:** OpenAI (GPT-4o) or Google Gemini 1.5 Pro (Do not use local LLMs)

## Architecture Pattern
- **Monorepo Structure:** `/frontend` and `/backend` in root.
- **Communication:** REST API (FastAPI) consumed by Next.js.
- **Isolation:** All SQL execution MUST happen inside ephemeral Docker containers.