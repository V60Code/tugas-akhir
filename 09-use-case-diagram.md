# 09 Use Case Diagram

## Mode Mermaid

```mermaid
flowchart LR
    A[User Belum Registrasi]
    B[User Terdaftar]

    subgraph SYS[SQL Optimizer System]
      UC1((Registrasi Akun))
      UC2((Login))
      UC3((Kelola Project))
      UC4((Upload SQL dan Analisis))
      UC5((Review Suggestion dan ERD))
      UC6((Finalize dan Validasi Sandbox))
      UC7((Download SQL Optimized))
      UC8((Kelola Sesi Profil /me dan Logout))
    end

    A --> UC1
    A -. Tidak bisa akses fitur lain sebelum registrasi/login .-> X[Akses Ditolak]

    B --> UC2
    B --> UC3
    B --> UC4
    B --> UC5
    B --> UC6
    B --> UC7
    B --> UC8

    UC2 -. Setelah login berhasil .-> B
```

## Mode PlantUML

```plantuml
@startuml
left to right direction

actor "User Belum Registrasi" as Unregistered
actor "User Terdaftar" as Registered

rectangle "SQL Optimizer System" {
  usecase "Registrasi Akun" as UC1
  usecase "Login" as UC2
  usecase "Kelola Project" as UC3
  usecase "Upload SQL dan Analisis" as UC4
  usecase "Review Suggestion dan ERD" as UC5
  usecase "Finalize dan Validasi Sandbox" as UC6
  usecase "Download SQL Optimized" as UC7
  usecase "Kelola Sesi Profil /me dan Logout" as UC8
  usecase "Akses Ditolak" as UCDeny
}

Unregistered --> UC1
Unregistered ..> UCDeny : Tidak bisa akses fitur lain\nsebelum registrasi/login

Registered --> UC2
Registered --> UC3
Registered --> UC4
Registered --> UC5
Registered --> UC6
Registered --> UC7
Registered --> UC8

UC2 ..> Registered : Setelah login berhasil
@enduml
```

## Aturan Akses Aktor

- User Belum Registrasi: hanya bisa melakukan registrasi akun.
- User Terdaftar: bisa login dan mengakses semua fitur utama sistem.
- Semua endpoint/halaman fitur utama wajib protected (JWT + ownership check).