"""Visual regressions across all auth screens using actual PTK rendered cells."""
import asyncio
import unittest

from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.utils import get_cwidth

from app.ui.auth_copy import concise_message
from app.ui.auth_workspace import AuthWorkspace, Field, bounded_lines
from app.ui.menu_auth import MAIN_CHOICES, ROLE_CHOICES, OTP_CHOICES


class AuthCopyTests(unittest.TestCase):
    def test_remaining_attempts_lock_time_and_expiry_preserved(self):
        for before, expected in (
            ('Username atau password salah. Sisa percobaan sebelum penguncian: 2.', '2 percobaan'),
            ('Akun dikunci sementara karena terlalu banyak percobaan login gagal. Coba lagi setelah 14:35:00 UTC.', '14:35:00 UTC'),
            ('Terlalu banyak percobaan login gagal. Akun dikunci selama 15 menit.', '15 menit'),
            ('Akun berhasil dibuat. OTP berhasil dikirim. Masa berlaku: 5 menit.', '5 menit'),
            ('Kode OTP salah. Sisa percobaan: 1.', '1.'),
            ('Akun berhasil dibuat, tetapi OTP belum berhasil dikirim. Jenis error: RuntimeError. Pilih menu kirim ulang OTP untuk mencoba lagi.', 'kirim ulang OTP'),
        ):
            with self.subTest(before=before):
                self.assertIn(expected, concise_message(before))
                self.assertLessEqual(get_cwidth(concise_message(before)), 66)

    def test_unfamiliar_message_is_safe_and_bounded_in_cells(self):
        message = 'Alasan: ' + '漢字' * 400 + '\x1b[31m\nbaris lain'
        result = bounded_lines(concise_message(message),40)
        self.assertLessEqual(len(result.splitlines()),2)
        self.assertTrue(result.endswith('…'))
        self.assertNotIn('\x1b',result)
        for line in result.splitlines():
            self.assertLessEqual(get_cwidth(line),40)

    def test_neutral_recovery_message_remains_conditional(self):
        # No account existence or actual OTP delivery is revealed.
        from unittest.mock import Mock
        from app.ui.menu_auth import AuthController
        from test_ui001_auth_remake import FakeView
        auth = Mock()
        auth.minta_otp_reset_password.return_value=(True,'Jika memenuhi syarat, OTP dikirim.')
        view=FakeView(forms=[{'email':'demo@example.com'},None])
        asyncio.run(AuthController(auth,Mock()).menu_lupa_password(view))
        recovery=next(kwargs for title,kwargs in view.seen if title=='KODE PEMULIHAN')
        self.assertIn('jika email memenuhi syarat',recovery['notice'])
        self.assertEqual(recovery['notice_style'],'muted')


class AllAuthRenderTests(unittest.TestCase):
    def test_all_auth_pages_share_header_panel_and_field_layout(self):
        scenes = [
            ('menu','MENU UTAMA',MAIN_CHOICES,{'subtitle':'Sistem Informasi Bimbingan Belajar'},[]),
            ('menu','PILIH JENIS AKUN',ROLE_CHOICES,{'subtitle':'Langkah 1/4 · Pilih peran akun'},[]),
            ('form','LOGIN PENGGUNA',[Field('u','Username'), Field('p','Password',secret=True)],{'subtitle':'Masuk menggunakan akun SIBIMA','submit_label':'Masuk'},['Username','Password']),
            ('form','INFORMASI AKUN',[Field('n','Nama lengkap'),Field('u','Username'),Field('e','Email aktif')],{'step':'Langkah 2/4','hint':'Username 4–30: huruf, angka, underscore.'},['Nama lengkap','Username','Email aktif']),
            ('form','KEAMANAN AKUN',[Field('p','Password',secret=True),Field('c','Konfirmasi password',secret=True)],{'step':'Langkah 3/4'},['Password','Konfirmasi password']),
            ('menu','TINJAU PENDAFTARAN',[('daftar','Daftar'),('back','Kembali')],{'subtitle':'Langkah 4/4','details':('Role: Siswa','Email: demo@example.com')},[]),
            ('menu','VERIFIKASI EMAIL',OTP_CHOICES,{'subtitle':'Akun: demo','notice':'OTP kedaluwarsa. Silakan minta kode baru.','notice_style':'error'},[]),
            ('form','MASUKKAN KODE OTP',[Field('k','Kode OTP (6 digit)',secret=True)],{},['Kode OTP (6 digit)']),
            ('form','PULIHKAN AKUN',[Field('e','Email terdaftar')],{'hint':'OTP dikirim jika email memenuhi syarat.'},['Email terdaftar']),
            ('form','KODE PEMULIHAN',[Field('k','Kode OTP (6 angka)',secret=True)],{},['Kode OTP (6 angka)']),
            ('form','PASSWORD BARU',[Field('p','Password baru',secret=True),Field('c','Ulangi password baru',secret=True)],{},['Password baru','Ulangi password baru']),
            ('form','GANTI PASSWORD WAJIB',[Field('p','Password baru',secret=True),Field('c','Ulangi password baru',secret=True)],{'notice':'Password direset Admin. Ganti sekarang.','notice_style':'warning'},['Password baru','Ulangi password baru']),
            ('message','PEMULIHAN GAGAL','Kode OTP kedaluwarsa. Minta kode baru.',{'kind':'error'},[]),
            ('menu','KELUAR DARI APLIKASI',[('back','Kembali'),('exit','Keluar')],{},[]),
        ]
        class Output(DummyOutput):
            def get_size(self):
                return Size(rows=24,columns=80)
        with create_pipe_input() as inp:
            w=AuthWorkspace(input=inp,output=Output(),motion_enabled=False)
            async def route(view):
                for method,title,data,kwargs,labels in scenes:
                    async def drive():
                        try:
                            await asyncio.sleep(.06)
                            s=view.app.renderer.last_rendered_screen
                            lines=[''.join(s.data_buffer[y][x].char for x in range(80)) for y in range(24)]
                            text='\n'.join(lines)
                            self.assertIn('S I B I M A',lines[0])
                            self.assertIn('Sistem Informasi Bimbingan Belajar',lines[1])
                            self.assertNotIn('SIBIMA-AI  '+title,text)
                            top=next(i for i,line in enumerate(lines) if '┌' in line)
                            bottom=next(i for i,line in enumerate(lines) if '└' in line)
                            self.assertIn(title,lines[top+1])
                            self.assertEqual(lines[top].index('┐')-lines[top].index('┌'),59)
                            self.assertTrue(any('│  ─────' in row for row in lines[top:bottom]))
                            if labels:
                                indexes=[next(i for i,line in enumerate(lines) if '│  '+label in line) for label in labels]
                                self.assertTrue(all(y-x==2 for x,y in zip(indexes,indexes[1:])),title)
                                self.assertIn('│  ❯',lines[indexes[0]+1])
                                self.assertIn('Kembali',lines[bottom-1])
                            view.finish(None)
                        except Exception as exc:
                            view.app.exit(exception=exc)
                    task=asyncio.create_task(drive())
                    try:
                        await getattr(view,method)(title,data,**kwargs)
                    finally:
                        await task
            w.run(route)

    def test_long_warning_and_keyboard_on_narrow_terminal(self):
        class Output(DummyOutput):
            def get_size(self):
                return Size(rows=15,columns=48)
        with create_pipe_input() as inp:
            w=AuthWorkspace(input=inp,output=Output(),motion_enabled=False)
            async def route(view):
                async def drive():
                    try:
                        await asyncio.sleep(.08)
                        s=view.app.renderer.last_rendered_screen
                        lines=[''.join(s.data_buffer[y][x].char for x in range(48)) for y in range(15)]
                        self.assertIn('S I B I M A',lines[0])
                        top=next(i for i,line in enumerate(lines) if '┌' in line)
                        bottom=next(i for i,line in enumerate(lines) if '└' in line)
                        username=next(i for i,line in enumerate(lines) if '│  Username' in line)
                        rule=next(i for i,line in enumerate(lines) if '│  ─────' in line)
                        self.assertEqual(username-rule,3)
                        self.assertIn('…',lines[rule+2])
                        for y in range(top+1,bottom):
                            self.assertEqual(lines[y][1],'│')
                            self.assertEqual(lines[y][46],'│')
                        inp.send_text('demo\tsecret\t\t')
                        await asyncio.sleep(.08)
                        s=view.app.renderer.last_rendered_screen
                        text='\n'.join(''.join(s.data_buffer[y][x].char for x in range(48)) for y in range(15))
                        self.assertIn('Kembali',text)
                        self.assertNotIn('secret',text)
                        inp.send_text('\r')
                    except Exception as exc:
                        view.app.exit(exception=exc)
                task=asyncio.create_task(drive())
                try:
                    return await view.form('LOGIN PENGGUNA',[Field('u','Username'),Field('p','Password',secret=True)],subtitle='Masuk menggunakan akun SIBIMA',notice='Pendaftaran ditolak. Alasan: '+('Panjang sekali. '*100),submit_label='Masuk')
                finally:
                    await task
            self.assertIsNone(w.run(route))


if __name__=='__main__':
    unittest.main()
