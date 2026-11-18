-- Jalankan psql -U postgres -d sibima_db -f sql/04_validasi.sql
-- Semua perintah SELECT saja.
SELECT current_database() AS database_saat_ini;
SELECT COUNT(*) AS tabel_fisik_berbahasa_indonesia
  FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relkind IN ('r','p')
    AND c.relname IN ('pengguna','siswa','tutor','kode_otp','log_aktivitas',
      'program_bimbel','ruangan','jadwal_kelas','pendaftaran','pertemuan_kelas',
      'kehadiran','nilai','tagihan','pembayaran','pengembalian_pembayaran',
      'pengumuman','target_pengumuman','pembacaan_pengumuman');
SELECT COUNT(*) AS atribut_tabel_fisik
  FROM information_schema.columns c JOIN pg_catalog.pg_class t
    ON t.relname=c.table_name JOIN pg_catalog.pg_namespace n
    ON n.oid=t.relnamespace AND n.nspname=c.table_schema
  WHERE c.table_schema='public' AND t.relkind IN ('r','p')
    AND c.table_name IN ('pengguna','siswa','tutor','kode_otp','log_aktivitas',
      'program_bimbel','ruangan','jadwal_kelas','pendaftaran','pertemuan_kelas',
      'kehadiran','nilai','tagihan','pembayaran','pengembalian_pembayaran',
      'pengumuman','target_pengumuman','pembacaan_pengumuman');
SELECT COUNT(*) AS foreign_key
  FROM pg_catalog.pg_constraint k JOIN pg_catalog.pg_class t ON t.oid=k.conrelid
  JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
  WHERE n.nspname='public' AND k.contype='f'
    AND t.relname IN ('pengguna','siswa','tutor','kode_otp','log_aktivitas',
      'program_bimbel','ruangan','jadwal_kelas','pendaftaran','pertemuan_kelas',
      'kehadiran','nilai','tagihan','pembayaran','pengembalian_pembayaran',
      'pengumuman','target_pengumuman','pembacaan_pengumuman');
SELECT COUNT(*) AS kompatibilitas_view
  FROM pg_catalog.pg_views WHERE schemaname='public'
    AND viewname IN ('users','students','tutors','otp_codes','activity_logs',
      'programs','rooms','schedules','enrollments','class_sessions','attendances',
      'grades','invoices','payments','payment_refunds','announcements',
      'announcement_targets','announcement_reads');
SELECT COUNT(*) AS view_laporan
  FROM pg_catalog.pg_views WHERE schemaname='public'
    AND viewname IN ('v_nilai_akhir','v_pemasukan_bulanan',
      'v_program_kuota','v_rekap_kehadiran','v_tagihan_status');
SELECT COUNT(*) AS trigger_bisnis
  FROM pg_catalog.pg_trigger g
  JOIN pg_catalog.pg_class t ON t.oid=g.tgrelid
  JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
  WHERE n.nspname='public' AND NOT g.tgisinternal;
-- Pastikan query lama melalui VIEW updatable dan menampilkan kolom lama.
SELECT table_name, column_name
 FROM information_schema.columns
 WHERE table_schema='public' AND table_name IN ('pengguna','users')
   AND column_name IN ('id','id_pengguna','username')
 ORDER BY table_name, column_name;
