"""UI-008 regression tests: existing tutor services are injected; no real database."""
import ast
import unittest
from datetime import date,time,datetime
from pathlib import Path
from unittest.mock import Mock,AsyncMock,call
from test_ui003b_enrollment import View
from test_ui002_admin_workspace import text_of
from app.ui.admin_workspace import width_of
from app.ui.tutor_workspace import TutorSnapshot,load_snapshot,dashboard_pages,TutorDashboardNavigator,MENU
from app.ui.tutor_academic import TutorAcademicController,schedule_sections,attendance_progress_pages,attendance_review_pages,student_sections
from app.ui.tutor_communication import CommunicationController,announcement_pages,notification_target

PROGRAM=dict(id=1,nama='Matematika SMA',kode='MTK',jenjang='SMA',siswa_aktif=2,jadwal_aktif=2,jumlah_siswa=2)
SLOT=dict(id=1,schedule_id=1,program_id=1,nama_program='Matematika SMA',kode_program='MTK',jenjang='SMA',nama_ruang='Ruang A',hari='jumat',jam_mulai=time(14),jam_selesai=time(15,30),aktif=True,hari_ini=True,jumlah_siswa=2,status_sesi_hari_ini='perlu_laporan')
SESSION=dict(SLOT,session_id=11,pertemuan_ke=4,tanggal=date(2026,11,27),status_pertemuan='perlu_laporan',jumlah_absen=0,topik='Fungsi kuadrat',ringkasan='Materi latihan')
STUDENT=dict(student_id=21,enrollment_id=31,nama_lengkap='Andi Pratama',nis='S001',status_absensi='H',keterangan='',nilai_akhir=88,tugas=90,kuis=84,uts=88,uas=89,hadir=4,izin=1,sakit=0,alpa=0,persen_hadir=80,total_absensi=5,total_pertemuan=5)
STUDENT2=dict(STUDENT,student_id=22,enrollment_id=32,nama_lengkap='Aulia Rahma',nis='S002',status_absensi=None)
GRADE=dict(STUDENT,grade_id=41,jenis='tugas',judul='Latihan 1',nilai=90,tanggal=date(2026,11,27))
PROFILE=dict(nama_lengkap='Dewi Anggraini',username='dewi',email='dewi@example.test',status_akun='aktif',kode_tutor='T001',keahlian='Matematika',no_hp='0812345678')
STATS=dict(program_diampu=2,jadwal_aktif=4,siswa_aktif=24,sesi_perlu_laporan=1)
SNAP=TutorSnapshot(STATS,[SLOT,dict(SLOT,id=2,hari_ini=False,hari='sabtu',nama_program='Fisika SMA')],3,True)
MESSAGE=dict(id=6,judul='Pengingat pertemuan',isi='Laporan pertemuan belum lengkap.',sumber='sistem',kategori='pengingat',related_type='schedule_pending',created_at=datetime(2026,11,27,8))
ANNOUNCE=dict(batch_key='n2t-test',judul='Latihan minggu ini',isi='Bawa buku latihan.',nama_program='Matematika SMA',jumlah_penerima=2,created_at=datetime(2026,11,27,8),expires_at=datetime(2026,12,4,8))

def service(**kwargs):
    defaults=dict(program_tutor=(True,[PROGRAM]),daftar_siswa=(True,[STUDENT,STUDENT2]),
        detail_siswa=(True,STUDENT),jadwal=(True,[SLOT]),pertemuan_per_jadwal=(True,[SESSION]),
        daftar_pertemuan=(True,[SESSION]),ringkasan_pertemuan=(True,SESSION),siapkan_pertemuan=(True,SESSION),
        daftar_absensi=(True,[STUDENT,STUDENT2,STUDENT]),simpan_absensi=(True,'Tersimpan'),
        selesaikan_pertemuan=(True,'Selesai'),batalkan_pertemuan=(True,'Dibatalkan'),
        rekap_absensi=(True,[STUDENT]),input_nilai=(True,'Tersimpan'),ubah_nilai=(True,'Diubah'),
        daftar_nilai=(True,[GRADE]),nilai_kelas=(True,[STUDENT]),simpan_catatan=(True,'Tersimpan'),daftar_catatan=(True,[SESSION]))
    mocks={k:Mock(return_value=v) for k,v in defaults.items()}
    mocks.update(kwargs)
    return Mock(**mocks)

def tutor():
    return Mock(profil=Mock(return_value=(True,PROFILE)),ubah_profil=Mock(return_value=(True,'Tersimpan')),
        ganti_password=Mock(return_value=(True,'Diubah')))

def engagement(**kwargs):
    defaults=dict(sinkronisasi_notifikasi=None,jumlah_notifikasi_belum_dibaca=3,daftar_notifikasi_filter=[MESSAGE],
        buka_notifikasi=MESSAGE,buka_notifikasi_arsip=MESSAGE,arsipkan_notifikasi_pribadi=None,tandai_semua_dibaca=3,
        daftar_pengumuman_tutor=[ANNOUNCE],daftar_program_pengumuman_tutor=[PROGRAM],akhiri_pengumuman_tutor=None,
        buat_pengumuman_tutor={'jumlah_penerima':2,'expires_at':ANNOUNCE['expires_at']},
        daftar_pertemuan_tertunda_tutor=[SESSION],buka_pertemuan_terlewat_tutor=11)
    mocks={k:Mock(return_value=v) for k,v in defaults.items()}
    mocks.update(kwargs)
    return Mock(**mocks)

class LayoutTests(unittest.TestCase):
    def test_every_page_is_bounded(self):
        long=dict(STUDENT,nama_lengkap='Nama sangat panjang 界 '*20)
        preview=[dict(nis='S001',nama=long['nama_lengkap'],status='H',keterangan='Keterangan panjang '*100)]
        for w in (20,40,60,78,100):
            for b in (1,4,12,24):
                for pages in (dashboard_pages(SNAP,w,b),dashboard_pages(TutorSnapshot({'program_diampu':0},[],0,True),w,b),
                              attendance_progress_pages(SESSION,long,1,2,w,b),attendance_review_pages(SESSION,preview,w,b),
                              announcement_pages(dict(ANNOUNCE,isi='Pesan panjang '*150),w,b)):
                    for page in pages:
                        self.assertLessEqual(len(page),b,(w,b))
                        for row in page:self.assertLessEqual(width_of(row),w,(w,b,row))
    def test_snapshot_uses_tutor_identity_and_does_not_fake_zero(self):
        stats=Mock(return_value=STATS);schedules=Mock(side_effect=RuntimeError('secret'))
        sync=Mock(side_effect=RuntimeError('secret'));unread=Mock(return_value=3)
        snap=load_snapshot({'id':9},stats=stats,schedules=schedules,sync=sync,unread=unread)
        stats.assert_called_once_with(9);schedules.assert_called_once_with(9)
        sync.assert_called_once_with('tutor');unread.assert_called_once_with('tutor')
        self.assertIsNone(snap.schedules);self.assertFalse(snap.sync_ok)
        self.assertEqual(snap.metric('unknown'),'—')
        txt=' '.join(text_of(p) for p in dashboard_pages(snap,100,24))
        self.assertIn('Data belum lengkap',txt);self.assertNotIn('secret',txt)
    def test_schedule_projection_is_explicit(self):
        sections=str(schedule_sections(SLOT,[SESSION]))
        self.assertIn('PERKIRAAN',sections);self.assertIn('bukan bukti',sections)
    def test_notification_targets(self):
        self.assertEqual(notification_target(MESSAGE),'tertunda')
        self.assertEqual(notification_target(dict(MESSAGE,related_type='session')),'absensi')
        self.assertEqual(notification_target(dict(MESSAGE,related_type='schedule')),'jadwal')
        self.assertIsNone(notification_target(dict(MESSAGE,sumber='admin')))

class AcademicTests(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_navigation(self):
        loader=Mock(return_value=SNAP);v=View(['refresh','nilai'])
        nav=TutorDashboardNavigator(loader)
        self.assertEqual(await nav.choose(v,{'id':1}),'refresh')
        self.assertEqual(await nav.choose(v,{'id':1}),'nilai')
        self.assertEqual({k for k,l in v.events[0][1]},{k for k,l in MENU})
        self.assertIn('3 belum dibaca',str(v.events[0][1]))

    async def test_attendance_unique_single_batch(self):
        v=View(['H',{'note':''},'I',{'note':'Izin keluarga'},'confirm'])
        s=service();c=TutorAcademicController(v,s,tutor())
        await c.attendance_fill(11)
        s.simpan_absensi.assert_called_once_with(11,[dict(student_id=21,status='H',keterangan=''),dict(student_id=22,status='I',keterangan='Izin keluarga')])
        review=next(e for e in v.events if e[0]=='KONFIRMASI ABSENSI')
        self.assertEqual(review[2]['default'],'back')
        self.assertIn('Izin keluarga',str(review[3]))

    async def test_attendance_cancel_and_closed_never_save(self):
        for answers in (['back'],['H',None],['H',{'note':''},'back'],['H',{'note':''},'I',{'note':''},'back']):
            s=service();await TutorAcademicController(View(answers),s,tutor()).attendance_fill(11);s.simpan_absensi.assert_not_called()
        for status in ('selesai','batal'):
            s=service(ringkasan_pertemuan=Mock(return_value=(True,dict(SESSION,status_pertemuan=status))))
            await TutorAcademicController(View([]),s,tutor()).attendance_fill(11)
            s.daftar_absensi.assert_not_called();s.simpan_absensi.assert_not_called()

    async def test_empty_attendance(self):
        s=service(daftar_absensi=Mock(return_value=(True,[])))
        v=View([None]);await TutorAcademicController(v,s,tutor()).attendance_fill(11)
        s.simpan_absensi.assert_not_called();self.assertIn('Belum ada siswa',str(v.events))

    async def test_prepare_and_complete(self):
        s=service(ringkasan_pertemuan=Mock(side_effect=[(True,SESSION),(True,dict(SESSION,status_pertemuan='selesai'))]))
        v=View([1,'confirm','selesai','confirm','back'])
        await TutorAcademicController(v,s,tutor()).prepare_session()
        s.jadwal.assert_called_once_with(aktif=True);s.siapkan_pertemuan.assert_called_once_with(1)
        s.selesaikan_pertemuan.assert_called_once_with(11)
        closed=[e for e in v.events if e[0]=='KELOLA PERTEMUAN'][-1]
        self.assertNotIn('absensi',[k for k,l in closed[1]])

    async def test_cancel_session_reason_and_confirmation(self):
        s=service(ringkasan_pertemuan=Mock(side_effect=[(True,SESSION),(True,dict(SESSION,status_pertemuan='batal'))]))
        v=View(['batal',{'reason':'x'},{'reason':'  Tutor sakit  '},'confirm','back'])
        await TutorAcademicController(v,s,tutor()).manage_session(11)
        s.batalkan_pertemuan.assert_called_once_with(11,'Tutor sakit')
        self.assertIn('minimal 5',str(v.events))

    async def test_grade_input_and_own_grade_filter(self):
        v=View(['input',1,31,'tugas',{'judul':'Latihan','nilai':'87,5'},{'tanggal':''},'confirm',
            'ubah',1,41,'kuis',{'judul':'Kuis','nilai':'88'},{'tanggal':'2026-11-27'},'confirm','back'])
        s=service();await TutorAcademicController(v,s,tutor()).grades()
        s.input_nilai.assert_called_once_with(1,21,'tugas','87,5','Latihan',None)
        s.daftar_nilai.assert_called_once_with(1,hanya_milik_tutor=True)
        s.ubah_nilai.assert_called_once_with(41,'kuis','88','Kuis','2026-11-27')

    async def test_grade_cancel_and_material(self):
        s=service();c=TutorAcademicController(View(['tugas',{'judul':'X','nilai':'90'},{'tanggal':''},'back']),s,tutor())
        await c.grade_form(PROGRAM,student=STUDENT);s.input_nilai.assert_not_called()
        c=TutorAcademicController(View([{'topik':'Fungsi','ringkasan':'Baris satu\\nBaris dua'},'confirm']),s,tutor())
        await c.material_edit(SESSION);s.simpan_catatan.assert_called_once_with(11,'Fungsi','Baris satu\nBaris dua')
        await TutorAcademicController(View([]),s,tutor()).material_edit(dict(SESSION,status_pertemuan='batal'))
        self.assertEqual(s.simpan_catatan.call_count,1)

    async def test_schedule_and_student_read_only(self):
        s=service();v=View([1,'siswa',31,'back',None,'back',None])
        await TutorAcademicController(v,s,tutor()).schedule_list()
        s.detail_siswa.assert_called_once_with(1,21);s.siapkan_pertemuan.assert_not_called()

    async def test_profile_and_password(self):
        t=tutor();v=View(['ubah',{'keahlian':'Fisika','no_hp':'0800'},'confirm','password',{'old':'old'},
            {'new':'new','again':'different'},{'new':'new','again':'new'},'back'])
        await TutorAcademicController(v,service(),t).profile()
        t.ubah_profil.assert_called_once_with('Fisika','0800');t.ganti_password.assert_called_once_with('old','new','new')
        for e in v.events:
            if e[0]=='GANTI PASSWORD':
                self.assertTrue(all(f.secret for f in e[1]))
        self.assertIn('Konfirmasi password tidak sama',str(v.events))

class CommunicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_existing_and_missing(self):
        for row,answers in ((SESSION,[0,'manage',None]),(dict(SESSION,session_id=None),[0,'confirm',None])):
            s=engagement(daftar_pertemuan_tertunda_tutor=Mock(return_value=[row]))
            a=Mock(manage_session=AsyncMock());await CommunicationController(View(answers),s,a).pending()
            a.manage_session.assert_awaited_once_with(11)
            if row['session_id']:s.buka_pertemuan_terlewat_tutor.assert_not_called()
            else:s.buka_pertemuan_terlewat_tutor.assert_called_once_with(1,SESSION['tanggal'])

    async def test_pending_cancel(self):
        s=engagement(daftar_pertemuan_tertunda_tutor=Mock(return_value=[dict(SESSION,session_id=None)]))
        a=Mock(manage_session=AsyncMock());await CommunicationController(View([0,'back',None]),s,a).pending()
        s.buka_pertemuan_terlewat_tutor.assert_not_called();a.manage_session.assert_not_awaited()

    async def test_create_announcement_custom_wib(self):
        s=engagement();v=View([1,{'judul':'','isi':'X'},{'judul':'Latihan','isi':'Pertama\\nKedua'},
            'tanggal',{'tanggal':'2026-12-01 17:00'},'confirm'])
        await CommunicationController(v,s,Mock()).create_announcement()
        s.buat_pengumuman_tutor.assert_called_once_with(1,'Latihan','Pertama\nKedua','tanggal','2026-12-01 17:00')
        self.assertIn('Judul harus',str(v.events))
        s.buat_pengumuman_tutor.reset_mock()
        await CommunicationController(View([1,{'judul':'X','isi':'Y'},'7_hari','back']),s,Mock()).create_announcement()
        s.buat_pengumuman_tutor.assert_not_called()

    async def test_notification_private_archive_and_global_archive_separate(self):
        s=engagement()
        c=CommunicationController(View(['archive','confirm']),s,Mock())
        await c.notification_detail(MESSAGE,False)
        s.arsipkan_notifikasi_pribadi.assert_called_once_with('tutor',6)
        s.akhiri_pengumuman_tutor.assert_not_called()
        s.arsipkan_notifikasi_pribadi.reset_mock()
        await CommunicationController(View(['archive']),s,Mock()).notification_detail(MESSAGE,True)
        s.arsipkan_notifikasi_pribadi.assert_not_called()
        await CommunicationController(View(['n2t-test','archive','confirm',None]),s,Mock()).announcement_list('aktif')
        s.akhiri_pengumuman_tutor.assert_called_once_with('n2t-test')
        s.akhiri_pengumuman_tutor.reset_mock()
        await CommunicationController(View(['n2t-test','back',None]),s,Mock()).announcement_list('arsip')
        s.akhiri_pengumuman_tutor.assert_not_called()

    async def test_quick_open_and_mark_all(self):
        s=engagement()
        target=await CommunicationController(View(['inbox',6,'open']),s,Mock()).notifications()
        self.assertEqual(target,'tertunda')
        s.buka_notifikasi.assert_called_once_with('tutor',6)
        await CommunicationController(View(['allread','confirm','back']),s,Mock()).notifications()
        s.tandai_semua_dibaca.assert_called_once_with('tutor')

if __name__=='__main__':unittest.main()
