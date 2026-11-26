"""Ringkasan operasional Admin. SELECT only, tanpa efek samping."""

from psycopg.rows import dict_row
from app.db import pool


_SQL_RINGKASAN = """
WITH siap_acc AS (
    -- Same eligibility as enrollment_repo.daftar_menunggu().
    SELECT e.id, p.harga_bulanan
    FROM enrollments e
    JOIN students s ON s.user_id = e.student_id
    JOIN users u ON u.id = s.user_id
    JOIN programs p ON p.id = e.program_id
    LEFT JOIN LATERAL (
        SELECT i.status FROM invoices i WHERE i.enrollment_id = e.id
        ORDER BY i.created_at DESC, i.id DESC LIMIT 1
    ) inv ON TRUE
    WHERE e.status = 'menunggu' AND u.status = 'aktif'
      AND (p.harga_bulanan = 0 OR inv.status = 'lunas')
), calon_tagihan_bulanan AS (
    -- Same eligibility and period as billing_repo.buat_tagihan_bulanan().
    -- Existing invoices of ANY status keep their unique enrollment/period.
    SELECT e.id, p.harga_bulanan
    FROM enrollments e JOIN programs p ON p.id = e.program_id
    WHERE e.status = 'aktif' AND p.harga_bulanan > 0
      AND NOT EXISTS (
          SELECT 1 FROM invoices i WHERE i.enrollment_id = e.id
            AND i.periode = date_trunc('month', CURRENT_DATE)::date
      )
)
SELECT
    (SELECT COUNT(*) FROM users WHERE role = 'siswa' AND status = 'aktif') AS siswa_aktif,
    (SELECT COUNT(*) FROM users WHERE role = 'tutor' AND status = 'aktif') AS tutor_aktif,
    (SELECT COUNT(*) FROM programs WHERE status = 'buka') AS program_buka,
    (SELECT COUNT(*) FROM enrollments WHERE status = 'aktif') AS enrollment_aktif,
    (SELECT COUNT(*) FROM users WHERE role IN ('siswa', 'tutor')
        AND status = 'menunggu_konfirmasi') AS konfirmasi_akun,
    (SELECT COUNT(*) FROM siap_acc) AS konfirmasi_pendaftaran,
    (SELECT COUNT(*) FROM siap_acc WHERE harga_bulanan > 0) AS konfirmasi_berbayar,
    (SELECT COUNT(*) FROM siap_acc WHERE harga_bulanan = 0) AS konfirmasi_gratis,
    (SELECT COUNT(*) FROM users WHERE role = 'siswa'
        AND status = 'menunggu_konfirmasi') AS konfirmasi_siswa,
    (SELECT COUNT(*) FROM users WHERE role = 'tutor'
        AND status = 'menunggu_konfirmasi') AS konfirmasi_tutor,
    (SELECT COUNT(*) FROM invoices WHERE status = 'belum_dibayar') AS tagihan_belum_lunas,
    (SELECT COUNT(*) FROM invoices WHERE status = 'belum_dibayar'
        AND jatuh_tempo < (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Jakarta')::date) AS tagihan_terlambat,
    (SELECT COUNT(*) FROM invoices WHERE status = 'belum_dibayar'
        AND jatuh_tempo < CURRENT_DATE) AS tagihan_tunggakan,
    (SELECT COALESCE(SUM(jumlah), 0) FROM invoices WHERE status = 'belum_dibayar'
        AND jatuh_tempo < CURRENT_DATE) AS nominal_tunggakan,
    (SELECT COUNT(*) FROM calon_tagihan_bulanan) AS tagihan_bulanan_siap,
    (SELECT COALESCE(SUM(harga_bulanan),0) FROM calon_tagihan_bulanan) AS nominal_tagihan_bulanan_siap,
    date_trunc('month', CURRENT_DATE)::date AS periode_tagihan_bulanan,
    CURRENT_DATE AS tanggal_db,
    CURRENT_DATE + 7 AS jatuh_tempo_tagihan_bulanan,
    (SELECT COUNT(*) FROM schedules WHERE aktif = TRUE) AS jadwal_aktif,
    (SELECT COUNT(*) FROM class_sessions WHERE status::text = 'perlu_laporan') AS sesi_perlu_laporan,
    (SELECT COUNT(*) FROM users WHERE role = 'siswa') AS siswa_total,
    (SELECT COUNT(*) FROM users WHERE role = 'tutor') AS tutor_total,
    (SELECT COUNT(*) FROM users WHERE role = 'admin' AND status = 'aktif') AS admin_aktif,
    (SELECT COUNT(*) FROM users WHERE role = 'admin') AS admin_total,
    (SELECT COUNT(*) FROM programs) AS program_total,
    (SELECT COUNT(*) FROM rooms WHERE aktif = TRUE) AS ruang_aktif,
    (SELECT COUNT(*) FROM rooms) AS ruang_total,
    (SELECT COUNT(*) FROM enrollments WHERE status = 'menunggu_pembayaran') AS enrollment_menunggu_bayar,
    (SELECT COUNT(*) FROM enrollments WHERE status = 'selesai') AS enrollment_selesai,
    (SELECT COUNT(*) FROM enrollments WHERE status = 'menunggu') AS enrollment_menunggu,
    (SELECT COUNT(*) FROM enrollments WHERE status = 'ditolak') AS enrollment_ditolak,
    (SELECT COUNT(*) FROM enrollments WHERE status = 'batal') AS enrollment_batal,
    (SELECT COUNT(*) FROM invoices WHERE status = 'lunas') AS tagihan_lunas,
    (SELECT COALESCE(SUM(jumlah), 0) FROM invoices
        WHERE status = 'belum_dibayar') AS nominal_belum_lunas,
    (SELECT COUNT(*) FROM payments WHERE status = 'lunas'
        AND date_trunc('month', paid_at AT TIME ZONE 'Asia/Jakarta') =
            date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Jakarta')) AS transaksi_lunas_bulan_ini,
    (SELECT COUNT(*) FROM payments WHERE status = 'gagal'
        AND date_trunc('month', created_at AT TIME ZONE 'Asia/Jakarta') =
            date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Jakarta')) AS transaksi_gagal_bulan_ini,
    (SELECT COUNT(*) FROM payment_refunds WHERE status = 'berhasil'
        AND date_trunc('month', COALESCE(processed_at, created_at) AT TIME ZONE 'Asia/Jakarta') =
            date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Jakarta')) AS refund_bulan_ini,
    (SELECT COALESCE(SUM(jumlah), 0) FROM payment_refunds WHERE status = 'berhasil'
        AND date_trunc('month', COALESCE(processed_at, created_at) AT TIME ZONE 'Asia/Jakarta') =
            date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Jakarta')) AS nominal_refund_bulan_ini,
    (SELECT COALESCE(SUM(jumlah), 0) FROM payments
        WHERE status = 'lunas'
        AND date_trunc('month', paid_at AT TIME ZONE 'Asia/Jakarta') =
            date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Jakarta')) AS nominal_lunas_bulan_ini
"""

_SQL_JADWAL_HARI_INI = """
SELECT p.nama AS program, u.nama_lengkap AS tutor, r.nama AS ruang,
       s.jam_mulai, s.jam_selesai, COUNT(*) OVER () AS total_jadwal
FROM schedules s
JOIN programs p ON p.id = s.program_id
JOIN users u ON u.id = s.tutor_id
JOIN rooms r ON r.id = s.room_id
WHERE s.aktif = TRUE
  AND s.hari::text = CASE EXTRACT(ISODOW FROM
        (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Jakarta'))::int
        WHEN 1 THEN 'senin'
        WHEN 2 THEN 'selasa'
        WHEN 3 THEN 'rabu'
        WHEN 4 THEN 'kamis'
        WHEN 5 THEN 'jumat'
        WHEN 6 THEN 'sabtu'
        ELSE 'minggu' END
ORDER BY s.jam_mulai, p.nama, s.id
LIMIT 5
"""


def ringkasan_admin() -> dict:
    """Jumlah real dari data transaksi, tidak mengubah status apa pun."""
    with pool.connection(timeout=5) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(_SQL_RINGKASAN)
            return cur.fetchone() or {}


def jadwal_hari_ini_admin() -> list[dict]:
    """Jadwal rutin aktif pada hari lokal Asia/Jakarta; bukan sesi terlaksana."""
    with pool.connection(timeout=5) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(_SQL_JADWAL_HARI_INI)
            return list(cur.fetchall())
