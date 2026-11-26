"""Centered keyboard navigation for AI; no changes to conversation state.

Runs inline in the caller's temporary screen; does not enter a second
alternate screen and does not touch normal chat scrollback.
"""
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, HSplit, Layout, Window
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.layout.controls import FormattedTextControl

from ..admin_workspace import MENU_WIDTH, STYLE, fragments, line, menu_rows


class AINavigation:
    def __init__(self,title,choices,default=None,*,input=None,output=None):
        self.title=title
        self.choices=list(choices)
        if not self.choices:
            raise ValueError('Navigasi memerlukan pilihan.')
        self.index=next((i for i,label in enumerate(self.choices) if label==default),0)
        keys=KeyBindings()

        @keys.add('up')
        def up(event):
            self.index=(self.index-1)%len(self.choices)

        @keys.add('down')
        def down(event):
            self.index=(self.index+1)%len(self.choices)

        @keys.add('enter')
        def choose(event):
            event.app.exit(result=self.choices[self.index])

        @keys.add('escape',eager=True)
        @keys.add('c-c',eager=True)
        def cancel(event):
            event.app.exit(result=None)

        control=FormattedTextControl(lambda:fragments(self.rows()),focusable=True,show_cursor=False)
        # Inline like Questionary; the existing ChatScreen controls scrollback.
        root=HSplit([Window(control,align=WindowAlign.CENTER,wrap_lines=False,
                            height=lambda:Dimension.exact(len(self.rows())),always_hide_cursor=True)])
        self.app=Application(layout=Layout(root,focused_element=control),key_bindings=keys,
                             full_screen=False,erase_when_done=True,style=STYLE,input=input,output=output)

    def rows(self):
        width=max(1,min(MENU_WIDTH,self.app.output.get_size().columns-2))
        choices=[('back' if label=='Keluar dari asisten' else str(i),label)
                 for i,label in enumerate(self.choices)]
        menu,selected=menu_rows(choices,self.index,width)
        # Keep the selected choice visible in small terminals.
        limit=max(1,self.app.output.get_size().rows-7)
        if len(menu)>limit:
            start=max(0,min(selected-limit//2,len(menu)-limit))
            menu=menu[start:start+limit]
        return [line(self.title.upper(),width,'title','center'),[],*menu,[],
                line('↑ ↓ Pilih · Enter · Esc Kembali',width,'muted','center')]

    def run(self):
        return self.app.run()


def choose_navigation(title,choices,default=None):
    return AINavigation(title,choices,default).run()
