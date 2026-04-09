# Instrumen Pengujian Fungsional

## 1. Tujuan
Dokumen ini mendefinisikan instrumen pengujian fungsional untuk memastikan seluruh sistem SQL Optimizer berjalan sesuai kebutuhan fungsional, dari sisi user interface, API backend, worker asinkron, integrasi layanan eksternal, sampai alur finalisasi dan unduh hasil.

## 2. Ruang Lingkup
Cakupan pengujian meliputi seluruh project:
- Frontend Next.js: autentikasi, dashboard project, upload SQL, hasil analisis, ERD visualizer.
- Backend FastAPI: auth, project, jobs, schema endpoint, error handling.
- Worker Celery: analisis AI, finalisasi, self-correction, sandbox validation.
- Data layer: PostgreSQL, MinIO, Redis.
- Security flow: JWT, ownership check, middleware route guard, rate limiting.
- Operasional: health endpoint, Flower monitoring, robustness alur async.

## 3. Lingkungan Uji yang Disarankan
- Mode: docker compose (direkomendasikan untuk uji end-to-end).
- Service aktif: frontend, api, worker, db, redis, minio.
- Data awal:
  - Minimal 2 akun user berbeda.
  - Minimal 2 project pada user A dan 1 project pada user B.
  - Beberapa file SQL valid dan tidak valid.
- Browser: Chrome/Edge terbaru.
- API test tool: Postman/Insomnia atau curl.

## 4. Kriteria Kelulusan Umum
Skenario dinyatakan lulus jika:
- Perilaku aktual sesuai hasil yang diharapkan.
- HTTP status code dan pesan error sesuai kontrak.
- Tidak ada crash di frontend/backend/worker.
- Data persistence dan state transisi job konsisten.

## 5. Tabel Instrumen Pengujian Fungsional

### A. Auth dan Session

| ID | Uji Kasus | Skenario | Hasil yang Diharapkan |
|---|---|---|---|
| AUTH-01 | Register berhasil | Isi email valid, password >= 8, submit register | Akun terbentuk, user otomatis login, redirect ke dashboard |
| AUTH-02 | Register email duplikat | Register dengan email yang sudah terdaftar | Response error 400, pesan user sudah ada |
| AUTH-03 | Register password pendek | Isi password < 8 karakter | Validasi gagal 422 atau error validasi di UI |
| AUTH-04 | Login berhasil | Login dengan kredensial benar | Dapat token, cookie auth tersimpan, redirect dashboard |
| AUTH-05 | Login gagal | Password salah | Error login tampil, tidak redirect |
| AUTH-06 | Get profile /me | Panggil endpoint me setelah login | Data user sesuai akun login |
| AUTH-07 | Logout | Klik tombol logout | Cookie auth terhapus, redirect login |
| AUTH-08 | Session expired handling | Akses API dengan token expired | User diarahkan ke login dengan indikator session expired |
| AUTH-09 | Auth route guard | Akses /dashboard tanpa token | Redirect ke /login |
| AUTH-10 | Redirect user terautentikasi | Buka /login saat sudah login | Redirect ke /dashboard |

### B. Project Management

| ID | Uji Kasus | Skenario | Hasil yang Diharapkan |
|---|---|---|---|
| PRJ-01 | List project | User login membuka dashboard | Daftar project milik user tampil |
| PRJ-02 | Empty state project | User tanpa project membuka dashboard | Tampil empty state + tombol create project |
| PRJ-03 | Create project valid | Isi nama dan deskripsi valid | Project baru tersimpan dan muncul di list |
| PRJ-04 | Create project invalid | Nama kosong atau whitespace | Validasi gagal, error tampil |
| PRJ-05 | Open project detail | Klik card project | Masuk halaman detail project yang dipilih |
| PRJ-06 | Update project | Ubah nama/deskripsi project | Data project terbarui |
| PRJ-07 | Delete project berhasil | Hapus project milik sendiri | Project hilang dari list, data terkait terhapus |
| PRJ-08 | Delete project unauthorized | User B mencoba hapus project user A via API | Ditolak 403 |
| PRJ-09 | Get project not found | Akses project ID tidak ada | Response 404 |
| PRJ-10 | List project jobs | Buka riwayat job pada detail project | Riwayat job sesuai project dan urut terbaru |

### C. Upload SQL dan Analisis Job

| ID | Uji Kasus | Skenario | Hasil yang Diharapkan |
|---|---|---|---|
| JOB-01 | Upload SQL valid | Upload file .sql ukuran valid | Job dibuat status QUEUED, response 202 + job_id |
| JOB-02 | Upload ekstensi invalid | Upload file non-.sql | Ditolak 400 |
| JOB-03 | Upload file terlalu besar | Upload SQL > batas ukuran | Ditolak 413 |
| JOB-04 | Upload unauthorized | Panggil upload tanpa token | Ditolak 401/403 |
| JOB-05 | Upload ke project user lain | User B upload ke project user A | Ditolak 403 |
| JOB-06 | Polling status queued/processing | Setelah upload, frontend polling status | Status bergerak QUEUED/PROCESSING secara konsisten |
| JOB-07 | Status completed | Worker selesai analisis | Status menjadi COMPLETED |
| JOB-08 | Status failed | Paksa kondisi error parsing/LLM/storage | Status menjadi FAILED + error message tersimpan |
| JOB-09 | Suggestions retrieval | Ambil /jobs/{id}/suggestions setelah COMPLETED | Data original SQL + suggestions tampil |
| JOB-10 | Suggestions sebelum complete | Panggil suggestions saat job belum selesai | Response kosong sesuai desain, tidak crash |
| JOB-11 | Schema endpoint valid | Panggil /jobs/{id}/schema | Kembalikan tables, columns, relationships |
| JOB-12 | Schema endpoint unauthorized | Akses schema job user lain | Ditolak 403 |

### D. Finalisasi dan Download

| ID | Uji Kasus | Skenario | Hasil yang Diharapkan |
|---|---|---|---|
| FIN-01 | Finalize dengan accepted suggestions | Pilih suggestion lalu finalize | Task finalize ter-queue dan status diproses |
| FIN-02 | Finalize tanpa accepted suggestions | Finalize dengan list kosong | Alur tetap berjalan dengan patch kosong/non-kritis |
| FIN-03 | Finalize unauthorized | Finalize job milik user lain | Ditolak 403 |
| FIN-04 | Sandbox validasi sukses | Patch valid di sandbox | Job status FINALIZED, artifact optimized tersimpan |
| FIN-05 | Sandbox gagal lalu self-correct sukses | Patch awal gagal, koreksi AI berhasil | Job akhirnya FINALIZED |
| FIN-06 | Self-correct retries exhausted | Semua retry gagal | Job status FAILED, log error tersimpan |
| FIN-07 | Download setelah finalized | Klik download pada job FINALIZED | Presigned URL diterima dan file bisa diunduh |
| FIN-08 | Download sebelum finalized | Download saat status belum FINALIZED | Ditolak 400 |
| FIN-09 | Download artifact tidak ada | Job FINALIZED tapi artifact hilang | Response 404/500 sesuai handler |
| FIN-10 | Download unauthorized | User lain unduh hasil job bukan miliknya | Ditolak 403 |

### E. ERD Visualizer dan Parser SQL

| ID | Uji Kasus | Skenario | Hasil yang Diharapkan |
|---|---|---|---|
| ERD-01 | Render ERD normal | Buka halaman ERD dengan job valid | Diagram tabel dan relasi tampil |
| ERD-02 | Missing FK warnings | Upload SQL parsial dengan referensi tabel hilang | Warning partial upload tampil |
| ERD-03 | Parse warning handling | SQL kompleks menimbulkan warning parser | Warning tampil tanpa memblokir visualisasi |
| ERD-04 | JobId tidak ada di query param | Akses halaman ERD tanpa jobId | Tampil error dan opsi kembali |
| ERD-05 | Schema kosong | SQL tidak memiliki CREATE TABLE | Tampil empty-state no tables |
| ERD-06 | Risk badge mapping | Suggestions dengan risk HIGH/MEDIUM/LOW | Highlight risiko per tabel tampil sesuai |
| ERD-07 | View details warning | Klik detail warning di halaman ERD | Detail warning dapat ditampilkan |
| ERD-08 | Unauthorized ERD access | Buka ERD job user lain | Ditolak 403 |

### F. Keamanan dan Validasi Akses

| ID | Uji Kasus | Skenario | Hasil yang Diharapkan |
|---|---|---|---|
| SEC-01 | JWT required endpoints | Akses endpoint protected tanpa token | Ditolak 401/403 |
| SEC-02 | Ownership project guard | User B akses project user A | Ditolak 403 |
| SEC-03 | Ownership job guard | User B akses status/suggestion/download job user A | Ditolak 403 |
| SEC-04 | Password hashing | Register user baru | Password tersimpan hash, bukan plaintext |
| SEC-05 | Register rate limiting | Spam register > batas | Request ditolak 429 |
| SEC-06 | Login rate limiting | Spam login > batas | Request ditolak 429 |
| SEC-07 | Upload rate limiting | Spam upload > batas | Request ditolak 429 |
| SEC-08 | Global error normalization | Trigger validation error pydantic | Response detail berupa string render-safe |
| SEC-09 | Session cookie cleanup | Logout user | Token dan profile cookie terhapus |
| SEC-10 | Data leakage prevention | Login akun kedua di browser sama | Data project akun sebelumnya tidak tersisa |

### G. Integrasi Layanan Eksternal

| ID | Uji Kasus | Skenario | Hasil yang Diharapkan |
|---|---|---|---|
| INT-01 | MinIO bucket bootstrap | Startup API saat bucket belum ada | Bucket otomatis dibuat |
| INT-02 | Upload artifact ke MinIO | Upload SQL valid | Object tersimpan pada path user/job |
| INT-03 | Fetch original SQL | Ambil suggestions dan schema | Original SQL dapat diambil dari MinIO |
| INT-04 | Redis enqueue task | Upload/finalize dipanggil | Task masuk queue Redis |
| INT-05 | Worker consume task | Worker aktif | Task diproses dari queue |
| INT-06 | LLM call transient retry | Simulasikan error transient LLM | Retry berjalan sesuai kebijakan |
| INT-07 | LLM parse output | LLM response fenced JSON | Output tetap diparse benar |
| INT-08 | Sandbox container lifecycle | Jalankan validasi SQL | Container sandbox start, exec, cleanup |
| INT-09 | Sandbox timeout handling | Simulasikan DB sandbox lambat/hang | Worker hentikan proses dan catat gagal |
| INT-10 | Flower monitoring | Buka Flower saat workload berjalan | Task dan status worker terlihat |

### H. UI/UX Fungsional Frontend

| ID | Uji Kasus | Skenario | Hasil yang Diharapkan |
|---|---|---|---|
| UI-01 | Loading hydration login | Refresh halaman login saat ada cookie auth | Tidak ada flicker state yang salah |
| UI-02 | Login form validation | Submit tanpa email/password | Tombol disabled atau validasi muncul |
| UI-03 | Register confirm password mismatch | Password dan konfirmasi beda | Tampil warning mismatch |
| UI-04 | Dashboard skeleton | Muat dashboard saat fetch project | Skeleton loading tampil |
| UI-05 | Analyze button behavior | Klik analyze tanpa file | Tombol tidak aktif |
| UI-06 | Progress message | Job sedang diproses | Progress status tampil di UI |
| UI-07 | Suggestion toggle | Centang/uncentang suggestion | Diff preview berubah sesuai pilihan |
| UI-08 | Finalize button visibility | Status COMPLETED vs FINALIZED | Tombol finalize/download tampil sesuai status |
| UI-09 | History view results | Klik view hasil dari job history | Hasil lama dapat dimuat ulang |
| UI-10 | Error banner visibility | API gagal atau download gagal | Error banner tampil informatif |

### I. Reliabilitas Alur Async dan Data Konsistensi

| ID | Uji Kasus | Skenario | Hasil yang Diharapkan |
|---|---|---|---|
| REL-01 | Polling cancel on unmount | Pindah halaman saat polling aktif | Polling berhenti, tidak ada memory leak |
| REL-02 | Reset job state antar project | Pindah project setelah job sebelumnya | State job lama tidak terbawa |
| REL-03 | Commit status sequencing | Cek status saat process_analysis berjalan | Urutan status valid: QUEUED -> PROCESSING -> COMPLETED/FAILED |
| REL-04 | Finalize sequencing | Finalize dipicu | Status bergerak FINALIZING/PROCESSING -> FINALIZED/FAILED |
| REL-05 | Artifacts consistency | Job FINALIZED | Minimal ada RAW_UPLOAD dan OPTIMIZED_SQL artifact |
| REL-06 | Suggestions consistency | Job COMPLETED | Suggestions terasosiasi dengan job_id benar |
| REL-07 | Sandbox log persistence | Finalize selesai (sukses/gagal) | SandboxLog tersimpan dengan metadata attempt |
| REL-08 | Download link freshness | Minta URL download beberapa kali | URL tetap valid dalam masa berlaku yang ditentukan |

## 6. Prioritas Eksekusi Uji
Prioritas disarankan:
1. P0 (wajib lulus): AUTH-01..05, PRJ-01..04, JOB-01..04, JOB-07..09, FIN-01..04, FIN-07, SEC-01..04.
2. P1 (sangat penting): ERD-01..04, FIN-05..06, INT-01..05, UI-05..09, REL-01..04.
3. P2 (peningkatan mutu): INT-06..10, ERD-05..08, REL-05..08, UI-01..04, UI-10.

## 7. Format Catatan Hasil Uji
Gunakan format berikut saat eksekusi:
- ID uji
- Tanggal uji
- Penguji
- Build/commit
- Langkah aktual
- Hasil aktual
- Status: Lulus/Gagal
- Bukti: screenshot/log/link
- Catatan perbaikan (jika gagal)

## 8. Keterkaitan dengan Test Otomatis yang Sudah Ada
Project ini sudah memiliki test suite backend yang dapat dipakai sebagai baseline verifikasi:
- backend/tests/test_api_endpoints.py
- backend/tests/test_worker.py
- backend/tests/test_services.py
- backend/tests/test_self_correction.py
- backend/tests/test_security.py
- backend/tests/test_parser.py
- backend/tests/test_main.py
- backend/tests/test_schemas.py

Instrumen pada dokumen ini memperluas cakupan ke pengujian fungsional end-to-end dan UX yang belum seluruhnya tercakup oleh unit/integration test otomatis.
