# Audit Implementasi Pengujian Proyek

Dokumen ini disusun berdasarkan pemindaian langsung terhadap struktur proyek, terutama folder `backend/tests/`, konfigurasi `backend/pytest.ini`, `backend/requirements.txt`, `frontend/package.json`, `scripts/e2e_test.py`, serta report coverage yang sudah tersedia pada `backend/htmlcov/status.json`.

## Ringkasan Temuan

Secara umum, proyek ini sudah memiliki pengujian otomatis yang cukup kuat pada sisi backend. Terdapat 173 test function Python di folder `backend/tests/`, mencakup endpoint FastAPI, parser SQL, schema Pydantic, security/authentication, service MinIO, service sandbox Docker, LLM engine, self-correction, dan worker Celery.

Namun, sisi frontend belum memiliki pengujian otomatis unit/UI/E2E. Tidak ditemukan file `*.test.ts`, `*.spec.ts`, konfigurasi Jest, Vitest, React Testing Library, Cypress, maupun Playwright di source frontend. Pengujian frontend saat ini cenderung bersifat manual melalui penggunaan aplikasi.

## A. Pengujian Backend

### 1. Framework Pengujian

Backend menggunakan `pytest` sebagai framework utama. Hal ini terlihat dari:

- `backend/pytest.ini`
- `backend/requirements.txt`
- folder `backend/tests/`

Konfigurasi `pytest.ini` menunjukkan:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --cov=app --cov-report=term-missing --cov-report=html:htmlcov
```

Dependency testing backend yang tercatat di `backend/requirements.txt` adalah:

- `pytest`
- `pytest-asyncio`
- `pytest-cov`
- `httpx`
- `docker`

Jadi, framework utama backend adalah `pytest`, dengan `pytest-asyncio` untuk test async dan `pytest-cov` untuk coverage.

### 2. Pengujian Endpoint FastAPI

Ada pengujian endpoint FastAPI di `backend/tests/test_api_endpoints.py`.

Test endpoint tidak menggunakan `fastapi.testclient.TestClient`, tetapi menggunakan:

- `httpx.AsyncClient`
- `httpx.ASGITransport(app=app)`

Artinya, test dijalankan langsung terhadap aplikasi ASGI FastAPI tanpa menjalankan server HTTP sungguhan.

Endpoint yang diuji mencakup:

- `GET /`
- `GET /health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/projects/`
- `POST /api/v1/projects/`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`
- `DELETE /api/v1/projects/{project_id}`
- `GET /api/v1/projects/{project_id}/jobs`
- `POST /api/v1/jobs/upload`
- `GET /api/v1/jobs/{job_id}/status`
- `GET /api/v1/jobs/{job_id}/suggestions`
- `GET /api/v1/jobs/{job_id}/download`
- `GET /api/v1/jobs/{job_id}/schema`
- `POST /api/v1/jobs/{job_id}/finalize`

Untuk endpoint upload, terdapat test seperti `test_upload_success_queues_celery`, `test_upload_minio_failure_returns_500`, dan `test_upload_non_sql_extension_returns_400`.

Untuk endpoint status, terdapat test seperti `test_status_without_auth_returns_401` dan `test_status_nonexistent_job_returns_404_when_authed`.

Kesimpulannya, pengujian endpoint API sudah ada dan bersifat integration-style, tetapi dependency eksternal seperti database, MinIO, dan Celery dibuat mock.

### 3. Pengujian Layanan Asinkron Celery

Pada implementasi aplikasi, endpoint upload dan finalize memanggil Celery melalui:

- `process_analysis_job.delay(str(job.id))`
- `finalize_job.delay(str(job.id))`

Namun, pada test otomatis tidak ditemukan konfigurasi `task_always_eager = True`. Tidak ada konfigurasi yang membuat Celery berjalan sinkron melalui eager mode.

Pola testing yang digunakan adalah mocking terhadap task Celery. Contohnya:

- `patch("app.api.v1.jobs.process_analysis_job")`
- `patch("app.api.v1.jobs.finalize_job")`
- lalu test memastikan `.delay()` dipanggil.

Selain itu, logic worker diuji langsung dengan memanggil fungsi internal:

- `_process_analysis_job_async`
- `_finalize_job_async`

File yang relevan:

- `backend/tests/test_api_endpoints.py`
- `backend/tests/test_worker.py`

Jadi, strategi testing Celery proyek ini adalah:

- endpoint test memastikan `.delay()` terpanggil
- worker test memanggil fungsi async internal secara langsung
- tidak menggunakan `task_always_eager = True`
- tidak menjalankan worker Celery sungguhan pada unit test

### 4. Mocking Google Gemini dan MinIO

Pada test otomatis backend, pemanggilan Google Gemini dan MinIO tidak ditembak langsung. Keduanya di-mock.

Untuk Gemini atau LLM:

- `app.worker.llm_engine` di-mock pada test worker
- `ChatGoogleGenerativeAI` di-mock pada test service LLM
- `PydanticOutputParser` juga sering di-mock agar output LLM dapat dikontrol

Contoh file:

- `backend/tests/test_worker.py`
- `backend/tests/test_services.py`
- `backend/tests/test_self_correction.py`

Untuk MinIO:

- `app.api.v1.jobs.minio_service` di-mock pada test endpoint
- `app.worker.minio_service` di-mock pada test worker
- response `get_object()` dibuat menggunakan `MagicMock`
- `upload_file()` dan `get_presigned_url()` diatur hasilnya secara manual

Contoh file:

- `backend/tests/test_api_endpoints.py`
- `backend/tests/test_worker.py`
- `backend/tests/test_services.py`

Dengan demikian, pengujian otomatis backend tidak menghabiskan kuota Gemini dan tidak membutuhkan MinIO sungguhan.

Catatan: terdapat `scripts/e2e_test.py` yang menjalankan lifecycle API terhadap `http://localhost:8000`. Jika skrip ini dijalankan pada sistem live dengan API, worker, Redis, database, MinIO, dan API key Gemini aktif, maka alurnya dapat memicu layanan sungguhan. Skrip ini berbeda dari pytest backend yang offline dan berbasis mock.

## B. Pengujian Sandbox Docker

### 1. Test Khusus SandboxService

Ada test khusus untuk `SandboxService` di `backend/tests/test_services.py`, khususnya class `TestSandboxService`.

Skenario yang diuji antara lain:

- Docker client tidak tersedia
- Docker client berhasil dibuat
- validasi SQL sukses
- validasi SQL gagal karena syntax error
- exception Docker, misalnya image pull gagal
- pemilihan image PostgreSQL atau MySQL berdasarkan dialect
- command readiness PostgreSQL melalui `pg_isready`
- command readiness MySQL melalui `mysqladmin ping`
- timeout saat menunggu database siap
- timeout sebelum eksekusi SQL
- cleanup container tetap tidak membuat test gagal meskipun `stop()` error

Pada test ini Docker tidak benar-benar menjalankan container. Docker client dan container dibuat mock dengan `MagicMock`.

### 2. Pengujian SQL Berbahaya atau Destruktif

Tidak ditemukan test yang secara eksplisit memasukkan SQL destruktif seperti:

- `DROP TABLE`
- `TRUNCATE`
- `DELETE FROM` tanpa kondisi

Namun, ada test error-path untuk SQL invalid, yaitu:

- `test_run_sql_validation_sql_error_returns_failure`

Test tersebut menjalankan input:

```sql
INVALID SQL;;
```

Lalu output `psql` dimock menjadi:

```text
ERROR: syntax error at or near
```

Test ini memastikan `SandboxService.run_sql_validation()` mengembalikan:

- `success = False`
- `logs` berisi pesan `ERROR`

Ada juga test worker finalize yang mensimulasikan sandbox gagal karena syntax error, lalu sistem mencoba self-correction:

- `test_sandbox_fail_then_self_correction_succeeds`
- `test_exhausted_retries_marks_job_failed_without_upload`
- `test_llm_exception_during_correction_marks_failed`
- `test_empty_corrected_sql_breaks_correction_loop`

Untuk cleanup container, test happy path memastikan:

- `container.stop(timeout=5)` dipanggil
- `container.remove(force=True)` dipanggil

Selain itu, `test_cleanup_failure_does_not_propagate` memastikan kegagalan cleanup tidak merusak hasil utama validasi.

Kesimpulannya, pengujian sandbox sudah menguji validasi SQL gagal, error logs, timeout, dan cleanup container secara mock. Tetapi belum ada test eksplisit yang menggunakan query destruktif seperti `DROP TABLE`. Belum ada juga integration test yang benar-benar menjalankan Docker container nyata untuk membuktikan cleanup setelah SQL destruktif di runtime asli.

## C. Pengujian Frontend

### 1. Framework Pengujian UI

Frontend menggunakan Next.js dan Zustand, tetapi belum memiliki framework pengujian UI otomatis.

Berdasarkan `frontend/package.json`, script yang tersedia hanya:

```json
{
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "next lint"
}
```

Tidak ditemukan dependency atau konfigurasi untuk:

- Jest
- React Testing Library
- Vitest
- Cypress
- Playwright

Tidak ditemukan juga file test frontend seperti:

- `*.test.ts`
- `*.test.tsx`
- `*.spec.ts`
- `*.spec.tsx`

Catatan: beberapa file test ditemukan di `frontend/node_modules/`, tetapi itu milik dependency pihak ketiga, bukan test milik proyek.

### 2. Pengujian Zustand Store

Tidak ditemukan pengujian khusus untuk Zustand store.

Store utama yang relevan adalah:

- `frontend/src/store/useJobStore.ts`

Fungsi penting di dalamnya:

- `startAnalysis`
- `pollStatus`
- `cancelPolling`
- `triggerFinalize`
- `fetchDownloadUrl`
- `resetJob`
- `loadJobFromHistory`

Namun, tidak ada file test yang menguji fungsi-fungsi tersebut. Dengan demikian, behavior seperti polling status, transisi status job, error handling upload, finalize, dan download URL belum diuji secara otomatis di frontend.

### 3. End-to-End Testing

Tidak ditemukan framework E2E browser seperti Cypress atau Playwright pada frontend.

Yang ada adalah:

- `scripts/e2e_test.py`

Skrip ini merupakan E2E API test berbasis Python `requests`, bukan E2E browser test. Alurnya menguji:

- health check
- register
- login
- create project
- upload SQL
- polling status
- get suggestions
- get schema
- finalize
- polling finalization
- download
- beberapa error case

Skrip ini berguna untuk black-box API testing, tetapi tidak mensimulasikan klik pengguna di UI Next.js. Jadi, proyek belum memiliki E2E testing frontend berbasis browser.

## D. Metrik dan Coverage

### 1. Konfigurasi Coverage

Ada konfigurasi coverage pada `backend/pytest.ini`:

```ini
--cov=app --cov-report=term-missing --cov-report=html:htmlcov
```

Artinya, saat `pytest` dijalankan dari folder `backend`, coverage akan dihitung untuk package `app` dan report HTML akan dibuat di:

```text
backend/htmlcov
```

README juga menyebutkan bahwa coverage HTML dihasilkan di folder `backend/htmlcov`.

### 2. Persentase Coverage Saat Ini

Berdasarkan file report terakhir yang tersedia di `backend/htmlcov/status.json`, coverage backend adalah:

- total statement: 1155
- statement covered: 1117
- statement missing: 38
- coverage terhitung: 96,71%
- coverage yang ditampilkan di HTML: 97%

Catatan penting: saya mencoba menjalankan ulang `pytest`, tetapi environment Python yang aktif belum memiliki dependency backend:

- global `python` gagal karena `fastapi` tidak ditemukan
- `.venv` proyek gagal karena `pytest` tidak ditemukan

Jadi angka 96,71% di atas berasal dari report coverage yang sudah ada di repository, bukan hasil eksekusi ulang pada audit ini.

### 3. Teknik Pengujian yang Dominan

Teknik pengujian yang paling dominan pada proyek ini adalah automated backend testing dengan kombinasi:

- unit testing
- integration-style endpoint testing berbasis mock
- service-level testing
- worker/business-flow testing berbasis mock

Pengujian backend tidak sepenuhnya integration test terhadap infrastruktur nyata, karena database, MinIO, Celery, Gemini, dan Docker sandbox umumnya di-mock.

Pada sisi frontend, teknik yang dominan masih manual testing, karena belum ada test unit UI, test Zustand, maupun E2E browser test.

Secara keseluruhan, karakter testing proyek ini dapat dirangkum sebagai berikut:

| Area | Kondisi Saat Ini |
|---|---|
| Backend unit test | Ada dan cukup kuat |
| Backend endpoint test | Ada, menggunakan `httpx.AsyncClient` dan mock dependency |
| Celery test | Ada, dengan mock `.delay()` dan direct-call ke worker logic |
| Database test | Menggunakan mock session, bukan database nyata |
| MinIO test | Di-mock pada pytest |
| Gemini test | Di-mock pada pytest |
| Sandbox test | Ada, tetapi Docker/container di-mock |
| SQL destruktif seperti `DROP TABLE` | Belum ditemukan |
| Frontend unit/UI test | Belum ada |
| Zustand store test | Belum ada |
| E2E browser test | Belum ada |
| E2E API script | Ada, melalui `scripts/e2e_test.py` |
| Coverage backend | Ada, terakhir sekitar 96,71% |

## Kesimpulan untuk Bab 3

Implementasi pengujian pada proyek ini paling kuat berada di sisi backend. Backend menggunakan `pytest`, `pytest-asyncio`, dan `pytest-cov` untuk menguji endpoint FastAPI, service, parser, security, worker Celery, MinIO service, LLM engine, dan Docker sandbox service. Sebagian besar test dirancang agar dapat berjalan offline dengan cara melakukan mocking terhadap dependency eksternal seperti database, MinIO, Celery, Gemini, dan Docker.

Frontend belum memiliki automated testing. Tidak ada Jest, React Testing Library, Vitest, Cypress, maupun Playwright pada source frontend. Oleh karena itu, validasi UI dan workflow pengguna masih bergantung pada pengujian manual dan skrip E2E API berbasis Python.

Dari sisi coverage, backend memiliki konfigurasi coverage dan report terakhir menunjukkan cakupan sekitar 96,71%. Walaupun angka ini tinggi, perlu dicatat bahwa coverage tersebut dominan mengukur logic backend dengan dependency yang di-mock, bukan pengujian integrasi penuh terhadap layanan nyata.
