"""UI-003D: one workspace for all Prioritas modules, no business writes here."""
from __future__ import annotations

from .admin_workspace import Snapshot, changed_metrics, priority_pages
from .admin_confirmation import ConfirmationWorkspace, build_confirmation_controller
from .admin_enrollment import build_enrollment_controller
from .admin_billing import build_billing_controller
from .admin_navigation import KELOMPOK_MENU

ROUTES=tuple((code,label) for label,code in KELOMPOK_MENU[0][1])


class PriorityController:
    """Own the parent menu and delegate modules on the same running UI."""
    def __init__(self,*,summary,modules,is_admin,previous=None):
        self.summary=summary
        self.modules=modules
        self.is_admin=is_admin
        # The dashboard snapshot is read-only and remains a useful comparison
        # even after a transient read error.
        self.previous=self._snapshot(previous.summary) if isinstance(previous,Snapshot) else None

    @staticmethod
    def _snapshot(data):
        if not isinstance(data,dict) or not data:
            return Snapshot(None,None)
        data=dict(data)
        # In this workspace the overdue count follows the same database date
        # used by the actual billing list (UI-003C), even at a timezone boundary.
        data['tagihan_terlambat']=data.get('tagihan_tunggakan')
        return Snapshot(data,None)

    async def run(self,view):
        focus=ROUTES[0][0]
        while self.is_admin():
            try:
                data=await view.busy('Memuat pusat prioritas...',self.summary)
                snapshot=self._snapshot(data)
            except Exception:
                snapshot=Snapshot(None,None)

            changed=changed_metrics(self.previous,snapshot)
            if snapshot.summary is not None:
                self.previous=snapshot
            if not self.is_admin():
                return
            action=await view.page('PUSAT PRIORITAS',[
                *ROUTES,('refresh','Muat ulang'),('back','Kembali ke dashboard')],
                lambda w,b:priority_pages(snapshot,w,b,changed),default=focus)
            if action in (None,'back') or not self.is_admin():
                return
            if action=='refresh':
                # Preserve the highlighted menu when the R shortcut is used.
                focus=getattr(view,'refresh_focus',None) or focus
                continue
            if action in self.modules:
                focus=action
                await self.modules[action].run(view)
                # When any module returns, reload all three domains in one summary.
                # Mutations, notifications and retry decisions belong to its service.


def menu_prioritas_admin(*,previous=None):
    from app import session
    from app.repositories import admin_dashboard_repo
    if not session.punya_role('admin'):
        return
    user=session.get_user() or {}
    controller=PriorityController(
        summary=admin_dashboard_repo.ringkasan_admin,
        modules={
            'konfirmasi':build_confirmation_controller(),
            'pendaftaran':build_enrollment_controller(),
            'pembayaran':build_billing_controller(),
        },
        is_admin=lambda:session.punya_role('admin'),
        previous=previous,
    )
    return ConfirmationWorkspace(user.get('nama_lengkap') or user.get('username') or 'Admin').run(controller.run)
