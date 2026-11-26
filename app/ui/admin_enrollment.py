"""UI-003B: single-screen enrollment administration, existing services only."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .admin_confirmation import ConfirmationWorkspace, Field, value, rupiah, details_pages
from .admin_workspace import (
    Snapshot, line, pad, clip, width_of, paginate_blocks, _metric_bands, _stat_rows,
    _compact_section,
)

# Match enrollment_repo.STATUS_ENROLLMENT_VALID (not just the old filter menu).
STATUS_LABELS = {
    'aktif':'Aktif',
    'menunggu_pembayaran':'Menunggu bayar',
    'menunggu':'Menunggu keputusan',
    'selesai':'Selesai',
    'ditolak':'Ditolak',
    'batal':'Dibatalkan',
}
STATUS_TONE = {
    'aktif':'success','menunggu_pembayaran':'warning','menunggu':'warning',
    'selesai':'muted','ditolak':'error','batal':'error',
}
CARDS = (
    ('PENDAFTARAN BERJALAN',(
        ('enrollment_aktif','Aktif',None),
        ('enrollment_menunggu_bayar','Menunggu pembayaran',None),
        ('enrollment_menunggu','Menunggu keputusan',None),
    )),
    ('RIWAYAT PENDAFTARAN',(
        ('enrollment_selesai','Selesai',None),
        ('enrollment_ditolak','Ditolak',None),
        ('enrollment_batal','Dibatalkan',None),
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
    complete=summary is not None and all(
        summary.get(key) is not None for _,items in CARDS for key,_,_ in items)
    blocks.append([line('Data terakhir dimuat ●' if complete else 'Data belum lengkap · Muat ulang',
                        width,'muted' if complete else 'warning','center')])
    return paginate_blocks(blocks,budget)


def status_label(item):
    raw=item.get('status')
    return STATUS_LABELS.get(raw,value(item,'status'))


def date_label(item):
    date=item.get('created_at')
    return date.strftime('%d/%m/%Y') if hasattr(date,'strftime') else value(item,'created_at')[:10]


def _styled_table(width,columns,values,selected=False,header=False,status=None):
    tone='class:selected' if selected else 'class:muted' if header else 'class:title'
    row=[(tone,'❯ ' if selected else '  ')]
    for i,((label,cw),v) in enumerate(zip(columns,values)):
        if i:
            row.append((tone,' '))
        style=('class:'+STATUS_TONE.get(status,'muted')
               if not header and not selected and label=='Status' else tone)
        row.append((style,pad(v,cw,'right' if label in ('Tagihan','Biaya/bulan','Sisa kuota') else 'left')))
    if width_of(row)>width:
        return [(tone,pad(''.join(t for _,t in row),width))]
    return row


def enrollment_row(width,item=None,selected=False):
    """Wide rows show ID/NIS/name/program/status/invoice count/date; narrow condense."""
    if width>=92:
        rem=width-60
        columns=[('ID',6),('NIS',10),('Siswa',rem//2),('Program',rem-rem//2),
                 ('Status',19),('Tagihan',7),('Tanggal',10)]
        fields=(value(item,'enrollment_id'),value(item,'nis'),value(item,'nama_siswa'),
                value(item,'nama_program'),status_label(item),value(item,'jumlah_tagihan'),date_label(item)) if item else ()
    elif width>=60:
        rem=width-30
        columns=[('ID',6),('Siswa',rem//2),('Program',rem-rem//2),('Status',19)]
        fields=(value(item,'enrollment_id'),value(item,'nama_siswa'),value(item,'nama_program'),status_label(item)) if item else ()
    else:
        rem=max(2,width-24)
        columns=[('ID',5),('Siswa',rem),('Status',15)]
        fields=(value(item,'enrollment_id'),value(item,'nama_siswa'),status_label(item)) if item else ()
    return _styled_table(width,columns,fields or [label for label,_ in columns],selected,item is None,
                         item.get('status') if item else None)


def program_row(width,item=None,selected=False):
    if width>=66:
        columns=[('Kode',10),('Program',width-52),('Jenjang',10),('Biaya/bulan',17),('Sisa kuota',9)]
        fields=(value(item,'kode'),value(item,'nama'),value(item,'jenjang'),rupiah(item.get('harga_bulanan')),
                value(item,'sisa')) if item else ()
    else:
        columns=[('Kode',8),('Program',max(1,width-23)),('Sisa kuota',11)]
        fields=(value(item,'kode'),value(item,'nama'),value(item,'sisa')) if item else ()
    return _styled_table(width,columns,fields or [label for label,_ in columns],selected,item is None)


def filter_program_row(width,item=None,selected=False):
    columns=[('Kode',min(10,max(4,width//4))),('Program',max(1,width-min(10,max(4,width//4))-4))]
    fields=(value(item,'kode'),value(item,'nama')) if item else ()
    return _styled_table(width,columns,fields or [label for label,_ in columns],selected,item is None)


def detail_sections(item):
    return [
        ('IDENTITAS SISWA',[
            ('Nama',value(item,'nama_siswa')),('NIS',value(item,'nis')),
            ('Username',value(item,'username')),('Email',value(item,'email')),
            ('Status akun',value(item,'status_akun')),
        ]),
        ('PROGRAM BIMBEL',[
            ('Program',value(item,'nama_program')),('Kode',value(item,'kode_program')),
            ('Jenjang',value(item,'jenjang')),('Biaya / bulan',rupiah(item.get('harga_bulanan'))),
            ('Status',status_label(item)),
        ]),
        ('KEUANGAN',[
            ('Jumlah tagihan',value(item,'jumlah_tagihan')),
            ('Total tagihan',rupiah(item.get('total_tagihan'))),
            ('Pembayaran lunas',rupiah(item.get('total_terbayar'))),
        ]),
        ('RIWAYAT PENDAFTARAN',[
            ('ID pendaftaran',value(item,'enrollment_id')),
            ('Tanggal daftar',value(item,'created_at')),
            ('Diproses pada',value(item,'processed_at')),
            ('Diproses oleh',value(item,'diproses_oleh')),
            ('Alasan',value(item,'alasan_tolak')),
        ]),
    ]


def eligible_destinations(origin,programs,history):
    """Same selection criteria as legacy UI; repository rechecks in transaction."""
    seen={p['program_id'] for p in history}
    return [p for p in programs
            if p['id']!=origin['program_id'] and p.get('status')=='buka'
            and p.get('sisa',0)>0 and p['id'] not in seen]


def move_sections(origin,target,source_program):
    """Do not predict current-month paid status from lifetime payment totals."""
    return [
        ('PROGRAM ASAL',[
            ('Siswa',value(origin,'nama_siswa')),('Program',value(origin,'nama_program')),
            ('Biaya / bulan',rupiah(origin.get('harga_bulanan'))),
            ('Kuota tersisa',value(source_program,'sisa')),
            ('Status saat ini',status_label(origin)),
        ]),
        ('PROGRAM TUJUAN',[
            ('Kode',value(target,'kode')),('Program',value(target,'nama')),
            ('Biaya / bulan',rupiah(target.get('harga_bulanan'))),
            ('Kuota tersisa',value(target,'sisa')),('Jenjang',value(target,'jenjang')),
        ]),
        ('DAMPAK PEMINDAHAN',[
            ('Kelas asal','Selesai; riwayat tagihan tetap tersimpan.'),
            ('Bulan ini lunas','Tujuan langsung aktif; tanpa tagihan kedua.'),
            ('Tujuan gratis','Langsung aktif.'),
            ('Tujuan berbayar','Jika bulan ini belum lunas: tagihan baru, bayar lalu ACC Admin.'),
            ('Refund / prorata','Tidak ada refund atau prorata otomatis.'),
        ]),
    ]


def cancel_sections(item,reason):
    active=item.get('status')=='aktif'
    return [
        ('PENDAFTARAN YANG DIBATALKAN',[
            ('Nama siswa',value(item,'nama_siswa')),('Program',value(item,'nama_program')),
            ('Status saat ini',status_label(item)),('Alasan',reason or 'Tidak diisi'),
        ]),
        ('DAMPAK PEMBATALAN',[
            ('Status akhir','Dibatalkan'),
            ('Akses kelas','Berakhir' if active else 'Tidak diaktifkan'),
            ('Tagihan','Tagihan ditutup; riwayat tetap tersimpan.'),
            ('Estimasi refund',rupiah(item.get('total_terbayar')) if active else 'Rp0'),
            ('Refund','Semua pembayaran lunas, termasuk bulan sebelumnya.' if active else 'Tidak ada pembayaran lunas.'),
            ('Jenis transaksi','Simulasi internal; bukan uang sungguhan.'),
        ]),
    ]


class EnrollmentController:
    """Only orchestration. The authorized existing service owns mutations."""
    def __init__(self,*,summary,list_enrollments,detail,programs,programs_quota,
                 history,move,cancel,is_admin):
        self.summary=summary
        self.list_enrollments=list_enrollments
        self.load_detail=detail
        self.programs=programs
        self.programs_quota=programs_quota
        self.history=history
        self.move=move
        self.cancel=cancel
        self.is_admin=is_admin

    async def _read(self,view,title,fn,*args,service=False):
        try:
            data=await view.busy(title,fn,*args)
            if service:
                ok,data=data
                if not ok:
                    await view.result('DATA BELUM TERSEDIA',str(data),'error')
                    return None
            if data is None:
                raise ValueError('Data tidak tersedia')
            return data
        except Exception:
            await view.result('DATA GAGAL DIMUAT','Periksa koneksi, lalu coba lagi.','error')
            return None

    async def run(self,view):
        previous=None
        focus='list'
        while self.is_admin():
            try:
                summary=await view.busy('Memuat ringkasan...',self.summary)
            except Exception:
                summary=None
            keys={k for _,items in CARDS for k,_,_ in items}
            changed={k for k in keys if previous is not None and summary is not None
                     and previous.get(k) is not None and summary.get(k) is not None
                     and previous[k]!=summary[k]}
            if summary is not None:
                previous=summary
            action=await view.page('MANAJEMEN PENDAFTARAN',[
                ('list','Daftar Pendaftaran'),('move','Pindahkan Siswa'),('cancel','Batalkan Pendaftaran'),
                ('refresh','Muat ulang'),('back','Kembali ke Prioritas')],
                lambda w,b:dashboard_pages(summary,w,b,changed),default=focus)
            if action in (None,'back'):
                return
            if action=='list':
                await self.browse(view)
            elif action=='move':
                await self.move_flow(view)
            elif action=='cancel':
                await self.cancel_flow(view)
            focus=action

    async def _choose_filters(self,view,status,program_id):
        options=[('all','Semua status')]+[(key,label) for key,label in STATUS_LABELS.items()]+[('back','Kembali')]
        selected=await view.page('FILTER STATUS PENDAFTARAN',options,
            lambda w,b:[[line('Pilih status pendaftaran',w,'muted','center')]],default=status or 'all')
        if selected in (None,'back'):
            return None
        selected=None if selected=='all' else selected
        while self.is_admin():
            programs=await self._read(view,'Memuat program...',self.programs)
            if programs is None:
                return None
            rows=[{'id':0,'kode':'SEMUA','nama':'Semua program'}]+list(programs)
            choice=await view.record_table('FILTER PROGRAM',rows,key='id',renderer=filter_program_row,
                                          caption='Pilih program',initial=program_id or 0)
            if choice=='refresh':
                continue
            if type(choice) is not int:
                return None
            chosen=next((p for p in rows if p['id']==choice),None)
            return (selected,choice or None,value(chosen,'nama')) if chosen else None
        return None

    async def browse(self,view):
        status=None
        program_id=None
        program_name='Semua program'
        selected_id=None
        while self.is_admin():
            filters=await self._choose_filters(view,status,program_id)
            if filters is None:
                return
            status,program_id,program_name=filters
            while self.is_admin():
                records=await self._read(view,'Memuat pendaftaran...',self.list_enrollments,
                                         status,program_id,service=True)
                if records is None:
                    break
                selected=await view.record_table('DAFTAR PENDAFTARAN',records,key='enrollment_id',
                    renderer=enrollment_row,caption=f'{STATUS_LABELS.get(status,"Semua status")} · {program_name}',
                    empty='Tidak ada pendaftaran sesuai filter.',filter_action=True,initial=selected_id)
                if selected=='filter':
                    selected_id=None
                    break
                if selected=='refresh':
                    continue
                if selected in ('back',None):
                    return
                selected_id=selected
                detail=await self._read(view,'Memuat detail...',self.load_detail,selected,service=True)
                if detail is not None:
                    await view.page('DETAIL PENDAFTARAN',[('back','Kembali ke daftar')],
                        lambda w,b:details_pages(detail_sections(detail),w,b,full=True,paired=True))

    async def _choose_enrollment(self,view,statuses,title):
        while self.is_admin():
            rows=[]
            for status in statuses:
                data=await self._read(view,'Memuat pendaftaran...',self.list_enrollments,status,None,service=True)
                if data is None:
                    return None
                rows.extend(data)
            rows.sort(key=lambda x:(str(x.get('created_at') or ''),x['enrollment_id']),reverse=True)
            selected=await view.record_table(title,rows,key='enrollment_id',renderer=enrollment_row,
                caption=' · '.join(STATUS_LABELS[s] for s in statuses),
                empty='Tidak ada pendaftaran yang memenuhi syarat.')
            if selected=='refresh':
                continue
            if type(selected) is not int or not any(row['enrollment_id']==selected for row in rows):
                return None
            detail=await self._read(view,'Memuat detail...',self.load_detail,selected,service=True)
            if detail is None:
                return None
            if detail.get('status') not in statuses:
                await view.result('DATA BERUBAH','Status pendaftaran telah berubah. Muat ulang daftar.','warning')
                continue
            return detail
        return None

    async def _write(self,view,title,fn,*args):
        if not self.is_admin():
            return
        try:
            ok,message=await view.busy(title,fn,*args)
        except Exception:
            # An exception after commit cannot establish failure. No automatic retry.
            await view.result('HASIL BELUM DAPAT DIPASTIKAN',
                              'Periksa status terbaru sebelum mengulangi tindakan.','error')
            return
        await view.result('KEPUTUSAN TERSIMPAN' if ok else 'KEPUTUSAN GAGAL',str(message),
                          'success' if ok else 'error')

    async def move_flow(self,view):
        origin=await self._choose_enrollment(view,('aktif',),'PILIH PENDAFTARAN ASAL')
        if origin is None:
            return
        while self.is_admin():
            history=await self._read(view,'Memuat riwayat...',self.history,origin['student_id'])
            if history is None:
                return
            programs=await self._read(view,'Memuat kuota...',self.programs_quota)
            if programs is None:
                return
            targets=eligible_destinations(origin,programs,history)
            selected=await view.record_table('PILIH PROGRAM TUJUAN',targets,key='id',renderer=program_row,
                caption='Program buka · Kuota tersedia · Belum pernah diikuti',
                empty='Tidak ada program tujuan yang memenuhi syarat.')
            if selected=='refresh':
                continue
            target=next((p for p in targets if p['id']==selected),None)
            if target is None:
                return
            source=next((p for p in programs if p['id']==origin['program_id']),{})
            sections=move_sections(origin,target,source)
            # Separate explicit review from the selected table row.
            choice=await view.page('KONFIRMASI PEMINDAHAN',[
                ('confirm','Ya, pindahkan siswa'),('back','Batal')],
                lambda w,b:details_pages(sections,w,b,full=True,paired=True),default='back')
            if choice!='confirm':
                continue
            await self._write(view,'Memindahkan siswa...',self.move,origin['enrollment_id'],target['id'])
            return

    async def cancel_flow(self,view):
        item=await self._choose_enrollment(view,('menunggu','aktif'),'PILIH PENDAFTARAN UNTUK DIBATALKAN')
        if item is None:
            return
        try:
            paid=Decimal(str(item['total_terbayar']))
            if not paid.is_finite() or paid<0:
                raise ValueError('Nominal tidak valid')
        except (KeyError,InvalidOperation,ValueError,TypeError):
            await view.result('DATA BELUM LENGKAP','Jumlah pembayaran belum tersedia. Muat ulang.','error')
            return
        if item['status']=='menunggu' and paid>0:
            await view.result('GUNAKAN PUSAT KONFIRMASI',
                'Pendaftaran sudah dibayar. Pilih Tolak Pendaftaran di Pusat Konfirmasi untuk refund.','warning')
            return
        note=''
        reason=''
        while self.is_admin():
            answer=await view.form('ALASAN PEMBATALAN',[Field('reason','Alasan (opsional)',default=reason)],
                subtitle=value(item,'nama_siswa'),notice=note,hint='Maksimal 1000 karakter.',submit_label='Lanjutkan')
            if answer is None:
                return
            reason=answer.get('reason','').strip()
            if len(reason)<=1000:
                break
            note='Alasan maksimal 1000 karakter.'
        else:
            return
        sections=cancel_sections(item,reason)
        choice=await view.page('KONFIRMASI PEMBATALAN',[
            ('confirm','Ya, batalkan pendaftaran'),('back','Batal')],
            lambda w,b:details_pages(sections,w,b,full=True),default='back')
        if choice=='confirm':
            await self._write(view,'Memproses pembatalan...',self.cancel,item['enrollment_id'],reason)


def menu_pendaftaran_admin():
    from app import session
    if not session.punya_role('admin'):
        return
    from app.repositories import admin_dashboard_repo,enrollment_repo,program_repo
    from app.services import admin_enrollment_service
    user=session.get_user() or {}
    controller=EnrollmentController(
        summary=admin_dashboard_repo.ringkasan_admin,
        list_enrollments=admin_enrollment_service.daftar_pendaftaran,
        detail=admin_enrollment_service.detail_pendaftaran,
        programs=program_repo.daftar_program,programs_quota=program_repo.daftar_program_dengan_kuota,
        history=enrollment_repo.enrollment_siswa,
        move=admin_enrollment_service.pindahkan_pendaftaran,
        cancel=admin_enrollment_service.batalkan_pendaftaran,
        is_admin=lambda:session.punya_role('admin'))
    ConfirmationWorkspace(user.get('nama_lengkap') or user.get('username') or 'Admin').run(controller.run)
