"""Dashboard admin dan Pusat Konfirmasi akun SIBIMA."""

import psycopg
import questionary
from questionary import Choice, Separator, Style
from rich.align import Align
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markup import escape

from app import session
from app.repositories import user_repo, program_repo
from app.services import program_service, schedule_service
from app.ui import (
    menu_admin_data, menu_pembayaran, menu_admin_laporan, menu_admin_komunikasi,
)
from app.ui.console import (
    console,
    bersihkan_layar,
    gagal,
    info,
    peringatan,
    sukses,
)
from app.ui.admin_workspace import AdminDashboardNavigator


TEMA_ADMIN = Style([
    ("qmark", "fg:#00ffff bold"),
    ("question", "fg:#ffffff bold"),
    ("answer", "fg:#00ffff bold"),
    ("pointer", "fg:#00ffff bold"),
    ("highlighted", "fg:#00ffff bold"),
    ("selected", "fg:#00ffff"),
    ("separator", "fg:#444444"),
    ("instruction", "fg:#888888 italic"),
])


MENU_ADMIN = [
    ("Pusat Konfirmasi", "konfirmasi"),
    ("Manajemen Akun", "akun"),
    ("Data Siswa", "siswa"),
    ("Data Tutor", "tutor"),
    ("Program dan Ruang", "program"),
    ("Pendaftaran", "pendaftaran"),
    ("Jadwal", "jadwal"),
    ("Pembayaran", "pembayaran"),
    ("Laporan", "laporan"),
    ("Komunikasi", "pengumuman"),
    ("Log Aktivitas", "log"),
]


def _format_waktu(nilai):
    if nilai is None:
        return "-"
    try:
        return nilai.strftime("%d %b %Y %H:%M")
    except (AttributeError, ValueError):
        return str(nilai)


def _tampilkan_header(halaman: str, subtitle: str):
    console.print(
        Panel(
            Align.center(
                f"[bold cyan]S I B I M A[/bold cyan]\n"
                f"[bold white]{halaman.upper()}[/bold white]\n"
                f"[dim]{subtitle}[/dim]"
            ),
            border_style="cyan",
            padding=(1, 4),
            expand=True,
        )
    )


def _format_rupiah(nilai) -> str:
    try:
        return "Rp " + f"{nilai:,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(nilai)


def menu_konfirmasi():
    """UI-003A: workspace konfirmasi, kembali ke Prioritas saat keluar."""
    from app.ui.admin_confirmation import menu_konfirmasi as buka_konfirmasi
    return buka_konfirmasi()


def _tampilkan_modul_belum_tersedia(nama_modul: str):
    bersihkan_layar()
    _tampilkan_header("Modul Admin", nama_modul)
    console.print(
        Panel(
            f"[bold yellow]{nama_modul}[/bold yellow]\n\n"
            "[white]Modul ini masih dalam tahap pengembangan.[/white]\n"
            "[dim]Belum ada operasi bisnis yang dijalankan dari halaman ini.[/dim]",
            border_style="yellow",
            padding=(1, 3),
            expand=True,
        )
    )
    input("Tekan Enter untuk kembali ke dashboard...")



# ---------------------------------------------------------------------------
# Program, ruang, dan pengelolaan pendaftaran
# ---------------------------------------------------------------------------


def _tekan_enter(pesan="Tekan Enter untuk kembali..."):
    input(pesan)


def _pilih_program_admin(daftar=None, pertanyaan="Pilih program:"):
    """Pilih program berdasarkan ID; tidak mengembalikan ID program dari teks."""
    try:
        program = daftar if daftar is not None else program_repo.daftar_program_dengan_kuota()
    except psycopg.Error as exc:
        gagal("Gagal membaca data program dari database.")
        info(f"Jenis error: {type(exc).__name__}")
        _tekan_enter()
        return None

    if not program:
        peringatan("Belum ada program yang tersedia.")
        _tekan_enter()
        return None

    pilihan = [
        Choice(
            f"ID {item['id']} • {item['kode']} • {item['nama']} • "
            f"{item['status']} • kuota {item.get('sisa', '-')} tersisa",
            value=item["id"],
        )
        for item in program
    ]
    pilihan.extend([
        Separator("────────────────────────"),
        Choice("↩  Kembali", value="__kembali__"),
    ])
    nilai = questionary.select(
        pertanyaan, choices=pilihan, style=TEMA_ADMIN,
        qmark="⚡", pointer="▶", instruction=" (Gunakan ↑/↓ lalu Enter)",
    ).ask()
    return nilai if type(nilai) is int else None


def _tabel_program_admin(daftar):
    tabel = Table(
        title="Program Bimbel dan Kuota",
        header_style="bold cyan", border_style="blue", expand=True,
    )
    tabel.add_column("ID", justify="right", no_wrap=True)
    tabel.add_column("Kode", no_wrap=True)
    tabel.add_column("Nama Program", min_width=18)
    tabel.add_column("Jenjang", no_wrap=True)
    tabel.add_column("Harga/Bulan", justify="right", no_wrap=True)
    tabel.add_column("Terisi", justify="right")
    tabel.add_column("Sisa", justify="right")
    tabel.add_column("Status", no_wrap=True)
    for item in daftar:
        status = "[green]BUKA[/green]" if item["status"] == "buka" else "[yellow]TUTUP[/yellow]"
        tabel.add_row(
            str(item["id"]), str(item["kode"]), str(item["nama"]),
            str(item["jenjang"]), _format_rupiah(item["harga_bulanan"]),
            str(item.get("terisi", 0)), str(item.get("sisa", item["kuota"])), status,
        )
    console.print(tabel)


def _program_daftar_admin():
    bersihkan_layar()
    _tampilkan_header("Program dan Ruang", "DAFTAR PROGRAM DAN KUOTA")
    try:
        daftar = program_repo.daftar_program_dengan_kuota()
        if not daftar:
            peringatan("Belum ada program bimbel.")
        else:
            _tabel_program_admin(daftar)
    except psycopg.Error as exc:
        gagal("Gagal membaca daftar program.")
        info(f"Jenis error: {type(exc).__name__}")
    _tekan_enter()


def _program_tambah_admin():
    bersihkan_layar()
    _tampilkan_header("Program dan Ruang", "TAMBAH PROGRAM")
    console.print(Panel(
        "Bobot nilai awal: Tugas 30%, Kuis 20%, UTS 20%, UAS 30%. "
        "Total bobot harus 100%; bobot dapat diubah setelah program dibuat.",
        border_style="blue", padding=(1, 2), expand=True,
    ))
    kode = questionary.text("Kode program (maks. 10 karakter):", style=TEMA_ADMIN).ask()
    if kode is None:
        return
    nama = questionary.text("Nama program:", style=TEMA_ADMIN).ask()
    if nama is None:
        return
    jenjang = questionary.text("Jenjang (contoh: SMP, SMA, Umum):", style=TEMA_ADMIN).ask()
    if jenjang is None:
        return
    deskripsi = questionary.text("Deskripsi (opsional):", style=TEMA_ADMIN).ask()
    if deskripsi is None:
        return
    harga = questionary.text("Harga bulanan (contoh 250000):", style=TEMA_ADMIN).ask()
    if harga is None:
        return
    kuota = questionary.text("Kuota siswa (angka bulat):", style=TEMA_ADMIN).ask()
    if kuota is None:
        return
    yakin = questionary.confirm(
        f"Buat program {nama.strip() or '(tanpa nama)'}?", default=False, style=TEMA_ADMIN,
    ).ask()
    if yakin is not True:
        info("Penambahan program dibatalkan.")
        _tekan_enter()
        return
    berhasil, pesan = program_service.buat_program({
        "kode": kode, "nama": nama, "jenjang": jenjang,
        "deskripsi": deskripsi, "harga_bulanan": harga, "kuota": kuota,
    })
    sukses(pesan) if berhasil else gagal(pesan)
    _tekan_enter()


def _program_ubah_admin():
    bersihkan_layar()
    _tampilkan_header("Program dan Ruang", "UBAH DATA PROGRAM")
    try:
        daftar = program_repo.daftar_program_dengan_kuota()
    except psycopg.Error as exc:
        gagal("Gagal membaca daftar program.")
        info(f"Jenis error: {type(exc).__name__}")
        _tekan_enter()
        return
    program_id = _pilih_program_admin(daftar, "Pilih program yang ingin diubah:")
    if program_id is None:
        return
    item = next((x for x in daftar if x["id"] == program_id), None)
    if item is None:
        peringatan("Program tidak ditemukan; silakan muat ulang.")
        _tekan_enter()
        return

    bidang = questionary.select(
        f"Data yang akan diubah — {item['kode']} / {item['nama']}",
        choices=[
            Choice("Kode program", value="kode"),
            Choice("Nama program", value="nama"),
            Choice("Jenjang", value="jenjang"),
            Choice("Deskripsi", value="deskripsi"),
            Choice("Harga bulanan", value="harga_bulanan"),
            Choice("Kuota", value="kuota"),
            Choice("Bobot nilai (semua komponen sekaligus)", value="bobot"),
            Separator("────────────────────────"),
            Choice("Kembali", value="kembali"),
        ], style=TEMA_ADMIN, qmark="⚡", pointer="▶",
    ).ask()
    if bidang is None or bidang == "kembali":
        return

    perubahan = {}
    if bidang == "bobot":
        for kolom, label in [
            ("bobot_tugas", "Bobot tugas (%)"),
            ("bobot_kuis", "Bobot kuis (%)"),
            ("bobot_uts", "Bobot UTS (%)"),
            ("bobot_uas", "Bobot UAS (%)"),
        ]:
            nilai = questionary.text(
                f"{label} (saat ini {item[kolom]}):", default=str(item[kolom]), style=TEMA_ADMIN,
            ).ask()
            if nilai is None:
                return
            perubahan[kolom] = nilai
    else:
        label = {
            "kode": "Kode program", "nama": "Nama program", "jenjang": "Jenjang",
            "deskripsi": "Deskripsi (kosongkan untuk menghapus deskripsi)",
            "harga_bulanan": "Harga bulanan", "kuota": "Kuota siswa",
        }[bidang]
        default = "" if bidang == "deskripsi" and item.get(bidang) is None else str(item.get(bidang, ""))
        nilai = questionary.text(f"{label}:", default=default, style=TEMA_ADMIN).ask()
        if nilai is None:
            return
        if bidang == "deskripsi" and not nilai.strip():
            perubahan[bidang] = None
        else:
            perubahan[bidang] = nilai

    berhasil, pesan = program_service.ubah_program(program_id, perubahan)
    sukses(pesan) if berhasil else gagal(pesan)
    _tekan_enter()


def _program_toggle_admin():
    bersihkan_layar()
    _tampilkan_header("Program dan Ruang", "TUTUP / BUKA PROGRAM")
    try:
        daftar = program_repo.daftar_program_dengan_kuota()
    except psycopg.Error as exc:
        gagal("Gagal membaca daftar program.")
        info(f"Jenis error: {type(exc).__name__}")
        _tekan_enter()
        return
    program_id = _pilih_program_admin(daftar, "Pilih program:")
    if program_id is None:
        return
    item = next((x for x in daftar if x["id"] == program_id), None)
    if item is None:
        return
    status_baru = "tutup" if item["status"] == "buka" else "buka"
    aksi = "menutup" if status_baru == "tutup" else "membuka kembali"
    yakin = questionary.confirm(
        f"Yakin {aksi} program {item['nama']}?", default=False, style=TEMA_ADMIN,
    ).ask()
    if yakin is not True:
        info("Perubahan status dibatalkan.")
        _tekan_enter()
        return
    berhasil, pesan = program_service.ubah_program(program_id, {"status": status_baru})
    sukses(pesan) if berhasil else gagal(pesan)
    _tekan_enter()


def _ruang_daftar_admin():
    bersihkan_layar()
    _tampilkan_header("Program dan Ruang", "DAFTAR RUANG BELAJAR")
    try:
        daftar = program_repo.daftar_ruang()
        tabel = Table(title="Ruang Belajar", header_style="bold cyan", border_style="blue", expand=True)
        tabel.add_column("ID", justify="right")
        tabel.add_column("Nama Ruang")
        tabel.add_column("Kapasitas", justify="right")
        tabel.add_column("Status", justify="center")
        for item in daftar:
            tabel.add_row(
                str(item["id"]), str(item["nama"]), str(item["kapasitas"]),
                "[green]Aktif[/green]" if item["aktif"] else "[yellow]Nonaktif[/yellow]",
            )
        if daftar:
            console.print(tabel)
        else:
            peringatan("Belum ada ruang belajar.")
    except psycopg.Error as exc:
        gagal("Gagal membaca daftar ruang.")
        info(f"Jenis error: {type(exc).__name__}")
    _tekan_enter()


def _ruang_tambah_admin():
    bersihkan_layar()
    _tampilkan_header("Program dan Ruang", "TAMBAH RUANG")
    nama = questionary.text("Nama ruang (maks. 30 karakter):", style=TEMA_ADMIN).ask()
    if nama is None:
        return
    kapasitas = questionary.text("Kapasitas ruang:", style=TEMA_ADMIN).ask()
    if kapasitas is None:
        return
    berhasil, pesan = program_service.buat_ruang(nama, kapasitas)
    sukses(pesan) if berhasil else gagal(pesan)
    _tekan_enter()


def _ruang_ubah_admin():
    bersihkan_layar()
    _tampilkan_header("Program dan Ruang", "UBAH RUANG")
    try:
        daftar = program_repo.daftar_ruang()
    except psycopg.Error as exc:
        gagal("Gagal membaca daftar ruang.")
        info(f"Jenis error: {type(exc).__name__}")
        _tekan_enter()
        return
    if not daftar:
        peringatan("Belum ada ruang untuk diubah.")
        _tekan_enter()
        return
    pilihan = questionary.select(
        "Pilih ruang:",
        choices=[Choice(f"ID {x['id']} • {x['nama']} • kapasitas {x['kapasitas']}", value=x["id"]) for x in daftar]
        + [Separator("────────────────────────"), Choice("Kembali", value="kembali")],
        style=TEMA_ADMIN, qmark="⚡", pointer="▶",
    ).ask()
    if type(pilihan) is not int:
        return
    ruang = next((x for x in daftar if x["id"] == pilihan), None)
    if ruang is None:
        return
    nama = questionary.text("Nama ruang:", default=str(ruang["nama"]), style=TEMA_ADMIN).ask()
    if nama is None:
        return
    kapasitas = questionary.text("Kapasitas:", default=str(ruang["kapasitas"]), style=TEMA_ADMIN).ask()
    if kapasitas is None:
        return
    berhasil, pesan = program_service.ubah_ruang(pilihan, {"nama": nama, "kapasitas": kapasitas})
    sukses(pesan) if berhasil else gagal(pesan)
    _tekan_enter()


def menu_program_ruang():
    """Submenu program dan ruang sesuai rancangan MENU_CLI.md."""
    if not session.punya_role("admin"):
        peringatan("Akses ditolak. Silakan login sebagai admin.")
        return
    pilihan_aksi = {
        "daftar_program": _program_daftar_admin,
        "tambah_program": _program_tambah_admin,
        "ubah_program": _program_ubah_admin,
        "toggle_program": _program_toggle_admin,
        "daftar_ruang": _ruang_daftar_admin,
        "tambah_ruang": _ruang_tambah_admin,
        "ubah_ruang": _ruang_ubah_admin,
    }
    while session.punya_role("admin"):
        bersihkan_layar()
        _tampilkan_header("Program dan Ruang", "MANAJEMEN MASTER DATA")
        pilihan = questionary.select(
            "Pilih tindakan:",
            choices=[
                Choice("Daftar program (kuota terisi / sisa)", value="daftar_program"),
                Choice("Tambah program", value="tambah_program"),
                Choice("Ubah program (harga, kuota, bobot nilai)", value="ubah_program"),
                Choice("Tutup / buka program", value="toggle_program"),
                Separator("──────────── RUANG BELAJAR ────────────"),
                Choice("Daftar ruang", value="daftar_ruang"),
                Choice("Tambah ruang", value="tambah_ruang"),
                Choice("Ubah ruang", value="ubah_ruang"),
                Separator("────────────────────────"),
                Choice("Kembali ke dashboard", value="kembali"),
            ], style=TEMA_ADMIN, qmark="⚡", pointer="▶",
            instruction=" (Gunakan ↑/↓ lalu Enter)",
        ).ask()
        if pilihan is None or pilihan == "kembali":
            return
        aksi = pilihan_aksi.get(pilihan)
        if aksi:
            aksi()



# ---------------------------------------------------------------------------
# Jadwal reguler: lihat/filter, tambah, ubah, dan nonaktifkan
# ---------------------------------------------------------------------------

_HARI_JADWAL = [
    ("Senin", "senin"), ("Selasa", "selasa"), ("Rabu", "rabu"),
    ("Kamis", "kamis"), ("Jumat", "jumat"), ("Sabtu", "sabtu"),
    ("Minggu", "minggu"),
]


def _tabel_jadwal_admin(daftar, judul="Jadwal Mengajar"):
    tabel = Table(title=judul, header_style="bold cyan", border_style="blue", expand=True)
    for nama, kwargs in [
        ("ID", {"justify": "right", "no_wrap": True}),
        ("Hari", {"no_wrap": True}),
        ("Waktu", {"no_wrap": True}),
        ("Program", {"overflow": "fold"}),
        ("Tutor", {"overflow": "fold"}),
        ("Ruang", {"no_wrap": True}),
        ("Siswa", {"justify": "right", "no_wrap": True}),
        ("Sesi tercatat", {"justify": "right", "no_wrap": True}),
        ("Kapasitas", {"justify": "right", "no_wrap": True}),
        ("Status", {"no_wrap": True}),
    ]:
        tabel.add_column(nama, **kwargs)
    for item in daftar:
        status = "[green]AKTIF[/green]" if item["aktif"] else "[dim]NONAKTIF[/dim]"
        tabel.add_row(
            str(item["id"]), str(item["hari"]).capitalize(),
            f"{item['jam_mulai'].strftime('%H:%M')}-{item['jam_selesai'].strftime('%H:%M')}",
            f"{item.get('kode_program') or '-'} — {item.get('nama_program') or '-'}",
            f"{item.get('kode_tutor') or '-'} — {item.get('nama_tutor') or '-'}",
            str(item.get("nama_ruang") or "-"), str(item.get("jumlah_siswa", 0)),
            str(item.get("jumlah_pertemuan", 0)), str(item.get("kapasitas_ruang", "-")), status,
        )
    console.print(tabel)


def _ambil_opsi_jadwal(jenis, pertanyaan, aktif_saja=True):
    fungsi = {
        "program": schedule_service.opsi_program,
        "tutor": schedule_service.opsi_tutor,
        "ruang": schedule_service.opsi_ruang,
    }[jenis]
    berhasil, hasil = fungsi(aktif_saja=aktif_saja)
    if not berhasil:
        gagal(hasil)
        _tekan_enter()
        return None
    if not hasil:
        peringatan({"program": "Belum ada program terbuka.", "tutor": "Belum ada tutor aktif.", "ruang": "Belum ada ruang aktif."}[jenis])
        _tekan_enter()
        return None

    def label(item):
        if jenis == "program":
            return f"ID {item['id']} • {item['kode']} • {item['nama']} ({item['jenjang']})"
        if jenis == "tutor":
            kode = item.get("kode_tutor") or "tanpa kode"
            return f"ID {item['id']} • {kode} • {item['nama_lengkap']}"
        return f"ID {item['id']} • {item['nama']} • kapasitas {item['kapasitas']}"

    pilihan = questionary.select(
        pertanyaan,
        choices=[Choice(label(item), value=item["id"]) for item in hasil]
        + [Separator("────────────────────────"), Choice("Kembali", value="kembali")],
        style=TEMA_ADMIN, qmark="⚡", pointer="▶",
        instruction=" (Gunakan ↑/↓ lalu Enter)",
    ).ask()
    return pilihan if type(pilihan) is int else None


def _pilih_hari_jadwal(pertanyaan="Pilih hari:"):
    hasil = questionary.select(
        pertanyaan,
        choices=[Choice(label, value=value) for label, value in _HARI_JADWAL]
        + [Separator("────────────────────────"), Choice("Kembali", value="kembali")],
        style=TEMA_ADMIN, qmark="⚡", pointer="▶",
    ).ask()
    return hasil if hasil in {value for _, value in _HARI_JADWAL} else None


def _pilih_satu_jadwal(pertanyaan, *, hanya_aktif=None):
    berhasil, hasil = schedule_service.daftar_jadwal(aktif=hanya_aktif)
    if not berhasil:
        gagal(hasil)
        _tekan_enter()
        return None
    if not hasil:
        peringatan("Tidak ada jadwal yang cocok.")
        _tekan_enter()
        return None
    _tabel_jadwal_admin(hasil)
    pilihan = questionary.select(
        pertanyaan,
        choices=[Choice(
            f"ID {x['id']} • {x['hari'].capitalize()} {x['jam_mulai'].strftime('%H:%M')}-"
            f"{x['jam_selesai'].strftime('%H:%M')} • {x['nama_program']} • {x['nama_tutor']} • {x['nama_ruang']}",
            value=x["id"],
        ) for x in hasil] + [Separator("────────────────────────"), Choice("Kembali", value="kembali")],
        style=TEMA_ADMIN, qmark="⚡", pointer="▶",
    ).ask()
    if type(pilihan) is not int:
        return None
    return next((x for x in hasil if x["id"] == pilihan), None)


def _detail_jadwal_admin(item):
    """Detail read-only; tidak mengartikan jumlah catatan sebagai sesi selesai."""
    bersihkan_layar()
    _tampilkan_header("Detail Jadwal", str(item.get("nama_program") or "—"))
    konten = (
        f"[bold]Program[/bold]       : {escape(str(item.get('nama_program') or '—'))} "
        f"({escape(str(item.get('kode_program') or '—'))})\n"
        f"[bold]Tutor[/bold]         : {escape(str(item.get('nama_tutor') or '—'))}\n"
        f"[bold]Ruang[/bold]         : {escape(str(item.get('nama_ruang') or '—'))}\n"
        f"[bold]Jadwal rutin[/bold] : {escape(str(item.get('hari') or '—').capitalize())} "
        f"{item['jam_mulai'].strftime('%H:%M')}–{item['jam_selesai'].strftime('%H:%M')}\n"
        f"[bold]Status jadwal[/bold]: {'Aktif' if item.get('aktif') else 'Nonaktif'}\n"
        f"[bold]Peserta program[/bold]: {item.get('jumlah_siswa') or 0} enrollment aktif\n"
        f"[bold]Sesi tercatat[/bold]: {item.get('jumlah_pertemuan') or 0} (termasuk sesi dibatalkan)"
    )
    console.print(Panel(konten, title="RINCIAN KELAS & JADWAL", border_style="cyan", expand=True))
    info("Peserta dihitung per program, bukan per jadwal. Sesi tercatat tidak menjamin absensi lengkap.")
    _tekan_enter()


def _label_opsi_jadwal(jenis, identitas):
    """Nama untuk ringkasan konfirmasi; fallback ID bila daftar tidak bisa dimuat."""
    panggil = {"program": schedule_service.opsi_program,
              "tutor": schedule_service.opsi_tutor,
              "ruang": schedule_service.opsi_ruang}[jenis]
    try:
        ok, rows = panggil(aktif_saja=False)
        if ok:
            item = next((r for r in rows if r.get("id") == identitas), None)
            if item:
                return str(item.get("nama") or item.get("nama_lengkap") or f"ID {identitas}")
    except Exception:
        pass
    return f"ID {identitas}"


def _jadwal_lihat_admin():
    bersihkan_layar()
    _tampilkan_header("Jadwal", "LIHAT JADWAL PER PROGRAM / TUTOR / RUANG / HARI")
    kategori = questionary.select(
        "Tampilkan jadwal berdasarkan:",
        choices=[
            Choice("Semua jadwal", "semua"), Choice("Per program", "program"),
            Choice("Per tutor", "tutor"), Choice("Per ruang", "ruang"),
            Choice("Per hari", "hari"),
            Separator("────────────────────────"), Choice("Kembali", "kembali"),
        ], style=TEMA_ADMIN, qmark="⚡", pointer="▶",
    ).ask()
    if kategori is None or kategori == "kembali":
        return
    filters = {}
    if kategori in {"program", "tutor", "ruang"}:
        identitas = _ambil_opsi_jadwal(kategori, f"{('Pilih ' + kategori)} untuk filter:", aktif_saja=False)
        if identitas is None:
            return
        filters[{"program": "program_id", "tutor": "tutor_id", "ruang": "room_id"}[kategori]] = identitas
    elif kategori == "hari":
        hari = _pilih_hari_jadwal("Pilih hari yang ingin dilihat:")
        if hari is None:
            return
        filters["hari"] = hari

    berhasil, hasil = schedule_service.daftar_jadwal(**filters)
    bersihkan_layar()
    _tampilkan_header("Jadwal", "HASIL DAFTAR JADWAL")
    if not berhasil:
        gagal(hasil)
    elif not hasil:
        peringatan("Belum ada jadwal untuk filter tersebut.")
    else:
        _tabel_jadwal_admin(hasil)
        selected = questionary.select("Lihat detail jadwal:", choices=[
            Choice(f"{r.get('nama_program') or '—'} • {str(r.get('hari') or '').capitalize()} "
                   f"{r['jam_mulai'].strftime('%H:%M')}–{r['jam_selesai'].strftime('%H:%M')} "
                   f"• {r.get('nama_tutor') or '—'}", value=r["id"]) for r in hasil
        ] + [Choice("Kembali", value="__back__")], style=TEMA_ADMIN,
            qmark="⚡", pointer="▶").ask()
        if selected not in (None, "__back__"):
            row = next((r for r in hasil if r["id"] == selected), None)
            if row:
                _detail_jadwal_admin(row)
        return
    _tekan_enter()


def _jadwal_tambah_admin():
    bersihkan_layar()
    _tampilkan_header("Jadwal", "TAMBAH JADWAL MENGAJAR")
    program_id = _ambil_opsi_jadwal("program", "Pilih program yang dijadwalkan:")
    if program_id is None:
        return
    tutor_id = _ambil_opsi_jadwal("tutor", "Pilih tutor:")
    if tutor_id is None:
        return
    room_id = _ambil_opsi_jadwal("ruang", "Pilih ruang:")
    if room_id is None:
        return
    hari = _pilih_hari_jadwal()
    if hari is None:
        return
    jam_mulai = questionary.text("Jam mulai (HH:MM, contoh 15:00):", style=TEMA_ADMIN).ask()
    if jam_mulai is None:
        return
    jam_selesai = questionary.text("Jam selesai (HH:MM, contoh 16:30):", style=TEMA_ADMIN).ask()
    if jam_selesai is None:
        return
    console.print(Panel(
        f"Program: {escape(_label_opsi_jadwal('program', program_id))} (ID {program_id})\n"
        f"Tutor: {escape(_label_opsi_jadwal('tutor', tutor_id))} (ID {tutor_id})\n"
        f"Ruang: {escape(_label_opsi_jadwal('ruang', room_id))} (ID {room_id})\n"
        f"Hari: {escape(hari.capitalize())}\nWaktu: {escape(jam_mulai)}–{escape(jam_selesai)}",
        title="Ringkasan Jadwal", border_style="cyan", padding=(1, 2), expand=True,
    ))
    yakin = questionary.confirm("Simpan jadwal ini?", default=False, style=TEMA_ADMIN).ask()
    if yakin is not True:
        info("Pembuatan jadwal dibatalkan.")
        _tekan_enter()
        return
    berhasil, pesan = schedule_service.buat_jadwal({
        "program_id": program_id, "tutor_id": tutor_id, "room_id": room_id,
        "hari": hari, "jam_mulai": jam_mulai, "jam_selesai": jam_selesai,
    })
    sukses(pesan) if berhasil else gagal(pesan)
    _tekan_enter()


def _jadwal_ubah_admin():
    bersihkan_layar()
    _tampilkan_header("Jadwal", "UBAH JADWAL")
    item = _pilih_satu_jadwal("Pilih jadwal yang ingin diubah:", hanya_aktif=True)
    if item is None:
        return
    bidang = questionary.select(
        f"Pilih bagian jadwal ID {item['id']} yang ingin diubah:",
        choices=[
            Choice("Program", "program_id"), Choice("Tutor", "tutor_id"),
            Choice("Ruang", "room_id"), Choice("Hari", "hari"),
            Choice("Jam mulai", "jam_mulai"), Choice("Jam selesai", "jam_selesai"),
            Separator("────────────────────────"), Choice("Kembali", "kembali"),
        ], style=TEMA_ADMIN, qmark="⚡", pointer="▶",
    ).ask()
    if bidang is None or bidang == "kembali":
        return
    data = {}
    if bidang in {"program_id", "tutor_id", "room_id"}:
        jenis = {"program_id": "program", "tutor_id": "tutor", "room_id": "ruang"}[bidang]
        nilai = _ambil_opsi_jadwal(jenis, f"Pilih {jenis} yang baru:")
        if nilai is None:
            return
        data[bidang] = nilai
    elif bidang == "hari":
        nilai = _pilih_hari_jadwal("Pilih hari yang baru:")
        if nilai is None:
            return
        data[bidang] = nilai
    else:
        waktu_lama = item[bidang].strftime("%H:%M")
        nilai = questionary.text(
            f"{('Jam mulai' if bidang == 'jam_mulai' else 'Jam selesai')} baru (HH:MM):",
            default=waktu_lama, style=TEMA_ADMIN,
        ).ask()
        if nilai is None:
            return
        data[bidang] = nilai
    yakin = questionary.confirm("Simpan perubahan jadwal?", default=False, style=TEMA_ADMIN).ask()
    if yakin is not True:
        info("Perubahan jadwal dibatalkan.")
        _tekan_enter()
        return
    berhasil, pesan = schedule_service.ubah_jadwal(item["id"], data)
    sukses(pesan) if berhasil else gagal(pesan)
    _tekan_enter()


def _jadwal_nonaktifkan_admin():
    bersihkan_layar()
    _tampilkan_header("Jadwal", "NONAKTIFKAN JADWAL")
    item = _pilih_satu_jadwal("Pilih jadwal yang akan dinonaktifkan:", hanya_aktif=True)
    if item is None:
        return
    detail = (
        f"{item['hari'].capitalize()} {item['jam_mulai'].strftime('%H:%M')}-"
        f"{item['jam_selesai'].strftime('%H:%M')} • {item['nama_program']} • {item['nama_tutor']}"
    )
    yakin = questionary.confirm(
        f"Nonaktifkan jadwal ID {item['id']}? {detail}. Riwayat pertemuan tidak dihapus.",
        default=False, style=TEMA_ADMIN,
    ).ask()
    if yakin is not True:
        info("Penonaktifan jadwal dibatalkan.")
        _tekan_enter()
        return
    berhasil, pesan = schedule_service.nonaktifkan_jadwal(item["id"])
    sukses(pesan) if berhasil else gagal(pesan)
    _tekan_enter()


def menu_jadwal_admin():
    """Submenu jadwal admin menurut rancangan MENU_CLI.md."""
    if not session.punya_role("admin"):
        peringatan("Akses ditolak. Login sebagai admin terlebih dahulu.")
        return
    aksi = {
        "lihat": _jadwal_lihat_admin,
        "tambah": _jadwal_tambah_admin,
        "ubah": _jadwal_ubah_admin,
        "nonaktif": _jadwal_nonaktifkan_admin,
    }
    while session.punya_role("admin"):
        bersihkan_layar()
        _tampilkan_header("Jadwal", "MANAJEMEN JADWAL MENGAJAR")
        pilihan = questionary.select(
            "Pilih tindakan:",
            choices=[
                Choice("Lihat jadwal (per program / tutor / ruang / hari)", "lihat"),
                Choice("Tambah jadwal", "tambah"), Choice("Ubah jadwal", "ubah"),
                Choice("Nonaktifkan jadwal", "nonaktif"),
                Separator("────────────────────────"), Choice("Kembali ke dashboard", "kembali"),
            ], style=TEMA_ADMIN, qmark="⚡", pointer="▶",
            instruction=" (Gunakan ↑/↓ lalu Enter)",
        ).ask()
        if pilihan is None or pilihan == "kembali":
            return
        fungsi = aksi.get(pilihan)
        if fungsi:
            fungsi()


def menu_pendaftaran_admin():
    """UI-003B: workspace pendaftaran; service lama tetap memproses keputusan."""
    from app.ui.admin_enrollment import menu_pendaftaran_admin as buka_pendaftaran
    return buka_pendaftaran()


def jalankan():
    """Dashboard admin SIBIMA."""
    navigator = AdminDashboardNavigator()
    while True:
        if not session.punya_role("admin"):
            peringatan("Akses dashboard ditolak. Silakan login sebagai admin.")
            return

        bersihkan_layar()
        pengguna = session.get_user() or {}
        nama = pengguna.get("nama_lengkap") or pengguna.get("username") or "Admin"

        # UI-002: workspace selesai sebelum submenu lama atau AI dibuka.
        pilihan = navigator.choose(nama)

        if pilihan == "dashboard":
            continue

        if pilihan is None or pilihan == "logout":
            session.logout()
            sukses("Logout berhasil. Sesi telah ditutup.")
            return

        if pilihan == "ai":
            from app.services.ai_service import buka_ai
            buka_ai("admin")
            continue

        if pilihan == "konfirmasi":
            menu_konfirmasi()
            continue
        if pilihan == "program":
            menu_program_ruang()
            continue
        if pilihan == "pendaftaran":
            menu_pendaftaran_admin()
            continue
        if pilihan == "akun":
            menu_admin_data.menu_manajemen_akun_admin()
            continue
        if pilihan == "siswa":
            menu_admin_data.menu_data_siswa_admin()
            continue
        if pilihan == "tutor":
            menu_admin_data.menu_data_tutor_admin()
            continue
        if pilihan == "jadwal":
            menu_jadwal_admin()
            continue
        if pilihan == "pembayaran":
            menu_pembayaran.menu_pembayaran_admin()
            continue
        if pilihan == "laporan":
            menu_admin_laporan.menu_laporan_admin()
            continue
        if pilihan == "pengumuman":
            menu_admin_komunikasi.menu_pengumuman_admin()
            continue
        if pilihan == "log":
            menu_admin_komunikasi.menu_log_aktivitas_admin()
            continue

        label = next(
            (teks for teks, kode in MENU_ADMIN if kode == pilihan),
            pilihan,
        )
        _tampilkan_modul_belum_tersedia(label)
