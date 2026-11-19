# SIBIMA-AI

**Sistem Informasi Bimbingan Belajar berbasis AI**

Aplikasi manajemen bimbingan belajar berbasis terminal dengan integrasi PostgreSQL dan Google Gemini.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-5865F2?style=for-the-badge&logo=googlegemini&logoColor=white)
![CLI](https://img.shields.io/badge/Interactive_CLI-24292F?style=for-the-badge&logo=gnometerminal&logoColor=white)

[Overview](#overview) · [Fitur](#fitur-utama) · [Arsitektur](#arsitektur-sistem) · [Instalasi](#instalasi) · [SIBIMA-AI](#asisten-ai) · [Database](#database) · [Tim Pengembang](#tim-pengembang)

---

## Overview

**SIBIMA (Sistem Informasi Bimbingan Belajar)** merupakan aplikasi untuk mengelola kegiatan administrasi dan akademik lembaga bimbingan belajar dalam satu sistem terintegrasi. Aplikasi dibangun menggunakan Python dengan antarmuka Command Line Interface (CLI) interaktif serta PostgreSQL sebagai basis data relasional.

SIBIMA-AI mengintegrasikan Google Gemini sebagai asisten AI yang dapat membantu pengguna memperoleh informasi, memahami materi, dan menganalisis data bimbingan belajar sesuai hak akses masing-masing.

Sistem memiliki tiga peran utama: **Admin**, **Tutor**, dan **Siswa**. Setiap peran memiliki dashboard, menu, dan kewenangan yang berbeda.

| Database | Antarmuka | Asisten AI | Pengguna |
| :---: | :---: | :---: | :---: |
| 18 entitas | Rich + Questionary | Gemini + RAG | 3 role |

## Tim Pengembang

| No. | Nama | NIM |
| ---: | --- | --- |
| 1 | Ahmad Rafli Wijaya | 262410102025 |
| 2 | Ilzam Saifillah Yulianto | 262410102008 |
| 3 | Tegar Hafidz Firdausy | 262410102013 |
| 4 | Try Andra Wicaksono | 262410102011 |

## Fitur Utama

### Admin

- Mengelola akun, verifikasi, dan persetujuan Siswa serta Tutor.
- Mengelola program bimbel, kuota, biaya bulanan, ruangan, dan jadwal kelas.
- Mengelola pendaftaran, konfirmasi pembayaran, tagihan, dan pengembalian pembayaran.
- Memantau kehadiran, nilai, dan aktivitas akademik.
- Membuat serta mengarsipkan pengumuman.
- Melihat laporan pemasukan, jumlah siswa, kehadiran, dan nilai; mengekspor CSV atau Excel.
- Mengakses analisis data melalui SIBIMA-AI sesuai kebijakan akses Admin.

### Tutor

- Melihat jadwal mengajar dan daftar siswa pada program yang diampu.
- Mengelola pertemuan kelas, topik, dan ringkasan materi.
- Mencatat serta memperbarui kehadiran siswa.
- Menginput nilai tugas, kuis, UTS, dan UAS.
- Melihat rekap akademik kelas serta mengelola pengumuman kelas.
- Menggunakan SIBIMA-AI untuk membantu analisis kegiatan mengajar sesuai kewenangan Tutor.

### Siswa

- Registrasi akun, verifikasi OTP, dan pengelolaan profil.
- Melihat katalog program dan melakukan pendaftaran kelas.
- Melihat tagihan, melakukan simulasi pembayaran, dan memperoleh bukti pembayaran.
- Mengakses jadwal, materi pertemuan, absensi, nilai, dan rapor pribadi.
- Menerima pengumuman dan notifikasi.
- Menggunakan SIBIMA-AI untuk bantuan belajar dan informasi akademik pribadi.

> Pembayaran dan pengembalian pembayaran dalam proyek ini merupakan simulasi internal, bukan integrasi bank atau payment gateway. Tidak ada perpindahan uang sungguhan.

## Asisten AI

SIBIMA-AI menggabungkan beberapa mekanisme untuk membantu pengguna:

| Komponen | Fungsi |
| --- | --- |
| Gemini API | Percakapan berbasis bahasa alami dengan respons streaming |
| Function calling | Mengakses fungsi aplikasi yang telah diizinkan |
| Schema-aware query engine | Membaca metadata dan menyusun analisis data terstruktur sesuai izin |
| Multi-stage query | Menggabungkan hasil beberapa agregasi untuk analisis yang lebih kompleks |
| RAG (Retrieval-Augmented Generation) | Mengambil referensi dari dokumen pengetahuan yang relevan |
| Role-based access | Membatasi tool dan cakupan data berdasarkan role pengguna |

Contoh pertanyaan yang dapat digunakan dalam demonstrasi:

| Role | Contoh pertanyaan |
| --- | --- |
| Admin | Berapa jumlah siswa aktif pada setiap program? |
| Admin | Bagaimana ringkasan pembayaran dan tagihan periode ini? |
| Tutor | Bagaimana rekap kehadiran siswa pada kelas yang saya ampu? |
| Tutor | Siapa yang membutuhkan perhatian akademik berdasarkan nilai di kelas saya? |
| Siswa | Bagaimana perkembangan nilai saya? |
| Siswa | Apa jadwal kelas dan tagihan saya? |

Akses metadata database dan query generik dibatasi untuk Admin dan Tutor sesuai kewenangannya. Siswa menggunakan tool informasi pribadi dan tidak diberi akses ke tool metadata skema atau query generik. AI tidak dimaksudkan untuk menjalankan perubahan data melalui percakapan.

> Respons AI dapat dipengaruhi kualitas data, ketersediaan API, dan validitas rencana query. Pertanyaan kompleks tidak selalu dapat dijawab; hasil penting tetap perlu diverifikasi melalui aplikasi atau laporan resmi.

## Alur Sistem

```text
Registrasi akun → Verifikasi OTP → Persetujuan Admin
    → Login Siswa → Pilih program → Tagihan
    → Simulasi pembayaran → Konfirmasi Admin
        ├── Disetujui → Pendaftaran aktif
        │   → Jadwal dan pertemuan → Absensi dan nilai → Laporan
        └── Ditolak → Penanganan sesuai status transaksi
```

Akun yang sudah aktif dapat mengakses fitur akun dan pembayaran. Akses kegiatan kelas mengikuti status pendaftaran dan ketentuan pembayaran. Tagihan bulanan, absensi per pertemuan, dan penilaian menjadi bagian dari operasional berkelanjutan.

## Arsitektur Sistem

SIBIMA menggunakan struktur berlapis untuk memisahkan antarmuka, aturan bisnis, dan akses data.

```text
CLI (Rich + Questionary)
    └── Service Layer
        ├── Repository Layer → PostgreSQL
        └── SIBIMA-AI
            ├── Gemini API
            ├── Tool controller dan aturan akses → Repository Layer
            └── Dokumen RAG dan indeks lokal
```

| Lapisan | Tanggung jawab |
| --- | --- |
| UI | Tampilan terminal dan interaksi pengguna |
| Service | Aturan bisnis, autentikasi, validasi, dan otorisasi |
| Repository | Query PostgreSQL dan pengelolaan data |
| Database | Integritas data, foreign key, constraint, fungsi, trigger, dan view |
| AI | Integrasi Gemini, tool controller, query engine, dan retrieval dokumen |

## Tech Stack

| Teknologi | Kegunaan |
| --- | --- |
| Python | Bahasa pemrograman utama |
| PostgreSQL | Database relasional |
| Psycopg 3 | Driver PostgreSQL dan connection pool |
| Rich | Panel, tabel, dan komponen visual terminal |
| Questionary | Navigasi serta input interaktif |
| Google Gen AI SDK | Integrasi Gemini API |
| ChromaDB | Penyimpanan indeks vektor RAG |
| PyMuPDF | Pemrosesan dokumen PDF untuk RAG |
| bcrypt | Hash dan verifikasi password |
| python-dotenv | Konfigurasi environment |
| SMTP | Pengiriman OTP dan email ketika dikonfigurasi |
| ReportLab | Pembuatan dokumen PDF |
| OpenPyXL | Ekspor laporan Excel |
| pytest | Pengujian otomatis |

## Database

Nama database versi ini: **`sibima_db`**.

Skema PostgreSQL menggunakan nama entitas dan atribut sesuai perancangan. Struktur dasar terdiri dari 18 tabel fisik, 147 atribut, 28 constraint foreign key, dan 11 definisi tipe ENUM.

| Kelompok | Entitas fisik |
| --- | --- |
| Pengguna dan keamanan | `pengguna`, `siswa`, `tutor`, `kode_otp`, `log_aktivitas` |
| Program dan akademik | `program_bimbel`, `ruangan`, `jadwal_kelas`, `pertemuan_kelas`, `kehadiran`, `nilai`, `pendaftaran` |
| Keuangan | `tagihan`, `pembayaran`, `pengembalian_pembayaran` |
| Komunikasi | `pengumuman`, `target_pengumuman`, `pembacaan_pengumuman` |

Integritas data dijaga dengan identity, primary key, foreign key, unique constraint, check constraint, serta validasi jadwal dan pembayaran. Skema juga menyediakan view laporan dan trigger pendukung proses bisnis.

Versi migrasi mempertahankan view kompatibilitas dengan nama tabel lama agar modul Python yang belum dikonversi sepenuhnya tetap dapat mengakses tabel fisik berbahasa Indonesia. View tersebut bukan entitas fisik tambahan.

## Struktur Proyek

```text
SIBIMA-AI/
├── app/
│   ├── repositories/       # Query dan akses database
│   ├── services/           # Aturan bisnis dan integrasi AI
│   ├── ui/                 # Antarmuka CLI
│   ├── utils/              # Utilitas dan validasi
│   ├── config.py           # Konfigurasi aplikasi
│   ├── db.py               # Koneksi database
│   ├── main.py             # Entry point
│   └── session.py          # Sesi pengguna
├── knowledge/
│   ├── sources/            # Dokumen sumber RAG
│   └── verified/           # Dokumen pengetahuan terverifikasi
├── sql/
│   ├── 00_buat_database.sql
│   ├── schema.sql
│   ├── 02_kompatibilitas_dan_operasional.sql
│   ├── 03_seed_demo.sql
│   └── 04_validasi.sql
├── tests/                  # Pengujian otomatis
├── buat_admin.py           # Inisialisasi Admin pertama
├── .env.example            # Template environment
├── .gitignore
├── requirements.txt
└── README.md
```

## Instalasi

### 1. Prasyarat

- Python dan pip yang kompatibel dengan `requirements.txt`.
- PostgreSQL lokal dengan dukungan extension `btree_gist`.
- pgAdmin 4 atau PostgreSQL command-line tools (`psql`).
- Google Gemini API key untuk fitur AI; SMTP apabila menggunakan OTP/email sungguhan.

Buka terminal pada root proyek SIBIMA-AI.

### 2. Virtual environment dan dependensi

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### 3. Persiapan database

Untuk **instalasi baru pada database kosong**, periksa terlebih dahulu bahwa `sibima_db` belum digunakan. Jalankan skrip berikut secara berurutan:

```powershell
psql -U postgres -d postgres -v ON_ERROR_STOP=1 -f ".\sql\00_buat_database.sql"
psql -U postgres -d sibima_db -v ON_ERROR_STOP=1 -f ".\sql\schema.sql"
psql -U postgres -d sibima_db -v ON_ERROR_STOP=1 -f ".\sql\02_kompatibilitas_dan_operasional.sql"
psql -U postgres -d sibima_db -v ON_ERROR_STOP=1 -f ".\sql\04_validasi.sql"
```

Alternatif melalui pgAdmin: jalankan skrip pembuatan database pada koneksi `postgres`, lalu buka Query Tool pada `sibima_db` untuk menjalankan tiga skrip berikutnya secara berurutan.

Opsional, isi contoh program dan ruangan:

```powershell
psql -U postgres -d sibima_db -v ON_ERROR_STOP=1 -f ".\sql\03_seed_demo.sql"
```

Jangan menjalankan ulang schema pada database aktif atau menjalankan arsip migrasi lama pada `sibima_db`. Seed demo hanya digunakan sesuai prasyaratnya agar tidak terjadi konflik data.

### 4. Konfigurasi environment

Edit `.env` dari template yang telah disalin. Contoh konfigurasi pengujian lokal:

```dotenv
DB_TARGET=local
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sibima_db
DB_USER=postgres
DB_PASSWORD=<password-postgresql-lokal>
DB_SSLMODE=prefer

OTP_MODE=simulasi
OTP_EXPIRE_MINUTES=5
OTP_MAX_ATTEMPTS=3
PAYMENT_SIMULATION_SUCCESS_RATE=90

GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
SIBIMA_RAG_ENABLED=false
```

`DB_USER=postgres` merupakan contoh untuk pengujian lokal. Untuk penggunaan selain demo, gunakan role aplikasi khusus yang telah memperoleh hak akses minimum yang diperlukan.

- Isi `GEMINI_API_KEY` secara lokal dan pilih model yang tersedia pada API key untuk menggunakan AI.
- Aktifkan RAG hanya setelah dokumen pengetahuan dan indeks lokal siap serta sesuai skema terkini.
- Untuk `OTP_MODE=email`, isi variabel SMTP pada `.env` sesuai layanan pengiriman email yang digunakan.
- Jangan commit file `.env`, password, API key, atau kredensial SMTP.

### 5. Inisialisasi Admin pertama

```powershell
.\.venv\Scripts\python.exe buat_admin.py
```

Masukkan username, email, nama lengkap, dan password pada prompt terminal. Jalankan langkah ini hanya apabila belum ada Admin yang perlu digunakan.

### 6. Jalankan aplikasi

```powershell
.\.venv\Scripts\python.exe -m app.main
```

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Skenario pengujian utama meliputi autentikasi, akses per role, pendaftaran, transaksi pembayaran, jadwal, pertemuan, kehadiran, nilai, laporan, dan pembatasan akses AI. Beberapa pengujian integrasi memerlukan konfigurasi PostgreSQL atau Gemini yang sesuai. Tes historis yang masih memakai asumsi skema lama perlu ditinjau sebelum dianggap sebagai hasil pengujian final.

## Keamanan dan Batasan

- Password disimpan sebagai hash bcrypt, bukan teks biasa. OTP memiliki batas waktu dan percobaan.
- Persetujuan akun dan otorisasi diterapkan melalui alur aplikasi.
- Tool AI untuk membaca database dibatasi berdasarkan role; pengujian akses antarpengguna tetap diperlukan.
- Gunakan akun serta data fiktif untuk demonstrasi, dan backup database sebelum impor data atau menjalankan migrasi.
- Sistem ditujukan untuk pembelajaran, demonstrasi, dan pengembangan; belum diklaim siap untuk produksi tanpa pengujian end-to-end dan hardening tambahan.

---

**SIBIMA-AI**

*Sistem informasi bimbingan belajar yang mengintegrasikan administrasi, akademik, dan kecerdasan buatan.*

Dikembangkan sebagai proyek pembelajaran di bidang Teknologi Informasi.

