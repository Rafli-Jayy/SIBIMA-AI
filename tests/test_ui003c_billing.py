"""Billing workspace tests; all service calls use fixture data."""
import ast
import asyncio
import unittest
from datetime import date,datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock,call
from prompt_toolkit.input import create_pipe_input
from app.ui.admin_confirmation import ConfirmationWorkspace, details_pages
from app.ui.admin_billing import (
    BillingController, CARDS, dashboard_pages, invoice_row, payment_row, invoice_status,
    invoice_sections, transaction_sections, monthly_sections, receipt_sections, limited_caption,
)
from app.ui.admin_workspace import width_of
from test_ui002_admin_workspace import SUMMARY, Output, screen, text_of
from test_ui003b_enrollment import View

STATS=dict(SUMMARY,tagihan_bulanan_siap=12,nominal_tagihan_bulanan_siap=3000000,
           tagihan_tunggakan=2,nominal_tunggakan=500000,nominal_refund_bulan_ini=250000,
           periode_tagihan_bulanan=date(2026,11,1),tanggal_db=date(2026,11,26),
           jatuh_tempo_tagihan_bulanan=date(2026,12,3))
INVOICE=dict(invoice_id=41,no_invoice='INV-202611-000041',periode=date(2026,11,1),
             jumlah=Decimal('250000'),jatuh_tempo=date(2026,11,20),invoice_status='belum_dibayar',
             invoice_created_at=datetime(2026,11,13,8),enrollment_id=31,enrollment_status='aktif',
             nama_siswa='Andi Pratama',nis='S-0021',nama_program='Matematika SMA',kode_program='MTK',
             email='andi@example.test',payment_id=None,kode_bayar=None,payment_status=None,
             payment_jumlah=None,paid_at=None)
OPEN=dict(INVOICE,invoice_id=42,no_invoice='INV-202611-000042',nama_siswa='Nadia Putri',
          jatuh_tempo=date(2026,12,3),nama_program='Bahasa Inggris')
PAID=dict(INVOICE,invoice_id=43,no_invoice='INV-202611-000043',nama_siswa='Raka Wijaya',
          invoice_status='lunas',payment_id=61,kode_bayar='SIM-202611-000061',
          payment_status='lunas',payment_jumlah=300000,paid_at=datetime(2026,11,25,10),
          jumlah=300000,nama_program='Fisika SMA')
PAYMENT=dict(PAID,invoice_jumlah=300000,payment_created_at=datetime(2026,11,25,10),
             processed_at=datetime(2026,11,25,10),kode_refund=None,refund_status=None,
             refund_created_at=None,alasan_tolak=None)
FAILED=dict(PAYMENT,payment_id=62,kode_bayar='SIM-202611-000062',nama_siswa='Nadia Putri',
            payment_status='gagal',invoice_status='belum_dibayar',paid_at=None)
REFUND=dict(PAYMENT,payment_id=63,kode_bayar='SIM-202611-000063',nama_siswa='Andi Pratama',
            payment_status='direfund',kode_refund='RFD-003',refund_status='berhasil',
            refund_created_at=datetime(2026,11,24,12))
RECEIPT=dict(PAYMENT,email_siswa='raka@example.test')
PATH=r'C:\SIBIMA-AI\storage\bukti\SIM-202611-000061.pdf'

def make_controller(**overrides):
    def list_rows(status,overdue):
        return [i for i in (INVOICE,OPEN,PAID) if (status is None or i['invoice_status']==status)
                and (not overdue or invoice_status(i,STATS['tanggal_db'])=='menunggak')]
    args=dict(summary=Mock(return_value=STATS), invoices=Mock(side_effect=list_rows),
              history=Mock(return_value=[PAYMENT,FAILED,REFUND]), receipt=Mock(return_value=RECEIPT),
              make_monthly=Mock(return_value=dict(dibuat=11,email_terkirim=10,email_gagal=1)),
              make_pdf=Mock(return_value=PATH),
              send_email=Mock(return_value=dict(sent=False,path=PATH,email='raka@example.test',message='SMTP gagal')),
              is_admin=Mock(return_value=True))
    args.update(overrides)
    return BillingController(**args)

class BillingFlows(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_focus_refresh_and_monthly_cancel(self):
        c=make_controller()
        v=View(['monthly','back','refresh','back'])
        await c.run(v)
        c.make_monthly.assert_not_called()
        self.assertEqual(c.summary.call_count,4)
        self.assertEqual([e[2]['default'] for e in v.events if e[0]=='PUSAT PEMBAYARAN'],
                         ['monthly','monthly','refresh'])
        self.assertEqual(next(e for e in v.events if e[0]=='KONFIRMASI TAGIHAN BULANAN')[2]['default'],'back')

    async def test_monthly_partial_delivery_uses_actual_result(self):
        c=make_controller()
        v=View(['confirm','back'])
        await c.monthly(v)
        c.make_monthly.assert_called_once_with()
        review,result=v.events
        body='\n'.join(text_of(p) for p in review[3])
        for word in ('12','Rp3.000.000','03/12/2026','11/2026'):
            self.assertIn(word,body)
        body='\n'.join(text_of(p) for p in result[3])
        for word in ('11','10','Email gagal','pengiriman email perlu diperiksa'):
            self.assertIn(word,body)

    async def test_missing_summary_and_unknown_no_repeat(self):
        c=make_controller(summary=Mock(return_value={}))
        await c.monthly(View([]))
        c.make_monthly.assert_not_called()
        c=make_controller(make_monthly=Mock(side_effect=RuntimeError('secret')))
        v=View(['confirm'])
        await c.monthly(v)
        c.make_monthly.assert_called_once_with()
        self.assertIn('HASIL BELUM DAPAT DIPASTIKAN',str(v.events))
        self.assertNotIn('secret',str(v.events))

    async def test_zero_created(self):
        c=make_controller(make_monthly=Mock(return_value=dict(dibuat=0,email_terkirim=0,email_gagal=0)))
        v=View(['confirm','back'])
        await c.monthly(v)
        self.assertIn('Tidak ada tagihan baru','\n'.join(text_of(p) for p in v.events[-1][3]))

    async def test_invoice_filters_keep_selected_item(self):
        c=make_controller()
        c.today=STATS['tanggal_db']
        v=View(['all',41,'back','filter','lunas','refresh',43,'back','back'])
        await c.browse_invoices(v)
        self.assertEqual(c.invoices.call_args_list,[call(None,False),call(None,False),
                                                  call('lunas',False),call('lunas',False),call('lunas',False)])
        tables=[e for e in v.events if e[0]=='DAFTAR TAGIHAN']
        self.assertEqual(tables[1][2]['initial'],41)
        self.assertEqual(tables[-1][2]['initial'],43)

    async def test_overdue_only_and_no_filter(self):
        c=make_controller()
        v=View(['back'])
        await c.browse_invoices(v,overdue=True)
        c.invoices.assert_called_once_with(None,True)
        self.assertEqual(v.events[0][1],[INVOICE])
        self.assertFalse(v.events[0][2]['filter_action'])

    async def test_history_filter_and_detail(self):
        c=make_controller()
        v=View(['filter','direfund',63,'back','back'])
        await c.browse_history(v)
        tables=[e for e in v.events if e[0]=='RIWAYAT PEMBAYARAN']
        self.assertEqual(tables[1][1],[REFUND])
        self.assertEqual(tables[-1][2]['initial'],63)
        body='\n'.join(text_of(p) for p in next(e for e in v.events if e[0]=='DETAIL PEMBAYARAN')[3])
        self.assertIn('RFD-003',body)

    async def test_pdf_confirm_and_cancel(self):
        c=make_controller()
        v=View([61,'back','back'])
        await c.receipt_flow(v)
        self.assertEqual(v.events[0][1],[PAYMENT])
        self.assertEqual(v.events[1][2]['default'],'back')
        c.make_pdf.assert_not_called()
        v=View([61,'confirm','back'])
        await c.receipt_flow(v)
        c.make_pdf.assert_called_once_with(61)
        self.assertIn(PATH,'\n'.join(text_of(p) for p in v.events[-1][3]))

    async def test_email_failure_retains_path_and_recipient(self):
        c=make_controller()
        v=View([61,'confirm','back'])
        await c.receipt_flow(v,email=True)
        self.assertEqual(c.receipt.call_args_list,[call(61),call(61)])
        c.send_email.assert_called_once_with(61)
        self.assertEqual(v.events[-1][0],'EMAIL BELUM TERKIRIM')
        body='\n'.join(text_of(p) for p in v.events[-1][3])
        self.assertIn(PATH,body)
        self.assertIn('raka@example.test',body)

    async def test_email_cancel_and_blank_or_changed_recipient(self):
        c=make_controller()
        await c.receipt_flow(View([61,'back','back']),email=True)
        c.send_email.assert_not_called()
        for receipt in (Mock(return_value=dict(RECEIPT,email_siswa='  ')),
                        Mock(return_value=dict(RECEIPT,payment_status='direfund'))):
            c=make_controller(receipt=receipt)
            v=View([61,'back'])
            await c.receipt_flow(v,email=True)
            c.send_email.assert_not_called()
        c=make_controller(receipt=Mock(side_effect=[RECEIPT,dict(RECEIPT,email_siswa='new@example.test')]))
        v=View([61,'confirm','back'])
        await c.receipt_flow(v,email=True)
        c.send_email.assert_not_called()
        self.assertIn('DATA BERUBAH',str(v.events))

    async def test_role_rechecked_before_monthly_confirmation(self):
        c=make_controller(is_admin=Mock(side_effect=[True,False]))
        await c.monthly(View(['confirm']))
        c.make_monthly.assert_not_called()

class RenderTests(unittest.TestCase):
    def test_read_only_sql_matches_candidate_eligibility(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'app/repositories/admin_dashboard_repo.py').read_text())
        sql=next(n.value.value for n in tree.body if isinstance(n,ast.Assign)
                 and n.targets[0].id=='_SQL_RINGKASAN')
        for word in ("e.status = 'aktif' AND p.harga_bulanan > 0","NOT EXISTS",
                     "i.periode = date_trunc('month', CURRENT_DATE)::date","CURRENT_DATE + 7",
                     "AS nominal_refund_bulan_ini","AS tagihan_tunggakan"):
            self.assertIn(word,sql)
        for key in [k for _,metrics in CARDS for k,_,_ in metrics]:
            self.assertIn('AS '+key,sql)
        self.assertNotRegex(sql,r'\b(INSERT|UPDATE|DELETE|ALTER|TRUNCATE)\b')

    def test_dashboard_and_detail_render_bounded(self):
        long=dict(INVOICE,nama_siswa='漢字 '*100,email='a'*180+'@example.test')
        for w in (38,46,65,78,100):
            for b in (1,4,9,28):
                for pages in (dashboard_pages(STATS,w,b),dashboard_pages(None,w,b),
                  details_pages(invoice_sections(long),w,b,full=True,paired=True),
                  details_pages(transaction_sections(REFUND),w,b,full=True,paired=True),
                  details_pages(monthly_sections(STATS),w,b,full=True,paired=True),
                  details_pages(receipt_sections(RECEIPT),w,b,full=True,paired=True)):
                    self.assertTrue(pages)
                    for page in pages:
                        self.assertLessEqual(len(page),b)
                        self.assertTrue(all(width_of(row)<=w for row in page))
        self.assertIn('Data belum lengkap',text_of(dashboard_pages(None,100,40)[0]))

    def test_table_dimensions_dates_and_status(self):
        for w in (38,46,65,78,94,100):
            for row in (invoice_row(w),invoice_row(w,INVOICE,today=STATS['tanggal_db']),
                        payment_row(w),payment_row(w,PAYMENT,selected=True)):
                self.assertLessEqual(width_of(row),w)
        for w in (65,78,94,100):
            self.assertIn('25/11/2026',text_of([payment_row(w,PAYMENT)]))
        self.assertIn('Menunggak',text_of([invoice_row(100,INVOICE,today=STATS['tanggal_db'])]))
        self.assertIn('20/11/2026',text_of([invoice_row(100,INVOICE,today=STATS['tanggal_db'])]))
        self.assertEqual(invoice_status(OPEN,STATS['tanggal_db']),'belum_dibayar')
        self.assertIn('300',limited_caption('Data',[None]*300))

    def test_real_keyboard_defaults_cancel_monthly(self):
        with create_pipe_input() as inp:
            w=ConfirmationWorkspace('Jaya',input=inp,output=Output(29,108),motion_enabled=False)
            c=make_controller()
            async def wait(title):
                for _ in range(300):
                    if w.title==title and w.mode=='menu':
                        await asyncio.sleep(.04)
                        return
                    await asyncio.sleep(.01)
                raise AssertionError(f'Expected {title}, got {w.title}')
            async def drive():
                try:
                    await wait('PUSAT PEMBAYARAN')
                    inp.send_text('\r')
                    await wait('KONFIRMASI TAGIHAN BULANAN')
                    self.assertRegex('\n'.join(screen(w)),r'❯ +Batal')
                    inp.send_text('\r')
                    await wait('PUSAT PEMBAYARAN')
                    inp.send_text('\x1b')
                except Exception as exc:
                    w.app.exit(exception=exc)
            async def run(v):
                w.app.create_background_task(drive())
                await c.run(v)
            w.run(run)
            c.make_monthly.assert_not_called()

if __name__=='__main__':
    unittest.main()
