"""UI-006 contract and terminal regression tests using fixture services."""
import asyncio
import unittest
from datetime import datetime,date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock,call
from prompt_toolkit.input import create_pipe_input
from app.ui.admin_confirmation import ConfirmationWorkspace
from app.ui.admin_workspace import width_of
from app.ui.admin_reporting import (
    ReportingController, dashboard_pages, report_row, report_detail_pages,
    announcement_row, announcement_pages, log_row, log_pages, document_pages, REPORT_MENU,
)
from test_ui003b_enrollment import View
from test_ui002_admin_workspace import Output,screen,text_of

NOW=datetime(2026,11,26,9,25)
TYPES=[dict(kode=k,judul=l) for k,l in REPORT_MENU[:3]]+[dict(kode='absensi_arsip',judul='Arsip Absensi Lama'),dict(kode='nilai',judul='Rata-rata Nilai per Program')]
REPORTS={}
def fixture(code,cols,rows):
    REPORTS[code]=dict(kode=code,judul=next(r['judul'] for r in TYPES if r['kode']==code),kolom=cols,data=rows)
fixture('pemasukan',[('bulan','Bulan'),('jumlah_transaksi','Jumlah Transaksi'),('total_pemasukan','Total Pemasukan')],
        [dict(bulan=date(2026,m,1),jumlah_transaksi=n,total_pemasukan=Decimal(n*250000)) for m,n in [(11,26),(10,22),(9,18),(8,20),(7,16),(6,12)]])
fixture('siswa_program',[(k,l) for k,l in [('kode_program','Kode'),('nama_program','Nama Program'),('jenjang','Jenjang'),('status_program','Status'),('kuota','Kuota'),('siswa_aktif','Siswa Aktif'),('menunggu','Menunggu'),('kuota_tersisa','Sisa Kuota')]],
        [dict(kode_program='MTK',nama_program='Matematika SMA',jenjang='SMA',status_program='buka',kuota=30,siswa_aktif=22,menunggu=3,kuota_tersisa=5)])
fixture('kehadiran',[(k,k.replace('_',' ').title()) for k in ['nis','nama_siswa','kode_program','nama_program','enrollment_id','status_enrollment','jenjang','total_pertemuan','hadir','izin','sakit','alpa','persen_hadir']],
        [dict(nis='S-0001',nama_siswa='Aulia Rahma',kode_program='MTK',nama_program='Matematika SMA',enrollment_id=11,status_enrollment='aktif',jenjang='SMA',total_pertemuan=10,hadir=8,izin=1,sakit=1,alpa=0,persen_hadir=80)])
fixture('nilai',[(k,k.replace('_',' ').title()) for k in ['kode_program','nama_program','jenjang','siswa_dinilai','rata_nilai_akhir']],
        [dict(kode_program='MTK',nama_program='Matematika SMA',jenjang='SMA',siswa_dinilai=21,rata_nilai_akhir=Decimal('86.45'))])
ANNOUNCEMENTS=[
    dict(id=12,judul='Jadwal kelas pengganti',isi='Kelas Matematika dipindah ke Sabtu pukul 09.00.\n\nMohon periksa jadwal terbaru.',target_roles=['siswa','tutor'],nama_pembuat='Fajar Ramadhan',created_at=NOW,archived_at=None),
    dict(id=11,judul='Informasi evaluasi November',isi='Evaluasi dilaksanakan pekan depan.',target_roles=['tutor'],nama_pembuat='Fajar Ramadhan',created_at=NOW,archived_at=None),
    dict(id=10,judul='Pengingat pembayaran',isi='Periksa tagihan di aplikasi.',target_roles=['siswa'],nama_pembuat='Fajar Ramadhan',created_at=NOW,archived_at=None),
]
ARCHIVE=[dict(ANNOUNCEMENTS[0],id=6,archived_at=NOW,judul='Informasi libur Oktober')]
LOGS=[dict(id=200-i,created_at=NOW,pengguna=user,username=user.lower().replace(' ','_'),user_id=3,aksi=aksi,detail=detail)
      for i,(user,aksi,detail) in enumerate([
          ('Fajar Ramadhan','LOGIN','Login admin berhasil.'),
          ('Aulia Rahma','LOGIN','Login siswa berhasil.'),
          ('Fajar Ramadhan','BUAT_PENGUMUMAN','Pengumuman ID 12: Jadwal kelas pengganti.'),
          ('Dewi Anggraini','LAPORAN_SESI','Laporan sesi Matematika tersimpan.'),
          ('Fajar Ramadhan','EKSPOR_LAPORAN','Ekspor pemasukan (xlsx).'),
          ('Aulia Rahma','LOGIN','Login siswa berhasil.')])]
def make_controller(**kwargs):
    args=dict(types=Mock(return_value=TYPES),report=Mock(side_effect=REPORTS.__getitem__),
              export_csv=Mock(return_value=Path('laporan/pemasukan.csv')),export_excel=Mock(return_value=Path('laporan/pemasukan.xlsx')),
              announcements=Mock(side_effect=lambda status,limit:ANNOUNCEMENTS if status=='aktif' else ARCHIVE),
              announcement_detail=Mock(side_effect=lambda id:next(x for x in ANNOUNCEMENTS+ARCHIVE if x['id']==id)),
              publish=Mock(return_value={'id':13}),archive=Mock(return_value=None),logs=Mock(return_value=LOGS),
              filter_logs=Mock(return_value=LOGS[:2]),is_admin=Mock(return_value=True))
    args.update(kwargs)
    return ReportingController(**args)

def flattened(pages):
    return '\n'.join(text_of(p) for p in pages)

class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_navigation_and_ai_return(self):
        c=make_controller()
        v=View(['laporan','back','pengumuman','back','log','back','ai'])
        self.assertEqual(await c.run(v),'ai')
        self.assertEqual([e[0] for e in v.events],['LAPORAN & KOMUNIKASI','PUSAT LAPORAN','LAPORAN & KOMUNIKASI','PUSAT KOMUNIKASI','LAPORAN & KOMUNIKASI','LOG AKTIVITAS','LAPORAN & KOMUNIKASI'])
        self.assertEqual([e[2]['default'] for e in v.events if e[0]=='LAPORAN & KOMUNIKASI'],['laporan','laporan','pengumuman','log'])
        c.publish.assert_not_called()

    async def test_each_report_refresh_and_detail(self):
        for code in REPORTS:
            c=make_controller()
            v=View([1,'back','refresh','back'])
            await c.browse_report(v,code)
            self.assertEqual(c.report.call_args_list,[call(code)]*3)
            self.assertEqual(v.events[-1][2]['initial'],1)
            detail=next(e for e in v.events if e[0]=='DETAIL LAPORAN')
            for key,_ in REPORTS[code]['kolom']:
                self.assertIn(key.replace('_',' ').lower()[:5],flattened(detail[3]).lower()) if code=='kehadiran' else None

    async def test_duplicate_rows(self):
        report=dict(REPORTS['nilai'],data=REPORTS['nilai']['data']*2)
        c=make_controller(report=Mock(return_value=report))
        v=View(['back'])
        await c.browse_report(v,'nilai')
        self.assertEqual([x['_ui_row'] for x in v.events[0][1]],[1,2])

    async def test_export_formats_archived_type_and_exact_result(self):
        for fmt in ('csv','xlsx'):
            c=make_controller()
            v=View(['absensi_arsip','confirm','back'])
            await c.export(v,fmt)
            self.assertIn(('absensi_arsip','Arsip Absensi Lama'),v.events[0][1])
            self.assertEqual(v.events[1][2]['default'],'back')
            exporter=c.export_csv if fmt=='csv' else c.export_excel
            exporter.assert_called_once_with('absensi_arsip')
            self.assertIn(str(exporter.return_value),flattened(v.events[-1][3]))

    async def test_cancel_export(self):
        c=make_controller()
        await c.export(View(['pemasukan','back']),'csv')
        c.export_csv.assert_not_called()

    async def test_export_failure(self):
        c=make_controller(export_csv=Mock(side_effect=OSError('secret')))
        v=View(['pemasukan','confirm'])
        await c.export(v,'csv')
        self.assertEqual(v.events[-1][1][0],'EKSPOR GAGAL')
        self.assertNotIn('secret',str(v.events[-1]))

    async def test_publish_roles_validation_and_paragraphs(self):
        for role,expected in [('siswa',['siswa']),('tutor',['tutor']),('both',['siswa','tutor'])]:
            c=make_controller()
            v=View([{'judul':'','isi':'x'},{'judul':' Jadwal ','isi':r'Baris 1\n\nBaris 2'},role,'confirm'])
            await c.create_announcement(v)
            self.assertTrue(v.events[1][2]['notice'])
            self.assertEqual(v.events[3][2]['default'],'back')
            c.publish.assert_called_once_with('Jadwal','Baris 1\n\nBaris 2',expected)

    async def test_cancel_and_ambiguous_publish(self):
        c=make_controller()
        await c.create_announcement(View([{'judul':'J','isi':'I'},'both','back']))
        c.publish.assert_not_called()
        c=make_controller(publish=Mock(side_effect=OSError()))
        v=View([{'judul':'J','isi':'I'},'both','confirm'])
        await c.create_announcement(v)
        c.publish.assert_called_once()
        self.assertEqual(v.events[-1][1][0],'HASIL BELUM DAPAT DIPASTIKAN')

    async def test_archive_confirm_and_reload(self):
        c=make_controller()
        v=View([12,'archive','confirm','back'])
        await c.browse_announcements(v,'aktif')
        c.archive.assert_called_once_with(12)
        self.assertEqual(c.announcements.call_args_list,[call(status='aktif',limit=500)]*2)
        self.assertEqual(v.events[2][2]['default'],'back')

    async def test_archive_cancel_and_archived(self):
        c=make_controller()
        await c.browse_announcements(View([12,'archive','back','back','back']),'aktif')
        v=View([6,'archive','back'])
        await c.browse_announcements(v,'arsip')
        self.assertNotIn(('archive','Arsipkan Pengumuman'),v.events[1][1])
        c.archive.assert_not_called()

    async def test_filter_logs_exact_and_refresh(self):
        c=make_controller()
        v=View([{'pengguna':' Aulia ','aksi':'LOGIN'},200,'back','filter',{'pengguna':'','aksi':''},'refresh','back'])
        await c.browse_logs(v,filtered=True)
        self.assertEqual(c.filter_logs.call_args_list,[call(pengguna='Aulia',aksi='LOGIN',limit=200)]*2+[call(pengguna='',aksi='',limit=200)]*2)
        self.assertTrue(v.events[-1][2]['filter_action'])
        self.assertEqual(v.events[3][2]['initial'],200)

    async def test_no_access(self):
        c=make_controller(is_admin=Mock(return_value=False))
        await c.run(View([]))
        await c.browse_report(View([]),'nilai')
        c.report.assert_not_called()
        c.logs.assert_not_called()

class RenderTests(unittest.TestCase):
    def test_empty_failure_and_cap(self):
        data=make_controller(announcements=Mock(side_effect=OSError()))._overview('root')
        pages=dashboard_pages(data,'root',100,40)
        self.assertIn('Data belum lengkap',flattened(pages))
        self.assertIn('Data gagal dimuat',flattened(pages))
        data=dict(types=TYPES,active=ANNOUNCEMENTS*200,logs=LOGS)
        self.assertIn('600+',flattened(dashboard_pages(data,'root',100,40)))

    def test_width_and_height(self):
        data=dict(types=TYPES,active=ANNOUNCEMENTS,archive=ARCHIVE,logs=LOGS)
        for w in (30,38,46,65,78,100):
            for b in (1,4,9,30):
                pages=[dashboard_pages(data,k,w,b) for k in ('root','laporan','pengumuman','log')]
                pages.extend([announcement_pages(ANNOUNCEMENTS[0],w,b),log_pages(LOGS[0],w,b)])
                pages.extend(report_detail_pages(r,r['data'][0],w,b) for r in REPORTS.values())
                for group in pages:
                    for page in group:
                        self.assertLessEqual(len(page),b)
                        for row in page:self.assertLessEqual(width_of(row),w)
            for r in REPORTS.values():
                self.assertLessEqual(width_of(report_row(r,w,r['data'][0],True)),w)
            for fn,row in [(announcement_row,ANNOUNCEMENTS[0]),(log_row,LOGS[0])]:
                self.assertLessEqual(width_of(fn(w,row,True)),w)

    def test_preserve_long_full_detail_and_control_sanitization(self):
        title='AWAL '+('panjang '*19)+'JUDULAKHIR'
        body='Baris pertama\n\n'+('isi panjang dan aman '*300)+'PENUTUP'
        pages=document_pages(title,body,[('Penerima','Siswa')],46,9)
        t=flattened(pages)
        self.assertIn('JUDULAKHIR',t)
        self.assertIn('PENUTUP',t)
        self.assertGreater(len(pages),10)
        self.assertNotIn('\x1b',flattened(document_pages('J','\x1b[31mdata',[],50,9)))

class KeyboardTests(unittest.TestCase):
    def test_actual_workspace_routes_ai_without_invoking_service(self):
        c=make_controller()
        with create_pipe_input() as inp:
            w=ConfirmationWorkspace('Demo Admin',input=inp,output=Output(32,108),motion_enabled=False)
            async def drive():
                try:
                    async def wait(title):
                        for _ in range(200):
                            if w.title==title and w.mode=='menu':
                                await asyncio.sleep(.05)
                                return
                            await asyncio.sleep(.01)
                        raise AssertionError((title,w.title,w.mode))
                    await wait('LAPORAN & KOMUNIKASI')
                    inp.send_text('\r')
                    await wait('PUSAT LAPORAN')
                    inp.send_text('\r')
                    await wait('PEMASUKAN PER BULAN')
                    inp.send_text('\r')
                    await wait('DETAIL LAPORAN')
                    self.assertIn('Rp6.500.000','\n'.join(screen(w)))
                    inp.send_text('\r')
                    await wait('PEMASUKAN PER BULAN')
                    inp.send_text('\x1b')
                    await wait('PUSAT LAPORAN')
                    inp.send_text('\x1b')
                    await wait('LAPORAN & KOMUNIKASI')
                    inp.send_text('\x1b[B'*3+'\r')
                except Exception as exc:
                    w.app.exit(exception=exc)
            async def main(view):
                view.app.create_background_task(drive())
                return await c.run(view)
            self.assertEqual(w.run(main),'ai')
        c.publish.assert_not_called()

if __name__=='__main__':
    unittest.main()
