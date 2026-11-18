-- SIBIMA-AI | VALIDASI DATA PRESENTASI (READ-ONLY)
-- Jalankan di database sibima_db setelah seed berhasil.
DO $validasi$
DECLARE
  v RECORD;
BEGIN
  IF current_database() <> 'sibima_db' THEN
    RAISE EXCEPTION 'Database salah: %', current_database();
  END IF;
  FOR v IN
    SELECT * FROM (VALUES
      ('siswa_demo', (SELECT count(*)::int FROM public.siswa s JOIN public.pengguna u ON u.id_pengguna=s.id_pengguna WHERE u.email LIKE '%.sibima.demo26@example.test'), 20),
      ('tutor_demo', (SELECT count(*)::int FROM public.tutor t JOIN public.pengguna u ON u.id_pengguna=t.id_pengguna WHERE u.email LIKE '%.sibima.demo26@example.test'), 6),
      ('program_demo', (SELECT count(*)::int FROM public.program_bimbel WHERE kode LIKE 'D26-%'), 6),
      ('ruangan_demo', (SELECT count(*)::int FROM public.ruangan WHERE nama LIKE 'Presentasi %'), 4),
      ('jadwal_demo', (SELECT count(*)::int FROM public.jadwal_kelas j JOIN public.program_bimbel p ON p.id_program=j.id_program WHERE p.kode LIKE 'D26-%'), 8),
      ('pendaftaran_demo', (SELECT count(*)::int FROM public.pendaftaran d JOIN public.pengguna u ON u.id_pengguna=d.id_siswa WHERE u.email LIKE '%.sibima.demo26@example.test'), 30),
      ('pertemuan_demo', (SELECT count(*)::int FROM public.pertemuan_kelas pk JOIN public.jadwal_kelas j ON j.id_jadwal=pk.id_jadwal JOIN public.program_bimbel p ON p.id_program=j.id_program WHERE p.kode LIKE 'D26-%'), 40),
      ('kehadiran_demo', (SELECT count(*)::int FROM public.kehadiran k JOIN public.pertemuan_kelas pk ON pk.id_pertemuan=k.id_pertemuan JOIN public.jadwal_kelas j ON j.id_jadwal=pk.id_jadwal JOIN public.program_bimbel p ON p.id_program=j.id_program WHERE p.kode LIKE 'D26-%'), 140),
      ('nilai_demo', (SELECT count(*)::int FROM public.nilai n JOIN public.pendaftaran d ON d.id_pendaftaran=n.id_pendaftaran JOIN public.pengguna u ON u.id_pengguna=d.id_siswa WHERE u.email LIKE '%.sibima.demo26@example.test'), 75),
      ('tagihan_demo', (SELECT count(*)::int FROM public.tagihan WHERE no_invoice LIKE 'D26-INV-%'), 30),
      ('pembayaran_demo', (SELECT count(*)::int FROM public.pembayaran WHERE kode_bayar LIKE 'D26-PAY-%'), 28),
      ('refund_demo', (SELECT count(*)::int FROM public.pengembalian_pembayaran WHERE kode_refund LIKE 'D26-RFD-%'), 2),
      ('pengumuman_manual_demo', (SELECT count(*)::int FROM public.pengumuman WHERE event_key LIKE 'demo26:ann:%'), 8),
      ('target_pengumuman_manual', (SELECT count(*)::int FROM public.target_pengumuman t JOIN public.pengumuman a ON a.id_pengumuman=t.id_pengumuman WHERE a.event_key LIKE 'demo26:ann:%'), 10),
      ('pembacaan_manual_demo', (SELECT count(*)::int FROM public.pembacaan_pengumuman r JOIN public.pengumuman a ON a.id_pengumuman=r.id_pengumuman WHERE a.event_key LIKE 'demo26:ann:%'), 24),
      ('otp_demo', (SELECT count(*)::int FROM public.kode_otp o JOIN public.pengguna u ON u.id_pengguna=o.id_pengguna WHERE u.email LIKE '%.sibima.demo26@example.test'), 6),
      ('log_demo', (SELECT count(*)::int FROM public.log_aktivitas WHERE aksi LIKE 'PRESENTASI_%'), 40)
    ) AS z(nama, aktual, target)
  LOOP
    IF v.aktual <> v.target THEN
      RAISE EXCEPTION 'Validasi % gagal: aktual %, target %',v.nama,v.aktual,v.target;
    END IF;
  END LOOP;
  RAISE NOTICE 'VALIDASI LULUS: 20 siswa, 6 tutor, 18 entitas demo, 140 absensi, 75 nilai, 28 pembayaran.';
END;
$validasi$;

-- Ringkasan jumlah per role (tidak menampilkan hash password)
SELECT role, COUNT(*) AS jumlah_akun_demo FROM public.pengguna
WHERE email LIKE '%.sibima.demo26@example.test'
GROUP BY role ORDER BY role;

-- Demonstrasi relasi utama, cocok untuk screenshot pgAdmin
SELECT u.nama_lengkap AS siswa, p.nama AS program, d.status AS pendaftaran,
       t.status AS tagihan, t.jumlah AS nominal, b.status AS pembayaran
FROM public.pendaftaran d
JOIN public.pengguna u ON u.id_pengguna=d.id_siswa
JOIN public.program_bimbel p ON p.id_program=d.id_program
LEFT JOIN public.tagihan t ON t.id_pendaftaran=d.id_pendaftaran
LEFT JOIN public.pembayaran b ON b.id_tagihan=t.id_tagihan
WHERE u.email LIKE '%.sibima.demo26@example.test'
ORDER BY siswa, program;

-- Tutor yang mengajar > 1 program, data nyata dari dataset demo
SELECT u.nama_lengkap AS tutor, COUNT(DISTINCT j.id_program) AS jumlah_program
FROM public.jadwal_kelas j
JOIN public.tutor t ON t.id_pengguna=j.id_tutor
JOIN public.pengguna u ON u.id_pengguna=t.id_pengguna
JOIN public.program_bimbel p ON p.id_program=j.id_program
WHERE j.aktif AND p.kode LIKE 'D26-%'
GROUP BY u.id_pengguna,u.nama_lengkap
HAVING COUNT(DISTINCT j.id_program)>1
ORDER BY jumlah_program DESC,tutor;
