"""Regression tests for the shared Admin empty card and AI presentation only."""
import ast
import io
import unittest
import asyncio
from pathlib import Path
from prompt_toolkit.input import create_pipe_input
from app.ui.admin_confirmation import ConfirmationWorkspace,empty_state_rows
from app.ui.admin_workspace import width_of
from app.ui.admin_reporting import announcement_pages,log_pages
from app.ui.ai.navigation import AINavigation
from test_ui002_admin_workspace import Output,screen,text_of
from test_ui006_reporting import ANNOUNCEMENTS,LOGS

CHOICES=['Lanjutkan percakapan','Lihat riwayat','Mulai percakapan baru','Bantuan','Keluar dari asisten']
ROOT=Path(__file__).resolve().parents[1]

class EmptyStateTests(unittest.TestCase):
    def test_card_centered_width_and_context(self):
        rows=empty_state_rows(100,25,'Arsip permanen · Maks. 500','Belum ada pengumuman yang diarsipkan.')
        self.assertEqual(rows[0],[])
        text=text_of(rows)
        self.assertIn('BELUM ADA DATA',text)
        self.assertIn('Belum ada pengumuman yang diarsipkan.',text)
        self.assertIn('0 data · Arsip permanen · Maks. 500',text)
        self.assertEqual(text.splitlines()[1].index('┌'),18)
        self.assertEqual(text.splitlines()[1].rindex('┐'),81)
        self.assertLessEqual(len(rows),12)

    def test_all_admin_contexts_and_small_screens(self):
        examples=[
            ('Urutan terlama','Tidak ada akun menunggu konfirmasi.'),
            ('Aktif · Semua program','Tidak ada pendaftaran sesuai filter.'),
            ('Belum lunas','Tidak ada tagihan sesuai kriteria.'),
            ('Riwayat','Tidak ada transaksi sesuai filter.'),
            ('Semua status','Tidak ada akun sesuai filter.'),
            ('Profil siswa','Tidak ada profil sesuai kriteria.'),
            ('Profil tutor','Belum ada jadwal mengajar.'),
            ('Pilih program','Belum ada program bimbel.'),
            ('Pilih ruangan','Belum ada ruang belajar.'),
            ('Semua hari','Tidak ada jadwal sesuai filter.'),
            ('Laporan bulanan','Tidak ada data laporan.'),
            ('Aktif','Belum ada pengumuman aktif.'),
            ('Arsip permanen','Belum ada pengumuman yang diarsipkan.'),
            ('Pengguna: semua','Tidak ada aktivitas yang cocok.'),
        ]
        for caption,msg in examples:
            for w in (8,18,30,46,64,78,100):
                for b in (1,2,3,4,8,25):
                    rows=empty_state_rows(w,b,caption,msg,filter_action=True)
                    self.assertTrue(rows)
                    self.assertLessEqual(len(rows),b)
                    self.assertTrue(all(width_of(r)<=w for r in rows))
                    if w>=64 and b>=8:self.assertIn(msg,text_of(rows))
        self.assertIn('Ubah filter atau muat ulang.',text_of(empty_state_rows(100,25,'x','Tidak ada data.',filter_action=True)))

    def test_empty_keyboard_actions_and_position(self):
        for keys,expected in [('r','refresh'),('f','filter'),('\r','back'),('\x1b',None)]:
            with create_pipe_input() as inp:
                view=ConfirmationWorkspace('Demo Admin',input=inp,output=Output(32,108),motion_enabled=False)
                async def flow(v):
                    async def drive():
                        try:
                            await asyncio.sleep(.10)
                            rows=screen(v)
                            top=next(i for i,r in enumerate(rows) if '┌' in r)
                            self.assertLess(top,8)
                            self.assertEqual(rows[top].index('┌'),22)
                            self.assertIn('BELUM ADA DATA','\n'.join(rows))
                            self.assertIn('F Filter','\n'.join(rows))
                            inp.send_text(keys)
                        except Exception as exc:v.app.exit(exception=exc)
                    v.app.create_background_task(drive())
                    return await v.record_table('DAFTAR LOG AKTIVITAS',[],key='id',
                        renderer=lambda *args:[],caption='Maks. 200',
                        empty='Tidak ada aktivitas yang cocok.',filter_action=True)
                self.assertEqual(view.run(flow),expected)

class DetailTests(unittest.TestCase):
    def test_body_in_card_and_gap(self):
        for fn,item,body in [(announcement_pages,ANNOUNCEMENTS[0],'Kelas Matematika dipindah'),(log_pages,LOGS[0],'Login admin berhasil.')]:
            page=fn(item,100,25)[0]
            index=next(i for i,row in enumerate(page) if 'ISI / DETAIL' in text_of([row]))
            self.assertIn('┌',text_of([page[index-1]]))
            self.assertIn('│',text_of([page[index+1]]))
            self.assertIn(body,text_of(page))
            self.assertEqual(page[-1],[])
            self.assertIn('└',text_of(page[index:]))

    def test_long_body_is_pageable_and_preserves_text(self):
        item=dict(ANNOUNCEMENTS[0],isi='\n'.join(f'BARIS {i:03d}' for i in range(70)))
        for w in (30,46,100):
            for b in (1,3,4,10,25):
                pages=announcement_pages(item,w,b)
                rendered='\n'.join(text_of(p) for p in pages)
                for i in range(70):self.assertEqual(rendered.count(f'BARIS {i:03d}'),1)
                self.assertTrue(all(len(p)<=b for p in pages))
                self.assertTrue(all(width_of(r)<=w for p in pages for r in p))

class AINavigationTests(unittest.TestCase):
    def test_inline_keyboard_and_centered_rows(self):
        for keys,default,expected in [('\r',None,CHOICES[0]),('\x1b[B\r',None,CHOICES[1]),
                                      ('\x1b[A\r',None,CHOICES[-1]),('\r',CHOICES[2],CHOICES[2]),
                                      ('\x1b',None,None)]:
            with create_pipe_input() as inp:
                nav=AINavigation('Pilih navigasi',CHOICES,default,input=inp,output=Output(24,108))
                self.assertFalse(nav.app.full_screen)
                initial=text_of(nav.rows())
                self.assertIn('PILIH NAVIGASI',initial)
                self.assertIn('─'*48,initial)
                async def drive():
                    try:
                        await asyncio.sleep(.07)
                        rows=screen(nav)
                        selected=next(r for r in rows if '❯' in r)
                        self.assertEqual(selected.index('❯'),30)
                        inp.send_text(keys)
                    except Exception as exc:nav.app.exit(exception=exc)
                def start():nav.app.create_background_task(drive())
                self.assertEqual(nav.app.run(pre_run=start),expected)

    def test_narrow_menu(self):
        with create_pipe_input() as inp:
            nav=AINavigation('Pilih navigasi',CHOICES,input=inp,output=Output(10,30))
            nav.index=len(CHOICES)-1
            rows=nav.rows()
            self.assertTrue(all(width_of(r)<=28 for r in rows))
            self.assertIn('❯',text_of(rows))
            self.assertLessEqual(len(rows),10)

    def test_header_has_margin_and_divider_using_rich(self):
        # Header rendering requires Rich only (no markdown rendering here).
        # Use the available Rich implementation, including pip's bundled Rich
        # in stripped test environments. The application itself imports rich.
        try:
            from rich.console import Console,Group
            from rich.align import Align
            from rich.table import Table
            from rich.text import Text
        except ImportError:
            from pip._vendor.rich.console import Console,Group
            from pip._vendor.rich.align import Align
            from pip._vendor.rich.table import Table
            from pip._vendor.rich.text import Text
        p=ROOT/'app/ui/ai/response_renderer.py'
        tree=ast.parse(p.read_text(encoding='utf8'))
        funcs=[node for node in tree.body if isinstance(node,ast.FunctionDef)
               and node.name in ('_within_workspace','render_header')]
        # fit_width is verified separately from its unchanged implementation.
        theme=ast.parse((ROOT/'app/ui/ai/ai_theme.py').read_text(encoding='utf8'))
        fit=next(n for n in theme.body if isinstance(n,ast.FunctionDef) and n.name=='fit_width')
        ns=dict(Console=Console,Group=Group,Align=Align,Table=Table,Text=Text,WORKSPACE_MAX=94)
        exec(compile(ast.Module(body=[fit,*funcs],type_ignores=[]),str(p),'exec'),ns)
        for w in (24,48,108,160):
            out=io.StringIO()
            console=Console(width=w,file=out,force_terminal=False)
            console.print(ns['render_header']('admin',w,online=True))
            lines=out.getvalue().splitlines()
            self.assertEqual(lines[0].strip(),'')
            self.assertIn('SIBIMA AI',out.getvalue())
            self.assertIn('Gemini',out.getvalue())
            divider=next(r for r in lines if '─' in r)
            self.assertEqual(divider.count('─'),min(94,w-4))
            self.assertEqual(divider.index('─'),(w-min(94,w-4))//2)
            self.assertTrue(all(width_of([('',r)])<=w for r in lines))

    def test_chat_choice_wired_without_session_change(self):
        tree=ast.parse((ROOT/'app/ui/ai/chat_screen.py').read_text(encoding='utf8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ChatScreen')
        choice=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_choice')
        self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='choose_navigation' for n in ast.walk(choice)))
        # Both chat modes must still use render_chat and existing service lifecycle.
        for name in ('_scroll_chat_loop','_chat_loop'):
            loop=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertTrue(any(isinstance(n,ast.Call) and getattr(n.func,'id',None)=='render_chat' for n in ast.walk(loop)))

if __name__=='__main__':unittest.main()
