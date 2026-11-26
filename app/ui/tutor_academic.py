"""UI-008 Tutor academic flow, keeping the existing service boundary."""
from __future__ import annotations

from datetime import date
from collections import Counter

from .tutor_workspace import run_tutor,session_label,session_tone
from .student_features import (
    FeatureController,fields,column,table_renderer,metrics_pages,empty_pages,content_pages,
)
from .admin_confirmation import value,details_pages,wrap
from .admin_workspace import line,clip,paginate_blocks
from .admin_academic import add_panel
from .auth_workspace import Field
from .jadwal_context import HARI,jam_jadwal,label_hari,jadwal_rutin_terdekat
from .proyeksi_pertemuan import proyeksi_jadwal,CATATAN_PROYEKSI

ABSEN={'H':'Hadir','I':'Izin','S':'Sakit','A':'Alpa'}
JENIS={'tugas':'Tugas','kuis':'Kuis (nilai manual)','uts':'UTS','uas':'UAS'}
CLOSED={'batal','selesai'}


def tgl(v):return v.strftime('%d-%m-%Y') if hasattr(v,'strftime') else str(v or '—')

def score(v):
    if v is None:return '—'
    try:return f'{float(v):.2f}'
    except (TypeError,ValueError):return str(v)

def percent(v):
    return str(v)+'%' if v is not None else '—'

def session_status(r):
    # A stored session without a recognized state is not a routine slot.
    st=r.get('status_pertemuan')
    return session_label(st) if st is not None else 'Status belum tersedia'

def absen_status(r):return ABSEN.get(r.get('status_absensi'),'Belum dicatat')

def roster_unique(rows):
    out=[];seen=set()
    for r in rows:
        sid=r.get('student_id')
        if sid is None or sid in seen:continue
        seen.add(sid);out.append(r)
    return out


PROGRAMS=table_renderer([column('Program','nama',4),column('Jenjang','jenjang',2),
    column('Siswa aktif','siswa_aktif',2),column('Jadwal aktif','jadwal_aktif',2)])
SCHEDULES=table_renderer([column('Hari / jam',lambda r:label_hari(r.get('hari'))+' '+jam_jadwal(r),3),
    column('Program','nama_program',4),column('Ruang','nama_ruang',2),column('Peserta','jumlah_siswa',1)])
STUDENTS=table_renderer([column('Nama siswa','nama_lengkap',4),column('NIS','nis',2),
    column('Nilai akhir',lambda r:score(r.get('nilai_akhir')),2),
    column('% Hadir',lambda r:percent(r.get('persen_hadir')),1),column('Absensi','total_absensi',1)])
SESSIONS=table_renderer([column('Tanggal / ke-',lambda r:f"{tgl(r.get('tanggal'))} · #{r.get('pertemuan_ke') or '—'}",3),
    column('Program','nama_program',3),column('Status',session_status,3),column('Absensi','jumlah_absen',1)],lambda r:session_tone(r.get('status_pertemuan')))
RECAP=table_renderer([column('Nama siswa','nama_lengkap',4),column('NIS','nis',2),
    column('Hadir','hadir',1),column('Izin','izin',1),column('Sakit','sakit',1),column('Alpa','alpa',1),
    column('% Hadir',lambda r:percent(r.get('persen_hadir')),2)])
GRADE_ROWS=table_renderer([column('Nama siswa','nama_lengkap',3),column('Nilai',lambda r:score(r.get('nilai')),1),
    column('Jenis','jenis',1),column('Judul','judul',3),column('Tanggal',lambda r:tgl(r.get('tanggal')),2)])
CLASS_GRADES=table_renderer([column('Nama siswa','nama_lengkap',4),column('Akhir',lambda r:score(r.get('nilai_akhir')),2),
    column('Tugas',lambda r:score(r.get('tugas')),1),column('Kuis',lambda r:score(r.get('kuis')),1),
    column('UTS',lambda r:score(r.get('uts')),1),column('UAS',lambda r:score(r.get('uas')),1)])
NOTES=table_renderer([column('Topik','topik',4),column('Program','nama_program',3),
    column('Tanggal',lambda r:tgl(r.get('tanggal')),2),column('Ke-','pertemuan_ke',1)])


def schedule_sections(r,sessions):
    sections=[('KELAS & JADWAL',fields(r,[('Program','nama_program'),('Kode','kode_program'),('Jenjang','jenjang'),
        ('Ruangan','nama_ruang')])+[('Hari',label_hari(r.get('hari'))),('Waktu',jam_jadwal(r)),
        ('Status','Aktif' if r.get('aktif') else 'Nonaktif'),('Peserta program',value(r,'jumlah_siswa'))])]
    projected=proyeksi_jadwal(r,sessions) if r.get('aktif') else None
    if projected:
        prior,nxt=projected['sebelumnya'],projected['berikutnya']
        sections.extend([('SLOT SEBELUMNYA (PERKIRAAN)',[('Tanggal',tgl(prior['tanggal'])),('Status',prior['status'])]),
            ('SLOT BERIKUTNYA (PERKIRAAN)',[('Tanggal',tgl(nxt['tanggal'])),('Status',nxt['status'])])])
    if sessions:
        last=sessions[0]
        sections.append(('PERTEMUAN TERAKHIR',[('Tanggal',tgl(last.get('tanggal'))),('Pertemuan',value(last,'pertemuan_ke')),
            ('Status',session_status(last)),('Topik',value(last,'topik','Belum dilaporkan')),('Absensi tercatat',value(last,'jumlah_absen'))]))
    else:
        sections.append(('PERTEMUAN TERCATAT',[('Status','Belum ada laporan pertemuan')]))
    sections.append(('KETERANGAN',[('Perkiraan',CATATAN_PROYEKSI),
        ('Peserta','Jumlah enrollment aktif program, bukan peserta sesi.')]))
    return sections


def session_sections(r):
    state=r.get('status_pertemuan')
    rows=fields(r,[('Program','nama_program'),('Kode','kode_program'),('Pertemuan','pertemuan_ke')])+[
        ('Tanggal',tgl(r.get('tanggal'))),('Jam',jam_jadwal(r)),('Ruang',value(r,'nama_ruang')),('Status',session_status(r))]
    info=[('Absensi tercatat',value(r,'jumlah_absen')),('Topik',value(r,'topik','Belum dilaporkan'))]
    if state=='batal':info.append(('Alasan batal',value(r,'alasan_batal','Arsip lama (tidak tercatat)')))
    return [('PERTEMUAN',rows),('LAPORAN TUTOR',info)]


def student_sections(r,*,detail=False):
    identity=fields(r,[('Nama','nama_lengkap'),('NIS','nis'),('ID pendaftaran','enrollment_id')])
    if detail:
        identity+=fields(r,[('Username','username'),('Email','email'),('Sekolah','sekolah'),('Jenjang','jenjang'),
                               ('Nomor HP','no_hp'),('Nama wali','nama_wali'),('Kelas','nama_program'),('Kode kelas','kode_program')])
    grade=[(k.upper(),score(r.get(k))) for k in ('tugas','kuis','uts','uas')]+[('Nilai akhir',score(r.get('nilai_akhir')))]
    attendance=[('Tercatat',value(r,'total_absensi')),('Hadir',value(r,'hadir')),('Izin',value(r,'izin')),
        ('Sakit',value(r,'sakit')),('Alpa',value(r,'alpa')),('% Hadir',percent(r.get('persen_hadir')))]
    return [('IDENTITAS SISWA',identity),('NILAI AKADEMIK',grade),('KEHADIRAN TERCATAT',attendance)]


def attendance_progress_pages(session,student,index,total,w,b):
    """Keep student context above each H/I/S/A choice; draft remains local."""
    def progress(cw):
        bar_width=min(30,max(0,cw-14))
        n=round(bar_width*(index-1)/max(1,total))
        if bar_width>=4:
            return [[('class:success','█'*n),('class:rule','░'*(bar_width-n)),('', ' '),
                     *line(f'{index}/{total}',max(1,cw-bar_width-1),'title')]]
        return [line(f'Siswa {index}/{total}',cw,'title','center')]
    blocks=[]
    add_panel(blocks,'PENGISIAN ABSENSI',progress,w,b)
    cards=details_pages([('IDENTITAS SISWA',fields(student,[('Nama','nama_lengkap'),('NIS','nis')])+[
        ('Status sebelumnya',absen_status(student))]),
        ('KONTEKS PERTEMUAN',[('Program',value(session,'nama_program')),('Pertemuan',value(session,'pertemuan_ke')),
            ('Tanggal',tgl(session.get('tanggal'))),('Waktu',jam_jadwal(session)),('Ruang',value(session,'nama_ruang'))])],
        w,b,full=True,paired=True)
    blocks.extend(cards)
    return paginate_blocks(blocks,b)


def attendance_review_pages(session,preview,w,b):
    counts=Counter(r['status'] for r in preview)
    header=f"{len(preview)} siswa · H {counts['H']} · I {counts['I']} · S {counts['S']} · A {counts['A']}"
    blocks=[]
    # One concise summary, followed by fully pageable record descriptions.
    blocks.extend([[line(t,w,'title','center')] for t in wrap(header,max(1,w))])
    context=f"{value(session,'nama_program')} · Pertemuan #{value(session,'pertemuan_ke')} · {tgl(session.get('tanggal'))}"
    blocks.extend([[line(t,w,'muted','center')] for t in wrap(context,max(1,w))])
    for i,r in enumerate(preview,1):
        desc=f"{i:02d}  {r['nis']} · {r['nama']} · {ABSEN[r['status']]}"
        rows=[line(t,w,'title') for t in wrap(desc,w)]
        if r['keterangan']:
            rows.extend(line(t,w,'muted') for t in wrap('Keterangan: '+r['keterangan'],w))
        if len(rows)<=b:blocks.append(rows)
        else:blocks.extend([[row] for row in rows])
    return paginate_blocks(blocks,b)


class TutorAcademicController(FeatureController):
    def __init__(self,view,service,tutor_service):
        super().__init__(view);self.service=service;self.tutor=tutor_service

    async def data(self,fn,*args,**kwargs):return await self.read(fn,*args,service=True,**kwargs)

    async def write_payload(self,fn,*args):
        # For commands returning a structured success payload instead of message.
        try:ok,result=await self.view.busy('Memproses tindakan...',fn,*args)
        except Exception as exc:
            await self.view.result('HASIL BELUM DIPASTIKAN',
                'Periksa status terbaru sebelum mengulangi tindakan ('+type(exc).__name__+').','error')
            return None
        if not ok:
            await self.view.result('TINDAKAN BELUM BERHASIL',str(result),'error')
            return None
        return result

    async def pick_data(self,title,loader,renderer,*,key=None,empty='Belum ada data.',caption='Pilih data'):
        while True:
            rows=await loader()
            if rows is None:return None
            r=await self.pick(title,rows,renderer,key=key,empty=empty,caption=caption)
            if r=='refresh':continue
            return r

    async def program(self):
        return await self.pick_data('PILIH PROGRAM',
            lambda:self.data(self.service.program_tutor),PROGRAMS,key='id',
            empty='Belum ada kelas yang ditugaskan kepada akun Tutor.')

    async def student(self,pid):
        return await self.pick_data('PILIH SISWA',
            lambda:self.data(self.service.daftar_siswa,pid),STUDENTS,key='enrollment_id',
            empty='Belum ada siswa aktif di program ini.')

    async def session(self,pid=None,*,title='PILIH PERTEMUAN'):
        return await self.pick_data(title,lambda:self.data(self.service.daftar_pertemuan,pid),SESSIONS,
            key='session_id',empty='Belum ada laporan pertemuan. Kelola pertemuan di Absensi.')

    async def schedules(self):
        focus='hari'
        while True:
            rows=await self.data(self.service.jadwal,aktif=True)
            if rows is None:return
            today=[r for r in rows if r.get('hari')==HARI[date.today().weekday()]]
            render=lambda w,b:metrics_pages([('HARI INI',str(len(today)),'Slot rutin'),
                ('MINGGUAN',str(len(rows)),'Jadwal aktif')],w,b,note='Jadwal rutin bukan laporan pertemuan.') if rows else empty_pages(
                'Belum ada jadwal aktif yang ditugaskan Admin.','Jadwal mengajar',width=w,budget=b)
            action=await self.view.page('JADWAL MENGAJAR',[('hari','Jadwal hari ini'),('minggu','Jadwal mingguan'),
                ('refresh','Muat ulang'),('back','Kembali ke dashboard')],render,default=focus)
            if action in (None,'back'):return
            if action=='refresh':continue
            focus=action
            await self.schedule_list(action=='hari')

    async def schedule_list(self,today_only=False):
        title='JADWAL MENGAJAR HARI INI' if today_only else 'JADWAL MINGGUAN'
        focus=None
        while True:
            rows=await self.data(self.service.jadwal,aktif=True)
            if rows is None:return
            visible=[r for r in rows if not today_only or r.get('hari')==HARI[date.today().weekday()]]
            if not visible and rows and today_only:
                nearest=jadwal_rutin_terdekat(rows)
                if nearest:
                    dt,item=nearest
                    action=await self.page(title,[('week','Lihat jadwal mingguan'),('refresh','Muat ulang'),('back','Kembali')],
                        [('HARI INI',[('Status','Tidak ada jadwal rutin hari ini')]),
                        ('SLOT TERDEKAT (PERKIRAAN)',[('Tanggal',tgl(dt)),('Program',value(item,'nama_program')),('Jam',jam_jadwal(item))])],
                        notice='Jadwal rutin belum membuktikan pertemuan terlaksana.')
                    if action=='refresh':continue
                    if action=='week':await self.schedule_list(False);continue
                    return
            r=await self.pick(title,visible,SCHEDULES,key='id',initial=focus,
                caption='Jadwal rutin · peserta program, bukan peserta sesi',
                empty='Tidak ada jadwal mengajar hari ini.' if today_only else 'Belum ada jadwal aktif.')
            if r=='refresh':continue
            if not r:return
            focus=r['_ui_key']
            await self.schedule_detail(r)

    async def schedule_detail(self,r):
        while True:
            sessions=await self.data(self.service.pertemuan_per_jadwal,r['id'])
            if sessions is None:return
            action=await self.page('DETAIL JADWAL TUTOR',[
                ('riwayat','Riwayat pertemuan tercatat'),('siswa','Daftar siswa aktif program'),('back','Kembali')],
                schedule_sections(r,sessions),notice='Jadwal merupakan perkiraan; bukan bukti kelas terlaksana.')
            if action in (None,'back'):return
            if action=='riwayat':
                async def load():
                    data=await self.data(self.service.pertemuan_per_jadwal,r['id'])
                    return [dict(x,nama_program=r.get('nama_program'),kode_program=r.get('kode_program'),
                                 jam_mulai=r.get('jam_mulai'),jam_selesai=r.get('jam_selesai'),
                                 nama_ruang=r.get('nama_ruang')) for x in data] if data is not None else None
                async def detail(s):await self.read_session(s)
                await self.browse('RIWAYAT PERTEMUAN',load,SESSIONS,detail,key='session_id',empty='Belum ada sesi tercatat pada jadwal ini.')
            elif action=='siswa':
                await self.students(r['program_id'])

    async def students(self,pid):
        async def load():return await self.data(self.service.daftar_siswa,pid)
        async def detail(row):
            obj=await self.data(self.service.detail_siswa,pid,row['student_id'])
            if obj is not None:await self.details('DETAIL SISWA',student_sections(obj,detail=True))
        await self.browse('SISWA AKTIF PROGRAM',load,STUDENTS,detail,key='enrollment_id',empty='Belum ada siswa aktif di program ini.')

    async def classes(self):
        # The previous two menu entries used the same data; a single selectable
        # roster now covers both list and detail without a duplicate list.
        while True:
            p=await self.program()
            if not p:return
            # Keep all program information but remain on a single roster workflow.
            action=await self.page('KELAS & SISWA',[('siswa','Daftar siswa dan detail'),('back','Kembali')],
                [('KELAS YANG DIAMPU',fields(p,[('Program','nama'),('Kode','kode'),('Jenjang','jenjang')])),
                 ('RINGKASAN',fields(p,[('Siswa aktif','siswa_aktif'),('Jadwal aktif','jadwal_aktif')]))])
            if action=='siswa':await self.students(p['id'])

    async def read_session(self,r):
        await self.view.page('DETAIL PERTEMUAN',[('back','Kembali')],
            lambda w,b:content_pages(session_sections(r),[('RINGKASAN MATERI',r.get('ringkasan') or 'Belum dilaporkan')],w,b))

    async def prepare_session(self):
        r=await self.pick_data('PILIH JADWAL AKTIF',lambda:self.data(self.service.jadwal,aktif=True),
            SCHEDULES,key='id',empty='Belum ada jadwal mengajar aktif.',
            caption='Layanan memeriksa tanggal pertemuan hari ini')
        if not r:return
        if not await self.confirm('SIAPKAN PERTEMUAN',[('JADWAL',[('Program',value(r,'nama_program')),
                  ('Hari',label_hari(r.get('hari'))),('Jam',jam_jadwal(r)),('Ruang',value(r,'nama_ruang'))])],
                  label='Siapkan pertemuan',notice='Memakai jadwal Admin. Satu sesi per tanggal.'):
            return
        result=await self.write_payload(self.service.siapkan_pertemuan,r['id'])
        if result is not None:await self.manage_session(result['session_id'])

    async def manage_session(self,sid):
        while True:
            r=await self.data(self.service.ringkasan_pertemuan,sid)
            if r is None:return
            editable=r.get('status_pertemuan') not in CLOSED
            choices=([('absensi','Isi / koreksi absensi siswa'),('materi','Isi materi & catatan'),
                       ('selesai','Konfirmasi pertemuan selesai'),('batal','Laporkan pertemuan dibatalkan')]
                     if editable else [])
            choices+=[('detail','Baca catatan materi'),('refresh','Muat ulang'),('back','Kembali')]
            action=await self.page('KELOLA PERTEMUAN',choices,session_sections(r),
                notice='Absensi tidak dapat diubah setelah sesi ditutup.' if not editable else
                  'Kelengkapan absensi diperiksa layanan saat konfirmasi selesai.')
            if action in (None,'back'):return
            if action=='refresh':continue
            if action=='detail':await self.read_session(r);continue
            if not editable:continue
            if action=='absensi':await self.attendance_fill(sid)
            elif action=='materi':await self.material_edit(r)
            elif action=='selesai':
                if await self.confirm('KONFIRMASI PENYELESAIAN',session_sections(r),
                        label='Ya, selesaikan pertemuan',notice='Pastikan semua peserta sudah diabsen.'):
                    await self.mutate(self.service.selesaikan_pertemuan,sid,service=True)
            elif action=='batal':
                notice=''
                while True:
                    ans=await self.view.form('PEMBATALAN PERTEMUAN',[Field('reason','Alasan pertemuan tidak berlangsung')],
                        subtitle=value(r,'nama_program'),notice=notice,hint='Alasan wajib diisi (minimal 5 karakter).')
                    if ans is None:break
                    reason=ans['reason'].strip()
                    if len(reason)<5:
                        notice='Alasan minimal 5 karakter.';continue
                    if await self.confirm('KONFIRMASI PEMBATALAN',session_sections(r)+[('ALASAN',[('Keterangan',reason)])],
                        label='Ya, batalkan pertemuan',notice='Pembatalan hanya diizinkan jika absensi belum tercatat.'):
                        await self.mutate(self.service.batalkan_pertemuan,sid,reason,service=True)
                    break

    async def attendance_fill(self,sid):
        # Refresh ownership/status via the same service even when opened from a stale list.
        r=await self.data(self.service.ringkasan_pertemuan,sid)
        if r is None:return
        if r.get('session_id')!=sid or r.get('status_pertemuan') in CLOSED:
            await self.view.result('ABSENSI TIDAK DAPAT DIUBAH','Identitas sesi tidak tersedia atau sudah ditutup.','info')
            return
        while True:
            roster=await self.data(self.service.daftar_absensi,sid)
            if roster is None:return
            students=roster_unique(roster)
            if students:break
            action=await self.pick('PESERTA ABSENSI',[],STUDENTS,empty='Belum ada siswa yang dapat diabsen pada sesi ini.')
            if action!='refresh':return
        records=[];preview=[]
        for i,student in enumerate(students,1):
            name=value(student,'nama_lengkap','Nama belum tersedia')
            previous=student.get('status_absensi')
            choices=[(k,l+(' (sebelumnya)' if previous==k else '')) for k,l in ABSEN.items()]+[('back','Batalkan seluruh pengisian')]
            status=await self.view.page('ABSENSI · '+name,choices,
                lambda w,b:attendance_progress_pages(r,student,i,len(students),w,b),
                default=previous if previous in ABSEN else 'H')
            if status not in ABSEN:
                await self.view.result('ABSENSI DIBATALKAN','Tidak ada perubahan absensi yang disimpan.');return
            note=await self.view.form('KETERANGAN ABSENSI',[Field('note','Keterangan (opsional)',str(student.get('keterangan') or ''))],
                subtitle=f"{name} · {ABSEN[status]}",step=f'{i}/{len(students)}',
                hint='Keterangan tidak wajib.',submit_label='Lanjutkan')
            if note is None:
                await self.view.result('ABSENSI DIBATALKAN','Tidak ada perubahan absensi yang disimpan.');return
            records.append({'student_id':student['student_id'],'status':status,'keterangan':note['note']})
            preview.append({'nis':value(student,'nis'),'nama':name,'status':status,'keterangan':note['note']})
        decision=await self.view.page('KONFIRMASI ABSENSI',[('confirm','Simpan seluruh absensi'),('back','Batal')],
            lambda w,b:attendance_review_pages(r,preview,w,b),default='back')
        if decision=='confirm':
            await self.mutate(self.service.simpan_absensi,sid,records,service=True)
        else:await self.view.result('ABSENSI DIBATALKAN','Tidak ada perubahan absensi yang disimpan.')

    async def attendance_recap(self):
        p=await self.program()
        if not p:return
        async def load():return await self.data(self.service.rekap_absensi,p['id'])
        async def detail(r):
            await self.details('REKAP ABSENSI SISWA',[('SISWA',fields(r,[('Nama','nama_lengkap'),('NIS','nis'),('Pendaftaran','enrollment_id')])),
                ('SESI SELESAI',fields(r,[('Pertemuan','total_pertemuan'),('Hadir','hadir'),('Izin','izin'),('Sakit','sakit'),('Alpa','alpa')])+[
                    ('Persentase hadir',percent(r.get('persen_hadir')))])])
        await self.browse('REKAP ABSENSI KELAS',load,RECAP,detail,key='enrollment_id',
            empty='Belum ada rekap absensi untuk kelas ini.',caption='Hanya sesi selesai')

    async def attendance(self):
        while True:
            action=await self.view.page('PUSAT ABSENSI',[
                ('baru','Kelola pertemuan hari ini'),('kelola','Kelola pertemuan tercatat'),
                ('isi','Isi / ubah absensi pertemuan'),('rekap','Rekap absensi per siswa'),('back','Kembali')],
                lambda w,b:details_pages([('ALUR PERTEMUAN',[('01','Siapkan sesi sesuai jadwal'),
                    ('02','Isi absensi dan materi'),('03','Konfirmasi selesai atau batalkan')])],w,b))
            if action in (None,'back'):return
            if action=='baru':await self.prepare_session()
            elif action in ('kelola','isi'):
                r=await self.session()
                if r:
                    if action=='kelola':await self.manage_session(r['session_id'])
                    else:await self.attendance_fill(r['session_id'])
            elif action=='rekap':await self.attendance_recap()

    async def grade_kind(self,old=None):
        return await self.view.page('JENIS NILAI',[(k,l) for k,l in JENIS.items()]+[('back','Kembali')],
            lambda w,b:[[line('Pilih jenis komponen sesuai program.',w,'muted','center')]],default=old)

    async def grade_form(self,p,student=None,old=None):
        kind=await self.grade_kind(old.get('jenis') if old else None)
        if kind not in JENIS:return
        base=old or {}
        person=student or old
        title='UBAH NILAI' if old else 'INPUT NILAI'
        caption=f"{value(person,'nama_lengkap')} · {value(p,'nama')}"
        ans=await self.view.form(title,[Field('judul','Judul nilai (opsional)',str(base.get('judul') or '')),
            Field('nilai','Nilai 0–100 (boleh desimal)',str(base.get('nilai')) if base.get('nilai') is not None else '')],
            subtitle=caption,step='1/2',hint='Contoh nilai: 87,5.')
        if ans is None:return
        dt=await self.view.form(title,[Field('tanggal','Tanggal YYYY-MM-DD',str(base.get('tanggal') or ''))],
            subtitle=caption,step='2/2',hint='Kosong = hari ini.',submit_label='Tinjau nilai')
        if dt is None:return
        sections=[('NILAI SISWA',[('Nama',value(person,'nama_lengkap')),('NIS',value(person,'nis')),
                  ('Program',value(p,'nama')),('Jenis',JENIS[kind]),('Judul',ans['judul'] or '—'),
                  ('Nilai',ans['nilai']),('Tanggal',dt['tanggal'] or 'Hari ini')])]
        if old:sections.append(('NILAI SEBELUMNYA',[('Nilai lama',score(old.get('nilai'))),('Jenis lama',value(old,'jenis'))]))
        if not await self.confirm('KONFIRMASI '+title,sections,label='Ya, simpan nilai'):return
        if old:
            await self.mutate(self.service.ubah_nilai,old['grade_id'],kind,ans['nilai'],ans['judul'],dt['tanggal'] or None,service=True)
        else:
            await self.mutate(self.service.input_nilai,p['id'],student['student_id'],kind,ans['nilai'],ans['judul'],dt['tanggal'] or None,service=True)

    async def grades(self):
        while True:
            action=await self.view.page('PUSAT NILAI',[('input','Input nilai'),('ubah','Ubah nilai yang saya input'),
                ('kelas','Lihat nilai kelas & nilai akhir'),('back','Kembali')],
                lambda w,b:details_pages([('PENILAIAN',[('Jenis','Tugas · Kuis · UTS · UAS'),
                    ('Kepemilikan','Hanya nilai input sendiri yang dapat diubah.'),('Nilai akhir','Bobot program dari layanan')])],w,b))
            if action in (None,'back'):return
            p=await self.program()
            if not p:continue
            if action=='input':
                r=await self.student(p['id'])
                if r:await self.grade_form(p,student=r)
            elif action=='ubah':
                r=await self.pick_data('PILIH NILAI MILIK TUTOR',
                    lambda:self.data(self.service.daftar_nilai,p['id'],hanya_milik_tutor=True),GRADE_ROWS,
                    key='grade_id',empty='Belum ada nilai yang kamu input pada kelas ini.')
                if r:await self.grade_form(p,old=r)
            elif action=='kelas':
                async def load():return await self.data(self.service.nilai_kelas,p['id'])
                async def detail(r):await self.details('DETAIL NILAI SISWA',student_sections(r)[:2])
                await self.browse('NILAI KELAS',load,CLASS_GRADES,detail,key='enrollment_id',empty='Belum ada nilai kelas yang tersedia.')

    async def material_edit(self,r):
        if r.get('status_pertemuan')=='batal':
            await self.view.result('CATATAN TIDAK DAPAT DIUBAH','Pertemuan telah dibatalkan.');return
        caption=f"{value(r,'nama_program')} · #{value(r,'pertemuan_ke')}"
        ans=await self.view.form('CATATAN MATERI',[Field('topik','Topik pembelajaran',str(r.get('topik') or '')),
            Field('ringkasan','Ringkasan materi',str(r.get('ringkasan') or '').replace('\n','\\n'))],
            subtitle=caption,hint='Ketik \\n untuk baris baru.',submit_label='Tinjau catatan')
        if ans is None:return
        text=ans['ringkasan'].replace('\\n','\n')
        if await self.view.page('KONFIRMASI CATATAN MATERI',[('confirm','Ya, simpan catatan'),('back','Batal')],
            lambda w,b:content_pages([('PERTEMUAN',[('Program',value(r,'nama_program')),('Nomor',value(r,'pertemuan_ke'))])],
                [('TOPIK',ans['topik']),('RINGKASAN',text)],w,b),default='back')=='confirm':
            await self.mutate(self.service.simpan_catatan,r['session_id'],ans['topik'],text,service=True)

    async def materials(self):
        while True:
            action=await self.view.page('CATATAN MATERI',[('tulis','Tulis / ubah catatan pertemuan'),
                ('daftar','Daftar catatan sebelumnya'),('back','Kembali')],
                lambda w,b:details_pages([('MATERI KELAS',[('Topik','Materi yang diajarkan'),
                    ('Ringkasan','Catatan pembelajaran untuk siswa')])],w,b))
            if action in (None,'back'):return
            if action=='tulis':
                p=await self.program()
                if not p:continue
                r=await self.session(p['id'],title='PILIH PERTEMUAN UNTUK MATERI')
                if r:await self.material_edit(r)
            elif action=='daftar':
                async def load():return await self.data(self.service.daftar_catatan,None)
                async def detail(r):
                    await self.view.page('DETAIL CATATAN MATERI',[('back','Kembali')],
                        lambda w,b:content_pages([('PERTEMUAN',[('Program',value(r,'nama_program')),
                            ('Tanggal',tgl(r.get('tanggal'))),('Nomor',value(r,'pertemuan_ke'))])],
                            [('TOPIK',r.get('topik')),('RINGKASAN',r.get('ringkasan'))],w,b))
                await self.browse('CATATAN MATERI SEBELUMNYA',load,NOTES,detail,key='session_id',empty='Belum ada catatan materi.')

    async def profile(self):
        while True:
            p=await self.data(self.tutor.profil)
            if p is None:return
            action=await self.page('PROFIL TUTOR',[('ubah','Ubah keahlian dan nomor HP'),('password','Ganti password'),
                ('refresh','Muat ulang'),('back','Kembali')],
                [('IDENTITAS AKUN',fields(p,[('Nama','nama_lengkap'),('Username','username'),('Email','email'),('Status','status_akun')])),
                 ('PROFIL PENGAJAR',fields(p,[('Kode tutor','kode_tutor'),('Keahlian','keahlian'),('Nomor HP','no_hp')]))])
            if action in (None,'back'):return
            if action=='ubah':
                ans=await self.view.form('UBAH PROFIL',[Field('keahlian','Keahlian',str(p.get('keahlian') or '')),
                    Field('no_hp','Nomor HP',str(p.get('no_hp') or ''))],submit_label='Tinjau profil')
                if ans is not None and await self.confirm('SIMPAN PROFIL',[('PERUBAHAN',[('Keahlian',ans['keahlian']),('Nomor HP',ans['no_hp'])])],
                    label='Ya, simpan profil'):
                    await self.mutate(self.tutor.ubah_profil,ans['keahlian'],ans['no_hp'],service=True)
            elif action=='password':
                old=await self.view.form('GANTI PASSWORD',[Field('old','Password lama',secret=True)],step='1/2')
                if old is None:continue
                notice=''
                while True:
                    ans=await self.view.form('GANTI PASSWORD',[Field('new','Password baru',secret=True),Field('again','Ulangi password baru',secret=True)],
                        step='2/2',notice=notice,submit_label='Ganti password')
                    if ans is None:break
                    if ans['new']!=ans['again']:
                        notice='Konfirmasi password tidak sama.';continue
                    await self.mutate(self.tutor.ganti_password,old['old'],ans['new'],ans['again'],service=True)
                    break


def _controller(view):
    from app.services import academic_service,tutor_service
    return TutorAcademicController(view,academic_service,tutor_service)


def jalankan_modul(modul):
    mapping={'jadwal':'schedules','kelas':'classes','absensi':'attendance','nilai':'grades','materi':'materials','profil':'profile'}
    if modul not in mapping:return None
    async def flow(view):return await getattr(_controller(view),mapping[modul])()
    return run_tutor(flow)
