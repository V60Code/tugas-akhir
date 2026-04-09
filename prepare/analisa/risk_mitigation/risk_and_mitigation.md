# Risk Assessment & Mitigation Strategy: SQL Optimizer Project

Dokumen ini merinci kemungkinan risiko yang dapat terjadi dari sisi User, Database, dan Sistem, serta strategi mitigasi teknis dan desain pengalaman pengguna (UX) untuk menanganinya.

## I. Kemungkinan dari Sisi User (User Behavior)

Bagian ini menangani perilaku pengguna yang tidak terduga atau input yang tidak sesuai standar.

### 1. User Mengupload "Dirty SQL" (File Besar dengan Data)
**Risiko:** User mengupload file `.sql` yang bukan hanya berisi struktur tabel, tapi juga berisi jutaan baris data (`INSERT INTO`). File menjadi sangat besar (misal 500MB) padahal sistem hanya membutuhkan strukturnya, yang bisa menyebabkan server crash jika dimuat ke RAM.

**Mitigasi:**
* **Solusi Teknis (Streaming & Filtering):** Jangan baca seluruh file sekaligus; gunakan teknik *Stream Reading* (baca baris per baris). Terapkan *Regex Filter* saat membaca baris; jika diawali dengan `INSERT INTO`, `COPY`, atau `VALUES`, langsung buang (skip). Hanya ambil baris yang mengandung keyword DDL seperti `CREATE`, `ALTER`, `CONSTRAINT`, `KEY`.
* **Solusi UX:** Berikan loading bar dengan status: "Cleaning data rows... Only analyzing structure" untuk memberitahu user bahwa data mereka tidak diproses.

### 2. User Mengupload Data Sensitif
**Risiko:** File SQL yang diupload berisi data asli perusahaan, password user (hash), atau data pribadi (PII) karena mereka melakukan *full dump* dari database produksi. Terdapat risiko kebocoran privasi jika dikirim ke API Pihak Ketiga (LLM).

**Mitigasi:**
* **Solusi Teknis (Sanitization):** Buang semua `INSERT` statement secara otomatis di backend sebelum data diolah untuk menghilangkan 99% risiko kebocoran data. Pastikan prompt ke AI hanya menerima skema tabel (nama kolom & tipe data), bukan isi datanya.
* **Solusi UX (Trust):** Tampilkan *Privacy Disclaimer* di bawah tombol upload yang menyatakan "We process your SCHEMA only. All data rows (INSERTs) are discarded immediately for your privacy".

### 3. Conflicting Goals (Tujuan yang Bertentangan)
**Risiko:** User menginginkan *Write* super cepat, tapi *Read* juga harus instan, dan *Storage* harus hemat. User menginginkan kesempurnaan yang mustahil.

**Mitigasi:**
* **Solusi UX (Visual Trade-off):** Jangan gunakan Checkbox; gunakan *Slider* atau *Radio Button* yang saling mengunci. Terapkan konsep "Segitiga Kualitas": jika user menggeser slider ke arah "Extreme Read Speed", otomatis slider "Write Speed" turun.
* **Edukasi:** Berikan peringatan ramah bahwa untuk mendapatkan Read Speed maksimal, sistem harus menduplikasi data (Denormalisasi), yang akan sedikit memperlambat proses Write.

### 4. User Mengupload File Parsial
**Risiko:** User hanya mengupload satu tabel saja (misal `tabel_transaksi`) tanpa mengupload tabel relasinya (misal `tabel_users`), padahal ada `FOREIGN KEY` yang merujuk ke sana.

**Mitigasi:**
* **Solusi Teknis (Validation & Stubbing):** Lakukan *Pre-Check Parser* untuk mencatat semua tabel yang "disebut" tapi "tidak didefinisikan". Gunakan *Auto-Stubbing* (membuat tabel bayangan/dummy di memori) agar AI tidak error.
* **Solusi UX:** Tampilkan peringatan Kuning (Warning) yang menyatakan bahwa tabel referensi tidak ditemukan, sehingga analisis mungkin kurang akurat.

### 5. User Tidak Mengerti Bahasa Teknis
**Risiko:** User bingung dengan istilah teknis seperti "Denormalisasi", "Index", atau "High Join Cost" dan takut menekan tombol "Accept".

**Mitigasi:**
* **Solusi UX (Plain Language):** Terjemahkan istilah teknis ke bahasa awam.
    * Ganti "Saran Denormalisasi" menjadi "Percepat Tampilan Data".
    * Ganti "Normalisasi (3NF)" menjadi "Hemat Penyimpanan & Rapikan Data".
    * Ganti "High Join Cost" menjadi "Terlalu banyak tabel yang harus digabung".
* **Tooltip:** Sediakan ikon (?) kecil yang menampilkan penjelasan teknis mendalam saat di-hover.

### 6. Format File Salah
**Risiko:** User mengupload file `.txt`, `.docx`, atau kode PHP/Python yang berisi query SQL, bukan file `.sql` murni.

**Mitigasi:**
* **Solusi Teknis:** Batasi input pada elemen HTML dengan `accept=".sql"` dan cek MIME type di backend. Lakukan *Content Sniffing*: jika user upload `.txt` tapi isinya valid SQL, terima saja.
* **Solusi UX:** Berikan pesan error yang jelas. Jika user upload kode PHP, deteksi keyword `<?php` dan tolak dengan pesan saran untuk melakukan export database terlebih dahulu.

---

## II. Kemungkinan dari Sisi File Database (SQL Content & Syntax)

Bagian ini menangani variasi struktur dan sintaksis SQL yang beragam.

### 1. Variasi Dialek SQL (The Dialect Hell)
**Risiko:** Syntax MySQL (`INT AUTO_INCREMENT`) berbeda dengan PostgreSQL (`SERIAL`, `JSONB`), SQL Server (`T-SQL`), atau Oracle.

**Mitigasi:**
* **Solusi Teknis:** Gunakan *Universal Parser* yang mendukung multi-dialect (seperti `sqlglot`). Lakukan normalisasi/*transpilation* semua dialek menjadi satu Format Internal Standar (Generic Abstract Syntax Tree). Deteksi dialek secara otomatis (misal `JSONB` = Postgres).
* **Solusi UX:** Sediakan *Dropdown Selector* manual jika deteksi otomatis gagal dan opsi *Export* untuk memilih format output (MySQL atau PostgreSQL).

### 2. Penamaan Kolom Buruk (Cryptic Naming)
**Risiko:** Nama tabel/kolom tidak memiliki arti semantik (contoh: `t1`, `c1`, `x`), sehingga AI sulit menebak konteks bisnisnya.

**Mitigasi:**
* **Solusi Teknis:** Gunakan *Type Inference* (menebak berdasarkan tipe data, misal `TIMESTAMP` = waktu pembuatan). Pindai *SQL Comment* untuk mencari penjelasan kolom.
* **Solusi UX:** Tampilkan permintaan klarifikasi (*Clarification Request*) untuk tabel yang ambigu atau fitur *Alias Mapping* agar user bisa memberi nama samaran sementara.

### 3. Struktur Spaghetti & Circular Dependency
**Risiko:** Terdapat ketergantungan memutar antar tabel (A butuh B, B butuh C, C butuh A).

**Mitigasi:**
* **Solusi Teknis:** Gunakan algoritma graf (*Cycle Detection*) untuk mendeteksi siklus dan hentikan saran denormalisasi pada tabel tersebut karena berisiko *infinite loop*.
* **Solusi UX:** Visualisasikan diagram relasi dan sorot garis penyebab *loop* dengan warna merah, serta sarankan *refactoring* struktur.

### 4. Fitur SQL Lanjutan (Stored Procedures/Triggers)
**Risiko:** File mengandung `TRIGGER` atau `STORED PROCEDURE` kompleks di mana logika bisnis tersembunyi.

**Mitigasi:**
* **Solusi Teknis:** Batasi lingkup parser hanya pada DDL (`CREATE`, `ALTER`, `INDEX`) dan anggap blok prosedur sebagai komentar (*Partial Parsing*).
* **Solusi UX:** Berikan *disclaimer* bahwa alat fokus pada struktur tabel dan user harus mengecek manual dampak perubahan terhadap logika prosedur.

### 5. Tidak Ada Definisi Relasi (Missing Keys)
**Risiko:** User tidak mendefinisikan `PRIMARY KEY` atau `FOREIGN KEY` secara eksplisit, hanya kolom integer biasa, sehingga sistem buta relasi.

**Mitigasi:**
* **Solusi Teknis:** Gunakan inferensi heuristik (*Name Matching*) atau AI untuk menebak relasi berdasarkan kesamaan nama kolom (misal `orders.user_id` ke `users.id`).
* **Solusi UX:** Konfirmasi tebakan sistem kepada user (*Inferred Relationships Review*) dan sarankan penambahan *Constraint* eksplisit.

### 6. Database Sudah Sempurna
**Risiko:** Tidak ada yang perlu diperbaiki, user mungkin merasa alat tidak berguna.

**Mitigasi:**
* **Solusi Teknis:** Hitung skor kesehatan (*Health Score*) berdasarkan kriteria 3NF dan Indexing.
* **Solusi UX:** Berikan apresiasi (*Green Badge*) dan saran skalabilitas masa depan (misal: saran *Sharding* atau *Partitioning* jika data mencapai jutaan baris).

---

## III. Kemungkinan dari Sisi Sistem & AI (System Failure)

Bagian ini menangani kegagalan logika sistem, AI, dan keamanan.

### 1. AI Hallucination (Saran Sesat)
**Risiko:** AI menyarankan penggabungan tabel yang tidak logis atau berbahaya secara bisnis (misal: menggabungkan data gaji dengan profil publik).

**Mitigasi:**
* **Solusi Teknis:** Gunakan *Chain-of-Thought Prompting* (minta alasan "Kenapa"). Terapkan deteksi data sensitif non-AI (Regex) untuk memblokir saran yang menyentuh kolom sensitif seperti `salary` atau `password`.
* **Solusi UX:** Terapkan *Human-in-the-Loop* (jangan auto-apply). Berikan label risiko (*Low/High Risk*) dan skor keyakinan (*Confidence Score*).

### 2. Parser Failure / Crash
**Risiko:** Sistem berhenti total karena satu karakter aneh atau sintaks non-standar di baris tertentu.

**Mitigasi:**
* **Solusi Teknis:** Gunakan *Try-Catch* per statement (jangan parse satu file sekaligus). Lakukan *Linter Pre-check* untuk membuang karakter non-ASCII.
* **Solusi UX:** Berikan laporan sukses parsial (misal: berhasil 14 dari 15 tabel) agar user tidak merasa gagal total.

### 3. Broken Output Generation
**Risiko:** SQL hasil saran AI invalid dan error saat dijalankan di database target.

**Mitigasi:**
* **Solusi Teknis (Virtual Dry-Run):** Lakukan tes pada database sementara (*Ephemeral DB* seperti SQLite/Docker) di backend sebelum file diberikan ke user. Jika error, minta AI memperbaiki diri (*Self-Correction*).
* **Solusi UX:** Berikan label *Verified Badge* pada file download yang lolos validasi sintaks.

### 4. Time-Out & Resource Exhaustion
**Risiko:** Proses analisis terlalu lama atau server kehabisan memori karena banyak request besar bersamaan.

**Mitigasi:**
* **Solusi Teknis (Job Queue):** Gunakan arsitektur asinkronus (*Worker System*) agar tidak memproses di thread utama.
* **Solusi UX:** Gunakan *Real-time Progress Bar* via WebSocket dan tawarkan notifikasi email untuk proses yang lama.

### 5. Security Injection
**Risiko:** File SQL mengandung perintah berbahaya untuk menyerang server.

**Mitigasi:**
* **Solusi Teknis:** Perlakukan file SQL sebagai teks biasa (String), bukan kode eksekusi. Lakukan *Dry-Run* di dalam *Container* terisolasi (Sandboxing) tanpa akses internet atau file system utama.

---

## IV. Rangkuman Arsitektur Pertahanan

Sistem dirancang dengan lapisan pertahanan berikut untuk menangani risiko di atas:

1.  **Frontend:** Upload File -> Terima Job ID.
2.  **API Gateway:** Validasi File -> Masukkan ke Antrian (Redis).
3.  **Worker Service (Backend Utama):**
    * *Sanitizer:* Buang karakter aneh & data sensitif.
    * *Parser:* Baca struktur dengan penanganan error per tabel.
    * *AI Engine:* Minta saran & koreksi diri.
    * *Validator:* Tes jalan SQL di Sandbox DB.
4.  **Storage:** Simpan hasil SQL baru.
5.  **Frontend:** Notifikasi "Selesai" -> Download.