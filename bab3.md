# Bab 3 - Implementasi Prompt Engineering dan LangChain

Dokumen ini merangkum implementasi Prompt Engineering dan LangChain pada proyek optimasi skema database berbasis AI. Fokus pembahasan diarahkan pada lima aspek utama, yaitu definisi persona, konteks input prompt, format luaran terstruktur, mekanisme self-correction, dan konfigurasi parameter model.

## Gambaran Umum Arsitektur

Secara implementasi, proyek ini menggunakan LangChain dalam bentuk yang ringan, yaitu:

- `PromptTemplate` untuk menyusun prompt
- `ChatGoogleGenerativeAI` untuk memanggil model Gemini
- `PydanticOutputParser` untuk memaksa keluaran berbentuk JSON terstruktur

Proyek ini tidak menggunakan `ChatPromptTemplate`, memory, retrieval, agent, maupun RAG. Dengan demikian, alur utamanya adalah:

1. File SQL diunggah oleh pengguna.
2. File disanitasi agar data mentah tidak ikut diproses.
3. SQL di-parse menjadi representasi skema.
4. Representasi skema dikirim ke Gemini melalui prompt utama.
5. Keluaran Gemini diparse menggunakan schema Pydantic.
6. Jika patch SQL dipilih pengguna lalu gagal saat divalidasi di Docker Sandbox, sistem mengirim prompt self-correction ke Gemini.

## 1. Definisi Persona (System Message)

Pada kode sumber saat ini, tidak terdapat `SystemMessage` terpisah dalam format role-based LangChain. Prompt dibangun sebagai satu buah `PromptTemplate` lalu dikirim langsung ke model melalui `self.llm.invoke(prompt_str)`.

Artinya, persona model ditanamkan langsung di dalam template prompt utama. Teks persona dasarnya adalah sebagai berikut:

```text
You are a senior MySQL Database Architect and performance tuning expert.
Your task is to deeply analyze the database schema below and find REAL, ACTIONABLE optimization opportunities.
```

Setelah itu, prompt dilanjutkan dengan instruksi analisis yang lebih rinci:

```text
=== TARGET DIALECT ===
{db_dialect}

=== WORKLOAD CONTEXT ===
{app_context}
- READ_HEAVY: Prioritize indexes for SELECT performance (composite indexes, covering indexes, filtered access patterns)
- WRITE_HEAVY: Identify indexes that hurt INSERT/UPDATE performance, suggest index consolidation

=== DATABASE SCHEMA ===
{schema_json}

=== YOUR ANALYSIS MANDATE ===
You MUST find between 3 and 8 real issues. Even well-designed schemas have optimization opportunities.

Look for ALL of the following (not just obvious ones):
1. **Missing composite indexes** - columns frequently used together in WHERE/JOIN but only indexed individually
2. **Low-cardinality predicate optimization** - use index design that helps common filters (status, is_active, deleted_at)
3. **UUID primary key tradeoff** - if schema uses UUID PKs, note random write amplification and suggest MySQL-friendly alternatives if needed
4. **Covering indexes in MySQL** - indexes that reduce extra lookups for common query patterns
5. **JSON column optimization** - suggest generated columns + indexes when JSON fields are filtered frequently
6. **Soft-delete performance** - tables with deleted_at that lack indexes aligned with active-row query patterns
7. **Over-indexing** - tables with too many single-column indexes that slow down writes
8. **Missing CHECK constraints or NOT NULL** - columns that should be constrained but aren't
9. **Normalization opportunities** - repeated patterns that could be extracted to reference tables
10. **Large TEXT columns** - TEXT/LONGTEXT on frequently-filtered columns that should be VARCHAR(N) or separate lookup design

CRITICAL RULES:
- You MUST generate at least 3 suggestions. If the schema looks clean, find micro-optimizations.
- Every suggestion MUST include a concrete, runnable SQL patch (not a comment, actual SQL).
- Do NOT return empty sql_patch strings.
- Do NOT make up tables or columns that don't exist in the schema.
- Use MySQL 8-compatible SQL syntax.
- Do NOT use PostgreSQL-only features (GIN, BRIN, INCLUDE, partial index WHERE clause, PostgreSQL-specific operators).

{format_instructions}
```

Dengan demikian, persona AI pada sistem ini dapat dijelaskan sebagai:

- berperan sebagai arsitek database MySQL senior
- fokus pada performance tuning
- diarahkan untuk memberikan saran yang nyata, dapat dieksekusi, dan tidak spekulatif

## 2. Konteks dan Skema Input (Human Message)

Variabel yang benar-benar diinjeksikan ke prompt utama ada empat, yaitu:

- `app_context`
- `schema_json`
- `db_dialect`
- `format_instructions`

Walaupun sering disebut sebagai "human message", implementasi saat ini tidak memakai pemisahan role `system` dan `human` secara eksplisit. Semua konteks tersebut dirakit menjadi satu string prompt.

### Alur Penyusunan Input

Alur pembentukan input ke AI adalah sebagai berikut:

1. Endpoint `POST /upload` menerima:
   - file SQL
   - `project_id`
   - `app_context`
   - `db_dialect`
2. File SQL dibaca dan divalidasi ukurannya.
3. File disanitasi menggunakan `sanitize_sql_stream()`.
4. Sanitasi menghapus baris yang diawali `INSERT`, `COPY`, atau `VALUES`.
5. File hasil sanitasi disimpan ke MinIO.
6. Worker mengambil file tersebut dan memanggil `parse_sql_to_schema()`.
7. Hasil parsing dikirim ke `_prepare_schema_for_llm()` untuk diubah menjadi teks skema yang lebih ringkas.
8. Teks inilah yang akhirnya diinjeksi ke prompt sebagai `schema_json`.

### Penjelasan Tiap Variabel

#### a. `app_context`

Variabel ini berasal dari enum:

```python
class AppContext(str, enum.Enum):
    READ_HEAVY = "READ_HEAVY"
    WRITE_HEAVY = "WRITE_HEAVY"
```

Fungsinya adalah memberi tahu AI karakteristik beban kerja aplikasi:

- `READ_HEAVY`: AI diminta memprioritaskan indeks untuk performa query `SELECT`
- `WRITE_HEAVY`: AI diminta memperhatikan indeks yang berpotensi memperlambat `INSERT` dan `UPDATE`

#### b. `db_dialect`

Variabel ini diterima dari form upload dan diteruskan ke parser SQL serta prompt. Nilai default yang digunakan saat kosong adalah `"mysql"`.

Namun perlu dicatat bahwa isi prompt masih sangat MySQL-oriented. Persona dan aturan utamanya tetap diarahkan ke MySQL 8 walaupun field `db_dialect` dibuat fleksibel.

#### c. `schema_json`

Nama variabelnya memang `schema_json`, tetapi isi aktualnya bukan JSON mentah. Variabel ini berisi representasi teks hasil serialisasi skema oleh `_prepare_schema_for_llm()`.

Contoh bentuknya:

```text
-- Schema Summary: 12 tables, 84 columns total
-- Analyzing sample of up to 25 tables

TABLE: users
  id UUID
  email VARCHAR(255)
  created_at TIMESTAMP

TABLE: orders
  id UUID
  user_id UUID
  status VARCHAR(50)
```

Fungsi serialisasi ini adalah:

- meringkas skema agar tidak terlalu panjang
- membatasi jumlah tabel maksimal 25
- menambahkan ringkasan jumlah tabel dan kolom
- jika metadata tersedia, menandai kolom dengan flag seperti `PK`, `FK`, `NOT NULL`, dan `UNIQUE`

Walaupun `_prepare_schema_for_llm()` mendukung flag tersebut, pada pipeline analisis utama saat ini data skema berasal dari `parse_sql_to_schema()`, yang umumnya hanya menghasilkan:

- nama tabel
- nama kolom
- tipe kolom

Jadi, dalam praktiknya prompt analisis utama biasanya belum menerima metadata relasi dan constraint secara lengkap.

#### d. `format_instructions`

Variabel ini dihasilkan otomatis dari:

```python
self.parser.get_format_instructions()
```

Tujuannya adalah memberi instruksi kepada model agar mengembalikan JSON yang sesuai dengan schema Pydantic yang telah ditentukan.

## 3. Format Luaran (Pydantic Output Parser)

Untuk memastikan keluaran Gemini berbentuk JSON terstruktur, sistem menggunakan `PydanticOutputParser`.

Schema Pydantic utama yang digunakan adalah:

```python
class AISuggestionSchema(BaseModel):
    table_name: str = Field(description="Name of the table this suggestion applies to. Use 'GLOBAL' for schema-wide issues.")
    issue: str = Field(description="Short, specific title of the issue (max 80 chars)")
    suggestion: str = Field(description="Detailed explanation of WHY it is a problem and how to solve it")
    risk_level: RiskLevel = Field(description="Risk of applying the change: LOW, MEDIUM, or HIGH")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0 that this is a real issue")
    sql_patch: str = Field(description="Concrete, runnable SQL DDL/DML to fix or improve the issue. Never leave this empty.")


class AIAnalysisResult(BaseModel):
    suggestions: List[AISuggestionSchema]
```

### Field Wajib yang Harus Dikembalikan AI

Setiap item pada array `suggestions` wajib memiliki field:

- `table_name`
- `issue`
- `suggestion`
- `risk_level`
- `confidence`
- `sql_patch`

Sehingga struktur JSON targetnya adalah:

```json
{
  "suggestions": [
    {
      "table_name": "orders",
      "issue": "Missing composite index",
      "suggestion": "Query orders by user_id and status may scan too many rows without a composite index.",
      "risk_level": "MEDIUM",
      "confidence": 0.92,
      "sql_patch": "CREATE INDEX idx_orders_user_status ON orders(user_id, status);"
    }
  ]
}
```

### Makna Tiap Field

- `table_name`: nama tabel yang menjadi target rekomendasi
- `issue`: judul singkat masalah
- `suggestion`: penjelasan detail mengapa masalah itu penting dan bagaimana memperbaikinya
- `risk_level`: tingkat risiko implementasi, yaitu `LOW`, `MEDIUM`, atau `HIGH`
- `confidence`: tingkat keyakinan AI antara 0.0 sampai 1.0
- `sql_patch`: SQL konkret yang dapat langsung dijalankan

Dengan pendekatan ini, sistem tidak hanya menerima teks bebas dari AI, tetapi keluaran yang terstruktur dan mudah diproses lebih lanjut oleh aplikasi backend.

## 4. Prompt Mekanisme Self-Correction

Salah satu fitur penting dalam arsitektur proyek ini adalah mekanisme `AI Self-Correction`. Fitur ini aktif ketika patch SQL hasil rekomendasi AI gagal lolos validasi di Docker Sandbox.

### Alur Self-Correction

Alurnya adalah sebagai berikut:

1. Sistem menyusun `optimized_sql`, yaitu SQL asli ditambah bagian patch dari AI.
2. SQL tersebut dijalankan di container sandbox menggunakan Docker.
3. Jika validasi berhasil, proses finalisasi selesai.
4. Jika validasi gagal, sistem mengambil log error dari sandbox.
5. Sistem lalu mengirim patch yang gagal beserta log error ke Gemini.
6. Gemini diminta memperbaiki patch tersebut, bukan menulis ulang seluruh SQL dari nol.
7. Patch hasil koreksi diuji kembali di sandbox.
8. Mekanisme ini diulang hingga batas retry tercapai.

### Prompt Self-Correction yang Dikirim ke Gemini

Prompt spesifik yang digunakan adalah:

```text
You are a MySQL 8 SQL expert performing a SQL self-correction task.

A SQL patch generated for optimization failed database validation.
Your job is to output a corrected version of the SQL that will pass validation.

=== TABLE CONTEXT ===
Table: {table_name}

=== ORIGINAL SQL PATCH (FAILED) ===
{original_sql}

=== SANDBOX ERROR LOG ===
{error_log}

=== TARGET DIALECT ===
{db_dialect}

=== INSTRUCTIONS ===
- Analyze the error log carefully.
- Fix ONLY what is causing the failure - do not rewrite the entire patch.
- Return valid, runnable MySQL 8 DDL/DML.
- If the patch cannot be fixed (e.g., references a table that doesn't exist), return an empty corrected_sql.
- Do NOT wrap the SQL in markdown fences.
- Do NOT use PostgreSQL-only syntax/features.

{format_instructions}
```

### Informasi yang Dikirim Saat Self-Correction

Saat self-correction dipanggil, sistem mengirimkan beberapa variabel berikut:

- `table_name`
- `original_sql_patch`
- `error_log`
- `attempt`
- `db_dialect`

Artinya, benar bahwa sistem mengirimkan pesan error dari Docker Sandbox ke AI agar AI dapat merevisi `sql_patch`.

### Sumber Error Log

Error log berasal dari hasil eksekusi sandbox Docker. Metode `run_sql_validation()` menjalankan SQL di container database sementara, menangkap `stdout` dan `stderr`, lalu mengembalikan:

```python
{"success": bool, "logs": str}
```

Nilai `logs` inilah yang digunakan sebagai bahan analisis koreksi.

### Fokus Koreksi

Sistem tidak mengirim seluruh SQL hasil upload untuk ditulis ulang. Yang dikirim terutama adalah bagian patch AI, yaitu blok setelah penanda:

```text
/* --- AI OPTIMIZATIONS --- */
```

Pendekatan ini penting karena:

- memperkecil konteks prompt
- mencegah AI merombak DDL asli pengguna
- membatasi koreksi hanya pada bagian patch yang memang gagal

### Schema Output Self-Correction

Keluaran self-correction juga dipaksa mengikuti schema Pydantic:

```python
class SelfCorrectionResult(BaseModel):
    corrected_sql: str = Field(
        description="The corrected SQL patch that resolves the validation error. Must be valid, runnable SQL."
    )
    explanation: str = Field(
        description="Brief explanation of what was wrong and what was changed."
    )
```

Struktur ini mewajibkan AI mengembalikan:

- `corrected_sql`
- `explanation`

Jika `corrected_sql` kosong, sistem menganggap patch tersebut tidak dapat diperbaiki.

## 5. Konfigurasi Parameter Model

Model Gemini diinisialisasi pada kelas `LLMEngine` sebagai berikut:

```python
self.llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    temperature=0.1,
    convert_system_message_to_human=True,
    google_api_key=settings.GOOGLE_API_KEY,
)
```

### Parameter yang Digunakan

Parameter yang benar-benar diatur dalam kode adalah:

- `model = settings.GEMINI_MODEL`
- `temperature = 0.1`
- `convert_system_message_to_human = True`
- `google_api_key = settings.GOOGLE_API_KEY`

### Nilai Model yang Dipakai Saat Ini

Pada implementasi proyek saat ini, default konfigurasi model adalah:

```env
GEMINI_MODEL=gemini-2.5-flash-lite
```

Jadi, secara faktual kode saat ini tidak memakai `Gemini 1.5 Pro` sebagai default, melainkan `gemini-2.5-flash-lite`.

Hal ini penting untuk penulisan skripsi. Jika pada naskah masih tertulis `Gemini 1.5 Pro`, maka bagian tersebut perlu diperbarui agar sesuai dengan implementasi aktual.

### Parameter yang Tidak Diatur

Beberapa parameter yang tidak ditemukan pengaturannya secara eksplisit di kode adalah:

- `max_tokens`
- `max_output_tokens`
- `top_p`
- `top_k`
- `seed`
- `response_schema` native provider
- `safety_settings`

Dengan demikian, strategi pengendalian output agar lebih deterministik dan minim halusinasi pada sistem ini terutama bertumpu pada:

- temperature rendah (`0.1`)
- prompt yang sangat restriktif
- instruksi untuk tidak mengarang tabel atau kolom
- penggunaan `PydanticOutputParser`
- validasi patch SQL melalui Docker Sandbox

## Mekanisme Retry untuk Kestabilan Panggilan LLM

Selain prompt engineering, sistem juga menerapkan retry otomatis pada pemanggilan LLM menggunakan `tenacity`.

Konfigurasinya adalah:

- maksimum 3 kali percobaan
- exponential backoff
- jeda minimum 2 detik
- jeda maksimum 30 detik
- hanya untuk error yang dianggap transient

Pendekatan ini membantu menjaga stabilitas layanan ketika terjadi rate limit, timeout, atau gangguan sementara dari layanan Gemini.

## Kesimpulan

Berdasarkan implementasi kode, Prompt Engineering pada proyek ini dirancang dengan pendekatan instruksional yang ketat. Model diberi persona sebagai arsitek database MySQL senior, lalu menerima konteks berupa karakteristik workload, dialek database, dan ringkasan skema hasil parsing. Output Gemini dipaksa mengikuti schema JSON terstruktur melalui `PydanticOutputParser`, sehingga dapat langsung diproses oleh backend.

Keunggulan utama arsitektur ini terletak pada mekanisme `AI Self-Correction`, yaitu kemampuan sistem untuk mengirim ulang patch SQL yang gagal beserta log error sandbox agar AI merevisi patch tersebut secara otomatis. Dengan demikian, model tidak hanya menghasilkan rekomendasi, tetapi juga berperan dalam siklus validasi dan perbaikan.

Dari sisi konfigurasi, sistem menggunakan temperature rendah untuk menekan kreativitas berlebih, namun tetap memberi ruang bagi model untuk menemukan optimasi yang tidak terlalu kasat mata. Meskipun demikian, kontrol utama terhadap kualitas keluaran bukan hanya berasal dari hyperparameter, tetapi dari kombinasi prompt yang ketat, parser terstruktur, dan pengujian nyata di Docker Sandbox.

## Catatan Penting untuk Penulisan Skripsi

Ada satu hal yang perlu dijaga konsistensinya dalam penulisan Bab 3:

- Jika naskah Anda masih menyebut model yang digunakan adalah `Gemini 1.5 Pro`, maka itu tidak sesuai dengan implementasi kode saat ini.
- Implementasi aktual menunjukkan penggunaan `settings.GEMINI_MODEL` dengan default `gemini-2.5-flash-lite`.

Karena itu, penulisan metodologi sebaiknya mengikuti implementasi yang benar-benar berjalan pada proyek, kecuali memang ada versi eksperimen sebelumnya yang memakai model berbeda dan ingin dijelaskan sebagai bagian terpisah.
