"""Regression tests: no real database, email, or PDF calls."""
import asyncio
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from decimal import Decimal
from prompt_toolkit.input import create_pipe_input
from test_ui002_admin_workspace import SUMMARY, Output, screen, text_of, run_keys
from app.ui.admin_workspace import Snapshot, priority_pages, width_of, AdminDashboardNavigator
from app.ui.admin_confirmation import (
    ConfirmationController, ConfirmationWorkspace, account_sections,
    enrollment_sections, details_pages, table_row, wrap,
)

ACCOUNT=dict(id=21,nama_lengkap='Andi Pratama',username='andipratama',
             role='siswa',email_verified=True,status='menunggu_konfirmasi',
             email='andi@example.test',jenjang='SMA',sekolah='SMA Negeri 1',
             created_at=datetime(2026,11,26,8),nama_wali='Budi',student_no_hp='0812345678')
TUTOR=dict(ACCOUNT,id=22,role='tutor',nama_lengkap='Dewi Lestari',keahlian='Matematika')
PROGRAM=dict(enrollment_id=31,student_id=21,nama_siswa='Andi Pratama',
             nama_program='Matematika SMA',harga_bulanan=Decimal('250000'),
             invoice_jumlah=Decimal('250000'),invoice_status='lunas',payment_status='lunas',
             no_invoice='INV-20261126-0001',created_at=datetime(2026,11,26,8),status='menunggu')
FREE=dict(PROGRAM,enrollment_id=32,harga_bulanan=Decimal(0),
          invoice_status=None,payment_status=None,no_invoice=None,invoice_jumlah=None)


class FakeView:
    def __init__(self,answers):
        self.answers=iter(answers)
        self.events=[]
    async def busy(self,title,fn,*args):
        return fn(*args)
    async def page(self,title,choices,renderer,**kwargs):
        self.events.append((title,choices,kwargs))
        for row in renderer(100,30):
            assert len(row)<=30
        return next(self.answers)
    async def table(self,kind,items):
        self.events.append((kind,items))
        return next(self.answers)
    async def form(self,*args,**kwargs):
        self.events.append(('form',kwargs))
        return next(self.answers)
    async def result(self,*args):
        self.events.append(('result',args))


def controller(**updates):
    args=dict(summary=Mock(return_value=SUMMARY),accounts=Mock(return_value=[TUTOR,ACCOUNT]),
              enrollments=Mock(return_value=[PROGRAM,FREE]),account_detail=Mock(return_value=ACCOUNT),
              student_packages=Mock(return_value=[]),
              approve_account=Mock(return_value=(True,'Akun disetujui; NIS diterbitkan.')),
              reject_account=Mock(return_value=(True,'Akun ditolak.')),
              approve_enrollment=Mock(return_value=(True,'Pendaftaran aktif.')),
              reject_enrollment=Mock(return_value=(True,'Pendaftaran ditolak; refund tercatat.')),
              is_admin=Mock(return_value=True))
    args.update(updates)
    return ConfirmationController(**args)


class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_approve_account_exactly_once_and_reload(self):
        c=controller(accounts=Mock(side_effect=[[ACCOUNT],[]]))
        v=FakeView(['akun',21,'approve','confirm','back','back'])
        await c.run(v)
        c.approve_account.assert_called_once_with(21)
        c.accounts.assert_has_calls([unittest.mock.call(),unittest.mock.call()])
        self.assertEqual(c.accounts.call_count,2)
        c.reject_account.assert_not_called()
        self.assertTrue(any(event[0]=='result' and event[1][0]=='KEPUTUSAN TERSIMPAN' for event in v.events))

    async def test_default_cancel_and_no_write(self):
        c=controller()
        v=FakeView(['approve','back','back'])
        await c.detail(v,'akun',ACCOUNT)
        c.approve_account.assert_not_called()
        c.reject_account.assert_not_called()
        self.assertEqual(next(x[2]['default'] for x in v.events if x[0]=='KONFIRMASI KEPUTUSAN'),'back')

    async def test_reject_blank_reason_retry_then_service(self):
        c=controller()
        v=FakeView(['reject',{'reason':'   '},{'reason':'  Data tidak sesuai  '},'confirm'])
        await c.detail(v,'akun',ACCOUNT)
        c.reject_account.assert_called_once_with(21,'Data tidak sesuai')
        notes=[event[1]['notice'] for event in v.events if event[0]=='form']
        self.assertEqual(notes,['','Alasan penolakan wajib diisi.'])

    async def test_escape_reason_does_not_reject(self):
        c=controller()
        await c.detail(FakeView(['reject',None,'back']),'akun',ACCOUNT)
        c.reject_account.assert_not_called()

    async def test_unverified_and_stale_protected(self):
        c=controller(account_detail=Mock(return_value=dict(ACCOUNT,status='aktif')))
        v=FakeView([21,'back'])
        await c.queue(v,'akun')
        c.approve_account.assert_not_called()
        self.assertIn('ANTREAN BERUBAH',str(v.events))
        v=FakeView(['back'])
        await c.detail(v,'akun',dict(ACCOUNT,email_verified=False))
        self.assertEqual([key for key,_ in v.events[0][1]],['detail','back'])

    async def test_paid_and_free_enrollment_routes(self):
        c=controller()
        await c.detail(FakeView(['approve','confirm']),'program',FREE)
        c.approve_enrollment.assert_called_once_with(32)
        await c.detail(FakeView(['reject',{'reason':'Tidak sesuai'},'confirm']),'program',PROGRAM)
        c.reject_enrollment.assert_called_once_with(31,'Tidak sesuai')

    async def test_ambiguous_service_does_not_retry(self):
        c=controller(approve_account=Mock(side_effect=RuntimeError('private connection')))
        v=FakeView(['approve','confirm'])
        await c.detail(v,'akun',ACCOUNT)
        c.approve_account.assert_called_once_with(21)
        self.assertIn('HASIL BELUM DAPAT DIPASTIKAN',str(v.events))
        self.assertNotIn('private connection',str(v.events))

    async def test_failed_data_not_presented_as_empty(self):
        c=controller(accounts=Mock(side_effect=RuntimeError('database secret')))
        v=FakeView([])
        await c.queue(v,'akun')
        self.assertIn('DATA GAGAL DIMUAT',str(v.events))
        self.assertNotIn('database secret',str(v.events))

    async def test_role_check_before_write(self):
        c=controller(is_admin=Mock(side_effect=[True,False]))
        await c.detail(FakeView(['approve','confirm']),'akun',ACCOUNT)
        c.approve_account.assert_not_called()

    async def test_detail_with_packages_and_back(self):
        c=controller(student_packages=Mock(return_value=[dict(status='menunggu',kode_program='MTK',nama_program='Matematika',harga_bulanan=250000)]))
        await c.detail(FakeView(['detail','back','back']),'akun',ACCOUNT)
        c.student_packages.assert_called_once_with(21)


class RenderTests(unittest.TestCase):
    def test_priority_cards_and_corrected_label(self):
        body=text_of(priority_pages(Snapshot(SUMMARY,[]),100,40,set())[0])
        for title in ('KONFIRMASI AKUN','PENDAFTARAN SIAP ACC','TAGIHAN','PEMBAYARAN BULAN INI','PERLU TINDAKAN'):
            self.assertIn(title,body)
        self.assertNotIn('Konfirmasi pembayaran',body)
        self.assertIn('1.800.000',body)
        self.assertEqual(body.count('┌'),5)
        self.assertEqual(body.count('┘'),5)

    def test_width_and_height_and_no_markup(self):
        account=dict(ACCOUNT,nama_lengkap='漢字 '*50+'\x1b[31m',email='a'*240+'@example.test')
        for width in (38,48,60,78,100):
            for budget in (1,3,8,20,40):
                for pages in (priority_pages(Snapshot(SUMMARY,[]),width,budget,set()),
                              details_pages(account_sections(account,full=True),width,budget,full=True),
                              details_pages(enrollment_sections(PROGRAM),width,budget)):
                    for page in pages:
                        self.assertLessEqual(len(page),budget)
                        self.assertTrue(all(width_of(row)<=width for row in page))
                        self.assertNotIn('\x1b',text_of(page))
            for kind,record in (('akun',account),('program',PROGRAM)):
                self.assertLessEqual(width_of(table_row(kind,width,record,True)),width)
        self.assertEqual(''.join(wrap('x'*240,30)),'x'*240)

    def test_priority_keyboard_and_refresh(self):
        async def check(w,inp):
            inp.send_text('\r')
            await asyncio.sleep(.06)
            body='\n'.join(screen(w))
            self.assertIn('PUSAT PRIORITAS',body)
            self.assertIn('KONFIRMASI AKUN',body)
            self.assertIn('PENDAFTARAN SIAP ACC',body)
            inp.send_text('r')
            await asyncio.sleep(.12)
            self.assertIn('PUSAT PRIORITAS','\n'.join(screen(w)))
        loader=Mock(return_value=Snapshot(SUMMARY,[]))
        self.assertEqual(run_keys('\r',output=Output(40,180),check=check,loader=loader),'konfirmasi')
        self.assertEqual(loader.call_count,2)

    def test_navigator_restores_prioritas_after_module(self):
        from unittest.mock import patch
        nav=AdminDashboardNavigator()
        fake=Mock(snapshot=Snapshot(SUMMARY,[]))
        fake.run.side_effect=['konfirmasi','pembayaran','logout']
        with patch('app.ui.admin_workspace.AdminDashboardWorkspace',return_value=fake) as ctor:
            nav.choose('Jaya')
            nav.choose('Jaya')
            nav.choose('Jaya')
        self.assertEqual(ctor.call_args_list[1].kwargs['initial_group'],0)
        self.assertEqual(ctor.call_args_list[2].kwargs['initial_index'],2)

    def test_real_key_confirmation_table_and_cancel(self):
        selected=[]
        with create_pipe_input() as inp:
            view=ConfirmationWorkspace('Jaya',input=inp,output=Output(34,120),motion_enabled=False)
            async def flow(v):
                selected.append(await v.table('akun',[ACCOUNT,TUTOR]))
                selected.append(await v.page('KONFIRMASI KEPUTUSAN',[('confirm','Ya, lanjutkan'),('back','Batal')],
                                             lambda w,b:details_pages([('RINGKASAN',[('Nama','Dewi')])],w,b),default='back'))
            async def drive():
                try:
                    await asyncio.sleep(.08)
                    self.assertIn('ANTREAN KONFIRMASI AKUN','\n'.join(screen(view)))
                    self.assertIn('Andi Pratama','\n'.join(screen(view)))
                    inp.send_text('\x1b[B\r')
                    await asyncio.sleep(.08)
                    self.assertIn('KONFIRMASI KEPUTUSAN','\n'.join(screen(view)))
                    self.assertIn('❯      Batal','\n'.join(screen(view)))
                    inp.send_text('\r')
                except Exception as exc:
                    view.app.exit(exception=exc)
            async def combined(v):
                v.app.create_background_task(drive())
                return await flow(v)
            view.run(combined)
        self.assertEqual(selected,[22,'back'])

    def test_actual_rejection_form(self):
        with create_pipe_input() as inp:
            view=ConfirmationWorkspace('Jaya',input=inp,output=Output(24,80),motion_enabled=False)
            async def flow(v):
                from app.ui.auth_workspace import Field
                async def drive():
                    try:
                        await asyncio.sleep(.08)
                        self.assertIn('ALASAN PENOLAKAN','\n'.join(screen(v)))
                        inp.send_text('Data tidak sesuai\r')
                    except Exception as exc:
                        v.app.exit(exception=exc)
                v.app.create_background_task(drive())
                return await v.form('ALASAN PENOLAKAN',[Field('reason','Alasan penolakan')],
                                    hint='Alasan wajib diisi.',submit_label='Lanjutkan')
            self.assertEqual(view.run(flow),{'reason':'Data tidak sesuai'})


if __name__=='__main__':
    unittest.main()
