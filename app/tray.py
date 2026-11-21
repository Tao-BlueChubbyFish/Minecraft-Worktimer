"""系统托盘：最小化后计时继续，点击图标恢复窗口。"""
from __future__ import annotations

from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QSystemTrayIcon

from . import __version_label__, engine, theme


class Tray(QSystemTrayIcon):
    def __init__(self, widget, pal):
        icon = QIcon(theme.pixmap_icon(pal, 64))
        super().__init__(icon, widget)
        self.widget = widget
        self._notified = False
        self._last_tip = ""
        self.setToolTip(f"MC 工时牌 {__version_label__}")
        self.activated.connect(self._on_activated)

    # ------------------------------------------------------------------
    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.widget.toggle_visible()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            self.widget.open_menu(QCursor.pos())
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.widget.open_time_dialog()

    def refresh(self, snap, evening_choice: str | None = None) -> None:
        if snap.state == engine.ST_OVERTIME:
            if evening_choice == "home":
                tip = "MC 工时牌 · 今天已收工"
            else:
                tip = f"MC 工时牌 · 今日已加班 {engine.humanize(snap.overtime_minutes)}"
        elif snap.state == engine.ST_LUNCH:
            tip = f"MC 工时牌 · 午休中，还有 {engine.humanize(snap.lunch_left_minutes)}"
        elif snap.state == engine.ST_WEEKEND:
            tip = "MC 工时牌 · 今天休息"
        elif snap.state == engine.ST_UNSET:
            tip = f"MC 工时牌 {__version_label__} · 还没设置今天的上班时间"
        elif snap.state == engine.ST_BEFORE:
            tip = f"MC 工时牌 {__version_label__} · 距离上班 {engine.humanize(snap.to_work_minutes)}"
        else:
            tip = f"MC 工时牌 {__version_label__} · 距离下班 {engine.humanize(snap.remaining_minutes)}"
        if tip != self._last_tip:
            self._last_tip = tip
            self.setToolTip(tip)

    def notify_hidden(self) -> None:
        if self._notified:
            return
        self._notified = True
        try:
            self.showMessage("MC 工时牌", "已最小化到托盘，计时继续运行。点击托盘图标可以恢复窗口。",
                             QSystemTrayIcon.MessageIcon.Information, 4000)
        except Exception:
            pass
