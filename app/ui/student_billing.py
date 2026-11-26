"""UI-007E: student-only billing. Payment simulation and receipts use existing service."""
from __future__ import annotations

from datetime import date,datetime
from decimal import Decimal,InvalidOperation

from .student_features import FeatureController, run_student, fields, column, table_renderer, metrics_pages, empty_pages
from .admin_confirmation import value,rupiah
from .admin_workspace import line


def _date(v):
    return v.strftime('%d-%m-%Y %H:%M' if isinstance(v,datetime) else '%d-%m-%Y') if hasattr(v,'strftime') else str(v or '—')


def _amount(v):
    try:
        n=Decimal(str(v or 0))
        return n if n.is_finite() else Decimal(0)
    except (InvalidOperation,ValueError):
        return Decimal(0)


def overdue(r):
    due=r.get('jatuh_tempo')
    if isinstance(due,datetime):due=due.date()
    if isinstance(due,str):
        try:due=date.fromisoformat(due[:10])
        except ValueError:due=None
    return r.get('invoice_status')=='belum_dibayar' and isinstance(due,date) and due<date.today()


def invoice_status(r):
    if overdue(r):return 'Menunggak'
    return {'belum_dibayar':'Belum dibayar','lunas':'Lunas','batal':'Dibatalkan'}.get(r.get('invoice_status'),value(r,'invoice_status'))


def payment_status(r):
    return {'menunggu_pembayaran':'Menunggu bayar','menunggu_konfirmasi':'Legacy / tinjau',
            'lunas':'Lunas','ditolak':'Ditolak (legacy)','gagal':'Simulasi gagal','direfund':'Direfund'}.get(
            r.get('payment_status'),value(r,'payment_status','Belum ada pembayaran'))


INVOICES=table_renderer([column('Invoice','no_invoice',3),column('Status',invoice_status,2),
    column('Jumlah',lambda r:rupiah(r.get('jumlah')),2),column('Program','nama_program',3),
    column('Jatuh tempo',lambda r:_date(r.get('jatuh_tempo')),2)],
    lambda r:'success' if r.get('invoice_status')=='lunas' else 'warning')
PAYMENTS=table_renderer([column('Kode simulasi','kode_bayar',3),column('Status',payment_status,2),
    column('Nominal',lambda r:rupiah(r.get('payment_jumlah')),2),column('Program','nama_program',3),
    column('Waktu bayar',lambda r:_date(r.get('paid_at')),3)],
    lambda r:'success' if r.get('payment_status')=='lunas' else 'warning')


def invoice_sections(r):
    return [('INVOICE',fields(r,[('Nomor invoice','no_invoice'),('Program','nama_program'),('NIS','nis'),('Siswa','nama_siswa')])+[
            ('Periode',_date(r.get('periode'))),('Jatuh tempo',_date(r.get('jatuh_tempo')))]),
            ('RINCIAN TAGIHAN',[('Jumlah',rupiah(r.get('jumlah'))),('Status',invoice_status(r)),('Pembayaran',payment_status(r))])]


def payment_sections(r):
    return [('TRANSAKSI',fields(r,[('Kode simulasi','kode_bayar'),('Invoice','no_invoice'),('Program','nama_program'),
            ('NIS','nis'),('Siswa','nama_siswa')])+[('Nominal',rupiah(r.get('payment_jumlah'))),
            ('Waktu bayar',_date(r.get('paid_at'))),('Status',payment_status(r))]),
            ('KETERANGAN',fields(r,[('Kode refund','kode_refund'),('Alasan penolakan','alasan_tolak')]))]


def billing_pages(invoices,w,b):
    if not invoices:
        return empty_pages('Belum ada tagihan program untuk akun ini.','Tagihan & pembayaran',width=w,budget=b)
    due=[r for r in invoices if r.get('invoice_status')=='belum_dibayar']
    late=[r for r in due if overdue(r)]
    paid=[r for r in invoices if r.get('invoice_status')=='lunas']
    return metrics_pages([('BELUM LUNAS',str(len(due)),rupiah(sum((_amount(r.get('jumlah')) for r in due),Decimal(0)))),
                         ('MENUNGGAK',str(len(late)),'Lewat jatuh tempo'),
                         ('LUNAS',str(len(paid)),'Invoice lunas')],w,b,
        extra=[('INFORMASI PEMBAYARAN',lambda cw:[line('Checkout hanya simulasi internal SIBIMA.',cw,'title','center'),
            line('Tidak ada uang sungguhan yang dipindahkan.',cw,'muted','center')])])


class BillingController(FeatureController):
    def __init__(self,view,service):
        super().__init__(view)
        self.service=service

    async def run(self):
        focus='tagihan'
        while True:
            invoices=await self.read(self.service.daftar_tagihan_saya)
            if invoices is None:return
            action=await self.view.page('TAGIHAN & PEMBAYARAN',[
                ('tagihan','Tagihan saya'),('bayar','Checkout simulasi'),('riwayat','Riwayat pembayaran'),
                ('bukti_pdf','Unduh bukti pembayaran (PDF)'),('bukti_email','Kirim bukti ke email terdaftar'),
                ('refresh','Muat ulang'),('back','Kembali ke dashboard')],
                lambda w,b:billing_pages(invoices,w,b),default=focus)
            if action in (None,'back'):return
            if action=='refresh':continue
            focus=action
            if action=='tagihan':await self.invoices()
            elif action=='bayar':await self.checkout()
            elif action=='riwayat':await self.history()
            elif action in ('bukti_pdf','bukti_email'):await self.receipts(action)

    async def invoices(self):
        async def load():return await self.read(self.service.daftar_tagihan_saya)
        async def detail(r):await self.details('DETAIL TAGIHAN',invoice_sections(r))
        await self.browse('TAGIHAN SAYA',load,INVOICES,detail,key='invoice_id',
                          empty='Belum ada tagihan untuk akun ini.')

    async def checkout(self):
        while True:
            rows=await self.read(self.service.daftar_tagihan_saya,status='belum_dibayar')
            if rows is None:return
            eligible=[r for r in rows if r.get('invoice_status')=='belum_dibayar' and _amount(r.get('jumlah'))>0]
            r=await self.pick('CHECKOUT SIMULASI',eligible,INVOICES,key='invoice_id',
                    caption='Tagihan belum lunas · pilih invoice',empty='Tidak ada tagihan yang dapat dibayar saat ini.')
            if r=='refresh':continue
            if not r:return
            action=await self.confirm('KONFIRMASI CHECKOUT',invoice_sections(r),
                label='Jalankan simulasi',notice='Tidak ada uang sungguhan yang dipindahkan.')
            if not action:continue
            result=await self.mutate(self.service.bayar_simulasi,r['invoice_id'])
            if result is None:return
            success=result.get('payment_status')=='lunas'
            sections=[('HASIL SIMULASI',[('Status','LUNAS' if success else 'GAGAL'),
                ('Invoice',value(result,'no_invoice')),('Program',value(result,'nama_program')),
                ('Nominal',rupiah(result.get('payment_jumlah'))),('Kode simulasi',value(result,'kode_bayar'))]),
                ('TINDAK LANJUT',[('Tagihan','Lunas. Pendaftaran baru tetap menunggu Admin.' if success else 'Belum lunas; dapat mencoba kembali.'),
                    ('Email','Berhasil diproses' if result.get('email_sent') else 'Belum terkirim'),
                    ('Keterangan',value(result,'email_message'))])]
            await self.details('SIMULASI BERHASIL' if success else 'SIMULASI GAGAL',sections,
                notice='Simulasi internal SIBIMA, tanpa uang sungguhan.')
            return

    async def history(self):
        async def load():return await self.read(self.service.riwayat_pembayaran_saya)
        async def detail(r):await self.details('DETAIL PEMBAYARAN',payment_sections(r))
        await self.browse('RIWAYAT PEMBAYARAN',load,PAYMENTS,detail,key='payment_id',
                          empty='Belum ada riwayat pembayaran.')

    async def receipts(self,mode):
        while True:
            rows=await self.read(self.service.riwayat_pembayaran_saya)
            if rows is None:return
            r=await self.pick('BUKTI PEMBAYARAN', [x for x in rows if x.get('payment_status')=='lunas'],
                PAYMENTS,key='payment_id',caption='Hanya pembayaran lunas',empty='Belum ada pembayaran lunas untuk dibuatkan bukti.')
            if r=='refresh':continue
            if not r:return
            payment_id=r['payment_id']
            # Service performs an ownership/status check again for both actions.
            if mode=='bukti_pdf':
                if not await self.confirm('UNDUH BUKTI PDF',payment_sections(r),label='Buat PDF'):
                    continue
                path=await self.mutate(self.service.buat_bukti_pembayaran_pdf,payment_id)
                if path is not None:
                    await self.view.result('PDF BERHASIL DIBUAT',f'Bukti pembayaran tersimpan: {path}','success')
                return
            detail=await self.read(self.service.bukti_pembayaran_saya,payment_id)
            if detail is None:return
            email=str(detail.get('email_siswa') or '').strip()
            if not email:
                await self.view.result('EMAIL TIDAK TERSEDIA','Periksa alamat email akun terdaftar.','error');return
            if not await self.confirm('KIRIM BUKTI PEMBAYARAN',payment_sections(r)+[
                    ('PENERIMA',[('Email terdaftar',email)])],label='Ya, kirim bukti'):
                continue
            result=await self.mutate(self.service.kirim_bukti_pembayaran_email,payment_id)
            if result is not None:
                message=result.get('message') or ('Bukti terkirim.' if result.get('sent') else 'Email belum terkirim.')
                if not result.get('sent') and result.get('path'):
                    message+=' PDF tetap tersimpan: '+str(result['path'])
                await self.view.result('BUKTI TERKIRIM' if result.get('sent') else 'EMAIL BELUM TERKIRIM',
                    message,'success' if result.get('sent') else 'error')
            return


def menu_pembayaran_siswa():
    from app.services import billing_service
    async def flow(view):
        return await BillingController(view,billing_service).run()
    return run_student(flow)
