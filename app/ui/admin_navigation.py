"""Definisi navigasi Admin; kode modul lama tetap dipertahankan."""

# Seluruh kode modul Admin lama wajib tetap dapat diakses.
KELOMPOK_MENU = (
    ("Prioritas", (("Pusat Konfirmasi", "konfirmasi"),
                   ("Pendaftaran", "pendaftaran"),
                   ("Pembayaran", "pembayaran"))),
    ("Data Pengguna", (("Manajemen Akun", "akun"),
                       ("Data Siswa", "siswa"),
                       ("Data Tutor", "tutor"))),
    ("Akademik", (("Program dan Ruang", "program"),
                  ("Jadwal", "jadwal"))),
    ("Laporan & Komunikasi", (("Laporan", "laporan"),
                             ("Komunikasi", "pengumuman"),
                             ("Log Aktivitas", "log"),
                             ("SIBIMA-AI", "ai"))),
)
