"""UI-002 render/navigation tests. No PostgreSQL or external email requests."""
import ast
import asyncio
import unittest
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys

from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from app.ui.admin_navigation import KELOMPOK_MENU
from app.ui.admin_workspace import (
    AdminDashboardWorkspace, AdminDashboardNavigator, Snapshot, HOME_CHOICES,
    STAT_KEYS, ATTENTION_KEYS, changed_metrics, info_pages, width_of, load_snapshot,
    CONTENT_WIDTH, MENU_WIDTH, CARD_GAP, menu_rows, STAT_CARDS, TOTAL_KEYS,
)

SUMMARY = dict(siswa_aktif=20,tutor_aktif=5,program_buka=6,enrollment_aktif=18,
               konfirmasi_akun=3,konfirmasi_pendaftaran=2,tagihan_belum_lunas=4,
               tagihan_terlambat=1,sesi_perlu_laporan=2,
               siswa_total=24,tutor_total=6,admin_aktif=2,admin_total=3,program_total=8,
               ruang_aktif=4,ruang_total=5,jadwal_aktif=12,
               enrollment_menunggu_bayar=3,enrollment_selesai=7,
               tagihan_lunas=26,nominal_lunas_bulan_ini=4250000,
               konfirmasi_siswa=2,konfirmasi_tutor=1,konfirmasi_berbayar=1,konfirmasi_gratis=1,
               nominal_belum_lunas=1800000,transaksi_lunas_bulan_ini=26,
               transaksi_gagal_bulan_ini=2,refund_bulan_ini=1)
SCHEDULE = [
    dict(jam_mulai='08:00',jam_selesai='09:30',program='Matematika',tutor='Dewi',ruang='Ruang A'),
    dict(jam_mulai='10:00',jam_selesai='11:30',program='Bahasa Inggris',tutor='Andi',ruang='Ruang B'),
]


def text_of(rows):
    return '\n'.join(''.join(s for _,s in row) for row in rows)


class Output(DummyOutput):
    def __init__(self,rows=24,columns=80):
        self.rows,self.columns=rows,columns
    def get_size(self):
        return Size(rows=self.rows,columns=self.columns)


def screen(view):
    s=view.app.renderer.last_rendered_screen
    size=view.app.output.get_size()
    return [''.join(s.data_buffer[y][x].char for x in range(size.columns))
            for y in range(size.rows)]


def run_keys(keys, *, output=None, loader=None, check=None, previous=None):
    with create_pipe_input() as inp:
        w=AdminDashboardWorkspace('Demo Admin',load=loader or (lambda:Snapshot(SUMMARY,SCHEDULE)),
                                  previous=previous,input=inp,output=output or Output(),motion_enabled=False)
        async def drive():
            try:
                for _ in range(100):
                    if not w.loading:
                        break
                    await asyncio.sleep(.01)
                if w.loading:
                    raise AssertionError('Dashboard load did not finish')
                await asyncio.sleep(.05)
                if check:
                    await check(w,inp)
                inp.send_text(keys)
            except Exception as exc:
                w.app.exit(exception=exc)
        def start():
            w.app.create_background_task(w._fetch())
            w.app.create_background_task(drive())
        return w.app.run(pre_run=start)


class DataRenderTests(unittest.TestCase):
    def test_all_legacy_routes_and_group_keys(self):
        self.assertEqual([k for k,_ in HOME_CHOICES],[0,1,2,3,'logout'])
        actual={code for _,items in KELOMPOK_MENU for _,code in items}
        self.assertEqual(actual,{'konfirmasi','pendaftaran','pembayaran','akun','siswa','tutor',
                                 'program','jadwal','laporan','pengumuman','log','ai'})
        # Verify old controller still dispatches every route (including AI).
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/'app/ui/menu_admin.py').read_text(encoding='utf8'))
        jalankan=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='jalankan')
        comparisons={c.value for n in ast.walk(jalankan) if isinstance(n,ast.Compare)
                     for c in n.comparators if isinstance(c,ast.Constant)}
        self.assertTrue(actual<=comparisons)
        self.assertIn('logout',comparisons)

    def test_unknown_not_zero_and_empty_distinct(self):
        data=Snapshot(None,None)
        text='\n'.join(text_of(page) for page in info_pages(data,78,30,set()))
        self.assertIn('—',text)
        self.assertIn('Statistik gagal dimuat',text)
        self.assertIn('Jadwal gagal dimuat',text)
        text='\n'.join(text_of(page) for page in info_pages(Snapshot(dict.fromkeys(SUMMARY,0),[]),78,30,set()))
        self.assertIn('0',text)
        self.assertIn('Tidak ada jadwal rutin aktif',text)

    def test_changed_metrics_only_real_values(self):
        current=Snapshot({**SUMMARY,'siswa_aktif':21,'tagihan_belum_lunas':0},SCHEDULE)
        self.assertEqual(changed_metrics(Snapshot(SUMMARY,[]),current),{'siswa_aktif','tagihan_belum_lunas'})
        self.assertEqual(changed_metrics(Snapshot(None,[]),current),set())
        self.assertNotIn('siswa_aktif',changed_metrics(Snapshot({'siswa_aktif':None},[]),current))

    def test_width_height_and_unicode_bounds(self):
        schedule=[dict(jam_mulai='08:00',jam_selesai='10:00',program='漢字 '*100,
                       tutor='A\x1b[31m'*60,ruang='Ruang panjang '*50)]*5
        snapshot=Snapshot(SUMMARY,schedule)
        for width in (38,46,60,78,108):
            for budget in (1,3,5,11,30):
                with self.subTest(width=width,budget=budget):
                    pages=info_pages(snapshot,width,budget,set())
                    self.assertTrue(pages)
                    for page in pages:
                        self.assertLessEqual(len(page),budget)
                        self.assertTrue(all(width_of(row)<=width for row in page))
                        self.assertNotIn('\x1b',text_of(page))

    def test_repository_failure_independently_handled(self):
        repo=SimpleNamespace(ringkasan_admin=Mock(side_effect=RuntimeError('private')),
                             jadwal_hari_ini_admin=Mock(return_value=SCHEDULE))
        module=SimpleNamespace(admin_dashboard_repo=repo)
        with patch.dict(sys.modules,{'app.repositories':module}):
            snapshot=load_snapshot()
        self.assertIsNone(snapshot.summary)
        self.assertEqual(snapshot.schedule,SCHEDULE)
        repo.ringkasan_admin.assert_called_once_with()
        repo.jadwal_hari_ini_admin.assert_called_once_with()

    def test_highlight_and_missing_data_style(self):
        pages=info_pages(Snapshot(SUMMARY,SCHEDULE),108,30,{'siswa_aktif'})
        rendered=[frag for page in pages for row in page for frag in row]
        self.assertTrue(any(style=='class:success' and value.strip()=='20/24'
                            for style,value in rendered))
        rendered=[frag for page in info_pages(Snapshot(None,[]),108,30,set())
                  for row in page for frag in row]
        self.assertFalse(any(style=='class:success' and value.strip()=='—'
                             for style,value in rendered))

    def test_every_card_has_three_rows_and_every_metric_rendered(self):
        self.assertEqual([len(items) for _,items in STAT_CARDS],[3,3,3,3])
        pages=info_pages(Snapshot(SUMMARY,SCHEDULE),100,40,set())
        self.assertEqual(len(pages),1)
        body=text_of(pages[0])
        for expected in (
            'PENGGUNA · AKTIF/TOTAL','AKADEMIK','PENDAFTARAN','KEUANGAN',
            '20/24','5/6','2/3','6/8','4/5','Jadwal rutin aktif',
            'Pendaftaran aktif','Menunggu pembayaran','Pendaftaran selesai',
            'Tagihan lunas','Tagihan belum lunas','4.250.000',
            'Konfirmasi akun','Konfirmasi pendaftaran',
            'Tagihan lewat jatuh tempo','Sesi perlu laporan',
            'JADWAL HARI INI (RUTIN) · 2 jadwal','Data terakhir dimuat',
        ):
            self.assertIn(expected,body)
        self.assertEqual(body.count('┌'),6)
        self.assertEqual(body.count('┘'),6)

    def test_partial_counts_not_misrepresented_and_total_highlighted(self):
        newer=Snapshot({**SUMMARY,'siswa_total':25,
                        'nominal_lunas_bulan_ini':Decimal('4250000.50')},SCHEDULE)
        changed=changed_metrics(Snapshot(SUMMARY,SCHEDULE),newer)
        self.assertIn('siswa_total',changed)
        rows=[frag for page in info_pages(newer,100,40,changed) for row in page for frag in row]
        self.assertIn(('class:success','20/25'),rows)
        self.assertTrue(any(style=='class:success' and value.strip()=='4.250.000,50' for style,value in rows))
        partial=Snapshot({**SUMMARY,'tutor_total':None,'nominal_lunas_bulan_ini':None},SCHEDULE)
        rows=[frag for page in info_pages(partial,100,40,set()) for row in page for frag in row]
        self.assertTrue(any(style=='class:muted' and value.strip()=='5/—' for style,value in rows))
        self.assertTrue(any('Data belum lengkap' in value for _,value in rows))

    def test_schedule_limit_identified_and_all_five_rows_kept(self):
        schedule=[dict(SCHEDULE[0],program=f'Kelas {i}',total_jadwal=7) for i in range(5)]
        for width,budget in ((100,34),(78,12),(46,5)):
            body='\n'.join(text_of(page) for page in info_pages(Snapshot(SUMMARY,schedule),width,budget,set()))
            self.assertIn('5 dari 7',body)
            for i in range(5):
                self.assertIn(f'Kelas {i}',body)

    def test_repository_query_covers_displayed_keys(self):
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/'app/repositories/admin_dashboard_repo.py').read_text(encoding='utf8'))
        constants={n.targets[0].id:n.value.value for n in tree.body
                   if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
                   and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str)}
        summary=constants['_SQL_RINGKASAN']
        aliases=set(re.findall(r'\bAS\s+([a-z_]+)',summary,re.I))
        self.assertTrue({key for key,_ in STAT_KEYS+TOTAL_KEYS+ATTENTION_KEYS}<=aliases)
        self.assertTrue(summary.strip().startswith('WITH siap_acc AS'))
        self.assertNotRegex(summary,r'\b(INSERT|UPDATE|DELETE|TRUNCATE|ALTER)\b')
        self.assertIn("status = 'lunas'",summary)
        self.assertIn("paid_at AT TIME ZONE 'Asia/Jakarta'",summary)
        self.assertIn("status = 'menunggu_konfirmasi'",summary)
        self.assertNotIn("AS pembayaran_konfirmasi",summary)
        jadwal=constants['_SQL_JADWAL_HARI_INI']
        self.assertIn('COUNT(*) OVER () AS total_jadwal',jadwal)
        self.assertIn('LIMIT 5',jadwal)

    def test_navigator_remembers_only_successful_summary(self):
        navigator=AdminDashboardNavigator(load=Mock())
        one=Mock(snapshot=Snapshot(SUMMARY,SCHEDULE))
        one.run.return_value='akun'
        two=Mock(snapshot=Snapshot(None,None))
        two.run.return_value='logout'
        with patch('app.ui.admin_workspace.AdminDashboardWorkspace',side_effect=[one,two]) as cls:
            self.assertEqual(navigator.choose('Admin'),'akun')
            self.assertEqual(navigator.choose('Admin'),'logout')
        self.assertEqual(cls.call_args_list[1].kwargs['previous'],one.snapshot)
        self.assertEqual(navigator.previous,one.snapshot)


class KeyboardTests(unittest.TestCase):
    def test_each_module_route_with_real_key_input(self):
        for i,(_,items) in enumerate(KELOMPOK_MENU):
            for j,(_,code) in enumerate(items):
                with self.subTest(code=code):
                    self.assertEqual(run_keys('\x1b[B'*i+'\r'+'\x1b[B'*j+'\r'),code)

    def test_return_from_group_preserves_home_focus_without_refetch(self):
        load=Mock(return_value=Snapshot(SUMMARY,SCHEDULE))
        async def verify(w,inp):
            inp.send_text('\x1b[B\x1b[B\r')
            await asyncio.sleep(.08)
            self.assertEqual(w.group,2)
            self.assertIn('Program dan Ruang','\n'.join(screen(w)))
            inp.send_text('\x1b')
            await asyncio.sleep(.1)
            # Escape is parsed with a small timeout; flush with the next key if needed.
            for _ in range(60):
                if w.group is None:
                    break
                await asyncio.sleep(.02)
            self.assertIsNone(w.group)
            self.assertEqual(w.index,2)
            load.assert_called_once_with()
        self.assertEqual(run_keys('\r\r',loader=load,check=verify),'program')

    def test_paging_keeps_menu_pinned(self):
        async def verify(w,inp):
            before=screen(w)
            menu_y=next(i for i,r in enumerate(before) if '❯ 01   Prioritas' in r)
            self.assertIn('S I B I M A',before[0])
            self.assertIn('Pendaftaran aktif','\n'.join(before))
            self.assertIn(f'Info 1/{len(w._pages())}','\n'.join(before))
            inp.send_text('\x1b[6~')
            await asyncio.sleep(.08)
            after=screen(w)
            self.assertIn('JADWAL HARI INI (RUTIN)','\n'.join(after))
            self.assertIn(f'Info 2/{len(w._pages())}','\n'.join(after))
            self.assertEqual(menu_y,next(i for i,r in enumerate(after) if '❯ 01   Prioritas' in r))
            self.assertIn('❯ 01   Prioritas','\n'.join(after))
        self.assertEqual(run_keys('\r\r',check=verify),'konfirmasi')

    def test_sirasa_100_column_geometry_and_top_aligned_header(self):
        async def verify(w,inp):
            lines=screen(w)
            self.assertEqual(w._width(),100)
            self.assertEqual(w._menu_width(),48)
            self.assertEqual(lines[0].strip(),'S I B I M A')
            self.assertEqual(lines[1].strip(),'Demo Admin · Admin')
            self.assertEqual(lines[2].strip(),'─'*100)
            self.assertEqual(lines[3].strip(),'PUSAT KENDALI ADMIN')
            self.assertEqual(lines[4].index('┌'),40)
            self.assertEqual(lines[4].index('┐'),88)
            self.assertEqual(lines[4].rindex('┌'),91)
            self.assertEqual(lines[4].rindex('┐'),139)
            self.assertIn('PENGGUNA · AKTIF/TOTAL',lines[5])
            self.assertIn('AKADEMIK',lines[5])
            self.assertIn('Siswa aktif',lines[6])
            self.assertIn('Program buka',lines[6])
            self.assertIn('PENDAFTARAN',lines[12])
            self.assertIn('KEUANGAN',lines[12])
            self.assertIn('20/24',lines[6])
            self.assertIn('4.250.000',lines[15])
            self.assertFalse(any('MENU NAVIGASI' in row for row in lines))
            option=next(row for row in lines if '❯ 01   Prioritas' in row)
            self.assertEqual(option.index('❯'),66)
            sep=next(row for row in lines if row.strip()=='─'*48)
            self.assertEqual(sep.index('─'),66)
        self.assertEqual(run_keys('\r\r',output=Output(45,180),check=verify),'konfirmasi')

    def test_resize_keeps_all_data_and_menu_accessible(self):
        output=Output(45,180)
        async def verify(w,inp):
            self.assertEqual(w._width(),100)
            output.rows=24;output.columns=80
            w.app.invalidate()
            await asyncio.sleep(.08)
            self.assertEqual(w._width(),78)
            found=[]
            for i in range(len(w._pages())):
                found.extend(screen(w))
                if i+1<len(w._pages()):
                    inp.send_text('\x1b[6~')
                    await asyncio.sleep(.05)
            all_text='\n'.join(found)
            for text in ('Siswa aktif','Tutor aktif','Program buka','Pendaftaran aktif',
                         'JADWAL HARI INI (RUTIN)','PERLU PERHATIAN','Sesi perlu laporan'):
                self.assertIn(text,all_text)
            self.assertIn('❯ 01   Prioritas','\n'.join(screen(w)))
        self.assertEqual(run_keys('\r\r',output=output,check=verify),'konfirmasi')

    def test_actual_controller_routes_and_logout_order(self):
        # Execute the real jalankan function with injected service/UI doubles.
        # No imports of live DB, SMTP or the AI SDK are necessary.
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/'app/ui/menu_admin.py').read_text(encoding='utf8'))
        controller=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='jalankan')
        route_codes=[code for _,items in KELOMPOK_MENU for _,code in items]
        routes=Mock(side_effect=route_codes+['logout'])
        events=[]
        def action(code):
            return lambda *a: events.append(code)
        session=SimpleNamespace(punya_role=lambda role:role=='admin',
                                get_user=lambda:{'nama_lengkap':'Admin'},
                                logout=action('logout'))
        env=dict(AdminDashboardNavigator=lambda:SimpleNamespace(choose=routes),
                 session=session,bersihkan_layar=lambda:None,sukses=lambda *a:None,
                 peringatan=lambda *a:None,MENU_ADMIN=[],
                 menu_konfirmasi=action('konfirmasi'),menu_program_ruang=action('program'),
                 menu_pendaftaran_admin=action('pendaftaran'),menu_jadwal_admin=action('jadwal'),
                 menu_admin_data=SimpleNamespace(menu_manajemen_akun_admin=action('akun'),
                    menu_data_siswa_admin=action('siswa'),menu_data_tutor_admin=action('tutor')),
                 menu_pembayaran=SimpleNamespace(menu_pembayaran_admin=action('pembayaran')),
                 menu_admin_laporan=SimpleNamespace(menu_laporan_admin=action('laporan')),
                 menu_admin_komunikasi=SimpleNamespace(menu_pengumuman_admin=action('pengumuman'),
                    menu_log_aktivitas_admin=action('log')))
        exec(compile(ast.Module(body=[controller],type_ignores=[]),'<controller>','exec'),env)
        with patch.dict(sys.modules,{'app.services.ai_service':SimpleNamespace(buka_ai=action('ai'))}):
            env['jalankan']()
        self.assertEqual(events,route_codes+['logout'])
        self.assertEqual(routes.call_count,len(route_codes)+1)

    def test_small_viewport_and_logout(self):
        async def verify(w,inp):
            lines=screen(w)
            self.assertIn('PUSAT KENDALI ADMIN','\n'.join(lines))
            self.assertIn('Logout','\n'.join(lines))
            self.assertIn('Info 1/','\n'.join(lines))
            inp.send_text('\x1b[A')
            await asyncio.sleep(.07)
            self.assertIn('❯      Logout','\n'.join(screen(w)))
        self.assertEqual(run_keys('\r',output=Output(15,48),check=verify),'logout')

    def test_failed_load_does_not_log_out(self):
        def load():
            raise RuntimeError('secret connection string')
        async def verify(w,inp):
            text='\n'.join(screen(w))
            self.assertNotIn('secret connection string',text)
            self.assertIn('—',text)
            self.assertIn('Statistik gagal dimuat',text)
        self.assertEqual(run_keys('\r\r',loader=load,check=verify),'konfirmasi')


if __name__=='__main__':
    unittest.main()
