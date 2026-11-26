"""UI-007B/C/D/F: student academic screens. Existing services remain authoritative."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re

from .student_features import (
    FeatureController, run_student, fields, column, table_renderer,
    metrics_pages, empty_pages, content_pages,
)
from .student_workspace import accessible, label
from .admin_confirmation import value, rupiah, wrap
from .admin_workspace import line, paginate_blocks
from .admin_academic import bar_row, add_band, stat_tile
from .auth_workspace import Field
from .jadwal_context import HARI, kondisi_jadwal_siswa, jadwal_rutin_terdekat, jam_jadwal, label_hari
from .proyeksi_pertemuan import proyeksi_jadwal, CATATAN_PROYEKSI

STATUS_ABSENSI = {'H':'Hadir','I':'Izin','S':'Sakit','A':'Alpa'}
RUNNING = {'menunggu_pembayaran','menunggu','aktif'}


def _nilai(v, digits=1):
    try:
        return '—' if v is None else f'{float(v):.{digits}f}'
    except (TypeError, ValueError):
        return str(v)


def _tanggal(v):
    return v.strftime('%d-%m-%Y') if hasattr(v,'strftime') else str(v or '—')


def _label_status_sesi(s):
    return {'batal':'Dibatalkan','perlu_laporan':'Menunggu laporan Tutor',
            'selesai':'Selesai','terlaksana':'Catatan lama (belum final)'}.get(s,'Status belum tersedia')


def _absen(r):
    return 'Dibatalkan' if r.get('status_pertemuan')=='batal' else STATUS_ABSENSI.get(r.get('status_absensi'),'Belum dicatat')


def _class_tone(r):
    return 'success' if accessible(r) else 'warning' if r.get('status') in RUNNING else 'muted'


def _academ_label(r):
    return label(dict(r,status=r.get('status_enrollment',r.get('status'))))


def _academic_allowed(r):
    return r.get('status_enrollment',r.get('status')) in ('aktif','selesai') and r.get('akses_terkunci') is False


CATALOG=table_renderer([column('Program','nama',4),column('Jenjang','jenjang',2),
    column('Biaya / bulan',lambda r:rupiah(r.get('harga_bulanan') or 0),2),
    column('Sisa kuota',lambda r:f"{r.get('sisa',0)}/{r.get('kuota',0)}",1)])
CLASSES=table_renderer([column('Program','nama_program',4),column('Status',label,3),
    column('Tutor','tutor',3)],_class_tone)
PROGRAMS=table_renderer([column('Program','nama_program',4),column('Status',_academ_label,3),
    column('Jenjang','jenjang',2)],lambda r:'success' if _academic_allowed(r) else 'warning')
SCHEDULE=table_renderer([column('Hari / jam',lambda r:label_hari(r.get('hari'))+' '+jam_jadwal(r),3),
    column('Program','nama_program',3),column('Tutor','nama_tutor',3),column('Ruang','nama_ruang',2)])
SESSIONS=table_renderer([column('Pertemuan',lambda r:f"#{r.get('pertemuan_ke') or '—'} · {_tanggal(r.get('tanggal'))}",2),
    column('Materi','topik',4),column('Status',lambda r:_label_status_sesi(r.get('status_pertemuan')),3)])
ATTENDANCE=table_renderer([column('Tanggal / ke-',lambda r:f"{_tanggal(r.get('tanggal'))} · #{r.get('pertemuan_ke') or '—'}",2),
    column('Status',_absen,2),column('Sesi',lambda r:_label_status_sesi(r.get('status_pertemuan')),3),
    column('Topik','topik',3)],lambda r:'success' if r.get('status_pertemuan')=='selesai' and r.get('status_absensi')=='H' else 'warning')
GRADES=table_renderer([column('Judul','judul',4),column('Nilai',lambda r:_nilai(r.get('nilai'),2),1),
    column('Jenis',lambda r:value(r,'jenis').upper(),1),column('Tanggal',lambda r:_tanggal(r.get('tanggal')),2),
    column('Tutor','nama_tutor',3)])
MATERIALS=table_renderer([column('Topik','topik',4),column('Pertemuan',lambda r:f"#{r.get('pertemuan_ke') or '—'}",1),
    column('Tanggal',lambda r:_tanggal(r.get('tanggal')),2),column('Tutor','nama_tutor',3)])


def catalog_sections(p):
    return [('PROGRAM BIMBEL',fields(p,[('Nama','nama'),('Kode','kode'),('Jenjang','jenjang')])+[
        ('Biaya / bulan',rupiah(p.get('harga_bulanan') or 0))]),
        ('KETERSEDIAAN',[('Sisa kuota',str(p.get('sisa',0))),('Kapasitas',value(p,'kuota'))]),
        ('DESKRIPSI',[('Tentang program',value(p,'deskripsi','Belum ada deskripsi.'))])]


def class_sections(r):
    return [('IDENTITAS KELAS',fields(r,[('Program','nama_program'),('Kode','kode'),('Jenjang','jenjang'),
                ('Tutor terjadwal','tutor')])+[('Biaya / bulan',rupiah(r.get('harga_bulanan')))]),
            ('PENDAFTARAN',[('Status',label(r)),('Terdaftar',_tanggal(r.get('created_at'))),
                            ('Diproses',_tanggal(r.get('processed_at'))),
                            ('Keterangan',value(r,'alasan_tolak'))])]


def class_notice(r):
    if r.get('status')=='aktif' and r.get('akses_terkunci') is True:
        return 'Akses akademik terkunci H+3. Buka Tagihan & Pembayaran.'
    if r.get('status')=='aktif' and not accessible(r):
        return 'Status akses belum tersedia. Muat ulang kelas.'
    return {'menunggu_pembayaran':'Selesaikan pembayaran pertama di Tagihan & Pembayaran.',
            'menunggu':'Menunggu keputusan Admin.',
            'ditolak':'Pendaftaran ditolak. Daftar ulang melalui katalog jika tersedia.',
            'batal':'Pendaftaran dibatalkan. Riwayat tetap tersimpan.',
            'selesai':'Pendaftaran selesai. Arsip akademik tersedia melalui menu terkait.'}.get(r.get('status'),'')


def schedule_sections(r, sessions, enrollments):
    sections=[('JADWAL RUTIN',fields(r,[('Program','nama_program'),('Tutor','nama_tutor'),('Ruang','nama_ruang')])+[
        ('Hari',label_hari(r.get('hari'))),('Jam',jam_jadwal(r))])]
    projected=proyeksi_jadwal(r,sessions)
    if projected:
        prior,nxt=projected['sebelumnya'],projected['berikutnya']
        since=[e.get('created_at') for e in enrollments
               if e.get('program_id')==r.get('program_id') and accessible(e)]
        days=[x.date() if isinstance(x,datetime) else x for x in since if isinstance(x,date)]
        old_status='Sebelum pendaftaran ini (tidak dihitung)' if days and prior['tanggal']<max(days) else prior['status']
        sections += [('PERKIRAAN SLOT SEBELUMNYA',[('Tanggal',_tanggal(prior['tanggal'])),('Status',old_status)]),
                     ('PERKIRAAN SLOT BERIKUTNYA',[('Tanggal',_tanggal(nxt['tanggal'])),('Status',nxt['status'])])]
    sections.append(('KETERANGAN',[('Perkiraan',CATATAN_PROYEKSI)]))
    return sections


def session_sections(r):
    return [('IDENTITAS PERTEMUAN',[('Pertemuan',str(r.get('pertemuan_ke') or '—')),
             ('Tanggal',_tanggal(r.get('tanggal'))),('Jam',jam_jadwal(r)),
             ('Status',_label_status_sesi(r.get('status_pertemuan'))),('Kehadiran saya',_absen(r))]+
             fields(r,[('Tutor','nama_tutor'),('Ruang','nama_ruang')])),
            ('CATATAN PEMBELAJARAN',[('Topik',value(r,'topik','Belum dilaporkan tutor')),
             ('Ringkasan',value(r,'ringkasan','Belum dilaporkan tutor'))])]


def attendance_pages(summary,w,b):
    if not summary or not summary.get('total_pertemuan'):
        return empty_pages('Belum ada rekap absensi sesi selesai.','Absensi',width=w,budget=b)
    metrics=[('PERTEMUAN',str(summary.get('total_pertemuan',0)),'Sesi selesai'),
             ('HADIR',str(summary.get('hadir',0)),'Kehadiran tercatat'),
             ('PERSENTASE',_nilai(summary.get('persen_hadir'))+'%' if summary.get('persen_hadir') is not None else '—','Hadir dari sesi selesai')]
    def composition(cw):
        return [bar_row(t,summary.get(k),summary.get('total_pertemuan'),cw,tone=tone)
                for t,k,tone in [('Hadir','hadir','success'),('Izin','izin','number'),
                                 ('Sakit','sakit','warning'),('Alpa','alpa','error')]]
    return metrics_pages(metrics,w,b,note='Rekap hanya menghitung sesi selesai. Absensi dalam proses belum final.',
                         extra=[('KOMPOSISI KEHADIRAN',composition)])


def grade_pages(summary,w,b):
    if not summary or all(summary.get(k) is None for k in ('tugas','kuis','uts','uas','nilai_akhir')):
        return empty_pages('Belum ada nilai yang diinput Tutor.','Nilai akademik',width=w,budget=b)
    def weights(cw):
        if cw<28:
            return [line(f"{k.upper()}  {_nilai(summary.get(k),2)} · {summary.get('bobot_'+k,0)}%",cw,'title')
                for k in ('tugas','kuis','uts','uas')]
        left=cw//2
        middle=(cw-left)//2
        right=cw-left-middle
        rows=[[ *line('Komponen',left,'muted'),*line('Nilai',middle,'muted','right'),
               *line('Bobot',right,'muted','right')]]
        for k in ('tugas','kuis','uts','uas'):
            rows.append([*line(k.upper(),left,'title'),*line(_nilai(summary.get(k),2),middle,'title','right'),
                *line(str(summary.get('bobot_'+k,0))+'%',right,'muted','right')])
        return rows
    blocks=[]
    add_band(blocks,[('NILAI AKHIR',lambda cw:stat_tile(_nilai(summary.get('nilai_akhir'),2),'Berbobot',cw)),
                     ('KOMPONEN NILAI',weights)],w,b,weights=[1,2])
    for t in wrap('— = belum diinput. Nilai akhir memakai komponen yang tersedia sesuai bobot program.',max(1,w-2)):
        blocks.append([line(t,w,'muted','center')])
    return paginate_blocks(blocks,b)


class AcademicController(FeatureController):
    def __init__(self,view,service):
        super().__init__(view)
        self.service=service

    async def data(self,fn,*args,**kwargs):
        return await self.read(fn,*args,service=True,**kwargs)

    async def catalog(self,user,programs,enrollments,register):
        async def load():
            all_programs=await self.read(programs)
            if all_programs is None:return None
            registrations=await self.read(enrollments,user['id'])
            if registrations is None:return None
            existing={x['program_id'] for x in registrations if x['status'] in RUNNING}
            return [p for p in all_programs if p['id'] not in existing]
        async def detail(p):
            sections=catalog_sections(p)
            action=await self.page('DETAIL PROGRAM',[('register','Daftar program'),('back','Kembali ke katalog')],
                                    sections,default='back')
            if action!='register':return None
            paid=(p.get('harga_bulanan') or 0)>0
            notice='Invoice otomatis dibuat; pendaftaran menunggu pembayaran.' if paid else 'Program gratis; menunggu persetujuan Admin.'
            if await self.confirm('KONFIRMASI PENDAFTARAN',sections[:2],notice=notice,label='Ya, daftar program'):
                ok=await self.mutate(register,student_id=user['id'],program_id=p['id'],service=True)
                if ok:return 'registered'
            return None
        return await self.browse('KATALOG PROGRAM',load,CATALOG,detail,key='id',
            caption='Program buka · pilih detail',empty='Tidak ada program baru tersedia. Periksa Kelas Saya.')

    async def classes(self):
        focus='current'
        while True:
            rows=await self.data(self.service.kelas_saya)
            if rows is None:return
            current=[x for x in rows if x.get('status') in RUNNING]
            old=[x for x in rows if x.get('status') not in RUNNING]
            metrics=[('AKTIF',str(sum(accessible(x) for x in current)),'Dapat diakses'),
                     ('MENUNGGU',str(sum(x.get('status') in ('menunggu','menunggu_pembayaran') for x in current)),'Pembayaran / Admin'),
                     ('TERKUNCI',str(sum(x.get('akses_terkunci') is True and x.get('status')=='aktif' for x in current)),'Tagihan H+3')]
            action=await self.view.page('KELAS SAYA',
                [('current',f'Kelas berjalan ({len(current)})'),('history',f'Riwayat pendaftaran ({len(old)})'),
                 ('refresh','Muat ulang'),('back','Kembali ke dashboard')],
                lambda w,b:metrics_pages(metrics,w,b,note='Pilih kelas untuk melihat rincian.') if rows else
                    empty_pages('Belum memiliki kelas. Daftar lewat Katalog Program.','Kelas saya',width=w,budget=b),
                default=focus)
            if action in (None,'back'):return
            if action=='refresh':continue
            focus=action
            async def load():
                data=await self.data(self.service.kelas_saya)
                return None if data is None else [x for x in data if (x.get('status') in RUNNING)==(action=='current')]
            await self.browse('KELAS BERJALAN' if action=='current' else 'RIWAYAT PENDAFTARAN',load,CLASSES,self.class_detail,
                key='enrollment_id',empty='Belum ada kelas berjalan.' if action=='current' else 'Belum ada riwayat pendaftaran.')

    async def class_detail(self,r):
        while True:
            fresh=await self.data(self.service.kelas_saya)
            if fresh is None:return
            item=next((x for x in fresh if x.get('enrollment_id')==r.get('enrollment_id')),None)
            if item is None:
                await self.view.result('KELAS TIDAK TERSEDIA','Daftar kelas telah berubah.','error');return
            sections=class_sections(item)
            choices=[]
            schedules=None
            if accessible(item):
                schedules=await self.data(self.service.jadwal_saya,program_id=item['program_id'])
                if schedules is not None:
                    choices=[('schedule',f'Jadwal rutin ({len(schedules)})'),('sessions','Riwayat pertemuan & materi')]
                    sections.append(('AKTIVITAS BELAJAR',[('Jadwal rutin',str(len(schedules))+' slot' if schedules else 'Belum dijadwalkan'),
                                                         ('Pertemuan','Lihat laporan Tutor')]))
            action=await self.page('DETAIL KELAS',choices+[('back','Kembali ke daftar')],sections,notice=class_notice(item))
            if action=='schedule' and accessible(item):
                await self.schedule_list('JADWAL KELAS',item['program_id'])
            elif action=='sessions' and accessible(item):
                await self.sessions(item)
            else:return

    async def sessions(self,p):
        async def load():return await self.data(self.service.pertemuan_saya,p['program_id'])
        async def detail(r):
            sections=session_sections(r)
            await self.view.page('DETAIL PERTEMUAN',[('back','Kembali')],
                lambda w,b:content_pages([sections[0]],[
                    ('TOPIK',r.get('topik') or 'Belum dilaporkan Tutor'),
                    ('RINGKASAN',r.get('ringkasan') or 'Belum dilaporkan Tutor')],w,b))
        await self.browse('PERTEMUAN TERCATAT',load,SESSIONS,detail,key='session_id',
            caption='Laporan Tutor · maks. 50 terbaru',empty='Belum ada laporan pertemuan dari Tutor.')

    async def program(self,*,active_only=False):
        while True:
            rows=await self.data(self.service.kelas_saya if active_only else self.service.program_akademik)
            if rows is None:return None
            if active_only:
                rows=[dict(x,status_enrollment=x.get('status')) for x in rows if x.get('status')=='aktif']
            chosen=await self.pick('PILIH PROGRAM AKADEMIK',rows,PROGRAMS,key='enrollment_id',
                empty='Belum ada program yang dapat dipilih. Periksa Kelas Saya.',
                caption='Jadwal kelas aktif' if active_only else 'Program aktif / selesai')
            if chosen=='refresh':continue
            if not chosen:return None
            if not _academic_allowed(chosen):
                await self.view.result('AKSES KELAS TERBATAS',
                    'Tagihan H+3 terkunci. Buka Tagihan & Pembayaran.' if chosen.get('akses_terkunci') is True else 'Status akses belum tersedia. Muat ulang.','info')
                continue
            return chosen

    async def schedule(self):
        focus='today'
        while True:
            enroll=await self.data(self.service.kelas_saya)
            if enroll is None:return
            rows=await self.data(self.service.jadwal_saya)
            if rows is None:return
            active=[r for r in enroll if accessible(r)]
            active_ids={r['program_id'] for r in active}
            rows=[r for r in rows if r.get('program_id') in active_ids]
            day=HARI[date.today().weekday()]
            today=[r for r in rows if r.get('hari')==day]
            missing=[r for r in active if r.get('program_id') not in {s.get('program_id') for s in rows}]
            def render(w,b):
                if not rows:
                    return empty_pages(self.schedule_empty(kondisi_jadwal_siswa(enroll,rows)), 'Jadwal rutin',width=w,budget=b)
                return metrics_pages([('HARI INI',str(len(today)),'Slot rutin'),('MINGGUAN',str(len(rows)),'Slot rutin'),
                    ('BELUM ADA JADWAL',str(len(missing)),'Kelas aktif')],w,b,
                    note='Jadwal rutin bukan bukti pertemuan terlaksana.')
            action=await self.view.page('JADWAL SAYA',
                [('today','Jadwal hari ini'),('week','Jadwal mingguan'),('program','Filter berdasarkan program'),
                 ('refresh','Muat ulang'),('back','Kembali ke dashboard')],render,default=focus)
            if action in (None,'back'):return
            if action=='refresh':continue
            focus=action
            if action=='program':
                p=await self.program(active_only=True)
                if p:await self.schedule_list('JADWAL PROGRAM',p['program_id'])
            elif action in ('today','week'):
                await self.schedule_list('JADWAL HARI INI' if action=='today' else 'JADWAL MINGGUAN',today_only=action=='today')

    @staticmethod
    def schedule_empty(kondisi):
        return {'belum_ada_kelas':'Belum ada kelas aktif. Buka Katalog Program.',
                'terkunci_tagihan':'Akses kelas terkunci H+3. Buka Tagihan & Pembayaran.',
                'belum_dijadwalkan':'Kelas aktif belum memiliki jadwal rutin. Hubungi Admin.',
                'tidak_ada_hari_ini':'Tidak ada jadwal rutin hari ini.'}.get(kondisi,'Belum ada jadwal rutin.')

    async def schedule_list(self,title,program_id=None,today_only=False):
        focus=None
        while True:
            enroll=await self.data(self.service.kelas_saya)
            if enroll is None:return
            if program_id is not None:
                enroll=[x for x in enroll if x.get('program_id')==program_id]
            rows=await self.data(self.service.jadwal_saya,program_id=program_id)
            if rows is None:return
            active={x['program_id'] for x in enroll if accessible(x)}
            rows=[x for x in rows if x.get('program_id') in active]
            day=HARI[date.today().weekday()] if today_only else None
            visible=[x for x in rows if day is None or x.get('hari')==day]
            message=self.schedule_empty(kondisi_jadwal_siswa(enroll,rows,day))
            nxt=jadwal_rutin_terdekat(rows) if not visible and rows else None
            if nxt:
                dt,item=nxt
                # Keep the empty card concise, but allow a full next-slot detail.
                action=await self.page(title,[('next','Lihat jadwal mingguan'),('refresh','Muat ulang'),('back','Kembali')],
                    [('HARI INI',[('Status',message)]),
                     ('JADWAL BERIKUTNYA (PERKIRAAN)',[('Tanggal',_tanggal(dt)),('Program',value(item,'nama_program')),
                       ('Jam',jam_jadwal(item)),('Tutor',value(item,'nama_tutor'))])],
                    notice='Perkiraan jadwal rutin; bukan sesi yang terkonfirmasi.')
                if action=='next':
                    await self.schedule_list('JADWAL MINGGUAN',program_id)
                    continue
                if action=='refresh':continue
                return
            missing=sum(x.get('program_id') not in {s.get('program_id') for s in rows}
                        for x in enroll if accessible(x))
            caption='Jadwal rutin · pilih detail'
            if missing:caption+=f' · {missing} kelas belum dijadwalkan'
            r=await self.pick(title,visible,SCHEDULE,caption=caption,empty=message,initial=focus,key='schedule_id')
            if r=='refresh':continue
            if r is None:return
            focus=r['_ui_key']
            # Query pertemuan only for schedule returned through the access-checked service.
            try:
                ok,sessions=await self.view.busy('Memuat laporan Tutor...',self.service.pertemuan_saya,r['program_id'])
                if not ok:sessions=None
            except Exception:sessions=None
            await self.details('DETAIL JADWAL',schedule_sections(r,sessions,enroll))

    async def attendance(self):
        p=await self.program()
        if not p:return
        while True:
            summaries=await self.data(self.service.rekap_absensi,p['program_id'])
            if summaries is None:return
            summary=next((x for x in summaries if x.get('enrollment_id')==p.get('enrollment_id')),None)
            action=await self.view.page('ABSENSI · '+p['nama_program'],[
                ('history','Riwayat per pertemuan'),('refresh','Muat ulang'),('back','Kembali')],
                lambda w,b:attendance_pages(summary,w,b))
            if action in (None,'back'):return
            if action=='refresh':continue
            async def load():return await self.data(self.service.riwayat_absensi,p['program_id'])
            async def detail(r):
                await self.details('DETAIL ABSENSI',[('PER PERTEMUAN',[('Tanggal',_tanggal(r.get('tanggal'))),
                    ('Pertemuan',str(r.get('pertemuan_ke') or '—')),('Kehadiran',_absen(r)),
                    ('Status sesi',_label_status_sesi(r.get('status_pertemuan')))]),
                    ('CATATAN',fields(r,[('Topik','topik'),('Keterangan','keterangan')]))])
            await self.browse('RIWAYAT ABSENSI',load,ATTENDANCE,detail,empty='Belum ada absensi yang dicatat Tutor.',
                caption='Sesi dalam proses belum final')

    async def grades(self):
        p=await self.program()
        if not p:return
        while True:
            summaries=await self.data(self.service.ringkasan_nilai,p['program_id'])
            if summaries is None:return
            summary=next((x for x in summaries if x.get('enrollment_id')==p.get('enrollment_id')),None)
            action=await self.view.page('NILAI & RAPOR · '+p['nama_program'],[
                ('detail','Rincian nilai'),('txt','Cetak rapor TXT'),('refresh','Muat ulang'),('back','Kembali')],
                lambda w,b:grade_pages(summary,w,b))
            if action in (None,'back'):return
            if action=='refresh':continue
            async def load():return await self.data(self.service.detail_nilai,p['program_id'])
            if action=='detail':
                async def detail(r):
                    await self.details('DETAIL NILAI',[('PENILAIAN',fields(r,[('Judul','judul'),('Jenis','jenis'),('Tutor','nama_tutor')])+[
                        ('Tanggal',_tanggal(r.get('tanggal'))),('Nilai',_nilai(r.get('nilai'),2))])])
                await self.browse('RINCIAN NILAI',load,GRADES,detail,key='grade_id',empty='Belum ada rincian nilai.')
            elif action=='txt':
                if not summary:
                    await self.view.result('RAPOR BELUM TERSEDIA','Ringkasan nilai tidak ditemukan.');continue
                if not await self.confirm('CETAK RAPOR TXT',[('RAPOR',[('Program',p['nama_program']),('Format','TXT'),('Lokasi','Folder rapor')])],label='Ya, cetak'):
                    continue
                # Fetch again after confirmation; do not export stale data if the enrollment changed.
                summaries=await self.data(self.service.ringkasan_nilai,p['program_id'])
                if summaries is None:continue
                summary=next((x for x in summaries if x.get('enrollment_id')==p.get('enrollment_id')),None)
                if summary is None:
                    await self.view.result('RAPOR BELUM TERSEDIA','Akses atau pendaftaran berubah.');continue
                grades=await load()
                if grades is None:continue
                profile=await self.data(self.service.profil_saya)
                if profile is None:continue
                try:
                    path=await self.view.busy('Membuat rapor TXT...',_save_rapor,profile,summary,grades,p['program_id'])
                    await self.view.result('RAPOR BERHASIL DICETAK',f'Rapor tersimpan: {path}','success')
                except OSError as exc:
                    await self.view.result('CETAK RAPOR GAGAL',f'File tidak dapat dibuat ({type(exc).__name__}).','error')

    async def materials(self):
        p=await self.program()
        if not p:return
        async def load():return await self.data(self.service.catatan_materi,p['program_id'])
        async def detail(r):
            meta=[('PERTEMUAN',fields(r,[('Tutor','nama_tutor'),('Program','nama_program')])+[
                ('Tanggal',_tanggal(r.get('tanggal'))),('Pertemuan',str(r.get('pertemuan_ke') or '—'))])]
            await self.view.page('DETAIL CATATAN MATERI',[('back','Kembali')],
                lambda w,b:content_pages(meta,[('TOPIK',r.get('topik')),('RINGKASAN MATERI',r.get('ringkasan'))],w,b))
        await self.browse('CATATAN MATERI',load,MATERIALS,detail,key='session_id',empty='Belum ada catatan materi dari Tutor.')

    async def profile(self):
        while True:
            p=await self.data(self.service.profil_saya)
            if p is None:return
            sections=[('IDENTITAS AKUN',fields(p,[('Nama lengkap','nama_lengkap'),('Username','username'),('Email','email'),('NIS','nis'),('Status akun','status')])),
                      ('PROFIL SISWA',fields(p,[('Jenjang','jenjang'),('Sekolah','sekolah'),('Nomor HP','no_hp'),('Nama wali','nama_wali')]))]
            action=await self.page('PROFIL SAYA',[('edit','Lengkapi / ubah profil'),('password','Ganti password'),('refresh','Muat ulang'),('back','Kembali')],sections)
            if action in (None,'back'):return
            if action=='edit':
                data={}
                stages=[[('jenjang','Jenjang'),('sekolah','Sekolah')],[('no_hp','Nomor HP (opsional)'),('nama_wali','Nama wali')]]
                for i,stage in enumerate(stages,1):
                    ans=await self.view.form('UBAH PROFIL',[Field(k,l,str(p.get(k) or '')) for k,l in stage],step=f'{i}/2',
                        hint='Ubah data profil; identitas akun tetap.',submit_label='Lanjutkan')
                    if ans is None:break
                    data.update(ans)
                if len(data)==4 and await self.confirm('SIMPAN PROFIL',[('PERUBAHAN',[(l,data[k]) for stage in stages for k,l in stage])],label='Ya, simpan'):
                    await self.mutate(self.service.ubah_profil,data,service=True)
            elif action=='password':
                # Separate masked fields; never echo passwords in a review/result page.
                old=await self.view.form('GANTI PASSWORD',[Field('old','Password saat ini',secret=True)],step='1/2')
                if old is None:continue
                notice=''
                while True:
                    new=await self.view.form('GANTI PASSWORD',[Field('new','Password baru',secret=True),Field('again','Ulangi password baru',secret=True)],
                        step='2/2',notice=notice,submit_label='Ganti password')
                    if new is None:break
                    if new['new']!=new['again']:
                        notice='Konfirmasi password baru tidak cocok.';continue
                    await self.mutate(self.service.ganti_password,old['old'],new['new'],service=True)
                    break


def _save_rapor(profile,summary,grades,program_id):
    report_dir=Path('rapor')
    report_dir.mkdir(parents=True,exist_ok=True)
    nis_safe=re.sub(r'[^A-Za-z0-9_-]','_',str(profile.get('nis') or profile.get('id')))
    prog_safe=re.sub(r'[^A-Za-z0-9_-]','_',str(program_id))
    path=report_dir/f"rapor_{nis_safe}_program_{prog_safe}_{datetime.now():%Y%m%d_%H%M%S}.txt"
    path.write_text(_build_rapor_text(profile,summary,grades),encoding='utf-8')
    return path
def _build_rapor_text(profile, summary, grades):
    now = datetime.now().strftime("%d-%m-%Y %H:%M")
    lines = [
        "SIBIMA - RAPOR AKADEMIK SISWA",
        "=" * 56,
        f"Nama       : {profile.get('nama_lengkap') or '-'}",
        f"NIS        : {profile.get('nis') or '-'}",
        f"Username   : {profile.get('username') or '-'}",
        f"Program    : {summary.get('nama_program') or '-'} ({summary.get('jenjang') or '-'})",
        f"Status     : {str(summary.get('status_enrollment') or '-').upper()}",
        f"Dicetak    : {now}",
        "",
        "RINGKASAN NILAI",
        "-" * 56,
        f"Tugas : {_nilai(summary.get('tugas'), 2)} (bobot {summary.get('bobot_tugas', 0)}%)",
        f"Kuis  : {_nilai(summary.get('kuis'), 2)} (bobot {summary.get('bobot_kuis', 0)}%)",
        f"UTS   : {_nilai(summary.get('uts'), 2)} (bobot {summary.get('bobot_uts', 0)}%)",
        f"UAS   : {_nilai(summary.get('uas'), 2)} (bobot {summary.get('bobot_uas', 0)}%)",
        f"NILAI AKHIR BERBOBOT: {_nilai(summary.get('nilai_akhir'), 2)}",
        "",
        "RINCIAN NILAI",
        "-" * 56,
        "Tanggal | Jenis | Judul | Nilai | Tutor",
    ]
    if grades:
        for g in grades:
            lines.append(f"{_tanggal(g.get('tanggal'))} | {g.get('jenis', '-').upper()} | {g.get('judul') or '-'} | {_nilai(g.get('nilai'), 2)} | {g.get('nama_tutor') or '-'}")
    else:
        lines.append("Belum ada rincian nilai yang diinput.")
    lines += ["", "Dokumen ini dibuat oleh SIBIMA berdasarkan data akademik yang tersimpan."]
    return "\n".join(lines) + "\n"



def _run(method):
    from app.services import student_service
    async def flow(view):
        return await getattr(AcademicController(view,student_service),method)()
    return run_student(flow)


def menu_katalog(pengguna):
    from app.repositories import program_repo, enrollment_repo
    from app.services import enrollment_service, student_service
    async def flow(view):
        return await AcademicController(view,student_service).catalog(
            pengguna,program_repo.daftar_program_buka_dengan_kuota,enrollment_repo.enrollment_siswa,
            enrollment_service.daftar_program)
    return run_student(flow,pengguna)


def menu_kelas_saya():return _run('classes')
def menu_jadwal_saya():return _run('schedule')
def menu_absensi_siswa():return _run('attendance')
def menu_nilai_rapor():return _run('grades')
def menu_catatan_materi():return _run('materials')
def menu_profil_siswa():return _run('profile')


def pilih_data_paginasi(prompt,rows,labeler,value_key,*,page_size=8):
    """Compatibility for callers of the previous student selection helper."""
    async def flow(view):
        c=FeatureController(view)
        while True:
            row=await c.pick(prompt,rows,table_renderer([column('Data',labeler,1)]),key=value_key)
            if row=='refresh':continue
            return row[value_key] if row else None
    return run_student(flow)


def tampilkan_katalog_paginasi(programs):
    """Read-only compatibility view; catalog itself uses one selectable table."""
    async def flow(view):
        c=FeatureController(view)
        async def load():return programs
        async def detail(p):await c.details('DETAIL PROGRAM',catalog_sections(p))
        return await c.browse('KATALOG PROGRAM',load,CATALOG,detail,key='id')
    return run_student(flow)


def menu_tanya_ai_info():
    """Unused legacy placeholder; live AI remains routed through ai_service."""
    from app.ui.console import bersihkan_layar,console
    from rich.panel import Panel
    bersihkan_layar()
    console.print(Panel('Integrasi Gemini belum diaktifkan pada tahap ini.\n'
                       'Menu akan tersedia setelah konfigurasi API, pengelolaan kunci rahasia, batas penggunaan, dan penanganan error diselesaikan.',
                       border_style='yellow',title='FITUR TAHAP BERIKUTNYA',padding=(1,3),expand=True))
    try:input('\nTekan Enter untuk kembali...')
    except (EOFError,KeyboardInterrupt):pass
