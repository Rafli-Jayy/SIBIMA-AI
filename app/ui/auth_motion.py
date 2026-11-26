"""Efek visual autentikasi. Tidak melakukan I/O atau menentukan hasil bisnis."""
from __future__ import annotations

from time import monotonic

SPINNER = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
FRAME_SECONDS = 0.10
INTRO_SECONDS = 1.6
SUCCESS_SECONDS = 1.1

LOGO = (
    '███████╗██╗██████╗ ██╗███╗   ███╗ █████╗ ',
    '██╔════╝██║██╔══██╗██║████╗ ████║██╔══██╗',
    '███████╗██║██████╔╝██║██╔████╔██║███████║',
    '╚════██║██║██╔══██╗██║██║╚██╔╝██║██╔══██║',
    '███████║██║██████╔╝██║██║ ╚═╝ ██║██║  ██║',
    '╚══════╝╚═╝╚═════╝ ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝',
)


class AuthMotion:
    def __init__(self, enabled=True, clock=monotonic):
        self.enabled = enabled
        self.clock = clock
        self.started_at = clock()

    def start(self):
        self.started_at = self.clock()

    def elapsed(self):
        return max(0.0, self.clock() - self.started_at)

    def spinner(self):
        return SPINNER[int(self.elapsed() / FRAME_SECONDS) % len(SPINNER)] if self.enabled else '…'

    def marquee(self, width=15):
        if not self.enabled:
            return ''
        span = min(3, width)
        distance = max(1, width-span)
        tick = int(self.elapsed()/FRAME_SECONDS) % (2*distance)
        pos = min(tick, 2*distance-tick)
        return '·'*pos + '━'*span + '·'*(width-pos-span)

    def logo(self, width):
        if width < max(map(len, LOGO)) + 2:
            return 'S I B I M A'
        full = max(map(len, LOGO))
        count = full if not self.enabled else min(full, int(full*self.elapsed()/0.85))
        return '\n'.join(row[:count].ljust(full) for row in LOGO)

    def success_mark(self):
        frames = ('· ✓ ·', '· ✧ ✓ ✧ ·', '✧ · ✓ · ✧', '✓')
        if not self.enabled:
            return '✓'
        return frames[min(int(self.elapsed()/0.20), len(frames)-1)]
