# ERD Konseptual SQL Optimizer System (PlantUML)

Diagram ini menekankan entity dan hubungan antar-entity (konseptual), bukan detail tipe data tabel.

```plantuml
@startuml
left to right direction
hide circle
skinparam linetype ortho

entity "User" as User {
  *user_id
  --
  email
  full_name
  password
}

entity "Project" as Project {
  *project_id
  --
  name
  description
  created_at
}

entity "Analysis Job" as AnalysisJob {
  *job_id
  --
  original_filename
  status
  app_context
  db_dialect
  ai_model_used
  tokens_used
}

entity "AI Suggestion" as AISuggestion {
  *suggestion_id
  --
  table_name
  issue
  suggestion_text
  risk_level
  confidence
  action_status
  sql_patch
}

entity "Job Artifact" as JobArtifact {
  *artifact_id
  --
  artifact_type
  storage_path
  file_size_bytes
}

entity "Sandbox Log" as SandboxLog {
  *sandbox_log_id
  --
  attempt_number
  is_success
  container_log
  execution_time_ms
  was_self_corrected
  self_correction_count
}

User ||--o{ Project : owns
Project ||--o{ AnalysisJob : contains
AnalysisJob ||--o{ AISuggestion : generates
AnalysisJob ||--o{ JobArtifact : has
AnalysisJob ||--o{ SandboxLog : records

@enduml
```

## Ringkasan Relasi Entity

- User memiliki banyak Project (1..N)
- Project memiliki banyak Analysis Job (1..N)
- Analysis Job menghasilkan banyak AI Suggestion (1..N)
- Analysis Job memiliki banyak Job Artifact (1..N)
- Analysis Job memiliki banyak Sandbox Log (1..N)

## Alternatif: ERD Gaya Chen (Relationship-Centric)

```plantuml
@startuml
left to right direction
skinparam linetype ortho
skinparam shadowing false
skinparam usecase {
  BackgroundColor #F2F2F2
  BorderColor #666666
}

' Entity
rectangle "User" as E_USER #E6F2FF
rectangle "Project" as E_PROJECT #E6F2FF
rectangle "Analysis Job" as E_JOB #E6F2FF
rectangle "AI Suggestion" as E_SUGGESTION #E6F2FF
rectangle "Job Artifact" as E_ARTIFACT #E6F2FF
rectangle "Sandbox Log" as E_LOG #E6F2FF

' Relationship (Chen-style node approximation in PlantUML)
usecase "OWNS" as R_OWNS
usecase "CONTAINS" as R_CONTAINS
usecase "GENERATES" as R_GENERATES
usecase "HAS" as R_HAS
usecase "RECORDS" as R_RECORDS

' Cardinality
E_USER "1" -- "N" R_OWNS
R_OWNS "N" -- "1" E_PROJECT

E_PROJECT "1" -- "N" R_CONTAINS
R_CONTAINS "N" -- "1" E_JOB

E_JOB "1" -- "N" R_GENERATES
R_GENERATES "N" -- "1" E_SUGGESTION

E_JOB "1" -- "N" R_HAS
R_HAS "N" -- "1" E_ARTIFACT

E_JOB "1" -- "N" R_RECORDS
R_RECORDS "N" -- "1" E_LOG

@enduml
```

## Prompt Lucid AI (Siap Pakai)

Gunakan prompt berikut untuk membuat ERD konseptual dengan tampilan seperti contoh Google (entity-relationship centric):

```text
Buat Entity Relationship Diagram (ERD) konseptual dengan notasi Chen untuk sistem SQL Optimizer.

Gaya visual:
- Entity berbentuk persegi panjang biru muda
- Attribute berbentuk oval hijau
- Relationship berbentuk diamond hitam
- Garis relasi jelas, rapi, mudah dibaca
- Layout horizontal kiri ke kanan
- Tampilkan kardinalitas 1 dan N di tiap hubungan

Entity dan atribut:

1) User
- user_id (key)
- email
- full_name
- password_hash
- created_at

2) Project
- project_id (key)
- name
- description
- created_at

3) AnalysisJob
- job_id (key)
- original_filename
- status
- app_context
- db_dialect
- ai_model_used
- tokens_used
- error_message
- created_at
- completed_at

4) AISuggestion
- suggestion_id (key)
- table_name
- issue
- suggestion_text
- risk_level
- confidence
- action_status
- sql_patch

5) JobArtifact
- artifact_id (key)
- artifact_type
- storage_path
- file_size_bytes
- created_at

6) SandboxLog
- sandbox_log_id (key)
- attempt_number
- is_success
- container_log
- execution_time_ms
- was_self_corrected
- self_correction_count
- created_at

Relationship dan kardinalitas:
- User OWNS Project (1:N)
- Project CONTAINS AnalysisJob (1:N)
- AnalysisJob GENERATES AISuggestion (1:N)
- AnalysisJob HAS JobArtifact (1:N)
- AnalysisJob RECORDS SandboxLog (1:N)  

Aturan tambahan:
- Jangan ubah nama entity
- Jangan ubah nama relationship
- Fokus ERD konseptual (bukan tabel fisik SQL)
- Jangan tampilkan tipe data SQL detail
- Judul diagram: ERD Konseptual SQL Optimizer System
- Hasil siap ekspor PNG/SVG resolusi tinggi
```

Prompt ringkas:

```text
Buat ERD konseptual notasi Chen untuk SQL Optimizer dengan entity: User, Project, AnalysisJob, AISuggestion, JobArtifact, SandboxLog. Gunakan style klasik: entity rectangle biru, attribute oval hijau, relationship diamond hitam, kardinalitas 1:N. Relasi: User OWNS Project, Project CONTAINS AnalysisJob, AnalysisJob GENERATES AISuggestion, AnalysisJob HAS JobArtifact, AnalysisJob RECORDS SandboxLog. Tampilkan atribut inti tiap entity tanpa tipe data SQL, layout kiri ke kanan, rapi untuk presentasi.
```
