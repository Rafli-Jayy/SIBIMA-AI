-- SIBIMA-AI: lapisan kompatibilitas kueri lama + objek operasional asli.
-- DB tujuan wajib sibima_db. Tidak dijalankan di database SIBIMA lama.
-- 18 tabel fisik berbahasa Indonesia; view Inggris adalah API transisi untuk
-- mempertahankan modul Python lama sambil migrasi bertahap (BUKAN tabel baru).
BEGIN;
SET LOCAL search_path TO public;
DO $$
BEGIN
    IF current_database() <> 'sibima_db' THEN
        RAISE EXCEPTION 'DB tujuan salah. Gunakan sibima_db, bukan %', current_database();
    END IF;
    IF to_regclass('public.pengguna') IS NULL OR to_regclass('public.users') IS NOT NULL THEN
        RAISE EXCEPTION 'Jalankan schema.sql baru lebih dulu pada database sibima_db yang kosong.';
    END IF;
END $$;

CREATE VIEW public.users AS
SELECT
    id_pengguna AS id,
    username,
    email,
    nama_lengkap,
    password_hash,
    role,
    status,
    email_verified,
    failed_attempts,
    locked_until,
    must_change_password,
    id_pengguna_penyetuju AS approved_by,
    approved_at,
    reject_reason,
    last_login,
    created_at
FROM public.pengguna;

CREATE VIEW public.students AS
SELECT
    id_pengguna AS user_id,
    role,
    nis,
    jenjang,
    sekolah,
    no_hp,
    nama_wali
FROM public.siswa;

CREATE VIEW public.tutors AS
SELECT
    id_pengguna AS user_id,
    role,
    kode_tutor,
    keahlian,
    no_hp
FROM public.tutor;

CREATE VIEW public.otp_codes AS
SELECT
    id_otp AS id,
    id_pengguna AS user_id,
    code_hash,
    purpose,
    expires_at,
    attempts,
    used_at,
    created_at
FROM public.kode_otp;

CREATE VIEW public.activity_logs AS
SELECT
    id_log AS id,
    id_pengguna AS user_id,
    aksi,
    detail,
    created_at
FROM public.log_aktivitas;

CREATE VIEW public.programs AS
SELECT
    id_program AS id,
    kode,
    nama,
    jenjang,
    deskripsi,
    harga_bulanan,
    kuota,
    status,
    bobot_tugas,
    bobot_kuis,
    bobot_uts,
    bobot_uas,
    created_at
FROM public.program_bimbel;

CREATE VIEW public.rooms AS
SELECT
    id_ruangan AS id,
    nama,
    kapasitas,
    aktif
FROM public.ruangan;

CREATE VIEW public.schedules AS
SELECT
    id_jadwal AS id,
    id_program AS program_id,
    id_tutor AS tutor_id,
    id_ruangan AS room_id,
    hari,
    jam_mulai,
    jam_selesai,
    aktif,
    notif_monitor_from
FROM public.jadwal_kelas;

CREATE VIEW public.enrollments AS
SELECT
    id_pendaftaran AS id,
    id_siswa AS student_id,
    id_program AS program_id,
    status,
    alasan_tolak,
    id_pengguna_pemroses AS processed_by,
    processed_at,
    created_at
FROM public.pendaftaran;

CREATE VIEW public.class_sessions AS
SELECT
    id_pertemuan AS id,
    id_jadwal AS schedule_id,
    tanggal,
    pertemuan_ke,
    topik,
    ringkasan,
    status,
    created_at,
    alasan_batal,
    selesai_at
FROM public.pertemuan_kelas;

CREATE VIEW public.attendances AS
SELECT
    id_pertemuan AS session_id,
    id_siswa AS student_id,
    status,
    keterangan,
    dicatat_at,
    id_pendaftaran AS enrollment_id
FROM public.kehadiran;

CREATE VIEW public.grades AS
SELECT
    id_nilai AS id,
    id_pendaftaran AS enrollment_id,
    jenis,
    judul,
    nilai,
    tanggal,
    id_tutor_penginput AS input_by,
    created_at
FROM public.nilai;

CREATE VIEW public.invoices AS
SELECT
    id_tagihan AS id,
    no_invoice,
    id_pendaftaran AS enrollment_id,
    periode,
    jumlah,
    jatuh_tempo,
    status,
    created_at
FROM public.tagihan;

CREATE VIEW public.payments AS
SELECT
    id_pembayaran AS id,
    id_tagihan AS invoice_id,
    kode_bayar,
    jumlah,
    status,
    paid_at,
    id_pengguna_pemroses AS processed_by,
    processed_at,
    alasan_tolak,
    created_at
FROM public.pembayaran;

CREATE VIEW public.payment_refunds AS
SELECT
    id_pengembalian AS id,
    id_pembayaran AS payment_id,
    kode_refund,
    jumlah,
    alasan,
    status,
    created_at,
    processed_at
FROM public.pengembalian_pembayaran;

CREATE VIEW public.announcements AS
SELECT
    id_pengumuman AS id,
    judul,
    isi,
    id_pengguna_pembuat AS dibuat_by,
    created_at,
    archived_at,
    id_pengguna_penerima AS penerima_user_id,
    sumber,
    kategori,
    event_key,
    expires_at,
    id_program AS program_id,
    batch_key,
    id_pengguna_aktor AS actor_user_id,
    related_type,
    related_id
FROM public.pengumuman;

CREATE VIEW public.announcement_targets AS
SELECT
    id_pengumuman AS announcement_id,
    target_role
FROM public.target_pengumuman;

CREATE VIEW public.announcement_reads AS
SELECT
    id_pengumuman AS announcement_id,
    id_pengguna AS user_id,
    read_at,
    archived_at
FROM public.pembacaan_pengumuman;

CREATE VIEW public.v_nilai_akhir AS
 WITH rata AS (
         SELECT grades.enrollment_id,
            grades.jenis,
            avg(grades.nilai) AS rata
           FROM public.grades
          GROUP BY grades.enrollment_id, grades.jenis
        ), pivot AS (
         SELECT rata.enrollment_id,
            max(rata.rata) FILTER (WHERE (rata.jenis = 'tugas'::public.grade_type)) AS tugas,
            max(rata.rata) FILTER (WHERE (rata.jenis = 'kuis'::public.grade_type)) AS kuis,
            max(rata.rata) FILTER (WHERE (rata.jenis = 'uts'::public.grade_type)) AS uts,
            max(rata.rata) FILTER (WHERE (rata.jenis = 'uas'::public.grade_type)) AS uas
           FROM rata
          GROUP BY rata.enrollment_id
        )
 SELECT e.id AS enrollment_id,
    e.student_id,
    e.program_id,
    round(pv.tugas, 2) AS tugas,
    round(pv.kuis, 2) AS kuis,
    round(pv.uts, 2) AS uts,
    round(pv.uas, 2) AS uas,
    round(((((COALESCE((pv.tugas * (p.bobot_tugas)::numeric), (0)::numeric) + COALESCE((pv.kuis * (p.bobot_kuis)::numeric), (0)::numeric)) + COALESCE((pv.uts * (p.bobot_uts)::numeric), (0)::numeric)) + COALESCE((pv.uas * (p.bobot_uas)::numeric), (0)::numeric)) / (NULLIF((((
        CASE
            WHEN (pv.tugas IS NOT NULL) THEN (p.bobot_tugas)::integer
            ELSE 0
        END +
        CASE
            WHEN (pv.kuis IS NOT NULL) THEN (p.bobot_kuis)::integer
            ELSE 0
        END) +
        CASE
            WHEN (pv.uts IS NOT NULL) THEN (p.bobot_uts)::integer
            ELSE 0
        END) +
        CASE
            WHEN (pv.uas IS NOT NULL) THEN (p.bobot_uas)::integer
            ELSE 0
        END), 0))::numeric), 2) AS nilai_akhir
   FROM ((public.enrollments e
     JOIN public.programs p ON ((p.id = e.program_id)))
     LEFT JOIN pivot pv ON ((pv.enrollment_id = e.id)));

CREATE VIEW public.v_pemasukan_bulanan AS
 SELECT (date_trunc('month'::text, paid_at))::date AS bulan,
    count(*) AS jumlah_transaksi,
    sum(jumlah) AS total_pemasukan
   FROM public.payments
  WHERE (status = 'lunas'::public.payment_status)
  GROUP BY ((date_trunc('month'::text, paid_at))::date);

CREATE VIEW public.v_program_kuota AS
SELECT
    NULL::integer AS program_id,
    NULL::character varying(10) AS kode,
    NULL::character varying(100) AS nama,
    NULL::smallint AS kuota,
    NULL::bigint AS terisi,
    NULL::bigint AS sisa;

CREATE VIEW public.v_rekap_kehadiran AS
 SELECT e.student_id,
    e.program_id,
    r.total_pertemuan,
    r.hadir,
    r.izin,
    r.sakit,
    r.alpa,
    r.persen_hadir,
    e.id AS enrollment_id,
    (e.status)::text AS status_enrollment,
    (e.created_at)::date AS tanggal_pendaftaran
   FROM (public.enrollments e
     CROSS JOIN LATERAL ( SELECT count(*) AS total_pertemuan,
            count(*) FILTER (WHERE (a.status = 'H'::public.attendance_status)) AS hadir,
            count(*) FILTER (WHERE (a.status = 'I'::public.attendance_status)) AS izin,
            count(*) FILTER (WHERE (a.status = 'S'::public.attendance_status)) AS sakit,
            count(*) FILTER (WHERE (a.status = 'A'::public.attendance_status)) AS alpa,
            round(((100.0 * (count(*) FILTER (WHERE (a.status = 'H'::public.attendance_status)))::numeric) / (NULLIF(count(*), 0))::numeric), 1) AS persen_hadir
           FROM ((public.attendances a
             JOIN public.class_sessions cs ON (((cs.id = a.session_id) AND (cs.status = 'selesai'::public.session_status))))
             JOIN public.schedules s ON (((s.id = cs.schedule_id) AND (s.program_id = e.program_id))))
          WHERE ((a.enrollment_id = e.id) AND (a.student_id = e.student_id))) r)
  WHERE (e.status = ANY (ARRAY['aktif'::public.enrollment_status, 'selesai'::public.enrollment_status, 'batal'::public.enrollment_status]));

CREATE VIEW public.v_tagihan_status AS
SELECT
    NULL::integer AS invoice_id,
    NULL::character varying(30) AS no_invoice,
    NULL::integer AS enrollment_id,
    NULL::integer AS student_id,
    NULL::date AS periode,
    NULL::date AS jatuh_tempo,
    NULL::public.invoice_status AS status,
    NULL::numeric(12,2) AS jumlah,
    NULL::numeric(12,2) AS total_tagihan,
    NULL::numeric AS terbayar;

CREATE OR REPLACE VIEW public.v_program_kuota AS
 SELECT p.id AS program_id,
    p.kode,
    p.nama,
    p.kuota,
    count(e.id) FILTER (WHERE (e.status = ANY (ARRAY['menunggu_pembayaran'::public.enrollment_status, 'menunggu'::public.enrollment_status, 'aktif'::public.enrollment_status]))) AS terisi,
    (p.kuota - count(e.id) FILTER (WHERE (e.status = ANY (ARRAY['menunggu_pembayaran'::public.enrollment_status, 'menunggu'::public.enrollment_status, 'aktif'::public.enrollment_status])))) AS sisa
   FROM (public.programs p
     LEFT JOIN public.enrollments e ON ((e.program_id = p.id)))
  GROUP BY p.id, p.kode, p.nama, p.kuota;

CREATE OR REPLACE VIEW public.v_tagihan_status AS
 SELECT i.id AS invoice_id,
    i.no_invoice,
    i.enrollment_id,
    e.student_id,
    i.periode,
    i.jatuh_tempo,
    i.status,
    i.jumlah,
    i.jumlah AS total_tagihan,
    COALESCE(sum(p.jumlah) FILTER (WHERE (p.status = 'lunas'::public.payment_status)), (0)::numeric) AS terbayar
   FROM ((public.invoices i
     JOIN public.enrollments e ON ((e.id = i.enrollment_id)))
     LEFT JOIN public.payments p ON ((p.invoice_id = i.id)))
  GROUP BY i.id, i.no_invoice, i.enrollment_id, i.periode, i.jatuh_tempo, i.status, i.jumlah, e.student_id;

CREATE SEQUENCE public.kode_tutor_seq START WITH 1;
CREATE SEQUENCE public.nis_seq START WITH 1;
-- tagihan.no_invoice uses original-style formatting from buat_nomor_invoice().
-- Function compatibility: no extra invoice sequence needed.
CREATE FUNCTION public.fn_next_invoice() RETURNS text
LANGUAGE sql VOLATILE AS $$ SELECT public.buat_nomor_invoice() $$;

CREATE FUNCTION public.fn_next_kode_tutor() RETURNS text
    LANGUAGE sql
    AS $$
    SELECT 'T-' || lpad(nextval('kode_tutor_seq')::text, 3, '0');
$$;

CREATE FUNCTION public.fn_next_nis() RETURNS text
    LANGUAGE sql
    AS $$
    SELECT 'S-' || lpad(nextval('nis_seq')::text, 4, '0');
$$;

CREATE FUNCTION public.fn_validate_full_payment() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    nominal_tagihan NUMERIC(12,2);
BEGIN
    SELECT jumlah INTO nominal_tagihan
    FROM invoices
    WHERE id = NEW.id_tagihan;

    IF nominal_tagihan IS NULL THEN
        RAISE EXCEPTION 'Tagihan % tidak ditemukan.', NEW.id_tagihan;
    END IF;
    IF NEW.jumlah <> nominal_tagihan THEN
        RAISE EXCEPTION 'Pembayaran harus penuh sebesar %.', nominal_tagihan;
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION public.sibima_n1_emit(target_id integer, category_name text, unique_event_key text, notification_title text, notification_body text, actor_id integer DEFAULT NULL::integer) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE author_id integer; real_actor integer;
BEGIN
  IF target_id IS NULL OR unique_event_key IS NULL THEN RETURN; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.users WHERE id=target_id) THEN RETURN; END IF;
  real_actor := NULL;
  IF actor_id IS NOT NULL AND actor_id <> target_id
    AND EXISTS (SELECT 1 FROM public.users WHERE id=actor_id)
  THEN real_actor := actor_id; END IF;
  author_id := COALESCE(real_actor,target_id);
  INSERT INTO public.pengumuman
    (judul,isi,id_pengguna_pembuat,id_pengguna_penerima,sumber,kategori,event_key,id_pengguna_aktor)
  VALUES (left(notification_title,150),left(notification_body,4000),author_id,
          target_id,'sistem',category_name,unique_event_key,real_actor)
  ON CONFLICT DO NOTHING;
END $$;

CREATE FUNCTION public.sibima_n1_enrollment_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE program_name text;
BEGIN
  SELECT p.nama INTO program_name FROM public.programs p WHERE p.id = NEW.id_program;
  program_name := coalesce(program_name, 'program bimbel');
  IF TG_OP = 'INSERT' THEN
    IF NEW.status::text IN ('menunggu_pembayaran', 'menunggu') THEN
      PERFORM public.sibima_n1_emit(NEW.id_siswa, 'pendaftaran', 'n1:enrollment:dibuat:' || NEW.id_pendaftaran,
        'Pendaftaran Kelas Tercatat',
        'Pendaftaran ' || program_name || ' tercatat. Status: ' ||
        CASE WHEN NEW.status::text = 'menunggu_pembayaran' THEN 'menunggu pembayaran pertama.'
             ELSE 'menunggu persetujuan Admin.' END,
        NEW.id_siswa);
    END IF;
  ELSIF OLD.status IS DISTINCT FROM NEW.status THEN
    IF NEW.status::text = 'aktif' AND OLD.status::text = 'menunggu' THEN
      PERFORM public.sibima_n1_emit(NEW.id_siswa, 'pendaftaran', 'n1:enrollment:aktif:' || NEW.id_pendaftaran,
        'Kelas Disetujui dan Aktif',
        'Pendaftaran ' || program_name || ' telah disetujui Admin. Kelas sekarang aktif.',
        NEW.id_pengguna_pemroses);
    ELSIF NEW.status::text = 'ditolak' THEN
      PERFORM public.sibima_n1_emit(NEW.id_siswa, 'pendaftaran', 'n1:enrollment:ditolak:' || NEW.id_pendaftaran,
        'Pendaftaran Kelas Ditolak',
        'Pendaftaran ' || program_name || ' ditolak. ' ||
          CASE WHEN NEW.alasan_tolak IS NOT NULL AND btrim(NEW.alasan_tolak) <> ''
               THEN 'Alasan: ' || left(NEW.alasan_tolak, 1000)
               ELSE 'Silakan hubungi Admin untuk informasi.' END,
        NEW.id_pengguna_pemroses);
    END IF;
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION public.sibima_n1_invoices_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE student_id integer; program_name text;
BEGIN
  SELECT e.student_id, p.nama INTO student_id, program_name
  FROM public.enrollments e JOIN public.programs p ON p.id = e.program_id
  WHERE e.id = NEW.id_pendaftaran;
  PERFORM public.sibima_n1_emit(student_id, 'tagihan', 'n1:invoice:dibuat:' || NEW.id_tagihan,
    'Tagihan Baru Diterbitkan',
    'Invoice ' || NEW.no_invoice || ' untuk ' || coalesce(program_name, 'program bimbel') ||
    ' tersedia. Periksa nominal dan tanggal jatuh tempo melalui menu Tagihan dan Pembayaran.',
    student_id);
  RETURN NEW;
END $$;

CREATE FUNCTION public.sibima_n1_payments_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE student_id integer; invoice_code text; title_text text; body_text text;
BEGIN
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM NEW.status THEN RETURN NEW; END IF;
  IF NEW.status::text NOT IN ('lunas', 'gagal', 'ditolak') THEN RETURN NEW; END IF;
  SELECT e.student_id, i.no_invoice INTO student_id, invoice_code
  FROM public.invoices i JOIN public.enrollments e ON e.id = i.enrollment_id
  WHERE i.id = NEW.id_tagihan;
  IF NEW.status::text = 'lunas' THEN
    title_text := 'Pembayaran Simulasi Berhasil';
    body_text := 'Pembayaran simulasi untuk invoice ' || invoice_code ||
      ' berhasil tercatat. Jika pendaftaran masih menunggu Admin, akses kelas belum aktif.';
  ELSE
    title_text := 'Pembayaran Tidak Berhasil';
    body_text := 'Pembayaran simulasi untuk invoice ' || invoice_code ||
      ' tidak berhasil. Periksa menu Tagihan dan Pembayaran untuk melanjutkan.';
  END IF;
  PERFORM public.sibima_n1_emit(student_id, 'tagihan',
     'n1:payment:' || NEW.status::text || ':' || NEW.id_pembayaran,
     title_text, body_text, student_id);
  RETURN NEW;
END $$;

CREATE FUNCTION public.sibima_n1_users_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
  IF NEW.status::text = 'aktif' AND OLD.status::text = 'menunggu_konfirmasi'
     AND NEW.role::text IN ('siswa', 'tutor') THEN
    PERFORM public.sibima_n1_emit(NEW.id_pengguna, 'akun', 'n1:akun:aktif:' || NEW.id_pengguna,
      'Akun SIBIMA Disetujui',
      'Akun kamu telah disetujui Admin dan sudah aktif. Silakan masuk ke SIBIMA untuk melihat layanan yang tersedia.',
      NEW.id_pengguna_penyetuju);
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION public.sibima_n2_attendance_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE st record; nama_status text;
BEGIN
 IF OLD.status IS NOT DISTINCT FROM NEW.status THEN RETURN NEW; END IF;
 SELECT cs.id AS sid,cs.pertemuan_ke,cs.tanggal,s.program_id,s.tutor_id,p.nama AS nama_program
 INTO st FROM public.class_sessions cs JOIN public.schedules s ON s.id=cs.schedule_id
 JOIN public.programs p ON p.id=s.program_id
 WHERE cs.id=NEW.id_pertemuan AND cs.status::text='selesai';
 IF st IS NULL THEN RETURN NEW; END IF;
 nama_status := CASE NEW.status::text WHEN 'H' THEN 'Hadir' WHEN 'I' THEN 'Izin'
                  WHEN 'S' THEN 'Sakit' WHEN 'A' THEN 'Alpa' ELSE NEW.status::text END;
 PERFORM public.sibima_n2_emit(NEW.id_siswa,'absensi',
   'n2:attendance:correction:'||NEW.id_pertemuan||':'||NEW.id_siswa||':'||txid_current()::text,
   'Koreksi Absensi: '||nama_status,
   'Absensi '||st.nama_program||' tanggal '||st.tanggal::text||
   ' diperbarui menjadi '||nama_status||'.',st.tutor_id,st.program_id,'session',NEW.id_pertemuan);
 RETURN NEW;
END $$;

CREATE FUNCTION public.sibima_n2_emit(target_id integer, category_name text, unique_event_key text, notification_title text, notification_body text, actor_id integer DEFAULT NULL::integer, program_ref integer DEFAULT NULL::integer, ref_type text DEFAULT NULL::text, ref_id integer DEFAULT NULL::integer) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE author_id integer; valid_actor integer;
BEGIN
 IF target_id IS NULL OR unique_event_key IS NULL OR notification_title IS NULL THEN RETURN; END IF;
 IF NOT EXISTS (SELECT 1 FROM public.users WHERE id=target_id) THEN RETURN; END IF;
 valid_actor := NULL;
 IF actor_id IS NOT NULL AND EXISTS (SELECT 1 FROM public.users WHERE id=actor_id) THEN
   valid_actor := actor_id;
 END IF;
 author_id := COALESCE(valid_actor,target_id);
 INSERT INTO public.pengumuman
   (judul,isi,id_pengguna_pembuat,id_pengguna_penerima,sumber,kategori,event_key,
    id_pengguna_aktor,id_program,related_type,related_id)
 VALUES (left(notification_title,150),left(notification_body,4000),author_id,
         target_id,'sistem',left(category_name,30),unique_event_key,
         valid_actor,program_ref,left(ref_type,30),ref_id)
 ON CONFLICT DO NOTHING;
END $$;

CREATE FUNCTION public.sibima_n2_grade_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE sid integer; pid integer; pname text; title_text text; body_text text; key_text text;
BEGIN
 IF TG_OP='UPDATE' THEN
   IF (OLD.nilai,OLD.jenis,OLD.judul,OLD.tanggal)
       IS NOT DISTINCT FROM (NEW.nilai,NEW.jenis,NEW.judul,NEW.tanggal) THEN RETURN NEW; END IF;
 END IF;
 SELECT e.student_id,e.program_id,p.nama INTO sid,pid,pname
 FROM public.enrollments e JOIN public.programs p ON p.id=e.program_id WHERE e.id=NEW.id_pendaftaran;
 IF sid IS NULL THEN RETURN NEW; END IF;
 title_text := CASE WHEN TG_OP='INSERT' THEN 'Nilai Baru Diterbitkan' ELSE 'Nilai Diperbarui' END;
 body_text := 'Nilai ' || upper(NEW.jenis::text) || ' - ' || coalesce(nullif(btrim(NEW.judul),''),'Penilaian') ||
   ' untuk ' || coalesce(pname,'kelas') || ': ' || NEW.nilai::text || '/100.';
 IF TG_OP='UPDATE' THEN body_text := body_text || ' Nilai sebelumnya: ' || OLD.nilai::text || '/100.'; END IF;
 key_text := CASE WHEN TG_OP='INSERT' THEN 'n2:grade:new:' || NEW.id_nilai
                  ELSE 'n2:grade:edit:' || NEW.id_nilai || ':' || txid_current()::text END;
 PERFORM public.sibima_n2_emit(sid,'nilai',key_text,title_text,body_text,
   NEW.id_tutor_penginput,pid,'grade',NEW.id_nilai);
 RETURN NEW;
END $$;

CREATE FUNCTION public.sibima_n2_schedule_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE target_row record; pname text; notes text;
BEGIN
 IF (OLD.id_program,OLD.id_tutor,OLD.hari,OLD.jam_mulai,OLD.jam_selesai,OLD.id_ruangan,OLD.aktif)
   IS NOT DISTINCT FROM
    (NEW.id_program,NEW.id_tutor,NEW.hari,NEW.jam_mulai,NEW.jam_selesai,NEW.id_ruangan,NEW.aktif)
 THEN RETURN NEW; END IF;
 SELECT nama INTO pname FROM public.programs WHERE id=NEW.id_program;
 notes := 'Jadwal '||coalesce(pname,'kelas')||' diperbarui. Hari: '||NEW.hari::text||
   ', jam: '||NEW.jam_mulai::text||'â€“'||NEW.jam_selesai::text||
   '. Status: '||CASE WHEN NEW.aktif THEN 'aktif' ELSE 'nonaktif' END||
   '. Periksa menu Jadwal untuk detail terkini.';
 UPDATE public.announcements SET expires_at=now()
 WHERE related_type='schedule' AND related_id=NEW.id_jadwal AND kategori='jadwal'
   AND event_key LIKE ('n2:jadwal:'||NEW.id_jadwal||':%')
   AND (expires_at IS NULL OR expires_at > now());
 FOR target_row IN
    SELECT DISTINCT student_id AS uid FROM public.enrollments
    WHERE program_id IN (OLD.id_program,NEW.id_program) AND status::text='aktif'
    UNION SELECT OLD.id_tutor AS uid UNION SELECT NEW.id_tutor AS uid
 LOOP
  PERFORM public.sibima_n2_emit(target_row.uid,'jadwal',
    'n2:schedule:changed:'||NEW.id_jadwal||':'||txid_current()::text||':'||target_row.uid,
    'Perubahan Jadwal Kelas',notes,NULL,NEW.id_program,'schedule',NEW.id_jadwal);
 END LOOP;
 RETURN NEW;
END $$;

CREATE FUNCTION public.sibima_n2_session_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE schedule_row record; a record; student_row record;
DECLARE nama_status text; body_text text;
BEGIN
 IF OLD.status IS NOT DISTINCT FROM NEW.status OR NEW.status::text NOT IN ('selesai','batal') THEN RETURN NEW; END IF;
 SELECT s.id AS schedule_id,s.program_id,s.tutor_id,p.nama AS nama_program
 INTO schedule_row FROM public.schedules s JOIN public.programs p ON p.id=s.program_id
 WHERE s.id=NEW.id_jadwal;
 IF schedule_row IS NULL THEN RETURN NEW; END IF;
 -- Pengingat jadwal hari itu tidak boleh tampak aktif setelah sesi final/batal.
 UPDATE public.announcements SET expires_at=now()
  WHERE sumber='sistem' AND kategori='jadwal'
   AND related_type='schedule' AND related_id=NEW.id_jadwal
   AND event_key LIKE ('n2:jadwal:'||NEW.id_jadwal||':'||NEW.tanggal::text||':%')
   AND (expires_at IS NULL OR expires_at > now());
 IF NEW.status::text='batal' THEN
  FOR student_row IN SELECT DISTINCT e.student_id FROM public.enrollments e
      WHERE e.program_id=schedule_row.program_id
        AND e.status::text='aktif'
        AND COALESCE(e.processed_at::date,e.created_at::date)<=NEW.tanggal
  LOOP
   PERFORM public.sibima_n2_emit(student_row.student_id,'jadwal',
    'n2:session:cancel:'||NEW.id_pertemuan||':'||student_row.student_id,
    'Pertemuan Dibatalkan',
    'Pertemuan '||schedule_row.nama_program||' tanggal '||NEW.tanggal::text||
      ' dibatalkan. Alasan: '||coalesce(nullif(NEW.alasan_batal,''),'Tidak dicantumkan.'),
    schedule_row.tutor_id,schedule_row.program_id,'session',NEW.id_pertemuan);
  END LOOP;
 ELSE
  FOR a IN SELECT student_id,status::text AS status_absen FROM public.attendances
    WHERE session_id=NEW.id_pertemuan
  LOOP
   nama_status := CASE a.status_absen WHEN 'H' THEN 'Hadir' WHEN 'I' THEN 'Izin'
                  WHEN 'S' THEN 'Sakit' WHEN 'A' THEN 'Alpa' ELSE a.status_absen END;
   body_text := 'Absensi '||schedule_row.nama_program||' pertemuan ke-'||NEW.pertemuan_ke::text||
      ' ('||NEW.tanggal::text||') telah difinalisasi. Status kamu: '||nama_status||'.';
   PERFORM public.sibima_n2_emit(a.student_id,'absensi',
     'n2:attendance:final:'||NEW.id_pertemuan||':'||a.student_id,
     'Hasil Absensi: '||nama_status,body_text,
     schedule_row.tutor_id,schedule_row.program_id,'session',NEW.id_pertemuan);
  END LOOP;
 END IF;
 RETURN NEW;
END $$;

CREATE TRIGGER sibima_n1_enroll_insert AFTER INSERT ON public.pendaftaran FOR EACH ROW EXECUTE FUNCTION public.sibima_n1_enrollment_trigger();

CREATE TRIGGER sibima_n1_enroll_update AFTER UPDATE OF status ON public.pendaftaran FOR EACH ROW WHEN ((old.status IS DISTINCT FROM new.status)) EXECUTE FUNCTION public.sibima_n1_enrollment_trigger();

CREATE TRIGGER sibima_n1_invoice_insert AFTER INSERT ON public.tagihan FOR EACH ROW EXECUTE FUNCTION public.sibima_n1_invoices_trigger();

CREATE TRIGGER sibima_n1_payment_insert AFTER INSERT ON public.pembayaran FOR EACH ROW EXECUTE FUNCTION public.sibima_n1_payments_trigger();

CREATE TRIGGER sibima_n1_payment_update AFTER UPDATE OF status ON public.pembayaran FOR EACH ROW WHEN ((old.status IS DISTINCT FROM new.status)) EXECUTE FUNCTION public.sibima_n1_payments_trigger();

CREATE TRIGGER sibima_n1_users_after_update AFTER UPDATE OF status ON public.pengguna FOR EACH ROW WHEN ((old.status IS DISTINCT FROM new.status)) EXECUTE FUNCTION public.sibima_n1_users_trigger();

CREATE TRIGGER sibima_n2_attendance_updated AFTER UPDATE ON public.kehadiran FOR EACH ROW EXECUTE FUNCTION public.sibima_n2_attendance_trigger();

CREATE TRIGGER sibima_n2_grade_insert AFTER INSERT ON public.nilai FOR EACH ROW EXECUTE FUNCTION public.sibima_n2_grade_trigger();

CREATE TRIGGER sibima_n2_grade_update AFTER UPDATE ON public.nilai FOR EACH ROW EXECUTE FUNCTION public.sibima_n2_grade_trigger();

CREATE TRIGGER sibima_n2_schedule_changed AFTER UPDATE OF id_program, id_tutor, hari, jam_mulai, jam_selesai, id_ruangan, aktif ON public.jadwal_kelas FOR EACH ROW EXECUTE FUNCTION public.sibima_n2_schedule_trigger();

CREATE TRIGGER sibima_n2_session_finished AFTER UPDATE OF status ON public.pertemuan_kelas FOR EACH ROW EXECUTE FUNCTION public.sibima_n2_session_trigger();

CREATE TRIGGER trg_validate_full_payment BEFORE INSERT OR UPDATE OF id_tagihan, jumlah ON public.pembayaran FOR EACH ROW EXECUTE FUNCTION public.fn_validate_full_payment();

COMMIT;
