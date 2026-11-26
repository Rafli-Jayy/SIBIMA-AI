"""UI-007A: student dashboard/onboarding presentation, using existing services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from .admin_confirmation import ConfirmationWorkspace, rupiah, wrap
from .admin_workspace import (
    line, clip, dashboard_card, paginate_blocks, _compact_section,
)
from .admin_academic import add_band, add_panel, stat_tile
from .jadwal_context import HARI, jam_jadwal, jadwal_rutin_terdekat

MENU = [
    ('katalog','Katalog Program'),('pendaftaran','Kelas Saya'),
    ('jadwal','Jadwal Saya'),('absensi','Absensi'),('nilai','Nilai & Rapor'),
    ('pembayaran','Tagihan & Pembayaran'),('materi','Catatan Materi'),
    ('notifikasi','Notifikasi'),('ai','SIBIMA-AI'),('profil','Profil Saya'),
    ('refresh','Muat ulang'),('logout','Logout'),
]
STATUS = {
    'aktif':'Aktif','menunggu_pembayaran':'Menunggu bayar','menunggu':'Menunggu Admin',
    'ditolak':'Ditolak','batal':'Dibatalkan','selesai':'Selesai','ditangguhkan':'Ditangguhkan',
}


class StudentWorkspace(ConfirmationWorkspace):
    """Same bounded workspace/key bindings as Admin, but a student identity."""
    def _nav_height(self):
        # Include the separator before Logout, too.
        return min(len(self.choices)+int(any(k in ('back','logout') for k,_ in self.choices)),
                   max(1,self._remaining()-1))

    def _header(self):
        h=self._header_height()
        w=self._admin_width()
        if h==1:
            return [('class:brand',clip('S I B I M A · '+self.title,w))]
        if h==2:
            return [('class:brand','S I B I M A\n'),('class:title',clip(self.title,w))]
        return [('class:brand','S I B I M A\n'),
                ('class:muted',clip(self.nama+' · Siswa',w)+'\n'),
                ('class:rule','─'*w+'\n'),('class:title',clip(self.title,w))]


def accessible(item):
    # A missing lock flag is not evidence of accessible enrollment.
    return item.get('status')=='aktif' and item.get('akses_terkunci') is False


def label(item):
    if item.get('status')=='aktif':
        if item.get('akses_terkunci') is True:
            return 'Terkunci H+3'
        if not accessible(item):
            return 'Akses belum pasti'
    return STATUS.get(item.get('status'),'Status lain')


@dataclass(frozen=True)
class StudentSnapshot:
    enrollments: list[dict]
    stats: dict | None
    schedules: list[dict] | None
    attendance: list[dict] | None
    grades: list[dict] | None
    unread: int | None
    sync_ok: bool
    today: date


def _safe_read(fn,*args):
    try:
        ok,data=fn(*args)
        return data if ok and isinstance(data,list) else None
    except Exception:
        return None


def load_snapshot(student_id,enrollments,*,stats,schedules,attendance,grades,sync,unread,today=None):
    """Read existing APIs independently. Do not expose the legacy aggregate's
    unfiltered academic metrics. Filter scoped service results to the currently
    accessible enrollment identifiers and never query academic data if all locked.
    """
    active=[x for x in enrollments if accessible(x)]
    prog_ids={x['program_id'] for x in active if type(x.get('program_id')) is int}
    e_ids={x['enrollment_id'] for x in active if type(x.get('enrollment_id')) is int}
    try:
        financial=stats(student_id)
        if not isinstance(financial,dict):
            financial=None
        else:
            financial={k:financial.get(k) for k in ('tagihan_belum_lunas','jumlah_tagihan','tagihan_terlambat')}
    except Exception:
        financial=None
    j=_safe_read(schedules) if prog_ids else []
    a=_safe_read(attendance) if e_ids else []
    g=_safe_read(grades) if e_ids else []
    if j is not None:
        j=[x for x in j if x.get('program_id') in prog_ids]
    if a is not None:
        a=[x for x in a if x.get('enrollment_id') in e_ids]
    if g is not None:
        g=[x for x in g if x.get('enrollment_id') in e_ids]
    try:
        sync('siswa')
        sync_ok=True
    except Exception:
        sync_ok=False
    try:
        count=unread('siswa')
        n=count if type(count) is int and count>=0 else None
    except Exception:
        n=None
    return StudentSnapshot(list(enrollments),financial,j,a,g,n,sync_ok,today or date.today())


def _stat(snap,k):
    return None if snap.stats is None else snap.stats.get(k)


def _changed(old,new):
    return old is not None and new is not None and old!=new


def _counts(snap):
    rows=snap.enrollments
    active=sum(accessible(r) for r in rows)
    locked=sum(r.get('status')=='aktif' and r.get('akses_terkunci') is True for r in rows)
    unknown=sum(r.get('status')=='aktif' and r.get('akses_terkunci') is not True and r.get('akses_terkunci') is not False for r in rows)
    pending=sum(r.get('status')=='menunggu' for r in rows)
    pay=sum(r.get('status')=='menunggu_pembayaran' for r in rows)
    return active,locked,unknown,pending,pay


def _attendance(snap):
    if not any(accessible(r) for r in snap.enrollments):
        return '—','Belum ada akses kelas'
    if snap.attendance is None:
        return '—','Rekap gagal dimuat'
    if not snap.attendance:
        return '—','Belum ada rekap'
    expected={r.get('enrollment_id') for r in snap.enrollments if accessible(r)}
    if not expected.issubset({r.get('enrollment_id') for r in snap.attendance}):
        return '—','Rekap belum lengkap'
    if any(r.get('hadir') is None or r.get('total_pertemuan') is None for r in snap.attendance):
        return '—','Rekap belum lengkap'
    count=sum(r['hadir'] for r in snap.attendance)
    total=sum(r['total_pertemuan'] for r in snap.attendance)
    return str(count),'Sesi selesai: '+str(total) if total else 'Belum ada sesi selesai'


def _score(raw):
    if raw is None:
        return '—'
    try:
        n=Decimal(str(raw))
        return f'{n:.1f}' if n.is_finite() else '—'
    except (InvalidOperation,ValueError):
        return '—'


def _class_rows(snap,w):
    # Prioritize accessible/current programs, not old rejected registrations.
    rows=snap.enrollments
    current=[x for x in rows if x.get('status') in ('aktif','menunggu','menunggu_pembayaran','ditangguhkan')]
    if not current:
        return [line('Belum ada kelas berjalan.',w,'muted','center'),
                line('Buka Katalog Program.',w,'title','center')]
    ordered=sorted(current,key=lambda r:0 if accessible(r) else 1 if r.get('status')=='aktif' else 2)
    grade_map={g.get('enrollment_id'):g.get('nilai_akhir') for g in (snap.grades or [])}
    show_grade=w>=42 and any(accessible(r) for r in current)
    sw=min(17,max(11,w//3))
    gw=11 if show_grade else 0
    nw=max(1,w-sw-gw-(2 if show_grade else 1))
    if w<20:
        return [line((r.get('nama_program') or '—')+' · '+label(r),w,'title') for r in ordered[:3]]
    results=[[*line('Program',nw),('', ' '),*line('Status',sw),
              *([('', ' '),*line('Nilai akhir',gw,'muted','right')] if show_grade else [])]]
    for r in ordered[:3]:
        tone='success' if accessible(r) else 'warning' if r.get('status') in ('aktif','menunggu','menunggu_pembayaran','ditangguhkan') else 'muted'
        score=_score(grade_map.get(r.get('enrollment_id'))) if accessible(r) else '—'
        results.append([*line(r.get('nama_program') or '—',nw,'title'),('', ' '),*line(label(r),sw,tone),
                        *([('', ' '),*line(score,gw,'number','right')] if show_grade else [])])
    if len(current)>3:
        results.append(line(f'+ {len(current)-3} kelas lain · Kelas Saya',w,'muted'))
    return results


def _schedule_rows(snap,w):
    active,locked,unknown,_,_=_counts(snap)
    if not active:
        msg=('Akses kelas terkunci H+3.' if locked else 'Status akses belum pasti.' if unknown else 'Belum ada kelas aktif.')
        return [line(msg,w,'warning' if locked or unknown else 'muted','center')]
    if snap.schedules is None:
        return [line('Jadwal gagal dimuat.',w,'warning','center')]
    if not snap.schedules:
        return [line('Belum ada jadwal rutin.',w,'muted','center'),line('Hubungi Admin.',w,'muted','center')]
    day=HARI[snap.today.weekday()]
    today=[r for r in snap.schedules if r.get('hari')==day]
    if not today:
        out=[line('Tidak ada jadwal rutin hari ini.',w,'muted','center')]
        upcoming=jadwal_rutin_terdekat(snap.schedules,snap.today)
        if upcoming:
            dt,row=upcoming
            out.append(line('Berikutnya (perkiraan): '+dt.strftime('%d/%m'),w,'title'))
            out.append(line(jam_jadwal(row)+' · '+str(row.get('nama_program') or '—'),w,'number'))
        return out
    out=[]
    for r in today[:2]:
        out.append(line(jam_jadwal(r)+' · '+str(r.get('nama_program') or '—'),w,'title'))
        out.append(line(str(r.get('nama_tutor') or '—')+' · '+str(r.get('nama_ruang') or '—'),w,'muted'))
    if len(today)>2:
        out.append(line(f'+ {len(today)-2} jadwal lain · Jadwal Saya',w,'muted'))
    return out


def _inset(fn,w):
    if w<10:
        return fn(w)
    return [[('', ' '),*r,('', ' ')] for r in fn(w-2)]


def _attention(snap,w):
    active,locked,unknown,pending,pay=_counts(snap)
    messages=[]
    if locked:
        messages.append((f'{locked} kelas terkunci H+3 · Buka Tagihan & Pembayaran.','warning'))
    suspended=sum(r.get('status')=='ditangguhkan' for r in snap.enrollments)
    if suspended:
        messages.append((f'{suspended} pendaftaran ditangguhkan · Periksa Kelas Saya.','warning'))
    if unknown:
        messages.append((f'{unknown} status akses kelas belum pasti · Muat ulang.','warning'))
    if pay:
        messages.append((f'{pay} pendaftaran menunggu pembayaran pertama.','warning'))
    if pending:
        messages.append((f'{pending} pendaftaran menunggu persetujuan Admin.','warning'))
    count=_stat(snap,'tagihan_belum_lunas')
    if count is None:
        messages.append(('Ringkasan tagihan gagal dimuat.','warning'))
    elif count:
        total=_stat(snap,'jumlah_tagihan')
        due=_stat(snap,'tagihan_terlambat')
        messages.append((f'{count} tagihan belum lunas · {rupiah(total)}'+(f' · {due} lewat jatuh tempo' if due else ''),'warning'))
    if not messages:
        messages.append(('Tidak ada pendaftaran atau tagihan yang perlu perhatian.','success'))
    return [line(part,w,tone) for t,tone in messages for part in wrap(t,w)[:2]]


def _status(snap,width):
    unknown=(snap.stats is None or any(_stat(snap,k) is None for k in ('tagihan_belum_lunas','jumlah_tagihan','tagihan_terlambat'))
             or snap.schedules is None or snap.attendance is None or snap.grades is None
             or snap.unread is None or not snap.sync_ok)
    events='Notifikasi belum tersedia' if snap.unread is None else f'{snap.unread} notifikasi belum dibaca'
    stamp='Data belum lengkap · Muat ulang' if unknown else 'Data terakhir dimuat ●'
    if width>=62:
        return [line(events+' · '+stamp,width,'warning' if unknown else 'muted','center')]
    return [line(events,width,'muted','center'),line(stamp,width,'warning' if unknown else 'muted','center')]


def _welcome(width,budget,history=False):
    message=('Belum ada pendaftaran berjalan. Riwayat sebelumnya tetap tersimpan.'
             if history else 'Kamu belum memiliki kelas bimbel.')
    # Reuse the top-centered, 64-column empty card geometry; adapt both message
    # and next-step content to a student's initial state.
    cw=min(64,width)
    text_rows=[line(t,cw-2,'title','center') for t in wrap(message,max(1,cw-4))]
    hints=[line(t,cw-2,'muted','center') for t in wrap('Buka Katalog Program untuk mulai mendaftar.',max(1,cw-4))]
    rows=dashboard_card('MULAI BELAJAR',[*text_rows,*hints],cw)
    if len(rows)>budget:
        return _compact_section('MULAI BELAJAR',[line(message,width,'title','center'),line('Buka Katalog Program.',width,'muted','center')],width,budget)
    return [[[('', ' '*((width-cw)//2)),*r,('', ' '*(width-cw-(width-cw)//2))] for r in rows]]


def dashboard_pages(snap,width,budget,previous=None):
    """Bounded cards, status-specific priorities, no duplicate quick-access list."""
    budget=max(1,budget)
    blocks=[]
    active,locked,unknown,pending,pay=_counts(snap)
    old_counts=_counts(previous) if previous else None
    presence,note=_attendance(snap)
    old_presence=_attendance(previous)[0] if previous else None
    unpaid=_stat(snap,'tagihan_belum_lunas')
    if not (active or locked or unknown or pending or pay or any(r.get('status')=='ditangguhkan' for r in snap.enrollments)):
        blocks.extend(_welcome(width,budget,bool(snap.enrollments)))
    add_band(blocks,[
        ('KELAS AKTIF',lambda w:stat_tile(str(active),f'Dapat diakses · {locked} terkunci' if locked else 'Dapat diakses',w,
          old_counts is not None and _changed(old_counts[0],active))),
        ('KEHADIRAN',lambda w:stat_tile(presence,note,w,_changed(old_presence,presence) and '—' not in (old_presence,presence))),
        ('TAGIHAN',lambda w:stat_tile('—' if unpaid is None else str(unpaid),'Belum lunas',w,
          previous is not None and _changed(_stat(previous,'tagihan_belum_lunas'),unpaid))),
    ],width,budget)
    status=_status(snap,width)
    # Keep warnings visible before longer preview panels at short heights.
    urgent=locked or unknown or pending or pay or _stat(snap,'tagihan_belum_lunas') or _stat(snap,'tagihan_belum_lunas') is None
    compact=budget<16
    prioritize=compact or locked or unknown or pending or pay
    if prioritize:
        add_panel(blocks,'PERLU PERHATIAN',lambda w:_inset(lambda x:_attention(snap,x),w),width,budget)
    if active or locked or unknown or pending or pay or snap.enrollments:
        add_band(blocks,[('KELAS SAYA',lambda w:_inset(lambda x:_class_rows(snap,x),w)),
                         ('JADWAL HARI INI · '+HARI[snap.today.weekday()].upper(),lambda w:_inset(lambda x:_schedule_rows(snap,x),w))],width,budget,[3,2])
    if not prioritize and (urgent or active or snap.enrollments):
        add_panel(blocks,'PERLU PERHATIAN',lambda w:_inset(lambda x:_attention(snap,x),w),width,budget)
    # Keep unread status intact even on very short displays.
    blocks.extend([[r] for r in status] if len(status)>budget else [status])
    return paginate_blocks(blocks,budget)


def onboarding_pages(enrollments,width,budget):
    """Pending account: no enrollment or academic actions, even in inconsistent states."""
    budget=max(1,budget)
    blocks=[]
    def account(w):
        return [line('MENUNGGU PERSETUJUAN ADMIN',w,'warning','center'),
                *[line(t,w,'muted','center') for t in wrap('NIS diterbitkan setelah akun disetujui. Pendaftaran program terpisah.',w)]]
    add_panel(blocks,'STATUS AKUN',account,width,budget)
    waiting=[r for r in enrollments if r.get('status')=='menunggu']
    active=[r for r in enrollments if r.get('status')=='aktif']
    if active:
        add_panel(blocks,'PERLU PEMERIKSAAN',lambda w:[
            line(f'{len(active)} pendaftaran aktif pada akun pending.',w,'warning','center'),
            line('Hubungi Admin untuk memeriksa konsistensi data.',w,'muted','center')],width,budget)
    if waiting:
        add_panel(blocks,'PENDAFTARAN TERCATAT',lambda w:[
            *[line(r.get('nama_program') or '—',w,'title') for r in waiting[:3]],
            line(f'{len(waiting)} pendaftaran menunggu keputusan program.',w,'muted')],width,budget)
    if not active and not waiting:
        # Do not imply the student can enroll before approval.
        add_panel(blocks,'LANGKAH BERIKUTNYA',lambda w:[
            line('Tunggu keputusan akun dari Admin.',w,'title','center'),
            line('Pilih Periksa status atau Logout.',w,'muted','center')],width,budget)
    return paginate_blocks(blocks,budget)


def _name(user):
    return user.get('nama_lengkap') or user.get('username') or 'Siswa'


def _loader(user,enrollments):
    from app.repositories import student_dashboard_repo
    from app.services import student_service, engagement_service
    return load_snapshot(user['id'],enrollments,
        stats=student_dashboard_repo.ringkasan_siswa,
        schedules=student_service.jadwal_saya,attendance=student_service.rekap_absensi,
        grades=student_service.ringkasan_nilai,sync=engagement_service.sinkronisasi_notifikasi,
        unread=engagement_service.jumlah_notifikasi_belum_dibaca)


class StudentDashboardNavigator:
    """One workspace per visit. Exit it before legacy submenu/AI opens."""
    def __init__(self,*,load=_loader):
        self.load=load
        self.previous=None
        self.focus='katalog'

    async def choose(self,view,user,enrollments):
        snapshot=await view.busy('Memuat dashboard siswa...',self.load,user,enrollments)
        choices=[(k,l if k!='notifikasi' or snapshot.unread is None else
                  f'Notifikasi ({snapshot.unread} belum dibaca)' if snapshot.unread else l)
                 for k,l in MENU]
        action=await view.page('PUSAT AKTIVITAS BELAJAR',choices,
            lambda w,b:dashboard_pages(snapshot,w,b,self.previous),default=self.focus)
        self.previous=snapshot
        if action=='refresh':
            self.focus=getattr(view,'refresh_focus',None) or self.focus
        elif action not in (None,'logout'):
            self.focus=action
        return action

    def run(self,user,enrollments):
        return StudentWorkspace(_name(user)).run(lambda view:self.choose(view,user,enrollments))


def pilih_onboarding_siswa(user,enrollments):
    return StudentWorkspace(_name(user)).run(lambda view:view.page(
        'PENYELESAIAN PENDAFTARAN SISWA',
        [('refresh','Periksa status persetujuan akun'),('logout','Logout')],
        lambda w,b:onboarding_pages(enrollments,w,b),default='refresh'))


def tampilkan_status_akun(user,reason):
    async def show(view):
        await view.result('STATUS AKUN','Akun tidak dapat digunakan. '+str(reason),'error')
    StudentWorkspace(_name(user)).run(show)
