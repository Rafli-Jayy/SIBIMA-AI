"""UI-008 Tutor notifications, class announcements, and missed-session followup."""
from __future__ import annotations

from .tutor_workspace import run_tutor
from .tutor_academic import _controller, tgl
from .student_features import FeatureController, fields, column, table_renderer, metrics_pages, empty_pages, content_pages
from .student_notifications import notification_table,notification_pages,stamp
from .admin_confirmation import value
from .admin_workspace import line
from .auth_workspace import Field
from .jadwal_context import jam_jadwal

ANNOUNCEMENTS=table_renderer([column('Judul','judul',4),column('Program','nama_program',3),
    column('Penerima','jumlah_penerima',1),column('Berakhir',lambda r:stamp(r.get('expires_at')),3)])
PROGRAMS=table_renderer([column('Program','nama',4),column('Siswa aktif','jumlah_siswa',2)])
PENDING=table_renderer([column('Tanggal',lambda r:tgl(r.get('tanggal')),2),column('Program','nama_program',4),
    column('Status',lambda r:'Sesi belum selesai' if r.get('session_id') else 'Belum ada sesi',3),
    column('Waktu',jam_jadwal,2)],lambda r:'warning')
DURATIONS={'7_hari':'7 hari','pertemuan_berikut':'Setelah pertemuan berikutnya','tanggal':'Tanggal dan jam khusus (WIB)'}


def announcement_pages(item,w,b):
    return content_pages([('INFORMASI PENGUMUMAN',fields(item,[('Judul','judul'),('Program','nama_program'),
        ('Penerima','jumlah_penerima')])+[('Diterbitkan',stamp(item.get('created_at'))),
        ('Berakhir',stamp(item.get('expires_at')))])],[('ISI PENGUMUMAN',item.get('isi'))],w,b)


def notification_target(r):
    if r.get('sumber') in ('admin','tutor') or r.get('kategori')=='pengumuman':return None
    return {'schedule_pending':'tertunda','session':'absensi','schedule':'jadwal'}.get(r.get('related_type'))


class CommunicationController(FeatureController):
    def __init__(self,view,service,academic):
        super().__init__(view)
        self.service=service
        self.academic=academic

    async def command(self,fn,*args):
        """Existing services may return dict/int/None; None success is distinct from error."""
        try:return True,await self.view.busy('Memproses tindakan...',fn,*args)
        except (ValueError,PermissionError) as exc:
            await self.view.result('TINDAKAN BELUM BERHASIL',str(exc),'error')
        except Exception as exc:
            await self.view.result('HASIL BELUM DIPASTIKAN',
                'Periksa status terbaru sebelum mengulangi tindakan ('+type(exc).__name__+').','error')
        return False,None

    async def sync(self):
        try:await self.view.busy('Memperbarui pengingat...',self.service.sinkronisasi_notifikasi,'tutor');return True
        except Exception:return False

    async def notifications(self):
        sync_ok=await self.sync()
        focus='inbox'
        while True:
            count=await self.read(self.service.jumlah_notifikasi_belum_dibaca,'tutor')
            if count is None:return None
            def render(w,b):
                return metrics_pages([('BELUM DIBACA',str(count),'Kotak masuk')],w,b,
                    note='Arsip pribadi hanya memengaruhi akun ini.'+(' Pengingat belum dapat diperbarui.' if not sync_ok else ''))
            action=await self.view.page('PUSAT NOTIFIKASI',[
                ('inbox','Kotak Masuk'),('allread','Tandai Semua Dibaca'),('archive','Arsip Saya'),
                ('refresh','Muat ulang'),('back','Kembali')],render,default=focus)
            if action in (None,'back'):return None
            if action=='refresh':sync_ok=await self.sync();continue
            focus=action
            if action in ('inbox','archive'):
                result=await self.inbox(action=='archive')
                if result:return result
            elif action=='allread':
                if await self.confirm('TANDAI SEMUA DIBACA',[('KOTAK MASUK',[('Belum dibaca',str(count)),
                    ('Aksi','Tandai semua pesan aktif')])],label='Ya, tandai semua'):
                    ok,result=await self.command(self.service.tandai_semua_dibaca,'tutor')
                    if ok:await self.view.result('PESAN DITANDAI DIBACA',f'{result} pesan ditandai sudah dibaca.','success')

    async def inbox(self,archived):
        async def load():return await self.read(self.service.daftar_notifikasi_filter,'tutor',arsip=archived,limit=500)
        async def detail(r):return await self.notification_detail(r,archived)
        return await self.browse('ARSIP SAYA' if archived else 'KOTAK MASUK',load,notification_table(archived),detail,
            key='id',caption='Maks. 500 pesan · pilih detail',
            empty='Belum ada notifikasi yang diarsipkan.' if archived else 'Kotak masuk belum memiliki notifikasi.')

    async def notification_detail(self,r,archived):
        service=self.service.buka_notifikasi_arsip if archived else self.service.buka_notifikasi
        item=await self.read(service,'tutor',r['id'])
        if item is None:return None
        link=None if archived else notification_target(item)
        while True:
            actions=([('open','Buka menu terkait')] if link else [])+(
                [('archive','Arsipkan Notifikasi')] if not archived else [])+[('back','Kembali ke daftar')]
            action=await self.view.page('DETAIL NOTIFIKASI',actions,lambda w,b:notification_pages(item,w,b),default='back')
            if action=='open' and link:return link
            if action!='archive' or archived:return None
            if await self.confirm('ARSIPKAN NOTIFIKASI',[('ARSIP PRIBADI',[('Judul',value(item,'judul')),
                ('Dampak','Hanya dipindahkan dari kotak masuk akun ini.')])],label='Ya, arsipkan'):
                ok,_=await self.command(self.service.arsipkan_notifikasi_pribadi,'tutor',item['id'])
                if ok:await self.view.result('NOTIFIKASI DIARSIPKAN','Pesan dipindahkan ke Arsip Saya.','success')
                return None

    async def announcements(self):
        focus='buat'
        while True:
            active=await self.read(self.service.daftar_pengumuman_tutor,'aktif')
            if active is None:return
            archives=await self.read(self.service.daftar_pengumuman_tutor,'arsip')
            if archives is None:return
            action=await self.view.page('PENGUMUMAN KELAS',[
                ('buat','Buat Pengumuman Baru'),('aktif',f'Pengumuman Aktif ({len(active)})'),
                ('arsip',f'Arsip & Pengumuman Berakhir ({len(archives)})'),('refresh','Muat ulang'),('back','Kembali')],
                lambda w,b:metrics_pages([('AKTIF',str(len(active)),'Pengumuman kelas'),('ARSIP',str(len(archives)),'Sudah berakhir')],
                    w,b,note='Penerima: siswa aktif pada program yang diampu. Tanpa email broadcast.'),
                default=focus)
            if action in (None,'back'):return
            if action=='refresh':continue
            focus=action
            if action=='buat':await self.create_announcement()
            elif action in ('aktif','arsip'):await self.announcement_list(action)

    async def create_announcement(self):
        while True:
            rows=await self.read(self.service.daftar_program_pengumuman_tutor)
            if rows is None:return
            p=await self.pick('PILIH KELAS TUJUAN',rows,PROGRAMS,key='id',caption='Langkah 1/4 · kelas yang diampu',
                empty='Tidak ada kelas aktif yang dapat menerima pengumuman.')
            if p=='refresh':continue
            if not p:return
            break
        notice=''
        draft={'judul':'','isi':''}
        while True:
            ans=await self.view.form('TULIS PENGUMUMAN',[Field('judul','Judul (maks. 150 karakter)',draft['judul']),
                Field('isi','Isi pengumuman',draft['isi'])],subtitle=value(p,'nama'),step='2/4',notice=notice,
                hint='Ketik \\n untuk baris baru.',submit_label='Lanjutkan')
            if ans is None:return
            draft=ans
            text=ans['isi'].replace('\\n','\n')
            if not 1<=len(ans['judul'].strip())<=150:
                notice='Judul harus 1–150 karakter.';continue
            if not 1<=len(text.strip())<=10000:
                notice='Isi harus 1–10.000 karakter.';continue
            break
        durasi=await self.view.page('MASA BERLAKU',[(k,l) for k,l in DURATIONS.items()]+[('back','Kembali')],
            lambda w,b:[[line('Langkah 3/4 · pilih waktu berakhir otomatis.',w,'muted','center')]],default='7_hari')
        if durasi not in DURATIONS:return
        tanggal=None
        if durasi=='tanggal':
            date=await self.view.form('MASA BERLAKU',[Field('tanggal','Berakhir YYYY-MM-DD HH:MM')],
                subtitle=value(p,'nama'),step='3/4',hint='Waktu Indonesia Barat (WIB).')
            if date is None:return
            tanggal=date['tanggal']
        sections=[('TUJUAN PENGUMUMAN',[('Kelas',value(p,'nama')),('Siswa aktif',value(p,'jumlah_siswa')),
            ('Judul',ans['judul']),('Masa berlaku',DURATIONS[durasi]),('Waktu khusus',tanggal or '—')])]
        action=await self.view.page('KONFIRMASI PENGUMUMAN',[('confirm','Terbitkan Pengumuman'),('back','Batal')],
            lambda w,b:content_pages(sections,[('ISI PENGUMUMAN',text)],w,b),default='back')
        if action!='confirm':return
        ok,result=await self.command(self.service.buat_pengumuman_tutor,p['id'],ans['judul'],text,durasi,tanggal)
        if ok:
            await self.view.result('PENGUMUMAN DITERBITKAN',
                f"{result['jumlah_penerima']} penerima · Berakhir {stamp(result.get('expires_at'))}.",'success')

    async def announcement_list(self,status):
        async def load():return await self.read(self.service.daftar_pengumuman_tutor,status)
        async def detail(item):
            while True:
                actions=([('archive','Arsipkan Pengumuman')] if status=='aktif' else [])+[('back','Kembali ke daftar')]
                action=await self.view.page('DETAIL PENGUMUMAN',actions,lambda w,b:announcement_pages(item,w,b),default='back')
                if action!='archive' or status!='aktif':return None
                if not await self.confirm('KONFIRMASI ARSIP',[('PENGUMUMAN',[('Judul',value(item,'judul')),
                    ('Kelas',value(item,'nama_program')),('Dampak','Diarsipkan untuk semua penerima; tidak dapat dikembalikan.')])],
                    label='Ya, arsipkan pengumuman'):continue
                ok,_=await self.command(self.service.akhiri_pengumuman_tutor,item['batch_key'])
                if ok:await self.view.result('PENGUMUMAN DIARSIPKAN','Tidak tampil lagi di kotak masuk aktif siswa.','success')
                return None
        await self.browse('PENGUMUMAN AKTIF' if status=='aktif' else 'ARSIP PENGUMUMAN',load,ANNOUNCEMENTS,detail,
            key='batch_key',caption='Pengumuman kelas sendiri',empty='Belum ada pengumuman aktif.' if status=='aktif'
            else 'Belum ada pengumuman berakhir atau diarsipkan.')

    async def pending(self):
        focus=None
        while True:
            rows=await self.read(self.service.daftar_pertemuan_tertunda_tutor,200)
            if rows is None:return
            r=await self.pick('PERTEMUAN TERTUNDA',rows,PENDING,initial=focus,
                caption='Maks. 200 · jadwal lewat belum membuktikan kelas berlangsung',
                empty='Tidak ada pertemuan yang perlu dilaporkan.')
            if r=='refresh':continue
            if r is None:return
            focus=r['_ui_key']
            sections=[('JADWAL TERTUNDA',[('Program',value(r,'nama_program')),('Tanggal',tgl(r.get('tanggal'))),
                ('Jam',jam_jadwal(r)),('Status','Sesi belum selesai' if r.get('session_id') else 'Belum ada catatan sesi')])]
            if r.get('session_id'):
                action=await self.page('DETAIL PERTEMUAN TERTUNDA',[('manage','Kelola pertemuan'),('back','Kembali')],
                    sections,notice='Tutor harus memverifikasi laporan.')
                if action=='manage':await self.academic.manage_session(r['session_id'])
            elif await self.confirm('BUKA LAPORAN TERLAMBAT',sections,
                label='Buat catatan sesi terlambat',notice='Jadwal terlewat bukan bukti kelas sudah dilaksanakan.'):
                ok,sid=await self.command(self.service.buka_pertemuan_terlewat_tutor,r['schedule_id'],r['tanggal'])
                if ok:await self.academic.manage_session(sid)


def _run(method):
    from app.services import engagement_service
    async def flow(view):return await getattr(CommunicationController(view,engagement_service,_controller(view)),method)()
    return run_tutor(flow)

def notifikasi():return _run('notifications')
def pengumuman():return _run('announcements')
def tertunda():return _run('pending')
