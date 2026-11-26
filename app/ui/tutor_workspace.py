"""UI-008 shared tutor workspace and adaptive dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .student_features import StudentFeatureWorkspace, empty_pages
from .admin_workspace import line, clip, paginate_blocks
from .admin_academic import add_band, add_panel, stat_tile
from .jadwal_context import jam_jadwal, label_hari, jadwal_rutin_terdekat

MENU=[
    ('jadwal','Jadwal & Detail Kelas'),('kelas','Kelas dan Siswa'),
    ('absensi','Absensi'),('nilai','Nilai'),('materi','Catatan Materi'),
    ('notifikasi','Notifikasi'),('pengumuman_tutor','Pengumuman Kelas'),
    ('tertunda','Pertemuan Tertunda'),('ai','SIBIMA-AI'),('profil','Profil Saya'),
    ('refresh','Muat ulang'),('logout','Logout'),
]


class TutorWorkspace(StudentFeatureWorkspace):
    """The common bounded page/table/form shell, with Tutor identity."""
    def _header(self):
        h=self._header_height()
        w=self._admin_width()
        if h==1:return [('class:brand',clip('S I B I M A · '+self.title,w))]
        if h==2:return [('class:brand','S I B I M A\n'),('class:title',clip(self.title,w))]
        return [('class:brand','S I B I M A\n'),
                ('class:muted',clip(self.nama+' · Tutor',w)+'\n'),
                ('class:rule','─'*w+'\n'),('class:title',clip(self.title,w))]


def name(user):return user.get('nama_lengkap') or user.get('username') or 'Tutor'


def run_tutor(controller):
    from app import session
    user=session.get_user() or {}
    if user.get('role')!='tutor' or user.get('status')!='aktif':
        return None
    return TutorWorkspace(name(user)).run(controller)


@dataclass(frozen=True)
class TutorSnapshot:
    stats:dict|None
    schedules:list|None
    unread:int|None
    sync_ok:bool

    def metric(self,key):
        v=self.stats.get(key) if self.stats is not None else None
        return '—' if v is None else str(v)


def load_snapshot(user,*,stats,schedules,sync,unread):
    try:
        s=stats(user['id'])
        if not isinstance(s,dict):s=None
    except Exception:s=None
    try:
        j=schedules(user['id'])
        if not isinstance(j,list):j=None
    except Exception:j=None
    try:sync('tutor');ok=True
    except Exception:ok=False
    try:
        n=unread('tutor')
        if type(n) is not int or n<0:n=None
    except Exception:n=None
    return TutorSnapshot(s,j,n,ok)


def session_label(status):
    return {None:'Terjadwal','perlu_laporan':'Perlu laporan','selesai':'Selesai',
            'batal':'Dibatalkan','terlaksana':'Catatan historis'}.get(status,'Status tidak diketahui')


def session_tone(status):
    return {'selesai':'success','perlu_laporan':'warning','batal':'error'}.get(status,'muted')


def _daily(rows,w):
    if rows is None:return [line('Jadwal gagal dimuat.',w,'warning','center')]
    today=[r for r in rows if r.get('hari_ini') is True]
    if not today:return [line('Tidak ada jadwal rutin hari ini.',w,'muted','center')]
    out=[]
    for r in today[:3]:
        out.append(line(jam_jadwal(r)+' · '+str(r.get('nama_program') or '—'),w,'title'))
        st=r.get('status_sesi_hari_ini')
        out.append(line(str(r.get('nama_ruang') or '—')+' · '+session_label(st),w,session_tone(st)))
    if len(today)>3:out.append(line(f'+ {len(today)-3} jadwal lain · buka Jadwal',w,'muted'))
    return out


def _weekly(rows,w):
    if rows is None:return [line('Jadwal gagal dimuat.',w,'warning','center')]
    if not rows:return [line('Belum ditugaskan jadwal aktif.',w,'muted','center')]
    out=[]
    for r in rows[:5]:
        out.append(line(label_hari(r.get('hari'))[:3]+' '+jam_jadwal(r)+' · '+str(r.get('nama_program') or '—'),w,'title'))
    if len(rows)>5:out.append(line(f'+ {len(rows)-5} jadwal lain',w,'muted'))
    return out


def dashboard_pages(snap,width,budget):
    b=max(1,budget)
    blocks=[]
    if snap.schedules==[] and snap.metric('program_diampu')=='0':
        blocks+=empty_pages('Belum ada jadwal mengajar yang ditugaskan Admin.','Pusat aktivitas pengajar',width=width,budget=b)
    metrics=[('PROGRAM DIAMPU','program_diampu','Program aktif'),
             ('SISWA AKTIF','siswa_aktif','Siswa unik'),('JADWAL AKTIF','jadwal_aktif','Slot mingguan'),
             ('PERLU LAPORAN','sesi_perlu_laporan','Sesi tercatat')]
    tiles=[(title,lambda w,k=k,d=d:stat_tile(snap.metric(k),d,w)) for title,k,d in metrics]
    if width<96:
        for i in range(0,len(tiles),2):add_band(blocks,tiles[i:i+2],width,b)
    else:add_band(blocks,tiles,width,b)
    notices=[]
    if snap.stats is None:notices.append('Statistik belum dapat dimuat.')
    if snap.schedules is None:notices.append('Daftar jadwal belum dapat dimuat.')
    pending=(snap.stats or {}).get('sesi_perlu_laporan')
    if isinstance(pending,int) and pending>0:notices.append(f'{pending} sesi tercatat belum selesai · buka Pertemuan Tertunda.')
    # Prioritize actionable alerts above schedule lists.
    if notices:add_panel(blocks,'PERLU PERHATIAN',lambda w:[line(t,w,'warning') for t in notices],width,b)
    if snap.schedules!=[]:
        add_band(blocks,[('JADWAL HARI INI',lambda w:_daily(snap.schedules,w)),
                         ('JADWAL MINGGUAN · RUTIN',lambda w:_weekly(snap.schedules,w))],width,b,weights=[3,2])
    status=('Notifikasi belum tersedia' if snap.unread is None else f'{snap.unread} notifikasi belum dibaca')
    status+=' · '+('Data belum lengkap' if snap.stats is None or snap.schedules is None or snap.unread is None or not snap.sync_ok else 'Data terakhir dimuat ●')
    blocks.append([line(status,width,'muted','center')])
    return paginate_blocks(blocks,b)


def _load(user):
    from app.repositories import tutor_dashboard_repo
    from app.services import engagement_service
    return load_snapshot(user,stats=tutor_dashboard_repo.ringkasan_tutor,
        schedules=tutor_dashboard_repo.jadwal_mingguan_tutor,
        sync=engagement_service.sinkronisasi_notifikasi,
        unread=engagement_service.jumlah_notifikasi_belum_dibaca)


class TutorDashboardNavigator:
    def __init__(self,load=_load):
        self.load=load
        self.focus='jadwal'

    async def choose(self,view,user):
        snap=await view.busy('Memuat aktivitas pengajar...',self.load,user)
        choices=[(key,title+(f' ({snap.unread} belum dibaca)' if key=='notifikasi' and snap.unread else '')) for key,title in MENU]
        result=await view.page('PUSAT AKTIVITAS PENGAJAR',choices,lambda w,b:dashboard_pages(snap,w,b),default=self.focus)
        self.focus=(getattr(view,'refresh_focus',None) or self.focus) if result=='refresh' else result or self.focus
        return result

    def run(self,user):
        return TutorWorkspace(name(user)).run(lambda view:self.choose(view,user))
