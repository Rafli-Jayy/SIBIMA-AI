"""Academic workspace regression tests with injected program/schedule services."""
import asyncio
import unittest
from datetime import date,datetime,time
from decimal import Decimal
from unittest.mock import Mock,call
from prompt_toolkit.input import create_pipe_input
from app.ui.admin_academic import (
    AcademicController, PROGRAM_MENU,SCHEDULE_MENU,academic_pages,open_quota,weekly_counts,
    program_row,room_row,schedule_row,option_row,program_sections,program_detail_pages,schedule_sections,bar_row,
)
from app.ui.admin_confirmation import ConfirmationWorkspace,details_pages
from app.ui.admin_workspace import width_of,AdminDashboardWorkspace,Snapshot
from test_ui002_admin_workspace import Output,screen,text_of,SUMMARY
from test_ui003b_enrollment import View

P1=dict(id=11,kode='MTK',nama='Matematika SMA',jenjang='SMA',deskripsi='Persiapan ujian dan numerasi.',
        harga_bulanan=Decimal('250000'),kuota=20,terisi=18,sisa=2,status='buka',
        bobot_tugas=30,bobot_kuis=20,bobot_uts=20,bobot_uas=30,created_at=datetime(2026,11,26,8))
P2=dict(P1,id=12,kode='ING',nama='Bahasa Inggris',kuota=20,terisi=12,sisa=8,harga_bulanan=300000)
P3=dict(P1,id=13,kode='FIS',nama='Fisika SMA',kuota=15,terisi=15,sisa=0)
P4=dict(P1,id=14,kode='BIO',nama='Biologi SMA',kuota=15,terisi=3,sisa=12,status='tutup')
P5=dict(P1,id=15,kode='KIM',nama='Kimia SMA',kuota=20,terisi=5,sisa=15)
PROGRAMS=[P1,P2,P3,P4,P5]
R1=dict(id=21,nama='Ruang A',kapasitas=20,aktif=True)
R2=dict(id=22,nama='Ruang B',kapasitas=25,aktif=True)
R3=dict(id=23,nama='Ruang C',kapasitas=15,aktif=False)
ROOMS=[R1,R2,R3]
T1=dict(id=31,kode_tutor='T-0031',nama_lengkap='Dewi Lestari',keahlian='Matematika',status='aktif')
T2=dict(id=32,kode_tutor='T-0032',nama_lengkap='Raka Wijaya',keahlian='Fisika',status='nonaktif')
J1=dict(id=41,program_id=11,kode_program='MTK',nama_program='Matematika SMA',jenjang='SMA',
        tutor_id=31,kode_tutor='T-0031',nama_tutor='Dewi Lestari',room_id=21,nama_ruang='Ruang A',
        kapasitas_ruang=20,hari='kamis',jam_mulai=time(8),jam_selesai=time(9,30),aktif=True,
        jumlah_siswa=18,jumlah_pertemuan=0)
J2=dict(J1,id=42,program_id=12,kode_program='ING',nama_program='Bahasa Inggris',room_id=22,nama_ruang='Ruang B',
        jam_mulai=time(10),jam_selesai=time(11,30),jumlah_siswa=12,jumlah_pertemuan=4)
J3=dict(J1,id=43,hari='senin',jam_mulai=time(13),jam_selesai=time(14,30),jumlah_pertemuan=6,aktif=False)
J4=dict(J1,id=44,hari='selasa',jam_mulai=time(13),jam_selesai=time(14,30),jumlah_pertemuan=2)
SCHEDULES=[J3,J4,J1,J2]
TODAY=[dict(jam_mulai=j['jam_mulai'],jam_selesai=j['jam_selesai'],program=j['nama_program'],
            tutor=j['nama_tutor'],ruang=j['nama_ruang'],total_jadwal=2) for j in (J1,J2)]
DATA=dict(programs=PROGRAMS,rooms=ROOMS,schedules=SCHEDULES,today=TODAY)
def make_controller(**kw):
    def schedule_list(**filters):
        return True,[j for j in SCHEDULES if all(j.get(k)==v for k,v in filters.items() if v is not None)]
    options={
        'program':Mock(side_effect=lambda aktif_saja=True:(True,[p for p in PROGRAMS if not aktif_saja or p['status']=='buka'])),
        'tutor':Mock(side_effect=lambda aktif_saja=True:(True,[T1] if aktif_saja else [T1,T2])),
        'ruang':Mock(side_effect=lambda aktif_saja=True:(True,[r for r in ROOMS if not aktif_saja or r['aktif']])),
    }
    args=dict(programs=Mock(return_value=PROGRAMS),rooms=Mock(return_value=ROOMS),
              today=Mock(return_value=TODAY),schedules=Mock(side_effect=schedule_list),
              detail_schedule=Mock(side_effect=lambda n:(True,next(j for j in SCHEDULES if j['id']==n))),
              options=options,create_program=Mock(return_value=(True,'Program dibuat.')),
              update_program=Mock(return_value=(True,'Program diubah.')),create_room=Mock(return_value=(True,'Ruang dibuat.')),
              update_room=Mock(return_value=(True,'Ruang diubah.')),create_schedule=Mock(return_value=(True,'Jadwal dibuat.')),
              update_schedule=Mock(return_value=(True,'Jadwal diubah.')),disable_schedule=Mock(return_value=(True,'Jadwal nonaktif.')),
              is_admin=Mock(return_value=True))
    args.update(kw)
    return AcademicController(**args)

class Flows(unittest.IsolatedAsyncioTestCase):
    async def test_root_all_11_routes_and_focus(self):
        c=make_controller()
        v=View(['program','back','jadwal','back','back'])
        await c.run(v)
        roots=[e for e in v.events if e[0]=='PUSAT AKADEMIK']
        self.assertEqual([e[2]['default'] for e in roots],['program','program','jadwal'])
        self.assertEqual(len(PROGRAM_MENU)+len(SCHEDULE_MENU),11)
        for title,menu in [('PROGRAM & RUANG',PROGRAM_MENU),('MANAJEMEN JADWAL',SCHEDULE_MENU)]:
            self.assertEqual(next(e for e in v.events if e[0]==title)[1],menu+[('refresh','Muat ulang'),('back','Kembali ke Akademik')])

    async def test_program_browse_detail_refresh(self):
        c=make_controller()
        v=View([11,'back','refresh','back'])
        await c.browse_programs(v)
        self.assertEqual(c.programs.call_count,3)
        self.assertIn('BOBOT PENILAIAN','\n'.join(text_of(p) for p in v.events[1][3]))
        self.assertEqual(v.events[2][2]['initial'],11)

    async def test_program_create_two_forms_exact_api(self):
        c=make_controller()
        first={'kode':'NEW','nama':'Program Baru','jenjang':'SMA'}
        second={'deskripsi':'','harga_bulanan':'250000','kuota':'20'}
        await c.add_program(View([first,second,'back']))
        c.create_program.assert_not_called()
        v=View([first,second,'confirm'])
        await c.add_program(v)
        c.create_program.assert_called_once_with({**first,**second})
        self.assertEqual(v.events[2][2]['default'],'back')
        self.assertIn('100%','\n'.join(text_of(p) for p in v.events[2][3]))

    async def test_program_edit_description_and_quota(self):
        c=make_controller()
        await c.edit_program(View([11,'deskripsi',{'deskripsi':'  '},'confirm']))
        c.update_program.assert_called_once_with(11,{'deskripsi':None})
        c=make_controller()
        await c.edit_program(View([11,'kuota',{'kuota':'25'},'confirm']))
        c.update_program.assert_called_once_with(11,{'kuota':'25'})

    async def test_all_four_weights_and_invalid_total(self):
        c=make_controller()
        first={'bobot_tugas':'25','bobot_kuis':'25'}
        second={'bobot_uts':'20','bobot_uas':'30'}
        v=View([11,'bobot',first,dict(second,bobot_uas='20')])
        await c.edit_program(v)
        self.assertIn('BOBOT BELUM VALID',str(v.events))
        c.update_program.assert_not_called()
        v=View([11,'bobot',first,second,'confirm'])
        await c.edit_program(v)
        c.update_program.assert_called_once_with(11,{**first,**second})
        self.assertIn('100%','\n'.join(text_of(p) for p in v.events[-2][3]))

    async def test_toggle_program_both_directions_and_cancel(self):
        c=make_controller()
        await c.toggle_program(View([11,'back']))
        c.update_program.assert_not_called()
        await c.toggle_program(View([11,'confirm']))
        await c.toggle_program(View([14,'confirm']))
        self.assertEqual(c.update_program.call_args_list,[call(11,{'status':'tutup'}),call(14,{'status':'buka'})])

    async def test_room_browse_create_edit(self):
        c=make_controller()
        v=View([21,'back','back'])
        await c.browse_rooms(v)
        self.assertIn('Ruang A','\n'.join(text_of(p) for p in v.events[1][3]))
        await c.add_room(View([{'nama':'Ruang D','kapasitas':'25'},'confirm']))
        c.create_room.assert_called_once_with('Ruang D','25')
        data={'nama':'Ruang A Baru','kapasitas':'30'}
        await c.edit_room(View([21,data,'confirm']))
        c.update_room.assert_called_once_with(21,data)

    async def test_all_schedule_filters_and_inactive_references_allowed(self):
        for kind,ident,expected in [('program',14,{'program_id':14}),('tutor',32,{'tutor_id':32}),
                                    ('ruang',23,{'room_id':23}),('hari','kamis',{'hari':'kamis'})]:
            c=make_controller()
            await c.browse_schedules(View([kind,ident,'back']))
            c.schedules.assert_called_once_with(**expected)
            if kind!='hari':
                c.options[kind].assert_called_once_with(aktif_saja=False)

    async def test_schedule_detail_fresh_and_filter_refresh(self):
        c=make_controller()
        v=View(['all',41,'back','filter','hari','kamis','refresh','back'])
        await c.browse_schedules(v)
        c.detail_schedule.assert_called_once_with(41)
        self.assertEqual(c.schedules.call_args_list,[call(),call(),call(hari='kamis'),call(hari='kamis')])
        detail=next(e for e in v.events if e[0]=='DETAIL JADWAL')
        self.assertIn('Sesi tercatat','\n'.join(text_of(p) for p in detail[3]))

    async def test_schedule_add_choices_active_and_zero_writes_on_cancel(self):
        c=make_controller()
        answer={'jam_mulai':'15:00','jam_selesai':'16:30'}
        await c.add_schedule(View([11,31,21,'kamis',answer,'back']))
        c.create_schedule.assert_not_called()
        c=make_controller()
        v=View([11,31,21,'kamis',answer,'confirm'])
        await c.add_schedule(v)
        c.create_schedule.assert_called_once_with(dict(program_id=11,tutor_id=31,room_id=21,hari='kamis',**answer))
        for fn in c.options.values():
            fn.assert_called_once_with(aktif_saja=True)
        self.assertIn('Dewi Lestari','\n'.join(text_of(p) for p in v.events[-2][3]))

    async def test_schedule_edit_one_field_exact_and_history_guard(self):
        c=make_controller()
        await c.edit_schedule(View([41,'jam_mulai',{'jam_mulai':'08:30'},'confirm']))
        c.schedules.assert_called_once_with(aktif=True)
        c.detail_schedule.assert_called_once_with(41)
        c.update_schedule.assert_called_once_with(41,{'jam_mulai':'08:30'})
        c=make_controller()
        v=View([42])
        await c.edit_schedule(v)
        c.update_schedule.assert_not_called()
        self.assertIn('JADWAL MEMILIKI RIWAYAT',str(v.events))

    async def test_schedule_edit_reference_and_day(self):
        c=make_controller()
        await c.edit_schedule(View([41,'room_id',22,'confirm']))
        c.options['ruang'].assert_called_once_with(aktif_saja=True)
        c.update_schedule.assert_called_once_with(41,{'room_id':22})
        c=make_controller()
        await c.edit_schedule(View([41,'hari','jumat','confirm']))
        c.update_schedule.assert_called_once_with(41,{'hari':'jumat'})

    async def test_deactivate_schedule_history_kept_and_cancel_safe(self):
        c=make_controller()
        await c.deactivate_schedule(View([42,'back']))
        c.disable_schedule.assert_not_called()
        v=View([42,'confirm'])
        await c.deactivate_schedule(v)
        c.disable_schedule.assert_called_once_with(42)
        self.assertIn('Riwayat pertemuan tetap disimpan','\n'.join(text_of(p) for p in v.events[1][3]))

    async def test_schedule_stale_and_service_bentrok_error(self):
        c=make_controller(detail_schedule=Mock(return_value=(True,dict(J1,aktif=False))))
        v=View([41])
        await c.deactivate_schedule(v)
        c.disable_schedule.assert_not_called()
        self.assertIn('JADWAL BERUBAH',str(v.events))
        c=make_controller(create_schedule=Mock(return_value=(False,'Jadwal bentrok dengan tutor.')))
        v=View([11,31,21,'kamis',{'jam_mulai':'08:00','jam_selesai':'09:30'},'confirm'])
        await c.add_schedule(v)
        c.create_schedule.assert_called_once()
        self.assertIn('Jadwal bentrok',str(v.events))

    async def test_failure_does_not_invent_zero_and_role_recheck(self):
        c=make_controller(rooms=Mock(side_effect=RuntimeError('private')))
        v=View(['back'])
        await c.run(v)
        self.assertIn('Data belum lengkap','\n'.join(text_of(p) for p in v.events[0][3]))
        c=make_controller(is_admin=Mock(return_value=False))
        await c.run(View([]))
        c.programs.assert_not_called()

class Renders(unittest.TestCase):
    def test_meaningful_metrics_and_bar_over_capacity(self):
        q=open_quota(PROGRAMS)
        self.assertEqual(q,dict(programs=4,cap=75,used=50,left=25,full=1))
        self.assertEqual(weekly_counts(SCHEDULES)['kamis'],2)
        self.assertEqual(weekly_counts(SCHEDULES)['senin'],0)
        self.assertIn('23/20',text_of([bar_row('Program',23,20,60)]))
        self.assertIsNone(open_quota(None))

    def test_layouts_fit_width_height_with_unicode(self):
        long=dict(P1,nama='漢字 '*100,deskripsi='Test '*200)
        for w in (30,38,46,65,78,100):
            for b in (1,4,8,25):
                for pages in (academic_pages(DATA,'root',w,b),academic_pages(DATA,'program',w,b),
                    academic_pages(DATA,'jadwal',w,b),academic_pages({},'root',w,b),
                    program_detail_pages(long,w,b),details_pages(program_sections(long),w,b,full=True,paired=True),
                    details_pages(schedule_sections(J1),w,b,full=True,paired=True)):
                    self.assertTrue(pages)
                    for page in pages:
                        self.assertLessEqual(len(page),b)
                        self.assertTrue(all(width_of(row)<=w for row in page))
            for row in (program_row(w,long),room_row(w,R1),schedule_row(w,J1),option_row('tutor',w,T1)):
                self.assertLessEqual(width_of(row),w)

    def test_visual_variants_not_uniform_card_grid(self):
        root=academic_pages(DATA,'root',100,40)[0]
        self.assertEqual(text_of(root).count('┌'),5)
        self.assertIn('█',text_of(root))
        program=text_of(academic_pages(DATA,'program',100,40)[0])
        self.assertIn('█',program)
        self.assertIn('15/15',program)
        jadwal=text_of(academic_pages(DATA,'jadwal',100,40)[0])
        for day in ('Sen','Sel','Rab','Kam','Jum','Sab','Min'):
            self.assertIn(day,jadwal)

    def test_home_academic_routes_direct(self):
        with create_pipe_input() as inp:
            view=AdminDashboardWorkspace('Jaya',input=inp,output=Output(32,108),motion_enabled=False,
                load=lambda:Snapshot(SUMMARY,[]),integrated_academic=True)
            async def drive():
                while view.loading:
                    await asyncio.sleep(.01)
                inp.send_text('\x1b[B\x1b[B\r')
            def start():
                view.app.create_background_task(view._fetch())
                view.app.create_background_task(drive())
            self.assertEqual(view.app.run(pre_run=start),'akademik')

    def test_real_keyboard_module_back_and_safe_cancel(self):
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
                    await wait('PUSAT AKADEMIK')
                    inp.send_text('\r')
                    await wait('PROGRAM & RUANG')
                    inp.send_text('\x1b[B'*3+'\r')
                    await wait('PILIH PROGRAM BUKA / TUTUP')
                    inp.send_text('\r')
                    await wait('KONFIRMASI STATUS PROGRAM')
                    self.assertRegex('\n'.join(screen(view)),r'❯ +Batal')
                    inp.send_text('\r')
                    await wait('PROGRAM & RUANG')
                    inp.send_text('\x1b')
                    await wait('PUSAT AKADEMIK')
                    inp.send_text('\x1b[B\r')
                    await wait('MANAJEMEN JADWAL')
                    inp.send_text('\x1b')
                    await wait('PUSAT AKADEMIK')
                    self.assertEqual(view.choices[view.index][0],'jadwal')
                    inp.send_text('\x1b')
                except Exception as e:
                    view.app.exit(exception=e)
            async def run(v):
                view.app.create_background_task(drive())
                await c.run(v)
            view.run(run)
        c.update_program.assert_not_called()
        c.create_schedule.assert_not_called()

if __name__=='__main__':
    unittest.main()
