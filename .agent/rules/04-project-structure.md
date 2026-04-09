---
trigger: always_on
---

# Project Directory Structure

You must strictly follow this directory structure. Do not create new top-level folders without permission.

```text
sql-optimizer-project/
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── backend/                  # FastAPI + Celery
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py           # FastAPI Entry
│   │   ├── worker.py         # Celery Entry
│   │   ├── api/v1/           # Endpoints
│   │   ├── core/             # Config, Security
│   │   ├── db/               # Session
│   │   ├── models/           # SQLAlchemy Models
│   │   ├── schemas/          # Pydantic Models
│   │   └── services/         # Logic: parser, sandbox, llm_engine
│   └── tests/
│
├── frontend/                 # Next.js + TypeScript
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── src/
│   │   ├── app/              # Pages & Layouts
│   │   ├── components/       # UI (shadcn), visualizer
│   │   ├── lib/              # api.ts, utils
│   │   ├── store/            # Zustand
│   │   └── types/            # TypeScript Interfaces
│   └── public/
│
├── data/                     # Local Data (Gitignored)
│   ├── postgres/
│   ├── redis/
│   └── minio/
│
└── docs/                     # Documentation
    ├── prd.md
    ├── api_contract.md
    ├── schema_spec.md
    └── tech_stack.md