# SQL Optimizer Platform

Platform web untuk menganalisis file DDL SQL, menghasilkan rekomendasi optimasi berbasis AI, memvalidasi patch SQL di sandbox terisolasi, lalu menyediakan hasil SQL final yang dapat diunduh.

## Tujuan
- Membantu user menemukan masalah desain skema database lebih cepat.
- Memberikan rekomendasi SQL patch yang actionable.
- Menurunkan risiko eksekusi patch dengan validasi sandbox sebelum finalisasi.

## Fitur Utama
- Autentikasi user berbasis JWT.
- Manajemen project (create, read, update, delete).
- Upload file SQL dan antrian analisis async.
- Analisis skema menggunakan LLM.
- Finalisasi patch dengan loop self-correction jika validasi gagal.
- Penyimpanan artifact SQL di object storage.
- Visualisasi skema ERD berbasis parser SQL.
- Monitoring task worker via Flower.

## Arsitektur Singkat
Sistem menggunakan arsitektur service terpisah:
- Frontend: Next.js.
- Backend API: FastAPI.
- Worker async: Celery.
- Queue/Broker: Redis.
- Database: PostgreSQL.
- Object storage: MinIO.
- SQL validation runtime: container sandbox.
- AI engine: Google Gemini via LangChain.

## Tech Stack
- Frontend: Next.js 14, TypeScript, Zustand, Axios, React Flow.
- Backend: FastAPI, SQLAlchemy Async, Alembic, Pydantic.
- Worker: Celery + Redis.
- Storage: MinIO.
- SQL parsing: SQLGlot.
- AI: LangChain + langchain-google-genai.
- Testing: pytest, pytest-asyncio, pytest-cov.
- Containerization: Docker Compose.

## Struktur Direktori
- backend: API, model, schema, service, worker, tests.
- frontend: web app Next.js.
- docs: dokumen requirement dan teknis.
- prepare: materi analisis/desain tambahan.
- data: volume data lokal untuk service container.
- scripts: utilitas tambahan.

## Prasyarat
- Docker dan Docker Compose.
- (Opsional local dev) Python 3.10+ dan Node.js 18+.
- API key Google Gemini untuk fitur AI.

## Quick Start (Direkomendasikan: Docker)
1. Salin file environment.
2. Isi nilai yang diperlukan, terutama GOOGLE_API_KEY dan SECRET_KEY.
3. Jalankan semua service.
4. Jalankan migrasi database.
5. Akses frontend dan backend.

Contoh perintah:

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api alembic upgrade head
```

URL default:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/api/v1/docs
- Flower: http://localhost:5555
- MinIO Console: http://localhost:9001

## Menjalankan Secara Local (Tanpa Docker untuk API/Frontend)
Tetap disarankan menjalankan PostgreSQL, Redis, dan MinIO via Docker.

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Set variabel frontend:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Menjalankan Testing
Backend tests:

```bash
cd backend
pytest
```

Coverage HTML akan dihasilkan di folder backend/htmlcov.

## Alur Utama Penggunaan
1. Register lalu login.
2. Buat project.
3. Upload file SQL pada project.
4. Pantau status job hingga COMPLETED.
5. Tinjau suggestions AI.
6. Pilih suggestion yang diterima lalu jalankan finalize.
7. Unduh optimized SQL saat status FINALIZED.

## Endpoint Inti API
Auth:
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- GET /api/v1/auth/me

Projects:
- GET /api/v1/projects/
- POST /api/v1/projects/
- GET /api/v1/projects/{project_id}
- PATCH /api/v1/projects/{project_id}
- DELETE /api/v1/projects/{project_id}
- GET /api/v1/projects/{project_id}/jobs

Jobs:
- POST /api/v1/jobs/upload
- GET /api/v1/jobs/{job_id}/status
- GET /api/v1/jobs/{job_id}/suggestions
- GET /api/v1/jobs/{job_id}/schema
- POST /api/v1/jobs/{job_id}/finalize
- GET /api/v1/jobs/{job_id}/download

## Diagram yang Tersedia di Repository
- 01-system-context-diagram.md
- 02-component-diagram.md
- 03-deployment-diagram.md
- 04-state-machine-diagram.md
- 05-domain-class-diagram.md
- 06-data-flow-diagram.md
- 07-c4-model-diagram.md
- 08-requirement-traceability-diagram.md

## Catatan Keamanan
- Jangan commit file environment berisi kredensial nyata.
- Segera rotate secret jika pernah ter-publish.
- Batasi akses endpoint monitoring (Flower, MinIO Console) hanya untuk internal.
- Gunakan secret kuat untuk SECRET_KEY dan FLOWER_PASSWORD.

## License
Tambahkan lisensi sesuai kebutuhan organisasi atau institusi.
