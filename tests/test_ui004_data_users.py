"""UI-004: covers every legacy route using simulated users, never a real database."""
import asyncio
import unittest
from datetime import datetime
from unittest.mock import Mock, call
from prompt_toolkit.input import create_pipe_input
from app.ui.admin_users import (DataUsersController, MENUS, account_metrics, profile_metrics,
    account_row, profile_row, dashboard_pages, history_row, program_row, account_sections, profile_sections)
from app.ui.admin_confirmation import ConfirmationWorkspace, details_pages
from app.ui.admin_workspace import width_of, AdminDashboardWorkspace, Snapshot
from test_ui002_admin_workspace import Output, screen, text_of, SUMMARY
from test_ui003b_enrollment import View

NOW=datetime(2026,11,26,10)
BASE=dict(email_verified=True,created_at=NOW,last_login=NOW,locked_until=None,failed_attempts=0,must_change_password=False)
STUDENT=dict(BASE,id=21,username='andi',email='andi@example.test',nama_lengkap='Andi Pratama',role='siswa',status='aktif',nis='S-0021',kode_tutor=None)
PENDING=dict(STUDENT,id=22,username='nadia',email='nadia@example.test',nama_lengkap='Nadia Putri',status='menunggu_konfirmasi',nis=None)
TUTOR=dict(BASE,id=31,username='dewi',email='dewi@example.test',nama_lengkap='Dewi Lestari',role='tutor',status='aktif',kode_tutor='T-0031',nis=None,failed_attempts=3,locked_until=NOW)
OFF=dict(TUTOR,id=32,username='raka',email='raka@example.test',nama_lengkap='Raka Wijaya',status='nonaktif',kode_tutor='T-0032',locked_until=None,failed_attempts=0)
ADMIN=dict(BASE,id=1,username='jaya',email='admin@example.test',nama_lengkap='Jaya',role='admin',status='aktif',nis=None,kode_tutor=None)
USERS=[STUDENT,PENDING,TUTOR,OFF,ADMIN]
SISWA=dict(STUDENT,user_id=21,jenjang='SMA',sekolah='SMA Negeri 1',no_hp='081234567890',nama_wali='Budi Pratama',program='Matematika SMA, Bahasa Inggris')
WAITING=dict(PENDING,user_id=22,jenjang='SMP',sekolah='SMP Negeri 2',no_hp=None,nama_wali=None,program='Belum ada program')
TUTOR_PROFILE=dict(TUTOR,user_id=31,keahlian='Matematika dan Fisika',no_hp='081234567891',jumlah_jadwal=2,program='Matematika SMA, Fisika SMA')
TUTOR_OFF=dict(OFF,user_id=32,keahlian='Bahasa Inggris',jumlah_jadwal=0,program='Belum ada jadwal')
HISTORY=[dict(enrollment_id=71,nama_program='Matematika SMA',status='aktif',created_at=NOW,processed_at=NOW),
         dict(enrollment_id=72,nama_program='Bahasa Inggris',status='menunggu',created_at=NOW,processed_at=None)]
SCHEDULES=[dict(id=81,kode_program='MTK',nama_program='Matematika SMA',hari='senin',jam_mulai='08:00',jam_selesai='09:30',ruang='Ruang A',aktif=True),
           dict(id=82,kode_program='FIS',nama_program='Fisika SMA',hari='selasa',jam_mulai='10:00',jam_selesai='11:30',ruang='Ruang B',aktif=False)]
PROGRAMS=[dict(id=1,kode='MTK',nama='Matematika SMA',status='buka'),dict(id=2,kode='ING',nama='Bahasa Inggris',status='buka')]
def make_controller(**overrides):
    def account_list(role=None,status=None):
        return [r for r in USERS if (role is None or r['role']==role) and (status is None or r['status']==status)]
    def student_list(jenjang=None,program_id=None,status=None,cari=None):
        return [r for r in (SISWA,WAITING) if (jenjang is None or r['jenjang']==jenjang)
                and (program_id is None or (r['user_id']==21 and program_id==1))
                and (status is None or r['status']==status)
                and (not cari or cari.lower() in (r['nama_lengkap']+' '+(r.get('nis') or '')).lower())]
    args=dict(accounts=Mock(side_effect=account_list),students=Mock(side_effect=student_list),
        tutors=Mock(return_value=[TUTOR_PROFILE,TUTOR_OFF]),student_detail=Mock(side_effect=lambda n:SISWA if n==21 else WAITING),
        tutor_detail=Mock(return_value=TUTOR_PROFILE),history=Mock(return_value=HISTORY),
        schedules=Mock(return_value=SCHEDULES),programs=Mock(return_value=PROGRAMS),
        status_update=Mock(return_value=(True,'Status diperbarui.')),unlock=Mock(return_value=(True,'Kunci dibuka.')),
        reset=Mock(return_value=(True,'Reset berhasil.','Demo-password123')),
        student_update=Mock(return_value=(True,'Profil disimpan.')),tutor_update=Mock(return_value=(True,'Profil disimpan.')),
        is_admin=Mock(return_value=True),current_id=1)
    args.update(overrides)
    return DataUsersController(**args)

class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_group_menu_routes_and_refresh_parent(self):
        c=make_controller()
        v=View(['akun','back','siswa','back','tutor','back','back'])
        await c.run(v)
        roots=[e for e in v.events if e[0]=='PUSAT DATA PENGGUNA']
        self.assertEqual([e[2]['default'] for e in roots],['akun','akun','siswa','tutor'])
        self.assertEqual(c.accounts.call_count,5)
        for kind,(title,choices) in MENUS.items():
            menu=next(e for e in v.events if e[0]==title)
            self.assertEqual(menu[1],choices+[('refresh','Muat ulang'),('back','Kembali ke Data Pengguna')])
        self.assertEqual(sum(len(choices) for _,choices in MENUS.values()),14)

    async def test_account_filter_and_detail_with_retained_selection(self):
        c=make_controller()
        v=View(['all','aktif',21,'back','filter','tutor','all','back'])
        await c.browse_accounts(v)
        self.assertEqual(c.accounts.call_args_list,[call(None,'aktif'),call(None,'aktif'),call('tutor',None)])
        tables=[e for e in v.events if e[0]=='DAFTAR AKUN']
        self.assertEqual(tables[1][2]['initial'],21)
        self.assertEqual([r['id'] for r in tables[-1][1]],[31,32])
        self.assertIn('Email terverifikasi','\n'.join(text_of(p) for p in next(e for e in v.events if e[0]=='DETAIL AKUN')[3]))

    async def test_status_account_active_and_nonactive_calls(self):
        for user_id,target in [(21,'nonaktif'),(32,'aktif')]:
            c=make_controller()
            v=View([user_id,'confirm','back'])
            await c.account_action(v,'status')
            c.status_update.assert_called_once_with(user_id,target)
            self.assertEqual([r['id'] for r in v.events[0][1]],[21,31,32])
            self.assertEqual(v.events[1][2]['default'],'back')

    async def test_unlock_eligible_and_reset_account_cancel(self):
        c=make_controller()
        v=View([31,'confirm','back'])
        await c.account_action(v,'unlock')
        c.unlock.assert_called_once_with(31)
        self.assertEqual([r['id'] for r in v.events[0][1]],[31])
        await c.account_action(View([21,'back','back']),'reset')
        c.reset.assert_not_called()

    async def test_reset_one_time_result_and_exclude_self(self):
        c=make_controller()
        v=View([21,'confirm','back','back'])
        await c.account_action(v,'reset')
        c.reset.assert_called_once_with(21)
        self.assertNotIn(1,[r['id'] for r in v.events[0][1]])
        pages=[e for e in v.events if e[0]=='RESET PASSWORD BERHASIL']
        self.assertEqual(len(pages),1)
        self.assertIn('Demo-password123','\n'.join(text_of(p) for p in pages[0][3]))
        self.assertNotIn('Demo-password123',str(v.events[1]))

    async def test_unknown_write_does_not_retry_or_expose_exception(self):
        c=make_controller(unlock=Mock(side_effect=RuntimeError('private')))
        v=View([31,'confirm','back'])
        await c.account_action(v,'unlock')
        c.unlock.assert_called_once_with(31)
        self.assertIn('HASIL BELUM DAPAT DIPASTIKAN',str(v.events))
        self.assertNotIn('private',str(v.events))

    async def test_siswa_search_and_filters_call_existing_api(self):
        c=make_controller()
        v=View([{'cari':'Andi'},'back'])
        await c.browse_profiles(v,'siswa','cari')
        c.students.assert_called_once_with(None,None,None,'Andi')
        self.assertEqual([r['user_id'] for r in v.events[-1][1]],[21])
        c=make_controller()
        v=View([{'jenjang':'SMA'},'choose',1,'aktif','back'])
        await c.browse_profiles(v,'siswa','filter')
        c.students.assert_called_once_with('SMA',1,'aktif',None)

    async def test_siswa_detail_history_detail_and_back(self):
        c=make_controller()
        v=View([21,'related',71,'back','back','back','back'])
        await c.browse_profiles(v,'siswa','detail')
        self.assertEqual(c.student_detail.call_count,3)
        self.assertEqual(c.history.call_args_list,[call(21),call(21)])
        details=next(e for e in v.events if e[0]=='DETAIL SISWA')
        self.assertIn('Budi Pratama','\n'.join(text_of(p) for p in details[3]))
        self.assertIn('DETAIL PROGRAM',str(v.events))

    async def test_tutor_schedule_includes_active_and_inactive(self):
        c=make_controller()
        v=View([31,'related',82,'back','back','back','back'])
        await c.browse_profiles(v,'tutor','detail')
        c.tutor_detail.assert_called_once_with(31)
        self.assertEqual(c.schedules.call_args_list,[call(31),call(31)])
        e=next(e for e in v.events if e[0]=='JADWAL MENGAJAR TUTOR')
        self.assertEqual(len(e[1]),2)
        self.assertIn('Nonaktif','\n'.join(text_of(p) for p in next(e for e in v.events if e[0]=='DETAIL JADWAL')[3]))

    async def test_edit_student_two_steps_prefill_and_optional_clear(self):
        c=make_controller()
        data1={'nama_lengkap':'Andi Baru','jenjang':'SMA','sekolah':''}
        data2={'no_hp':'','nama_wali':'Budi'}
        v=View([21,data1,data2,'confirm','back'])
        await c.profile_action(v,'siswa','ubah')
        c.student_update.assert_called_once_with(21,dict(data1,**data2))
        forms=[e for e in v.events if e[0]=='UBAH PROFIL SISWA']
        self.assertEqual(forms[0][1][0].default,'Andi Pratama')
        self.assertEqual(forms[1][1][0].default,'081234567890')
        preview=next(e for e in v.events if e[0]=='KONFIRMASI UBAH PROFIL')
        self.assertEqual(preview[2]['default'],'back')
        self.assertIn('Dikosongkan','\n'.join(text_of(p) for p in preview[3]))

    async def test_tutor_edit_validation_cancel_and_confirm(self):
        c=make_controller()
        bad={'nama_lengkap':'','keahlian':'Fisika','no_hp':''}
        good=dict(bad,nama_lengkap='Dewi Baru')
        v=View([31,bad,good,'back','back'])
        await c.profile_action(v,'tutor','ubah')
        c.tutor_update.assert_not_called()
        forms=[e for e in v.events if e[0]=='UBAH PROFIL TUTOR']
        self.assertEqual(forms[1][2]['notice'],'Nama lengkap wajib diisi.')
        await c.profile_action(View([31,good,'confirm','back']),'tutor','ubah')
        c.tutor_update.assert_called_once_with(31,good)

    async def test_deactivate_active_profiles_only(self):
        for kind,uid in [('siswa',21),('tutor',31)]:
            c=make_controller()
            v=View([uid,'confirm','back'])
            await c.profile_action(v,kind,'nonaktif')
            self.assertEqual([r['user_id'] for r in v.events[0][1]],[uid])
            c.status_update.assert_called_once_with(uid,'nonaktif')
            if kind=='tutor':
                self.assertIn('Jadwal dan riwayat','\n'.join(text_of(p) for p in v.events[1][3]))

    async def test_failure_unknown_and_role_denies_actions(self):
        c=make_controller(accounts=Mock(side_effect=RuntimeError('connection')))
        v=View(['back'])
        await c.run(v)
        self.assertIn('Data belum tersedia','\n'.join(text_of(p) for p in v.events[0][3]))
        c=make_controller(is_admin=Mock(return_value=False))
        await c.run(View([]))
        await c.account_action(View([]),'status')
        c.accounts.assert_not_called()
        c.status_update.assert_not_called()

class RenderTests(unittest.TestCase):
    def test_metrics_counts_without_fake_zeros(self):
        self.assertEqual(account_metrics(USERS)['siswa_aktif'],1)
        self.assertEqual(account_metrics(USERS)['siswa_total'],2)
        self.assertEqual(account_metrics(USERS)['locked'],1)
        self.assertEqual(account_metrics(USERS)['failed'],1)
        self.assertIsNone(account_metrics(None))
        self.assertEqual(profile_metrics([SISWA,WAITING],'siswa')['assigned'],1)
        self.assertEqual(profile_metrics([TUTOR_PROFILE,TUTOR_OFF],'tutor')['schedules'],2)

    def test_cards_tables_and_details_bounded(self):
        long=dict(SISWA,nama_lengkap='漢字 '*100,program='Program '*100,email='a'*130+'@example.test')
        for width in (30,38,46,58,78,100):
            for budget in (1,4,9,30):
                for pages in (dashboard_pages(account_metrics(USERS),'root',width,budget),
                              dashboard_pages(None,'akun',width,budget),
                              dashboard_pages(profile_metrics([SISWA,WAITING],'siswa'),'siswa',width,budget),
                              dashboard_pages(profile_metrics([TUTOR_PROFILE],'tutor'),'tutor',width,budget),
                              details_pages(account_sections(STUDENT),width,budget,full=True,paired=True),
                              details_pages(profile_sections('siswa',long),width,budget,full=True,paired=True)):
                    self.assertTrue(pages)
                    for page in pages:
                        self.assertLessEqual(len(page),budget)
                        self.assertTrue(all(width_of(r)<=width for r in page))
            for row in (account_row(width,STUDENT),profile_row('siswa',width,long,True),
                        profile_row('tutor',width,TUTOR_PROFILE),history_row('siswa',width,HISTORY[0]),
                        history_row('tutor',width,SCHEDULES[0]),program_row(width,PROGRAMS[0])):
                self.assertLessEqual(width_of(row),width)

    def test_home_routes_integrated_data(self):
        with create_pipe_input() as inp:
            view=AdminDashboardWorkspace('Jaya',input=inp,output=Output(32,108),motion_enabled=False,
                load=lambda:Snapshot(SUMMARY,[]),integrated_data=True)
            async def drive():
                while view.loading:
                    await asyncio.sleep(.01)
                inp.send_text('\x1b[B\r')
            def start():
                view.app.create_background_task(view._fetch())
                view.app.create_background_task(drive())
            self.assertEqual(view.app.run(pre_run=start),'data_pengguna')

    def test_real_keyboard_round_trip_and_safe_unlock_cancel(self):
        c=make_controller()
        with create_pipe_input() as inp:
            view=ConfirmationWorkspace('Jaya',input=inp,output=Output(32,108),motion_enabled=False)
            async def wait(title):
                for _ in range(350):
                    if view.title==title and view.mode=='menu':
                        await asyncio.sleep(.04)
                        return
                    await asyncio.sleep(.01)
                raise AssertionError(f'Expected {title}, got {view.title}/{view.mode}')
            async def drive():
                try:
                    await wait('PUSAT DATA PENGGUNA')
                    inp.send_text('\r')
                    await wait('MANAJEMEN AKUN')
                    inp.send_text('\x1b[B\x1b[B\r')
                    await wait('PILIH AKUN UNTUK BUKA KUNCI')
                    inp.send_text('\r')
                    await wait('KONFIRMASI BUKA KUNCI')
                    self.assertRegex('\n'.join(screen(view)),r'❯ +Batal')
                    inp.send_text('\r')
                    await wait('PILIH AKUN UNTUK BUKA KUNCI')
                    inp.send_text('\x1b')
                    await wait('MANAJEMEN AKUN')
                    inp.send_text('\x1b')
                    await wait('PUSAT DATA PENGGUNA')
                    inp.send_text('\x1b[B\r')
                    await wait('DATA SISWA')
                    inp.send_text('\x1b')
                    await wait('PUSAT DATA PENGGUNA')
                    inp.send_text('\x1b[B\r')
                    await wait('DATA TUTOR')
                    inp.send_text('\x1b')
                    await wait('PUSAT DATA PENGGUNA')
                    self.assertEqual(view.choices[view.index][0],'tutor')
                    inp.send_text('\x1b')
                except Exception as exc:
                    view.app.exit(exception=exc)
            async def run(v):
                view.app.create_background_task(drive())
                await c.run(v)
            view.run(run)
        c.unlock.assert_not_called()
        c.reset.assert_not_called()
        c.status_update.assert_not_called()

if __name__=='__main__':
    unittest.main()
