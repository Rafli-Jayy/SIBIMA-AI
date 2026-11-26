"""Compatibility entry point for UI-006 reporting."""
from app.ui.admin_reporting import menu_laporan_komunikasi_admin


def menu_laporan_admin():
    return menu_laporan_komunikasi_admin('laporan')
