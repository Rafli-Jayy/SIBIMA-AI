-- Data awal DEMO saja, tanpa akun atau informasi pribadi.
-- Hanya jalankan pada database sibima_db yang sudah memiliki schema lengkap.
BEGIN;
DO $$ BEGIN
    IF current_database() <> 'sibima_db' THEN
        RAISE EXCEPTION 'DB tujuan wajib sibima_db.';
    END IF;
END $$;
INSERT INTO public.ruangan(nama, kapasitas, aktif)
VALUES ('Ruang Demo 1',20,TRUE),('Ruang Demo 2',12,TRUE)
ON CONFLICT (nama) DO NOTHING;
INSERT INTO public.program_bimbel
(kode,nama,jenjang,deskripsi,harga_bulanan,kuota,status,bobot_tugas,bobot_kuis,bobot_uts,bobot_uas)
VALUES
('MAT-SMP','Matematika SMP','SMP','Program contoh untuk pengujian.',150000,20,'buka',30,20,20,30),
('ING-SMP','Bahasa Inggris SMP','SMP','Program contoh untuk pengujian.',175000,20,'buka',30,20,20,30),
('IPA-SMA','IPA SMA','SMA','Program contoh untuk pengujian.',200000,15,'buka',30,20,20,30)
ON CONFLICT (kode) DO NOTHING;
COMMIT;
