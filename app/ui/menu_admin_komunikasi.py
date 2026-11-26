"""Compatibility entry points for UI-006 communication and audit log."""
from app.ui.admin_reporting import menu_laporan_komunikasi_admin


def menu_pengumuman_admin():
    return menu_laporan_komunikasi_admin('pengumuman')


def menu_log_aktivitas_admin():
    return menu_laporan_komunikasi_admin('log')
