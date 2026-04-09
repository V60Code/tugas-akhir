# Analisis SDLC yang Paling Cocok untuk Proyek SQL Optimizer

## Ringkasan Jawaban
Untuk karakteristik proyek ini, pendekatan yang **paling cocok** adalah **Agile (Scrum/Kanban) berbasis iterasi-incremental**, diperkuat praktik **DevOps/MLOps ringan** dan **stage-gate** untuk kontrol kualitas.

Secara akademis, ini termasuk **hybrid SDLC**:
- Kerangka utama: Agile Iterative-Incremental.
- Mekanisme delivery: DevOps (CI/CD, test otomatis, observability).
- Kendali risiko: stage-gate pada milestone penting (security, reliability, rilis).

Model ini lebih tepat dibanding Waterfall murni karena domain proyek memiliki ketidakpastian teknis tinggi (AI suggestion quality, sandbox execution, performa async worker, dan reliability integrasi multi-service).

---

## Konteks Teknis Proyek
Dari implementasi yang ada, sistem memiliki karakteristik:
- Arsitektur terdistribusi: frontend, API backend, worker async, queue broker, storage objek, database relasional.
- Alur sinkron + asinkron: request API langsung dan pemrosesan background (analisis/finalisasi job).
- Integrasi eksternal: LLM service, sandbox validation, object storage.
- Evolusi skema data berkelanjutan: migrasi database dan tuning index.
- Kualitas sistem ditentukan oleh eksperimen: akurasi suggestion AI, keberhasilan self-correction, keberhasilan validasi sandbox.

Karakteristik ini menunjukkan **requirement dan solusi berkembang selama implementasi**, bukan domain yang sepenuhnya stabil sejak awal.

---

## Evaluasi Akademis Model SDLC

### 1. Waterfall
**Kekuatan:**
- Dokumentasi dan tahapan formal jelas.
- Cocok bila requirement sangat stabil dan perubahan minimal.

**Kelemahan pada proyek ini:**
- Umpan balik nyata baru terlihat saat integrasi AI/sandbox dijalankan.
- Perubahan desain sering diperlukan setelah pengujian end-to-end.
- Risiko biaya rework tinggi jika keputusan desain dibuat terlalu awal.

**Kesimpulan:** kurang cocok sebagai model utama.

### 2. Agile (Scrum/Kanban)
**Kekuatan:**
- Iteratif: fitur dikembangkan dalam sprint kecil, mudah adaptasi.
- Cepat mendapatkan feedback user dan feedback teknis (job status, kualitas suggestion, latency).
- Cocok untuk produk dengan ketidakpastian dan integrasi kompleks.

**Risiko:**
- Bila tanpa disiplin engineering, bisa terjadi scope creep dan technical debt.

**Mitigasi:**
- Definisi "Done" yang ketat: unit test, integration test, security check, observability.
- Backlog teknis eksplisit (reliability, retry policy, index optimization).

**Kesimpulan:** sangat cocok sebagai fondasi SDLC.

### 3. Spiral
**Kekuatan:**
- Sangat kuat pada manajemen risiko.
- Cocok untuk sistem kritikal dan berisiko tinggi.

**Kelemahan:**
- Lebih berat secara manajerial untuk tim kecil-menengah.
- Overhead dokumentasi dan risk cycle bisa memperlambat delivery.

**Kesimpulan:** bisa diadopsi parsial (pola pikir risk-driven), tetapi tidak perlu penuh.

### 4. V-Model
**Kekuatan:**
- Keterkaitan kuat antara spesifikasi dan pengujian.

**Kelemahan pada proyek ini:**
- Kurang fleksibel terhadap perubahan requirement yang sering muncul dari eksperimen AI.

**Kesimpulan:** baik sebagai referensi quality assurance, tetapi bukan model utama.

---

## Rekomendasi Final: Agile Hybrid (Paling Realistis)

### Bentuk yang direkomendasikan
Gunakan **Agile Iterative-Incremental** sebagai inti, dengan kombinasi:
- **Scrum** untuk cadence pengembangan (sprint 2 minggu).
- **Kanban** untuk operasi/bugfix/incident pasca deploy.
- **DevOps** untuk otomatisasi build-test-deploy dan monitoring.
- **Stage-gate** pada milestone penting agar kualitas tetap akademis dan terkontrol.

### Alasan teknis kuat
- Integrasi LLM perlu eksperimen bertahap (prompt, parser, correction loop).
- Worker async + queue membutuhkan tuning reliability bertahap (retry, idempotency, timeout).
- Validasi sandbox memunculkan edge case yang sulit diprediksi dari awal.
- Skema database dan index biasanya berkembang setelah pola query nyata terlihat.

### Alasan akademis
Secara teori rekayasa perangkat lunak modern, proyek dengan:
- requirement dinamis,
- ketidakpastian implementasi tinggi,
- feedback loop cepat,
lebih tepat memakai **iterative risk-reducing process** daripada linear sequential process.

---

## Desain Proses SDLC yang Disarankan

## 1) Inception (1 kali, singkat)
Output:
- Visi produk, batasan scope versi awal.
- High-level architecture dan non-functional requirements.
- Risk register awal (security, reliability, biaya API LLM, data privacy).

## 2) Iteration Cycle (berulang per sprint)
Setiap sprint:
1. Planning: pilih use case prioritas dan acceptance criteria.
2. Design ringan: API contract, schema change, error handling strategy.
3. Implementasi: coding feature + migration + test.
4. Verification: unit, integration, e2e terbatas, security scan.
5. Review: demo hasil, ukur metrik kualitas.
6. Retrospective: perbaikan proses sprint berikutnya.

## 3) Stage-Gate (setiap milestone besar)
Gate contoh sebelum release:
- Security gate: auth, authorization, secret handling, rate limiting.
- Reliability gate: queue failure recovery, retry behavior, idempotency.
- Performance gate: latency endpoint, worker throughput, DB query plan.
- Quality gate: test coverage minimum dan nol bug kritis.

## 4) Operations & Continuous Improvement
- Monitoring dashboard: status job, fail rate sandbox, retry rate, response time.
- Incident review: root cause analysis dan action item backlog.
- Continuous optimization: index DB, prompt tuning, parser robustness.

---

## Artefak Akademis yang Perlu Dijaga
Agar tetap kuat untuk kebutuhan akademik/skripsi dan praktik industri:
- Product backlog dan sprint backlog terdokumentasi.
- Definition of Done tertulis.
- Traceability ringan: requirement -> use case -> test case.
- Architecture Decision Record untuk keputusan besar.
- Metrik kualitas per sprint (defect rate, lead time, success rate finalization).

---

## Kapan Waterfall Masih Layak Dipakai Parsial?
Waterfall tetap berguna untuk bagian yang stabil, misalnya:
- Penulisan dokumen formal awal.
- Penyusunan bab metodologi yang linear.
- Baseline desain arsitektur sebelum iterasi dimulai.

Jadi praktik terbaik bukan menolak Waterfall total, tetapi **menggunakannya sebagai komponen dokumentasi awal**, lalu eksekusi teknis utama tetap Agile Hybrid.

---

## Kesimpulan Akhir
Jika tujuan Anda adalah menghasilkan sistem yang benar-benar berjalan, stabil, dan bisa beradaptasi dengan ketidakpastian AI + distributed architecture, maka pilihan paling tepat adalah:

**Agile Hybrid (Scrum/Kanban + DevOps + Stage-Gate Quality Control).**

Ini memberikan keseimbangan terbaik antara:
- fleksibilitas perubahan,
- kecepatan delivery,
- kontrol risiko teknis,
- dan kekuatan justifikasi akademis.
