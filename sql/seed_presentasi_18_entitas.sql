-- ============================================================================
-- SIBIMA-AI | DATA PRESENTASI - 20 SISWA + 6 TUTOR | 18 ENTITAS
-- Target database: sibima_db (tabel fisik bahasa Indonesia)
-- Semua pengisian data dilakukan dengan INSERT INTO ... VALUES / INSERT SELECT.
-- Tidak ada DROP, TRUNCATE, DELETE, UPDATE, CREATE USER, atau pengubahan schema.
-- Satu transaksi: gagal => ROLLBACK otomatis (psql: ON_ERROR_STOP=1).
-- Sekali jalan. Skrip MENOLAK jika data demo yang sama sudah ada.
-- Password login demo: Username capitalized + '_2026', mis. Jaya_2026.
-- Kolom password_hash hanya berisi bcrypt $2b$ cost 12, bukan plaintext.
-- Data fiktif, jangan gunakan di sistem produksi.
-- ============================================================================
BEGIN;
SET LOCAL search_path TO public, pg_temp;
SELECT pg_advisory_xact_lock(731042, 2026);
DO $guard$
DECLARE
    jumlah_admin INTEGER;
BEGIN
    IF current_database() <> 'sibima_db' THEN
        RAISE EXCEPTION 'Seed DEMO wajib dijalankan di sibima_db; database sekarang: %', current_database();
    END IF;
    IF to_regclass('public.pengguna') IS NULL OR to_regclass('public.pendaftaran') IS NULL
       OR to_regclass('public.v_nilai_akhir') IS NULL THEN
        RAISE EXCEPTION 'Schema/migrasi operasional SIBIMA-AI belum lengkap.';
    END IF;
    SELECT COUNT(*) INTO jumlah_admin FROM public.pengguna
      WHERE role='admin'::public.user_role AND status='aktif'::public.user_status;
    IF jumlah_admin < 1 THEN
        RAISE EXCEPTION 'Buat Admin pertama lebih dulu lewat buat_admin.py.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.pengguna
        WHERE email LIKE '%.sibima.demo26@example.test'
           OR LOWER(username) IN ('andi', 'bima', 'citra', 'salsa', 'daffa', 'naya', 'rafi', 'tiara', 'alif', 'rina', 'bagas', 'keyla', 'dito', 'zahra', 'arya', 'nisa', 'reza', 'lala', 'fajar', 'jaya', 'raka', 'dimas', 'laras', 'nanda', 'putri', 'faris')
    ) THEN
        RAISE EXCEPTION 'Data akun DEMO 2026 terdeteksi. Dibatalkan agar tidak dobel.';
    END IF;
    IF EXISTS (SELECT 1 FROM public.program_bimbel WHERE kode LIKE 'D26-%')
       OR EXISTS (SELECT 1 FROM public.ruangan WHERE nama LIKE 'Presentasi %')
       OR EXISTS (SELECT 1 FROM public.tagihan WHERE no_invoice LIKE 'D26-INV-%')
       OR EXISTS (SELECT 1 FROM public.pengumuman WHERE event_key LIKE 'demo26:%')
    THEN
       RAISE EXCEPTION 'Penanda dataset DEMO 2026 sudah ditemukan; seeding dibatalkan.';
    END IF;
END;
$guard$;

-- 01/18 PENGGUNA. Admin lama tidak diubah.
INSERT INTO public.pengguna
 (username, email, nama_lengkap, password_hash, role, status,
  email_verified, must_change_password, id_pengguna_penyetuju,
  approved_at, created_at)
SELECT x.username, x.email, x.nama_lengkap, x.password_hash,
       x.role::public.user_role, 'aktif'::public.user_status,
       TRUE, FALSE,
       (SELECT id_pengguna FROM public.pengguna WHERE role='admin' AND status='aktif'
        ORDER BY id_pengguna LIMIT 1),
       TIMESTAMPTZ '2026-08-20 10:00:00+07',
       TIMESTAMPTZ '2026-08-18 09:00:00+07'
FROM (VALUES
    ('andi', 'andi.sibima.demo26@example.test', 'Andi Pratama', '$2b$12$FDSZivL3xgnZX5JtsxnD1OC37CTNxWRvmNQjH/iJyvA54Tz3Sdi2W', 'siswa'),
    ('bima', 'bima.sibima.demo26@example.test', 'Bima Saputra', '$2b$12$9WlGaktRu07PljYHhN/Ah.Iq27n0N1qtg9XbO19ONYrybsG7xVKGO', 'siswa'),
    ('citra', 'citra.sibima.demo26@example.test', 'Citra Maharani', '$2b$12$rQZg56tkIWzQ2uKxfvwCouCnbF6fYlJvrGo3k98QKJud/QaIgyHzK', 'siswa'),
    ('salsa', 'salsa.sibima.demo26@example.test', 'Salsa Putri', '$2b$12$iugK0z./fpBLAEtmgjBXM.GKGsZtRl87EHmqqu42lnEE3LJ0MO8b2', 'siswa'),
    ('daffa', 'daffa.sibima.demo26@example.test', 'Daffa Maulana', '$2b$12$i4o4tSzfly06nOxkgvv7j.es1FUPguqblVrCIccvDq8UuRuRaX6iO', 'siswa'),
    ('naya', 'naya.sibima.demo26@example.test', 'Naya Kirana', '$2b$12$sNt2BvzX6sMBaZ04oiY4.uLWMXBu7gGHLIVZulYDR1Mv4iZ/E/y6e', 'siswa'),
    ('rafi', 'rafi.sibima.demo26@example.test', 'Rafi Hidayat', '$2b$12$6NE50X7kB5L14wk6LFLu1uM.7NwGWJhLaXsU/cbcrThroED6feQ1K', 'siswa'),
    ('tiara', 'tiara.sibima.demo26@example.test', 'Tiara Anindya', '$2b$12$Dyeoz.b12zFPVky7UDa2CeXcxiO4PpMqz8XtZ.f/4QwJL4vQR9dpe', 'siswa'),
    ('alif', 'alif.sibima.demo26@example.test', 'Alif Ramadhan', '$2b$12$4TJMc4rx.GF.7EXk5j9n7.eqFmoK6LAnw0WCRH7Ait5GCCPLtMOLS', 'siswa'),
    ('rina', 'rina.sibima.demo26@example.test', 'Rina Oktaviani', '$2b$12$toYqgp9OcTP/oxHnfUVkO.x8qZvlqguwuIDytiBRDowUNkCQfEXUq', 'siswa'),
    ('bagas', 'bagas.sibima.demo26@example.test', 'Bagas Wibowo', '$2b$12$n2jh2OH33zspvnCLR3MUUOq9.DQNvMA7uV5WCexNTSJE5HX6XGgzy', 'siswa'),
    ('keyla', 'keyla.sibima.demo26@example.test', 'Keyla Azzahra', '$2b$12$rLj/Watx38X3XlY6VJkhKeGPLglWgTo4dgxAEJFgLt0hbP4u9o3lG', 'siswa'),
    ('dito', 'dito.sibima.demo26@example.test', 'Dito Nugroho', '$2b$12$7Vd.K8YWw9Mi5NxSMM68ee4jjeKdQkNQGQ0R9Mupeci00PUFzPDw2', 'siswa'),
    ('zahra', 'zahra.sibima.demo26@example.test', 'Zahra Syafira', '$2b$12$Av4S6JnJM0HzBUvvYA0VUOlNYNU8QjLXP2zrRnHTUL5cztaPe2nGC', 'siswa'),
    ('arya', 'arya.sibima.demo26@example.test', 'Arya Pamungkas', '$2b$12$AMhmSI1ibcKgeOxfXgm0JeMMvLHbEngk7VTctxfExeUNZDMvggTUi', 'siswa'),
    ('nisa', 'nisa.sibima.demo26@example.test', 'Nisa Amelia', '$2b$12$PTh/R6sE/wuPp1hO5ELxDOw53ZBmP42e/rZATsWJ1VGvZ6jNUHY/y', 'siswa'),
    ('reza', 'reza.sibima.demo26@example.test', 'Reza Kurniawan', '$2b$12$v9DkinwCxBWMxsyuvtohT.CuoC3YkS6thpmyTWHUzWyZ5aZ/4FdqW', 'siswa'),
    ('lala', 'lala.sibima.demo26@example.test', 'Lala Permata', '$2b$12$vTpDd7L1rHb5zqMXBp588.npHJXcATAOu1fgjF6hMmegC3PWSUTgi', 'siswa'),
    ('fajar', 'fajar.sibima.demo26@example.test', 'Fajar Firmansyah', '$2b$12$jJ0RuZyheKU4Aoe8J77use6G.uV4rWo6XM0DCQmJejd52C.4K2VNG', 'siswa'),
    ('raka', 'raka.sibima.demo26@example.test', 'Raka Aditya', '$2b$12$Xmj9COCwkl8VMP4Q6iaTEOcrX9KAYlyL6BgEnkbVDaF4qMT5dTORe', 'tutor'),
    ('dimas', 'dimas.sibima.demo26@example.test', 'Dimas Prasetyo', '$2b$12$trl.NcCP1Pl8JERAxc2rYOFPxciXdVftFMCNtunYHu1dyUWutTW8S', 'tutor'),
    ('laras', 'laras.sibima.demo26@example.test', 'Laras Widyaningrum', '$2b$12$Gv/DNy8NjZdXXoYUtjt.kO86slBxhc6hYW9lvQy7AEavPxE5Ls7IS', 'tutor'),
    ('nanda', 'nanda.sibima.demo26@example.test', 'Nanda Mahendra', '$2b$12$tCi3xjcX3mTkS6eQ68oON.g1sVRzL5mes.GPLbCOJclnlCd1ifFgO', 'tutor'),
    ('putri', 'putri.sibima.demo26@example.test', 'Putri Anggraini', '$2b$12$AORQWgZosDrl4LTHq6v16eqKAhVEogL4E4geQ8BivVYFo1QZzEkri', 'tutor'),
    ('faris', 'faris.sibima.demo26@example.test', 'Faris Akbar', '$2b$12$Yx4M22GwBBM69IrKZT5EzepSbHyt/2yt/Ld2xmsWcjscdrFxuC9/.', 'tutor')
) AS x(username, email, nama_lengkap, password_hash, role);

-- 02/18 SISWA. 20 profil terhubung ke pengguna melalui PK/FK id_pengguna.
INSERT INTO public.siswa
  (id_pengguna, role, nis, jenjang, sekolah, nama_wali)
SELECT u.id_pengguna, 'siswa'::public.user_role, x.nis, x.jenjang,
       x.sekolah, x.nama_wali
FROM (VALUES
    ('andi', 'D26-0001', 'SMP', 'SMP Negeri Harapan', 'Nur Aisyah'),
    ('bima', 'D26-0002', 'SMP', 'SMP Negeri Harapan', 'Siti Maryam'),
    ('citra', 'D26-0003', 'SMP', 'SMP Negeri Harapan', 'Hendra Wijaya'),
    ('salsa', 'D26-0004', 'SMA', 'SMA Negeri Cendekia', 'Ratna Sari'),
    ('daffa', 'D26-0005', 'SMA', 'SMA Negeri Cendekia', 'Dewi Lestari'),
    ('naya', 'D26-0006', 'SMA', 'SMA Negeri Cendekia', 'Dian Puspita'),
    ('rafi', 'D26-0007', 'SMP', 'SMP Negeri Harapan', 'Yuni Hartati'),
    ('tiara', 'D26-0008', 'SMP', 'SMP Negeri Harapan', 'Agus Santosa'),
    ('alif', 'D26-0009', 'SMP', 'SMP Negeri Harapan', 'Fauziah Nur'),
    ('rina', 'D26-0010', 'SMA', 'SMA Negeri Cendekia', 'Eka Wulandari'),
    ('bagas', 'D26-0011', 'SMA', 'SMA Negeri Cendekia', 'Sri Rahayu'),
    ('keyla', 'D26-0012', 'SMA', 'SMA Negeri Cendekia', 'Rahma Fitriani'),
    ('dito', 'D26-0013', 'SMP', 'SMP Negeri Harapan', 'Novi Susanti'),
    ('zahra', 'D26-0014', 'SMP', 'SMP Negeri Harapan', 'Bambang Setiawan'),
    ('arya', 'D26-0015', 'SMP', 'SMP Negeri Harapan', 'Indah Pertiwi'),
    ('nisa', 'D26-0016', 'SMA', 'SMA Negeri Cendekia', 'Maya Kartika'),
    ('reza', 'D26-0017', 'SMA', 'SMA Negeri Cendekia', 'Rudi Hartono'),
    ('lala', 'D26-0018', 'SMA', 'SMA Negeri Cendekia', 'Tuti Anggraini'),
    ('fajar', 'D26-0019', 'SMP', 'SMP Negeri Harapan', 'Sumiati'),
    ('jaya', 'D26-0020', 'SMP', 'SMP Negeri Harapan', 'Yanti Wicaksono')
) AS x(username, nis, jenjang, sekolah, nama_wali)
JOIN public.pengguna u ON u.username=x.username AND u.role='siswa';

-- 03/18 TUTOR. 6 profil keahlian dan kode tutor.
INSERT INTO public.tutor
  (id_pengguna, role, kode_tutor, keahlian)
SELECT u.id_pengguna, 'tutor'::public.user_role, x.kode_tutor, x.keahlian
FROM (VALUES
    ('raka', 'TD26-01', 'Matematika SMP dan SMA'),
    ('dimas', 'TD26-02', 'Matematika dan numerasi'),
    ('laras', 'TD26-03', 'IPA SMP'),
    ('nanda', 'TD26-04', 'IPA terpadu'),
    ('putri', 'TD26-05', 'Bahasa Inggris SMP dan SMA'),
    ('faris', 'TD26-06', 'Fisika SMA')
) AS x(username, kode_tutor, keahlian)
JOIN public.pengguna u ON u.username=x.username AND u.role='tutor';

-- 04/18 PROGRAM BIMBEL. Program fiktif terpisah dari program asli.
INSERT INTO public.program_bimbel
 (kode, nama, jenjang, deskripsi, harga_bulanan, kuota, status,
  bobot_tugas, bobot_kuis, bobot_uts, bobot_uas)
VALUES
    ('D26-MT7', 'Matematika Kelas 7', 'SMP', 'Program presentasi SIBIMA-AI (data fiktif).', 145000, 15, 'buka', 30, 20, 20, 30),
    ('D26-IPA8', 'IPA Terpadu Kelas 8', 'SMP', 'Program presentasi SIBIMA-AI (data fiktif).', 155000, 15, 'buka', 30, 20, 20, 30),
    ('D26-ING7', 'Bahasa Inggris Kelas 7', 'SMP', 'Program presentasi SIBIMA-AI (data fiktif).', 135000, 15, 'buka', 30, 20, 20, 30),
    ('D26-MT10', 'Matematika Kelas 10', 'SMA', 'Program presentasi SIBIMA-AI (data fiktif).', 175000, 15, 'buka', 30, 20, 20, 30),
    ('D26-FIS10', 'Fisika Kelas 10', 'SMA', 'Program presentasi SIBIMA-AI (data fiktif).', 185000, 15, 'buka', 30, 20, 20, 30),
    ('D26-ING10', 'Bahasa Inggris Kelas 10', 'SMA', 'Program presentasi SIBIMA-AI (data fiktif).', 165000, 15, 'buka', 30, 20, 20, 30);

-- 05/18 RUANGAN.
INSERT INTO public.ruangan (nama, kapasitas, aktif)
VALUES
    ('Presentasi A', 20, TRUE),
    ('Presentasi B', 18, TRUE),
    ('Presentasi C', 16, TRUE),
    ('Presentasi D', 16, TRUE);

-- 06/18 JADWAL KELAS. Waktu tidak bentrok untuk tutor/ruangan yang sama.
INSERT INTO public.jadwal_kelas
 (id_program, id_tutor, id_ruangan, hari, jam_mulai, jam_selesai, aktif)
SELECT p.id_program, t.id_pengguna, r.id_ruangan,
       x.hari::public.nama_hari, x.mulai::time, x.selesai::time, TRUE
FROM (VALUES
    ('D26-MT7', 'raka', 'Presentasi A', 'senin', '15:00', '16:30'),
    ('D26-MT7', 'dimas', 'Presentasi B', 'rabu', '15:00', '16:30'),
    ('D26-IPA8', 'laras', 'Presentasi A', 'selasa', '15:00', '16:30'),
    ('D26-IPA8', 'nanda', 'Presentasi B', 'kamis', '15:00', '16:30'),
    ('D26-ING7', 'putri', 'Presentasi C', 'jumat', '15:00', '16:30'),
    ('D26-MT10', 'raka', 'Presentasi A', 'senin', '17:00', '18:30'),
    ('D26-FIS10', 'faris', 'Presentasi D', 'selasa', '17:00', '18:30'),
    ('D26-ING10', 'putri', 'Presentasi C', 'jumat', '17:00', '18:30')
) AS x(kode_program, username_tutor, nama_ruangan, hari, mulai, selesai)
JOIN public.program_bimbel p ON p.kode=x.kode_program
JOIN public.pengguna ut ON ut.username=x.username_tutor AND ut.role='tutor'
JOIN public.tutor t ON t.id_pengguna=ut.id_pengguna
JOIN public.ruangan r ON r.nama=x.nama_ruangan;

-- 07/18 PENDAFTARAN. 24 aktif, 2 menunggu bayar, 1 menunggu admin,
-- 2 ditolak, 1 selesai. Semua berhubungan ke siswa dan program yang benar.
INSERT INTO public.pendaftaran
 (id_siswa, id_program, status, alasan_tolak, id_pengguna_pemroses,
  processed_at, created_at)
SELECT u.id_pengguna, p.id_program, x.status::public.enrollment_status,
       CASE WHEN x.status='ditolak' THEN 'Simulasi pengembalian biaya demo.' ELSE NULL END,
       CASE WHEN x.status IN ('aktif','ditolak','selesai')
         THEN (SELECT id_pengguna FROM public.pengguna WHERE role='admin' AND status='aktif'
               ORDER BY id_pengguna LIMIT 1) ELSE NULL END,
       CASE WHEN x.status IN ('aktif','ditolak','selesai')
         THEN TIMESTAMPTZ '2026-08-25 10:00:00+07' ELSE NULL END,
       TIMESTAMPTZ '2026-08-20 09:00:00+07'
FROM (VALUES
    ('andi', 'D26-MT7', 'aktif'),
    ('bima', 'D26-ING7', 'aktif'),
    ('citra', 'D26-IPA8', 'aktif'),
    ('salsa', 'D26-MT10', 'aktif'),
    ('daffa', 'D26-FIS10', 'aktif'),
    ('naya', 'D26-ING10', 'aktif'),
    ('rafi', 'D26-MT7', 'aktif'),
    ('tiara', 'D26-IPA8', 'aktif'),
    ('alif', 'D26-ING7', 'aktif'),
    ('rina', 'D26-MT10', 'aktif'),
    ('bagas', 'D26-FIS10', 'aktif'),
    ('keyla', 'D26-ING10', 'aktif'),
    ('dito', 'D26-MT7', 'aktif'),
    ('zahra', 'D26-IPA8', 'aktif'),
    ('arya', 'D26-ING7', 'aktif'),
    ('nisa', 'D26-MT10', 'aktif'),
    ('reza', 'D26-FIS10', 'aktif'),
    ('lala', 'D26-ING10', 'aktif'),
    ('fajar', 'D26-MT7', 'aktif'),
    ('jaya', 'D26-IPA8', 'aktif'),
    ('andi', 'D26-IPA8', 'aktif'),
    ('citra', 'D26-MT7', 'aktif'),
    ('bima', 'D26-IPA8', 'aktif'),
    ('salsa', 'D26-FIS10', 'aktif'),
    ('daffa', 'D26-ING10', 'menunggu_pembayaran'),
    ('naya', 'D26-MT10', 'menunggu_pembayaran'),
    ('rafi', 'D26-ING7', 'menunggu'),
    ('tiara', 'D26-ING7', 'ditolak'),
    ('alif', 'D26-MT7', 'ditolak'),
    ('rina', 'D26-ING10', 'selesai')
) AS x(username_siswa, kode_program, status)
JOIN public.pengguna u ON u.username=x.username_siswa AND u.role='siswa'
JOIN public.program_bimbel p ON p.kode=x.kode_program;

-- 08/18 PERTEMUAN KELAS. 40 pertemuan (8 jadwal x 5),
-- 32 berstatus selesai, 8 menunggu laporan tutor.
INSERT INTO public.pertemuan_kelas
 (id_jadwal, tanggal, pertemuan_ke, topik, ringkasan, status, selesai_at, created_at)
SELECT j.id_jadwal, x.tanggal::date, x.ke::smallint, x.topik,
       CASE WHEN x.status='selesai' THEN 'Materi tersampaikan; absensi telah dicatat.' ELSE NULL END,
       x.status::public.session_status,
       CASE WHEN x.status='selesai' THEN (x.tanggal::date + TIME '17:00') AT TIME ZONE 'Asia/Jakarta' ELSE NULL END,
       ((x.tanggal::date - 1) + TIME '08:00') AT TIME ZONE 'Asia/Jakarta'
FROM (VALUES
    ('D26-MT7', 'raka', 'senin', '15:00', '2026-09-07', 1, 'selesai', 'Pembahasan materi pertemuan 1'),
    ('D26-MT7', 'raka', 'senin', '15:00', '2026-09-14', 2, 'selesai', 'Pembahasan materi pertemuan 2'),
    ('D26-MT7', 'raka', 'senin', '15:00', '2026-09-21', 3, 'selesai', 'Pembahasan materi pertemuan 3'),
    ('D26-MT7', 'raka', 'senin', '15:00', '2026-09-28', 4, 'selesai', 'Pembahasan materi pertemuan 4'),
    ('D26-MT7', 'raka', 'senin', '15:00', '2026-10-05', 5, 'perlu_laporan', 'Pembahasan materi pertemuan 5'),
    ('D26-MT7', 'dimas', 'rabu', '15:00', '2026-09-09', 1, 'selesai', 'Pembahasan materi pertemuan 1'),
    ('D26-MT7', 'dimas', 'rabu', '15:00', '2026-09-16', 2, 'selesai', 'Pembahasan materi pertemuan 2'),
    ('D26-MT7', 'dimas', 'rabu', '15:00', '2026-09-23', 3, 'selesai', 'Pembahasan materi pertemuan 3'),
    ('D26-MT7', 'dimas', 'rabu', '15:00', '2026-09-30', 4, 'selesai', 'Pembahasan materi pertemuan 4'),
    ('D26-MT7', 'dimas', 'rabu', '15:00', '2026-10-07', 5, 'perlu_laporan', 'Pembahasan materi pertemuan 5'),
    ('D26-IPA8', 'laras', 'selasa', '15:00', '2026-09-08', 1, 'selesai', 'Pembahasan materi pertemuan 1'),
    ('D26-IPA8', 'laras', 'selasa', '15:00', '2026-09-15', 2, 'selesai', 'Pembahasan materi pertemuan 2'),
    ('D26-IPA8', 'laras', 'selasa', '15:00', '2026-09-22', 3, 'selesai', 'Pembahasan materi pertemuan 3'),
    ('D26-IPA8', 'laras', 'selasa', '15:00', '2026-09-29', 4, 'selesai', 'Pembahasan materi pertemuan 4'),
    ('D26-IPA8', 'laras', 'selasa', '15:00', '2026-10-06', 5, 'perlu_laporan', 'Pembahasan materi pertemuan 5'),
    ('D26-IPA8', 'nanda', 'kamis', '15:00', '2026-09-10', 1, 'selesai', 'Pembahasan materi pertemuan 1'),
    ('D26-IPA8', 'nanda', 'kamis', '15:00', '2026-09-17', 2, 'selesai', 'Pembahasan materi pertemuan 2'),
    ('D26-IPA8', 'nanda', 'kamis', '15:00', '2026-09-24', 3, 'selesai', 'Pembahasan materi pertemuan 3'),
    ('D26-IPA8', 'nanda', 'kamis', '15:00', '2026-10-01', 4, 'selesai', 'Pembahasan materi pertemuan 4'),
    ('D26-IPA8', 'nanda', 'kamis', '15:00', '2026-10-08', 5, 'perlu_laporan', 'Pembahasan materi pertemuan 5'),
    ('D26-ING7', 'putri', 'jumat', '15:00', '2026-09-11', 1, 'selesai', 'Pembahasan materi pertemuan 1'),
    ('D26-ING7', 'putri', 'jumat', '15:00', '2026-09-18', 2, 'selesai', 'Pembahasan materi pertemuan 2'),
    ('D26-ING7', 'putri', 'jumat', '15:00', '2026-09-25', 3, 'selesai', 'Pembahasan materi pertemuan 3'),
    ('D26-ING7', 'putri', 'jumat', '15:00', '2026-10-02', 4, 'selesai', 'Pembahasan materi pertemuan 4'),
    ('D26-ING7', 'putri', 'jumat', '15:00', '2026-10-09', 5, 'perlu_laporan', 'Pembahasan materi pertemuan 5'),
    ('D26-MT10', 'raka', 'senin', '17:00', '2026-09-07', 1, 'selesai', 'Pembahasan materi pertemuan 1'),
    ('D26-MT10', 'raka', 'senin', '17:00', '2026-09-14', 2, 'selesai', 'Pembahasan materi pertemuan 2'),
    ('D26-MT10', 'raka', 'senin', '17:00', '2026-09-21', 3, 'selesai', 'Pembahasan materi pertemuan 3'),
    ('D26-MT10', 'raka', 'senin', '17:00', '2026-09-28', 4, 'selesai', 'Pembahasan materi pertemuan 4'),
    ('D26-MT10', 'raka', 'senin', '17:00', '2026-10-05', 5, 'perlu_laporan', 'Pembahasan materi pertemuan 5'),
    ('D26-FIS10', 'faris', 'selasa', '17:00', '2026-09-08', 1, 'selesai', 'Pembahasan materi pertemuan 1'),
    ('D26-FIS10', 'faris', 'selasa', '17:00', '2026-09-15', 2, 'selesai', 'Pembahasan materi pertemuan 2'),
    ('D26-FIS10', 'faris', 'selasa', '17:00', '2026-09-22', 3, 'selesai', 'Pembahasan materi pertemuan 3'),
    ('D26-FIS10', 'faris', 'selasa', '17:00', '2026-09-29', 4, 'selesai', 'Pembahasan materi pertemuan 4'),
    ('D26-FIS10', 'faris', 'selasa', '17:00', '2026-10-06', 5, 'perlu_laporan', 'Pembahasan materi pertemuan 5'),
    ('D26-ING10', 'putri', 'jumat', '17:00', '2026-09-11', 1, 'selesai', 'Pembahasan materi pertemuan 1'),
    ('D26-ING10', 'putri', 'jumat', '17:00', '2026-09-18', 2, 'selesai', 'Pembahasan materi pertemuan 2'),
    ('D26-ING10', 'putri', 'jumat', '17:00', '2026-09-25', 3, 'selesai', 'Pembahasan materi pertemuan 3'),
    ('D26-ING10', 'putri', 'jumat', '17:00', '2026-10-02', 4, 'selesai', 'Pembahasan materi pertemuan 4'),
    ('D26-ING10', 'putri', 'jumat', '17:00', '2026-10-09', 5, 'perlu_laporan', 'Pembahasan materi pertemuan 5')
) AS x(kode_program, username_tutor, hari, jam_mulai, tanggal, ke, status, topik)
JOIN public.program_bimbel p ON p.kode=x.kode_program
JOIN public.pengguna ut ON ut.username=x.username_tutor AND ut.role='tutor'
JOIN public.jadwal_kelas j ON j.id_program=p.id_program
  AND j.id_tutor=ut.id_pengguna AND j.hari=x.hari::public.nama_hari
  AND j.jam_mulai=x.jam_mulai::time;

-- 09/18 KEHADIRAN. Data dibuat untuk setiap siswa yang memiliki
-- pendaftaran aktif pada program di 32 pertemuan selesai (140 catatan).
WITH peserta AS (
 SELECT pk.id_pertemuan, pk.pertemuan_ke, pk.tanggal, pd.id_siswa,
        pd.id_pendaftaran,
        ROW_NUMBER() OVER (PARTITION BY pk.id_pertemuan ORDER BY pd.id_siswa) AS urutan
 FROM public.pertemuan_kelas pk
 JOIN public.jadwal_kelas jk ON jk.id_jadwal=pk.id_jadwal
 JOIN public.pendaftaran pd ON pd.id_program=jk.id_program AND pd.status='aktif'
 JOIN public.pengguna u ON u.id_pengguna=pd.id_siswa
 WHERE pk.status='selesai' AND u.email LIKE '%.sibima.demo26@example.test'
)
INSERT INTO public.kehadiran
 (id_pertemuan, id_siswa, status, keterangan, dicatat_at, id_pendaftaran)
SELECT id_pertemuan, id_siswa,
       CASE WHEN (urutan+pertemuan_ke) % 7 = 0 THEN 'A'::public.attendance_status
            WHEN (urutan+pertemuan_ke) % 9 = 0 THEN 'I'::public.attendance_status
            WHEN (urutan+pertemuan_ke) % 11 = 0 THEN 'S'::public.attendance_status
            ELSE 'H'::public.attendance_status END,
       CASE WHEN (urutan+pertemuan_ke) % 7 = 0 THEN 'Tidak hadir (data simulasi)'
            WHEN (urutan+pertemuan_ke) % 9 = 0 THEN 'Izin (data simulasi)'
            WHEN (urutan+pertemuan_ke) % 11 = 0 THEN 'Sakit (data simulasi)'
            ELSE NULL END,
       ((tanggal::date + TIME '18:00') AT TIME ZONE 'Asia/Jakarta'),
       id_pendaftaran
FROM peserta;

-- 10/18 NILAI. 3 jenis penilaian untuk masing-masing 24 pendaftaran aktif
-- dan 1 pendaftaran selesai (75 nilai). Pemilik nilai & tutor valid via FK.
INSERT INTO public.nilai
 (id_pendaftaran, jenis, judul, nilai, tanggal, id_tutor_penginput, created_at)
SELECT pd.id_pendaftaran, k.jenis::public.grade_type, k.judul,
       (55 + ((pd.id_siswa * 7 + k.urutan * 9) % 41))::numeric(5,2),
       (DATE '2026-10-02' + (k.urutan * 7)),
       (SELECT MIN(jk.id_tutor) FROM public.jadwal_kelas jk
        WHERE jk.id_program=pd.id_program AND jk.aktif=TRUE),
       TIMESTAMPTZ '2026-10-20 12:00:00+07'
FROM public.pendaftaran pd
JOIN public.pengguna u ON u.id_pengguna=pd.id_siswa
CROSS JOIN (VALUES ('tugas','Latihan Materi 1',1),
                   ('kuis','Kuis Tengah Bab',2),
                   ('uts','Ujian Tengah Semester',3)) AS k(jenis,judul,urutan)
WHERE u.email LIKE '%.sibima.demo26@example.test'
  AND pd.status IN ('aktif','selesai');

-- 11/18 TAGIHAN. 30 invoice (satu per pendaftaran) periode Oktober 2026.
-- Invoice untuk pendaftaran ditolak dibuat batal, belum bayar tetap terbuka.
WITH tagihan_demo AS (
 SELECT pd.id_pendaftaran, pd.status,
        p.harga_bulanan,
        ROW_NUMBER() OVER (ORDER BY pd.id_pendaftaran) AS nomor
 FROM public.pendaftaran pd
 JOIN public.program_bimbel p ON p.id_program=pd.id_program
 JOIN public.pengguna u ON u.id_pengguna=pd.id_siswa
 WHERE u.email LIKE '%.sibima.demo26@example.test'
)
INSERT INTO public.tagihan
 (no_invoice, id_pendaftaran, periode, jumlah, jatuh_tempo, status, created_at)
SELECT 'D26-INV-' || LPAD(nomor::text,4,'0'), id_pendaftaran,
       DATE '2026-10-01', harga_bulanan, DATE '2026-10-12',
       CASE WHEN status='menunggu_pembayaran' THEN 'belum_dibayar'::public.invoice_status
            WHEN status='ditolak' THEN 'batal'::public.invoice_status
            ELSE 'lunas'::public.invoice_status END,
       TIMESTAMPTZ '2026-09-28 09:00:00+07'
FROM tagihan_demo;

-- 12/18 PEMBAYARAN. 28 pembayaran, nominal 100% sesuai tagihan.
-- Pembayaran 2 pendaftaran ditolak berstatus direfund (catatan refund menyusul).
INSERT INTO public.pembayaran
 (id_tagihan, kode_bayar, jumlah, status, paid_at,
  id_pengguna_pemroses, processed_at, created_at)
SELECT t.id_tagihan,
       'D26-PAY-' || RIGHT(t.no_invoice,4), t.jumlah,
       CASE WHEN pd.status='ditolak' THEN 'direfund'::public.payment_status
            ELSE 'lunas'::public.payment_status END,
       TIMESTAMPTZ '2026-10-07 09:00:00+07',
       (SELECT id_pengguna FROM public.pengguna WHERE role='admin' AND status='aktif'
        ORDER BY id_pengguna LIMIT 1),
       TIMESTAMPTZ '2026-10-08 10:00:00+07',
       TIMESTAMPTZ '2026-10-06 08:00:00+07'
FROM public.tagihan t
JOIN public.pendaftaran pd ON pd.id_pendaftaran=t.id_pendaftaran
WHERE t.no_invoice LIKE 'D26-INV-%'
  AND pd.status <> 'menunggu_pembayaran';

-- 13/18 PENGEMBALIAN PEMBAYARAN. 2 contoh refund simulasi.
INSERT INTO public.pengembalian_pembayaran
 (id_pembayaran, kode_refund, jumlah, alasan, status, created_at, processed_at)
SELECT b.id_pembayaran, 'D26-RFD-' || RIGHT(b.kode_bayar,4), b.jumlah,
       'Pendaftaran ditolak; pengembalian dana simulasi.',
       'berhasil', TIMESTAMPTZ '2026-10-09 08:00:00+07',
       TIMESTAMPTZ '2026-10-09 09:00:00+07'
FROM public.pembayaran b
WHERE b.kode_bayar LIKE 'D26-PAY-%' AND b.status='direfund';

-- 14/18 PENGUMUMAN. 8 pengumuman manual. Trigger lain juga membuat
-- notifikasi otomatis berdasarkan pendaftaran/tagihan/pembayaran/nilai.
INSERT INTO public.pengumuman
 (judul, isi, id_pengguna_pembuat, created_at, sumber, kategori,
  event_key, id_program)
SELECT x.judul, x.isi,
       (SELECT id_pengguna FROM public.pengguna WHERE role='admin' AND status='aktif'
        ORDER BY id_pengguna LIMIT 1),
       TIMESTAMPTZ '2026-10-15 10:00:00+07', 'admin', x.kategori,
       'demo26:ann:' || x.nomor,
       (SELECT id_program FROM public.program_bimbel WHERE kode=x.program_kode)
FROM (VALUES
    ('01', 'Pembukaan Program Semester Ganjil', 'Program bimbel semester ganjil telah dibuka untuk peserta.', 'umum', NULL),
    ('02', 'Pengingat Jadwal Matematika', 'Periksa jadwal Matematika melalui menu Jadwal Kelas.', 'jadwal', 'D26-MT7'),
    ('03', 'Tips Belajar Efektif', 'Sisihkan waktu belajar dan mengulas catatan setiap minggu.', 'umum', NULL),
    ('04', 'Informasi Evaluasi Tengah Semester', 'Evaluasi tengah semester akan dilaksanakan sesuai jadwal.', 'umum', NULL),
    ('05', 'Pengumuman Pengajar', 'Tutor diminta melengkapi ringkasan pertemuan dan absensi.', 'umum', NULL),
    ('06', 'Pembaharuan Materi Bahasa Inggris', 'Materi kosakata tersedia untuk belajar mandiri.', 'umum', 'D26-ING7'),
    ('07', 'Informasi Pembayaran', 'Periksa status tagihan bulanan melalui dashboard siswa.', 'tagihan', NULL),
    ('08', 'Persiapan Presentasi Sistem', 'Seluruh akun dalam dataset ini adalah akun demonstrasi.', 'umum', NULL)
) AS x(nomor, judul, isi, kategori, program_kode);

-- 15/18 TARGET PENGUMUMAN. 10 kombinasi pengumuman dan peran.
INSERT INTO public.target_pengumuman (id_pengumuman, target_role)
SELECT a.id_pengumuman, x.role::public.user_role
FROM (VALUES
    ('01', 'siswa'),
    ('02', 'siswa'),
    ('03', 'siswa'),
    ('04', 'siswa'),
    ('05', 'tutor'),
    ('06', 'siswa'),
    ('07', 'siswa'),
    ('08', 'siswa'),
    ('08', 'tutor'),
    ('04', 'tutor')
) AS x(nomor, role)
JOIN public.pengumuman a ON a.event_key='demo26:ann:' || x.nomor;

-- 16/18 PEMBACAAN PENGUMUMAN. 24 bukti baca sesuai target role.
INSERT INTO public.pembacaan_pengumuman (id_pengumuman, id_pengguna, read_at)
SELECT a.id_pengumuman, u.id_pengguna,
       TIMESTAMPTZ '2026-10-16 09:00:00+07'
FROM (VALUES
    ('01', 'andi'),
    ('01', 'citra'),
    ('01', 'jaya'),
    ('02', 'andi'),
    ('02', 'rafi'),
    ('02', 'citra'),
    ('03', 'bima'),
    ('03', 'salsa'),
    ('03', 'naya'),
    ('04', 'andi'),
    ('04', 'tiara'),
    ('04', 'raka'),
    ('05', 'raka'),
    ('05', 'dimas'),
    ('05', 'laras'),
    ('06', 'bima'),
    ('06', 'alif'),
    ('06', 'arya'),
    ('07', 'salsa'),
    ('07', 'rina'),
    ('07', 'jaya'),
    ('08', 'jaya'),
    ('08', 'nanda'),
    ('08', 'putri')
) AS x(nomor, username)
JOIN public.pengumuman a ON a.event_key='demo26:ann:' || x.nomor
JOIN public.pengguna u ON u.username=x.username
JOIN public.target_pengumuman tp
  ON tp.id_pengumuman=a.id_pengumuman AND tp.target_role=u.role;

-- 17/18 KODE OTP. 6 OTP simulasi yang SUDAH KEDALUWARSA dan terpakai;
-- hash bcrypt saja; tidak dapat dipakai untuk login/verifikasi sekarang.
INSERT INTO public.kode_otp
 (id_pengguna, code_hash, purpose, expires_at, attempts, used_at, created_at)
SELECT u.id_pengguna, x.hash_otp, 'register'::public.otp_purpose,
       TIMESTAMPTZ '2026-08-18 09:05:00+07', 1,
       TIMESTAMPTZ '2026-08-18 09:02:00+07',
       TIMESTAMPTZ '2026-08-18 09:00:00+07'
FROM (VALUES
    ('andi', '$2b$12$CoSD0ViCzKt4HLCBQsVW5.gEUs6T4V79yW9ZjrOup7o.s4lXLCcBK'),
    ('citra', '$2b$12$1RvfobJDcpTKxuz8a/t/BuNdYSLiWWlF3vuiuIP911sS6dUg9X8xC'),
    ('bima', '$2b$12$hF0Dg5.Gn3xtrbhaGFsxM.L1OroRGru7N9aWqIWd3woMWdHNIP4Vi'),
    ('raka', '$2b$12$.NLE8XFuKN4kvs6y3nd/1.xsKFFmKvRdnzQnUjdGh6mU7RfYS.wD6'),
    ('dimas', '$2b$12$VPwBY.ZUSnI516DNjwEZZuvQ7Y7181ZTsdOZVkDVBrKFKK//u9D..'),
    ('jaya', '$2b$12$iQ2GXpKzHaD9OrOrM4lJ8ObJ2pASjtso3Li36AYHo24hYWY8qfF3O')
) AS x(username, hash_otp)
JOIN public.pengguna u ON u.username=x.username;

-- 18/18 LOG AKTIVITAS. 40 catatan fiktif untuk audit demo.
INSERT INTO public.log_aktivitas (id_pengguna, aksi, detail, created_at)
SELECT CASE WHEN x.username='__ADMIN__' THEN
          (SELECT id_pengguna FROM public.pengguna WHERE role='admin' AND status='aktif'
           ORDER BY id_pengguna LIMIT 1)
       ELSE (SELECT id_pengguna FROM public.pengguna WHERE username=x.username) END,
       x.aksi, x.detail, TIMESTAMPTZ '2026-10-20 11:00:00+07'
FROM (VALUES
    ('andi', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('bima', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('citra', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('salsa', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('daffa', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('naya', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('rafi', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('tiara', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('alif', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('rina', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('bagas', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('keyla', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('dito', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('zahra', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('arya', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('nisa', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('reza', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('lala', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('fajar', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('jaya', 'PRESENTASI_LOGIN', 'Simulasi akses dashboard siswa untuk dataset presentasi.'),
    ('raka', 'PRESENTASI_TUTOR', 'Simulasi pengelolaan jadwal dan nilai untuk presentasi.'),
    ('raka', 'PRESENTASI_ABSENSI', 'Simulasi pencatatan kehadiran untuk presentasi.'),
    ('dimas', 'PRESENTASI_TUTOR', 'Simulasi pengelolaan jadwal dan nilai untuk presentasi.'),
    ('dimas', 'PRESENTASI_ABSENSI', 'Simulasi pencatatan kehadiran untuk presentasi.'),
    ('laras', 'PRESENTASI_TUTOR', 'Simulasi pengelolaan jadwal dan nilai untuk presentasi.'),
    ('laras', 'PRESENTASI_ABSENSI', 'Simulasi pencatatan kehadiran untuk presentasi.'),
    ('nanda', 'PRESENTASI_TUTOR', 'Simulasi pengelolaan jadwal dan nilai untuk presentasi.'),
    ('nanda', 'PRESENTASI_ABSENSI', 'Simulasi pencatatan kehadiran untuk presentasi.'),
    ('putri', 'PRESENTASI_TUTOR', 'Simulasi pengelolaan jadwal dan nilai untuk presentasi.'),
    ('putri', 'PRESENTASI_ABSENSI', 'Simulasi pencatatan kehadiran untuk presentasi.'),
    ('faris', 'PRESENTASI_TUTOR', 'Simulasi pengelolaan jadwal dan nilai untuk presentasi.'),
    ('faris', 'PRESENTASI_ABSENSI', 'Simulasi pencatatan kehadiran untuk presentasi.'),
    ('__ADMIN__', 'PRESENTASI_ADMIN', 'Membuat program bimbel'),
    ('__ADMIN__', 'PRESENTASI_ADMIN', 'Menambahkan jadwal kelas'),
    ('__ADMIN__', 'PRESENTASI_ADMIN', 'Memeriksa pendaftaran'),
    ('__ADMIN__', 'PRESENTASI_ADMIN', 'Memverifikasi pembayaran'),
    ('__ADMIN__', 'PRESENTASI_ADMIN', 'Meninjau refund'),
    ('__ADMIN__', 'PRESENTASI_ADMIN', 'Memeriksa laporan nilai'),
    ('__ADMIN__', 'PRESENTASI_ADMIN', 'Meninjau absensi'),
    ('__ADMIN__', 'PRESENTASI_ADMIN', 'Membuat pengumuman')
) AS x(username, aksi, detail);

-- Semua 18 entitas berisi data. COMMIT hanya jika semua INSERT berhasil.
COMMIT;

