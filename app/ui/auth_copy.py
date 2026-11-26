"""Teks presentasi autentikasi. Tidak mengubah hasil maupun aturan service."""

import re


# Ringkas hanya pesan yang sudah diketahui; jangan menebak status dari input.
_SHORT_MESSAGES = {
    'Email belum diverifikasi. Selesaikan verifikasi terlebih dahulu.':
        'Email belum diverifikasi.',
    'Email terverifikasi. Akun tutor masih menunggu persetujuan admin.':
        'Akun tutor menunggu persetujuan Admin.',
    'Akun Anda telah dinonaktifkan.': 'Akun dinonaktifkan. Hubungi Admin.',
    'Akun belum dapat digunakan. Hubungi administrator.':
        'Akun belum dapat digunakan. Hubungi Admin.',
    'Data pengguna tidak dapat dimuat kembali.': 'Data akun gagal dimuat. Coba lagi.',
    'Gagal memperbarui status percobaan login.': 'Login gagal diproses. Coba lagi.',
    'Batas pengiriman OTP tercapai. Tunggu sebelum meminta kode baru.':
        'Batas kirim OTP tercapai. Tunggu sebentar.',
    'Pengiriman OTP gagal. Periksa konfigurasi email.':
        'OTP gagal dikirim. Hubungi Admin.',
    'OTP tidak ditemukan atau sudah digunakan.': 'OTP tidak tersedia. Minta kode baru.',
    'OTP sudah digunakan atau tidak aktif.': 'OTP tidak aktif. Minta kode baru.',
    'OTP kedaluwarsa. Silakan minta kode baru.': 'OTP kedaluwarsa. Minta kode baru.',
    'Kode OTP kedaluwarsa. Minta kode baru.': 'OTP kedaluwarsa. Minta kode baru.',
    'Batas percobaan OTP tercapai. Minta kode baru.':
        'Batas percobaan OTP habis. Minta kode baru.',
    'Batas percobaan tercapai. Minta OTP baru.':
        'Batas percobaan OTP habis. Minta kode baru.',
    'Kode OTP tidak valid atau sudah digunakan.': 'OTP tidak valid atau sudah digunakan.',
    'Kode OTP tidak valid atau tidak tersedia.': 'OTP tidak valid atau tidak tersedia.',
    'Password baru harus berbeda dari password sementara.':
        'Jangan gunakan ulang password sementara.',
    'Password baru harus berbeda dari password sebelumnya.':
        'Password baru harus berbeda dari password lama.',
    'Password terlalu panjang dalam UTF-8 untuk bcrypt (maksimal 72 byte).':
        'Password melebihi 72 byte UTF-8.',
    'Username 4-30 karakter: huruf, angka, atau underscore.':
        'Username 4–30: huruf, angka, atau underscore (_).',
    'Password harus mengandung minimal satu huruf.': 'Password perlu minimal 1 huruf.',
    'Password harus mengandung minimal satu angka.': 'Password perlu minimal 1 angka.',
    'Password harus terdiri dari 8-64 karakter.': 'Password harus 8–64 karakter.',
    'Password berhasil diatur ulang. Silakan login kembali.':
        'Password diperbarui. Silakan login kembali.',
    'Email berhasil diverifikasi. Akun menunggu persetujuan admin.':
        'Email terverifikasi. Tunggu persetujuan Admin.',
    'Operasi belum dapat diselesaikan. Periksa koneksi dan coba kembali.':
        'Operasi gagal. Periksa koneksi, lalu coba lagi.',
}


def concise_message(value):
    """Pertahankan alasan, sisa percobaan, waktu kunci, dan masa berlaku OTP."""
    message = ' '.join(str(value or '').split())
    if message in _SHORT_MESSAGES:
        return _SHORT_MESSAGES[message]
    if message.startswith('Akun berhasil dibuat, tetapi OTP belum berhasil dikirim.'):
        return 'Akun dibuat. OTP gagal dikirim; kirim ulang OTP.'
    sent = re.fullmatch(r'(?:Akun berhasil dibuat\. )?OTP berhasil dikirim\. Masa berlaku: (\d+) menit\.', message)
    if sent:
        if message.startswith('Akun berhasil dibuat.'):
            return f'Akun dibuat. OTP berlaku {sent[1]} menit.'
        return f'OTP dikirim. Berlaku {sent[1]} menit.'
    locked = re.fullmatch(r'Akun dikunci sementara karena terlalu banyak percobaan login gagal\. Coba lagi setelah (.+)\.', message)
    if locked:
        return f'Akun dikunci. Coba lagi setelah {locked[1]}.'
    locked = re.fullmatch(r'Terlalu banyak percobaan login gagal\. Akun dikunci selama (\d+) menit\.', message)
    if locked:
        return f'Login dibatasi. Akun dikunci {locked[1]} menit.'
    attempts = re.fullmatch(r'Username atau password salah\. Sisa percobaan sebelum penguncian: (\d+)\.', message)
    if attempts:
        return f'Username/password salah. Sisa: {attempts[1]} percobaan.'
    return message
