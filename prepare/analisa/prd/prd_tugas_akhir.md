# SQL Optimizer & Architect: Product Requirements Document (PRD)

| Field | Value |
| :--- | :--- |
| **Author** | Muhammad Alfarizi Habibullah |
| **Status** | DRAFT |
| **Updated** | 2025-11-20 |
| **Strategy Doc** | [Link to Architecture Diagram] |
| **Eng Design Doc** | [Link to Tech Stack Spec] |

---

## 1. Problem
Developer dan Database Administrator (DBA) sering kali mewarisi database "legacy" dengan struktur yang buruk (Spaghetti Database), yang menyebabkan performa aplikasi lambat dan biaya infrastruktur membengkak.

Saat ini, melakukan *refactoring* database adalah proses yang sangat menakutkan dan berisiko tinggi. Developer takut mengubah struktur tabel karena khawatir merusak integritas data atau memutus aplikasi. Tidak ada alat yang aman dan terjangkau untuk memvisualisasikan, menganalisis, dan memvalidasi perubahan arsitektur database secara otomatis tanpa membahayakan data produksi.

## 2. Vision & Opportunity
**Vision:** Menjadi "Intelligent Co-pilot" standar industri untuk arsitektur database.

**Opportunity:** Kami ingin memungkinkan jutaan developer untuk memodernisasi skema database lama mereka agar mencapai performa tinggi (Read/Write Optimized) dan efisiensi penyimpanan, dengan cara yang aman, visual, dan otomatis.

## 3. Target Use Cases
Kami menargetkan pengguna teknis yang menangani sistem backend:

1.  **The Legacy Maintainer (Backend Dev):** "Sebagai backend developer, saya sering harus memperbaiki performa aplikasi tua yang lambat, tetapi saya takut melakukan perubahan struktur tabel karena relasinya terlalu rumit dan tidak terdokumentasi."
2.  **The Scaler (CTO/Tech Lead):** "Sebagai CTO startup yang sedang berkembang, saya perlu mengubah struktur database dari mode 'asal jalan' menjadi 'optimized for read' agar dashboard analytics kami tidak *timeout*, namun saya butuh panduan otomatis untuk menyeimbangkan antara performa dan ukuran data."
3.  **The Freelancer:** "Sebagai freelancer, saya butuh cara cepat untuk mengaudit database klien baru dan memberikan laporan optimasi profesional sebelum mulai coding."

## 4. Landscape
Saat ini, solusi yang ada terbagi menjadi dua ekstrem:
* **Linter SQL Sederhana:** Hanya cek sintaks, tidak paham konteks bisnis.
* **DBA Tools Enterprise:** Sangat mahal dan kompleks.

Belum ada tool berbasis web yang menggabungkan *Static Analysis*, *AI Reasoning*, dan *Sandboxed Execution* yang mudah diakses developer menengah.

## 5. Proposed Solution
Platform SaaS berbasis web di mana user dapat mengupload file SQL skema mereka. Sistem akan membersihkan data sensitif, menganalisis struktur menggunakan AI berdasarkan konteks (Read vs Write heavy), dan memvalidasi perubahan di lingkungan terisolasi.

### Top 3 MVP Value Props
1.  **Safety Shield (The Painkiller):** Otomatis membuang data sensitif (`INSERT` rows) secara lokal dan menjalankan validasi di Docker Container terisolasi. Zero risk to production.
2.  **Interactive Visualizer (The Vitamin):** Mengubah kode SQL yang membosankan menjadi Diagram ERD interaktif yang menyorot masalah (seperti Circular Dependency) secara visual.
3.  **Context-Aware AI (The Steroid):** Memberikan saran normalisasi/denormalisasi bukan berdasarkan aturan baku saja, tapi berdasarkan input tujuan user (Read-Heavy vs Write-Heavy).

## 6. Goals & Non-Goals
### Goals
* Mempercepat waktu refactoring database hingga 50%.
* Mencegah error sintaks SQL mencapai production melalui validasi *Dry-Run*.
* Menyediakan platform yang aman (Privacy-first) untuk analisis database.

### Non-Goals
* Koneksi langsung ke Database Production (Live Connection) pada rilis MVP.
* Optimasi query `SELECT` spesifik (Query optimization). Fokus saat ini adalah Struktur/DDL.
* Dukungan NoSQL (MongoDB/Firebase) pada rilis pertama.

## 7. Y1 Success Metrics

| GOALS | SIGNALS | METRICS | TARGETS |
| :--- | :--- | :--- | :--- |
| **Engagement & Adoption** | User menyelesaikan proses optimasi. | Completion Rate (Upload to Download) | > 40% Completion |
| **User Trust** | User menerima saran AI. | Suggestion Acceptance Rate | > 60% Accepted |
| **Reliability** | File hasil valid dan bisa dijalankan. | Valid SQL Generation Rate | < 5% Error rate |

---

## 8. Conceptual Model
Alur kerja utama yang perlu dipahami pengguna digambarkan dalam diagram alur berikut.

**Legend:**
* **Raw SQL:** File asli user yang mungkin berisi data sensitif.
* **Sanitized Architecture:** Struktur tabel bersih yang diproses sistem.
* **Analysis Job:** Proses async yang melibatkan Parser dan AI.
* **Sandbox:** Ruang isolasi untuk tes validitas.

### User Flow Diagram

**1. Raw Data Phase**
`[User Upload .sql]`
      ↓
      ↓ *(Raw SQL)*
      ↓

**2. Security & Context Phase**
`[Sanitizer]` ---> *(Strips INSERTs / Data Sensitif)*
      ↓
`[Context Input]` ---> *(User memilih: Read vs Write Priority)*
      ↓

**3. Intelligence Phase**
`[AI Architect Analysis]` ---> *(Analisis Struktur & Relasi)*
      ↓
      ↓ *(Suggestions List)*
      ↓

**4. Verification Phase**
`{Interactive Review}` ---> *(User memilih: Accept / Reject)*
      ↓
`[Sandbox Validation]` ---> *(Virtual Dry-Run di Docker)*
      ↓
      ↓ *(Jika Validasi Sukses)*
      ↓
**5. Final Phase**
`[Download Optimized SQL]`

---

## 9. Requirements
Prioritas persyaratan berdasarkan Critical User Journeys (CUJ).

**Legend:** `[P0]` = MVP Must Have, `[P1]` = Important, `[P2]` = Nice to have.

### Use Case 1: Upload & Context Injection (The Setup)
*User ingin mengupload file database mereka dengan aman dan memberikan konteks bisnis agar analisisnya akurat.*

* **[P0]** User dapat mengupload file berekstensi `.sql` (Drag & Drop).
* **[P0]** Sistem wajib melakukan *Client-side Streaming* untuk mendeteksi dan membuang baris `INSERT`, `COPY`, `VALUES` sebelum file dikirim ke server (Privacy Shield).
* **[P0]** User harus memilih profil aplikasi melalui Slider/Toggle: "Optimize for Write Speed (Transactional)" vs "Optimize for Read Speed (Analytics)".
* **[P0]** Sistem memberikan feedback visual *Real-time Progress* (Parsing -> Analyzing -> Done) via WebSocket.
* **[P1]** Sistem mendeteksi dialek SQL secara otomatis (MySQL/Postgres), namun menyediakan **Dropdown Selector Manual** jika deteksi gagal.
* **[P1]** Sistem memberikan peringatan (*Warning*) jika mendeteksi tabel relasi yang hilang (Partial File Upload).

### Use Case 2: Review & Visualization (The Diagnosis)
*User ingin melihat masalah pada struktur database mereka secara visual dan memilih solusi yang masuk akal.*

* **[P0]** User melihat visualisasi ERD (Entity Relationship Diagram) dari skema yang diupload.
* **[P0]** Sistem menyorot (highlight) tabel yang memiliki masalah kritikal seperti *Circular Dependency*, *Missing Keys*, atau *Index Bloat*.
* **[P0]** User melihat daftar "Kartu Saran" dari AI. Setiap saran harus memiliki atribut mitigasi risiko:
    * **Plain Language Title:** Judul yang mudah dipahami orang awam (misal: "Percepat Akses Data" alih-alih "Denormalisasi").
    * **Risk Level:** Label risiko (Low/High).
    * **Confidence Score:** Tingkat keyakinan AI.
* **[P0]** User dapat melakukan tindakan "Accept" atau "Reject" pada setiap saran.
* **[P1]** Sistem mendukung *Partial Success Analysis*: Jika satu tabel gagal diparsing (syntax error), sistem tetap menampilkan tabel lainnya tanpa *crash*.
* **[P2]** User dapat melihat *Diff Code* (Perbandingan SQL Before vs After).

### Use Case 3: Validation & Export (The Solution)
*User ingin mendapatkan file hasil yang dijamin aman, valid, dan siap dipakai (deploy-ready).*

* **[P0]** User harus menekan tombol "Generate Optimized SQL" untuk memfinalisasi perubahan.
* **[P0]** Sistem wajib menjalankan ("Dry-Run") SQL hasil generasi di dalam *Docker Container* sementara di backend.
* **[P0]** Jika validasi gagal, sistem melakukan *Self-Correction* menggunakan AI atau mengembalikan error log spesifik.
* **[P0]** User mengunduh file `.sql` final yang berisi struktur baru dan komentar dokumentasi mengenai *Trade-off* performa.

---

## 10. Appendix

### Tech Stack Specification
* **Frontend:**
    * Framework: Next.js (App Router) + TypeScript.
    * Visualization: React Flow (untuk ERD).
    * State & UI: Zustand + Shadcn/UI + Tailwind CSS.
* **Backend:**
    * API: FastAPI (Python).
    * Async Processing: Celery + Redis (Message Broker).
    * **Internal Database:** PostgreSQL (untuk Metadata User & Job History).
* **Core Engine:**
    * Parser: SQLGlot (Transpilation & AST).
    * AI Logic: LangChain + OpenAI/Gemini API.
* **Security & Infra:**
    * Isolation: Docker (Ephemeral Sandbox).
    * Storage: MinIO/S3 (untuk file raw sementara).

### Security Constraints
* Parser tidak boleh mengeksekusi kode (Static Analysis only).
* Semua eksekusi validasi (Dry-Run) hanya terjadi di *Ephemeral Container* tanpa akses internet.
* Data baris (`INSERT`) dibuang di sisi klien (streaming) atau segera dibuang di memori server sebelum disimpan ke disk.