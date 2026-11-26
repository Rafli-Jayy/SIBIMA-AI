"""Integrated Prioritas: actual key navigation with injected, non-writing services."""
import asyncio
import unittest
from unittest.mock import Mock, AsyncMock
from prompt_toolkit.input import create_pipe_input
from app.ui.admin_workspace import AdminDashboardWorkspace, AdminDashboardNavigator, Snapshot
from app.ui.admin_confirmation import ConfirmationWorkspace
from app.ui.admin_priority import PriorityController, ROUTES
from test_ui002_admin_workspace import Output, screen, text_of
from test_ui003a_confirmation import controller as confirmation, PROGRAM
from test_ui003b_enrollment import make_controller as enrollment, View
from test_ui003c_billing import make_controller as billing, STATS

DATA=dict(STATS,enrollment_menunggu=3,enrollment_ditolak=1,enrollment_batal=1)

class BridgeView(View):
    async def table(self,kind,items):
        self.events.append(('queue',kind,list(items)))
        return next(self.answers)

def setup(**kwargs):
    summary=kwargs.get('summary',Mock(return_value=DATA))
    role=kwargs.get('role',Mock(return_value=True))
    mods=kwargs.get('modules',{'konfirmasi':confirmation(summary=summary,is_admin=role),
                               'pendaftaran':enrollment(summary=summary,is_admin=role),
                               'pembayaran':billing(summary=summary,is_admin=role)})
    c=PriorityController(summary=summary,modules=mods,is_admin=role,previous=kwargs.get('previous'))
    return c,mods

class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_controller_workflow_then_fresh_root_summary(self):
        snapshot=dict(DATA,konfirmasi_pendaftaran=2)
        summary=Mock(side_effect=lambda:dict(snapshot))
        def approve(n):
            snapshot['konfirmasi_pendaftaran']=1
            snapshot['enrollment_aktif']+=1
            return True,'Pendaftaran aktif.'
        c,mods=setup(summary=summary)
        mods['konfirmasi'].approve_enrollment=Mock(side_effect=approve)
        mods['konfirmasi'].enrollments=Mock(side_effect=[[PROGRAM],[]])
        v=BridgeView(['konfirmasi','program',31,'approve','confirm','back','back',
                      'pendaftaran','back','pembayaran','back','back'])
        await c.run(v)
        mods['konfirmasi'].approve_enrollment.assert_called_once_with(31)
        mods['konfirmasi'].approve_account.assert_not_called()
        mods['pendaftaran'].move.assert_not_called()
        mods['pembayaran'].make_monthly.assert_not_called()
        roots=[e for e in v.events if e[0]=='PUSAT PRIORITAS']
        self.assertEqual([e[2]['default'] for e in roots],
                         ['konfirmasi','konfirmasi','pendaftaran','pembayaran'])
        self.assertEqual([key for key,_ in roots[0][1]],
                         ['konfirmasi','pendaftaran','pembayaran','refresh','back'])
        self.assertTrue(any(style=='class:success' and val.strip()=='1'
                            for page in roots[1][3] for row in page for style,val in row))
        self.assertEqual(c.previous.summary['konfirmasi_pendaftaran'],1)
        self.assertEqual(c.previous.summary['enrollment_aktif'],DATA['enrollment_aktif']+1)

    async def test_summary_failure_is_unknown_and_previous_retained(self):
        data=Mock(side_effect=[DATA,RuntimeError('connection'),dict(DATA,tagihan_tunggakan=4)])
        c,_=setup(summary=data)
        v=BridgeView(['refresh','refresh','back'])
        await c.run(v)
        self.assertIn('Data belum lengkap','\n'.join(text_of(p) for p in v.events[1][3]))
        self.assertTrue(any(style=='class:success' and val.strip()=='4'
                            for page in v.events[2][3] for row in page for style,val in row))
        self.assertEqual(c.previous.summary['tagihan_terlambat'],4)

    async def test_cancel_and_role_loss_do_not_dispatch(self):
        modules={k:Mock(run=AsyncMock()) for k,_ in ROUTES}
        c,_=setup(modules=modules)
        await c.run(BridgeView([None]))
        c,_=setup(modules=modules,role=Mock(side_effect=[True,True,False]))
        await c.run(BridgeView(['pembayaran']))
        for mod in modules.values():
            mod.run.assert_not_awaited()

    async def test_same_paid_overdue_definition_without_mutating_input(self):
        source=dict(DATA,tagihan_terlambat=1,tagihan_tunggakan=5)
        c,_=setup(summary=Mock(return_value=source),previous=Snapshot(source,[]))
        v=BridgeView(['back'])
        await c.run(v)
        self.assertEqual(c.previous.summary['tagihan_terlambat'],5)
        self.assertEqual(source['tagihan_terlambat'],1)
        self.assertIsNone(c._snapshot({k:v for k,v in source.items() if k!='tagihan_tunggakan'}).summary['tagihan_terlambat'])

    async def test_confirmation_returns_to_selected_queue(self):
        c=confirmation()
        v=BridgeView(['program','back','back'])
        await c.run(v)
        self.assertEqual([e[2]['default'] for e in v.events if e[0]=='PUSAT KONFIRMASI'],
                         ['akun','program'])

class KeyboardTests(unittest.TestCase):
    def test_home_opens_integrated_priority_with_one_enter(self):
        with create_pipe_input() as inp:
            w=AdminDashboardWorkspace('Jaya',input=inp,output=Output(32,108),motion_enabled=False,
                                      load=lambda:Snapshot(DATA,[]),integrated_priority=True)
            async def drive():
                while w.loading:
                    await asyncio.sleep(.01)
                inp.send_text('\r')
            def start():
                w.app.create_background_task(w._fetch())
                w.app.create_background_task(drive())
            self.assertEqual(w.app.run(pre_run=start),'prioritas')

    def test_home_and_priority_share_billing_overdue_count(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from app.ui.admin_workspace import load_snapshot
        import sys
        original=dict(DATA,tagihan_terlambat=1,tagihan_tunggakan=2)
        repo=SimpleNamespace(ringkasan_admin=lambda:original,jadwal_hari_ini_admin=lambda:[])
        with patch.dict(sys.modules,{'app.repositories':SimpleNamespace(admin_dashboard_repo=repo)}):
            snapshot=load_snapshot()
        self.assertEqual(snapshot.summary['tagihan_terlambat'],2)
        self.assertEqual(original['tagihan_terlambat'],1)

    def test_navigator_returns_home_after_priority(self):
        from unittest.mock import patch
        nav=AdminDashboardNavigator(integrated_priority=True)
        fake=Mock(snapshot=Snapshot(DATA,[]))
        fake.run.side_effect=['prioritas','logout']
        with patch('app.ui.admin_workspace.AdminDashboardWorkspace',return_value=fake) as ctor:
            self.assertEqual(nav.choose('Jaya'),'prioritas')
            self.assertEqual(nav.choose('Jaya'),'logout')
        self.assertIsNone(ctor.call_args_list[1].kwargs['initial_group'])
        self.assertTrue(ctor.call_args_list[1].kwargs['integrated_priority'])

    def test_single_workspace_keyboard_full_round_trip_and_safe_refresh(self):
        c,mods=setup()
        with create_pipe_input() as inp:
            w=ConfirmationWorkspace('Jaya',input=inp,output=Output(34,108),motion_enabled=False)
            async def wait(title,choice=None):
                for _ in range(400):
                    if w.title==title and w.mode=='menu' and (choice is None or w.choices[w.index][0]==choice):
                        await asyncio.sleep(.04)
                        return
                    await asyncio.sleep(.01)
                raise AssertionError(f'Expected {title}/{choice}; got {w.title}/{w.mode}/{w.index}')
            async def drive():
                try:
                    await wait('PUSAT PRIORITAS','konfirmasi')
                    inp.send_text('\r')
                    await wait('PUSAT KONFIRMASI','akun')
                    inp.send_text('\x1b[B\r')
                    await wait('ANTREAN KONFIRMASI PENDAFTARAN')
                    inp.send_text('\x1b')
                    await wait('PUSAT KONFIRMASI','program')
                    inp.send_text('\x1b')
                    await wait('PUSAT PRIORITAS','konfirmasi')
                    inp.send_text('\x1b[B')
                    await wait('PUSAT PRIORITAS','pendaftaran')
                    before=c.summary.call_count
                    inp.send_text('r')
                    for _ in range(300):
                        if c.summary.call_count>before and w.mode=='menu':
                            break
                        await asyncio.sleep(.01)
                    await wait('PUSAT PRIORITAS','pendaftaran')
                    self.assertGreater(c.summary.call_count,before)
                    inp.send_text('\r')
                    await wait('MANAJEMEN PENDAFTARAN')
                    inp.send_text('\x1b')
                    await wait('PUSAT PRIORITAS','pendaftaran')
                    inp.send_text('\x1b[B\r')
                    await wait('PUSAT PEMBAYARAN','monthly')
                    inp.send_text('\r')
                    await wait('KONFIRMASI TAGIHAN BULANAN','back')
                    inp.send_text('r')
                    await asyncio.sleep(.08)
                    self.assertEqual(w.title,'KONFIRMASI TAGIHAN BULANAN')
                    self.assertEqual(w.choices[w.index][0],'back')
                    inp.send_text('\r')
                    await wait('PUSAT PEMBAYARAN','monthly')
                    inp.send_text('\x1b')
                    await wait('PUSAT PRIORITAS','pembayaran')
                    inp.send_text('\x1b')
                except Exception as e:
                    w.app.exit(exception=e)
            async def run(v):
                w.app.create_background_task(drive())
                return await c.run(v)
            w.run(run)
        mods['pembayaran'].make_monthly.assert_not_called()
        mods['konfirmasi'].approve_enrollment.assert_not_called()

if __name__=='__main__':
    unittest.main()
