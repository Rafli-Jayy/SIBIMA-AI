"""UI-003C: Admin billing workspace, using existing simulation services only."""
from __future__ import annotations

from datetime import date, datetime

from .admin_confirmation import ConfirmationWorkspace, details_pages, value, rupiah
from .admin_workspace import (
    Snapshot, line, pad, width_of, _metric_bands, _stat_rows,
    _compact_section, paginate_blocks,
)

INVOICE_LABELS = {
    'belum_dibayar':'Belum lunas','lunas':'Lunas','batal':'Dibatalkan',
}
PAYMENT_LABELS = {
    'menunggu_pembayaran':'Menunggu bayar',
    'menunggu_konfirmasi':'Legacy: tinjau',
    'lunas':'Lunas','ditolak':'Ditolak (legacy)','gagal':'Simulasi gagal','direfund':'Direfund',
}
TONES = {
    'lunas':'success','belum_dibayar':'warning','menunggak':'error',
    'batal':'muted','menunggu_pembayaran':'warning','menunggu_konfirmasi':'warning',
    'ditolak':'error','gagal':'error','direfund':'number',
}
CARDS = (
    ('PEMBAYARAN LUNAS · BULAN INI',(
        ('nominal_lunas_bulan_ini','Nominal (Rp)',None),
        ('transaksi_lunas_bulan_ini','Transaksi lunas',None),
    )),
    ('TAGIHAN BELUM LUNAS',(
        ('nominal_belum_lunas','Nominal (Rp)',None),
        ('tagihan_belum_lunas','Jumlah tagihan',None),
    )),
    ('TUNGGAKAN',(
        ('nominal_tunggakan','Nominal (Rp)',None),
        ('tagihan_tunggakan','Lewat jatuh tempo',None),
    )),
    ('REFUND BERHASIL · BULAN INI',(
        ('nominal_refund_bulan_ini','Nominal (Rp)',None),
        ('refund_bulan_ini','Jumlah refund',None),
    )),
)


def dashboard_pages(summary,width,budget,changed=frozenset()):
    budget=max(1,budget)
    snapshot=Snapshot(summary,None)
    blocks=[]
    for block,items in _metric_bands(snapshot,width,changed,CARDS):
        if len(block)<=budget:
            blocks.append(block)
        else:
            for title,metrics in items:
                blocks.extend(_compact_section(title,_stat_rows(snapshot,width,metrics,changed),width,budget))
    complete=(summary is not None and all(summary.get(k) is not None for _,items in CARDS for k,_,_ in items)
              and summary.get('tagihan_bulanan_siap') is not None)
    if complete:
        blocks.append([line(f"Calon tagihan bulanan: {snapshot.value('tagihan_bulanan_siap')} · Data terakhir dimuat ●",
                            width,'muted','center')])
    else:
        blocks.append([line('Data belum lengkap · Muat ulang',width,'warning','center')])
    blocks.append([line('Transaksi simulasi internal; tidak ada uang sungguhan.',width,'muted','center')])
    return paginate_blocks(blocks,budget)


def short_date(raw,*,period=False):
    if isinstance(raw,(date,datetime)):
        return raw.strftime('%m/%Y' if period else '%d/%m/%Y')
    return str(raw)[:10] if raw is not None else '—'


def invoice_status(item,today=None,*,overdue=False):
    raw=item.get('invoice_status')
    due=item.get('jatuh_tempo')
    if raw=='belum_dibayar':
        if overdue or (type(due) is date and type(today) is date and due<today):
            return 'menunggak'
    return raw


def invoice_label(item,today=None,*,overdue=False):
    status=invoice_status(item,today,overdue=overdue)
    return 'Menunggak' if status=='menunggak' else INVOICE_LABELS.get(status,value(item,'invoice_status'))


def payment_label(item):
    raw=item.get('payment_status')
    if raw is None:
        return 'Belum ada transaksi'
    return PAYMENT_LABELS.get(raw,value(item,'payment_status'))


def table_row(width,columns,fields,selected=False,header=False,status=None):
    tone='class:selected' if selected else 'class:muted' if header else 'class:title'
    row=[(tone,'❯ ' if selected else '  ')]
    for i,((label,cw),v) in enumerate(zip(columns,fields)):
        if i:
            row.append((tone,' '))
        style=('class:'+TONES.get(status,'muted') if label=='Status' and not selected and not header else tone)
        row.append((style,pad(v,cw,'right' if label=='Nominal' else 'left')))
    if width_of(row)>width:
        return [(tone,pad(''.join(t for _,t in row),width))]
    return row


def invoice_row(width,item=None,selected=False,*,today=None,overdue=False):
    if width>=94:
        # 100 cols: ID 5, invoice 20, names 14/14, amount 13, due 11, status 15.
        rem=width-72
        columns=[('ID',5),('No. Invoice',20),('Siswa',rem//2),('Program',rem-rem//2),
                 ('Nominal',13),('Jatuh tempo',11),('Status',15)]
        fields=(value(item,'invoice_id'),value(item,'no_invoice'),value(item,'nama_siswa'),
                value(item,'nama_program'),rupiah(item.get('jumlah')),short_date(item.get('jatuh_tempo')),
                invoice_label(item,today,overdue=overdue)) if item else ()
    elif width>=65:
        rem=width-48
        columns=[('ID',5),('No. Invoice',18),('Siswa',rem),('Nominal',13),('Status',6)]
        fields=(value(item,'invoice_id'),value(item,'no_invoice'),value(item,'nama_siswa'),
                rupiah(item.get('jumlah')),invoice_label(item,today,overdue=overdue)) if item else ()
        # At narrower widths use an explicitly short status, not ambiguous truncation.
        if item:
            fields=(*fields[:-1],{'belum_dibayar':'Belum','lunas':'Lunas','batal':'Batal','menunggak':'Telat'}
                    .get(invoice_status(item,today,overdue=overdue),'—'))
    else:
        rem=max(1,width-26)
        columns=[('ID',5),('Siswa',rem),('Nominal',10),('Status',6)]
        fields=(value(item,'invoice_id'),value(item,'nama_siswa'),rupiah(item.get('jumlah')),
                {'belum_dibayar':'Belum','lunas':'Lunas','batal':'Batal','menunggak':'Telat'}
                 .get(invoice_status(item,today,overdue=overdue),'—')) if item else ()
    return table_row(width,columns,fields or [label for label,_ in columns],selected,item is None,
                     invoice_status(item,today,overdue=overdue) if item else None)


def payment_row(width,item=None,selected=False):
    if width>=94:
        rem=width-74
        columns=[('ID',5),('Kode Simulasi',23),('Siswa',rem),('Nominal',13),('Status',16),('Tanggal',10)]
        fields=(value(item,'payment_id'),value(item,'kode_bayar'),value(item,'nama_siswa'),
                rupiah(item.get('payment_jumlah')),payment_label(item),
                short_date(item.get('paid_at') or item.get('payment_created_at'))) if item else ()
    elif width>=65:
        rem=width-50
        columns=[('ID',5),('Siswa',rem),('Nominal',13),('Status',16),('Tanggal',10)]
        fields=(value(item,'payment_id'),value(item,'nama_siswa'),rupiah(item.get('payment_jumlah')),
                payment_label(item),short_date(item.get('paid_at') or item.get('payment_created_at'))) if item else ()
    else:
        rem=max(1,width-31)
        columns=[('ID',5),('Siswa',rem),('Nominal',10),('Status',11)]
        fields=(value(item,'payment_id'),value(item,'nama_siswa'),rupiah(item.get('payment_jumlah')),
                {'lunas':'Lunas','gagal':'Gagal','direfund':'Direfund','ditolak':'Ditolak',
                 'menunggu_konfirmasi':'Legacy','menunggu_pembayaran':'Menunggu'}.get(item.get('payment_status'),'—')) if item else ()
    return table_row(width,columns,fields or [label for label,_ in columns],selected,item is None,
                     item.get('payment_status') if item else None)


def invoice_sections(item,today=None,*,overdue=False):
    return [
        ('SISWA & PROGRAM',[
            ('Nama siswa',value(item,'nama_siswa')),('NIS',value(item,'nis')),
            ('Program',value(item,'nama_program')),('Kode',value(item,'kode_program')),
            ('Pendaftaran',value(item,'enrollment_status')),
        ]),
        ('INFORMASI TAGIHAN',[
            ('Invoice',value(item,'no_invoice')),('Periode',short_date(item.get('periode'),period=True)),
            ('Jatuh tempo',short_date(item.get('jatuh_tempo'))),('Nominal',rupiah(item.get('jumlah'))),
            ('Status',invoice_label(item,today,overdue=overdue)),
        ]),
        ('PEMBAYARAN TERAKHIR',[
            ('Kode simulasi',value(item,'kode_bayar')),('Nominal',rupiah(item.get('payment_jumlah'))),
            ('Status',payment_label(item)),('Waktu bayar',value(item,'paid_at')),
        ]),
        ('REFERENSI',[
            ('ID tagihan',value(item,'invoice_id')),('ID pendaftaran',value(item,'enrollment_id')),
            ('Dibuat pada',value(item,'invoice_created_at')),('Email siswa',value(item,'email')),
        ]),
    ]


def transaction_sections(item):
    return [
        ('SISWA & PROGRAM',[
            ('Nama siswa',value(item,'nama_siswa')),('NIS',value(item,'nis')),
            ('Program',value(item,'nama_program')),('Kode program',value(item,'kode_program')),
        ]),
        ('TRANSAKSI SIMULASI',[
            ('Kode simulasi',value(item,'kode_bayar')),('Nominal',rupiah(item.get('payment_jumlah'))),
            ('Status',payment_label(item)),('Waktu bayar',value(item,'paid_at')),
            ('Dibuat pada',value(item,'payment_created_at')),
            ('Diproses pada',value(item,'processed_at')),
        ]),
        ('TAGIHAN',[
            ('Invoice',value(item,'no_invoice')),('Periode',short_date(item.get('periode'),period=True)),
            ('Nominal tagihan',rupiah(item.get('invoice_jumlah'))),
            ('Jatuh tempo',short_date(item.get('jatuh_tempo'))),
            ('Status tagihan',value(item,'invoice_status')),
        ]),
        ('REFUND & CATATAN',[
            ('Kode refund',value(item,'kode_refund')),('Status refund',value(item,'refund_status')),
            ('Tanggal refund',value(item,'refund_created_at')),('Alasan',value(item,'alasan_tolak')),
        ]),
    ]


def monthly_sections(summary):
    summary=summary or {}
    return [
        ('PREVIEW TAGIHAN BULANAN',[
            ('Periode',short_date(summary.get('periode_tagihan_bulanan'),period=True)),
            ('Jatuh tempo',short_date(summary.get('jatuh_tempo_tagihan_bulanan'))),
            ('Calon tagihan',value(summary,'tagihan_bulanan_siap')),
            ('Estimasi nominal',rupiah(summary.get('nominal_tagihan_bulanan_siap'))),
        ]),
        ('ATURAN PEMBUATAN',[
            ('Pendaftaran','Aktif; program berbayar.'),
            ('Periode','Bulan berjalan, tanpa tagihan duplikat.'),
            ('Email','Tagihan baru dikirim ke email siswa.'),
            ('Catatan','Estimasi dapat berubah saat diproses.'),
        ]),
    ]


def receipt_sections(item,*,email=False):
    left=[('Nama siswa',value(item,'nama_siswa')),('NIS',value(item,'nis')),
          ('Program',value(item,'nama_program')),('Email terdaftar',value(item,'email_siswa'))]
    return [
        ('PENERIMA BUKTI' if email else 'IDENTITAS PEMBAYARAN',left),
        ('BUKTI PEMBAYARAN',[
            ('Invoice',value(item,'no_invoice')),('Kode simulasi',value(item,'kode_bayar')),
            ('Nominal',rupiah(item.get('payment_jumlah'))),('Status',payment_label(item)),
            ('Waktu bayar',value(item,'paid_at')),
        ]),
    ]


def limited_caption(base,rows):
    # The existing service returns at most 300; do not imply an unbounded list.
    return base+(' · Maks. 300 baris dari service' if len(rows)>=300 else '')


class BillingController:
    """UI orchestration only. Existing billing_service validates roles and writes."""
    def __init__(self,*,summary,invoices,history,receipt,make_monthly,make_pdf,send_email,is_admin):
        self.summary=summary
        self.invoices=invoices
        self.history=history
        self.receipt=receipt
        self.make_monthly=make_monthly
        self.make_pdf=make_pdf
        self.send_email=send_email
        self.is_admin=is_admin
        self.today=None

    async def _read(self,view,title,fn,*args):
        try:
            data=await view.busy(title,fn,*args)
            if data is None:
                raise LookupError('Data tidak tersedia.')
            return data
        except (ValueError,PermissionError,LookupError) as exc:
            await view.result('DATA BELUM TERSEDIA',str(exc),'error')
        except Exception:
            await view.result('DATA GAGAL DIMUAT','Periksa koneksi, lalu coba lagi.','error')
        return None

    async def run(self,view):
        previous=None
        focus='monthly'
        while self.is_admin():
            try:
                summary=await view.busy('Memuat ringkasan...',self.summary)
            except Exception:
                summary=None
            self.today=summary.get('tanggal_db') if summary else None
            keys={k for _,items in CARDS for k,_,_ in items}
            changed={k for k in keys if previous is not None and summary is not None
                     and previous.get(k) is not None and summary.get(k) is not None
                     and previous[k]!=summary[k]}
            if summary is not None:
                previous=summary
            action=await view.page('PUSAT PEMBAYARAN',[
                ('monthly','Buat Tagihan Bulanan'),('invoices','Daftar Tagihan'),
                ('overdue','Daftar Tunggakan'),('history','Riwayat Pembayaran'),
                ('pdf','Unduh Bukti PDF'),('email','Kirim Bukti via Email'),
                ('refresh','Muat ulang'),('back','Kembali ke Prioritas')],
                lambda w,b:dashboard_pages(summary,w,b,changed),default=focus)
            if action in (None,'back'):
                return
            if action=='monthly':
                await self.monthly(view)
            elif action in ('invoices','overdue'):
                await self.browse_invoices(view,overdue=action=='overdue')
            elif action=='history':
                await self.browse_history(view)
            elif action in ('pdf','email'):
                await self.receipt_flow(view,email=action=='email')
            focus=(getattr(view,'refresh_focus',None) or action) if action=='refresh' else action

    async def monthly(self,view):
        if not self.is_admin():
            return
        summary=await self._read(view,'Memuat calon tagihan...',self.summary)
        if summary is None:
            return
        if any(summary.get(key) is None for key in ('tagihan_bulanan_siap','nominal_tagihan_bulanan_siap',
                                                    'periode_tagihan_bulanan','jatuh_tempo_tagihan_bulanan')):
            await view.result('DATA BELUM LENGKAP','Preview tagihan belum tersedia. Muat ulang.','error')
            return
        choice=await view.page('KONFIRMASI TAGIHAN BULANAN',
            [('confirm','Ya, buat tagihan bulanan'),('back','Batal')],
            lambda w,b:details_pages(monthly_sections(summary),w,b,full=True,paired=True),default='back')
        if choice!='confirm' or not self.is_admin():
            return
        try:
            result=await view.busy('Membuat tagihan...',self.make_monthly)
            counts={k:result[k] for k in ('dibuat','email_terkirim','email_gagal')}
            if any(type(v) is not int or v<0 for v in counts.values()):
                raise ValueError('Hasil tidak valid')
        except Exception:
            # A service exception may occur after database commit.
            await view.result('HASIL BELUM DAPAT DIPASTIKAN',
                'Periksa daftar tagihan sebelum mengulangi tindakan.','warning')
            return
        sections=[('HASIL PEMBUATAN',[
            ('Tagihan baru',str(counts['dibuat'])),
            ('Email terkirim',str(counts['email_terkirim'])),
            ('Email gagal',str(counts['email_gagal'])),
        ])]
        note=('Tagihan tersimpan; pengiriman email perlu diperiksa.' if counts['email_gagal']
              else 'Tidak ada tagihan baru untuk periode ini.' if not counts['dibuat']
              else 'Pembuatan selesai.')
        await view.page('HASIL TAGIHAN BULANAN',[('back','Lanjutkan')],
            lambda w,b:details_pages(sections,w,b,notice=note,full=True))

    async def _invoice_filter(self,view,status):
        options=[('all','Semua status')]+list(INVOICE_LABELS.items())+[('back','Kembali')]
        return await view.page('FILTER STATUS TAGIHAN',options,
            lambda w,b:[[line('Pilih status tagihan',w,'muted','center')]],default=status or 'all')

    async def browse_invoices(self,view,*,overdue=False):
        status=None
        initial=None
        if not overdue:
            selected=await self._invoice_filter(view,status)
            if selected in (None,'back'):
                return
            status=None if selected=='all' else selected
        while self.is_admin():
            rows=await self._read(view,'Memuat tagihan...',self.invoices,status,overdue)
            if rows is None:
                return
            caption='Belum lunas · Lewat jatuh tempo' if overdue else INVOICE_LABELS.get(status,'Semua status')
            selected=await view.record_table('DAFTAR TUNGGAKAN' if overdue else 'DAFTAR TAGIHAN',rows,
                key='invoice_id',renderer=lambda w,item=None,selected=False:invoice_row(
                    w,item,selected,today=self.today,overdue=overdue),
                caption=limited_caption(caption,rows),empty='Tidak ada tagihan sesuai kriteria.',
                filter_action=not overdue,initial=initial)
            if selected=='filter' and not overdue:
                new=await self._invoice_filter(view,status)
                if new in (None,'back'):
                    continue
                status=None if new=='all' else new
                initial=None
                continue
            if selected=='refresh':
                continue
            item=next((x for x in rows if x['invoice_id']==selected),None)
            if item is None:
                return
            initial=selected
            await view.page('DETAIL TAGIHAN',[('back','Kembali ke daftar')],
                lambda w,b:details_pages(invoice_sections(item,self.today,overdue=overdue),
                                         w,b,full=True,paired=True))

    async def _payment_filter(self,view,status):
        choices=[('all','Semua status')]+list(PAYMENT_LABELS.items())+[('back','Kembali')]
        return await view.page('FILTER RIWAYAT PEMBAYARAN',choices,
            lambda w,b:[[line('Filter pada hasil riwayat yang dimuat',w,'muted','center')]],default=status or 'all')

    async def browse_history(self,view):
        status=None
        initial=None
        while self.is_admin():
            records=await self._read(view,'Memuat riwayat...',self.history)
            if records is None:
                return
            rows=[x for x in records if status is None or x.get('payment_status')==status]
            selected=await view.record_table('RIWAYAT PEMBAYARAN',rows,key='payment_id',renderer=payment_row,
                caption=limited_caption(PAYMENT_LABELS.get(status,'Semua status')+' · Urutan terbaru',records),
                empty='Tidak ada transaksi sesuai filter.',filter_action=True,initial=initial)
            if selected=='filter':
                new=await self._payment_filter(view,status)
                if new not in (None,'back'):
                    status=None if new=='all' else new
                    initial=None
                continue
            if selected=='refresh':
                continue
            item=next((x for x in rows if x['payment_id']==selected),None)
            if item is None:
                return
            initial=selected
            await view.page('DETAIL PEMBAYARAN',[('back','Kembali ke riwayat')],
                lambda w,b:details_pages(transaction_sections(item),w,b,full=True,paired=True))

    async def receipt_flow(self,view,*,email=False):
        initial=None
        while self.is_admin():
            records=await self._read(view,'Memuat pembayaran lunas...',self.history)
            if records is None:
                return
            paid=[r for r in records if r.get('payment_status')=='lunas']
            selected=await view.record_table('PILIH BUKTI UNTUK EMAIL' if email else 'PILIH BUKTI PDF',paid,
                key='payment_id',renderer=payment_row,caption=limited_caption('Pembayaran berstatus lunas',records),
                empty='Tidak ada pembayaran lunas yang dapat dipilih.',initial=initial)
            if selected=='refresh':
                continue
            if type(selected) is not int or not any(x['payment_id']==selected for x in paid):
                return
            initial=selected
            # Recheck paid receipt and recipient using the same service as legacy selection.
            try:
                item=await view.busy('Memuat detail bukti...',self.receipt,selected)
            except Exception:
                await view.result('DATA GAGAL DIMUAT','Detail bukti gagal dimuat. Coba lagi.','error')
                return
            if not item or item.get('payment_status')!='lunas':
                await view.result('BUKTI TIDAK TERSEDIA','Bukti hanya tersedia untuk pembayaran lunas.','warning')
                continue
            address=str(item.get('email_siswa') or '').strip()
            if email and not address:
                await view.result('EMAIL BELUM TERSEDIA','Periksa email terdaftar siswa terlebih dahulu.','warning')
                continue
            choice=await view.page('KONFIRMASI KIRIM EMAIL' if email else 'KONFIRMASI BUKTI PDF',[
                ('confirm','Ya, kirim bukti' if email else 'Ya, buat PDF'),('back','Batal')],
                lambda w,b:details_pages(receipt_sections(item,email=email),w,b,full=True,paired=True),
                default='back')
            if choice!='confirm':
                continue
            if not self.is_admin():
                return
            if email:
                try:
                    fresh=await view.busy('Memeriksa penerima...',self.receipt,selected)
                except Exception:
                    await view.result('DATA GAGAL DIMUAT','Penerima tidak dapat diperiksa. Coba lagi.','error')
                    return
                if not fresh or fresh.get('payment_status')!='lunas' or str(fresh.get('email_siswa') or '').strip()!=address:
                    await view.result('DATA BERUBAH','Periksa ulang status pembayaran dan email penerima.','warning')
                    continue
                if not self.is_admin():
                    return
                await self._send(view,selected)
            else:
                await self._pdf(view,selected)
            return

    async def _pdf(self,view,payment_id):
        try:
            path=await view.busy('Membuat PDF...',self.make_pdf,payment_id)
            if not path:
                raise ValueError('Lokasi PDF belum tersedia.')
        except ImportError:
            await view.result('PDF BELUM TERSEDIA','Pasang dependensi: python -m pip install -r requirements.txt','error')
            return
        except (ValueError,PermissionError,LookupError) as exc:
            await view.result('PDF GAGAL DIBUAT',str(exc),'error')
            return
        except Exception:
            await view.result('PDF GAGAL DIBUAT','Periksa folder penyimpanan dan coba lagi.','error')
            return
        await view.page('BUKTI PDF BERHASIL DIBUAT',[('back','Lanjutkan')],
            lambda w,b:details_pages([('LOKASI FILE',[('Path',str(path))])],w,b,full=True))

    async def _send(self,view,payment_id):
        try:
            result=await view.busy('Mengirim bukti...',self.send_email,payment_id)
            sent=result['sent']
            if type(sent) is not bool:
                raise ValueError('Status pengiriman belum diketahui.')
        except ImportError:
            await view.result('PDF BELUM TERSEDIA','Pasang dependensi: python -m pip install -r requirements.txt','error')
            return
        except Exception:
            await view.result('HASIL EMAIL BELUM DIPASTIKAN',
                              'Periksa hasil pengiriman sebelum mencoba kembali.','warning')
            return
        # Retain actual delivery result, including a local PDF when SMTP fails.
        sections=[('HASIL PENGIRIMAN',[
            ('Email',value(result,'email')),
            ('Status','Terkirim' if sent else 'Belum terkirim'),
            ('Pesan',value(result,'message')),
            ('File PDF',value(result,'path')),
        ])]
        await view.page('EMAIL TERKIRIM' if sent else 'EMAIL BELUM TERKIRIM',[('back','Lanjutkan')],
            lambda w,b:details_pages(sections,w,b,full=True,
                notice='' if sent else 'PDF tetap tersimpan jika lokasi file tersedia.'))


def build_billing_controller():
    """Construct the controller without opening another terminal application."""
    from app import session
    from app.repositories import admin_dashboard_repo
    from app.services import billing_service
    return BillingController(
        summary=admin_dashboard_repo.ringkasan_admin,
        invoices=billing_service.daftar_tagihan_admin,
        history=billing_service.riwayat_pembayaran_admin,
        receipt=billing_service.bukti_pembayaran_admin,
        make_monthly=billing_service.buat_tagihan_bulanan,
        make_pdf=billing_service.buat_bukti_pembayaran_pdf,
        send_email=billing_service.kirim_bukti_pembayaran_email,
        is_admin=lambda:session.punya_role('admin'))


def menu_pembayaran_admin():
    from app import session
    if not session.punya_role('admin'):
        return
    user=session.get_user() or {}
    ConfirmationWorkspace(user.get('nama_lengkap') or user.get('username') or 'Admin').run(
        build_billing_controller().run)
