# Schema Specification

Dokumen ini berisi spesifikasi skema database untuk aplikasi SQL Optimizer.

## 1. Tabel User

Menyimpan data pengguna aplikasi.

| Nama Kolom | Tipe Data (Postgres) | Constraints / Default | Deskripsi |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, DEFAULT `gen_random_uuid()` | ID unik pengguna (aman dari tebakan). |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Email untuk login. Di-index untuk pencarian cepat. |
| `full_name` | VARCHAR(100) | NULL | Nama lengkap pengguna. |
| `password_hash` | VARCHAR | NOT NULL | Hash password (misal: bcrypt/argon2). |
| `tier` | `user_tier` | DEFAULT 'FREE' | Level langganan user. |
| `credits_balance` | INTEGER | DEFAULT 5 | Sisa kuota upload. Berkurang 1 tiap upload. |
| `created_at` | TIMESTAMPTZ | DEFAULT `NOW()` | Waktu pendaftaran (Timezone aware). |

## 2. Tabel Project

Mengelompokkan analisis SQL berdasarkan proyek.

| Nama Kolom | Tipe Data | Constraints | Deskripsi |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, DEFAULT `gen_random_uuid()` | ID unik proyek. |
| `user_id` | UUID | FK -> `users.id` (ON DELETE CASCADE) | Pemilik proyek. Jika user dihapus, proyek ikut terhapus. |
| `name` | VARCHAR(150) | NOT NULL | Nama proyek (misal: "Toko Online Revamp"). |
| `description` | TEXT | NULL | Catatan tambahan user. |
| `created_at` | TIMESTAMPTZ | DEFAULT `NOW()` | Waktu pembuatan. |

## 3. Tabel analysis_job

Menyimpan status dan metadata dari setiap proses analisis SQL.

| Nama Kolom | Tipe Data | Constraints | Deskripsi |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, DEFAULT `gen_random_uuid()` | Job ID yang dikembalikan ke Frontend. |
| `project_id` | UUID | FK -> `projects.id` (ON DELETE CASCADE) | Referensi ke proyek. |
| `original_filename` | VARCHAR(255) | NOT NULL | Nama file asli (misal: `backup_v1.sql`). |
| `status` | `job_status` | DEFAULT 'QUEUED' | Status progress untuk polling frontend. |
| `app_context` | `app_context` | NOT NULL | Pilihan user: Prioritas Baca atau Tulis. |
| `db_dialect` | VARCHAR(50) | NULL | Hasil deteksi otomatis (MySQL/Postgres). |
| `ai_model_used` | VARCHAR(50) | NULL | Model AI yang dipakai (misal: `gpt-4o`). |
| `tokens_used` | INTEGER | DEFAULT 0 | Total token terpakai (untuk audit biaya). |
| `error_message` | TEXT | NULL | Diisi hanya jika status FAILED. |
| `created_at` | TIMESTAMPTZ | DEFAULT `NOW()` | Waktu job dimulai. |
| `completed_at` | TIMESTAMPTZ | NULL | Waktu job selesai. |

## 4. Job_artifacts

Menyimpan file terkait job (file asli, hasil sanitasi, hasil optimasi).

| Nama Kolom | Tipe Data | Constraints | Deskripsi |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, DEFAULT `gen_random_uuid()` | ID unik artifact. |
| `job_id` | UUID | FK -> `analysis_jobs.id` | Referensi ke Job. |
| `artifact_type` | `artifact_type` | NOT NULL | Jenis file (Raw, Sanitized, Optimized). |
| `storage_path` | VARCHAR(512) | NOT NULL | Path S3 (misal: `/jobs/{id}/raw.sql`). |
| `file_size_bytes` | BIGINT | NOT NULL | Ukuran file dalam bytes. |
| `created_at` | TIMESTAMPTZ | DEFAULT `NOW()` | Waktu file disimpan. |

## 5. Ai_suggestion

Menyimpan saran optimasi yang dihasilkan oleh AI.

| Nama Kolom | Tipe Data | Constraints | Deskripsi |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, DEFAULT `gen_random_uuid()` | ID unik saran. |
| `job_id` | UUID | FK -> `analysis_jobs.id` | Referensi ke Job. |
| `table_name` | VARCHAR(100) | NOT NULL | Tabel target optimasi. |
| `issue` | VARCHAR(255) | NOT NULL | Judul masalah (misal: "Circular Dependency"). |
| `suggestion` | TEXT | NOT NULL | Penjelasan solusi (Bahasa manusia). |
| `risk_level` | `risk_level` | NOT NULL | Tingkat risiko perubahan. |
| `confidence` | FLOAT | Check (0.0 <= val <= 1.0) | Skor keyakinan AI. |
| `action_status` | `action_status` | DEFAULT 'PENDING' | Keputusan user (Terima/Tolak). |
| `sql_patch` | TEXT | NOT NULL | Query SQL spesifik untuk saran ini. |

## 6. Sandbox_logs

Menyimpan log hasil validasi atau dry-run dari query.

| Nama Kolom | Tipe Data | Constraints | Deskripsi |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, DEFAULT `gen_random_uuid()` | ID unik log. |
| `job_id` | UUID | FK -> `analysis_jobs.id` | Referensi ke Job. |
| `attempt_number` | INTEGER | DEFAULT 1 | Percobaan ke-berapa? (Retry mechanism). |
| `is_success` | BOOLEAN | NOT NULL | Apakah Dry-Run berhasil? |
| `container_log` | TEXT | NULL | Output raw dari Docker (termasuk error code). |
| `execution_time_ms` | INTEGER | NULL | Berapa milidetik proses validasi berjalan? |
| `created_at` | TIMESTAMPTZ | DEFAULT `NOW()` | Waktu eksekusi. |
