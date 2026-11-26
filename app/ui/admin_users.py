"""UI-004: Data Pengguna as one Admin workspace; existing services own all writes."""
from __future__ import annotations

from .admin_confirmation import ConfirmationWorkspace, Field, details_pages, value, yes
from .admin_workspace import (Snapshot, line, pad, width_of, paginate_blocks,
                              _metric_bands, _stat_rows, _compact_section)
from .admin_navigation import KELOMPOK_MENU

STATUS = {
    'belum_verifikasi':'Belum verifikasi',
    'menunggu_konfirmasi':'Menunggu ACC',
    'aktif':'Aktif',
    'ditolak':'Ditolak',
    'nonaktif':'Nonaktif',
}
ROLE = {'siswa':'Siswa','tutor':'Tutor','admin':'Admin'}
STATUS_TONE = {'aktif':'success','nonaktif':'muted','ditolak':'error',
               'belum_verifikasi':'warning','menunggu_konfirmasi':'warning'}
ROUTES = tuple((code,label) for label,code in KELOMPOK_MENU[1][1])
MENUS = {
    'akun': ('MANAJEMEN AKUN', [
        ('daftar','Daftar Akun · Filter Role/Status'),
        ('status','Nonaktifkan / Aktifkan Akun'),
        ('unlock','Buka Kunci Login'),
        ('reset','Reset Password Akun'),
    ]),
    'siswa': ('DATA SISWA', [
        ('daftar','Lihat Daftar Siswa'),('cari','Cari Siswa · Nama/NIS'),
        ('filter','Filter Jenjang / Program / Status'),
        ('detail','Detail & Riwayat Pendaftaran'),('ubah','Ubah Data Siswa'),
        ('nonaktif','Nonaktifkan Akun Siswa'),
    ]),
    'tutor': ('DATA TUTOR', [
        ('daftar','Lihat Daftar Tutor'),('detail','Detail & Jadwal Mengajar'),
        ('ubah','Ubah Data Tutor'),('nonaktif','Nonaktifkan Akun Tutor'),
    ]),
}
PROFILE_FIELDS = {
    'siswa': [('nama_lengkap','Nama lengkap',100),('jenjang','Jenjang',20),
              ('sekolah','Sekolah',100),('no_hp','Nomor HP',20),('nama_wali','Nama wali',100)],
    'tutor': [('nama_lengkap','Nama lengkap',100),('keahlian','Keahlian',150),('no_hp','Nomor HP',20)],
}
ROOT_CARDS = (
    ('SISWA',(('siswa_aktif','Aktif / total','siswa_total'),
              ('siswa_wait','Menunggu konfirmasi',None),('siswa_nonaktif','Nonaktif',None))),
    ('TUTOR',(('tutor_aktif','Aktif / total','tutor_total'),
              ('tutor_wait','Menunggu konfirmasi',None),('tutor_nonaktif','Nonaktif',None))),
    ('ADMIN',(('admin_aktif','Aktif / total','admin_total'),
              ('admin_nonaktif','Nonaktif',None),('admin_must_change','Wajib ganti password',None))),
    ('KEAMANAN LOGIN',(('locked','Kunci login tercatat',None),
                      ('failed','Akun dengan login gagal',None),('must_change','Wajib ganti password',None))),
)
ACCOUNT_CARDS = (
    ('AKUN · AKTIF/TOTAL',(('siswa_aktif','Siswa','siswa_total'),('tutor_aktif','Tutor','tutor_total'),
                         ('admin_aktif','Admin','admin_total'))),
    ('STATUS AKUN',(('belum_verifikasi','Belum verifikasi',None),
                    ('menunggu_konfirmasi','Menunggu konfirmasi',None),('aktif','Aktif',None))),
    ('STATUS LAIN & EMAIL',(('nonaktif','Nonaktif',None),('ditolak','Ditolak',None),
                             ('email_unverified','Email belum terverifikasi',None))),
    ('KEAMANAN LOGIN',ROOT_CARDS[-1][1]),
)
PROFILE_CARDS = {
    'siswa': (
        ('STATUS SISWA',(('aktif','Aktif / total','total'),('menunggu_konfirmasi','Menunggu konfirmasi',None),
                         ('belum_verifikasi','Belum verifikasi',None))),
        ('IDENTITAS & PROGRAM',(('issued','NIS sudah terbit',None),('assigned','Punya program aktif/menunggu',None),
                               ('unassigned','Tanpa program aktif/menunggu',None))),
        ('STATUS LAIN',(('nonaktif','Nonaktif',None),('ditolak','Ditolak',None))),
    ),
    'tutor': (
        ('STATUS TUTOR',(('aktif','Aktif / total','total'),('menunggu_konfirmasi','Menunggu konfirmasi',None),
                         ('belum_verifikasi','Belum verifikasi',None))),
        ('IDENTITAS & JADWAL',(('issued','Kode tutor terbit',None),('assigned','Tutor punya jadwal aktif',None),
                               ('schedules','Total jadwal aktif',None))),
        ('STATUS LAIN',(('nonaktif','Nonaktif',None),('ditolak','Ditolak',None))),
    ),
}


def lock_recorded(row):
    return row.get('locked_until') is not None


def failed_login(row):
    return (row.get('failed_attempts') or 0)>0


def account_metrics(rows):
    if rows is None:
        return None
    result={s:sum(row.get('status')==s for row in rows) for s in STATUS}
    for role in ROLE:
        group=[r for r in rows if r.get('role')==role]
        result.update({role+'_total':len(group),role+'_aktif':sum(r.get('status')=='aktif' for r in group),
                       role+'_wait':sum(r.get('status')=='menunggu_konfirmasi' for r in group),
                       role+'_nonaktif':sum(r.get('status')=='nonaktif' for r in group),
                       role+'_must_change':sum(bool(r.get('must_change_password')) for r in group)})
    result.update(locked=sum(lock_recorded(r) for r in rows),failed=sum(failed_login(r) for r in rows),
                  must_change=sum(bool(r.get('must_change_password')) for r in rows),
                  email_unverified=sum(not bool(r.get('email_verified')) for r in rows))
    return result


def profile_metrics(rows,kind):
    if rows is None:
        return None
    result={s:sum(row.get('status')==s for row in rows) for s in STATUS}
    result['total']=len(rows)
    result['issued']=sum(bool(r.get('nis' if kind=='siswa' else 'kode_tutor')) for r in rows)
    if kind=='siswa':
        result['assigned']=sum(bool(r.get('program')) and r['program']!='Belum ada program' for r in rows)
        result['unassigned']=result['total']-result['assigned']
    else:
        result['assigned']=sum((r.get('jumlah_jadwal') or 0)>0 for r in rows)
        result['schedules']=sum(r.get('jumlah_jadwal') or 0 for r in rows)
    return result


def dashboard_pages(data,kind,width,budget,changed=frozenset()):
    cards=ROOT_CARDS if kind=='root' else ACCOUNT_CARDS if kind=='akun' else PROFILE_CARDS[kind]
    snapshot=Snapshot(data,None)
    budget=max(1,budget)
    blocks=[]
    for block,group in _metric_bands(snapshot,width,changed,cards):
        if len(block)<=budget:
            blocks.append(block)
        else:
            for title,items in group:
                blocks.extend(_compact_section(title,_stat_rows(snapshot,width,items,changed),width,budget))
    if kind in ('root','akun'):
        blocks.append([line('Kunci tercatat bisa sudah kedaluwarsa · Percobaan gagal dihitung per akun',
                            width,'muted','center')])
    blocks.append([line('Data terakhir dimuat ●' if data is not None else 'Data belum tersedia · Muat ulang',
                        width,'muted' if data is not None else 'warning','center')])
    return paginate_blocks(blocks,budget)


def status(row):
    return STATUS.get(row.get('status'),value(row,'status'))


def login_state(row):
    return 'Kunci tercatat' if lock_recorded(row) else 'Login gagal' if failed_login(row) else 'Normal'


def _row(width,columns,row,selected,raw_status=None):
    """Distribute spare cells over flexible columns, without wrapping."""
    fixed=sum(size for _,size,_ in columns if size)
    flexible=sum(1 for _,size,_ in columns if not size)
    rest=max(flexible,width-2-max(0,len(columns)-1)-fixed)
    n=0
    base='class:selected' if selected else 'class:muted' if row is None else 'class:title'
    result=[(base,'❯ ' if selected else '  ')]
    for i,(label,size,field) in enumerate(columns):
        if not size:
            size=rest//flexible+int(n<rest%flexible)
            n+=1
        if i:
            result.append((base,' '))
        tone='class:'+STATUS_TONE.get(raw_status,'muted') if label=='Status' and row is not None and not selected else base
        result.append((tone,pad(label if row is None else field(row),size)))
    if width_of(result)>width:
        return [(base,pad(''.join(s for _,s in result),width))]
    return result


def account_row(width,row=None,selected=False):
    fields=[('ID',5,lambda r:value(r,'id')),('Role',7,lambda r:value(r,'role')),
            ('Nama',0,lambda r:value(r,'nama_lengkap')),('Username',0,lambda r:value(r,'username')),
            ('Status',16,status),('Email',6,lambda r:yes(r.get('email_verified'))),
            ('ID resmi',11,lambda r:str(r.get('nis') or r.get('kode_tutor') or '—')),
            ('Login',14,login_state)]
    if width<92:
        fields=[x for x in fields if x[0] not in ('Email','ID resmi','Username')]
    if width<62:
        fields=[x for x in fields if x[0]!='Login']
        fields=[(l,12 if l=='Status' else w,f) for l,w,f in fields]
    if width<38:
        fields=[x for x in fields if x[0]!='Role']
    return _row(width,fields,row,selected,row.get('status') if row else None)


def profile_row(kind,width,row=None,selected=False):
    fields=[('ID',5,lambda r:value(r,'user_id')),
            ('NIS' if kind=='siswa' else 'Kode Tutor',12,
             lambda r:str(r.get('nis' if kind=='siswa' else 'kode_tutor') or 'Belum terbit')),
            ('Nama',0,lambda r:value(r,'nama_lengkap')),
            ('Jenjang' if kind=='siswa' else 'Keahlian',14 if kind=='siswa' else 0,
             lambda r:value(r,'jenjang' if kind=='siswa' else 'keahlian')),
            ('Program',0,lambda r:value(r,'program')),('Status',16,status)]
    if kind=='tutor':
        fields.insert(-2,('Jadwal',6,lambda r:value(r,'jumlah_jadwal')))
    if width<85:
        fields=[x for x in fields if x[0] not in ('Program','Keahlian','Jenjang')]
    if width<58:
        fields=[x for x in fields if x[0]!='Jadwal']
        fields=[(l,10 if l in ('NIS','Kode Tutor') else 12 if l=='Status' else w,f) for l,w,f in fields]
    if width<38:
        fields=[x for x in fields if x[0] not in ('NIS','Kode Tutor')]
    return _row(width,fields,row,selected,row.get('status') if row else None)


def program_row(width,row=None,selected=False):
    return _row(width,[('ID',5,lambda r:value(r,'id')),('Kode',10,lambda r:value(r,'kode')),
                       ('Program',0,lambda r:value(r,'nama')),('Status',8,lambda r:value(r,'status'))],
                row,selected)


def history_row(kind,width,row=None,selected=False):
    if kind=='siswa':
        columns=[('ID',5,lambda r:value(r,'enrollment_id')),('Program',0,lambda r:value(r,'nama_program')),
                 ('Status',18,lambda r:value(r,'status')),('Daftar',17,lambda r:value(r,'created_at')),
                 ('Diproses',17,lambda r:value(r,'processed_at'))]
        if width<80:
            columns=columns[:3]
    else:
        columns=[('ID',5,lambda r:value(r,'id')),('Program',0,lambda r:value(r,'nama_program')),
                 ('Hari',10,lambda r:value(r,'hari')),('Jam',12,lambda r:value(r,'jam_mulai')+'–'+value(r,'jam_selesai')),
                 ('Ruang',0,lambda r:value(r,'ruang')),('Status',8,lambda r:'Aktif' if r.get('aktif') else 'Nonaktif')]
        if width<80:
            columns=[c for c in columns if c[0]!='Ruang']
        if width<54:
            columns=[c for c in columns if c[0] not in ('Hari','Jam')]
    return _row(width,columns,row,selected,row.get('status') if row and kind=='siswa'
                else ('aktif' if row.get('aktif') else 'nonaktif') if row else None)


def account_sections(row):
    return [
        ('IDENTITAS AKUN',[('ID',value(row,'id')),('Nama',value(row,'nama_lengkap')),('Username',value(row,'username')),
                          ('Role',value(row,'role')),('Email',value(row,'email'))]),
        ('STATUS & IDENTITAS RESMI',[('Status',status(row)),('Email terverifikasi',yes(row.get('email_verified'))),
                                   ('NIS',value(row,'nis')),('Kode tutor',value(row,'kode_tutor'))]),
        ('KEAMANAN LOGIN',[('Gagal login',value(row,'failed_attempts')),('Kunci sampai',value(row,'locked_until')),
                           ('Wajib ganti password',yes(row.get('must_change_password')))]),
        ('AKTIVITAS AKUN',[('Dibuat',value(row,'created_at')),('Login terakhir',value(row,'last_login'))]),
    ]


def profile_sections(kind,row):
    identity=[('User ID',value(row,'user_id')),('Nama',value(row,'nama_lengkap')),('Username',value(row,'username')),
              ('NIS' if kind=='siswa' else 'Kode tutor',str(row.get('nis' if kind=='siswa' else 'kode_tutor') or 'Belum terbit'))]
    account=[('Status akun',status(row)),('Email',value(row,'email')),('Email terverifikasi',yes(row.get('email_verified'))),
             ('Dibuat',value(row,'created_at'))]
    if kind=='siswa':
        profile=[('Jenjang',value(row,'jenjang')),('Sekolah',value(row,'sekolah')),
                 ('Nomor HP',value(row,'no_hp')),('Nama wali',value(row,'nama_wali'))]
        related=[('Program aktif/menunggu',value(row,'program')),('Login terakhir',value(row,'last_login'))]
    else:
        profile=[('Keahlian',value(row,'keahlian')),('Nomor HP',value(row,'no_hp'))]
        related=[('Program',value(row,'program')),('Jadwal aktif',value(row,'jumlah_jadwal'))]
    return [('IDENTITAS',identity),('AKUN',account),('PROFIL',profile),('AKADEMIK',related)]


class DataUsersController:
    def __init__(self,*,accounts,students,tutors,student_detail,tutor_detail,history,schedules,
                 programs,status_update,unlock,reset,student_update,tutor_update,is_admin,current_id=None):
        self.accounts=accounts
        self.students=students
        self.tutors=tutors
        self.student_detail=student_detail
        self.tutor_detail=tutor_detail
        self.history=history
        self.schedules=schedules
        self.programs=programs
        self.status_update=status_update
        self.unlock=unlock
        self.reset=reset
        self.student_update=student_update
        self.tutor_update=tutor_update
        self.is_admin=is_admin
        self.current_id=current_id
        self.previous={}
        self.focus={}

    async def _read(self,view,title,fn,*args):
        if not self.is_admin():
            return None
        try:
            result=await view.busy(title,fn,*args)
            if result is None:
                await view.result('DATA TIDAK TERSEDIA','Data tidak ditemukan. Muat ulang.','warning')
            return result
        except (ValueError,PermissionError) as exc:
            await view.result('DATA GAGAL DIMUAT',str(exc),'error')
        except Exception:
            await view.result('DATA GAGAL DIMUAT','Periksa koneksi, lalu coba lagi.','error')
        return None

    async def _write(self,view,title,fn,*args):
        if not self.is_admin():
            return
        try:
            ok,message=await view.busy(title,fn,*args)
        except Exception:
            await view.result('HASIL BELUM DAPAT DIPASTIKAN',
                              'Periksa data terbaru sebelum mencoba kembali.','warning')
            return
        await view.result('PERUBAHAN TERSIMPAN' if ok else 'PERUBAHAN GAGAL',str(message),
                          'success' if ok else 'error')

    async def _dashboard(self,view,kind,rows,choices,title):
        data=account_metrics(rows) if kind in ('root','akun') else profile_metrics(rows,kind)
        old=self.previous.get(kind)
        changed={k for k,v in (data or {}).items() if old is not None and old.get(k) is not None and old[k]!=v}
        if data is not None:
            self.previous[kind]=data
        focus=self.focus.get(kind,choices[0][0])
        action=await view.page(title,[*choices,('refresh','Muat ulang'),
                    ('back','Kembali ke dashboard' if kind=='root' else 'Kembali ke Data Pengguna')],
                    lambda w,b:dashboard_pages(data,kind,w,b,changed),default=focus)
        if action=='refresh':
            self.focus[kind]=getattr(view,'refresh_focus',None) or focus
        elif action not in (None,'back'):
            self.focus[kind]=action
        return action

    async def run(self,view,initial=None):
        if initial in MENUS:
            await self.module(view,initial)
            return
        while self.is_admin():
            # A failed summary is not a zero population. Let the user refresh.
            try:
                rows=await view.busy('Memuat data pengguna...',self.accounts,None,None)
            except Exception:
                rows=None
            if not self.is_admin():
                return
            action=await self._dashboard(view,'root',rows,ROUTES,'PUSAT DATA PENGGUNA')
            if action in (None,'back') or not self.is_admin():
                return
            if action in MENUS:
                await self.module(view,action)

    async def module(self,view,kind):
        title,choices=MENUS[kind]
        while self.is_admin():
            try:
                rows=await view.busy('Memuat ringkasan...',self.accounts,None,None) if kind=='akun' else await view.busy(
                    'Memuat ringkasan...',self.students if kind=='siswa' else self.tutors)
            except Exception:
                rows=None
            if not self.is_admin():
                return
            action=await self._dashboard(view,kind,rows,choices,title)
            if action in (None,'back') or not self.is_admin():
                return
            if action=='refresh':
                continue
            if kind=='akun':
                if action=='daftar':
                    await self.browse_accounts(view)
                elif action in ('status','unlock','reset'):
                    await self.account_action(view,action)
            elif action in ('daftar','cari','filter','detail'):
                await self.browse_profiles(view,kind,action)
            elif action in ('ubah','nonaktif'):
                await self.profile_action(view,kind,action)

    async def _choose(self,view,title,options,default='all',caption='Pilih salah satu'):
        return await view.page(title,[*options,('back','Kembali')],
            lambda w,b:[[line(caption,w,'muted','center')]],default=default)

    async def _account_filters(self,view,role=None,state=None):
        role=await self._choose(view,'FILTER ROLE',[('all','Semua role'),*ROLE.items()],role or 'all')
        if role in (None,'back'):
            return None
        state=await self._choose(view,'FILTER STATUS AKUN',[('all','Semua status'),*STATUS.items()],state or 'all')
        if state in (None,'back'):
            return None
        return (None if role=='all' else role,None if state=='all' else state)

    async def browse_accounts(self,view):
        filters=await self._account_filters(view)
        if filters is None:
            return
        initial=None
        while self.is_admin():
            rows=await self._read(view,'Memuat daftar akun...',self.accounts,*filters)
            if rows is None:
                return
            role,state=filters
            selected=await view.record_table('DAFTAR AKUN',rows,key='id',renderer=account_row,
                caption=ROLE.get(role,'Semua role')+' · '+STATUS.get(state,'Semua status'),
                filter_action=True,initial=initial,empty='Tidak ada akun sesuai filter.')
            if selected=='filter':
                new=await self._account_filters(view,*filters)
                if new is not None:
                    filters=new
                    initial=None
                continue
            if selected=='refresh':
                continue
            row=next((r for r in rows if r['id']==selected),None)
            if row is None:
                return
            initial=selected
            await view.page('DETAIL AKUN',[('back','Kembali ke daftar')],
                lambda w,b:details_pages(account_sections(row),w,b,full=True,paired=True))

    async def account_action(self,view,action):
        titles={'status':'PILIH AKUN AKTIF/NONAKTIF','unlock':'PILIH AKUN UNTUK BUKA KUNCI',
                'reset':'PILIH AKUN UNTUK RESET PASSWORD'}
        initial=None
        while self.is_admin():
            rows=await self._read(view,'Memuat akun...',self.accounts,None,None)
            if rows is None:
                return
            if action=='status':
                rows=[r for r in rows if r.get('role') in ('siswa','tutor') and r.get('status') in ('aktif','nonaktif')]
            elif action=='unlock':
                rows=[r for r in rows if lock_recorded(r) or failed_login(r)]
            elif action=='reset':
                rows=[r for r in rows if r['id']!=self.current_id]
            selected=await view.record_table(titles[action],rows,key='id',renderer=account_row,
                initial=initial,empty='Tidak ada akun yang dapat dipilih.',caption='Pilih target akun')
            if selected=='refresh':
                continue
            row=next((r for r in rows if r['id']==selected),None)
            if row is None:
                return
            initial=selected
            if action=='status':
                target='nonaktif' if row['status']=='aktif' else 'aktif'
                await self.confirm_status(view,row,selected,target)
            elif action=='unlock':
                confirm=await self._decision(view,'KONFIRMASI BUKA KUNCI',row,
                    [('Tindakan','Reset kunci dan percobaan gagal'),('Kunci sampai',value(row,'locked_until')),
                     ('Gagal login',value(row,'failed_attempts'))],'Ya, buka kunci')
                if confirm:
                    await self._write(view,'Membuka kunci...',self.unlock,selected)
            elif action=='reset':
                confirm=await self._decision(view,'KONFIRMASI RESET PASSWORD',row,
                    [('Tindakan','Password sementara acak'),('Dampak','Password sebelumnya tidak berlaku.'),
                     ('Login berikutnya','Wajib ganti password.')],'Ya, reset password',
                    notice='Password sementara hanya ditampilkan sekali.')
                if confirm:
                    await self._reset_password(view,selected)

    async def _decision(self,view,title,row,fields,confirm_label,notice=''):
        if not self.is_admin():
            return False
        sections=[('TARGET',[('Nama',value(row,'nama_lengkap')),('Username',value(row,'username')),
                             ('Status',status(row)),('ID',str(row.get('id',row.get('user_id','—'))))]),
                  ('DAMPAK TINDAKAN',fields)]
        action=await view.page(title,[('confirm',confirm_label),('back','Batal')],
            lambda w,b:details_pages(sections,w,b,notice=notice,full=True,paired=True),default='back')
        return action=='confirm' and self.is_admin()

    async def confirm_status(self,view,row,user_id,target,kind=None):
        title='KONFIRMASI STATUS AKUN'
        note=('Jadwal dan riwayat tetap disimpan. Atur ulang jadwal bila diperlukan.'
              if kind=='tutor' else 'Riwayat pendaftaran dan tagihan tidak dihapus.')
        confirmed=await self._decision(view,title,row,[('Status saat ini',status(row)),
            ('Status baru',STATUS[target]),('Riwayat','Tetap disimpan')],
            'Ya, '+('nonaktifkan' if target=='nonaktif' else 'aktifkan')+' akun',notice=note)
        if confirmed:
            await self._write(view,'Memperbarui status akun...',self.status_update,user_id,target)

    async def _reset_password(self,view,user_id):
        if not self.is_admin():
            return
        try:
            ok,message,password=await view.busy('Mereset password...',self.reset,user_id)
        except Exception:
            await view.result('HASIL BELUM DAPAT DIPASTIKAN','Periksa status akun sebelum mereset kembali.','warning')
            return
        if not ok:
            await view.result('RESET PASSWORD GAGAL',str(message),'error')
            return
        if not isinstance(password,str) or not password:
            await view.result('PASSWORD TIDAK TERSEDIA','Periksa hasil reset sebelum melanjutkan.','warning')
            return
        # Only reveal once to the admin, no log, no preview or saved result.
        if not self.is_admin():
            return
        secret=[('PASSWORD SEMENTARA',[('Password',password),('Login berikutnya','Wajib ganti password')])]
        try:
            await view.page('RESET PASSWORD BERHASIL',[('back','Tutup hasil')],
                lambda w,b:details_pages(secret,w,b,full=True,
                    notice='Catat dan sampaikan lewat kanal aman. Jangan kirim ke grup.'))
        finally:
            secret.clear()
            if hasattr(view,'page_renderer'):
                view.page_renderer=None

    async def _pick_program(self,view,initial=None):
        selected=await self._choose(view,'FILTER PROGRAM',[('all','Semua program'),('choose','Pilih program')],
                                    'choose' if initial else 'all')
        if selected in (None,'back'):
            return None
        if selected=='all':
            return 'all'
        while self.is_admin():
            rows=await self._read(view,'Memuat program...',self.programs)
            if rows is None:
                return None
            selected=await view.record_table('PILIH PROGRAM',rows,key='id',renderer=program_row,
                caption='Program tersedia',initial=initial,empty='Belum ada program.')
            if selected=='refresh':
                continue
            return selected if type(selected) is int and any(r['id']==selected for r in rows) else None

    async def _student_filters(self,view,existing=(None,None,None,None)):
        jenjang,pid,state,_=existing
        answer=await view.form('FILTER JENJANG',[Field('jenjang','Jenjang (opsional)',jenjang or '')],
                               hint='Kosong = semua jenjang.',submit_label='Lanjutkan')
        if answer is None:
            return None
        pid=await self._pick_program(view,pid)
        if pid is None:
            return None
        state=await self._choose(view,'FILTER STATUS SISWA',[('all','Semua status'),*STATUS.items()],state or 'all')
        if state in (None,'back'):
            return None
        return answer['jenjang'].strip() or None,None if pid=='all' else pid,None if state=='all' else state,None

    async def _search(self,view,default=''):
        answer=await view.form('CARI SISWA',[Field('cari','Nama atau NIS',default)],
                               hint='Masukkan nama / NIS; kosong = semua siswa.',submit_label='Cari')
        return None if answer is None else (answer['cari'].strip() or '')

    async def browse_profiles(self,view,kind,action):
        filters=(None,None,None,None)
        if kind=='siswa' and action=='cari':
            search=await self._search(view)
            if search is None:
                return
            filters=(None,None,None,search)
        elif kind=='siswa' and action=='filter':
            filters=await self._student_filters(view)
            if filters is None:
                return
        initial=None
        while self.is_admin():
            fn=self.students if kind=='siswa' else self.tutors
            rows=await self._read(view,'Memuat profil...',fn,*(filters if kind=='siswa' else ()))
            if rows is None:
                return
            title='DAFTAR SISWA' if kind=='siswa' else 'DAFTAR TUTOR'
            caption='Semua data'
            if kind=='siswa':
                j,p,s,c=filters
                caption=' · '.join(x for x in (('Cari: '+c) if c else '',('Jenjang: '+j) if j else '',
                        ('Program ID: '+str(p)) if p else '',STATUS.get(s,'') if s else '') if x) or 'Semua data'
            selected=await view.record_table(title,rows,key='user_id',
                renderer=lambda w,row=None,selected=False:profile_row(kind,w,row,selected),
                caption=caption,filter_action=kind=='siswa',initial=initial,
                empty='Tidak ada profil sesuai kriteria.')
            if selected=='filter' and kind=='siswa':
                mode=await self._choose(view,'FILTER DATA SISWA',
                    [('search','Cari nama / NIS'),('filters','Jenjang / Program / Status'),('all','Reset filter')])
                if mode=='search':
                    search=await self._search(view,filters[3] or '')
                    new=None if search is None else (None,None,None,search)
                elif mode=='filters':
                    new=await self._student_filters(view,filters)
                elif mode=='all':
                    new=(None,None,None,None)
                else:
                    new=None
                if new is not None:
                    filters=new
                    initial=None
                continue
            if selected=='refresh':
                continue
            if not any(r['user_id']==selected for r in rows):
                return
            initial=selected
            await self.detail_profile(view,kind,selected)

    async def detail_profile(self,view,kind,user_id):
        fn=self.student_detail if kind=='siswa' else self.tutor_detail
        row=await self._read(view,'Memuat detail profil...',fn,user_id)
        if row is None:
            return
        while self.is_admin():
            link='Riwayat Pendaftaran' if kind=='siswa' else 'Jadwal Mengajar'
            action=await view.page('DETAIL '+kind.upper(),[('related',link),('back','Kembali ke daftar')],
                lambda w,b:details_pages(profile_sections(kind,row),w,b,full=True,paired=True))
            if action!='related':
                return
            await self.related(view,kind,user_id)

    async def related(self,view,kind,user_id):
        initial=None
        while self.is_admin():
            # The student history uses the existing repository, so reauthorize
            # via the existing service before that read.
            if kind=='siswa' and await self._read(view,'Memeriksa akses...',self.student_detail,user_id) is None:
                return
            rows=await self._read(view,'Memuat riwayat...' if kind=='siswa' else 'Memuat jadwal...',
                                  self.history if kind=='siswa' else self.schedules,user_id)
            if rows is None:
                return
            key='enrollment_id' if kind=='siswa' else 'id'
            title='RIWAYAT PENDAFTARAN SISWA' if kind=='siswa' else 'JADWAL MENGAJAR TUTOR'
            selected=await view.record_table(title,rows,key=key,initial=initial,
                renderer=lambda w,row=None,selected=False:history_row(kind,w,row,selected),
                caption='Riwayat program' if kind=='siswa' else 'Jadwal aktif dan nonaktif',
                empty='Belum ada riwayat pendaftaran.' if kind=='siswa' else 'Belum ada jadwal mengajar.')
            if selected=='refresh':
                continue
            row=next((r for r in rows if r[key]==selected),None)
            if row is None:
                return
            initial=selected
            fields=([('ID',value(row,key)),('Program',value(row,'nama_program')),
                     ('Status',value(row,'status')),('Tanggal daftar',value(row,'created_at')),
                     ('Diproses',value(row,'processed_at'))] if kind=='siswa' else
                    [('ID',value(row,key)),('Kode program',value(row,'kode_program')),
                     ('Program',value(row,'nama_program')),('Hari',value(row,'hari')),
                     ('Jam',value(row,'jam_mulai')+'–'+value(row,'jam_selesai')),
                     ('Ruang',value(row,'ruang')),('Status','Aktif' if row.get('aktif') else 'Nonaktif')])
            await view.page('DETAIL PROGRAM' if kind=='siswa' else 'DETAIL JADWAL',[('back','Kembali ke daftar')],
                lambda w,b:details_pages([(title,fields)],w,b,full=True))

    async def profile_action(self,view,kind,action):
        initial=None
        while self.is_admin():
            fn=self.students if kind=='siswa' else self.tutors
            rows=await self._read(view,'Memuat profil...',fn)
            if rows is None:
                return
            if action=='nonaktif':
                rows=[r for r in rows if r.get('status')=='aktif']
            selected=await view.record_table('PILIH '+kind.upper()+' UNTUK '+('DIUBAH' if action=='ubah' else 'DINONAKTIFKAN'),
                rows,key='user_id',initial=initial,renderer=lambda w,row=None,selected=False:profile_row(kind,w,row,selected),
                caption='Pilih profil',empty='Tidak ada profil yang dapat dipilih.')
            if selected=='refresh':
                continue
            row=next((r for r in rows if r['user_id']==selected),None)
            if row is None:
                return
            initial=selected
            if action=='nonaktif':
                await self.confirm_status(view,row,selected,'nonaktif',kind)
            else:
                await self.edit_profile(view,kind,selected)

    async def edit_profile(self,view,kind,user_id):
        row=await self._read(view,'Memuat profil terbaru...',
                             self.student_detail if kind=='siswa' else self.tutor_detail,user_id)
        if row is None:
            return
        specs=PROFILE_FIELDS[kind]
        groups=[specs[:3],specs[3:]] if kind=='siswa' else [specs]
        data={}
        for i,group in enumerate(groups):
            defaults={k:str(row.get(k) or '') for k,_,_ in group}
            notice=''
            while self.is_admin():
                answer=await view.form('UBAH PROFIL '+kind.upper(),
                    [Field(k,label,defaults[k]) for k,label,_ in group],
                    subtitle=value(row,'nama_lengkap'),step=f'{i+1}/{len(groups)}',
                    notice=notice,hint='Kosongkan kolom opsional untuk menghapus nilai.',submit_label='Lanjutkan')
                if answer is None:
                    return
                defaults={k:str(answer.get(k,'')) for k,_,_ in group}
                bad=next((label+' wajib diisi.' if k=='nama_lengkap' and not defaults[k].strip()
                          else label+f' maksimal {limit} karakter.' for k,label,limit in group
                          if (k=='nama_lengkap' and not defaults[k].strip()) or len(defaults[k].strip())>limit),None)
                if bad:
                    notice=bad
                    continue
                data.update(defaults)
                break
            else:
                return
        before=[(label,value(row,k)) for k,label,_ in specs]
        after=[(label,data[k].strip() or 'Dikosongkan') for k,label,_ in specs]
        selected=await view.page('KONFIRMASI UBAH PROFIL',[('confirm','Ya, simpan perubahan'),('back','Batal')],
            lambda w,b:details_pages([('DATA SEBELUMNYA',before),('DATA BARU',after)],w,b,full=True,paired=True),default='back')
        if selected=='confirm':
            await self._write(view,'Menyimpan profil...',self.student_update if kind=='siswa' else self.tutor_update,
                              user_id,data)


def build_controller():
    from app import session
    from app.repositories import enrollment_repo,program_repo
    from app.services import admin_management_service as svc
    user=session.get_user() or {}
    return DataUsersController(
        accounts=svc.daftar_akun,students=svc.daftar_siswa,tutors=svc.daftar_tutor,
        student_detail=svc.detail_siswa,tutor_detail=svc.detail_tutor,
        history=enrollment_repo.enrollment_siswa,schedules=svc.jadwal_tutor,
        programs=program_repo.daftar_program,status_update=svc.ubah_status_akun,
        unlock=svc.buka_kunci_akun,reset=svc.reset_password_akun,student_update=svc.ubah_siswa,
        tutor_update=svc.ubah_tutor,is_admin=lambda:session.punya_role('admin'),current_id=user.get('id'))


def menu_data_pengguna_admin(initial=None):
    from app import session
    if not session.punya_role('admin'):
        return
    user=session.get_user() or {}
    controller=build_controller()
    ConfirmationWorkspace(user.get('nama_lengkap') or user.get('username') or 'Admin').run(
        lambda view:controller.run(view,initial=initial))
