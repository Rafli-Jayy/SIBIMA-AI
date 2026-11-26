"""UI-001 tests: controller routes + real Prompt Toolkit keyboard input, no DB."""
import asyncio
import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.output.vt100 import Vt100_Output

from app.ui.auth_motion import AuthMotion
from app.ui.auth_workspace import AuthWorkspace, Field, safe_text
from app.ui.menu_auth import AuthController, MAIN_CHOICES


class FakeView:
    def __init__(self, menus=(), forms=()):
        self.menus=iter(menus)
        self.forms=iter(forms)
        self.messages=[]
        self.seen=[]
        self.opened=0

    async def menu(self,title,choices,**kwargs):
        self.seen.append((title,kwargs))
        selected=next(self.menus)
        assert selected is None or selected in [k for k,_ in choices]
        return selected

    async def form(self,title,fields,**kwargs):
        self.seen.append((title,kwargs))
        values=next(self.forms)
        return dict(values) if values is not None else None

    async def message(self,title,content,**kwargs):
        self.messages.append((title,content,kwargs))

    async def busy(self,title,fn,*args):
        self.seen.append((title,{}))
        return fn(*args)

    async def opening(self):
        self.opened+=1


def account(role='siswa',status='aktif',**kw):
    return dict(id=12,username='demo',nama_lengkap='Demo',role=role,status=status,**kw)


def run(coro):
    return asyncio.run(coro)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.auth=Mock()
        self.lookup=Mock()
        self.c=AuthController(self.auth,self.lookup)

    def test_main_menu_exact_legacy_routes(self):
        self.assertEqual([k for k,_ in MAIN_CHOICES],['Login','Register','Lupa Password','Keluar'])

    def test_login_all_existing_roles(self):
        for role in ('admin','tutor','siswa'):
            u=account(role)
            self.auth.login.return_value=(True,u)
            view=FakeView(menus=['Login'],forms=[{'username':'demo','password':'test'}])
            self.assertEqual(run(self.c.run(view)),u)
            self.assertEqual(view.opened,1)

    def test_pending_student_preserved(self):
        u=account(status='menunggu_konfirmasi')
        self.auth.login.return_value=(True,u)
        v=FakeView(forms=[{'username':'demo','password':'test'}])
        self.assertEqual(run(self.c.menu_login(v)),u)
        self.assertIn('menunggu_konfirmasi',v.messages[-1][1])

    def test_failed_login_no_new_otp_route(self):
        self.auth.login.return_value=(False,'Email belum diverifikasi.')
        v=FakeView(forms=[{'username':'demo','password':'test'},None])
        self.assertIsNone(run(self.c.menu_login(v)))
        self.assertEqual(self.auth.login.call_count,1)
        self.assertIn('Email belum diverifikasi.',str(v.seen))
        self.auth.kirim_ulang_otp_registrasi.assert_not_called()

    def test_password_temporary_success(self):
        self.auth.login.return_value=(True,account(must_change_password=True))
        self.auth.ganti_password.return_value=(True,'ok')
        self.lookup.return_value=account(must_change_password=False)
        v=FakeView(forms=[{'username':'demo','password':'old'},
                          {'baru':'newpass1','confirm':'newpass1'}])
        self.assertEqual(run(self.c.menu_login(v)),self.lookup.return_value)
        self.auth.ganti_password.assert_called_once_with(12,'old','newpass1')

    def test_password_temporary_cancel_no_dashboard(self):
        self.auth.login.return_value=(True,account(must_change_password=True))
        v=FakeView(forms=[{'username':'demo','password':'old'},None])
        self.assertIsNone(run(self.c.menu_login(v)))
        self.auth.ganti_password.assert_not_called()

    def test_password_temporary_three_invalid_pairs(self):
        self.auth.login.return_value=(True,account(must_change_password=True))
        v=FakeView(forms=[{'username':'demo','password':'old'}]+[{'baru':'a','confirm':'b'}]*3)
        self.assertIsNone(run(self.c.menu_login(v)))
        self.auth.ganti_password.assert_not_called()

    def test_registration_existing_role_and_otp_retry(self):
        self.auth.register.return_value=(True,'Akun dibuat, OTP belum berhasil dikirim.')
        self.auth.kirim_ulang_otp_registrasi.return_value=(True,'OTP dikirim')
        self.auth.verifikasi_otp_registrasi.side_effect=[(False,'Kode salah'),(True,'Email terverifikasi')]
        view=FakeView(menus=['tutor','daftar','kirim_ulang','verifikasi','verifikasi'],
                      forms=[{'nama_lengkap':'Demo User','username':'demo','email':'a@example.com'},
                             {'password':'abc12345','confirm':'abc12345'},{'kode':'123456'},{'kode':'654321'}])
        # capture call payload before the controller clears secrets
        captured=[]
        def register(r,p):
            captured.append((r,dict(p)))
            return True,'Akun dibuat, OTP belum berhasil dikirim.'
        self.auth.register.side_effect=register
        run(self.c.menu_register(view))
        self.assertEqual(captured,[('tutor',dict(nama_lengkap='Demo User',username='demo',
                                               email='a@example.com',password='abc12345'))])
        self.auth.kirim_ulang_otp_registrasi.assert_called_once_with('demo')
        self.assertEqual(self.auth.verifikasi_otp_registrasi.call_count,2)
        self.assertIn('tunggu persetujuan Admin',view.messages[-1][1])

    def test_otp_cancel_does_not_call_service(self):
        v=FakeView(menus=['verifikasi','selesai'],forms=[None])
        run(self.c.menu_verifikasi_registrasi(v,'demo'))
        self.auth.verifikasi_otp_registrasi.assert_not_called()

    def test_password_recovery_exact_legacy_contract(self):
        self.auth.minta_otp_reset_password.return_value=(True,'Jika memenuhi syarat, OTP dikirim.')
        self.auth.reset_password.return_value=(True,'Selesai')
        v=FakeView(forms=[{'email':'a@example.com'},{'kode':'123456'},
                          {'baru':'newpass1','confirm':'newpass1'}])
        run(self.c.menu_lupa_password(v))
        self.auth.minta_otp_reset_password.assert_called_once_with('a@example.com')
        self.auth.reset_password.assert_called_once_with('a@example.com','123456','newpass1')
        self.assertEqual(v.messages[-1][2]['kind'],'success')

    def test_reset_mismatch_no_service_call(self):
        self.auth.minta_otp_reset_password.return_value=(True,'Jika memenuhi syarat, OTP dikirim.')
        v=FakeView(forms=[{'email':'a@example.com'},{'kode':'123456'},{'baru':'x','confirm':'y'}])
        run(self.c.menu_lupa_password(v))
        self.auth.reset_password.assert_not_called()

    def test_error_message_does_not_expose_traceback(self):
        self.auth.login.side_effect=RuntimeError('SECRET DSN')
        v=FakeView(forms=[{'username':'demo','password':'test'},None])
        self.assertIsNone(run(self.c.menu_login(v)))
        self.assertNotIn('SECRET DSN',str(v.seen))

    def test_exit_confirmation_and_no_opening_on_return(self):
        v=FakeView(menus=['Keluar','back','Keluar','exit'])
        self.assertIsNone(run(self.c.run(v,opening=False)))
        self.assertEqual(v.opened,0)


class WorkspaceTests(unittest.TestCase):
    def test_motion_does_not_require_sleep(self):
        now=[0.]
        motion=AuthMotion(clock=lambda:now[0])
        a=motion.spinner()
        now[0]=0.25
        self.assertNotEqual(motion.spinner(),a)
        self.assertEqual(len(motion.marquee()),15)
        self.assertEqual(motion.logo(20),'S I B I M A')
        self.assertEqual(AuthMotion(enabled=False).success_mark(),'✓')

    def test_sanitize_control_characters(self):
        self.assertNotIn('\x1b',safe_text('a\x1b[3mb'))

    def test_real_keyboard_menu_and_password_form(self):
        with create_pipe_input() as inp:
            w=AuthWorkspace(input=inp,output=DummyOutput(),motion_enabled=False)
            async def route(view):
                async def keys(sequence):
                    await asyncio.sleep(.05)
                    inp.send_text(sequence)
                asyncio.create_task(keys('\x1b[B\r'))
                chosen=await view.menu('TEST MENU',[('a','A'),('b','B')])
                asyncio.create_task(keys('demo\tsecret-only\r'))
                form=await view.form('TEST FORM',[Field('username','Username'),
                                                Field('password','Password',secret=True)])
                return chosen,form,view.form_fields
            result=w.run(route)
            self.assertEqual(result,('b',{'username':'demo','password':'secret-only'},{}))

    def test_sirasa_exact_panel_rows_and_focus_marker(self):
        class Output(DummyOutput):
            def get_size(self):
                return Size(rows=24, columns=80)

        def screen(view):
            rendered = view.app.renderer.last_rendered_screen
            return ["".join(rendered.data_buffer[y][x].char for x in range(80))
                    for y in range(24)]

        with create_pipe_input() as inp:
            w=AuthWorkspace(input=inp,output=Output(),motion_enabled=False)
            async def route(view):
                async def keys():
                    await asyncio.sleep(.08)
                    lines=screen(view)
                    username=next(i for i,line in enumerate(lines) if '│  Username' in line)
                    password=next(i for i,line in enumerate(lines) if '│  Password' in line)
                    assert '❯ demo' in lines[username+1]
                    assert password==username+2
                    top=next(i for i,line in enumerate(lines) if '┌' in line)
                    bottom=next(i for i,line in enumerate(lines) if '└' in line)
                    assert bottom-top==12  # 13 rows including frame borders.
                    assert lines[top].index('┐') - lines[top].index('┌') == 59
                    assert username==top+5
                    assert not lines[password+2].strip(' │')
                    assert 'Masuk' in lines[password+3]
                    assert 'Kembali' in lines[password+4]
                    inp.send_text('\tprivate-password')
                    await asyncio.sleep(.08)
                    after=screen(view)
                    assert '❯ demo' not in '\n'.join(after)
                    assert '❯ ' in after[password+1]
                    assert 'private-password' not in '\n'.join(after)
                    inp.send_text('\x1b')
                async def drive():
                    try:
                        await keys()
                    except Exception as exc:
                        view.app.exit(exception=exc)
                task=asyncio.create_task(drive())
                try:
                    return await view.form('LOGIN PENGGUNA',[
                        Field('username','Username','demo'),
                        Field('password','Password',secret=True),
                    ], subtitle='Masuk menggunakan akun SIBIMA', submit_label='Masuk')
                finally:
                    await asyncio.gather(task,return_exceptions=True)
            self.assertIsNone(w.run(route))

    def test_sirasa_header_separator_and_arrow_focus(self):
        class Output(DummyOutput):
            def get_size(self):
                return Size(rows=35, columns=110)

        def screen(view):
            rendered=view.app.renderer.last_rendered_screen
            return "\n".join("".join(rendered.data_buffer[y][x].char for x in range(110))
                             for y in range(35))

        with create_pipe_input() as inp:
            w=AuthWorkspace(input=inp,output=Output(),motion_enabled=False)
            async def route(view):
                async def drive():
                    try:
                        await asyncio.sleep(.08)
                        before=screen(view)
                        assert '███████' in before
                        assert 'Sistem Informasi Bimbingan Belajar' in before
                        assert 'Akses khusus pengguna terdaftar' in before
                        assert '│  ─────' in before
                        assert '❯ demo' in before
                        inp.send_text('\x1b[Bprivatepass')
                        await asyncio.sleep(.08)
                        assert '❯ ***********' in screen(view)
                        assert 'privatepass' not in screen(view)
                        inp.send_text('\x1b[A')
                        await asyncio.sleep(.08)
                        assert '❯ demo' in screen(view)
                        inp.send_text('\x1b')
                    except Exception as exc:
                        view.app.exit(exception=exc)
                task=asyncio.create_task(drive())
                try:
                    return await view.form('LOGIN PENGGUNA',[
                        Field('username','Username','demo'),
                        Field('password','Password',secret=True),
                    ],subtitle='Masuk menggunakan akun SIBIMA',submit_label='Masuk')
                finally:
                    await asyncio.gather(task,return_exceptions=True)
            self.assertIsNone(w.run(route))

    def test_real_small_terminal_render_and_escape(self):
        # Render to an actual VT100 output, but keep user state isolated.
        for size in (Size(rows=24,columns=80),Size(rows=15,columns=48)):
            out=io.StringIO()
            with create_pipe_input() as inp:
                output=Vt100_Output(out,lambda:size,term='xterm-256color',enable_cpr=False)
                w=AuthWorkspace(input=inp,output=output,motion_enabled=False)
                async def route(view):
                    async def keys():
                        await asyncio.sleep(.08)
                        inp.send_text('demo\tprivate-password\x1b')
                    asyncio.create_task(keys())
                    return await view.form('LOGIN PENGGUNA',[Field('username','Username'),
                                                          Field('password','Password',secret=True)])
                self.assertIsNone(w.run(route))
                rendered=out.getvalue()
                self.assertIn('LOGIN PENGGUNA',rendered)
                self.assertNotIn('private-password',rendered)


if __name__=='__main__':
    unittest.main()
