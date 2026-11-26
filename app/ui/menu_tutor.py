"""Dashboard dan navigasi Tutor UI-008."""
from app import session
from app.ui.console import bersihkan_layar, gagal, sukses
from app.ui.tutor_workspace import TutorDashboardNavigator
from app.ui import tutor_academic, tutor_communication


def jalankan():
    navigator=TutorDashboardNavigator()
    while True:
        pengguna=session.get_user()
        if not pengguna or pengguna.get('role')!='tutor':
            gagal('Akses ditolak. Silakan login menggunakan akun tutor.')
            return
        pilihan=navigator.run(pengguna)
        if pilihan=='refresh':
            continue
        if pilihan is None or pilihan=='logout':
            session.logout()
            bersihkan_layar()
            sukses('Logout berhasil. Sesi telah ditutup.')
            try:
                input('\nTekan Enter untuk kembali ke menu utama...')
            except (EOFError,KeyboardInterrupt):
                pass
            return
        if pilihan == "ai":
            from app.services.ai_service import buka_ai
            buka_ai("tutor")
        elif pilihan=='notifikasi':
            tujuan=tutor_communication.notifikasi()
            if tujuan=='tertunda':
                tutor_communication.tertunda()
            elif tujuan:
                tutor_academic.jalankan_modul(tujuan)
        elif pilihan=='pengumuman_tutor':
            tutor_communication.pengumuman()
        elif pilihan=='tertunda':
            tutor_communication.tertunda()
        else:
            tutor_academic.jalankan_modul(pilihan)
