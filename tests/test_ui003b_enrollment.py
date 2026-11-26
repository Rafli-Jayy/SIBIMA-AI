"""UI-003B regression tests with injected services; no database mutations."""
import asyncio
import re
import unittest
from unittest.mock import Mock,call
from datetime import datetime
from decimal import Decimal
from prompt_toolkit.input import create_pipe_input
from test_ui002_admin_workspace import Output, screen, text_of, SUMMARY
from app.ui.admin_workspace import width_of
from app.ui.admin_confirmation import ConfirmationWorkspace, details_pages
from app.ui.admin_enrollment import (
    EnrollmentController,STATUS_LABELS,dashboard_pages,enrollment_row,program_row,
    filter_program_row,detail_sections,eligible_destinations,move_sections,cancel_sections,
)

STATS={**SUMMARY,'enrollment_menunggu':2,'enrollment_ditolak':1,'enrollment_batal':3}
ACTIVE=dict(enrollment_id=31,student_id=21,program_id=1,nama_siswa='Andi Pratama',
            nis='S-0021',username='andipratama',email='andi@example.test',status_akun='aktif',
            nama_program='Matematika SMA',kode_program='MTK',jenjang='SMA',
            harga_bulanan=Decimal('250000'),status='aktif',jumlah_tagihan=3,
            total_tagihan=Decimal('750000'),total_terbayar=Decimal('500000'),
            created_at=datetime(2026,11,26,8))
WAITING=dict(ACTIVE,enrollment_id=32,status='menunggu',total_terbayar=Decimal('0'))
PAID_WAITING=dict(WAITING,total_terbayar=Decimal('250000'))
ORIGIN=dict(id=1,kode='MTK',nama='Matematika SMA',jenjang='SMA',harga_bulanan=250000,kuota=20,sisa=5,status='buka')
TARGET=dict(ORIGIN,id=2,kode='ING',nama='Bahasa Inggris',harga_bulanan=300000,sisa=8)
FULL=dict(TARGET,id=3,sisa=0)
CLOSED=dict(TARGET,id=4,status='tutup')
SEEN=dict(TARGET,id=5)
PROGRAMS=[ORIGIN,TARGET,FULL,CLOSED,SEEN]


class View:
    def __init__(self,answers):
        self.answers=iter(answers)
        self.events=[]
    async def busy(self,title,fn,*args):
        return fn(*args)
    async def page(self,title,choices,renderer,**kwargs):
        self.events.append((title,list(choices),kwargs,renderer(100,40)))
        return next(self.answers)
    async def record_table(self,title,items,**kwargs):
        self.events.append((title,list(items),kwargs))
        return next(self.answers)
    async def form(self,title,fields,**kwargs):
        self.events.append((title,list(fields),kwargs))
        return next(self.answers)
    async def result(self,*args):
        self.events.append(('result',args))


def make_controller(**kwargs):
    def list_rows(status,program_id):
        records=[ACTIVE,WAITING]
        return True,[x for x in records if (status is None or x['status']==status)
                     and (program_id is None or x['program_id']==program_id)]
    def detail(n):
        return True,ACTIVE if n==31 else WAITING
    args=dict(summary=Mock(return_value=STATS),list_enrollments=Mock(side_effect=list_rows),
              detail=Mock(side_effect=detail),programs=Mock(return_value=PROGRAMS),
              programs_quota=Mock(return_value=PROGRAMS),
              history=Mock(return_value=[{'program_id':1},{'program_id':5}]),
              move=Mock(return_value=(True,'Pendaftaran dipindahkan.')),
              cancel=Mock(return_value=(True,'Refund simulasi tercatat.')),
              is_admin=Mock(return_value=True))
    args.update(kwargs)
    return EnrollmentController(**args)


class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_refresh_after_return_from_action(self):
        c=make_controller(summary=Mock(side_effect=[STATS,dict(STATS,enrollment_aktif=17)]))
        v=View(['move',31,2,'confirm','back'])
        await c.run(v)
        c.move.assert_called_once_with(31,2)
        self.assertEqual(c.summary.call_count,2)
        dashboards=[e for e in v.events if e[0]=='MANAJEMEN PENDAFTARAN']
        self.assertEqual(dashboards[1][2]['default'],'move')
        self.assertTrue(any(style=='class:success' and value.strip()=='17'
            for page in dashboards[1][3] for row in page for style,value in row))

    async def test_filter_all_six_statuses_and_retain_on_detail(self):
        c=make_controller()
        v=View(['menunggu_pembayaran',1,'filter','aktif',1,31,'back','refresh','back'])
        await c.browse(v)
        self.assertEqual(c.list_enrollments.call_args_list,[
            call('menunggu_pembayaran',1),call('aktif',1),call('aktif',1),call('aktif',1)])
        c.load_detail.assert_called_once_with(31)
        filters=[e for e in v.events if e[0]=='FILTER STATUS PENDAFTARAN']
        self.assertEqual({key for key,_ in filters[0][1]},set(STATUS_LABELS)|{'all','back'})
        self.assertEqual(filters[1][2]['default'],'menunggu_pembayaran')
        tables=[e for e in v.events if e[0]=='DAFTAR PENDAFTARAN']
        self.assertEqual(tables[-1][2]['initial'],31)
        self.assertTrue(tables[-1][2]['filter_action'])

    async def test_move_eligible_target_only_and_exact_service_call(self):
        c=make_controller()
        v=View([31,2,'confirm'])
        await c.move_flow(v)
        c.list_enrollments.assert_called_once_with('aktif',None)
        c.move.assert_called_once_with(31,2)
        dest=next(e for e in v.events if e[0]=='PILIH PROGRAM TUJUAN')
        self.assertEqual([p['id'] for p in dest[1]],[2])
        review=next(e for e in v.events if e[0]=='KONFIRMASI PEMINDAHAN')
        self.assertEqual(review[2]['default'],'back')
        text='\n'.join(text_of(p) for p in review[3])
        for word in ('Matematika SMA','Bahasa Inggris','Rp250.000','Rp300.000','Refund / prorata','tanpa tagihan kedua'):
            self.assertIn(word,text)

    async def test_move_cancel_preserves_data(self):
        c=make_controller()
        await c.move_flow(View([31,2,'back',None]))
        c.move.assert_not_called()

    async def test_move_no_eligible_target_no_service(self):
        c=make_controller(programs_quota=Mock(return_value=[ORIGIN,FULL,CLOSED,SEEN]))
        v=View([31,'back'])
        await c.move_flow(v)
        c.move.assert_not_called()
        self.assertEqual(next(e for e in v.events if e[0]=='PILIH PROGRAM TUJUAN')[1],[])

    async def test_cancel_active_reason_and_financial_review(self):
        c=make_controller()
        v=View([31,{'reason':'  Pindah kota  '},'confirm'])
        await c.cancel_flow(v)
        c.cancel.assert_called_once_with(31,'Pindah kota')
        self.assertEqual(c.list_enrollments.call_args_list,[call('menunggu',None),call('aktif',None)])
        review=next(e for e in v.events if e[0]=='KONFIRMASI PEMBATALAN')
        self.assertEqual(review[2]['default'],'back')
        text='\n'.join(text_of(p) for p in review[3])
        for word in ('Rp500.000','Dibatalkan','Pindah kota','Simulasi internal'):
            self.assertIn(word,text)

    async def test_cancel_optional_reason_and_1000_limit(self):
        c=make_controller()
        v=View([32,{'reason':'x'*1001},{'reason':''},'confirm'])
        await c.cancel_flow(v)
        c.cancel.assert_called_once_with(32,'')
        forms=[e for e in v.events if e[0]=='ALASAN PEMBATALAN']
        self.assertEqual(forms[1][2]['notice'],'Alasan maksimal 1000 karakter.')

    async def test_cancel_paid_pending_routes_to_confirmation_not_write(self):
        c=make_controller(detail=Mock(return_value=(True,PAID_WAITING)))
        v=View([32])
        await c.cancel_flow(v)
        c.cancel.assert_not_called()
        self.assertIn('GUNAKAN PUSAT KONFIRMASI',str(v.events))

    async def test_cancel_skip_form_or_confirm_means_no_write(self):
        c=make_controller()
        await c.cancel_flow(View([31,None]))
        await c.cancel_flow(View([31,{'reason':'Batal'},'back']))
        c.cancel.assert_not_called()

    async def test_missing_amount_not_assumed_zero(self):
        c=make_controller(detail=Mock(return_value=(True,dict(ACTIVE,total_terbayar=None))))
        v=View([31])
        await c.cancel_flow(v)
        c.cancel.assert_not_called()
        self.assertIn('DATA BELUM LENGKAP',str(v.events))

    async def test_stale_status_reloads_before_action(self):
        c=make_controller(detail=Mock(return_value=(True,dict(ACTIVE,status='selesai'))))
        v=View([31,None])
        await c.move_flow(v)
        c.move.assert_not_called()
        self.assertIn('DATA BERUBAH',str(v.events))

    async def test_service_error_caught_no_retry(self):
        c=make_controller(move=Mock(side_effect=RuntimeError('secret')))
        v=View([31,2,'confirm'])
        await c.move_flow(v)
        c.move.assert_called_once_with(31,2)
        self.assertIn('HASIL BELUM DAPAT DIPASTIKAN',str(v.events))
        self.assertNotIn('secret',str(v.events))

    async def test_role_recheck_before_write(self):
        c=make_controller(is_admin=Mock(return_value=False))
        v=View([])
        await c._write(v,'move',c.move,31,2)
        c.move.assert_not_called()


class RenderTests(unittest.TestCase):
    def test_dashboard_geometry(self):
        pages=dashboard_pages(STATS,100,25)
        body=text_of(pages[0])
        self.assertEqual(body.count('┌'),2)
        self.assertEqual(body.count('┘'),2)
        self.assertIn('PENDAFTARAN BERJALAN',body)
        self.assertIn('RIWAYAT PENDAFTARAN',body)
        self.assertIn('Menunggu pembayaran',body)
        self.assertIn('Data terakhir dimuat',body)
        self.assertIn('Data belum lengkap','\n'.join(text_of(p) for p in dashboard_pages(None,78,30)))

    def test_width_height_unicode_and_all_details(self):
        long=dict(ACTIVE,nama_siswa='漢字 '*100,email='a'*300,alasan_tolak='L'*900)
        for width in (38,48,60,78,92,100):
            for render,row in ((enrollment_row,long),(program_row,TARGET),(filter_program_row,TARGET)):
                self.assertLessEqual(width_of(render(width,row,True)),width)
                self.assertLessEqual(width_of(render(width)),width)
            for budget in (1,5,16,40):
                for pages in (dashboard_pages(STATS,width,budget),
                    details_pages(detail_sections(long),width,budget,full=True,paired=True),
                    details_pages(move_sections(ACTIVE,TARGET,ORIGIN),width,budget,full=True,paired=True),
                    details_pages(cancel_sections(ACTIVE,'L'*800),width,budget,full=True,paired=True)):
                    for page in pages:
                        self.assertLessEqual(len(page),budget)
                        self.assertTrue(all(width_of(row)<=width for row in page))
                    self.assertTrue(pages)
        rendered='\n'.join(text_of(p) for p in details_pages(detail_sections(long),100,40,full=True,paired=True))
        self.assertEqual(sum(len(run) for run in re.findall(r'L{2,}',rendered)),900)
        self.assertEqual(rendered.count('a')>=300,True)

    def test_filter_keyboard_on_table_including_empty(self):
        def run(items):
            with create_pipe_input() as inp:
                view=ConfirmationWorkspace('Jaya',input=inp,output=Output(24,80),motion_enabled=False)
                async def flow(v):
                    async def drive():
                        try:
                            await asyncio.sleep(.08)
                            body='\n'.join(screen(v))
                            self.assertIn('DAFTAR PENDAFTARAN',body)
                            self.assertIn('F Filter',body)
                            inp.send_text('f')
                        except Exception as e:
                            v.app.exit(exception=e)
                    v.app.create_background_task(drive())
                    return await v.record_table('DAFTAR PENDAFTARAN',items,key='enrollment_id',
                        renderer=enrollment_row,caption='Aktif · Semua program',filter_action=True)
                return view.run(flow)
        self.assertEqual(run([ACTIVE]),'filter')
        self.assertEqual(run([]),'filter')

    def test_table_selection_preserved_and_default_cancel_real_keys(self):
        with create_pipe_input() as inp:
            view=ConfirmationWorkspace('Jaya',input=inp,output=Output(32,120),motion_enabled=False)
            selected=[]
            async def flow(v):
                async def drive():
                    try:
                        await asyncio.sleep(.07)
                        self.assertIn('❯ 32','\n'.join(screen(v)))
                        inp.send_text('\r')
                        await asyncio.sleep(.08)
                        self.assertIn('KONFIRMASI PEMBATALAN','\n'.join(screen(v)))
                        self.assertIn('❯      Batal','\n'.join(screen(v)))
                        inp.send_text('\r')
                    except Exception as e:
                        v.app.exit(exception=e)
                v.app.create_background_task(drive())
                selected.append(await v.record_table('DAFTAR PENDAFTARAN',[ACTIVE,WAITING],
                    key='enrollment_id',renderer=enrollment_row,caption='Semua status',initial=32))
                selected.append(await v.page('KONFIRMASI PEMBATALAN',[('confirm','Ya, batalkan'),('back','Batal')],
                    lambda w,b:details_pages(cancel_sections(ACTIVE,''),w,b,full=True,paired=True),default='back'))
            view.run(flow)
        self.assertEqual(selected,[32,'back'])


if __name__=='__main__':
    unittest.main()
