"""UI-003A: satu workspace konfirmasi Admin; service lama tetap pemilik keputusan."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import Dimension, HSplit, Window
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.utils import get_cwidth

from .auth_workspace import AuthWorkspace, Field
from .admin_workspace import (
    CONTENT_WIDTH, MENU_WIDTH, CARD_GAP, Snapshot, band, clean, clip, pad,
    dashboard_card, line, fragments, menu_rows, priority_pages, changed_metrics,
    paginate_blocks, _compact_section,
)


def value(item, key, default='—'):
    result=item.get(key)
    if result is None or result=='':
        return default
    if hasattr(result,'strftime'):
        return result.strftime('%d %b %Y %H:%M')
    return clean(result)


def yes(value):
    return 'Ya' if value else 'Tidak'


def rupiah(amount):
    try:
        n=Decimal(str(amount))
        if not n.is_finite():
            return '—'
        result=f'{n:,.2f}'.translate(str.maketrans({',':'.','.':','}))
        return 'Rp'+(result[:-3] if result.endswith(',00') else result)
    except (InvalidOperation,ValueError):
        return '—'


def wrap(value,width):
    """No data lost in the full-detail page, even for long Unicode names."""
    width=max(1,width)
    rest=clean(value)
    rows=[]
    while rest:
        end=0
        for i,ch in enumerate(rest):
            if get_cwidth(rest[:i+1])>width:
                break
            end=i+1
        if end==0:
            rows.append('…')
            rest=rest[1:]
            continue
        split=rest.rfind(' ',0,end+1) if end<len(rest) else -1
        end=split if split>0 else end
        rows.append(rest[:end])
        rest=rest[end:].lstrip()
    return rows or ['—']


def field_rows(fields,width,*,full=False):
    rows=[]
    label_width=min(22,max(1,(width-3)//2))
    value_width=max(1,width-label_width-3)
    for label,val in fields:
        values=wrap(val,value_width) if full else [clip(val,value_width)]
        for i,v in enumerate(values):
            rows.append([('', ' '),*line(label if i==0 else '',label_width,'muted'),
                         ('',' '),*line(v,value_width,'title'),('',' ')])
    return rows


def details_pages(sections,width,budget,*,notice='',full=False,paired=False):
    """Cards use SIRASA's 49 + 2 + 49 geometry; long details remain pageable."""
    budget=max(1,budget)
    cols=2 if width>=78 and (not full or paired) else 1
    blocks=[]
    for i in range(0,len(sections),cols):
        group=sections[i:i+cols]
        available=width-CARD_GAP*(len(group)-1)
        widths=[available//len(group)+int(j<available%len(group)) for j in range(len(group))]
        bodies=[field_rows(fields,cw-2,full=full) for (_,fields),cw in zip(group,widths)]
        # Equal card heights align both bottom borders in a two-card row.
        height=max(map(len,bodies))
        cards=[dashboard_card(title,body+[[]]*(height-len(body)),cw)
               for (title,_),body,cw in zip(group,bodies,widths)]
        if max(map(len,cards))<=budget:
            blocks.append(band(cards,widths))
        else:
            for title,fields in group:
                compact=field_rows(fields,width,full=full)
                blocks.extend(_compact_section(title,compact,width,budget))
    if notice:
        notes=[line(t,width-2,'warning','center') for t in wrap(notice,max(1,width-2))[:2]]
        blocks.extend([notes] if len(notes)<=budget else [[row] for row in notes])
    return paginate_blocks(blocks,budget)


def account_sections(item,*,full=False):
    role=item.get('role')
    basic=[('Nama',value(item,'nama_lengkap')),('Username',value(item,'username')),
           ('Role',str(role or '—').upper()),('Email terverifikasi',yes(item.get('email_verified')))]
    if full:
        basic.extend([('ID pengguna',value(item,'id')),('Email',value(item,'email')),
                      ('Tanggal daftar',value(item,'created_at')),('Status',value(item,'status'))])
    if role=='siswa':
        profile=[('Jenjang',value(item,'jenjang')),('Sekolah',value(item,'sekolah')),
                 ('NIS',value(item,'nis','Belum diterbitkan')),('Status','Menunggu ACC' if item.get('status')=='menunggu_konfirmasi' else value(item,'status'))]
        if full:
            profile.extend([('Nomor HP',value(item,'student_no_hp')),('Wali',value(item,'nama_wali'))])
    else:
        profile=[('Keahlian',value(item,'keahlian')),('Kode tutor',value(item,'kode_tutor','Belum diterbitkan')),
                 ('Nomor HP',value(item,'tutor_no_hp')),('Status','Menunggu ACC' if item.get('status')=='menunggu_konfirmasi' else value(item,'status'))]
    sections=[('IDENTITAS AKUN',basic),('PROFIL '+str(role or 'pengguna').upper(),profile)]
    if full:
        sections.append(('KEAMANAN & RIWAYAT',[
            ('Login terakhir',value(item,'last_login')),('Gagal login',value(item,'failed_attempts')),
            ('Terkunci sampai',value(item,'locked_until')),('Wajib ganti sandi',yes(item.get('must_change_password'))),
            ('Disetujui pada',value(item,'approved_at')),('Alasan penolakan',value(item,'reject_reason'))]))
    return sections


def enrollment_sections(item,*,full=False):
    free=item.get('harga_bulanan')==0
    person=[('Nama siswa',value(item,'nama_siswa')),('NIS',value(item,'nis')),
            ('Program',value(item,'nama_program')),('Biaya per bulan',rupiah(item.get('harga_bulanan')))]
    billing=[('Invoice',value(item,'no_invoice','Tanpa tagihan' if free else '—')),
             ('Status tagihan',value(item,'invoice_status','Tidak diperlukan' if free else '—')),
             ('Pembayaran',value(item,'payment_status','Tidak diperlukan' if free else '—')),
             ('Nominal invoice',rupiah(item.get('invoice_jumlah',0) if free else item.get('invoice_jumlah')))]
    if full:
        person.extend([('ID pendaftaran',value(item,'enrollment_id')),('ID siswa',value(item,'student_id')),
                       ('Username',value(item,'username')),('Email',value(item,'email')),
                       ('Kode program',value(item,'kode_program')),('Jenjang',value(item,'jenjang')),
                       ('Tanggal daftar',value(item,'created_at')),('Status',value(item,'status'))])
        billing.append(('Waktu bayar',value(item,'paid_at')))
    return [('SISWA & PROGRAM',person),('TAGIHAN & PEMBAYARAN',billing)]


def table_columns(kind,width):
    """One selection row per record; no duplicate Questionary list."""
    if kind=='akun':
        if width>=72:
            return [('ID',6),('Nama',width-44),('Role',8),('Email',14),('Tanggal',10)]
        return [('ID',6),('Nama',max(1,width-21)),('Role',8)]
    if width>=72:
        return [('ID',6),('Siswa',(width-35)//2),('Program',width-35-(width-35)//2),('Tagihan',13),('Tanggal',10)]
    return [('ID',6),('Siswa',max(1,(width-10)//2)),('Program',max(1,width-10-(width-10)//2))]


def table_row(kind,width,item=None,selected=False):
    cols=table_columns(kind,width)
    if item is None:
        values=[key for key,_ in cols]
    elif kind=='akun':
        values=[value(item,'id'),value(item,'nama_lengkap'),value(item,'role').upper(),
                'Terverifikasi' if item.get('email_verified') else 'Belum',
                (item['created_at'].strftime('%d/%m/%Y') if hasattr(item.get('created_at'),'strftime') else value(item,'created_at')[:10])]
    else:
        values=[value(item,'enrollment_id'),value(item,'nama_siswa'),value(item,'nama_program'),
                'Gratis' if item.get('harga_bulanan')==0 else value(item,'invoice_status').upper(),
                (item['created_at'].strftime('%d/%m/%Y') if hasattr(item.get('created_at'),'strftime') else value(item,'created_at')[:10])]
    tone='class:selected' if selected else 'class:muted' if item is None else 'class:title'
    out=[(tone,'❯ ' if selected else '  ')]
    for i,((_,cw),v) in enumerate(zip(cols,values)):
        if i:
            out.append((tone,' '))
        out.append((tone,pad(v,cw)))
    # Bounds even for exceptionally narrow terminals.
    if sum(get_cwidth(t) for _,t in out)>width:
        return [(tone,pad(''.join(t for _,t in out),width))]
    return out


class ConfirmationWorkspace(AuthWorkspace):
    """Reuse the approved SIRASA auth form, but keep the Admin 100-col header."""
    def __init__(self,nama,**kwargs):
        self.nama=clean(nama) or 'Admin'
        self.page_index=0
        self.table_active=False
        self.page_active=False
        self.table_data=[]
        self.table_filter=False
        self.table_caption=""
        self.table_empty=""
        self.table_renderer=None
        self.page_renderer=None
        super().__init__(**kwargs)

        @self.app.key_bindings.add('r',filter=Condition(lambda: self.table_active and self.mode=='menu'))
        @self.app.key_bindings.add('R',filter=Condition(lambda: self.table_active and self.mode=='menu'))
        def refresh(event):
            self.finish('refresh')

        @self.app.key_bindings.add('f',filter=Condition(lambda: self.table_active and self.table_filter and self.mode=='menu'))
        @self.app.key_bindings.add('F',filter=Condition(lambda: self.table_active and self.table_filter and self.mode=='menu'))
        def filter_records(event):
            self.finish('filter')

        @self.app.key_bindings.add('pageup',filter=Condition(lambda: self.mode=='menu' and (self.page_active or self.table_active)))
        def prev(event):
            if self.table_active:
                self.index=max(0,self.index-self._table_capacity())
            else:
                self.page_index=max(0,self.page_index-1)

        @self.app.key_bindings.add('pagedown',filter=Condition(lambda: self.mode=='menu' and (self.page_active or self.table_active)))
        def next_page(event):
            if self.table_active:
                self.index=min(len(self.choices)-1,self.index+self._table_capacity())
            else:
                self.page_index=min(len(self._page_rows())-1,self.page_index+1)

    def _admin_width(self):
        return max(8,min(CONTENT_WIDTH,self.app.output.get_size().columns-2))

    def _header_height(self):
        rows=self.app.output.get_size().rows
        return 4 if rows>=18 else 2 if rows>=11 else 1

    def _header(self):
        h=self._header_height()
        width=self._admin_width()
        if h==1:
            return [('class:brand',clip('S I B I M A · '+self.title,width))]
        if h==2:
            return [('class:brand','S I B I M A\n'),('class:title',clip(self.title,width))]
        return [('class:brand','S I B I M A\n'),
                ('class:muted',clip(self.nama+' · Admin',width)+'\n'),
                ('class:rule','─'*width+'\n'),('class:title',clip(self.title,width))]

    def _footer(self):
        if self.mode=='menu' and self.table_active:
            hint=('↑ ↓ Pilih · Enter · PgUp/PgDn · F Filter · R Muat ulang · Esc Kembali' if self.table_filter
                  else '↑ ↓ Pilih · Enter · PgUp/PgDn · R Muat ulang · Esc Kembali')
            if get_cwidth(hint)>self._admin_width():
                hint='↑↓ Enter · F Filter · R Muat ulang · Esc' if self.table_filter else '↑↓ Enter · R Muat ulang · Esc'
            return [('class:muted',clip(hint,self._admin_width()))]
        if self.mode=='menu' and self.page_active:
            prefix='PgUp/PgDn Baca · ' if len(self._page_rows())>1 else ''
            return [('class:muted',clip(prefix+'↑ ↓ Pilih · Enter · Esc Kembali',self._admin_width()))]
        return super()._footer()

    def _remaining(self):
        return max(1,self.app.output.get_size().rows-self._header_height()-1)

    def _nav_height(self):
        return min(len(self.choices)+int(any(k=='back' for k,_ in self.choices)),max(1,self._remaining()-1))

    def _budget(self):
        return max(0,self._remaining()-self._nav_height())

    def _page_rows(self):
        budget=self._budget()
        if not budget or self.page_renderer is None:
            return [[]]
        pages=self.page_renderer(self._admin_width(),budget)
        if len(pages)>1 and budget>=2:
            pages=self.page_renderer(self._admin_width(),budget-1)
        return pages or [[]]

    def _page_info_rows(self):
        pages=self._page_rows()
        i=min(self.page_index,len(pages)-1)
        rows=list(pages[i])
        h=max(map(len,pages))
        if len(pages)>1 and self._budget()>=2:
            rows.extend([[]]*(h-len(rows)))
            rows.append(line(f'Info {i+1}/{len(pages)} · PgUp/PgDn',self._admin_width(),'muted','center'))
        return rows

    def _page_nav(self):
        rows,selected=menu_rows(self.choices,self.index,min(MENU_WIDTH,self._admin_width()))
        height=self._nav_height()
        start=max(0,min(selected-height//2,len(rows)-height))
        return fragments(rows[start:start+height])

    async def page(self,title,choices,renderer,*,default=None):
        self.page_index=0
        self.page_renderer=renderer
        self.table_active=False
        self.page_active=True
        self.choices=list(choices)
        self.index=next((i for i,(key,_) in enumerate(self.choices) if key==default),0)
        control=FormattedTextControl(self._page_nav,focusable=True,show_cursor=False)
        body=HSplit([
            Window(FormattedTextControl(lambda:fragments(self._page_info_rows())),
                   height=lambda:Dimension.exact(min(self._budget(),len(self._page_info_rows()))),
                   align=WindowAlign.CENTER,wrap_lines=False),
            Window(control,height=lambda:Dimension.exact(self._nav_height()),
                   align=WindowAlign.CENTER,wrap_lines=False,always_hide_cursor=True),
            Window(height=Dimension(min=0,weight=1)),
        ])
        try:
            return await self._prepare('menu',title,body,control)
        finally:
            self.page_active=False

    def _table_capacity(self):
        return max(1,self._remaining()-4)

    def _table_rows(self):
        width=self._admin_width()
        if not self.table_data:
            return ([line('0 data · '+self.table_caption,width,'muted','center'),
                    line(self.table_empty,width,'success','center'),
                    line('F Filter · R Muat ulang · Esc Kembali' if self.table_filter else
                         'R Muat ulang · Esc Kembali',width,'muted','center')][:self._remaining()]
                    if self._remaining()>=2 else [line('Data kosong · Esc',width,'success','center')])
        n=len(self.table_data)
        capacity=self._table_capacity()
        start=max(0,min(self.index-capacity//2,n-capacity))
        end=min(n,start+capacity)
        caption=f'{start+1}–{end} dari {n} · {self.table_caption}'
        rows=[line(caption,width,'muted','center'),
              self.table_renderer(width),line('─'*width,width,'rule')]
        rows.extend(self.table_renderer(width,self.table_data[i],i==self.index) for i in range(start,end))
        if len(rows)>self._remaining():
            rows=rows[-self._remaining():]
        return rows

    async def record_table(self,title,items,*,key,renderer,caption='Urutan terbaru',
                           empty='Tidak ada data.',filter_action=False,initial=None):
        """Shared Admin table: one selectable row per record; R and optional F."""
        self.table_data=list(items)
        self.table_active=True
        self.table_filter=filter_action
        self.table_caption=caption
        self.table_empty=empty
        self.table_renderer=renderer
        self.page_active=False
        self.choices=[(row[key],'') for row in items] or [('back','Kembali')]
        self.index=next((i for i,(k,_) in enumerate(self.choices) if k==initial),0)
        control=FormattedTextControl(lambda:fragments(self._table_rows()),focusable=True,show_cursor=False)
        body=HSplit([Window(control,align=WindowAlign.CENTER,wrap_lines=False,
                            height=lambda:Dimension.exact(len(self._table_rows())),
                            always_hide_cursor=True),
                     Window(height=Dimension(min=0,weight=1))])
        try:
            return await self._prepare('menu',title,body,control)
        finally:
            self.table_active=False
            self.table_filter=False
            self.table_data=[]
            self.table_renderer=None

    async def table(self,kind,items):
        return await self.record_table('ANTREAN KONFIRMASI '+('AKUN' if kind=='akun' else 'PENDAFTARAN'),
            items,key='id' if kind=='akun' else 'enrollment_id',
            renderer=lambda w,item=None,selected=False:table_row(kind,w,item,selected),
            caption='Urutan terlama',empty='Tidak ada antrean menunggu.')

    async def result(self,title,message,kind='info'):
        """Two-line notification + optional full service result, no lost warning."""
        tone={'success':'success','error':'error'}.get(kind,'warning')
        def preview(width,budget):
            lower=message.lower()
            partial=(kind=='success' and any(term in lower for term in ('email','pdf','dokumen'))
                     and any(term in lower for term in ('gagal','belum','tidak','perlu diperiksa')))
            if partial:
                rows=[line('Keputusan tersimpan.',width,'success','center'),
                      line('Email/PDF perlu diperiksa · Detail hasil',width,'warning','center')]
            else:
                parts=wrap(message,width)
                rows=[line(t,width,tone,'center') for t in parts[:2]]
                if len(parts)>2:
                    rows[-1]=line(clip(parts[1],max(1,width-1))+'…',width,tone,'center')
            return [rows[:budget]]
        while True:
            action=await self.page(title,[('back','Lanjutkan'),('detail','Detail hasil')],preview,default='back')
            if action!='detail':
                return
            await self.page('DETAIL HASIL',[('back','Kembali')],
                            lambda w,b:paginate_blocks([[line(t,w,tone)] for t in wrap(message,w)],b))


class ConfirmationController:
    """Orchestrate existing services; no repository writes or new business rules."""
    def __init__(self,*,summary,accounts,enrollments,account_detail,student_packages,
                 approve_account,reject_account,approve_enrollment,reject_enrollment,is_admin):
        self.summary=summary
        self.accounts=accounts
        self.enrollments=enrollments
        self.account_detail=account_detail
        self.student_packages=student_packages
        self.approve_account=approve_account
        self.reject_account=reject_account
        self.approve_enrollment=approve_enrollment
        self.reject_enrollment=reject_enrollment
        self.is_admin=is_admin

    async def run(self,view):
        previous=None
        while self.is_admin():
            try:
                snapshot=Snapshot(await view.busy('Memuat ringkasan...',self.summary),None)
            except Exception:
                snapshot=Snapshot(None,None)
            changed=changed_metrics(previous,snapshot)
            if snapshot.summary is not None:
                previous=snapshot
            action=await view.page('PUSAT KONFIRMASI',[
                ('akun','Konfirmasi Akun ('+snapshot.value('konfirmasi_akun')+')'),
                ('program','Konfirmasi Pendaftaran ('+snapshot.value('konfirmasi_pendaftaran')+')'),
                ('refresh','Muat ulang'),('back','Kembali ke Prioritas')],
                lambda w,b:priority_pages(snapshot,w,b,changed,confirmation=True))
            if action in (None,'back'):
                return
            if action in ('akun','program'):
                await self.queue(view,action)

    async def queue(self,view,kind):
        loader=self.accounts if kind=='akun' else self.enrollments
        key='id' if kind=='akun' else 'enrollment_id'
        while self.is_admin():
            try:
                records=await view.busy('Memuat antrean...',loader)
                if records is None:
                    raise ValueError('Antrean tidak tersedia')
                if kind=='akun':
                    records=[x for x in records if x.get('role') in ('siswa','tutor')]
                records=sorted(records,key=lambda x:(str(x.get('created_at') or ''),x[key]))
            except Exception:
                await view.result('DATA GAGAL DIMUAT','Antrean gagal dimuat. Periksa koneksi, lalu coba lagi.','error')
                return
            selection=await view.table(kind,records)
            if selection in (None,'back'):
                return
            if selection=='refresh':
                continue
            item=next((row for row in records if row[key]==selection),None)
            if not item:
                continue
            if kind=='akun':
                try:
                    detail=await view.busy('Memuat detail...',self.account_detail,selection)
                except Exception:
                    await view.result('DATA GAGAL DIMUAT','Detail akun gagal dimuat. Coba lagi.','error')
                    continue
                if not detail or detail.get('status')!='menunggu_konfirmasi' or detail.get('role') not in ('siswa','tutor'):
                    await view.result('ANTREAN BERUBAH','Akun tidak lagi menunggu. Daftar akan dimuat ulang.')
                    continue
                item=detail
            await self.detail(view,kind,item)

    async def detail(self,view,kind,item):
        account=kind=='akun'
        role=item.get('role')
        identity=value(item,'nama_lengkap' if account else 'nama_siswa')
        title='DETAIL PENDAFTAR AKUN' if account else 'DETAIL PENDAFTARAN PROGRAM'
        sections=account_sections(item) if account else enrollment_sections(item)
        eligible=not account or bool(item.get('email_verified'))
        impact=('Persetujuan mengaktifkan akun dan menerbitkan '+('NIS.' if role=='siswa' else 'kode tutor.')
                if account else 'Persetujuan mengaktifkan kelas. Program gratis atau tagihan lunas dapat diproses.')
        if not eligible:
            impact='Email belum terverifikasi. Akun belum dapat diproses.'
        selection_id=item['id' if account else 'enrollment_id']
        while self.is_admin():
            choices=([('approve','Setujui Akun' if account else 'Terima Pendaftaran'),
                      ('reject','Tolak Akun' if account else 'Tolak Pendaftaran')] if eligible else [])
            choices.extend([('detail','Detail Lengkap'),('back','Kembali ke antrean')])
            action=await view.page(title,choices,
                                  lambda w,b:details_pages(sections,w,b,notice=impact))
            if action in (None,'back'):
                return
            if action=='detail':
                full=account_sections(item,full=True) if account else enrollment_sections(item,full=True)
                if account and role=='siswa':
                    try:
                        packages=await view.busy('Memuat riwayat program...',self.student_packages,selection_id)
                        programs=[(value(p,'kode_program'),value(p,'nama_program')+' · '+rupiah(p.get('harga_bulanan')))
                                  for p in packages if p.get('status')=='menunggu']
                        full.append(('PROGRAM MENUNGGU',programs or [('Info','Tidak ada program menunggu')]))
                    except Exception:
                        full.append(('PROGRAM MENUNGGU',[('Info','Riwayat gagal dimuat')]))
                await view.page('DETAIL LENGKAP',[('back','Kembali')],
                                lambda w,b:details_pages(full,w,b,full=True))
                continue
            if action not in ('approve','reject') or not eligible:
                continue
            reason=None
            if action=='reject':
                notice=''
                while True:
                    answer=await view.form('ALASAN PENOLAKAN',[Field('reason','Alasan penolakan')],
                                           subtitle=identity,notice=notice,
                                           hint='Alasan wajib diisi.',submit_label='Lanjutkan')
                    if answer is None:
                        break
                    reason=answer.get('reason','').strip()
                    if reason:
                        break
                    notice='Alasan penolakan wajib diisi.'
                if not reason:
                    continue
            if action=='reject':
                impact_reject=('Akun ditolak; paket siswa yang menunggu ikut ditolak.' if account and role=='siswa'
                               else 'Akun ditolak.' if account else 'Pendaftaran ditolak; refund simulasi otomatis jika sudah lunas.')
                explanation=impact_reject
            else:
                explanation=impact
            summary=[('Target',identity),
                     ('Keputusan','Setujui' if action=='approve' else 'Tolak')]
            if reason is not None:
                summary.append(('Alasan',reason))
            decision=await view.page('KONFIRMASI KEPUTUSAN',
                [('confirm','Ya, lanjutkan'),('back','Batal')],
                lambda w,b:details_pages([('RINGKASAN KEPUTUSAN',summary)],w,b,notice=explanation,full=True),
                default='back')
            if decision!='confirm':
                continue
            if not self.is_admin():
                return
            fn=(self.approve_account if action=='approve' else self.reject_account) if account else (
                self.approve_enrollment if action=='approve' else self.reject_enrollment)
            try:
                args=(selection_id,reason) if action=='reject' else (selection_id,)
                ok,message=await view.busy('Memproses keputusan...',fn,*args)
            except Exception:
                # Commit may already have succeeded. Never retry automatically.
                await view.result('HASIL BELUM DAPAT DIPASTIKAN',
                                  'Periksa status terbaru sebelum mengulangi tindakan.','error')
                return
            await view.result('KEPUTUSAN TERSIMPAN' if ok else 'KEPUTUSAN GAGAL',str(message),
                              'success' if ok else 'error')
            return


def menu_konfirmasi():
    """Entry point used by menu_admin; session and service checks stay intact."""
    from app import session
    from app.repositories import admin_dashboard_repo,user_repo,enrollment_repo,profile_repo
    from app.services import approval_service
    if not session.punya_role('admin'):
        return
    user=session.get_user() or {}
    controller=ConfirmationController(
        summary=admin_dashboard_repo.ringkasan_admin,
        accounts=lambda:user_repo.daftar_by_status('menunggu_konfirmasi'),
        enrollments=enrollment_repo.daftar_menunggu,
        account_detail=profile_repo.detail_pengguna_persetujuan,
        student_packages=enrollment_repo.enrollment_siswa,
        approve_account=approval_service.setujui_akun,reject_account=approval_service.tolak_akun,
        approve_enrollment=approval_service.setujui_enrollment,reject_enrollment=approval_service.tolak_enrollment,
        is_admin=lambda:session.punya_role('admin'))
    ConfirmationWorkspace(user.get('nama_lengkap') or user.get('username') or 'Admin').run(controller.run)
