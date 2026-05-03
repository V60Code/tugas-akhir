# Bab 3.4 - Implementasi Frontend, Layanan Asinkron, dan Validasi Sandbox

Dokumen ini merangkum hasil pembacaan struktur direktori `frontend/` dan `backend/` untuk kebutuhan penulisan Bab 3 Skripsi bagian implementasi. Fokus pembahasan diarahkan pada dua area utama, yaitu implementasi frontend dan layanan asinkron, serta implementasi validasi sandbox berbasis Docker SDK.

## Gambaran Struktur Direktori

Secara umum, proyek dibagi menjadi dua bagian besar:

- `frontend/` berisi aplikasi antarmuka berbasis Next.js 14
- `backend/` berisi layanan API berbasis FastAPI, worker asinkron Celery, dan sandbox validasi SQL

Beberapa file inti yang paling relevan terhadap implementasi ini adalah:

- `frontend/src/app/dashboard/[projectId]/page.tsx`
- `frontend/src/store/useJobStore.ts`
- `frontend/src/lib/api.ts`
- `backend/app/api/v1/jobs.py`
- `backend/app/worker.py`
- `backend/app/services/sandbox.py`

## A. Implementasi Frontend dan Layanan Asinkron

### 1. Komponen Frontend Utama

Berdasarkan implementasi yang ada, fitur upload file, loading/progress state, dan rendering hasil rekomendasi AI terutama ditangani oleh halaman utama:

- `frontend/src/app/dashboard/[projectId]/page.tsx`

Nama komponen React utamanya adalah:

- `ProjectDetailPage`

Komponen ini merupakan pusat interaksi analisis SQL. Di dalam satu file ini, beberapa tanggung jawab utama dilakukan sekaligus:

1. menerima file SQL dari pengguna
2. memicu proses upload dan analisis
3. menampilkan loading state
4. menampilkan progress message hasil polling
5. menampilkan daftar rekomendasi AI
6. menampilkan preview perubahan SQL
7. memicu finalisasi dan download hasil

### 2. Komponen atau File yang Menangani Upload File

Upload file dilakukan langsung di dalam `ProjectDetailPage`, bukan pada komponen terpisah.

Bagian yang menangani upload terdiri dari:

- state lokal `file`
- fungsi `handleFileChange`
- fungsi `handleAnalyze`
- action Zustand `startAnalysis`

Implementasi utamanya terlihat pada:

- `handleFileChange` untuk membaca file dari input
- `handleAnalyze` untuk memanggil proses analisis

Secara teknis:

- file dipilih melalui elemen `<input type="file" accept=".sql" />`
- tombol `Analyze` memanggil `handleAnalyze()`
- `handleAnalyze()` lalu memanggil `startAnalysis(file, projectId, appContext, dbDialect)`

Dengan demikian, walaupun tidak ada komponen bernama khusus seperti `UploadForm`, fungsi upload secara nyata berada di dalam komponen `ProjectDetailPage`.

### 3. Komponen atau Bagian yang Menampilkan Progress Bar atau Loading State

Pada implementasi saat ini, frontend tidak memakai komponen progress bar numerik yang terpisah. Yang digunakan adalah loading state berbasis status teks dan ikon spinner.

Loading state utama juga dirender langsung oleh `ProjectDetailPage`.

Elemen yang digunakan adalah:

- ikon `Loader2` dari `lucide-react`
- variabel store `progressMessage`
- flag `isAnalyzing`

Status analisis dihitung dengan:

```ts
const isAnalyzing = status === 'UPLOADING' || status === 'PROCESSING' || status === 'FINALIZING';
```

Lalu UI menampilkan indikator proses melalui blok:

- pesan upload: `Uploading SQL file…`
- pesan proses AI: `File uploaded. AI analysis in progress…`
- pesan polling: `Analyzing… (QUEUED/PROCESSING)`
- pesan sandbox: `Running sandbox validation…`

Jadi, istilah "progress bar/loading state" pada proyek ini lebih tepat dijelaskan sebagai:

- loading state berbasis spinner
- progress state berbasis polling status backend
- progress message tekstual yang berubah sesuai fase proses

### 4. Komponen atau Bagian yang Merender Hasil Rekomendasi AI

Hasil rekomendasi AI juga dirender langsung di `ProjectDetailPage`.

Bagian hasil analisis muncul ketika:

- `status === 'COMPLETED'`
- atau `status === 'FINALIZED'`
- dan `results` tersedia

Di dalam file ini, hasil AI ditampilkan melalui beberapa bagian:

- daftar rekomendasi pada panel "Optimization Found"
- daftar checkbox untuk memilih rekomendasi yang diterapkan
- preview SQL diff pada komponen `SqlDiffViewer`
- ringkasan estimasi performa
- warning missing foreign key reference

Nama komponen tambahan yang dipakai untuk render hasil SQL diff adalah:

- `SqlDiffViewer`

File komponen tersebut berada di:

- `frontend/src/components/ui/SqlDiffViewer.tsx`

Jadi, jika ditanya komponen asli yang merender hasil rekomendasi AI, jawabannya adalah:

- komponen utama: `ProjectDetailPage`
- komponen pendukung preview SQL: `SqlDiffViewer`

### 5. Implementasi State Management dengan Zustand

State management pada frontend menggunakan Zustand. Store utama yang menangani proses analisis job adalah:

- `useJobStore`

File implementasinya:

- `frontend/src/store/useJobStore.ts`

Store ini menyimpan state penting seperti:

- `jobId`
- `status`
- `results`
- `downloadUrl`
- `downloadError`
- `error`
- `progressMessage`

Action penting di dalam `useJobStore` adalah:

- `startAnalysis`
- `pollStatus`
- `cancelPolling`
- `triggerFinalize`
- `fetchDownloadUrl`
- `resetJob`
- `loadJobFromHistory`

### 6. Action Zustand yang Bertugas Melakukan Polling

Action Zustand yang secara khusus bertugas melakukan polling status ke backend adalah:

- `pollStatus`

Action ini bekerja dengan cara:

1. membaca `jobId` dari store
2. memanggil API `getJobStatus(jobId)`
3. memeriksa status hasil backend
4. jika status masih `QUEUED` atau `PROCESSING`, menjadwalkan polling berikutnya
5. jika status `COMPLETED`, mengambil hasil rekomendasi lewat `getJobSuggestions(jobId)`
6. jika status `FAILED`, menyimpan pesan error ke store
7. jika status `FINALIZED`, menandai proses akhir selesai

Penjadwalan polling dilakukan dengan:

```ts
_pollingTimerId = setTimeout(() => get().pollStatus(), 2500);
```

Artinya:

- interval polling = 2500 ms
- polling dilakukan menggunakan `setTimeout`, bukan `setInterval`
- timer ID disimpan pada variabel module-level `_pollingTimerId`

Selain itu:

- `startAnalysis()` akan memanggil `await get().pollStatus()`
- `triggerFinalize()` juga melanjutkan polling setelah backend finalisasi dipicu

Jadi, jika ditanya nama action polling yang asli, jawabannya adalah:

- `pollStatus`

### 7. Implementasi Layer API di Frontend

Komunikasi frontend ke backend dilakukan melalui file:

- `frontend/src/lib/api.ts`

Beberapa fungsi API yang relevan adalah:

- `uploadSqlFile()`
- `getJobStatus()`
- `getJobSuggestions()`
- `finalizeJob()`
- `getDownloadUrl()`
- `getJobSchema()`

Fungsi `uploadSqlFile()` menggunakan `FormData` dan mengirim request ke:

- `POST /api/v1/jobs/upload`

Sedangkan `getJobStatus()` mengakses:

- `GET /api/v1/jobs/{jobId}/status`

### 8. Implementasi Backend Asinkron dengan Celery

Pada sisi backend, task Celery utama yang menangani pemrosesan AI adalah:

- `process_analysis_job`

Task wrapper Celery-nya dideklarasikan sebagai:

```python
@celery.task(name="app.worker.process_analysis_job")
def process_analysis_job(job_id: str):
```

Di balik wrapper ini, logika bisnis utamanya dikerjakan oleh fungsi async:

- `_process_analysis_job_async(job_id, session_factory)`

Alur kerja `_process_analysis_job_async` adalah:

1. mengambil job dari database
2. mengubah status job menjadi `PROCESSING`
3. mengambil file SQL dari MinIO
4. mem-parse SQL menjadi representasi schema
5. memanggil `llm_engine.analyze_schema(...)`
6. menyimpan rekomendasi AI ke tabel `ai_suggestions`
7. mengubah status job menjadi `COMPLETED`

### 9. Cara FastAPI Memicu Task Celery pada Endpoint `/upload`

FastAPI memicu task Celery di endpoint:

- `POST /api/v1/jobs/upload`

Nama fungsi endpoint-nya adalah:

- `upload_sql_file`

Setelah file berhasil:

1. divalidasi
2. disanitasi
3. diunggah ke MinIO
4. metadata job disimpan ke database
5. `db.commit()` dilakukan
6. task Celery dipicu dengan:

```python
process_analysis_job.delay(str(job.id))
```

Jadi, pola implementasinya adalah:

- FastAPI menerima request
- FastAPI menyimpan job ke database
- FastAPI menaruh job ke antrean Celery dengan `.delay(...)`
- Celery worker memprosesnya secara asynchronous di background

Selain task analisis, ada juga task finalisasi:

- `finalize_job`

yang dideklarasikan sebagai:

```python
@celery.task(name="app.worker.finalize_job")
def finalize_job(job_id: str):
```

Task ini dipicu dari endpoint:

- `POST /api/v1/jobs/{job_id}/finalize`

melalui:

```python
finalize_job.delay(str(job.id))
```

## B. Implementasi Validasi Sandbox Berbasis Docker SDK

### 1. Docker Image yang Digunakan

Image database pada sandbox dipilih secara dinamis berdasarkan dialek SQL:

- jika MySQL: `mysql:8`
- jika bukan MySQL: `postgres:15-alpine`

Pemilihannya dilakukan dengan:

```python
use_mysql = _is_mysql_dialect(db_dialect)
image = "mysql:8" if use_mysql else "postgres:15-alpine"
```

Karena sistem optimasi utama lebih berorientasi ke MySQL, maka pada alur umum proyek ini image yang paling sering digunakan adalah:

- `mysql:8`

Jadi, jika ditanya image basis data yang digunakan saat membangkitkan sandbox container, jawaban teknis yang tepat adalah:

- `mysql:8` untuk dialek MySQL
- `postgres:15-alpine` untuk dialek PostgreSQL

### 2. Cara Sistem Menggabungkan `raw_ddl` dengan `sql_patch`

Penggabungan SQL tidak dilakukan di `sandbox.py`, tetapi dilakukan lebih dulu di:

- `backend/app/worker.py`

tepatnya pada fungsi:

- `_finalize_job_async`

Alurnya adalah:

1. worker mengambil `original_sql` dari artifact yang diunggah pengguna
2. worker mengambil semua suggestion yang status-nya `ACCEPTED`
3. worker membangun string SQL baru bernama `optimized_sql`
4. `optimized_sql` berisi SQL asli + marker AI + seluruh `sql_patch` yang dipilih

Implementasinya:

```python
optimized_sql = original_sql + f"\n\n{_AI_SECTION_MARKER}\n"
for s in suggestions:
    optimized_sql += f"\n-- Issue: {s.issue}\n"
    optimized_sql += f"{s.sql_patch}\n"
```

Dengan kata lain, format penggabungannya adalah:

1. `raw_ddl` asli
2. marker `/* --- AI OPTIMIZATIONS --- */`
3. komentar issue
4. SQL patch hasil AI

Contoh bentuk finalnya secara konseptual:

```sql
CREATE TABLE users (...);
CREATE TABLE orders (...);

/* --- AI OPTIMIZATIONS --- */

-- Issue: Missing composite index
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- Issue: Missing NOT NULL constraint
ALTER TABLE users MODIFY email VARCHAR(255) NOT NULL;
```

Jadi, sandbox menerima satu string SQL utuh yang sudah berisi gabungan antara DDL asli dan patch AI.

### 3. Cara SQL Dieksekusi di Dalam Container

Eksekusi SQL di sandbox dilakukan menggunakan Docker SDK for Python, bukan memanggil CLI `docker exec` secara shell manual.

Alurnya adalah:

1. container dijalankan dengan `self.client.containers.run(...)`
2. sistem menunggu database di dalam container siap
3. file SQL hasil gabungan disalin ke container menggunakan `put_archive()`
4. SQL dieksekusi menggunakan `container.exec_run(...)`

#### a. Menjalankan Container

Container dibuat dengan:

```python
container = self.client.containers.run(
    image,
    name=container_name,
    environment=env,
    detach=True,
    network_disabled=True,
    mem_limit="256m",
)
```

Parameter pentingnya:

- `detach=True`
- `network_disabled=True`
- `mem_limit="256m"`

#### b. Menyalin File SQL ke Container

SQL tidak dikirim sebagai command inline panjang, tetapi dibuat dulu menjadi file `validate.sql`, lalu dimasukkan ke container melalui arsip tar:

```python
container.put_archive("/tmp", tar_stream)
```

File tujuan di container adalah:

- `/tmp/validate.sql`

#### c. Menjalankan SQL

Perintah eksekusi disusun berdasarkan dialek:

Untuk MySQL:

```python
sql_cmd = "sh -lc 'mysql -uroot -proot sandbox < /tmp/validate.sql'"
```

Untuk PostgreSQL:

```python
sql_cmd = "psql -U postgres -d postgres -f /tmp/validate.sql"
```

Lalu dieksekusi dengan:

```python
exec_result = container.exec_run(sql_cmd, stdout=True, stderr=True)
```

Jadi, cara eksekusinya adalah:

- memakai method Docker SDK `exec_run()`
- output `stdout` dan `stderr` ditangkap sekaligus

### 4. Cara Menangkap Pesan Error jika Validasi Gagal

Pesan error diambil dari hasil `exec_run()` tersebut.

Implementasinya:

```python
exec_result = container.exec_run(sql_cmd, stdout=True, stderr=True)
exit_code, raw_output = _unpack_exec_result(exec_result)
output = raw_output.decode("utf-8", errors="replace")

return {"success": exit_code == 0, "logs": output}
```

Artinya:

- `stdout` dan `stderr` digabung dalam `raw_output`
- output di-decode menjadi string UTF-8
- hasilnya disimpan pada field `logs`
- jika `exit_code != 0`, maka validasi dianggap gagal

Dengan demikian, pesan error SQL seperti syntax error, table not found, constraint error, atau engine error akan masuk ke:

- `validation_result["logs"]`

Nilai `logs` inilah yang:

- disimpan ke tabel `sandbox_logs`
- diringkas ke `job.error_message`
- dipakai sebagai input self-correction ke LLM

### 5. Mekanisme Cleanup atau Penghancuran Container

Sistem tidak menggunakan:

- `remove=True`
- `auto_remove=True`

Sebaliknya, cleanup dilakukan secara eksplisit di blok `finally`.

Implementasinya adalah:

```python
finally:
    if container:
        try:
            container.stop(timeout=5)
            container.remove(force=True)
            logger.info(f"Sandbox container '{container_name}' cleaned up.")
        except Exception as e:
            logger.warning(f"Failed to cleanup container '{container_name}': {e}")
```

Dengan pendekatan ini, container akan selalu dicoba dihentikan dan dihapus, baik:

- validasi berhasil
- validasi gagal
- terjadi exception di tengah proses
- terjadi timeout

Jadi, jaminan agar container tidak menumpuk di server diberikan oleh:

- blok `finally`
- `container.stop(timeout=5)`
- `container.remove(force=True)`

Tambahan pembatasan resource yang juga membantu mencegah pemborosan server adalah:

- `mem_limit="256m"`
- `network_disabled=True`
- timeout global `SANDBOX_TIMEOUT_SECONDS = 30`

### 6. Ringkasan Alur Validasi Sandbox

Secara ringkas, urutan implementasinya adalah:

1. backend menyusun `optimized_sql` dari DDL asli dan patch AI
2. sandbox memilih image database sesuai dialek
3. sandbox menjalankan container sementara
4. sandbox menunggu database di dalam container siap
5. file `validate.sql` disalin ke `/tmp/validate.sql`
6. SQL dieksekusi lewat `container.exec_run(...)`
7. output `stdout/stderr` ditangkap sebagai `logs`
8. container dihentikan dan dihapus di blok `finally`

## Kesimpulan

Berdasarkan implementasi kode, frontend proyek ini memusatkan proses upload, progress monitoring, dan render hasil AI pada satu halaman utama, yaitu `ProjectDetailPage` di `frontend/src/app/dashboard/[projectId]/page.tsx`. State management dilakukan dengan Zustand melalui `useJobStore`, dan action utama untuk polling backend adalah `pollStatus`.

Pada sisi backend, FastAPI tidak memproses analisis AI secara sinkron. Endpoint `/upload` hanya membuat job lalu memicu task Celery `process_analysis_job.delay(...)`. Dengan arsitektur ini, proses parsing, analisis AI, penyimpanan hasil, hingga validasi SQL dapat dijalankan di background tanpa memblokir request utama.

Untuk validasi SQL, sistem menggunakan Docker SDK dengan container database sementara. Image yang dipakai dipilih berdasarkan dialek, yaitu `mysql:8` atau `postgres:15-alpine`. SQL asli dan patch AI digabung lebih dahulu di worker, lalu dikirim ke sandbox sebagai satu file SQL utuh. Eksekusi dilakukan melalui `container.exec_run(...)`, log kesalahan ditangkap melalui output command, dan container dibersihkan secara eksplisit memakai `container.stop()` serta `container.remove(force=True)` pada blok `finally`.

## Daftar Nama Implementasi Inti

Berikut daftar nama file, komponen, store, action, dan fungsi inti yang bisa langsung dipakai pada penulisan skripsi:

- Komponen halaman utama frontend: `ProjectDetailPage`
- File frontend utama: `frontend/src/app/dashboard/[projectId]/page.tsx`
- Komponen preview SQL: `SqlDiffViewer`
- Store Zustand: `useJobStore`
- Action polling Zustand: `pollStatus`
- Action upload analisis: `startAnalysis`
- Action finalisasi: `triggerFinalize`
- Fungsi API upload frontend: `uploadSqlFile`
- Endpoint FastAPI upload: `upload_sql_file`
- Celery task analisis: `process_analysis_job`
- Fungsi async worker analisis: `_process_analysis_job_async`
- Celery task finalisasi: `finalize_job`
- Fungsi async worker finalisasi: `_finalize_job_async`
- Service sandbox: `SandboxService`
- Fungsi validasi sandbox: `run_sql_validation`
