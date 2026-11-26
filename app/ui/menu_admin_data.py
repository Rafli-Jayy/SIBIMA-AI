"""Entry points for the integrated Data Pengguna workspace."""

from app.ui.admin_users import menu_data_pengguna_admin


def menu_manajemen_akun_admin():
    return menu_data_pengguna_admin('akun')


def menu_data_siswa_admin():
    return menu_data_pengguna_admin('siswa')


def menu_data_tutor_admin():
    return menu_data_pengguna_admin('tutor')
