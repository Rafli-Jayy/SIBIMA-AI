"""UI-002: dashboard Admin satu layar, tanpa mengubah service atau query.

Workspace hanya memilih kode modul. Controller lama tetap memeriksa role,
menjalankan submenu, logout, dan mengelola scrollback SIBIMA-AI.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import os
from time import monotonic
from typing import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, HSplit, Layout, Window
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.utils import get_cwidth

from .admin_navigation import KELOMPOK_MENU


# Same palette as auth/SIRASA. No dependency on a different UI layer.
STYLE = Style.from_dict({
    'brand': '#67d4e8 bold', 'title': '#e2e8f0 bold',
    'muted': '#94a3b8', 'rule': '#475569', 'number': '#67d4e8 bold',
    'selected': '#67d4e8 bold noreverse bg:default',
    'success': '#4ade80 bold', 'warning': '#fbbf24', 'error': '#f87171',
})
SPINNER = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
CONTENT_WIDTH = 100
MENU_WIDTH = 48
CARD_GAP = 2
# Four balanced cards: each has exactly three meaningful rows.
# A denominator denotes active/total, not a separate metric or percentage.
STAT_CARDS = (
    ('PENGGUNA · AKTIF/TOTAL', (
        ('siswa_aktif', 'Siswa aktif', 'siswa_total'),
        ('tutor_aktif', 'Tutor aktif', 'tutor_total'),
        ('admin_aktif', 'Admin aktif', 'admin_total'),
    )),
    ('AKADEMIK', (
        ('program_buka', 'Program buka / total', 'program_total'),
        ('ruang_aktif', 'Ruangan aktif / total', 'ruang_total'),
        ('jadwal_aktif', 'Jadwal rutin aktif', None),
    )),
    ('PENDAFTARAN', (
        ('enrollment_aktif', 'Pendaftaran aktif', None),
        ('enrollment_menunggu_bayar', 'Menunggu pembayaran', None),
        ('enrollment_selesai', 'Pendaftaran selesai', None),
    )),
    ('KEUANGAN', (
        ('tagihan_lunas', 'Tagihan lunas', None),
        ('tagihan_belum_lunas', 'Tagihan belum lunas', None),
        ('nominal_lunas_bulan_ini', 'Bayar lunas bulan ini (Rp)', None),
    )),
)
STAT_KEYS = tuple((key,label) for _,items in STAT_CARDS for key,label,_ in items)
TOTAL_KEYS = tuple((total,label) for _,items in STAT_CARDS
                   for _,label,total in items if total is not None)
ATTENTION_KEYS = (
    ('konfirmasi_akun', 'Konfirmasi akun'),
    ('konfirmasi_pendaftaran', 'Konfirmasi pendaftaran'),
    ('tagihan_terlambat', 'Tagihan lewat jatuh tempo'),
    ('sesi_perlu_laporan', 'Sesi perlu laporan'),
)
PRIORITY_CARDS = (
    ('KONFIRMASI AKUN', (
        ('konfirmasi_siswa', 'Calon siswa', None),
        ('konfirmasi_tutor', 'Calon tutor', None),
        ('konfirmasi_akun', 'Menunggu keputusan', None),
    )),
    ('PENDAFTARAN SIAP ACC', (
        ('konfirmasi_berbayar', 'Sudah bayar', None),
        ('konfirmasi_gratis', 'Program gratis', None),
        ('konfirmasi_pendaftaran', 'Menunggu keputusan', None),
    )),
    ('TAGIHAN', (
        ('tagihan_belum_lunas', 'Belum lunas', None),
        ('tagihan_terlambat', 'Lewat jatuh tempo', None),
        ('nominal_belum_lunas', 'Belum lunas (Rp)', None),
    )),
    ('PEMBAYARAN BULAN INI · SIMULASI', (
        ('transaksi_lunas_bulan_ini', 'Transaksi lunas', None),
        ('transaksi_gagal_bulan_ini', 'Simulasi gagal', None),
        ('refund_bulan_ini', 'Refund berhasil', None),
    )),
)
PRIORITY_KEYS = tuple((key,label) for _,items in PRIORITY_CARDS for key,label,_ in items)
GROUP_CHOICES = tuple((i, f'{i+1:02d}  {label}') for i, (label, _) in enumerate(KELOMPOK_MENU))
HOME_CHOICES = GROUP_CHOICES + (('logout', '00  Logout'),)
GROUP_HINTS = (
    'Konfirmasi akun, program, dan pembayaran.',
    'Kelola akun serta data profil siswa dan tutor.',
    'Kelola program, ruangan, dan jadwal mengajar.',
    'Laporan, pengumuman, log aktivitas, dan AI.',
)

# A rendered row is a list of (style, text) fragments. No terminal escape
# sequences or Rich markup are interpreted from data.
Row = list[tuple[str, str]]


def clean(value):
    return ' '.join(''.join(c if c.isprintable() else ' ' for c in str('' if value is None else value)).split())


def clip(value, width):
    width = max(0, width)
    value = clean(value)
    if get_cwidth(value) <= width:
        return value
    out = ''
    for char in value:
        if get_cwidth(out + char) > width - 1:
            break
        out += char
    return out.rstrip() + '…' if width else ''


def pad(value, width, align='left'):
    value = clip(value, width)
    spare = max(0, width-get_cwidth(value))
    if align == 'right':
        return ' '*spare + value
    if align == 'center':
        return ' '*(spare//2) + value + ' '*(spare-spare//2)
    return value + ' '*spare


def line(value, width, style='muted', align='left'):
    return [('class:'+style, pad(value,width,align))]


def width_of(row):
    return sum(get_cwidth(text) for _, text in row)


def frame(rows, width, *, heading='', tone='rule', heading_style='title'):
    inner = width-2
    border = 'class:'+tone
    label = ' '+clip(heading,inner-4)+' ' if heading and inner>=5 else ''
    top = '─'*max(0,inner-1-get_cwidth(label))
    result = [[(border,'┌─'), ('class:'+heading_style,label), (border,top+'┐')]]
    for row in rows:
        # All render helpers produce width-limited fragments.
        if width_of(row)>inner:
            row = line(''.join(t for _,t in row),inner)
        result.append([(border,'│'), *row, ('',' '*max(0,inner-width_of(row))), (border,'│')])
    result.append([(border,'└'+'─'*inner+'┘')])
    return result


def band(blocks, widths):
    """SIRASA uses two cell columns between neighboring cards."""
    rows = []
    height = max(map(len,blocks),default=0)
    for y in range(height):
        row = []
        for i,(block,width) in enumerate(zip(blocks,widths)):
            if i:
                row.append(('', ' '*CARD_GAP))
            row.extend(block[y] if y<len(block) else [('', ' '*width)])
        rows.append(row)
    return rows


def dashboard_card(title,rows,width,*,tone='rule',title_style='title'):
    """Centered heading inside frame, matching the SIRASA card geometry."""
    return frame([line(title,width-2,title_style,'center'),*rows],width,tone=tone)


@dataclass(frozen=True)
class Snapshot:
    summary: dict | None
    schedule: list[dict] | None

    def value(self, key):
        raw = self.summary.get(key) if self.summary is not None else None
        return '—' if raw is None else str(raw)


def load_snapshot():
    """Use exactly the existing read-only repository methods."""
    from app.repositories import admin_dashboard_repo
    try:
        summary = admin_dashboard_repo.ringkasan_admin()
    except Exception:
        summary = None
    try:
        schedule = admin_dashboard_repo.jadwal_hari_ini_admin()
    except Exception:
        schedule = None
    return Snapshot(summary,schedule)


def changed_metrics(previous, current):
    if previous is None or previous.summary is None or current.summary is None:
        return set()
    return {k for k,_ in STAT_KEYS+TOTAL_KEYS+ATTENTION_KEYS+PRIORITY_KEYS
            if previous.summary.get(k) is not None and current.summary.get(k) is not None
            and previous.summary[k]!=current.summary[k]}


def _metric_tone(snapshot,key,changed):
    if snapshot.value(key)=='—':
        return 'muted'
    if key in changed:
        return 'success'
    if key in ('tagihan_terlambat','transaksi_gagal_bulan_ini'):
        return 'error' if snapshot.value(key)!='0' else 'muted'
    if key=='transaksi_lunas_bulan_ini':
        return 'success'
    if key in dict(ATTENTION_KEYS) or key.startswith('konfirmasi_') or key=='tagihan_belum_lunas':
        return 'warning' if snapshot.value(key)!='0' else 'muted'
    return 'number'


def _display_value(snapshot,key):
    raw=snapshot.value(key)
    if raw=='—':
        return raw
    if key.startswith('nominal_'):
        try:
            amount=Decimal(raw)
            if not amount.is_finite():
                return '—'
            # Indonesian separators; retain cents when present.
            result=f'{amount:,.2f}'.translate(str.maketrans({',':'.','.':','}))
            return result[:-3] if result.endswith(',00') else result
        except (InvalidOperation, ValueError):
            return '—'
    try:
        return f'{int(raw):,}'.replace(',','.')
    except (ValueError, TypeError):
        return '—'


def _labeled_metric(snapshot,key,label,total,inner,changed):
    value=_display_value(snapshot,key)
    if total is not None:
        value+='/'+_display_value(snapshot,total)
        changed=changed|({key} if total in changed else set())
    tone=_metric_tone(snapshot,key,changed)
    if '—' in value:
        tone='muted'
    # Reserve enough value space for larger numbers without crowding labels.
    # On narrow terminals the label truncates rather than wrapping the card.
    margin=1 if inner>=8 else 0
    right=min(max(3,get_cwidth(value)),max(1,inner-margin*2-1))
    left=max(0,inner-margin*2-right-1)
    return [('', ' '*margin),*line(label,left,'muted'),('', ' '),
            *line(value,right,tone,'right'),('', ' '*margin)]


def _stat_rows(snapshot,inner,items,changed):
    return [_labeled_metric(snapshot,key,label,total,inner,changed)
            for key,label,total in items]


def _metric_bands(snapshot,width,changed,cards=STAT_CARDS):
    # Same geometry as the previous hotfix: 49 + 2 + 49 at 100 columns.
    columns=2 if width>=78 else 1
    for start in range(0,len(cards),columns):
        items=cards[start:start+columns]
        n=len(items)
        avail=width-CARD_GAP*(n-1)
        widths=[avail//n+int(i<avail%n) for i in range(n)]
        panels=[dashboard_card(title,_stat_rows(snapshot,cw-2,metrics,changed),cw)
               for (title,metrics),cw in zip(items,widths)]
        # Keep the logical sections available for very short terminals.
        yield band(panels,widths),items


def _attention_rows(snapshot,inner,changed):
    items=[(key,label,None) for key,label in ATTENTION_KEYS]
    if inner<76:
        return _stat_rows(snapshot,inner,items,changed)
    # Read across two aligned columns, with no inner box borders. Five
    # actionable counts use three rows instead of five.
    left=(inner-CARD_GAP)//2
    right=inner-CARD_GAP-left
    rows=[]
    for i in range(0,len(items),2):
        first=_stat_rows(snapshot,left,items[i:i+1],changed)[0]
        second=(_stat_rows(snapshot,right,items[i+1:i+2],changed)[0]
                if i+1<len(items) else [('', ' '*right)])
        rows.append([*first,('', ' '*CARD_GAP),*second])
    return rows


def _schedule_heading(snapshot):
    title='JADWAL HARI INI (RUTIN)'
    if snapshot.schedule:
        total=snapshot.schedule[0].get('total_jadwal')
        if isinstance(total,int) and total>len(snapshot.schedule):
            title+=f' · {len(snapshot.schedule)} dari {total}'
        else:
            title+=f' · {len(snapshot.schedule)} jadwal'
    return title


def _time(value):
    if value is None:
        return '?'
    return value.strftime('%H:%M') if hasattr(value,'strftime') else str(value)[:5]


def _schedule_rows(snapshot,inner):
    if snapshot.schedule is None:
        return [line('Jadwal gagal dimuat.',inner,'warning','center')]
    if not snapshot.schedule:
        return [line('Tidak ada jadwal rutin aktif hari ini.',inner,'muted','center')]
    # The original repository returns at most five routine schedules.
    # On small terminals keep time/program visible and include tutor/room in
    # the second line when needed. The existing Jadwal module has full details.
    rows=[]
    if inner>=43:
        program_width=(inner-15)//2
        who_width=inner-15-program_width
        rows.append([('', ' '),*line('Jam',11,'muted'),('', ' '),
                     *line('Program',program_width,'muted'),('', ' '),
                     *line('Tutor / Ruang',who_width,'muted'),('', ' ')])
    for item in snapshot.schedule[:5]:
        time=f"{_time(item.get('jam_mulai'))}–{_time(item.get('jam_selesai'))}"
        program=item.get('program') or '—'
        who=f"{item.get('tutor') or '—'} / {item.get('ruang') or '—'}"
        if inner>=43:
            program_width=(inner-15)//2
            who_width=inner-15-program_width
            rows.append([('', ' '),*line(time,11,'number'),('', ' '),
                         *line(program,program_width,'title'),('', ' '),
                         *line(who,who_width),('', ' ')])
        else:
            rows.append([('', ' '),*line(time,min(12,max(0,inner-2)),'number'),
                         *line(program,max(0,inner-14),'title'),('', ' ')])
            rows.append(line(who,inner,'muted','center'))
    return rows


def _compact_section(title,rows,width,budget):
    """Keep full values available when an entire bordered card is too tall."""
    if budget<=1:
        return [[row] for row in rows] or [[line(title,width,'title','center')]]
    head=line(title,width,'title','center')
    step=budget-1
    return [[head,*rows[i:i+step]] for i in range(0,len(rows),step)] or [[head]]


def info_pages(snapshot,width,budget,changed):
    """Top-aligned card bands, then schedule and full-width attention.

    Page breaks respect card boundaries; only over-height sections switch to
    compact rows. The navigation area stays visible at small terminal heights.
    """
    budget=max(1,budget)
    if snapshot is None:
        return [[]]
    warnings=[]
    if snapshot.summary is None:
        warnings=[line('Statistik gagal dimuat. Periksa koneksi.',width,'warning','center')]
    attention=_attention_rows(snapshot,width-2,changed)
    schedule=_schedule_rows(snapshot,width-2)
    schedule_title=_schedule_heading(snapshot)
    schedule_card=dashboard_card(schedule_title,schedule,width,
                                 tone='error' if snapshot.schedule is None else 'rule')
    attention_card=dashboard_card('PERLU PERHATIAN',attention,width,title_style='warning')
    complete=(snapshot.summary is not None and snapshot.schedule is not None
              and all(snapshot.summary.get(key) is not None
                      for key,_ in STAT_KEYS+TOTAL_KEYS+ATTENTION_KEYS))
    status=[line('Data terakhir dimuat ●' if complete else 'Data belum lengkap',width,
                 'muted' if complete else 'warning','center')]
    blocks=[]
    if warnings:
        blocks.append(warnings)
    for block,items in _metric_bands(snapshot,width,changed):
        if len(block)<=budget:
            blocks.append(block)
        else:
            for title,metrics in items:
                blocks.extend(_compact_section(title,_stat_rows(snapshot,width,metrics,changed),
                                               width,budget))
    for title,card,compact in (
        (schedule_title,schedule_card,_schedule_rows(snapshot,width)),
        ('PERLU PERHATIAN',attention_card,_attention_rows(snapshot,width,changed)),
    ):
        blocks.extend([card] if len(card)<=budget else _compact_section(title,compact,width,budget))
    blocks.append(status)

    return paginate_blocks(blocks,budget)


def paginate_blocks(blocks,budget):
    pages=[]; page=[]
    for block in blocks:
        gap=1 if page and len(block)>1 and len(page)+1+len(block)<=budget else 0
        if page and len(page)+gap+len(block)>budget:
            pages.append(page);page=[];gap=0
        if gap:
            page.append([])
        page.extend(block)
    if page:
        pages.append(page)
    return pages or [[]]


def priority_pages(snapshot,width,budget,changed,*,confirmation=False):
    """UI-003A: priority and confirmation cards from one real summary."""
    budget=max(1,budget)
    snapshot=snapshot or Snapshot(None,None)
    cards=PRIORITY_CARDS[:2] if confirmation else PRIORITY_CARDS
    blocks=[]
    for block,items in _metric_bands(snapshot,width,changed,cards):
        if len(block)<=budget:
            blocks.append(block)
        else:
            for title,metrics in items:
                blocks.extend(_compact_section(title,_stat_rows(snapshot,width,metrics,changed),
                                               width,budget))
    if not confirmation:
        items=(('konfirmasi_akun','Akun menunggu keputusan',None),
               ('konfirmasi_pendaftaran','Pendaftaran siap diproses',None),
               ('tagihan_terlambat','Tagihan melewati jatuh tempo',None))
        rows=_stat_rows(snapshot,width-2,items,changed)
        card=dashboard_card('PERLU TINDAKAN',rows,width,title_style='warning')
        blocks.extend([card] if len(card)<=budget else
                      _compact_section('PERLU TINDAKAN',_stat_rows(snapshot,width,items,changed),width,budget))
    complete=snapshot.summary is not None and all(
        snapshot.summary.get(key) is not None for _,items in cards for key,_,_ in items)
    blocks.append([line('Data terakhir dimuat ●' if complete else 'Data belum lengkap · Muat ulang',
                        width,'muted' if complete else 'warning','center')])
    return paginate_blocks(blocks,budget)


def menu_rows(choices,index,width):
    """48-column text navigation, using a separator before Kembali/Logout."""
    body=[]
    selected_row=0
    number=0
    for i,(key,label) in enumerate(choices):
        last=key in ('back','logout')
        if last and i>0:
            body.append([('class:rule','─'*width)])
        if i==index:
            selected_row=len(body)
        mark='❯ ' if i==index else '  '
        tone='class:selected' if i==index else 'class:muted' if last else ''
        if last:
            prefix='     '
            label='Logout' if key=='logout' else label
        else:
            number+=1
            prefix=f'{number:02d}   '
            # HOME_CHOICES already contains a display number; avoid duplication.
            label=label[4:] if type(key) is int else label
        raw=mark+prefix
        if width<=get_cwidth(raw):
            raw=mark[:max(0,width-1)]
        body.append([(tone,raw+pad(label,max(0,width-get_cwidth(raw))))])
    return body,selected_row


def fragments(rows):
    return [fragment for i,row in enumerate(rows)
            for fragment in ([('', '\n')] if i else [])+row]


class AdminDashboardWorkspace:
    """Pinned menu + pageable information; no writes and no action dispatch."""
    def __init__(self,nama,*,load=load_snapshot,previous=None,input=None,output=None,
                 motion_enabled=None,initial_group=None,initial_index=0):
        self.nama=clean(nama) or 'Admin'
        self.load: Callable[[], Snapshot]=load
        self.previous=previous
        self.snapshot=None
        self.metrics_changed=set()
        self.highlight_until=0.
        self.loading=True
        self.group=initial_group if initial_group in range(len(KELOMPOK_MENU)) else None
        self.home_index=self.group if self.group is not None else 0
        self.index=min(max(0,initial_index),len(self.choices)-1)
        self.page_index=0
        self.motion_enabled=(os.getenv('SIBIMA_NO_MOTION','').strip().lower()
                             not in ('1','true','yes')) if motion_enabled is None else motion_enabled
        self.started=monotonic()
        self.control=FormattedTextControl(self._menu_text,focusable=True,show_cursor=False)
        kb=KeyBindings()
        ready=Condition(lambda: not self.loading)

        @kb.add('up',filter=ready)
        def up(event):
            self.index=(self.index-1)%len(self.choices)

        @kb.add('down',filter=ready)
        def down(event):
            self.index=(self.index+1)%len(self.choices)

        @kb.add('pageup',filter=ready)
        def pageup(event):
            self.page_index=max(0,min(self.page_index,len(self._pages())-1)-1)

        @kb.add('pagedown',filter=ready)
        def pagedown(event):
            self.page_index=min(len(self._pages())-1,self.page_index+1)

        @kb.add('r',filter=ready)
        @kb.add('R',filter=ready)
        def refresh(event):
            self.previous=self.snapshot
            self.loading=True
            self.started=monotonic()
            self.page_index=0
            event.app.create_background_task(self._fetch())
            if self.motion_enabled:
                event.app.create_background_task(self._animate())

        @kb.add('enter',filter=ready)
        def enter(event):
            key=self.choices[self.index][0]
            if self.group is None and type(key) is int:
                self.home_index=self.index
                self.group=key
                self.index=0
                self.page_index=0
            elif key=='back':
                self._back()
            else:
                event.app.exit(result=key)

        @kb.add('escape',filter=ready,eager=True)
        @kb.add('c-c',filter=ready,eager=True)
        def back(event):
            if self.group is not None:
                self._back()
            else:
                event.app.exit(result='logout')

        header=Window(FormattedTextControl(self._header_text),height=self._header_height,
                      align=WindowAlign.CENTER,wrap_lines=False,always_hide_cursor=True)
        info=Window(FormattedTextControl(self._info_text),height=self._info_height,
                    align=WindowAlign.CENTER,wrap_lines=False,always_hide_cursor=True)
        nav=Window(self.control,height=self._menu_height,align=WindowAlign.CENTER,
                   wrap_lines=False,always_hide_cursor=True)
        footer=Window(FormattedTextControl(self._footer),height=1,align=WindowAlign.CENTER,
                      wrap_lines=False,always_hide_cursor=True)
        root=HSplit([header,info,Window(height=self._nav_space),nav,
                     Window(height=Dimension(min=0,weight=1)),footer])
        self.app=Application(layout=Layout(root,focused_element=nav),style=STYLE,
                             key_bindings=kb,full_screen=True,input=input,output=output,
                             mouse_support=False)

    @property
    def choices(self):
        if self.group is None:
            return HOME_CHOICES
        return tuple((code,label) for label,code in KELOMPOK_MENU[self.group][1])+(
            ('back','Kembali ke dashboard'),)

    def _size(self):
        return self.app.output.get_size()

    def _width(self):
        return max(8,min(CONTENT_WIDTH,self._size().columns-2))

    def _menu_width(self):
        return min(self._width(),MENU_WIDTH)

    def _header_height(self):
        rows=self._size().rows
        return Dimension.exact(4 if rows>=18 else 2 if rows>=11 else 1)

    def _header_text(self):
        title=('PUSAT KENDALI ADMIN' if self.group is None else 'PUSAT PRIORITAS'
               if self.group==0 else KELOMPOK_MENU[self.group][0].upper())
        width=self._size().columns
        h=self._header_height().preferred
        if h==1:
            return [('class:brand',clip('S I B I M A · '+title,width))]
        if h==2:
            return [('class:brand','S I B I M A\n'),('class:title',clip(title,width))]
        # The four-row SIRASA header: logo, signed-in name/role,
        # a 100-column rule, then the current page title.
        return [('class:brand','S I B I M A\n'),
                ('class:muted',clip(self.nama+' · Admin',width)+'\n'),
                ('class:rule','─'*self._width()+'\n'),
                ('class:title',clip(title,width))]

    def _menu_height(self):
        # Reserve the viewport for navigation at very small heights.
        available=max(1,self._size().rows-self._header_height().preferred-1)
        if self.group is None and available>=5 and available<=len(self.choices)+1:
            available-=1
        return Dimension.exact(min(len(self.choices)+1,available))

    def _budget(self):
        return max(0,self._size().rows-self._header_height().preferred-self._menu_height().preferred-1)

    def _pages(self):
        budget=self._budget()
        if self.group is not None and self.group!=0 and not self.loading:
            return [[line(GROUP_HINTS[self.group],self._width(),'muted','center')]] if budget else [[]]
        if self.loading:
            if not budget:
                return [[]]
            spin=SPINNER[int((monotonic()-self.started)/.1)%len(SPINNER)] if self.motion_enabled else '…'
            return [[line(spin+' Memuat ringkasan Admin...',self._width(),'number','center')]]
        active=self.metrics_changed if self.motion_enabled and monotonic()<self.highlight_until else set()
        renderer=priority_pages if self.group==0 else info_pages
        pages=renderer(self.snapshot,self._width(),max(1,budget),active)
        if len(pages)>1 and budget>=2:
            return renderer(self.snapshot,self._width(),budget-1,active)
        return pages if budget else [[]]

    def _info_height(self):
        pages=self._pages()
        indicator=int(len(pages)>1 and self._budget()>=2)
        return Dimension.exact(min(self._budget(),max(map(len,pages))+indicator))

    def _info_text(self):
        pages=self._pages()
        index=min(self.page_index,len(pages)-1)
        rows=list(pages[index])
        if len(pages)>1 and self._budget()>=2:
            # Pad shorter pages so the menu never jumps when flipping pages.
            rows.extend([[]]*(max(map(len,pages))-len(rows)))
            rows.append(line(f'Info {index+1}/{len(pages)} · PgUp/PgDn',self._width(),'muted','center'))
        elif len(pages)>1 and self._budget()==1 and rows:
            # Ultra-short terminals still expose every information row.
            marker=f'[{index+1}/{len(pages)}] '
            plain=''.join(t for _,t in rows[0])
            rows=[[('class:muted',marker+clip(plain,self._width()-get_cwidth(marker)))]]
        return fragments(rows)

    def _nav_space(self):
        # SIRASA pins menu directly after information, leaving remaining space below.
        return Dimension.exact(1 if self._budget()>self._info_height().preferred else 0)

    def _menu_text(self):
        rows,selected=menu_rows(self.choices,-1 if self.loading else self.index,self._menu_width())
        height=self._menu_height().preferred
        if len(rows)>height:
            # Keep selected option visible on unusually short terminals.
            start=max(0,min(selected-height//2,len(rows)-height))
            rows=rows[start:start+height]
        return fragments(rows)

    def _footer(self):
        if self.loading:
            text='Memuat data...'
        elif self.group is not None:
            text=('PgUp/PgDn Baca | ' if len(self._pages())>1 else '')+'↑ ↓ Pilih | Enter | R Muat ulang | Esc Kembali'
        else:
            text=('PgUp/PgDn Baca | ' if len(self._pages())>1 else '')+'↑ ↓ Pilih | Enter Buka | R Muat ulang | Esc Logout'
        if get_cwidth(text)>self._size().columns:
            text=('PgUp/Dn | ' if len(self._pages())>1 else '')+'↑ ↓ | Enter | Esc'
        return [('class:muted',clip(text,self._size().columns))]

    def _back(self):
        self.group=None
        self.index=self.home_index
        self.page_index=0

    async def _fetch(self):
        try:
            loaded=await asyncio.to_thread(self.load)
            self.snapshot=loaded if isinstance(loaded,Snapshot) else Snapshot(None,None)
        except Exception:
            self.snapshot=Snapshot(None,None)
        self.metrics_changed=changed_metrics(self.previous,self.snapshot)
        self.highlight_until=monotonic()+1.2
        self.loading=False
        self.app.invalidate()

    async def _animate(self):
        while self.loading or monotonic()<self.highlight_until:
            self.app.invalidate()
            await asyncio.sleep(.1)
        self.app.invalidate()

    def run(self):
        def start():
            self.app.create_background_task(self._fetch())
            if self.motion_enabled:
                self.app.create_background_task(self._animate())
        return self.app.run(pre_run=start)


class AdminDashboardNavigator:
    """Remember previous real counts between returns from legacy modules."""

    def __init__(self, *, load=load_snapshot):
        self.load=load
        self.previous=None
        self.return_group=None
        self.return_index=0

    def choose(self,nama):
        workspace=AdminDashboardWorkspace(nama,load=self.load,previous=self.previous,
                                          initial_group=self.return_group,initial_index=self.return_index)
        result=workspace.run()
        # Returning from a Prioritas module restores its immediate parent.
        self.return_group=0 if result in ('konfirmasi','pendaftaran','pembayaran') else None
        self.return_index={'konfirmasi':0,'pendaftaran':1,'pembayaran':2}.get(result,0)
        if workspace.snapshot is not None and workspace.snapshot.summary is not None:
            self.previous=workspace.snapshot
        return result
