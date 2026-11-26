"""UI-006: reporting, announcements and audit log UI. The AI screen is untouched."""
from __future__ import annotations

from collections import Counter
from datetime import date,datetime
from decimal import Decimal

from .admin_confirmation import ConfirmationWorkspace, Field, details_pages, field_rows, value, rupiah, wrap
from .admin_workspace import line, pad, clip, clean, width_of, paginate_blocks, dashboard_card, _compact_section
from .admin_academic import add_band, add_panel, bar_row, stat_tile
from .admin_navigation import KELOMPOK_MENU

ROUTES=tuple((code,label) for label,code in KELOMPOK_MENU[3][1])
REPORT_MENU=[
    ('pemasukan','Pemasukan per Bulan'),('siswa_program','Siswa per Program'),
    ('kehadiran','Rekap Kehadiran'),('nilai','Rata-rata Nilai per Program'),
    ('csv','Ekspor Laporan CSV'),('xlsx','Ekspor Laporan Excel'),
]
ANNOUNCE_MENU=[('buat','Buat Pengumuman'),('aktif','Pengumuman Aktif'),('arsip','Arsip Pengumuman')]
LOG_MENU=[('terbaru','Aktivitas Terbaru'),('filter','Filter Pengguna / Aksi')]
TARGETS={'siswa':['siswa'],'tutor':['tutor'],'both':['siswa','tutor']}
REPORT_NOTES={
    'pemasukan':'Simulasi lunas dan belum direfund · Maks. 24 bulan dalam hasil service.',
    'siswa_program':'Per program · Menunggu mencakup pembayaran dan persetujuan.',
    'kehadiran':'Per pendaftaran · Sesi belum selesai tidak dihitung · Maks. 5.000 baris.',
    'nilai':'Rata-rata nilai akhir berbobot · Pendaftaran batal/ditolak dikecualikan.',
    'absensi_arsip':'Catatan lama belum terhubung · Maks. 5.000 baris.',
}
# (field, short label, width, min terminal width); flexible name columns take remainder.
REPORT_COLUMNS={
    'pemasukan': [('bulan','Bulan',12,0),('jumlah_transaksi','Transaksi lunas',17,0),('total_pemasukan','Pemasukan (Rp)',0,0)],
    'siswa_program':[('kode_program','Kode',10,70),('nama_program','Program',0,0),('jenjang','Jenjang',10,85),
        ('status_program','Status',8,90),('kuota','Kuota',6,70),('siswa_aktif','Aktif',6,0),
        ('menunggu','Menunggu',8,0),('kuota_tersisa','Sisa',6,60)],
    'kehadiran':[('nama_siswa','Siswa',0,0),('nama_program','Program',0,58),('nis','NIS',12,94),
        ('total_pertemuan','Sesi',5,74),('hadir','H',4,0),('izin','I',4,66),('sakit','S',4,66),
        ('alpa','A',4,66),('persen_hadir','Hadir %',9,0)],
    'nilai':[('kode_program','Kode',10,68),('nama_program','Program',0,0),
        ('jenjang','Jenjang',10,75),('siswa_dinilai','Dinilai',10,0),('rata_nilai_akhir','Rata-rata',13,0)],
}


def report_value(raw,key):
    if raw is None:
        return '—'
    if key=='total_pemasukan':
        return rupiah(raw)
    if key=='persen_hadir':
        try:
            return f'{float(raw):.1f}%'
        except (TypeError,ValueError):
            return clean(raw)
    if isinstance(raw,datetime):
        return raw.strftime('%d-%m-%Y %H:%M')
    if isinstance(raw,date):
        return raw.strftime('%m-%Y' if key=='bulan' else '%d-%m-%Y')
    if isinstance(raw,Decimal):
        return f'{raw:.2f}'
    return clean(raw)


def table_row(width,columns,row=None,selected=False):
    # Hide columns according to terminal width. Complete values remain in detail.
    if not columns:
        return [line('—',width)[0]]
    fixed=sum(cw for _,_,cw in columns)
    flexible=sum(cw==0 for _,_,cw in columns)
    free=max(flexible,width-2-(len(columns)-1)-fixed)
    base='class:selected' if selected else 'class:muted' if row is None else 'class:title'
    result=[(base,'❯ ' if selected else '  ')]
    n=0
    for i,(key,label,cw) in enumerate(columns):
        if cw==0:
            cw=free//flexible+int(n<free%flexible)
            n+=1
        if i:
            result.append((base,' '))
        v=label if row is None else report_value(row.get(key),key)
        result.append((base,pad(v,cw)))
    return result if width_of(result)<=width else [(base,pad(''.join(t for _,t in result),width))]


def report_row(report,width,row=None,selected=False):
    cols=REPORT_COLUMNS.get(report.get('kode'))
    accepted={k for k,_ in report['kolom']}
    if cols:
        fields=[(k,label,cw) for k,label,cw,min_width in cols if width>=min_width and k in accepted]
        if width<46 and report.get('kode')=='pemasukan':
            fields=[(k,l,8 if k=='bulan' else cw) for k,l,cw in fields if k!='jumlah_transaksi']
        if width<46 and report.get('kode')=='nilai':
            fields=[(k,l,7 if k=='siswa_dinilai' else 10 if k=='rata_nilai_akhir' else cw) for k,l,cw in fields]
    else:
        fields=[(k,l,0) for k,l in report['kolom'][:max(1,width//22)]]
    return table_row(width,fields,row,selected)


def target_text(item):
    return ', '.join(str(r).capitalize() for r in item.get('target_roles',[]) or []) or '—'


def announcement_row(width,row=None,selected=False):
    cols=[('id','ID',6),('judul','Judul',0),('target_label','Penerima',14),('created_at','Dibuat',17)]
    if width<65:
        cols=cols[:3]
    if width<39:
        cols=cols[:2]
    if row is not None:
        row={**row,'target_label':target_text(row)}
    return table_row(width,cols,row,selected)


def log_row(width,row=None,selected=False):
    cols=[('id','ID',7),('created_at','Waktu',17),('pengguna','Pengguna',0),
          ('aksi','Aksi',21),('detail','Detail',0)]
    if width<84:
        cols=cols[:-1]
    if width<61:
        cols=[('id','ID',5),('pengguna','Pengguna',0),('aksi','Aksi',16)]
    if width<36:
        cols=cols[1:]
    return table_row(width,cols,row,selected)


def capped_count(rows,limit):
    return '—' if rows is None else str(len(rows))+('+' if len(rows)>=limit else '')


def recent_rows(rows,width,*,kind,limit=3):
    if rows is None:
        return [line('Data gagal dimuat',width,'warning','center')]
    if not rows:
        return [line('Belum ada data',width,'muted','center')]
    result=[]
    for row in rows[:limit]:
        ts=row.get('created_at')
        stamp=ts.strftime('%d/%m %H:%M') if hasattr(ts,'strftime') else '—'
        label=row.get('judul') if kind=='announcement' else row.get('aksi')
        if width>=36:
            result.append([*line(stamp,12,'muted'),('', ' '),*line(label or '—',width-13,'title')])
        else:
            result.append(line(label or '—',width,'title'))
    return result


def dashboard_pages(data,kind,width,budget,changed=frozenset()):
    budget=max(1,budget)
    blocks=[]
    types,active,archive,logs=(data.get(k) for k in ('types','active','archive','logs'))
    if kind=='root':
        tiles=[('LAPORAN',lambda w:stat_tile('—' if types is None else str(len(types)),'Termasuk jenis ekspor',w,'types' in changed)),
               ('PENGUMUMAN',lambda w:stat_tile(capped_count(active,500),'Aktif · maks. 500',w,'active' in changed)),
               ('LOG AKTIVITAS',lambda w:stat_tile(capped_count(logs,200),'Terbaru · maks. 200',w,'logs' in changed))]
        add_band(blocks,tiles,width,budget)
        add_band(blocks,[('AKTIVITAS TERBARU',lambda w:recent_rows(logs,w,kind='log')),
                         ('PENGUMUMAN AKTIF',lambda w:recent_rows(active,w,kind='announcement'))],
                 width,budget,[3,2])
        blocks.append([line('SIBIMA-AI · Halaman chat tetap menggunakan UI lama.',width,'muted','center')])
        needed=('types','active','logs')
    elif kind=='laporan':
        def listing(w):
            if types is None:
                return [line('Daftar jenis belum tersedia.',w,'warning')]
            available={x['kode'] for x in types}
            rows=[line(label,w,'title') for k,label in REPORT_MENU[:4] if k in available]
            return rows or [line('Tidak ada jenis laporan interaktif.',w)]
        add_band(blocks,[
            ('LAPORAN INTERAKTIF',listing),
            ('FORMAT EKSPOR',lambda w:[line('CSV · UTF-8 BOM · ;',w,'title'),line('Excel · .xlsx berformat',w,'title'),
                                      line('Data sesuai laporan',w,'muted')])],width,budget,[3,2])
        blocks.append([line('Jumlah baris dan nilai diperoleh saat membuka laporan.',width,'muted','center')])
        needed=('types',)
    elif kind=='pengumuman':
        add_band(blocks,[
            ('AKTIF',lambda w:stat_tile(capped_count(active,500),'Batas daftar 500',w,'active' in changed)),
            ('ARSIP PERMANEN',lambda w:stat_tile(capped_count(archive,500),'Batas daftar 500',w,'archive' in changed)),
            ('PENERIMA',lambda w:[line('Siswa / Tutor',w,'title','center'),line('Notifikasi aplikasi',w,'muted','center')])],width,budget)
        add_panel(blocks,'PENGUMUMAN TERBARU',lambda w:recent_rows(active,w,kind='announcement',limit=4),width,budget)
        needed=('active','archive')
    else:
        def action_rows(w):
            if logs is None:
                return [line('Data belum tersedia.',w,'warning')]
            counts=Counter(str(r.get('aksi') or '—') for r in logs)
            if not counts:
                return [line('Belum ada aktivitas.',w)]
            # Counts relative to the loaded sample, not all-time audit totals.
            return [bar_row(k,n,len(logs),w,tone='number') for k,n in counts.most_common(4)]
        add_band(blocks,[
            ('AKTIVITAS TERBARU',lambda w:recent_rows(logs,w,kind='log',limit=4)),
            ('AKSI TERBANYAK · SAMPEL',action_rows)],width,budget,[3,2])
        blocks.append([line('Sampel '+capped_count(logs,200)+' log terbaru · Batas 200 · Hanya baca',width,'muted','center')])
        needed=('logs',)
    complete=all(data.get(k) is not None for k in needed)
    blocks.append([line('Data terakhir dimuat ●' if complete else 'Data belum lengkap · Muat ulang',
                        width,'muted' if complete else 'warning','center')])
    return paginate_blocks(blocks,budget)


def document_pages(title,body,metadata,width,budget,notice=''):
    """A full-width reading pane. Preserve paragraph breaks; long messages page."""
    budget=max(1,budget)
    blocks=[]
    def meta(w):
        return [*[line(t,w,'title','center') for t in wrap(title,w)],*field_rows(metadata,w,full=True)]
    add_panel(blocks,'RINGKASAN',meta,width,budget)
    # Render a proper reading card: text inset, heading inside the border,
    # paragraph breaks preserved. Split long bodies into complete pages.
    inset=2 if width>=16 else 0
    text_width=max(1,width-2-inset*2)
    bodyrows=[]
    for paragraph in str(body or '').split('\n'):
        if not paragraph.strip():
            bodyrows.append([])
        else:
            bodyrows.extend([('', ' '*inset),*line(part,text_width,'title'),('', ' '*inset)]
                            for part in wrap(paragraph,text_width))
    if not any(bodyrows):
        bodyrows=[line('—',max(1,width-2),'muted','center')]
    if budget>=4:
        step=budget-3
        for start in range(0,len(bodyrows),step):
            blocks.append(dashboard_card('ISI / DETAIL',bodyrows[start:start+step],width))
    else:
        blocks.extend(_compact_section('ISI / DETAIL',bodyrows,width,budget))
    if notice:
        blocks.extend([[line(t,width,'warning','center')] for t in wrap(notice,width)[:2]])
    pages=paginate_blocks(blocks,budget)
    # Navigation must not touch the reading card or warning.
    for page in pages:
        if len(page)<budget:
            page.append([])
    return pages


def announcement_pages(item,width,budget,notice=''):
    return document_pages(value(item,'judul','Tanpa judul'),item.get('isi'),
        [('ID',value(item,'id')),('Penerima',target_text(item)),('Dibuat oleh',value(item,'nama_pembuat')),
         ('Dibuat',value(item,'created_at')),('Status','Arsip permanen' if item.get('archived_at') else 'Aktif'),
         ('Diarsipkan',value(item,'archived_at'))],width,budget,notice)


def log_pages(row,width,budget):
    return document_pages(value(row,'aksi'),row.get('detail'),[
        ('ID log',value(row,'id')),('Waktu',value(row,'created_at')),
        ('Pengguna',value(row,'pengguna','Sistem')),('Username',value(row,'username')),
        ('User ID',value(row,'user_id'))],width,budget)


def report_detail_pages(report,row,width,budget):
    pairs=[(label,report_value(row.get(k),k)) for k,label in report['kolom']]
    if report['kode']=='kehadiran':
        groups=[('IDENTITAS & PENDAFTARAN',pairs[:7]),('REKAP PER SESI',pairs[7:])]
    elif report['kode']=='siswa_program':
        groups=[('PROGRAM',pairs[:4]),('KETERISIAN',pairs[4:])]
    else:
        groups=[('DATA LAPORAN',pairs)]
    return details_pages(groups,width,budget,notice=REPORT_NOTES.get(report['kode'],''),full=True,paired=True)


class ReportingController:
    def __init__(self,*,types,report,export_csv,export_excel,announcements,announcement_detail,publish,archive,logs,filter_logs,is_admin):
        self.types=types;self.report=report;self.export_csv=export_csv;self.export_excel=export_excel
        self.announcements=announcements;self.announcement_detail=announcement_detail
        self.publish=publish;self.archive=archive;self.logs=logs;self.filter_logs=filter_logs
        self.is_admin=is_admin;self.focus={};self.previous={}

    def _overview(self,kind):
        calls={}
        if kind in ('root','laporan'):calls['types']=self.types
        if kind in ('root','pengumuman'):calls['active']=lambda:self.announcements(status='aktif',limit=500)
        if kind=='pengumuman':calls['archive']=lambda:self.announcements(status='arsip',limit=500)
        if kind in ('root','log'):calls['logs']=lambda:self.logs(limit=200)
        data={}
        for key,fn in calls.items():
            try:
                result=fn()
                data[key]=result if isinstance(result,list) else None
            except Exception:
                data[key]=None
        return data

    async def _error(self,view,exc,operation):
        if type(exc).__name__=='InsufficientPrivilege':
            await view.result('HAK AKSES BELUM TERSEDIA','Periksa izin SELECT objek laporan pada database sibima_db.','error')
        elif isinstance(exc,(PermissionError,ValueError,RuntimeError)):
            await view.result(operation,str(exc),'error')
        else:
            await view.result(operation,'Periksa koneksi atau lokasi file, lalu coba lagi.','error')

    async def _read(self,view,title,fn,*args,**kw):
        if not self.is_admin():
            return None
        try:
            result=await view.busy(title,lambda:fn(*args,**kw))
            if result is None:
                await view.result('DATA TIDAK TERSEDIA','Data tidak ditemukan. Muat ulang.','warning')
            return result
        except Exception as exc:
            await self._error(view,exc,'DATA GAGAL DIMUAT')
            return None

    async def _dashboard(self,view,kind,menu,title):
        try:
            data=await view.busy('Memuat ringkasan...',self._overview,kind)
        except Exception:
            data={}
        if not self.is_admin():
            return None
        counts={k:len(v) for k,v in data.items() if isinstance(v,list)}
        old=self.previous.get(kind,{})
        changed={k for k,n in counts.items() if k in old and old[k]!=n}
        self.previous[kind]={**old,**counts}
        focus=self.focus.get(kind,menu[0][0])
        action=await view.page(title,[*menu,('refresh','Muat ulang'),
               ('back','Kembali ke dashboard' if kind=='root' else 'Kembali ke Laporan & Komunikasi')],
               lambda w,b:dashboard_pages(data,kind,w,b,changed),default=focus)
        if action=='refresh':
            self.focus[kind]=getattr(view,'refresh_focus',None) or focus
        elif action not in (None,'back'):
            self.focus[kind]=action
        return action

    async def run(self,view,initial=None):
        if initial in ('laporan','pengumuman','log'):
            return await self.module(view,initial)
        while self.is_admin():
            action=await self._dashboard(view,'root',ROUTES,'LAPORAN & KOMUNIKASI')
            if action in (None,'back') or not self.is_admin():
                return
            if action=='ai':
                # Exit full-screen first; caller opens the original AI feature.
                return 'ai'
            if action in ('laporan','pengumuman','log'):
                await self.module(view,action)

    async def module(self,view,kind):
        menu,title={'laporan':(REPORT_MENU,'PUSAT LAPORAN'),
                    'pengumuman':(ANNOUNCE_MENU,'PUSAT KOMUNIKASI'),
                    'log':(LOG_MENU,'LOG AKTIVITAS')}[kind]
        while self.is_admin():
            action=await self._dashboard(view,kind,menu,title)
            if action in (None,'back') or not self.is_admin():
                return
            if action=='refresh':
                continue
            if kind=='laporan':
                if action in ('csv','xlsx'):
                    await self.export(view,action)
                elif action in {k for k,_ in REPORT_MENU[:4]}:
                    await self.browse_report(view,action)
            elif kind=='pengumuman':
                if action=='buat':
                    await self.create_announcement(view)
                elif action in ('aktif','arsip'):
                    await self.browse_announcements(view,action)
            elif action in ('terbaru','filter'):
                await self.browse_logs(view,filtered=action=='filter')

    async def _choose(self,view,title,choices,default=None,caption='Pilih salah satu'):
        return await view.page(title,[*choices,('back','Kembali')],
            lambda w,b:[[line(caption,w,'muted','center')]],default=default)

    async def _confirm(self,view,title,renderer,label):
        if not self.is_admin():
            return False
        answer=await view.page(title,[('confirm',label),('back','Batal')],renderer,default='back')
        return answer=='confirm' and self.is_admin()

    async def browse_report(self,view,code):
        initial=None
        while self.is_admin():
            report=await self._read(view,'Memuat laporan...',self.report,code)
            if report is None:
                return
            # The repository-defined data/columns are authoritative. No new query
            # or aggregation; every row has a positional UI key even if duplicate.
            rows=[{**row,'_ui_row':i} for i,row in enumerate(report['data'],1)]
            selected=await view.record_table(report['judul'].upper(),rows,key='_ui_row',
                renderer=lambda w,row=None,selected=False:report_row(report,w,row,selected),
                caption=REPORT_NOTES.get(code,'Laporan')+' · Enter detail',
                initial=initial,empty='Tidak ada data laporan.')
            if selected=='refresh':
                continue
            row=next((r for r in rows if r['_ui_row']==selected),None)
            if row is None:
                return
            initial=selected
            await view.page('DETAIL LAPORAN',[('back','Kembali ke daftar')],
                lambda w,b:report_detail_pages(report,row,w,b))

    async def export(self,view,fmt):
        types=await self._read(view,'Memuat jenis laporan...',self.types)
        if types is None:
            return
        code=await self._choose(view,'PILIH LAPORAN '+fmt.upper(),[(r['kode'],r['judul']) for r in types],
                                caption='Semua jenis dari service lama')
        item=next((r for r in types if r['kode']==code),None)
        if item is None:
            return
        info=[('Laporan',item['judul']),('Format','CSV (.csv)' if fmt=='csv' else 'Excel (.xlsx)'),
              ('Isi','Data terbaru saat diekspor'),('Lokasi','Folder laporan di proyek')]
        if fmt=='csv':info.append(('Pemisah','Titik koma · UTF-8 BOM'))
        else:info.append(('Format sel','Judul, filter, format angka'))
        if not await self._confirm(view,'KONFIRMASI EKSPOR '+fmt.upper(),
            lambda w,b:details_pages([('RINCIAN EKSPOR',info)],w,b,full=True), 'Ya, ekspor laporan'):
            return
        try:
            path=await view.busy('Mengekspor laporan...',self.export_csv if fmt=='csv' else self.export_excel,code)
            if not path:raise ValueError('Lokasi file hasil ekspor tidak tersedia.')
        except Exception as exc:
            await self._error(view,exc,'EKSPOR GAGAL')
            return
        await view.page('EKSPOR BERHASIL',[('back','Lanjutkan')],
            lambda w,b:details_pages([('FILE LAPORAN',[('Laporan',item['judul']),('Lokasi',str(path))])],w,b,full=True,
               notice='CSV berisi data mentah tanpa format sel.' if fmt=='csv' else 'Workbook Excel berformat.'))

    async def create_announcement(self,view):
        captured={'judul':'','isi':''}
        notice=''
        while self.is_admin():
            answer=await view.form('BUAT PENGUMUMAN',[
                Field('judul','Judul (maks. 150)',captured['judul']),Field('isi','Isi pengumuman',captured['isi'])],
                hint=r'Gunakan \n untuk baris baru.',notice=notice,submit_label='Lanjutkan')
            if answer is None:
                return
            captured={k:answer[k] for k in captured}
            title=captured['judul'].strip()
            body=captured['isi'].replace('\\n','\n').strip()
            if not title or len(title)>150 or not body or len(body)>10000:
                notice='Judul wajib (maks. 150); isi wajib (maks. 10.000).'
                continue
            break
        else:
            return
        selected=await self._choose(view,'PILIH PENERIMA',[('siswa','Siswa'),('tutor','Tutor'),('both','Siswa dan Tutor')],
                                    caption='Notifikasi aplikasi, bukan email')
        roles=TARGETS.get(selected)
        if roles is None:
            return
        metadata=[('Penerima',', '.join(r.capitalize() for r in roles)),('Kanal','Notifikasi dalam aplikasi')]
        if not await self._confirm(view,'KONFIRMASI TERBITKAN PENGUMUMAN',
            lambda w,b:document_pages(title,body,metadata,w,b,'Periksa isi sebelum menerbitkan.'),
            'Ya, terbitkan pengumuman'):
            return
        try:
            item=await view.busy('Menerbitkan pengumuman...',self.publish,title,body,list(roles))
            if not item or item.get('id') is None:
                raise LookupError('Hasil belum diketahui')
        except (ValueError,PermissionError) as exc:
            await view.result('PENGUMUMAN GAGAL',str(exc),'error')
            return
        except Exception:
            await view.result('HASIL BELUM DAPAT DIPASTIKAN','Periksa daftar aktif sebelum menerbitkan lagi.','warning')
            return
        await view.result('PENGUMUMAN TERBIT',f"Pengumuman ID {item['id']} berhasil diterbitkan.",'success')

    async def browse_announcements(self,view,status):
        initial=None
        while self.is_admin():
            rows=await self._read(view,'Memuat pengumuman...',self.announcements,status=status,limit=500)
            if rows is None:
                return
            selected=await view.record_table('PENGUMUMAN AKTIF' if status=='aktif' else 'ARSIP PENGUMUMAN',
                rows,key='id',renderer=announcement_row,initial=initial,
                caption=('Notifikasi penerima' if status=='aktif' else 'Arsip permanen')+' · Maks. 500',
                empty='Belum ada pengumuman aktif.' if status=='aktif' else 'Belum ada pengumuman yang diarsipkan.')
            if selected=='refresh':
                continue
            if not any(r['id']==selected for r in rows):
                return
            initial=selected
            item=await self._read(view,'Memuat isi pengumuman...',self.announcement_detail,selected)
            if item is None:
                continue
            await self.detail(view,item)

    async def detail(self,view,item):
        while self.is_admin():
            archived=bool(item.get('archived_at'))
            choices=[] if archived else [('archive','Arsipkan Pengumuman')]
            action=await view.page('DETAIL PENGUMUMAN',[*choices,('back','Kembali ke daftar')],
                lambda w,b:announcement_pages(item,w,b,'Arsip permanen; tidak dapat dipulihkan.' if archived else ''),
                default='back')
            if action!='archive' or archived:
                return
            if not await self._confirm(view,'KONFIRMASI ARSIP PENGUMUMAN',
                lambda w,b:announcement_pages(item,w,b,'Arsip permanen; tidak lagi tampil di Notifikasi penerima.'),
                'Ya, arsipkan'):
                continue
            try:
                await view.busy('Mengarsipkan pengumuman...',self.archive,item['id'])
            except (PermissionError,ValueError) as exc:
                await view.result('ARSIP GAGAL',str(exc),'error')
                return
            except Exception:
                await view.result('HASIL BELUM DAPAT DIPASTIKAN','Periksa daftar aktif dan arsip sebelum mencoba lagi.','warning')
                return
            await view.result('PENGUMUMAN DIARSIPKAN','Pengumuman tidak lagi tampil di Notifikasi penerima.','success')
            return

    async def _log_filters(self,view,filters=None):
        defaults=filters or {'pengguna':'','aksi':''}
        notice=''
        while self.is_admin():
            answer=await view.form('FILTER LOG AKTIVITAS',[Field('pengguna','ID / Username / Nama',defaults['pengguna']),
                Field('aksi','Aksi (contoh LOGIN)',defaults['aksi'])],
                hint='Kosong = semua aktivitas.',notice=notice,submit_label='Terapkan filter')
            if answer is None:
                return None
            defaults={k:answer[k].strip() for k in defaults}
            if len(defaults['pengguna'])>120 or len(defaults['aksi'])>60:
                notice='Pengguna maks. 120 karakter; aksi maks. 60.'
                continue
            return defaults
        return None

    async def browse_logs(self,view,*,filtered=False):
        filters=await self._log_filters(view) if filtered else None
        if filtered and filters is None:
            return
        initial=None
        while self.is_admin():
            if filters is None:
                rows=await self._read(view,'Memuat aktivitas...',self.logs,limit=200)
                caption='Terbaru'
            else:
                rows=await self._read(view,'Memuat aktivitas...',self.filter_logs,**filters,limit=200)
                caption='Pengguna: '+(filters['pengguna'] or 'semua')+' · Aksi: '+(filters['aksi'] or 'semua')
            if rows is None:
                return
            selected=await view.record_table('DAFTAR LOG AKTIVITAS',rows,key='id',renderer=log_row,
                caption=caption+' · Maks. 200',initial=initial,filter_action=True,empty='Tidak ada aktivitas yang cocok.')
            if selected=='refresh':
                continue
            if selected=='filter':
                new=await self._log_filters(view,filters)
                if new is not None:
                    filters=new;initial=None
                continue
            row=next((r for r in rows if r['id']==selected),None)
            if row is None:
                return
            initial=selected
            await view.page('DETAIL LOG AKTIVITAS',[('back','Kembali ke daftar')],
                lambda w,b:log_pages(row,w,b))


def build_controller():
    from app import session
    from app.services import report_service as reports,engagement_service as engage,log_service as logs
    return ReportingController(types=reports.daftar_jenis_laporan,report=reports.ambil_laporan,
        export_csv=reports.ekspor_csv,export_excel=reports.ekspor_excel,
        announcements=engage.daftar_pengumuman_admin,announcement_detail=engage.detail_pengumuman_admin,
        publish=engage.buat_pengumuman,archive=engage.arsipkan_pengumuman_admin,logs=logs.aktivitas_terbaru,
        filter_logs=logs.filter_aktivitas,is_admin=lambda:session.punya_role('admin'))


def menu_laporan_komunikasi_admin(initial=None):
    from app import session
    if not session.punya_role('admin'):
        return
    user=session.get_user() or {}
    controller=build_controller()
    return ConfirmationWorkspace(user.get('nama_lengkap') or user.get('username') or 'Admin').run(
        lambda view:controller.run(view,initial=initial))
