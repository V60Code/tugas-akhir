# Tech Stack Specification: SQL Optimizer & Architect

Dokumen ini mendefinisikan standar teknologi (Tech Stack) yang digunakan untuk membangun sistem "SQL Optimizer". Pemilihan teknologi ini didasarkan pada kebutuhan akan performa I/O tinggi, keamanan eksekusi (Sandboxing), dan kemampuan analisis AI.

---

## 1. Frontend (User Interface)
**Fokus:** Interaktivitas tinggi, visualisasi diagram, dan manajemen state asinkronus.

| Komponen | Teknologi | Alasan Pemilihan |
| :--- | :--- | :--- |
| **Framework** | **Next.js 14+ (App Router)** | Standar industri, mendukung SSR untuk performa awal, dan routing yang kuat. |
| **Language** | **TypeScript** | Wajib untuk Type Safety, mencegah runtime error pada struktur data API yang kompleks. |
| **State Management** | **Zustand** | Ringan dan efisien untuk mengelola global state (seperti Job ID, Upload Progress) tanpa boilerplate Redux. |
| **Data Fetching** | **TanStack Query (React Query)** | Mengelola caching API, polling otomatis (untuk status job), dan loading state. |
| **Visualization** | **React Flow** | Library terbaik untuk merender Entity Relationship Diagram (ERD) yang interaktif (bisa di-drag/zoom). |
| **UI Library** | **Shadcn/UI + Tailwind CSS** | Komponen modern, aksesibel, dan mudah dikustomisasi untuk membangun Dashboard profesional. |
| **HTTP Client** | **Axios** | Untuk melakukan request ke Backend dengan interceptor (handling token JWT). |

---

## 2. Backend (Core Logic & API)
**Fokus:** Pemrosesan data asinkronus, validasi ketat, dan orkestrasi AI.

| Komponen | Teknologi | Alasan Pemilihan |
| :--- | :--- | :--- |
| **Language** | **Python 3.10+** | Ekosistem data science/AI terbaik. Diperlukan untuk library `sqlglot` dan `langchain`. |
| **Framework** | **FastAPI** | Performa tinggi (Asynchronous), dokumentasi otomatis (Swagger UI), dan validasi input bawaan. |
| **Data Validation** | **Pydantic V2** | Validasi skema JSON request/response yang ketat dan cepat. |
| **Authentication** | **Python-Jose (JWT)** | Standar keamanan untuk token berbasis sesi (Stateless Authentication). |
| **File Handling** | **Python-Multipart** | Menangani upload file `.sql` besar dengan teknik streaming (tanpa memuat ke RAM sekaligus). |

---

## 3. Data & Infrastructure (Persistence)
**Fokus:** Integritas data, antrian tugas berat, dan penyimpanan file.

| Komponen | Teknologi | Alasan Pemilihan |
| :--- | :--- | :--- |
| **Internal Database** | **PostgreSQL 15+** | Menyimpan metadata (Users, Jobs, Projects). Mendukung UUID native dan JSONB. |
| **ORM** | **SQLAlchemy (Async) / SQLModel** | Abstraksi database modern untuk Python. |
| **Migrations** | **Alembic** | Version control untuk skema database (penting untuk perubahan skema di masa depan). |
| **Message Broker** | **Redis** | Menyimpan antrian tugas (Job Queue) untuk Celery dan Caching sementara. |
| **Object Storage** | **MinIO (Dev) / AWS S3 (Prod)** | Menyimpan file fisik (`.sql` raw, hasil parsing JSON). Database hanya menyimpan path-nya. |

---

## 4. Processing Engine (The "Brain")
**Fokus:** Parsing SQL, Logika AI, dan Eksekusi Aman.

| Komponen | Teknologi | Alasan Pemilihan |
| :--- | :--- | :--- |
| **Task Queue** | **Celery** | Menjalankan proses berat di background (Worker) agar API tidak timeout. |
| **SQL Parser** | **SQLGlot** | Library Python untuk transpilation SQL multi-dialek dan pembuatan AST (Abstract Syntax Tree). |
| **AI Orchestrator** | **LangChain** | Manajemen prompt, context injection, dan parsing output JSON dari LLM. |
| **LLM Models** | **OpenAI (GPT-4o) / Gemini 1.5 Pro** | Model AI dengan kemampuan penalaran logika (*reasoning*) tinggi. |
| **Sandbox** | **Docker SDK for Python** | Menjalankan container Docker *ephemeral* untuk validasi SQL (*Dry-Run*) secara aman dan terisolasi. |

---

## 5. Development Tools
* **Containerization:** Docker & Docker Compose (untuk menjalankan stack lokal).
* **Linting/Formatting:** ESLint (TS), Ruff/Black (Python).
* **Version Control:** Git.

---

## 6. Architecture Summary
Sistem menggunakan pola **Asynchronous Micro-services** (Modular Monolith).

1.  **Client** upload file ke **FastAPI**.
2.  **FastAPI** menyimpan file ke **MinIO** dan kirim Job ID ke **Redis**.
3.  **Celery Worker** mengambil Job, memproses dengan **SQLGlot** & **LangChain**.
4.  Worker memvalidasi hasil menggunakan **Docker Sandbox**.
5.  Hasil disimpan ke **PostgreSQL** dan status diupdate.
6.  **Client** melakukan polling dan menampilkan hasil.