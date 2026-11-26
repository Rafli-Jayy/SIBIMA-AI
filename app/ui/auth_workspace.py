"""Satu workspace autentikasi terminal (Prompt Toolkit).

View murni: tidak membaca PostgreSQL, tidak mengatur session maupun aturan OTP.
Controller meneruskan operasi lama ke service. Animasi tidak menentukan hasil.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from typing import Callable

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.clipboard import DummyClipboard
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import DummyHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import DynamicContainer, HSplit, Layout, ScrollablePane, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Button, Frame, TextArea
from prompt_toolkit.utils import get_cwidth

from .auth_copy import concise_message

from .auth_motion import AuthMotion, FRAME_SECONDS, INTRO_SECONDS, SUCCESS_SECONDS, LOGO

STYLE = Style.from_dict({
    'brand':'#67d4e8 bold', 'title':'#e2e8f0 bold', 'muted':'#94a3b8',
    'selected':'#67d4e8 bold noreverse bg:default', 'rule':'#475569',
    'success':'#4ade80 bold', 'warning':'#fbbf24', 'error':'#f87171',
    'field':'#e2e8f0 bg:default', 'field-label':'#94a3b8',
    'field-focus':'#67d4e8 bold', 'frame.border':'#475569',
    'button':'bg:default noreverse', 'button.focused':'#67d4e8 bold noreverse bg:default',
    'error.frame.border':'#f87171', 'auth-error frame.border':'#f87171',
    'auth-success frame.border':'#4ade80',
    'auth-form button':'bg:default noreverse',
    'auth-form button.focused':'#67d4e8 bold noreverse bg:default',
})


def safe_text(value):
    """Jangan mengeksekusi markup/escape terminal dari data atau service."""
    return ''.join(ch if ch == '\n' or (ord(ch) >= 32 and not 127 <= ord(ch) <= 159) else ' '
                   for ch in str(value or ''))


def fit_line(value, width):
    """Batas berdasarkan lebar sel terminal, termasuk karakter lebar Unicode."""
    text = ' '.join(safe_text(value).split())
    if get_cwidth(text) <= width:
        return text
    if width <= 0:
        return ''
    limit = width - 1
    result = ''
    for ch in text:
        if get_cwidth(result + ch) > limit:
            break
        result += ch
    return result.rstrip() + '…'


def bounded_lines(value, width, max_lines=2):
    """Word-wrap dibatasi; satu kata sangat panjang pun tidak keluar panel."""
    width = max(1, width)
    text = ' '.join(safe_text(value).split())
    rows = []
    while text and len(rows) < max_lines - 1:
        if get_cwidth(text) <= width:
            break
        end = 0
        for idx, ch in enumerate(text):
            if get_cwidth(text[:idx+1]) > width:
                break
            end = idx+1
        end = max(1, end)
        cut = text.rfind(' ', 0, end+1)
        cut = cut if cut > 0 else end
        rows.append(fit_line(text[:cut], width))
        text = text[cut:].lstrip()
    if text:
        rows.append(fit_line(text, width))
    return '\n'.join(rows)


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    default: str = ''
    secret: bool = False


class ActionButton(Button):
    def _get_text_fragments(self):
        self.left_symbol = '❯ ' if get_app().layout.has_focus(self) else '  '
        self.right_symbol = ' '
        return super()._get_text_fragments()


class AuthWorkspace:
    def __init__(self, *, input=None, output=None, motion_enabled=None):
        if motion_enabled is None:
            motion_enabled = os.getenv('SIBIMA_NO_MOTION', '').strip().lower() not in ('1','true','yes')
        self.motion = AuthMotion(enabled=motion_enabled)
        self.mode = 'idle'
        self.title = 'MENU UTAMA'
        self.future = None
        self.control = FormattedTextControl('', focusable=True, show_cursor=False)
        self.body = Window(self.control)
        self.index = 0
        self.choices = []
        self.form_fields = {}
        kb = KeyBindings()
        menu = Condition(lambda: self.mode == 'menu')
        form = Condition(lambda: self.mode == 'form')
        message = Condition(lambda: self.mode in ('intro','message','success'))
        busy = Condition(lambda: self.mode == 'busy')

        @kb.add('up', filter=menu)
        def up(event):
            self.index = (self.index-1) % len(self.choices)
        @kb.add('down', filter=menu)
        def down(event):
            self.index = (self.index+1) % len(self.choices)
        @kb.add('enter', filter=menu)
        def choose(event):
            self.finish(self.choices[self.index][0])
        @kb.add('tab', filter=form)
        @kb.add('down', filter=form)
        def next_field(event):
            event.app.layout.focus_next()
        @kb.add('s-tab', filter=form)
        @kb.add('up', filter=form)
        def previous_field(event):
            event.app.layout.focus_previous()
        @kb.add('escape', filter=menu | form, eager=True)
        @kb.add('c-c', filter=menu | form, eager=True)
        def back(event):
            self.finish(None)
        @kb.add('enter', filter=message, eager=True)
        @kb.add('escape', filter=message, eager=True)
        @kb.add('c-c', filter=message, eager=True)
        def advance(event):
            self.finish(True)
        @kb.add('<any>', filter=busy, eager=True)
        @kb.add('enter', filter=busy, eager=True)
        @kb.add('tab', filter=busy, eager=True)
        @kb.add('escape', filter=busy, eager=True)
        @kb.add('c-c', filter=busy, eager=True)
        def ignore(event):
            pass

        root = HSplit([
            Window(FormattedTextControl(self._header),
                   height=lambda: Dimension.exact(self._header_height()),
                   align=WindowAlign.CENTER, wrap_lines=False),
            DynamicContainer(lambda: self.body),
            Window(FormattedTextControl(self._footer), height=1, align=WindowAlign.CENTER, wrap_lines=False),
        ])
        self.app = Application(layout=Layout(root, focused_element=self.control),
                               key_bindings=kb, full_screen=True, style=STYLE,
                               input=input, output=output, clipboard=DummyClipboard(),
                               mouse_support=False)

    def _width(self):
        return max(8, min(60, self.app.output.get_size().columns-2))

    def _content_width(self):
        return max(1, self._width()-6)

    def _large_form_header(self):
        size = self.app.output.get_size()
        return self.mode != 'intro' and size.rows >= 30 and size.columns >= 54

    def _header_height(self):
        if self.mode == 'intro':
            return 1
        if self.app.output.get_size().rows < 18:
            return 1
        return 9 if self._large_form_header() else 2

    def _header(self):
        # Satu identitas untuk semua layar auth; judul halaman hanya di panel.
        if self._header_height() == 1:
            return [('class:brand','S I B I M A')]
        brand = '\n' + '\n'.join(LOGO) + '\n\n' if self._large_form_header() else 'S I B I M A\n'
        subtitle = fit_line('Sistem Informasi Bimbingan Belajar', self.app.output.get_size().columns)
        return [('class:brand',brand),('class:muted',subtitle)]

    def _footer(self):
        hints = {'menu':'↑ ↓ Navigasi  |  Enter Pilih  |  Esc Kembali',
                 'form':'Tab / ↑ ↓ Pindah | Enter Pilih | Esc Kembali',
                 'intro':'Enter / Esc Lewati opening',
                 'success':'Enter / Esc Lanjutkan',
                 'message':'Enter / Esc Kembali',
                 'busy':'Operasi sedang berlangsung; tunggu hasil.'}
        value = hints.get(self.mode,'')
        if self.app.output.get_size().columns < 48 and self.mode in ('menu','form'):
            value = 'Tab / ↑ ↓ | Enter | Esc' if self.mode == 'form' else '↑ ↓ | Enter | Esc'
        return [('class:muted',fit_line(value,self.app.output.get_size().columns))]

    def _text(self, content, style='', *, center=True):
        return Window(FormattedTextControl(content), style=style,
                      align=WindowAlign.CENTER if center else WindowAlign.LEFT,
                      wrap_lines=True, dont_extend_height=True)

    def _center(self, content, *, framed=True, error=False):
        panel = Frame(content, style='class:error' if error else '') if framed else content
        # Center vertically at normal sizes; ScrollablePane is accessible on short terminals.
        centered = VSplit([Window(width=Dimension(weight=1)),
                           ScrollablePane(HSplit([Window(height=Dimension(weight=1)),
                                                  panel, Window(height=Dimension(weight=1))]),
                                          width=lambda:Dimension.exact(self._width()),
                                          show_scrollbar=False, display_arrows=False),
                           Window(width=Dimension(weight=1))])
        return centered

    def _center_form(self, body, *, error=False, success=False):
        """Centered fixed-width form with the SIRASA frame and inner scrolling."""
        body.width = lambda: Dimension.exact(self._width()-6)
        pane = ScrollablePane(
            VSplit([Window(width=2), body, Window(width=2)]),
            width=lambda: Dimension.exact(self._width()-2),
            show_scrollbar=False, display_arrows=False,
        )
        frame = Frame(pane, width=lambda: Dimension.exact(self._width()))
        frame.container.style = 'class:frame class:auth-form' + (
            ' class:auth-error' if error else ' class:auth-success' if success else '')
        def height():
            natural = pane.preferred_height(self._width()-2, pane.max_available_height).preferred + 2
            return Dimension(min=0, preferred=natural, max=natural)
        panel = VSplit([Window(),frame,Window()],height=height)
        return HSplit([Window(height=Dimension(min=0,preferred=0,weight=1)),
                       panel,
                       Window(height=Dimension(min=0,preferred=0,weight=1))])

    def _bounded_text(self, value, style, *, max_lines=2, concise=False, center=True):
        text = concise_message(value) if concise else value
        return self._text(lambda: [('class:'+style,
            bounded_lines(text, self._content_width(), max_lines))], center=center)

    def _panel_heading(self, title, subtitle=''):
        return [self._bounded_text(title,'title',max_lines=2),
                self._bounded_text(subtitle,'muted',max_lines=2),
                Window(char='─',style='class:rule',height=1)]

    def _prepare(self, mode, title, body, focus):
        self.mode, self.title, self.body = mode, title, body
        self.future = asyncio.get_running_loop().create_future()
        self.app.layout.focus(focus)
        self.app.invalidate()
        return self.future

    def finish(self, value):
        if self.future is not None and not self.future.done():
            self.future.set_result(value)
            self.mode = 'idle'
            self.app.invalidate()

    async def menu(self, title, choices, *, subtitle='', notice='', notice_style='muted', details=()):
        if not choices:
            raise ValueError('Daftar pilihan wajib memiliki isi.')
        self.choices, self.index = list(choices), 0

        def choice_width():
            return min(self._content_width(), max(24, max(get_cwidth(str(label)) for _,label in self.choices)+4))

        def rows():
            fragments = []
            for i, (_, label) in enumerate(self.choices):
                prefix = '❯ ' if i == self.index else '  '
                fragments.append(('class:selected' if i==self.index else 'class:title',
                                  prefix+fit_line(label,choice_width()-2)+'\n'))
            return fragments

        control = FormattedTextControl(rows, focusable=True, show_cursor=False)
        self.control = control
        choice_window = Window(control,wrap_lines=False,height=len(choices),align=WindowAlign.LEFT,
                               width=lambda:Dimension.exact(choice_width()))
        content = self._panel_heading(title,subtitle)
        if notice:
            content.append(self._bounded_text(notice,notice_style,concise=True))
        for detail in details:
            # User data in the registration review must not be silently truncated.
            content.append(self._text(safe_text(detail),'class:muted',center=False))
        content.extend([Window(height=lambda: Dimension.exact(1 if self.app.output.get_size().rows >= 18 else 0)),
                        VSplit([Window(),choice_window,Window()]),
                        Window(height=lambda: Dimension.exact(1 if self.app.output.get_size().rows >= 18 else 0))])
        return await self._prepare('menu',title,self._center_form(
            HSplit(content),error=bool(notice and notice_style=='error')),control)

    def _field_prompt(self, area):
        """Focus marker with a stable width, following the SIRASA form pattern."""
        focused = self.mode == 'form' and self.app.layout.has_focus(area)
        return [('class:field-focus' if focused else 'class:field-label',
                 '❯ ' if focused else '  ')]

    def _field_label(self, label, area):
        def render():
            focused = self.mode == 'form' and self.app.layout.has_focus(area)
            return [('class:field-focus' if focused else 'class:field-label',
                     fit_line(label,self._content_width()))]
        return Window(FormattedTextControl(render),height=1,wrap_lines=False)

    async def form(self, title, fields, *, subtitle='', notice='', notice_style='error', step='', hint='', submit_label='Lanjutkan'):
        if not fields:
            raise ValueError('Formulir wajib memiliki kolom.')
        areas = {}
        caption = ' · '.join(part for part in (step,subtitle) if part)
        parts = self._panel_heading(title,caption)
        default_hint = 'Akses khusus pengguna terdaftar' if title == 'LOGIN PENGGUNA' else 'Isi kolom untuk melanjutkan.'
        parts.append(self._bounded_text(notice or hint or default_hint,
            notice_style if notice else 'muted',concise=bool(notice)))
        def submit():
            values = {key: area.text for key,area in areas.items()}
            self.finish(values)
        def back():
            self.finish(None)
        for f in fields:
            if f.secret and f.default:
                raise ValueError('Password/OTP tidak boleh diisi ulang dari default.')
            def accept(buf):
                if get_app().layout.has_focus(list(areas.values())[-1]):
                    submit()
                else:
                    get_app().layout.focus_next()
                return True
            area = TextArea(text=f.default, multiline=False, password=f.secret, height=1,
                            style='class:field', accept_handler=accept, history=DummyHistory(),
                            prompt=lambda key=f.key: self._field_prompt(areas[key]),
                            wrap_lines=False)
            areas[f.key] = area
            # Semua form: label dan input berurutan, tanpa spacer antarkolom.
            parts.extend([self._field_label(f.label,area),area])
        parts.extend([Window(height=lambda: Dimension.exact(1 if self.app.output.get_size().rows >= 18 else 0)), ActionButton(submit_label,handler=submit,width=22),
                      ActionButton('Kembali',handler=back,width=22)])
        self.form_fields = areas
        try:
            return await self._prepare(
                'form', title, self._center_form(HSplit(parts),error=bool(notice and notice_style=='error')),
                next(iter(areas.values())))
        finally:
            # Jangan tinggalkan password/OTP di buffer ketika layar diganti.
            for f in fields:
                if f.secret:
                    areas[f.key].buffer.reset()
            self.form_fields = {}

    async def message(self, title, content, *, kind='info', auto=False):
        mode = 'success' if kind=='success' else 'message'
        self.motion.start()
        def display():
            glyph = self.motion.success_mark() if kind=='success' else ('✗' if kind=='error' else '!')
            color = 'success' if kind=='success' else ('error' if kind=='error' else 'warning')
            return [('class:'+color,glyph)]
        control = FormattedTextControl([('class:field-focus','❯ Lanjutkan' if kind=='success' else '❯ Kembali')],focusable=True,show_cursor=False)
        # Preserve purposeful line breaks (name, role, status) in success pages;
        # each authored line is width-limited rather than spilling outside the panel.
        def result_text():
            value = safe_text(content)
            lines = [line for line in value.splitlines() if line.strip()]
            if title != 'AUTENTIKASI BERHASIL':
                return [('class:'+('error' if kind=='error' else 'muted'),
                         bounded_lines(concise_message(value),self._content_width(),2))]
            return [('class:muted','\n'.join(
                fit_line(line,self._content_width()) for line in lines[:4]))]
        body = self._center_form(HSplit([
            self._bounded_text(title,'title'),Window(FormattedTextControl(display),
                height=1,align=WindowAlign.CENTER,always_hide_cursor=True),
            Window(char='─',style='class:rule',height=1),
            self._text(result_text),
            Window(height=1),Window(control,height=1,align=WindowAlign.CENTER,
                always_hide_cursor=True),
        ]),error=kind=='error',success=kind=='success')
        future = self._prepare(mode,title,body,control)
        if auto:
            if self.motion.enabled:
                async def advance():
                    await asyncio.sleep(SUCCESS_SECONDS)
                    if self.future is future:
                        self.finish(True)
                timer = asyncio.create_task(advance())
                try:
                    await future
                finally:
                    timer.cancel()
                    await asyncio.gather(timer,return_exceptions=True)
            else:
                self.finish(True)
        else:
            await future

    async def opening(self):
        if not self.motion.enabled:
            return
        self.motion.start()
        def display():
            return [('class:title','SELAMAT DATANG\n\n'),
                    ('class:brand',self.motion.logo(self._width())+'\n\n'),
                    ('class:title','Sistem Informasi Bimbingan Belajar\n'),
                    ('class:muted','SIBIMA-AI')]
        control=FormattedTextControl(display,focusable=True,show_cursor=False)
        future=self._prepare('intro','OPENING',self._center(Window(control, wrap_lines=False,
                               align=WindowAlign.CENTER,dont_extend_height=True),framed=False),control)
        async def advance():
            await asyncio.sleep(INTRO_SECONDS)
            if self.future is future:
                self.finish(True)
        task=asyncio.create_task(advance())
        try:
            await future
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)

    async def busy(self,title,fn: Callable,*args):
        """UI menunggu operasi sebenarnya; tidak membuat progres persentase palsu."""
        self.motion.start()
        def display():
            return [('class:brand',fit_line(self.motion.spinner()+' '+safe_text(title), self._content_width())+'\n\n'),
                    ('class:brand',self.motion.marquee()),('class:muted','\nMohon tunggu sebentar.')]
        control=FormattedTextControl(display,focusable=True,show_cursor=False)
        self._prepare('busy',title,self._center_form(HSplit([
            self._bounded_text('MOHON TUNGGU','title'),
            Window(char='─',style='class:rule',height=1),
            Window(control,wrap_lines=False,align=WindowAlign.CENTER,dont_extend_height=True)
        ])),control)
        try:
            return await asyncio.to_thread(fn,*args)
        finally:
            self.finish(None)

    def run(self, controller):
        """Keluar dari alternate screen sebelum dashboard CLI lama dijalankan."""
        async def flow():
            try:
                result = await controller(self)
                self.app.exit(result=result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.app.exit(exception=exc)
        async def animate():
            previous = None
            while True:
                if self.mode in ('intro','busy','success'):
                    frame = (self.mode,self.motion.logo(self._width()) if self.mode=='intro' else
                             self.motion.spinner()+self.motion.marquee() if self.mode=='busy' else self.motion.success_mark())
                    if frame != previous:
                        previous = frame
                        self.app.invalidate()
                else:
                    previous = None
                await asyncio.sleep(FRAME_SECONDS)
        def start():
            self.app.create_background_task(flow())
            if self.motion.enabled:
                self.app.create_background_task(animate())
        return self.app.run(pre_run=start)
