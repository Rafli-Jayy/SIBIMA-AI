"""UI-007F: inbox and personal archive for students, preserving N2 semantics."""
from __future__ import annotations

from .student_features import FeatureController,run_student,fields,column,table_renderer,metrics_pages,content_pages
from .admin_confirmation import value
from .admin_workspace import line


def source(r):
    if r.get('sumber') in ('admin','tutor'):
        return r['sumber'].capitalize()+': '+str(r.get('nama_pembuat') or 'Tidak tersedia')
    return 'Sistem SIBIMA'


def stamp(v):
    return v.strftime('%d-%m-%Y %H:%M WIB') if hasattr(v,'strftime') else str(v or '—')


def notification_status(r):
    return 'Dibaca' if r.get('sudah_dibaca') else 'Baru'


def notification_table(archived=False):
    return table_renderer([column('Judul','judul',5),
        column('Status',lambda r:'Arsip' if archived else notification_status(r),1),
        column('Sumber',source,3),column('Tanggal',lambda r:stamp(r.get('created_at')),3)],
        lambda r:'muted' if archived or r.get('sudah_dibaca') else 'success')


def notification_sections(r):
    identity=[('Sumber',source(r)),('Kategori',value(r,'kategori','umum')),
              ('Diterbitkan',stamp(r.get('created_at')))]
    if r.get('sumber')=='sistem' and r.get('nama_pelaku'):
        identity.append(('Tindakan oleh',value(r,'nama_pelaku')))
    if r.get('nama_program'):
        identity.append(('Kelas',value(r,'nama_program')))
    if r.get('expires_at'):
        identity.append(('Berlaku sampai',stamp(r['expires_at'])))
    return [('PESAN',[('Judul',value(r,'judul','Tanpa judul')),('Isi',value(r,'isi','Tidak ada isi'))]),
            ('INFORMASI',identity)]


def notification_pages(r,w,b):
    sections=notification_sections(r)
    identity=sections[1][1]+[('Judul',value(r,'judul','Tanpa judul'))]
    return content_pages([('INFORMASI PESAN',identity)],
        [('ISI PESAN',r.get('isi') or 'Tidak ada isi')],w,b)


def target(r):
    if r.get('sumber') in ('admin','tutor') or r.get('kategori')=='pengumuman':
        return None
    kind=r.get('related_type')
    if kind in ('grade','session','schedule'):
        return {'grade':'nilai','session':'absensi','schedule':'jadwal'}[kind]
    return {'tagihan':'pembayaran','pendaftaran':'pendaftaran'}.get(r.get('kategori'))


class NotificationController(FeatureController):
    def __init__(self,view,service):
        super().__init__(view)
        self.service=service

    async def sync(self):
        try:
            await self.view.busy('Memperbarui pengingat...',self.service.sinkronisasi_notifikasi,'siswa')
            return True
        except Exception:
            return False

    async def run(self):
        sync_ok=await self.sync()
        focus='inbox'
        while True:
            count=await self.read(self.service.jumlah_notifikasi_belum_dibaca,'siswa')
            if count is None:return
            def render(w,b):
                metrics=[('BELUM DIBACA',str(count),'Kotak masuk')]
                note='Arsip pribadi tidak mengubah pengumuman untuk pengguna lain.'
                if not sync_ok:note+=' Pengingat belum dapat diperbarui.'
                return metrics_pages(metrics,w,b,note=note)
            action=await self.view.page('PUSAT NOTIFIKASI',[('inbox','Kotak Masuk'),
                ('allread','Tandai Semua Dibaca'),('archive','Arsip Saya'),('refresh','Muat ulang'),('back','Kembali')],
                render,default=focus)
            if action in (None,'back'):return
            if action=='refresh':
                sync_ok=await self.sync();continue
            focus=action
            if action in ('inbox','archive'):
                result=await self.messages(action=='archive')
                if result:return result
            elif action=='allread':
                if await self.confirm('TANDAI SEMUA DIBACA',
                        [('KOTAK MASUK',[('Belum dibaca',str(count)),('Tindakan','Tandai seluruh pesan aktif sebagai dibaca')])],
                        label='Ya, tandai semua'):
                    result=await self.mutate(self.service.tandai_semua_dibaca,'siswa')
                    if result is not None:
                        await self.view.result('PESAN DITANDAI DIBACA',f'{result} pesan ditandai sudah dibaca.','success')

    async def messages(self,archived):
        async def load():
            return await self.read(self.service.daftar_notifikasi_filter,'siswa',arsip=archived,limit=500)
        async def detail(r):
            return await self.detail(r,archived)
        return await self.browse('ARSIP SAYA' if archived else 'KOTAK MASUK',load,notification_table(archived),detail,
            key='id',caption='Maks. 500 pesan · pilih detail',
            empty='Belum ada notifikasi yang diarsipkan.' if archived else 'Belum ada notifikasi di kotak masuk.')

    async def detail(self,r,archived):
        fn=self.service.buka_notifikasi_arsip if archived else self.service.buka_notifikasi
        item=await self.read(fn,'siswa',r['id'])
        if item is None:return None
        link=None if archived else target(item)
        while True:
            choices=[]
            if link:choices.append(('open','Buka menu terkait'))
            if not archived:choices.append(('archive','Arsipkan Notifikasi'))
            choices.append(('back','Kembali ke daftar'))
            action=await self.view.page('DETAIL NOTIFIKASI',choices,lambda w,b:notification_pages(item,w,b),default='back')
            if action=='open' and link:return link
            if action!='archive' or archived:return None
            if await self.confirm('ARSIPKAN NOTIFIKASI',
                [('ARSIP PRIBADI',[('Judul',value(item,'judul')),('Dampak','Pindahkan ke Arsip Saya, hanya akun ini.')])],
                label='Ya, arsipkan'):
                # Existing archive endpoint returns None on successful completion;
                # distinguish that from an exception without inferring success.
                try:
                    await self.view.busy('Mengarsipkan...',self.service.arsipkan_notifikasi_pribadi,'siswa',item['id'])
                except Exception:
                    await self.view.result('ARSIP BELUM DIPASTIKAN','Periksa kotak masuk dan Arsip Saya.','error')
                    return None
                await self.view.result('NOTIFIKASI DIARSIPKAN','Pesan dipindahkan ke Arsip Saya.','success')
                return None


def jalankan_siswa():
    from app.services import engagement_service
    async def flow(view):return await NotificationController(view,engagement_service).run()
    return run_student(flow)
