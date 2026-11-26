"""Shared presentation and loading helpers for UI-007B–F (student only)."""
from __future__ import annotations

from functools import partial

from .student_workspace import StudentWorkspace, _name
from .admin_confirmation import details_pages, empty_state_rows, value, wrap
from .admin_workspace import line, pad, clip, paginate_blocks
from .admin_academic import add_band, add_panel, stat_tile


class StudentFeatureWorkspace(StudentWorkspace):
    async def result(self, title, message, kind='info'):
        """Visible result is concise; the original message is available on demand."""
        message = str(message)
        tone = {'success': 'success', 'error': 'error'}.get(kind, 'warning')

        def preview(w, b):
            parts = wrap(message, max(1, min(60, w-4)))
            text = ' '.join(parts[:2]) if len(parts) <= 2 else parts[0]+' '+parts[1]+' …'
            blocks = []
            # Avoid the inaccurate Admin-specific "Keputusan tersimpan" shortcut.
            add_panel(blocks, 'HASIL', lambda cw: [
                line(s, cw, tone, 'center') for s in wrap(text, cw)[:2]
            ], min(64,w), b)
            cw = min(64,w)
            offset = (w-cw)//2
            return [[[( '', ' '*offset), *row] for row in page]
                    for page in paginate_blocks(blocks,b)]
        while True:
            action = await self.page(title, [('detail','Detail hasil'),('back','Lanjutkan')], preview, default='back')
            if action != 'detail':
                return
            await self.page('DETAIL HASIL', [('back','Kembali')],
                lambda w,b: paginate_blocks([[line(t,w,tone)] for t in wrap(message,w)],b))


def run_student(controller, user=None):
    """Open a bounded student workspace; legacy AI entry still runs separately."""
    from app import session
    actual = session.get_user() or {}
    if actual.get('role') != 'siswa' or actual.get('status') != 'aktif':
        return None
    if user is not None and user.get('id') != actual.get('id'):
        return None
    return StudentFeatureWorkspace(_name(actual)).run(controller)


def fields(row, specs):
    return [(label, value(row,key)) for label,key in specs]


def column(label, key, weight=1):
    return (label, key, weight)


def table_renderer(columns, status_tone=None):
    """Single selectable row, compact on small terminals. Full values in detail."""
    def render(w, item=None, selected=False):
        if w < 16:
            text = columns[0][0] if item is None else _cell(item, columns[0][1])
            return [('class:selected' if selected else 'class:title', clip(('❯ ' if selected else '  ')+text,w))]
        cols = columns if w >= 74 else columns[:3] if w >= 44 else columns[:2]
        available = max(len(cols),w-2-(len(cols)-1))
        weights = sum(c[2] for c in cols)
        sizes = [max(1,available*c[2]//weights) for c in cols]
        sizes[-1] += available-sum(sizes)
        tone = 'class:selected' if selected else 'class:muted' if item is None else 'class:title'
        out = [(tone,'❯ ' if selected else '  ')]
        for i,((title,key,_),size) in enumerate(zip(cols,sizes)):
            if i:
                out.append((tone,' '))
            style = tone
            if title == 'Status' and status_tone and item is not None and not selected:
                style = 'class:'+status_tone(item)
            out.append((style,pad(title if item is None else _cell(item,key),size)))
        return out
    return render


def _cell(item,key):
    v = key(item) if callable(key) else value(item,key)
    return '—' if v is None else str(v)


def empty_pages(message,caption='Data tersedia',*,width,budget):
    return [empty_state_rows(width,budget,caption,message)]


def metrics_pages(metrics,width,budget,*,note='',extra=()):
    """Different UI geometry: inline tiles plus full-width information bands."""
    blocks=[]
    for i in range(0,len(metrics),3):
        add_band(blocks,[(label,lambda w,v=v,d=d: stat_tile(v,d,w))
                         for label,v,d in metrics[i:i+3]],width,budget)
    for title,renderer in extra:
        add_panel(blocks,title,renderer,width,budget)
    if note:
        for t in wrap(note,max(1,width-2)):
            blocks.append([line(t,width,'muted','center')])
    return paginate_blocks(blocks,budget)


def content_pages(sections, documents, width, budget):
    """Identity cards plus full-width reading panels; preserve paragraphs and long content."""
    blocks=details_pages(sections,width,budget,full=True,paired=True) if sections else []
    for title,body in documents:
        def render(cw, body=body):
            rows=[]
            for paragraph in str(body or '—').splitlines() or ['—']:
                if not paragraph.strip():
                    rows.append([])
                    continue
                margin=1 if cw>=8 else 0
                rows.extend([('', ' '*margin), *line(t,cw-2*margin,'title'),('', ' '*margin)]
                            for t in wrap(paragraph,max(1,cw-2*margin)))
            return rows
        add_panel(blocks,title,render,width,budget)
    return paginate_blocks(blocks,budget)


class FeatureController:
    """Services own the authorization, validation, transactions, and side effects."""
    def __init__(self, view):
        self.view=view

    async def read(self,fn,*args,service=False,**kwargs):
        try:
            result=await self.view.busy('Memuat data...',partial(fn,*args,**kwargs))
            if service:
                ok,result=result
                if not ok:
                    await self.view.result('DATA TIDAK TERSEDIA',str(result),'error')
                    return None
            if result is None:
                await self.view.result('DATA TIDAK TERSEDIA','Data tidak ditemukan.','error')
            return result
        except Exception as exc:
            await self.view.result('DATA GAGAL DIMUAT',
                'Data tidak dapat dimuat ('+type(exc).__name__+'). Coba lagi.','error')
            return None

    async def mutate(self,fn,*args,service=False,**kwargs):
        try:
            result=await self.view.busy('Memproses tindakan...',partial(fn,*args,**kwargs))
        except Exception as exc:
            # Do not automatically retry a transaction with an uncertain outcome.
            await self.view.result('HASIL BELUM DIPASTIKAN',
                'Periksa status terbaru sebelum mencoba lagi ('+type(exc).__name__+').','error')
            return None
        if service:
            ok,message=result
            await self.view.result('BERHASIL' if ok else 'BELUM BERHASIL',str(message),'success' if ok else 'error')
            return bool(ok)
        return result

    async def page(self,title,choices,sections,*,notice='',default=None):
        return await self.view.page(title,choices,
            lambda w,b:details_pages(sections,w,b,notice=notice,full=True,paired=True),
            default=default)

    async def details(self,title,sections,*,notice=''):
        return await self.page(title,[('back','Kembali')],sections,notice=notice)

    async def confirm(self,title,sections,*,label='Ya, lanjutkan',notice=''):
        return await self.page(title,[('confirm',label),('back','Batal')],sections,
            notice=notice,default='back') == 'confirm'

    async def pick(self,title,rows,renderer,*,caption='Pilih untuk melihat detail',empty='Belum ada data.',initial=None,key=None):
        # Use a screen-local index for records without unique IDs (e.g. absensi).
        # No surrogate UI index is ever passed to a service.
        keyed=[dict(r,_ui_key=r[key] if key else i) for i,r in enumerate(rows)]
        selected=await self.view.record_table(title,keyed,key='_ui_key',renderer=renderer,
            caption=caption,empty=empty,initial=initial)
        if selected == 'refresh':
            return 'refresh'
        return next((r for r in keyed if r['_ui_key']==selected),None)

    async def browse(self,title,loader,renderer,detail,*,empty='Belum ada data.',
                     caption='Pilih untuk melihat detail',key=None):
        focus=None
        while True:
            rows=await loader()
            if rows is None:
                return None
            row=await self.pick(title,rows,renderer,caption=caption,empty=empty,initial=focus,key=key)
            if row == 'refresh':
                continue
            if row is None:
                return None
            focus=row['_ui_key']
            result=await detail(row)
            if result is not None:
                return result
