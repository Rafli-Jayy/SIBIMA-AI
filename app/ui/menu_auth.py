"""UI-001: autentikasi SIBIMA, satu workspace tanpa mengubah kontrak service.

Menu, urutan operasi, role, dan validasi berasal dari CLI sebelumnya.
Dashboard lama tetap dijalankan di luar alternate screen autentikasi.
"""
from __future__ import annotations

from .auth_workspace import AuthWorkspace, Field

MAIN_CHOICES = (
    ('Login', '01  Masuk ke Akun'),
    ('Register', '02  Pendaftaran Baru'),
    ('Lupa Password', '03  Lupa Password'),
    ('Keluar', '00  Keluar'),
)
ROLE_CHOICES = (('siswa', 'Siswa'), ('tutor', 'Tutor'), ('back', 'Kembali'))
OTP_CHOICES = (
    ('verifikasi', 'Masukkan kode OTP'),
    ('kirim_ulang', 'Kirim ulang OTP'),
    ('selesai', 'Selesai / kembali'),
)
ERROR_GENERIC = 'Operasi belum dapat diselesaikan. Periksa koneksi dan coba kembali.'


class AuthController:
    """Adapter interaksi baru untuk service yang sama; dapat diuji tanpa database."""

    def __init__(self, auth, user_lookup):
        self.auth = auth
        self.user_lookup = user_lookup

    async def _request(self, view, label, method, *args):
        try:
            return await view.busy(label, getattr(self.auth, method), *args)
        except Exception:
            # Jangan tampilkan traceback, kredensial, atau detail koneksi.
            return False, ERROR_GENERIC

    async def menu_verifikasi_registrasi(self, view, username, message=''):
        notice = message or 'Periksa Inbox/Spam untuk kode OTP.'
        style = 'warning' if 'OTP belum berhasil dikirim' in notice else 'muted'
        while True:
            choice = await view.menu(
                'VERIFIKASI EMAIL', OTP_CHOICES,
                subtitle=f'Akun: {username}',
                notice=notice, notice_style=style,
            )
            if choice in (None,'selesai'):
                return
            if choice=='kirim_ulang':
                ok,notice = await self._request(view, 'Mengirim ulang kode OTP...',
                                              'kirim_ulang_otp_registrasi',username)
                style = 'success' if ok else 'error'
                continue
            if choice!='verifikasi':
                continue
            fields = await view.form('MASUKKAN KODE OTP', [Field('kode','Kode OTP (6 digit)',secret=True)],
                                     subtitle='Verifikasi email pendaftaran',
                                     hint='Pakai OTP terbaru. Jangan bagikan kode.',
                                     submit_label='Verifikasi')
            if fields is None:
                notice,style='Verifikasi dibatalkan. Pilih tindakan.','warning'
                continue
            kode = fields['kode'].strip()
            if not kode:
                notice,style='Kode OTP wajib diisi.','error'
                continue
            ok,notice = await self._request(view,'Memverifikasi kode OTP...',
                                           'verifikasi_otp_registrasi',username,kode)
            if ok:
                await view.message('VERIFIKASI BERHASIL',
                    'Email terverifikasi. Silakan tunggu persetujuan Admin.',
                    kind='success')
                return
            style='error'

    async def _proses_password_sementara(self, view, user, password_lama):
        notice='Password direset Admin. Ganti sekarang.'
        style='warning'
        for _ in range(3):
            data=await view.form('GANTI PASSWORD WAJIB', [
                Field('baru','Password baru',secret=True),
                Field('confirm','Ulangi password baru',secret=True),
            ],subtitle='8–64 karakter, min. 1 huruf dan 1 angka',
            notice=notice,notice_style=style,submit_label='Simpan')
            if data is None:
                await view.message('LOGIN DIBATALKAN','Password sementara masih berlaku.')
                return None
            baru=data['baru']
            if baru!=data['confirm']:
                notice,style='Konfirmasi password tidak cocok.','error'
                continue
            if baru==password_lama:
                notice,style='Password baru harus berbeda dari password sementara.','error'
                continue
            ok,pesan=await self._request(view,'Menyimpan password baru...',
                                         'ganti_password',user['id'],password_lama,baru)
            if not ok:
                notice,style=pesan,'error'
                continue
            try:
                terbaru=await view.busy('Memastikan perubahan password...',self.user_lookup,user['id'])
            except Exception:
                terbaru=None
            if not terbaru or terbaru.get('must_change_password'):
                await view.message('PASSWORD BELUM TERKONFIRMASI',
                    'Silakan coba login kembali.',kind='error')
                return None
            await view.message('PASSWORD BERHASIL DIGANTI','Password baru telah tersimpan.',kind='success',auto=True)
            return terbaru
        await view.message('BATAS PERCOBAAN','Silakan login kembali.',kind='error')
        return None

    async def menu_login(self, view):
        username=''
        notice=''
        while True:
            data=await view.form('LOGIN PENGGUNA',[
                Field('username','Username',default=username),
                Field('password','Password',secret=True),
            ],subtitle='Masuk menggunakan akun SIBIMA',notice=notice,submit_label='Masuk')
            if data is None or not data['username'] or not data['password']:
                return None
            username=data['username']
            password=data['password']
            ok,user=await self._request(view,'Memverifikasi kredensial...','login',username,password)
            if not ok:
                # Service menentukan status dan akses. Tidak menambah rute OTP/login baru.
                notice=str(user)
                password=None
                data.clear()
                continue
            if user.get('must_change_password'):
                user=await self._proses_password_sementara(view,user,password)
                if user is None:
                    return None
            password=None
            data.clear()
            role=user.get('role')
            if role not in ('admin','tutor','siswa'):
                await view.message('AKSES DITOLAK','Role akun tidak dikenali.',kind='error')
                return None
            # Siswa menunggu tetap mengikuti onboarding dashboard lama. Tutor menunggu
            # ditolak oleh service. Jangan mengubah status akun dari presentasi.
            label='Membuka halaman akun...' if user.get('status')!='aktif' else f'Membuka dashboard {role.capitalize()}...'
            await view.message('AUTENTIKASI BERHASIL',
                f"Selamat datang, {user.get('nama_lengkap') or username}\n"
                f"Role: {role.upper()}  |  Status: {user.get('status','—')}\n\n{label}",
                kind='success',auto=True)
            return user

    async def menu_register(self,view):
        """Wizard hanya memisahkan tampilan; tetap 1 panggilan register."""
        role=None
        account={'username':'','email':'','nama_lengkap':''}
        step=1
        notice=''
        password=None
        while True:
            if step==1:
                role=await view.menu('PILIH JENIS AKUN',ROLE_CHOICES,
                                     subtitle='Langkah 1/4 · Pilih peran akun')
                if role in (None,'back'):
                    return
                step=2
            elif step==2:
                values=await view.form('INFORMASI AKUN',[
                    Field('nama_lengkap','Nama lengkap',account['nama_lengkap']),
                    Field('username','Username',account['username']),
                    Field('email','Email aktif',account['email']),
                ],step='Langkah 2/4',subtitle='Informasi pengguna',
                    hint='Username 4–30: huruf, angka, atau underscore (_).',notice=notice)
                if values is None:
                    step=1
                    notice=''
                    continue
                account.update(values)
                if not all(account.values()):
                    notice='Semua kolom wajib diisi.'
                    continue
                notice=''
                step=3
            elif step==3:
                values=await view.form('KEAMANAN AKUN',[
                    Field('password','Password',secret=True),
                    Field('confirm','Konfirmasi password',secret=True),
                ],step='Langkah 3/4',subtitle='Keamanan',
                    hint='8–64 karakter, min. 1 huruf dan 1 angka',notice=notice)
                if values is None:
                    step=2
                    notice=''
                    continue
                if values['password']!=values['confirm']:
                    notice='Konfirmasi password tidak cocok.'
                    continue
                if not values['password']:
                    notice='Password wajib diisi.'
                    continue
                password=values['password']
                values.clear()
                notice=''
                step=4
            else:
                action=await view.menu('TINJAU PENDAFTARAN',(
                    ('daftar','Daftar'),('back','Kembali'),
                ),subtitle='Langkah 4/4 · Periksa data akun',
                    notice='Verifikasi email & persetujuan Admin.',
                    details=(f"Role: {role.capitalize()}",
                             f"Nama: {account['nama_lengkap']}",
                             f"Username: {account['username']}",
                             f"Email: {account['email']}"))
                if action!='daftar':
                    password=None
                    step=3
                    continue
                payload={k:v.strip() for k,v in account.items()}
                payload['password']=password
                ok,pesan=await self._request(view,'Memproses pendaftaran...','register',role,payload)
                payload.pop('password',None)
                password=None
                if ok:
                    await self.menu_verifikasi_registrasi(view,payload['username'],str(pesan))
                    return
                await view.message('REGISTRASI GAGAL',pesan,kind='error')
                step=2

    async def menu_lupa_password(self,view):
        data=await view.form('PULIHKAN AKUN',[Field('email','Email terdaftar')],
            subtitle='Pemulihan password',
            hint='OTP dikirim jika email memenuhi syarat.',submit_label='Kirim OTP')
        if data is None:
            return
        email=data['email']
        ok,pesan=await self._request(view,'Memproses permintaan OTP...',
                                     'minta_otp_reset_password',email)
        if not ok:
            await view.message('PERMINTAAN GAGAL',pesan,kind='error')
            return
        # Pesan netral dari service: tidak mengungkap apakah email terdaftar.
        otp=await view.form('KODE PEMULIHAN',[Field('kode','Kode OTP (6 angka)',secret=True)],
                            subtitle='Periksa Inbox/Spam. Jangan bagikan OTP.',
                            notice='OTP dikirim jika email memenuhi syarat.',notice_style='muted')
        if otp is None:
            return
        values=await view.form('PASSWORD BARU',[
            Field('baru','Password baru',secret=True),
            Field('confirm','Ulangi password baru',secret=True),
        ],subtitle='8–64 karakter, min. 1 huruf dan 1 angka',
            hint='OTP diverifikasi saat password disimpan.',submit_label='Simpan')
        if values is None:
            return
        if values['baru']!=values['confirm']:
            await view.message('KONFIRMASI TIDAK COCOK','Silakan ulangi proses.',kind='error')
            return
        ok,pesan=await self._request(view,'Memverifikasi dan menyimpan password...',
                                     'reset_password',email,otp['kode'].strip(),values['baru'])
        otp.clear()
        values.clear()
        await view.message('PASSWORD BERHASIL DIPERBARUI' if ok else 'PEMULIHAN GAGAL',
                           pesan,kind='success' if ok else 'error')

    async def run(self,view,*,opening=True):
        if opening:
            await view.opening()
        while True:
            action=await view.menu('MENU UTAMA',MAIN_CHOICES,
                                  subtitle='Sistem Informasi Bimbingan Belajar')
            if action in (None,'Keluar'):
                choice=await view.menu('KELUAR DARI APLIKASI',(
                    ('back','Kembali'),('exit','Keluar'),
                ),subtitle='Akhiri sesi SIBIMA-AI?')
                if choice=='exit':
                    await view.message('SAMPAI JUMPA','Terima kasih telah menggunakan SIBIMA-AI.',kind='success',auto=True)
                    return None
            elif action=='Login':
                user=await self.menu_login(view)
                if user is not None:
                    return user
            elif action=='Register':
                await self.menu_register(view)
            elif action=='Lupa Password':
                await self.menu_lupa_password(view)


def jalankan():
    from app import session
    from app.services import auth_service
    from app.repositories import user_repo

    controller=AuthController(auth_service,user_repo.cari_by_id)
    opening=True
    while True:
        user=AuthWorkspace().run(lambda view:controller.run(view,opening=opening))
        opening=False
        if user is None:
            return
        session.set_user(user)
        role=user['role']
        # The old dashboards run only after Prompt Toolkit has restored the normal
        # screen; none of the Admin/Tutor/Siswa/AI menu code is changed by UI-001.
        if role=='admin':
            from app.ui import menu_admin as dashboard
        elif role=='tutor':
            from app.ui import menu_tutor as dashboard
        else:
            from app.ui import menu_siswa as dashboard
        dashboard.jalankan()


if __name__=='__main__':
    jalankan()
