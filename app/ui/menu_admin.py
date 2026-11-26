"""Dashboard admin dan Pusat Konfirmasi akun SIBIMA."""

from rich.align import Align
from rich.panel import Panel

from app import session
from app.ui import (
    menu_admin_data, menu_pembayaran, menu_admin_laporan, menu_admin_komunikasi,
)
from app.ui.console import (
    console,
    bersihkan_layar,
    peringatan,
    sukses,
)
from app.ui.admin_workspace import AdminDashboardNavigator


MENU_ADMIN = [
    ("Pusat Konfirmasi", "konfirmasi"),
    ("Manajemen Akun", "akun"),
    ("Data Siswa", "siswa"),
    ("Data Tutor", "tutor"),
    ("Program dan Ruang", "program"),
    ("Pendaftaran", "pendaftaran"),
    ("Jadwal", "jadwal"),
    ("Pembayaran", "pembayaran"),
    ("Laporan", "laporan"),
    ("Komunikasi", "pengumuman"),
    ("Log Aktivitas", "log"),
]


def _tampilkan_header(halaman: str, subtitle: str):
    console.print(
        Panel(
            Align.center(
                f"[bold cyan]S I B I M A[/bold cyan]\n"
                f"[bold white]{halaman.upper()}[/bold white]\n"
                f"[dim]{subtitle}[/dim]"
            ),
            border_style="cyan",
            padding=(1, 4),
            expand=True,
        )
    )


def menu_konfirmasi():
    """UI-003A: workspace konfirmasi, kembali ke Prioritas saat keluar."""
    from app.ui.admin_confirmation import menu_konfirmasi as buka_konfirmasi
    return buka_konfirmasi()


def _tampilkan_modul_belum_tersedia(nama_modul: str):
    bersihkan_layar()
    _tampilkan_header("Modul Admin", nama_modul)
    console.print(
        Panel(
            f"[bold yellow]{nama_modul}[/bold yellow]\n\n"
            "[white]Modul ini masih dalam tahap pengembangan.[/white]\n"
            "[dim]Belum ada operasi bisnis yang dijalankan dari halaman ini.[/dim]",
            border_style="yellow",
            padding=(1, 3),
            expand=True,
        )
    )
    input("Tekan Enter untuk kembali ke dashboard...")



def menu_program_ruang():
    """UI-005 compatibility entry point."""
    from app.ui.admin_academic import menu_akademik_admin
    return menu_akademik_admin('program')


def menu_jadwal_admin():
    """UI-005 compatibility entry point."""
    from app.ui.admin_academic import menu_akademik_admin
    return menu_akademik_admin('jadwal')


def menu_pendaftaran_admin():
    """UI-003B: workspace pendaftaran; service lama tetap memproses keputusan."""
    from app.ui.admin_enrollment import menu_pendaftaran_admin as buka_pendaftaran
    return buka_pendaftaran()


def jalankan():
    """Dashboard admin SIBIMA."""
    navigator = AdminDashboardNavigator(integrated_priority=True, integrated_data=True, integrated_academic=True, integrated_reporting=True)
    while True:
        if not session.punya_role("admin"):
            peringatan("Akses dashboard ditolak. Silakan login sebagai admin.")
            return

        bersihkan_layar()
        pengguna = session.get_user() or {}
        nama = pengguna.get("nama_lengkap") or pengguna.get("username") or "Admin"

        # UI-002: workspace selesai sebelum submenu lama atau AI dibuka.
        pilihan = navigator.choose(nama)

        if pilihan == "dashboard":
            continue

        if pilihan is None or pilihan == "logout":
            session.logout()
            sukses("Logout berhasil. Sesi telah ditutup.")
            return

        if pilihan == "laporan_komunikasi":
            from app.ui.admin_reporting import menu_laporan_komunikasi_admin
            pilihan = menu_laporan_komunikasi_admin()
            if pilihan != "ai" or not session.punya_role("admin"):
                continue

        if pilihan == "ai":
            from app.services.ai_service import buka_ai
            buka_ai("admin")
            continue

        if pilihan == "prioritas":
            from app.ui.admin_priority import menu_prioritas_admin
            menu_prioritas_admin(previous=navigator.previous)
            continue

        if pilihan == "konfirmasi":
            menu_konfirmasi()
            continue
        if pilihan == "akademik":
            from app.ui.admin_academic import menu_akademik_admin
            menu_akademik_admin()
            continue
        if pilihan == "program":
            menu_program_ruang()
            continue
        if pilihan == "pendaftaran":
            menu_pendaftaran_admin()
            continue
        if pilihan == "data_pengguna":
            menu_admin_data.menu_data_pengguna_admin()
            continue
        if pilihan == "akun":
            menu_admin_data.menu_manajemen_akun_admin()
            continue
        if pilihan == "siswa":
            menu_admin_data.menu_data_siswa_admin()
            continue
        if pilihan == "tutor":
            menu_admin_data.menu_data_tutor_admin()
            continue
        if pilihan == "jadwal":
            menu_jadwal_admin()
            continue
        if pilihan == "pembayaran":
            menu_pembayaran.menu_pembayaran_admin()
            continue
        if pilihan == "laporan":
            menu_admin_laporan.menu_laporan_admin()
            continue
        if pilihan == "pengumuman":
            menu_admin_komunikasi.menu_pengumuman_admin()
            continue
        if pilihan == "log":
            menu_admin_komunikasi.menu_log_aktivitas_admin()
            continue

        label = next(
            (teks for teks, kode in MENU_ADMIN if kode == pilihan),
            pilihan,
        )
        _tampilkan_modul_belum_tersedia(label)
