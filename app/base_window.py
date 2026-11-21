"""所有自绘窗口共用的底座：物理像素缓冲区 + 整数倍像素缩放 + 拖动。"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter


class PixelCanvas:
    """把窗口画进一张 1:1 物理像素的缓冲区再整体贴回。

    这样所有坐标都是真实像素，配合整数倍材质缩放，任何 DPI 下都不会糊。
    """

    _buf: QImage | None = None
    _dpr: float = 1.0
    S: int = 2                      # 一个"像素单位"= S 个物理像素
    W_UNITS: int = 216
    H_UNITS: int = 78

    # ------------------------------------------------------------------
    def init_canvas(self, cfg) -> None:
        screen = QGuiApplication.primaryScreen()
        dpr = 1.0
        phys_h = 1080
        if screen is not None:
            dpr = float(screen.devicePixelRatio() or 1.0)
            phys_h = int(screen.geometry().height() * dpr)
        self._dpr = dpr
        manual = int(cfg.get("ui.pixel_scale", 0) or 0)
        auto = max(1, min(5, int(round(phys_h / 720.0))))
        base = manual if manual > 0 else auto
        scale = float(cfg.get("font_scale", 1.0))
        # 基准倍率：尺寸档位在这之上加档（+1 就是大一号），始终是整数倍
        self._base_s = max(1, min(8, int(round(base * scale))))
        self.S = self._base_s

    # ------------------------------------------------------------------
    def apply_units_size(self) -> None:
        dpr = self._dpr or 1.0
        w = max(1, int(round(self.W_UNITS * self.S / dpr)))
        h = max(1, int(round(self.H_UNITS * self.S / dpr)))
        self.setFixedSize(w, h)

    def u(self, units: float) -> int:
        """单位 → 物理像素。"""
        return int(round(units * self.S))

    def lx(self, units: float) -> int:
        """单位 → Qt 逻辑像素（放置子控件用）。"""
        return int(round(units * self.S / (self._dpr or 1.0)))

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        dpr = self._dpr or 1.0
        w = max(1, int(round(self.width() * dpr)))
        h = max(1, int(round(self.height() * dpr)))
        if self._buf is None or self._buf.width() != w or self._buf.height() != h:
            self._buf = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        self._buf.setDevicePixelRatio(1.0)
        self._buf.fill(Qt.GlobalColor.transparent)
        bp = QPainter(self._buf)
        bp.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        bp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        bp.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
        try:
            self.render_canvas(bp, w, h)
        finally:
            bp.end()
        self._buf.setDevicePixelRatio(dpr)
        out = QPainter(self)
        out.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        out.drawImage(0, 0, self._buf)
        out.end()

    def render_canvas(self, p: QPainter, w: int, h: int) -> None:
        raise NotImplementedError


class DragMixin:
    """无边框窗口拖动（带边界吸附与位置持久化回调）。"""

    _drag_offset: QPoint | None = None
    _drag_moved: bool = False

    def begin_drag(self, global_pos: QPoint) -> None:
        self._drag_offset = global_pos - self.frameGeometry().topLeft()
        self._drag_moved = False

    def update_drag(self, global_pos: QPoint) -> None:
        if self._drag_offset is None:
            return
        target = global_pos - self._drag_offset
        if (target - self.pos()).manhattanLength() > 0:
            self._drag_moved = True
        self.move(target)

    def end_drag(self, global_pos: QPoint) -> bool:
        """返回是否真的移动过。"""
        self._drag_offset = None
        return bool(self._drag_moved)
