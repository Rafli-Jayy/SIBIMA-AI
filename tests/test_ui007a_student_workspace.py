"""UI-007A tests using service doubles; no database, Gemini, or SMTP."""
import ast
import asyncio
import sys
import unittest
from datetime import date,time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch,call
from prompt_toolkit.input import create_pipe_input

from app.ui.student_workspace import (
    StudentWorkspace,StudentSnapshot,StudentDashboardNavigator,load_snapshot,
    dashboard_pages,onboarding_pages,MENU,accessible,_attendance,
)
from app.ui.admin_workspace import width_of
from test_ui002_admin_workspace import Output,screen,text_of
from test_ui003b_enrollment import View

TODAY=date(2026,11,27)
USER={'id':22,'role':'siswa','status':'aktif','nama_lengkap':'Aulia Rahma','email_verified':True}
A={'enrollment_id':11,'program_id':1,'nama_program':'Matematika SMA','status':'aktif','akses_terkunci':False}
B=dict(A,enrollment_id=12,program_id=2,nama_program='Bahasa Inggris')
C=dict(A,enrollment_id=13,program_id=3,nama_program='Fisika')
LOCK=dict(A,enrollment_id=21,program_id=4,nama_program='Kimia',akses_terkunci=True)
PAY=dict(A,enrollment_id=31,program_id=5,nama_program='Biologi',status='menunggu_pembayaran')
PENDING=dict(A,enrollment_id=32,program_id=6,nama_program='Ekonomi',status='menunggu')
HISTORY=dict(A,enrollment_id=40,program_id=7,nama_program='Sejarah',status='selesai')
SCHEDULE=dict(program_id=1,hari='jumat',jam_mulai=time(15,30),jam_selesai=time(17),nama_program='Matematika SMA',nama_tutor='Dewi Anggraini',nama_ruang='Ruang A')
NEXT=dict(SCHEDULE,program_id=2,hari='sabtu',nama_program='Bahasa Inggris')
PRIVATE=dict(SCHEDULE,program_id=4,nama_program='KIMIA RAHASIA',nama_tutor='TUTOR RAHASIA')
ATTEND=[dict(enrollment_id=r['enrollment_id'],hadir=n,total_pertemuan=n+1) for r,n in [(A,6),(B,4),(C,4),(LOCK,999),(HISTORY,777)]]
GRADES=[dict(enrollment_id=r['enrollment_id'],nilai_akhir=n) for r,n in [(A,Decimal('87.5')),(B,Decimal('90.0')),(C,None),(LOCK,Decimal('999.0')),(HISTORY,Decimal('999.0'))]]
STATS=dict(kelas_aktif=999,pertemuan_hadir=999,rata_nilai_tercatat=999,
           tagihan_belum_lunas=1,jumlah_tagihan=Decimal('250000'),tagihan_terlambat=0)
CLEAR=dict(STATS,tagihan_belum_lunas=0,jumlah_tagihan=0)

def deps(**kw):
    args=dict(stats=Mock(return_value=STATS),schedules=Mock(return_value=(True,[SCHEDULE,NEXT,PRIVATE])),
              attendance=Mock(return_value=(True,ATTEND)),grades=Mock(return_value=(True,GRADES)),
              sync=Mock(return_value=None),unread=Mock(return_value=2))
    args.update(kw)
    return args

def fixture(enrollments=None,**kw):
    return load_snapshot(22,[A,B,C] if enrollments is None else enrollments,today=TODAY,**deps(**kw))

def all_text(pages):
    return '\n'.join(text_of(p) for p in pages)

class DataTests(unittest.TestCase):
    def test_existing_services_and_scope(self):
        args=deps()
        snap=load_snapshot(22,[A,B,C,LOCK,HISTORY],today=TODAY,**args)
        args['stats'].assert_called_once_with(22)
        for k in ('schedules','attendance','grades'):args[k].assert_called_once_with()
        args['sync'].assert_called_once_with('siswa')
        args['unread'].assert_called_once_with('siswa')
        self.assertEqual([r['program_id'] for r in snap.schedules],[1,2])
        self.assertEqual([r['enrollment_id'] for r in snap.grades],[11,12,13])
        self.assertEqual([r['enrollment_id'] for r in snap.attendance],[11,12,13])
        self.assertNotIn('rata_nilai_tercatat',snap.stats)
        self.assertNotIn('pertemuan_hadir',snap.stats)
        text=all_text(dashboard_pages(snap,100,40))
        for term in ('14','87.5','terkunci','Rp250.000','2 notifikasi belum dibaca'):
            self.assertIn(term,text)
        for term in ('KIMIA RAHASIA','TUTOR RAHASIA','999','777'):
            self.assertNotIn(term,text)

    def test_no_academic_reads_when_not_accessible(self):
        for rows in ([],[PAY],[PENDING],[LOCK],[HISTORY],[dict(A,akses_terkunci=None)]):
            args=deps()
            snap=load_snapshot(22,rows,today=TODAY,**args)
            for key in ('schedules','attendance','grades'):args[key].assert_not_called()
            self.assertEqual(_attendance(snap)[0],'—')
            self.assertFalse(snap.schedules)
            self.assertNotIn('RAHASIA',all_text(dashboard_pages(snap,100,40)))

    def test_failed_loads_distinct(self):
        def fail(*args):raise OSError('PRIVATE ERROR')
        snap=fixture(stats=fail,schedules=Mock(return_value=(False,'PRIVATE ERROR')),
                     attendance=fail,grades=fail,sync=fail,unread=fail)
        text=all_text(dashboard_pages(snap,100,40))
        for term in ('Jadwal gagal dimuat','Rekap gagal dimuat','Ringkasan tagihan gagal dimuat','Notifikasi belum tersedia','Data belum lengkap'):
            self.assertIn(term,text)
        self.assertNotIn('PRIVATE ERROR',text)

    def test_notification_sync_failure_does_not_hide_available_count(self):
        snap=fixture(sync=Mock(side_effect=OSError()))
        self.assertEqual(snap.unread,2)
        self.assertFalse(snap.sync_ok)
        self.assertIn('Data belum lengkap',all_text(dashboard_pages(snap,100,40)))

    def test_partial_attendance_is_not_counted_as_total(self):
        snap=fixture(attendance=Mock(return_value=(True,[ATTEND[0]])))
        self.assertEqual(_attendance(snap),('—','Rekap belum lengkap'))

class RenderTests(unittest.TestCase):
    def test_adaptive_states(self):
        cases=[
            ([],['MULAI BELAJAR','Kamu belum memiliki kelas']),
            ([PAY],['menunggu pembayaran pertama','Menunggu bayar']),
            ([PENDING],['menunggu persetujuan Admin','Menunggu Admin']),
            ([LOCK],['terkunci H+3','Belum ada akses kelas']),
            ([HISTORY],['Riwayat sebelumnya tetap']),
            ([dict(A,akses_terkunci=None)],['Status akses belum pasti']),
            ([dict(A,status='ditangguhkan')],['pendaftaran ditangguhkan']),
            ([A,B,C],['Matematika SMA','15:30','87.5','14']),
        ]
        for rows,expected in cases:
            text=all_text(dashboard_pages(fixture(rows),100,40))
            for term in expected:self.assertIn(term,text)

    def test_schedule_states_and_next_routine(self):
        no_schedule=fixture(schedules=Mock(return_value=(True,[])))
        self.assertIn('Belum ada jadwal rutin',all_text(dashboard_pages(no_schedule,100,40)))
        next_schedule=fixture(schedules=Mock(return_value=(True,[NEXT])))
        text=all_text(dashboard_pages(next_schedule,100,40))
        self.assertIn('Tidak ada jadwal rutin hari ini',text)
        self.assertIn('Berikutnya (perkiraan)',text)
        self.assertIn('28/11',text)

    def test_bounds_including_narrow_and_long(self):
        long=dict(A,nama_program='漢字'*100)
        for rows in ([],[PAY],[PENDING],[LOCK],[A,B,C,LOCK,PAY,PENDING],[long]):
            snap=fixture(rows)
            for w in (8,18,30,46,64,78,100):
                for b in (1,2,4,8,16,40):
                    for pages in (dashboard_pages(snap,w,b),onboarding_pages(rows,w,b)):
                        for p in pages:
                            self.assertLessEqual(len(p),b,(w,b))
                            self.assertTrue(all(width_of(r)<=w for r in p),(w,b,p))

    def test_onboarding_does_not_offer_enrollment(self):
        for rows in ([],[PENDING],[A],[PENDING,A]):
            text=all_text(onboarding_pages(rows,100,40))
            self.assertIn('MENUNGGU PERSETUJUAN ADMIN',text)
            self.assertIn('NIS diterbitkan setelah akun disetujui',text)
            self.assertNotIn('Buka Katalog Program',text)
        self.assertIn('PERLU PEMERIKSAAN',all_text(onboarding_pages([A],100,40)))

class NavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_routes_focus_and_refresh(self):
        c=StudentDashboardNavigator(load=Mock(return_value=fixture()))
        v=View(['jadwal','refresh','ai'])
        self.assertEqual(await c.choose(v,USER,[A]),'jadwal')
        c.focus='jadwal'
        v.refresh_focus='pembayaran'
        self.assertEqual(await c.choose(v,USER,[A]),'refresh')
        self.assertEqual(c.focus,'pembayaran')
        self.assertEqual(await c.choose(v,USER,[A]),'ai')
        expected={k for k,_ in MENU}
        self.assertEqual({k for k,_ in v.events[0][1]},expected)
        self.assertIn(('notifikasi','Notifikasi (2 belum dibaca)'),v.events[0][1])
        self.assertEqual(v.events[1][2]['default'],'jadwal')
        self.assertEqual(v.events[2][2]['default'],'pembayaran')

class KeyboardTests(unittest.TestCase):
    def test_real_student_workspace_menu_and_refresh(self):
        for keys,expected in [('\r','katalog'),('\x1b[A\r','logout'),('r','refresh'),('\x1b[B'*8+'\r','ai')]:
            c=StudentDashboardNavigator(load=Mock(return_value=fixture()))
            with create_pipe_input() as inp:
                view=StudentWorkspace('Aulia Rahma',input=inp,output=Output(38,108),motion_enabled=False)
                async def drive():
                    try:
                        for _ in range(200):
                            if view.title=='PUSAT AKTIVITAS BELAJAR' and view.mode=='menu':
                                await asyncio.sleep(.06);break
                            await asyncio.sleep(.01)
                        text='\n'.join(screen(view))
                        self.assertIn('Aulia Rahma · Siswa',text)
                        self.assertIn('Logout',text)
                        self.assertIn('SIBIMA-AI',text)
                        self.assertNotIn('· Admin',text)
                        self.assertIn('KELAS AKTIF',text)
                        inp.send_text(keys)
                    except Exception as exc:view.app.exit(exception=exc)
                async def main(v):
                    v.app.create_background_task(drive())
                    return await c.choose(v,USER,[A,B,C])
                self.assertEqual(view.run(main),expected)

    def test_onboarding_actual_keys(self):
        with create_pipe_input() as inp:
            view=StudentWorkspace('Aulia Rahma',input=inp,output=Output(24,80),motion_enabled=False)
            async def drive():
                try:
                    await asyncio.sleep(.1)
                    text='\n'.join(screen(view))
                    self.assertIn('MENUNGGU PERSETUJUAN ADMIN',text)
                    self.assertIn('Logout',text)
                    self.assertNotIn('Katalog Program',text)
                    inp.send_text('\r')
                except Exception as exc:view.app.exit(exception=exc)
            async def main(v):
                v.app.create_background_task(drive())
                return await v.page('PENYELESAIAN PENDAFTARAN SISWA',[('refresh','Periksa status persetujuan akun'),('logout','Logout')],
                                    lambda w,b:onboarding_pages([],w,b),default='refresh')
            self.assertEqual(view.run(main),'refresh')

class IntegrationTests(unittest.TestCase):
    def build(self,*names,**env):
        p=Path(__file__).resolve().parents[1]/'app/ui/menu_siswa.py'
        tree=ast.parse(p.read_text(encoding='utf8'))
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),env)
        return env

    def test_legacy_routes_notification_targets_ai_logout_and_reload(self):
        routes=[k for k,_ in MENU if k not in ('refresh','logout','notifikasi')]
        seq=routes+['notifikasi']*5+['refresh','logout']
        calls=[]
        def record(k):return lambda *a,**kw:calls.append(k)
        navigator=Mock()
        navigator.run.side_effect=seq
        session=SimpleNamespace(logout=record('logout'))
        env=self.build('jalankan',StudentDashboardNavigator=Mock(return_value=navigator),
             _pengguna_siswa=lambda:USER,_ambil_pendaftaran=Mock(return_value=[A]),
             psycopg=SimpleNamespace(Error=OSError),session=session,gagal=Mock(),sukses=Mock(),_jeda=Mock(),
             menu_katalog=record('katalog'),
             menu_siswa_academic=SimpleNamespace(menu_kelas_saya=record('pendaftaran'),menu_jadwal_saya=record('jadwal'),
                 menu_absensi_siswa=record('absensi'),menu_nilai_rapor=record('nilai'),
                 menu_catatan_materi=record('materi'),menu_profil_siswa=record('profil')),
             menu_pembayaran=SimpleNamespace(menu_pembayaran_siswa=record('pembayaran')),
             menu_notifikasi=SimpleNamespace(jalankan=Mock(side_effect=['nilai','absensi','jadwal','pembayaran','pendaftaran'])))
        with patch.dict(sys.modules,{'app.services.ai_service':SimpleNamespace(buka_ai=record('ai'))}):
            env['jalankan']()
        self.assertEqual(calls,routes+['nilai','absensi','jadwal','pembayaran','pendaftaran','logout'])
        self.assertEqual(env['_ambil_pendaftaran'].call_args_list,[call(22)]*len(seq))
        self.assertEqual(env['menu_notifikasi'].jalankan.call_args_list,[call('siswa')]*5)

    def test_pending_onboarding_refresh_to_approved(self):
        pending=dict(USER,status='menunggu_konfirmasi')
        sess=Mock()
        opts=Mock(return_value='refresh')
        users=Mock(side_effect=[pending,USER])
        env=self.build('_jalankan_onboarding',user_repo=SimpleNamespace(cari_by_id=users),
             enrollment_repo=SimpleNamespace(enrollment_siswa=Mock(return_value=[])),
             session=sess,pilih_onboarding_siswa=opts,psycopg=SimpleNamespace(Error=OSError))
        self.assertTrue(env['_jalankan_onboarding'](pending))
        opts.assert_called_once_with(pending,[])
        sess.set_user.assert_has_calls([call(pending),call(USER)])
        sess.logout.assert_not_called()

    def test_pending_rejected_and_pending_logout(self):
        pending=dict(USER,status='menunggu_konfirmasi')
        for actual,choice in [(pending,'logout'),(dict(pending,status='ditolak',reject_reason='Verifikasi Admin'),'refresh')]:
            sess=Mock();opts=Mock(return_value=choice);show=Mock()
            env=self.build('_jalankan_onboarding',user_repo=SimpleNamespace(cari_by_id=Mock(return_value=actual)),
                enrollment_repo=SimpleNamespace(enrollment_siswa=Mock(return_value=[])),session=sess,
                pilih_onboarding_siswa=opts,tampilkan_status_akun=show,psycopg=SimpleNamespace(Error=OSError),
                sukses=Mock(),_jeda=Mock())
            self.assertFalse(env['_jalankan_onboarding'](pending))
            sess.logout.assert_called_once()
            if actual['status']=='ditolak':
                opts.assert_not_called()
                show.assert_called_once_with(actual,'Verifikasi Admin')

if __name__=='__main__':unittest.main()
