"""UI-005: varied, responsive academic CLI; all business mutations stay in services."""
from __future__ import annotations

import re

from .admin_confirmation import ConfirmationWorkspace, Field, details_pages, field_rows, value, rupiah
from .admin_workspace import (Snapshot, line, pad, clip, width_of, frame, band,
                              paginate_blocks, _compact_section, _schedule_rows, _schedule_heading, _time)
from .admin_navigation import KELOMPOK_MENU

DAYS=('senin','selasa','rabu','kamis','jumat','sabtu','minggu')
ROUTES=tuple((code,label) for label,code in KELOMPOK_MENU[2][1])
PROGRAM_MENU=[
    ('daftar_program','Daftar Program & Kuota'),('tambah_program','Tambah Program'),
    ('ubah_program','Ubah Program & Bobot Nilai'),('toggle_program','Tutup / Buka Program'),
    ('daftar_ruang','Daftar Ruang Belajar'),('tambah_ruang','Tambah Ruang'),
    ('ubah_ruang','Ubah Ruang'),
]
SCHEDULE_MENU=[
    ('lihat','Lihat & Filter Jadwal'),('tambah','Tambah Jadwal'),
    ('ubah','Ubah Jadwal'),('nonaktif','Nonaktifkan Jadwal'),
]
PROGRAM_FIELDS={'kode':'Kode program','nama':'Nama program','jenjang':'Jenjang',
                'deskripsi':'Deskripsi','harga_bulanan':'Harga bulanan','kuota':'Kuota siswa'}
WEIGHTS={'bobot_tugas':'Tugas','bobot_kuis':'Kuis','bobot_uts':'UTS','bobot_uas':'UAS'}
SCHEDULE_FIELDS={'program_id':'Program','tutor_id':'Tutor','room_id':'Ruang',
                 'hari':'Hari','jam_mulai':'Jam mulai','jam_selesai':'Jam selesai'}
REF_KIND={'program_id':'program','tutor_id':'tutor','room_id':'ruang'}
LABEL_KEY={'program_id':'nama_program','tutor_id':'nama_tutor','room_id':'nama_ruang'}


def count_pair(rows,predicate):
    return '—' if rows is None else f'{sum(predicate(x) for x in rows)}/{len(rows)}'


def total_text(n):
    return '—' if n is None else str(n)


def open_quota(programs):
    if programs is None:
        return None
    opened=[x for x in programs if x.get('status')=='buka']
    if any(x.get(k) is None for x in opened for k in ('kuota','terisi','sisa')):
        return None
    return dict(programs=len(opened),cap=sum(x['kuota'] for x in opened),
                used=sum(x['terisi'] for x in opened),left=sum(x['sisa'] for x in opened),
                full=sum(x['sisa']<=0 for x in opened))


def weekly_counts(schedules):
    if schedules is None:
        return None
    return {day:sum(x.get('aktif') is True and x.get('hari')==day for x in schedules) for day in DAYS}


def overview_metrics(data):
    p,r,s=data.get('programs'),data.get('rooms'),data.get('schedules')
    return {
        'program':count_pair(p,lambda x:x.get('status')=='buka'),
        'room':count_pair(r,lambda x:x.get('aktif') is True),
        'schedule':count_pair(s,lambda x:x.get('aktif') is True),
        'capacity':None if r is None or any(x.get('kapasitas') is None for x in r if x.get('aktif'))
                    else sum(x['kapasitas'] for x in r if x.get('aktif')),
    }


def stat_tile(val,description,width,changed=False):
    # Centered value tiles have an embedded title, rather than repeating 49x49 label cards.
    return [line(val,width,'success' if changed else 'number','center'),
            line(description,width,'muted','center')]


def panel(title,rows,width):
    return frame(rows,width,heading=title)


def add_panel(blocks,title,render,width,budget):
    rows=render(max(1,width-2))
    card=panel(title,rows,width)
    blocks.extend([card] if len(card)<=budget else _compact_section(title,render(width),width,budget))


def add_band(blocks,sections,width,budget,weights=None):
    """Allocate unequal or equal widths, equal-height borders, and safe fallback."""
    if width<78 or len(sections)==1:
        for title,render in sections:
            add_panel(blocks,title,render,width,budget)
        return
    weights=weights or [1]*len(sections)
    avail=width-2*(len(sections)-1)
    widths=[avail*v//sum(weights) for v in weights]
    widths[-1]+=avail-sum(widths)
    bodies=[render(cw-2) for (_,render),cw in zip(sections,widths)]
    height=max(map(len,bodies),default=0)
    cards=[panel(section[0],body+[[]]*(height-len(body)),cw)
           for section,body,cw in zip(sections,bodies,widths)]
    rows=band(cards,widths)
    if len(rows)<=budget:
        blocks.append(rows)
    else:
        for title,render in sections:
            add_panel(blocks,title,render,width,budget)


def bar_row(label,used,capacity,width,*,tone=None):
    if used is None or capacity is None:
        return line(f'{label} · —',width,'muted')
    ratio=f'{used}/{capacity}'
    if width<30:
        return line(label+' '+ratio,width,'title')
    rw=min(max(8,len(ratio)),max(8,width//3))
    bw=min(24,max(5,width//4))
    lw=max(1,width-rw-bw-2)
    filled=0 if capacity<=0 else max(0,min(bw,round(bw*used/capacity)))
    tone=tone or ('error' if used>=capacity and capacity>0 else 'warning' if capacity>0 and used*5>=capacity*4 else 'number')
    return [*line(label,lw,'title'),('', ' '),('class:'+tone,'█'*filled),
            ('class:rule','░'*(bw-filled)),('', ' '),*line(ratio,rw,'title','right')]


def quota_rows(programs,width,*,limit=5):
    if programs is None:
        return [line('Kuota gagal dimuat.',width,'warning','center')]
    if not programs:
        return [line('Belum ada program.',width,'muted','center')]
    opened=[r for r in programs if r.get('status')=='buka']
    if not opened:
        return [line('Tidak ada program buka.',width,'muted','center')]
    # Most filled open programs first; use the repo's own reserved-seat counts.
    rows=sorted(opened,key=lambda r: (r.get('sisa') is None,r.get('sisa') or 0,r['id']))
    result=[bar_row(r.get('nama') or '—',r.get('terisi'),r.get('kuota'),width)
            for r in rows[:limit]]
    result.append(line(f'{min(limit,len(rows))} dari {len(rows)} program buka · Terisi / kuota',
                       width,'muted','center'))
    return result


def quota_summary(programs,width):
    q=open_quota(programs)
    if q is None:
        return [line('Data kuota belum tersedia',width,'warning','center')]
    return [bar_row('Kuota',q['used'],q['cap'],width),
            line(f"Sisa kuota: {q['left']}",width,'title','center'),
            line(f"Program penuh: {q['full']}/{q['programs']}",width,'warning' if q['full'] else 'muted','center'),
            line('Program buka saja',width,'muted','center')]


def week_rows(schedules,width):
    counts=weekly_counts(schedules)
    if counts is None:
        return [line('Jadwal mingguan gagal dimuat.',width,'warning','center')]
    if width>=55:
        # One seven-column calendar strip, no redundant cards.
        sizes=[width//7+int(i<width%7) for i in range(7)]
        return [[f for day,w in zip(DAYS,sizes) for f in line(day[:3].capitalize(),w,'muted','center')],
                [f for day,w in zip(DAYS,sizes) for f in line(str(counts[day]),w,'number' if counts[day] else 'muted','center')]]
    return [line(f'{day.capitalize()} · {counts[day]} jadwal aktif',width,
                 'number' if counts[day] else 'muted') for day in DAYS]


def academic_pages(data,kind,width,budget,changed=frozenset()):
    width=max(8,width)
    budget=max(1,budget)
    blocks=[]
    metrics=overview_metrics(data)
    p,r,s,t=(data.get(k) for k in ('programs','rooms','schedules','today'))
    titles={'program':('PROGRAM', 'Buka / total'),'room':('RUANG', 'Aktif / total'),
            'schedule':('JADWAL','Rutin aktif / total')}
    selected=('program','room','schedule') if kind=='root' else ('program','room') if kind=='program' else ('schedule',)
    tiles=[(titles[key][0],lambda w,k=key:stat_tile(metrics[k],titles[k][1],w,k in changed))
           for key in selected]
    if kind=='program':
        tiles.append(('KAPASITAS RUANG',lambda w:stat_tile(total_text(metrics['capacity']),'Total kursi ruang aktif',w,
                                                        'capacity' in changed)))
    if kind=='jadwal':
        # Full-width calendar strip next to a concise total at normal widths.
        tiles.append(('DISTRIBUSI JADWAL AKTIF',lambda w:week_rows(s,w)))
        add_band(blocks,tiles,width,budget,[1,3])
    else:
        add_band(blocks,tiles,width,budget)
    if kind=='root':
        snap=Snapshot(None,t)
        add_band(blocks,[(_schedule_heading(snap),lambda w:_schedule_rows(snap,w)),
                         ('KUOTA PROGRAM BUKA',lambda w:quota_summary(p,w))],
                 width,budget,[2,1])
    elif kind=='program':
        add_panel(blocks,'KETERISIAN PROGRAM · PRIORITAS SISA KUOTA',lambda w:quota_rows(p,w),width,budget)
        blocks.append([line('Kapasitas ruang bukan indikator ruang kosong saat ini.',width,'muted','center')])
    else:
        snap=Snapshot(None,t)
        add_panel(blocks,_schedule_heading(snap),lambda w:_schedule_rows(snap,w),width,budget)
        blocks.append([line('Jadwal rutin, bukan absensi atau sesi yang sudah selesai.',width,'muted','center')])
    needed=('programs','rooms','schedules','today') if kind=='root' else ('programs','rooms') if kind=='program' else ('schedules','today')
    complete=all(data.get(k) is not None for k in needed)
    blocks.append([line('Data terakhir dimuat ●' if complete else 'Data belum lengkap · Muat ulang',
                        width,'muted' if complete else 'warning','center')])
    return paginate_blocks(blocks,budget)


def _table(width,columns,row=None,selected=False,tone='muted'):
    fixed=sum(cw for _,cw,_ in columns)
    flexible=sum(cw==0 for _,cw,_ in columns)
    free=max(flexible,width-2-(len(columns)-1)-fixed)
    base='class:selected' if selected else 'class:muted' if row is None else 'class:title'
    result=[(base,'❯ ' if selected else '  ')]
    n=0
    for i,(label,cw,field) in enumerate(columns):
        if cw==0:
            cw=free//flexible+int(n<free%flexible)
            n+=1
        if i:
            result.append((base,' '))
        style=base if selected or row is None else 'class:'+tone if label=='Status' else base
        result.append((style,pad(label if row is None else field(row),cw)))
    return result if width_of(result)<=width else [(base,pad(''.join(t for _,t in result),width))]


def program_row(width,row=None,selected=False):
    cols=[('ID',5,lambda r:value(r,'id')),('Kode',10,lambda r:value(r,'kode')),
          ('Program',0,lambda r:value(r,'nama')),('Jenjang',10,lambda r:value(r,'jenjang')),
          ('Harga/bln',14,lambda r:rupiah(r.get('harga_bulanan'))),
          ('Terisi/Kuota',12,lambda r:value(r,'terisi')+'/'+value(r,'kuota')),
          ('Sisa',6,lambda r:value(r,'sisa')),('Status',7,lambda r:value(r,'status').capitalize())]
    if width<90:
        cols=[c for c in cols if c[0]!='Jenjang']
    if width<75:
        cols=[c for c in cols if c[0] not in ('Harga/bln','Sisa')]
    if width<52:
        cols=[c for c in cols if c[0]!='Kode']
    if width<35:
        cols=[c for c in cols if c[0]!='Terisi/Kuota']
    return _table(width,cols,row,selected,'success' if row and row.get('status')=='buka' else 'muted')


def room_row(width,row=None,selected=False):
    return _table(width,[('ID',5,lambda r:value(r,'id')),('Ruang',0,lambda r:value(r,'nama')),
                         ('Kapasitas',10,lambda r:value(r,'kapasitas')),
                         ('Status',9,lambda r:'Aktif' if r.get('aktif') else 'Nonaktif')],row,selected,
                  'success' if row and row.get('aktif') else 'muted')


def schedule_row(width,row=None,selected=False):
    cols=[('ID',5,lambda r:value(r,'id')),('Hari',7,lambda r:value(r,'hari').capitalize()),
          ('Waktu',11,lambda r:_time(r.get('jam_mulai'))+'–'+_time(r.get('jam_selesai'))),
          ('Program',0,lambda r:value(r,'nama_program')),('Tutor',0,lambda r:value(r,'nama_tutor')),
          ('Ruang',0,lambda r:value(r,'nama_ruang')),('Siswa',5,lambda r:value(r,'jumlah_siswa')),
          ('Sesi',5,lambda r:value(r,'jumlah_pertemuan')),('Status',9,lambda r:'Aktif' if r.get('aktif') else 'Nonaktif')]
    if width<95:
        cols=[c for c in cols if c[0] not in ('Siswa','Sesi')]
    if width<74:
        cols=[c for c in cols if c[0]!='Ruang']
    if width<53:
        cols=[c for c in cols if c[0] not in ('Tutor','Hari')]
    return _table(width,cols,row,selected,'success' if row and row.get('aktif') else 'muted')


def option_row(kind,width,row=None,selected=False):
    if kind=='ruang':
        return room_row(width,row,selected)
    code='kode' if kind=='program' else 'kode_tutor'
    name='nama' if kind=='program' else 'nama_lengkap'
    cols=[('ID',5,lambda r:value(r,'id')),('Kode',12,lambda r:value(r,code)),
          ('Nama',0,lambda r:value(r,name)),
          ('Jenjang' if kind=='program' else 'Keahlian',0,lambda r:value(r,'jenjang' if kind=='program' else 'keahlian')),
          ('Status',16,lambda r:value(r,'status'))]
    if width<66:
        cols=[c for c in cols if c[0] not in ('Jenjang','Keahlian')]
    if width<48:
        cols=[c for c in cols if c[0]!='Kode']
    return _table(width,cols,row,selected,'success' if row and row.get('status') in ('buka','aktif') else 'muted')


def program_sections(row):
    return [
        ('IDENTITAS',[('Kode',value(row,'kode')),('Nama program',value(row,'nama')),('Jenjang',value(row,'jenjang')),
                     ('Status',value(row,'status'))]),
        ('BIAYA & KUOTA',[('Harga / bulan',rupiah(row.get('harga_bulanan'))),('Kuota',value(row,'kuota')),
                         ('Terisi',value(row,'terisi')),('Sisa',value(row,'sisa'))]),
        ('BOBOT NILAI',[(label,value(row,k)+'%') for k,label in WEIGHTS.items()]),
        ('DESKRIPSI',[('Deskripsi',value(row,'deskripsi')),('Dibuat',value(row,'created_at'))]),
    ]


def program_detail_pages(row,width,budget):
    """Use the program identity, capacity strip and grading bars, not four equal cards."""
    width=max(8,width)
    budget=max(1,budget)
    blocks=[]
    sections=program_sections(row)
    add_band(blocks,[
        ('IDENTITAS PROGRAM',lambda w:field_rows(sections[0][1],w,full=True)),
        ('BIAYA & KUOTA',lambda w:[line(rupiah(row.get('harga_bulanan'))+' / bulan',w,'number','center'),
             bar_row('Kuota',row.get('terisi'),row.get('kuota'),w),
             line('Sisa kuota: '+value(row,'sisa'),w,'title','center')]),
    ],width,budget,[3,2])
    def weights(w):
        result=[]
        for key,label in WEIGHTS.items():
            raw=row.get(key)
            result.append(bar_row(label,raw,100,w) if isinstance(raw,int) else line(label+' · '+value(row,key)+'%',w,'muted'))
        vals=[row.get(k) for k in WEIGHTS]
        total=sum(vals) if all(isinstance(v,int) for v in vals) else None
        result.append(line('Total: '+(str(total)+'%' if total is not None else '—'),w,'success' if total==100 else 'warning','center'))
        return result
    add_band(blocks,[('BOBOT PENILAIAN (%)',weights),
        ('DESKRIPSI',lambda w:field_rows(sections[3][1],w,full=True))],width,budget,[2,3])
    return paginate_blocks(blocks,budget)


def schedule_sections(row):
    return [
        ('JADWAL RUTIN',[('ID',value(row,'id')),('Hari',value(row,'hari').capitalize()),
                         ('Waktu',_time(row.get('jam_mulai'))+'–'+_time(row.get('jam_selesai'))),
                         ('Status','Aktif' if row.get('aktif') else 'Nonaktif')]),
        ('PENUGASAN',[('Program',value(row,'nama_program')),('Kode program',value(row,'kode_program')),
                     ('Tutor',value(row,'nama_tutor')),('Kode tutor',value(row,'kode_tutor')),
                     ('Ruang',value(row,'nama_ruang'))]),
        ('CATATAN KELAS',[('Peserta program',value(row,'jumlah_siswa')),('Kapasitas ruang',value(row,'kapasitas_ruang')),
                        ('Sesi tercatat',value(row,'jumlah_pertemuan'))]),
    ]


def room_sections(row):
    return [('RUANG BELAJAR',[('ID',value(row,'id')),('Nama',value(row,'nama')),
                             ('Kapasitas',value(row,'kapasitas')),('Status','Aktif' if row.get('aktif') else 'Nonaktif')])]


class AcademicController:
    def __init__(self,*,programs,rooms,today,schedules,detail_schedule,options,
                 create_program,update_program,create_room,update_room,create_schedule,update_schedule,
                 disable_schedule,is_admin):
        self.programs=programs;self.rooms=rooms;self.today=today
        self.schedules=schedules;self.detail_schedule=detail_schedule;self.options=options
        self.create_program=create_program;self.update_program=update_program
        self.create_room=create_room;self.update_room=update_room
        self.create_schedule=create_schedule;self.update_schedule=update_schedule
        self.disable_schedule=disable_schedule;self.is_admin=is_admin
        self.focus={};self.previous={}

    def _overview(self,kind):
        """Independent read failures remain unknown rather than becoming zero."""
        calls={}
        if kind in ('root','program'):
            calls.update(programs=(self.programs,False),rooms=(self.rooms,False))
        if kind in ('root','jadwal'):
            calls.update(schedules=(self.schedules,True),today=(self.today,False))
        data={}
        for key,(fn,service) in calls.items():
            try:
                result=fn()
                if service:
                    ok,result=result
                    if not ok:
                        result=None
                data[key]=result if isinstance(result,list) else None
            except Exception:
                data[key]=None
        return data

    async def _read(self,view,title,fn,*args,service=False,**kwargs):
        if not self.is_admin():
            return None
        try:
            result=await view.busy(title,lambda:fn(*args,**kwargs))
            if service:
                ok,result=result
                if not ok:
                    await view.result('DATA BELUM TERSEDIA',str(result),'error')
                    return None
            if result is None:
                await view.result('DATA BELUM TERSEDIA','Data tidak ditemukan. Muat ulang.','warning')
            return result
        except Exception:
            await view.result('DATA GAGAL DIMUAT','Periksa koneksi, lalu coba lagi.','error')
            return None

    async def _write(self,view,title,fn,*args):
        if not self.is_admin():
            return
        try:
            ok,message=await view.busy(title,fn,*args)
        except Exception:
            await view.result('HASIL BELUM DAPAT DIPASTIKAN','Periksa data terbaru sebelum mencoba kembali.','warning')
            return
        await view.result('PERUBAHAN TERSIMPAN' if ok else 'OPERASI GAGAL',str(message),
                          'success' if ok else 'error')

    async def _dashboard(self,view,kind,choices,title):
        try:
            data=await view.busy('Memuat ringkasan akademik...',self._overview,kind)
        except Exception:
            data={}
        if not self.is_admin():
            return None
        metrics=overview_metrics(data)
        previous=self.previous.get(kind,{})
        changed={k for k,v in metrics.items() if v not in (None,'—') and previous.get(k) not in (None,'—') and v!=previous[k]}
        self.previous[kind]={**previous,**{k:v for k,v in metrics.items() if v not in (None,'—')}}
        focus=self.focus.get(kind,choices[0][0])
        action=await view.page(title,[*choices,('refresh','Muat ulang'),
            ('back','Kembali ke dashboard' if kind=='root' else 'Kembali ke Akademik')],
            lambda w,b:academic_pages(data,kind,w,b,changed),default=focus)
        if action=='refresh':
            self.focus[kind]=getattr(view,'refresh_focus',None) or focus
        elif action not in (None,'back'):
            self.focus[kind]=action
        return action

    async def run(self,view,initial=None):
        if initial in ('program','jadwal'):
            await self.module(view,initial)
            return
        while self.is_admin():
            action=await self._dashboard(view,'root',ROUTES,'PUSAT AKADEMIK')
            if action in (None,'back') or not self.is_admin():
                return
            if action in ('program','jadwal'):
                await self.module(view,action)

    async def module(self,view,kind):
        menu=PROGRAM_MENU if kind=='program' else SCHEDULE_MENU
        title='PROGRAM & RUANG' if kind=='program' else 'MANAJEMEN JADWAL'
        routes={'daftar_program':self.browse_programs,'tambah_program':self.add_program,
                'ubah_program':self.edit_program,'toggle_program':self.toggle_program,
                'daftar_ruang':self.browse_rooms,'tambah_ruang':self.add_room,'ubah_ruang':self.edit_room} if kind=='program' else {
                'lihat':self.browse_schedules,'tambah':self.add_schedule,
                'ubah':self.edit_schedule,'nonaktif':self.deactivate_schedule}
        while self.is_admin():
            action=await self._dashboard(view,kind,menu,title)
            if action in (None,'back') or not self.is_admin():
                return
            if action in routes:
                await routes[action](view)

    async def _choose(self,view,title,choices,default=None,caption='Pilih salah satu'):
        return await view.page(title,[*choices,('back','Kembali')],
            lambda w,b:[[line(caption,w,'muted','center')]],default=default)

    async def _pick(self,view,title,loader,renderer,*,service=False,caption='Pilih data',**kwargs):
        while self.is_admin():
            rows=await self._read(view,'Memuat pilihan...',loader,service=service,**kwargs)
            if rows is None:
                return None
            selected=await view.record_table(title,rows,key='id',renderer=renderer,
                caption=caption,empty='Tidak ada data yang dapat dipilih.')
            if selected=='refresh':
                continue
            return next((r for r in rows if type(selected) is int and r['id']==selected),None)
        return None

    async def _confirm(self,view,title,sections,notice='',label='Ya, simpan'):
        if not self.is_admin():
            return False
        action=await view.page(title,[('confirm',label),('back','Batal')],
            lambda w,b:details_pages(sections,w,b,full=True,paired=True,notice=notice),default='back')
        return action=='confirm' and self.is_admin()

    async def _browse(self,view,title,loader,renderer,sections,detail_title,*,service=False,note='',detail_renderer=None,empty='Belum ada data.'):
        initial=None
        while self.is_admin():
            rows=await self._read(view,'Memuat data...',loader,service=service)
            if rows is None:
                return
            selected=await view.record_table(title,rows,key='id',renderer=renderer,caption='Pilih untuk melihat detail',
                initial=initial,empty=empty)
            if selected=='refresh':
                continue
            row=next((r for r in rows if r['id']==selected),None)
            if row is None:
                return
            initial=selected
            await view.page(detail_title,[('back','Kembali ke daftar')],
                lambda w,b:detail_renderer(row,w,b) if detail_renderer is not None else
                details_pages(sections(row),w,b,full=True,paired=True,notice=note))

    async def browse_programs(self,view):
        await self._browse(view,'DAFTAR PROGRAM DAN KUOTA',self.programs,program_row,program_sections,'DETAIL PROGRAM',detail_renderer=program_detail_pages,empty='Belum ada program bimbel.')

    async def browse_rooms(self,view):
        await self._browse(view,'DAFTAR RUANG BELAJAR',self.rooms,room_row,room_sections,'DETAIL RUANG',empty='Belum ada ruang belajar.')

    async def add_program(self,view):
        first=await view.form('TAMBAH PROGRAM',[Field(k,PROGRAM_FIELDS[k]) for k in ('kode','nama','jenjang')],
            step='1/2',hint='Kode maksimal 10 karakter.',submit_label='Lanjutkan')
        if first is None or not self.is_admin():
            return
        second=await view.form('TAMBAH PROGRAM',[Field('deskripsi','Deskripsi (opsional)'),
            Field('harga_bulanan','Harga bulanan (angka)'),Field('kuota','Kuota siswa')],
            step='2/2',hint='Harga 0 untuk program gratis.',submit_label='Lanjutkan')
        if second is None:
            return
        data={**first,**second}
        sections=[('PROGRAM BARU',[(PROGRAM_FIELDS[k],data.get(k,'') or '—') for k in PROGRAM_FIELDS]),
                  ('BOBOT AWAL',[('Tugas','30%'),('Kuis','20%'),('UTS','20%'),('UAS','30%'),('Total','100%')])]
        if await self._confirm(view,'KONFIRMASI PROGRAM BARU',sections,
                               'Validasi kode, harga dan kuota dilakukan saat disimpan.'):
            await self._write(view,'Membuat program...',self.create_program,data)

    async def edit_program(self,view):
        row=await self._pick(view,'PILIH PROGRAM UNTUK DIUBAH',self.programs,program_row)
        if row is None:
            return
        field=await self._choose(view,'PILIH DATA PROGRAM',[*PROGRAM_FIELDS.items(),('bobot','Bobot nilai (semua komponen)')],
                                 caption=value(row,'kode')+' · '+value(row,'nama'))
        if field in (None,'back'):
            return
        if field=='bobot':
            data={}
            keys=list(WEIGHTS)
            for i,group in enumerate((keys[:2],keys[2:])):
                answer=await view.form('UBAH BOBOT NILAI',[Field(k,WEIGHTS[k]+' (%)',str(row[k])) for k in group],
                    step=f'{i+1}/2',subtitle=value(row,'nama'),hint='Total seluruh bobot harus tepat 100%.',submit_label='Lanjutkan')
                if answer is None:
                    return
                data.update(answer)
            try:
                numbers=[int(data[k].strip()) for k in keys]
                valid=(all(re.fullmatch(r'[+-]?\d+',data[k].strip()) for k in keys)
                       and all(0<=x<=100 for x in numbers) and sum(numbers)==100)
            except (ValueError,TypeError,KeyError):
                valid=False
            if not valid:
                await view.result('BOBOT BELUM VALID','Isi bobot bulat 0–100; jumlah seluruhnya harus tepat 100%.','error')
                return
            labels=WEIGHTS
        else:
            if field not in PROGRAM_FIELDS:
                return
            answer=await view.form('UBAH PROGRAM',[Field(field,PROGRAM_FIELDS[field],
                  str(row.get(field) if row.get(field) is not None else ''))],subtitle=value(row,'nama'),
                  hint='Kosongkan untuk menghapus deskripsi.' if field=='deskripsi' else 'Masukkan nilai baru.',
                  submit_label='Lanjutkan')
            if answer is None:
                return
            data={field:None if field=='deskripsi' and not answer[field].strip() else answer[field]}
            labels=PROGRAM_FIELDS
        sections=[('SEBELUM',[(labels[k],value(row,k)) for k in data]),
                  ('SESUDAH',[(labels[k],str(v) if v is not None else 'Dikosongkan') for k,v in data.items()])]
        if await self._confirm(view,'KONFIRMASI UBAH PROGRAM',sections,
                               'Kuota baru tidak boleh kurang dari jumlah terisi.' if field=='kuota' else
                               'Total bobot baru: 100%.' if field=='bobot' else ''):
            await self._write(view,'Menyimpan program...',self.update_program,row['id'],data)

    async def toggle_program(self,view):
        row=await self._pick(view,'PILIH PROGRAM BUKA / TUTUP',self.programs,program_row)
        if row is None or row.get('status') not in ('buka','tutup'):
            return
        target='tutup' if row['status']=='buka' else 'buka'
        sections=[('PROGRAM',[('Nama',value(row,'nama')),('Kode',value(row,'kode'))]),
                  ('PERUBAHAN STATUS',[('Saat ini',row['status'].capitalize()),('Status baru',target.capitalize())])]
        if await self._confirm(view,'KONFIRMASI STATUS PROGRAM',sections,label='Ya, '+('tutup program' if target=='tutup' else 'buka program')):
            await self._write(view,'Memperbarui program...',self.update_program,row['id'],{'status':target})

    async def add_room(self,view):
        data=await view.form('TAMBAH RUANG',[Field('nama','Nama ruang'),Field('kapasitas','Kapasitas ruang')],
            hint='Nama maksimal 30 karakter; kapasitas angka bulat.',submit_label='Lanjutkan')
        if data is None:
            return
        if await self._confirm(view,'KONFIRMASI RUANG BARU',[('RUANG BELAJAR',
                [('Nama',data['nama']),('Kapasitas',data['kapasitas'])])]):
            await self._write(view,'Membuat ruang...',self.create_room,data['nama'],data['kapasitas'])

    async def edit_room(self,view):
        row=await self._pick(view,'PILIH RUANG UNTUK DIUBAH',self.rooms,room_row)
        if row is None:
            return
        data=await view.form('UBAH RUANG',[Field('nama','Nama ruang',str(row['nama'])),
            Field('kapasitas','Kapasitas',str(row['kapasitas']))],hint='Masukkan data baru.',submit_label='Lanjutkan')
        if data is None:
            return
        if await self._confirm(view,'KONFIRMASI UBAH RUANG',[
                ('SEBELUM',[('Nama',value(row,'nama')),('Kapasitas',value(row,'kapasitas'))]),
                ('SESUDAH',[('Nama',data['nama']),('Kapasitas',data['kapasitas'])])]):
            await self._write(view,'Menyimpan ruang...',self.update_room,row['id'],data)

    async def _pick_option(self,view,kind,active_only):
        return await self._pick(view,'PILIH '+kind.upper(),self.options[kind],
            lambda w,row=None,selected=False:option_row(kind,w,row,selected),service=True,
            caption='Pilihan aktif / terbuka' if active_only else 'Seluruh pilihan',aktif_saja=active_only)

    async def _day(self,view,default=None):
        selected=await self._choose(view,'PILIH HARI',[(d,d.capitalize()) for d in DAYS],default=default)
        return selected if selected in DAYS else None

    async def _filters(self,view):
        selected=await self._choose(view,'FILTER JADWAL',[
            ('all','Semua jadwal'),('program','Per program'),('tutor','Per tutor'),('ruang','Per ruang'),('hari','Per hari')],
            default='all')
        if selected in (None,'back'):
            return None
        if selected=='all':
            return {},'Semua jadwal'
        if selected=='hari':
            day=await self._day(view)
            return None if day is None else ({'hari':day},day.capitalize())
        row=await self._pick_option(view,selected,False)
        if row is None:
            return None
        key={'program':'program_id','tutor':'tutor_id','ruang':'room_id'}[selected]
        return {key:row['id']},value(row,'nama_lengkap' if selected=='tutor' else 'nama')

    async def browse_schedules(self,view):
        filters=await self._filters(view)
        if filters is None:
            return
        initial=None
        while self.is_admin():
            args,caption=filters
            rows=await self._read(view,'Memuat jadwal...',self.schedules,service=True,**args)
            if rows is None:
                return
            selected=await view.record_table('DAFTAR JADWAL MENGAJAR',rows,key='id',renderer=schedule_row,
                caption=caption+' · Siswa per program · Sesi tercatat',initial=initial,filter_action=True,empty='Tidak ada jadwal sesuai filter.')
            if selected=='filter':
                new=await self._filters(view)
                if new is not None:
                    filters=new;initial=None
                continue
            if selected=='refresh':
                continue
            if not any(r['id']==selected for r in rows):
                return
            initial=selected
            row=await self._read(view,'Memuat detail...',self.detail_schedule,selected,service=True)
            if row is None:
                continue
            await view.page('DETAIL JADWAL',[('back','Kembali ke daftar')],
                lambda w,b:details_pages(schedule_sections(row),w,b,full=True,paired=True,
                    notice='Peserta dihitung per program. Sesi tercatat termasuk yang dibatalkan.'))

    async def add_schedule(self,view):
        data={};labels={}
        for key,kind in REF_KIND.items():
            option=await self._pick_option(view,kind,True)
            if option is None:
                return
            data[key]=option['id']
            labels[key]=value(option,'nama_lengkap' if kind=='tutor' else 'nama')+f" (ID {option['id']})"
        day=await self._day(view)
        if day is None:
            return
        answer=await view.form('WAKTU JADWAL',[Field('jam_mulai','Jam mulai (HH:MM)'),Field('jam_selesai','Jam selesai (HH:MM)')],
            subtitle=day.capitalize(),hint='Contoh: 15:00 – 16:30.',submit_label='Lanjutkan')
        if answer is None:
            return
        data.update(hari=day,**answer)
        sections=[('PENUGASAN',[(SCHEDULE_FIELDS[k],labels[k]) for k in REF_KIND]),
                  ('WAKTU RUTIN',[('Hari',day.capitalize()),('Jam mulai',answer['jam_mulai']),('Jam selesai',answer['jam_selesai'])])]
        if await self._confirm(view,'KONFIRMASI JADWAL BARU',sections,
                               'Service memeriksa bentrok tutor dan ruang saat penyimpanan.'):
            await self._write(view,'Membuat jadwal...',self.create_schedule,data)

    async def _active_schedule(self,view,title):
        row=await self._pick(view,title,self.schedules,schedule_row,service=True,aktif=True,caption='Jadwal aktif')
        if row is None:
            return None
        fresh=await self._read(view,'Memuat jadwal terbaru...',self.detail_schedule,row['id'],service=True)
        if fresh is None:
            return None
        if not fresh.get('aktif'):
            await view.result('JADWAL BERUBAH','Jadwal sudah nonaktif. Muat ulang.','warning')
            return None
        return fresh

    async def edit_schedule(self,view):
        row=await self._active_schedule(view,'PILIH JADWAL UNTUK DIUBAH')
        if row is None:
            return
        if (row.get('jumlah_pertemuan') or 0)>0:
            await view.result('JADWAL MEMILIKI RIWAYAT','Nonaktifkan jadwal lama lalu buat jadwal baru untuk menjaga riwayat.','warning')
            return
        field=await self._choose(view,'PILIH BAGIAN JADWAL',list(SCHEDULE_FIELDS.items()),
                                 caption='ID '+str(row['id'])+' · '+value(row,'nama_program'))
        if field in (None,'back'):
            return
        if field in REF_KIND:
            option=await self._pick_option(view,REF_KIND[field],True)
            if option is None:
                return
            new=option['id']
            before=value(row,LABEL_KEY[field])
            after=value(option,'nama_lengkap' if field=='tutor_id' else 'nama')+f" (ID {new})"
        elif field=='hari':
            new=await self._day(view,row.get('hari'))
            if new is None:
                return
            before=value(row,'hari').capitalize();after=new.capitalize()
        elif field in ('jam_mulai','jam_selesai'):
            before=_time(row.get(field))
            answer=await view.form('UBAH WAKTU JADWAL',[Field(field,SCHEDULE_FIELDS[field]+' (HH:MM)',before)],
                hint='Masukkan waktu baru.',submit_label='Lanjutkan')
            if answer is None:
                return
            new=after=answer[field]
        else:
            return
        sections=[('JADWAL',[('ID',value(row,'id')),('Program',value(row,'nama_program')),
                             ('Hari',value(row,'hari')),('Waktu',_time(row.get('jam_mulai'))+'–'+_time(row.get('jam_selesai')))]),
                  ('PERUBAHAN',[(SCHEDULE_FIELDS[field]+' lama',before),(SCHEDULE_FIELDS[field]+' baru',after)])]
        if await self._confirm(view,'KONFIRMASI UBAH JADWAL',sections,
                               'Service tetap memeriksa bentrok dan riwayat pertemuan.'):
            await self._write(view,'Menyimpan jadwal...',self.update_schedule,row['id'],{field:new})

    async def deactivate_schedule(self,view):
        row=await self._active_schedule(view,'PILIH JADWAL UNTUK DINONAKTIFKAN')
        if row is None:
            return
        if await self._confirm(view,'KONFIRMASI NONAKTIFKAN JADWAL',schedule_sections(row),
                               'Riwayat pertemuan tetap disimpan.',label='Ya, nonaktifkan jadwal'):
            await self._write(view,'Menonaktifkan jadwal...',self.disable_schedule,row['id'])


def build_controller():
    from app import session
    from app.repositories import program_repo,admin_dashboard_repo
    from app.services import program_service as ps,schedule_service as ss
    return AcademicController(
        programs=program_repo.daftar_program_dengan_kuota,rooms=program_repo.daftar_ruang,
        today=admin_dashboard_repo.jadwal_hari_ini_admin,schedules=ss.daftar_jadwal,detail_schedule=ss.detail_jadwal,
        options={'program':ss.opsi_program,'tutor':ss.opsi_tutor,'ruang':ss.opsi_ruang},
        create_program=ps.buat_program,update_program=ps.ubah_program,create_room=ps.buat_ruang,update_room=ps.ubah_ruang,
        create_schedule=ss.buat_jadwal,update_schedule=ss.ubah_jadwal,disable_schedule=ss.nonaktifkan_jadwal,
        is_admin=lambda:session.punya_role('admin'))


def menu_akademik_admin(initial=None):
    from app import session
    if not session.punya_role('admin'):
        return
    user=session.get_user() or {}
    controller=build_controller()
    ConfirmationWorkspace(user.get('nama_lengkap') or user.get('username') or 'Admin').run(
        lambda view:controller.run(view,initial=initial))
