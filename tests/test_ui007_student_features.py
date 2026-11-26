"""UI-007B–F regressions. No real DB, Gemini, SMTP, or payments."""
import asyncio
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch, call
from types import SimpleNamespace

from prompt_toolkit.input import create_pipe_input
from app.ui.student_features import FeatureController, StudentFeatureWorkspace, empty_pages, table_renderer, column, content_pages
from app.ui.menu_siswa_academic import (
    AcademicController, CATALOG, CLASSES, PROGRAMS, SCHEDULE, SESSIONS,
    ATTENDANCE, GRADES, MATERIALS, catalog_sections, class_sections,
    schedule_sections, session_sections, attendance_pages, grade_pages,
    _save_rapor,
)
from app.ui.student_billing import BillingController, INVOICES, PAYMENTS, billing_pages, invoice_sections, payment_sections
from app.ui.student_notifications import NotificationController, notification_table, notification_sections, notification_pages, target
from app.ui.admin_confirmation import details_pages
from app.ui.admin_workspace import width_of
from test_ui002_admin_workspace import Output, screen, text_of
from test_ui003b_enrollment import View
from test_ui007a_student_workspace import USER,A,LOCK,PAY,PENDING,HISTORY,SCHEDULE as SLOT


PROGRAM=dict(id=5,nama='Biologi SMA',kode='BIO',jenjang='SMA',harga_bulanan=250000,kuota=20,sisa=5,deskripsi='Belajar biologi dasar dan latihan.')
LOCKED_PROGRAM=dict(LOCK,status_enrollment='aktif',nama_program='Kimia')
ACTIVE_PROGRAM=dict(A,status_enrollment='aktif')
CLASS=dict(A,kode='MTK',jenjang='SMA',tutor='Dewi Anggraini',harga_bulanan=250000,created_at=date(2026,11,1))
OLD=dict(HISTORY,tutor='Dewi Anggraini',kode='SEJ',jenjang='SMA',harga_bulanan=100000)
SLOT=dict(SLOT,schedule_id=1)
SESSION=dict(session_id=1,schedule_id=1,pertemuan_ke=3,tanggal=date(2026,11,20),
    status_pertemuan='selesai',status_absensi='H',topik='Fungsi kuadrat',ringkasan='Latihan soal dan evaluasi',
    nama_tutor='Dewi Anggraini',nama_ruang='Ruang A',jam_mulai=time(15,30),jam_selesai=time(17))
RECAP=dict(enrollment_id=A['enrollment_id'],total_pertemuan=7,hadir=6,izin=1,sakit=0,alpa=0,persen_hadir=Decimal('85.7'))
SCORE=dict(enrollment_id=A['enrollment_id'],nama_program=A['nama_program'],jenjang='SMA',status_enrollment='aktif',
    tugas=90,kuis=85,uts=80,uas=None,nilai_akhir=85.5,bobot_tugas=20,bobot_kuis=20,bobot_uts=30,bobot_uas=30)
GRADE=dict(grade_id=9,judul='Kuis Fungsi',tanggal=date(2026,11,20),jenis='kuis',nilai=85,nama_tutor='Dewi Anggraini')
PROFILE=dict(USER,username='aulia',nis='S001',email='aulia@example.test',jenjang='SMA',sekolah='SMA 1',no_hp='08123',nama_wali='Rina')
INVOICE=dict(invoice_id=1,no_invoice='INV-001',nama_program='Biologi SMA',jumlah=250000,
    invoice_status='belum_dibayar',payment_status=None,periode=date(2026,11,1),jatuh_tempo=date(2026,11,24))
PAID=dict(INVOICE,invoice_id=2,invoice_status='lunas',payment_status='lunas')
PAYMENT=dict(PAID,payment_id=10,kode_bayar='SIM-101',payment_jumlah=250000,paid_at=datetime(2026,11,26,10))
MESSAGE=dict(id=1,judul='Nilai baru diterbitkan',isi='Nilai kuis sudah tersedia.',sumber='sistem',related_type='grade',
    kategori='akademik',sudah_dibaca=False,created_at=datetime(2026,11,26,10))
ANNOUNCEMENT=dict(MESSAGE,id=2,judul='Pengumuman Tutor',sumber='tutor',kategori='pengumuman',nama_pembuat='Dewi')


def ok(v):return Mock(return_value=(True,v))


def academic(**kw):
    d=dict(kelas_saya=ok([CLASS,LOCK,OLD]),program_akademik=ok([ACTIVE_PROGRAM,LOCKED_PROGRAM]),
        jadwal_saya=ok([SLOT]),pertemuan_saya=ok([SESSION]),
        rekap_absensi=ok([RECAP]),riwayat_absensi=ok([SESSION]),
        ringkasan_nilai=ok([SCORE]),detail_nilai=ok([GRADE]),catatan_materi=ok([SESSION]),
        profil_saya=ok(PROFILE),ubah_profil=ok('Profil tersimpan.'),ganti_password=ok('Password diubah.'))
    d.update(kw)
    return SimpleNamespace(**d)


def billing(**kw):
    d=dict(daftar_tagihan_saya=Mock(return_value=[INVOICE,PAID]),
           riwayat_pembayaran_saya=Mock(return_value=[PAYMENT,dict(PAYMENT,payment_id=11,payment_status='direfund')]),
           bayar_simulasi=Mock(return_value=dict(PAYMENT,email_sent=False,email_message='Email belum dikirim')),
           bukti_pembayaran_saya=Mock(return_value=dict(PAYMENT,email_siswa='aulia@example.test')),
           buat_bukti_pembayaran_pdf=Mock(return_value=Path('bukti.pdf')),
           kirim_bukti_pembayaran_email=Mock(return_value={'sent':True,'message':'Bukti terkirim'}))
    d.update(kw)
    return SimpleNamespace(**d)


def notifications(**kw):
    d=dict(sinkronisasi_notifikasi=Mock(),jumlah_notifikasi_belum_dibaca=Mock(return_value=2),
           daftar_notifikasi_filter=Mock(return_value=[MESSAGE,ANNOUNCEMENT]),
           buka_notifikasi=Mock(return_value=MESSAGE),buka_notifikasi_arsip=Mock(return_value=ANNOUNCEMENT),
           arsipkan_notifikasi_pribadi=Mock(return_value=None),tandai_semua_dibaca=Mock(return_value=2))
    d.update(kw)
    return SimpleNamespace(**d)


def event(view,title):return next(e for e in view.events if e[0]==title)
def titles(view):return [e[0] for e in view.events]


class LayoutTests(unittest.TestCase):
    def test_table_bounds_and_selection(self):
        pairs=[(CATALOG,PROGRAM),(CLASSES,CLASS),(PROGRAMS,ACTIVE_PROGRAM),(SCHEDULE,SLOT),
               (SESSIONS,SESSION),(ATTENDANCE,SESSION),(GRADES,GRADE),(MATERIALS,SESSION),
               (INVOICES,INVOICE),(PAYMENTS,PAYMENT),(notification_table(),MESSAGE)]
        for table,row in pairs:
            for w in (8,14,18,30,44,60,74,100):
                for r in (None,row,{k:'漢字'*100 if isinstance(v,str) else v for k,v in row.items()}):
                    for selected in (False,True):
                        line=table(w,r,selected)
                        self.assertLessEqual(width_of(line),w,(table,row,w,line))

    def test_cards_and_empty_bounds(self):
        for w in (8,18,30,44,64,78,100):
            for b in (1,2,4,8,16,40):
                for pages in (attendance_pages(RECAP,w,b),grade_pages(SCORE,w,b),
                    billing_pages([INVOICE,PAID],w,b),attendance_pages(None,w,b),grade_pages(None,w,b),
                    billing_pages([],w,b),empty_pages('Belum ada data.','Arsip',width=w,budget=b),
                    details_pages(notification_sections(dict(MESSAGE,isi='漢字 '*400)),w,b,full=True,paired=True),
                    details_pages(session_sections(SESSION),w,b,full=True,paired=True),
                    notification_pages(dict(MESSAGE,isi='漢字 '*200+'\nAkhir'),w,b),
                    content_pages([], [('CATATAN','漢字 '*200)],w,b)):
                    self.assertTrue(pages)
                    for page in pages:
                        self.assertLessEqual(len(page),b)
                        for row in page:self.assertLessEqual(width_of(row),w)

    def test_full_details_and_real_projection(self):
        text='\n'.join(text_of(p) for p in details_pages(schedule_sections(SLOT,[SESSION],[CLASS]),100,40,full=True,paired=True))
        self.assertIn('PERKIRAAN',text)
        self.assertIn('bukan bukti',text)
        long='awal '+'kata '*250+'AKHIR_UNIK'
        for sections in (catalog_sections(dict(PROGRAM,deskripsi=long)),notification_sections(dict(MESSAGE,isi=long)),
                         session_sections(dict(SESSION,ringkasan=long))):
            text='\n'.join(text_of(p) for p in details_pages(sections,75,10,full=True,paired=True))
            self.assertIn('AKHIR_UNIK',text)

    def test_full_width_reading_panel_preserves_last_line(self):
        text='baris pertama\n\n'+'kata '*600+'AKHIR_UNIK'
        pages=notification_pages(dict(MESSAGE,isi=text),100,12)
        all_text='\n'.join(text_of(p) for p in pages)
        self.assertIn('baris pertama',all_text)
        self.assertIn('AKHIR_UNIK',all_text)
        self.assertIn('ISI PESAN',all_text)

    def test_real_table_enter_escape_refresh(self):
        for keys,expected in [('\r',5),('\x1b',None),('r','refresh')]:
            with create_pipe_input() as inp:
                w=StudentFeatureWorkspace('Aulia Rahma',input=inp,output=Output(28,100),motion_enabled=False)
                async def main(v):
                    async def drive():
                        try:
                            await asyncio.sleep(.07)
                            text='\n'.join(screen(v))
                            self.assertIn('Aulia Rahma · Siswa',text)
                            self.assertIn('Biologi SMA',text)
                            self.assertEqual(text.count('Biologi SMA'),1)
                            inp.send_text(keys)
                        except Exception as exc:v.app.exit(exception=exc)
                    v.app.create_background_task(drive())
                    return await v.record_table('KATALOG PROGRAM',[PROGRAM],key='id',renderer=CATALOG)
                self.assertEqual(w.run(main),expected)

    def test_real_empty_card(self):
        with create_pipe_input() as inp:
            w=StudentFeatureWorkspace('Aulia Rahma',input=inp,output=Output(24,100),motion_enabled=False)
            async def main(v):
                async def drive():
                    try:
                        await asyncio.sleep(.07)
                        t=screen(v)
                        self.assertIn('BELUM ADA DATA','\n'.join(t))
                        self.assertIn('Belum ada tagihan','\n'.join(t))
                        inp.send_text('r')
                    except Exception as exc:v.app.exit(exception=exc)
                v.app.create_background_task(drive())
                return await v.record_table('TAGIHAN SAYA',[],key='id',renderer=INVOICES,empty='Belum ada tagihan.')
            self.assertEqual(w.run(main),'refresh')


class AcademicFlows(unittest.IsolatedAsyncioTestCase):
    async def test_catalog_enrollment_confirm_and_filter(self):
        v=View([5,'register','confirm'])
        register=ok('Pendaftaran tercatat.')
        await AcademicController(v,academic()).catalog(USER,Mock(return_value=[PROGRAM,dict(PROGRAM,id=1)]),Mock(return_value=[CLASS]),register)
        register.assert_called_once_with(student_id=22,program_id=5)
        self.assertEqual([r['id'] for r in event(v,'KATALOG PROGRAM')[1]],[5])
        self.assertEqual(event(v,'KONFIRMASI PENDAFTARAN')[2]['default'],'back')

    async def test_catalog_cancel_refetch_and_empty(self):
        v=View([5,'register','back','refresh',None]);register=Mock()
        programs=Mock(return_value=[PROGRAM])
        await AcademicController(v,academic()).catalog(USER,programs,Mock(return_value=[]),register)
        self.assertEqual(programs.call_count,3)
        register.assert_not_called()
        v=View([None])
        await AcademicController(v,academic()).catalog(USER,Mock(return_value=[]),Mock(return_value=[]),register)
        self.assertFalse(event(v,'KATALOG PROGRAM')[1])

    async def test_class_locked_has_no_academic_reads(self):
        s=academic();v=View(['back'])
        await AcademicController(v,s).class_detail(LOCK)
        choices=event(v,'DETAIL KELAS')[1]
        self.assertEqual(choices,[('back','Kembali ke daftar')])
        s.jadwal_saya.assert_not_called();s.pertemuan_saya.assert_not_called()

    async def test_class_active_sessions_and_detail(self):
        s=academic();v=View(['sessions',1,'back',None,'back'])
        await AcademicController(v,s).class_detail(CLASS)
        s.pertemuan_saya.assert_called_with(1)
        self.assertIn('DETAIL PERTEMUAN',titles(v))
        self.assertIn('Riwayat pertemuan & materi',dict(event(v,'DETAIL KELAS')[1]).values())

    async def test_classes_history_read_only(self):
        s=academic();v=View(['history',OLD['enrollment_id'],'back',None,'back'])
        await AcademicController(v,s).classes()
        self.assertEqual([x['enrollment_id'] for x in event(v,'RIWAYAT PENDAFTARAN')[1]],[OLD['enrollment_id']])
        s.jadwal_saya.assert_not_called()

    async def test_locked_program_blocks_all_academic_apis(self):
        for route in ('attendance','grades','materials'):
            s=academic();v=View([LOCK['enrollment_id'],None])
            await getattr(AcademicController(v,s),route)()
            for k in ('rekap_absensi','ringkasan_nilai','catatan_materi'):
                getattr(s,k).assert_not_called()
            self.assertIn('AKSES KELAS TERBATAS',str(v.events))

    async def test_attendance_and_history(self):
        s=academic();v=View([A['enrollment_id'],'history',0,'back',None,'back'])
        await AcademicController(v,s).attendance()
        s.rekap_absensi.assert_called_with(1)
        s.riwayat_absensi.assert_called_with(1)
        self.assertIn('DETAIL ABSENSI',titles(v))

    async def test_grade_detail_and_report_cancel(self):
        s=academic();v=View([A['enrollment_id'],'detail',9,'back',None,'txt','back','back'])
        with patch('app.ui.menu_siswa_academic._save_rapor') as save:
            await AcademicController(v,s).grades()
            save.assert_not_called()
        self.assertIn('DETAIL NILAI',titles(v))

    async def test_grade_report_uses_fresh_checked_data(self):
        s=academic();v=View([A['enrollment_id'],'txt','confirm','back'])
        with patch('app.ui.menu_siswa_academic._save_rapor',return_value=Path('rapor/test.txt')) as save:
            await AcademicController(v,s).grades()
            save.assert_called_once_with(PROFILE,SCORE,[GRADE],1)
        self.assertGreaterEqual(s.ringkasan_nilai.call_count,2)

    async def test_material_detail(self):
        s=academic();v=View([A['enrollment_id'],1,'back',None])
        await AcademicController(v,s).materials()
        s.catatan_materi.assert_called_with(1)
        self.assertIn('DETAIL CATATAN MATERI',titles(v))

    async def test_schedule_scope_and_detail(self):
        hidden=dict(SLOT,schedule_id=99,program_id=LOCK['program_id'],nama_program='RAHASIA')
        s=academic(jadwal_saya=ok([SLOT,hidden]));v=View([1,'back',None])
        await AcademicController(v,s).schedule_list('JADWAL MINGGUAN')
        self.assertEqual([r['schedule_id'] for r in event(v,'JADWAL MINGGUAN')[1]],[1])
        s.pertemuan_saya.assert_called_once_with(1)

    async def test_profile_confirm_and_cancel(self):
        for decision in ('back','confirm'):
            s=academic();v=View(['edit',{'jenjang':'SMA','sekolah':'SMA 2'},
                {'no_hp':'08123','nama_wali':'Rina'},decision,'back'])
            await AcademicController(v,s).profile()
            if decision=='confirm':
                s.ubah_profil.assert_called_once_with({'jenjang':'SMA','sekolah':'SMA 2','no_hp':'08123','nama_wali':'Rina'})
            else:s.ubah_profil.assert_not_called()

    async def test_password_mismatch_and_masked_fields(self):
        s=academic();v=View(['password',{'old':'old'},{'new':'new','again':'wrong'},{'new':'new','again':'new'},'back'])
        await AcademicController(v,s).profile()
        forms=[e for e in v.events if e[0]=='GANTI PASSWORD']
        self.assertTrue(all(f.secret and not f.default for e in forms for f in e[1]))
        self.assertIn('tidak cocok',forms[-1][2]['notice'])
        s.ganti_password.assert_called_once_with('old','new')

    async def test_read_error_distinct_from_empty(self):
        s=academic(kelas_saya=Mock(return_value=(False,'Database gagal.')));v=View([])
        await AcademicController(v,s).classes()
        self.assertEqual(v.events,[('result',('DATA TIDAK TERSEDIA','Database gagal.','error'))])

    def test_report_content_and_safe_path(self):
        import os
        cwd=os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            try:
                os.chdir(d);path=_save_rapor(dict(PROFILE,nis='../nama'),SCORE,[GRADE],1)
                self.assertEqual(path.parent,Path('rapor'))
                self.assertIn('Kuis Fungsi',path.read_text())
                self.assertIn('NILAI AKHIR BERBOBOT: 85.50',path.read_text())
            finally:os.chdir(cwd)


class BillingFlows(unittest.IsolatedAsyncioTestCase):
    async def test_checkout_confirm_and_eligible(self):
        s=billing();v=View([1,'confirm','back'])
        await BillingController(v,s).checkout()
        s.daftar_tagihan_saya.assert_called_once_with(status='belum_dibayar')
        s.bayar_simulasi.assert_called_once_with(1)
        self.assertEqual([r['invoice_id'] for r in event(v,'CHECKOUT SIMULASI')[1]],[1])
        self.assertEqual(event(v,'KONFIRMASI CHECKOUT')[2]['default'],'back')
        self.assertIn('SIMULASI BERHASIL',titles(v))

    async def test_checkout_cancel_and_uncertain_no_auto_retry(self):
        s=billing();v=View([1,'back',None])
        await BillingController(v,s).checkout();s.bayar_simulasi.assert_not_called()
        s=billing(bayar_simulasi=Mock(side_effect=OSError()));v=View([1,'confirm'])
        await BillingController(v,s).checkout();s.bayar_simulasi.assert_called_once_with(1)
        self.assertIn('HASIL BELUM DIPASTIKAN',str(v.events))

    async def test_checkout_failure(self):
        s=billing(bayar_simulasi=Mock(return_value=dict(PAYMENT,payment_status='gagal',email_sent=False)))
        v=View([1,'confirm','back']);await BillingController(v,s).checkout()
        self.assertIn('SIMULASI GAGAL',titles(v))

    async def test_pdf_and_email_only_lunas(self):
        for mode in ('bukti_pdf','bukti_email'):
            s=billing();v=View([10,'confirm'])
            await BillingController(v,s).receipts(mode)
            self.assertEqual([r['payment_id'] for r in event(v,'BUKTI PEMBAYARAN')[1]],[10])
            if mode=='bukti_pdf':
                s.buat_bukti_pembayaran_pdf.assert_called_once_with(10)
                s.kirim_bukti_pembayaran_email.assert_not_called()
            else:
                s.bukti_pembayaran_saya.assert_called_once_with(10)
                s.kirim_bukti_pembayaran_email.assert_called_once_with(10)

    async def test_email_cancel_no_send(self):
        s=billing();v=View([10,'back',None]);await BillingController(v,s).receipts('bukti_email')
        s.kirim_bukti_pembayaran_email.assert_not_called()


class NotificationFlows(unittest.IsolatedAsyncioTestCase):
    async def test_quick_link_returns_old_route(self):
        s=notifications();v=View(['inbox',1,'open'])
        self.assertEqual(await NotificationController(v,s).run(),'nilai')
        s.buka_notifikasi.assert_called_once_with('siswa',1)
        s.sinkronisasi_notifikasi.assert_called_once_with('siswa')

    async def test_announcement_archive_only_and_private(self):
        s=notifications(buka_notifikasi=Mock(return_value=ANNOUNCEMENT));v=View(['archive','confirm'])
        await NotificationController(v,s).detail(ANNOUNCEMENT,False)
        self.assertNotIn('open',dict(event(v,'DETAIL NOTIFIKASI')[1]))
        s.arsipkan_notifikasi_pribadi.assert_called_once_with('siswa',2)

    async def test_archived_read_only_and_cancel(self):
        s=notifications();v=View(['back'])
        await NotificationController(v,s).detail(ANNOUNCEMENT,True)
        s.buka_notifikasi_arsip.assert_called_once_with('siswa',2)
        self.assertEqual(event(v,'DETAIL NOTIFIKASI')[1],[('back','Kembali ke daftar')])
        s.arsipkan_notifikasi_pribadi.assert_not_called()
        v=View(['archive','back','back'])
        await NotificationController(v,s).detail(MESSAGE,False)
        s.arsipkan_notifikasi_pribadi.assert_not_called()

    async def test_mark_all_confirm_and_refresh(self):
        s=notifications();v=View(['allread','confirm','refresh','back'])
        await NotificationController(v,s).run()
        s.tandai_semua_dibaca.assert_called_once_with('siswa')
        self.assertEqual(s.sinkronisasi_notifikasi.call_count,2)


if __name__=='__main__':unittest.main()
