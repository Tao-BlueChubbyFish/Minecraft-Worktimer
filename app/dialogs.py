"""MC 风格的对话框：设置上班时间 / 累计加班 / 二次确认。"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, time as dt_time

from PySide6.QtCore import QRect, Qt
from PySide6.QtCore import QUrl
from PySide6.QtGui import (QColor, QCursor, QDesktopServices, QFont, QGuiApplication,
                           QPainter)
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QWidget

from . import __version__, __version_label__, engine, pixel_font, style, theme
from .base_window import DragMixin, PixelCanvas

# 休息日那七个小格子里的字：一 二 三 四 五 六 日
_DAY_CH = ("一", "二", "三", "四", "五", "六", "日")


class MCDialog(PixelCanvas, DragMixin, QDialog):
    W_UNITS = 200
    H_UNITS = 104
    TITLE = ""
    SHOW_ICON = True

    def __init__(self, parent, cfg, pal, S: int, dpr: float):
        super().__init__(parent)
        self.cfg = cfg
        self.pal = pal
        self.S = max(1, int(S))
        self._dpr = float(dpr or 1.0)
        self._buf = None
        self.family = pixel_font.pixel_family()

        self.setWindowFlags(Qt.WindowType.Dialog
                            | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFont(self._qfont(9))
        self.setStyleSheet(style.dialog_qss(pal, self._font_px(9), self.family))
        self.setFixedSize(self.lx(self.W_UNITS), self.lx(self.H_UNITS))
        self._center_on_parent(parent)

    # ------------------------------------------------------------------
    def _font_px(self, units: float) -> int:
        return max(9, int(round(units * self.S / self._dpr)))

    def _qfont(self, units: float, bold: bool = False) -> QFont:
        f = QFont(self.family)
        f.setPixelSize(self._font_px(units))
        f.setBold(bold)
        return f

    def _place(self, widget, x, y, w, h) -> None:
        widget.setGeometry(self.lx(x), self.lx(y), self.lx(w), self.lx(h))

    def _center_on_parent(self, parent) -> None:
        screen = QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else QRect(0, 0, 2560, 1440)
        if parent is not None and parent.isVisible():
            pg = parent.frameGeometry()
            x = pg.center().x() - self.width() // 2
            y = pg.center().y() - self.height() // 2 + self.lx(20)
        else:
            x = area.center().x() - self.width() // 2
            y = area.center().y() - self.height() // 2
        x = max(area.left() + 8, min(x, area.right() - self.width() - 8))
        y = max(area.top() + 8, min(y, area.bottom() - self.height() - 8))
        self.move(x, y)

    # ------------------------------------------------------------------
    def render_canvas(self, p: QPainter, w: int, h: int) -> None:
        S = self.S
        pal = self.pal
        p.fillRect(QRect(2 * S, 2 * S, w, h), QColor(0, 0, 0, 60))
        theme.draw_panel(p, 0, 0, w, h, S, pal)
        hh = self.u(18)
        # 对话框的标题顶在上边，雪只能压 2 单位，不然白字会陷进雪里
        theme.draw_grass_strip(p, w, hh, S, pal, keep_clear=(0, w), clear_max=2)
        theme.fill(p, 0, hh, w, S, QColor(pal["outline"]))

        x = self.u(7)
        if self.SHOW_ICON:
            icon_px = self.u(12)
            theme.draw_image_outlined(p, x, self.u(3), icon_px,
                                      theme.iso_block(pal), S, pal, outline=False)
            x += icon_px + self.u(6)
        title_h = 12 * S
        pixel_font.draw_cjk(p, x, self.u(14) - title_h, self.title_text(),
                            title_h, QColor(pal["text_on_grass"]), self.family,
                            shadow=QColor(pal["text_shadow"]), bold=True)
        self.render_body(p, w, h)

    def title_text(self) -> str:
        return self.TITLE

    def render_body(self, p: QPainter, w: int, h: int) -> None:
        pass

    # ------------------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin_drag(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.update_drag(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self.end_drag(event.globalPosition().toPoint())
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.raise_()
        self.activateWindow()


class TimeInput(PixelCanvas, QWidget):
    """自绘的 HH:MM 输入框：MC 黑色文本框观感，支持键盘 / 滚轮 / 点击分段编辑。"""

    W_UNITS = 76
    H_UNITS = 19

    def __init__(self, parent, pal, S, dpr, family, value):
        super().__init__(parent)
        self.pal = pal
        self.S = max(1, int(S))
        self._dpr = float(dpr or 1.0)
        self.family = family
        self._buf = None
        self._h = value.hour
        self._m = value.minute
        self._part = 0          # 0 = 时, 1 = 分
        self._buf_digits = ""
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(self.lx(self.W_UNITS), self.lx(self.H_UNITS))
        self.setCursor(QCursor(Qt.CursorShape.IBeamCursor))

    # ------------------------------------------------------------------
    @property
    def value(self):
        return datetime.now().replace(hour=self._h, minute=self._m,
                                      second=0, microsecond=0).time()

    def set_value(self, t) -> None:
        self._h, self._m, self._buf_digits = t.hour, t.minute, ""
        self.update()

    # ------------------------------------------------------------------
    def render_canvas(self, p: QPainter, w: int, h: int) -> None:
        S = self.S
        pal = self.pal
        theme.fill(p, 0, 0, w, h, QColor("#141414"))
        theme.fill(p, 0, 0, w, S, QColor("#000000"))
        theme.fill(p, 0, 0, S, h, QColor("#000000"))
        theme.fill(p, 0, h - S, w, S, QColor(pal["bevel_dark"]))
        theme.fill(p, w - S, 0, S, h, QColor(pal["bevel_dark"]))

        text = f"{self._h:02d}:{self._m:02d}"
        k = max(2, int(round((h * 0.52) / pixel_font.GLYPH_H)))
        tw = pixel_font.text_width(text, k)
        th = pixel_font.text_height(k)
        tx = (w - tw) // 2
        ty = (h - th) // 2
        pixel_font.draw_bits(p, tx, ty, text, k, QColor("#f2f2f2"))

        # 当前编辑段下划线
        hw = pixel_font.text_width("00", k)
        colon = (pixel_font.GLYPH_W + pixel_font.GLYPH_GAP) * k
        ux = tx if self._part == 0 else tx + hw + colon
        theme.fill(p, ux, ty + th + S, hw, S, QColor(pal["accent"]))

        if self.hasFocus():
            theme.fill(p, 0, 0, w, S, QColor(pal["accent"]).darker(120))

    # ------------------------------------------------------------------
    def _apply_digit(self, d: str) -> None:
        self._buf_digits += d
        target = self._buf_digits[-2:]
        n = int(target)
        if self._part == 0:
            self._h = min(23, n)
            if len(self._buf_digits) >= 2 or self._h * 10 > 23:
                self._part, self._buf_digits = 1, ""
        else:
            self._m = min(59, n)
            if len(self._buf_digits) >= 2 or self._m * 10 > 59:
                self._buf_digits = ""
        self.update()

    def _nudge(self, delta: int) -> None:
        self._buf_digits = ""
        if self._part == 0:
            self._h = (self._h + delta) % 24
        else:
            self._m = (self._m + delta) % 60
        self.update()

    def keyPressEvent(self, event):  # noqa: N802
        key = event.key()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            self._apply_digit(str(key - Qt.Key.Key_0))
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._part = 1 - self._part
            self._buf_digits = ""
            self.update()
            return
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = 1
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                step = 5
            self._nudge(step if key == Qt.Key.Key_Up else -step)
            return
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._buf_digits = ""
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):  # noqa: N802
        self._nudge(1 if event.angleDelta().y() > 0 else -1)

    def mousePressEvent(self, event):  # noqa: N802
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._part = 0 if event.position().x() < self.width() / 2 else 1
        self._buf_digits = ""
        self.update()

    def focusInEvent(self, event):  # noqa: N802
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):  # noqa: N802
        super().focusOutEvent(event)
        self.update()


class TimeDialog(MCDialog):
    W_UNITS = 202
    H_UNITS = 146
    TITLE = "设置上班时间"
    REMEMBER_TEXT = "以后每天用这个时间，不再问我"

    def __init__(self, parent, cfg, pal, S, dpr, current):
        self.result_time = None
        # 还没设过天气才问。这个窗每个工作日都会弹，天天问一遍「要不要真实天气」
        # 比不问还烦，所以问过一次（选什么都算）就彻底不再出现。
        self.ask_weather = (not bool(str(cfg.get("weather.place", "") or "").strip())
                            and not bool(cfg.get("weather.asked", False)))
        self.use_real = False
        self.place = ""
        if self.ask_weather:
            self.H_UNITS = 200
        super().__init__(parent, cfg, pal, S, dpr)

        default = engine.parse_hhmm(self.cfg.get("schedule.default_work_start", "09:00"),
                                    dt_time(9, 0))
        start = current or default
        self._input = TimeInput(self, pal, self.S, self._dpr, self.family, start)
        self._place(self._input, 14, 42, TimeInput.W_UNITS, TimeInput.H_UNITS)
        self._input.setFocus()

        presets = [("08:00", dt_time(8, 0)), ("08:30", dt_time(8, 30)),
                   ("09:00", dt_time(9, 0)), ("现在", None)]
        for i, (text, t) in enumerate(presets):
            b = QPushButton(text, self)
            b.setFont(self._qfont(7))
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._place(b, 14 + i * 44, 68, 40, 13)
            b.clicked.connect(lambda _=False, tt=t: self._apply_preset(tt))

        # 记住这个时间：一块透明的可选中按钮盖在自绘的方框上，
        # 外观还是 MC 的方块，行为是标准复选（点字也能切）
        self._chk = QPushButton("", self)
        self._chk.setCheckable(True)
        self._chk.setChecked(bool(self.cfg.get("schedule.remember_start", False)))
        self._chk.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._chk.setStyleSheet("QPushButton{background:transparent;border:none;}"
                                "QPushButton:hover{background:rgba(255,255,255,26);}")
        self._place(self._chk, 12, 82, 178, 16)
        self._chk.toggled.connect(lambda _=False: self.update())

        # 「扣 60 分钟午休」原来是死字：改午休得去右键「设置」里翻，没人找得到。
        # 这里摆一个明写着的按钮，点它直接进完整设置。
        self._host = parent
        self._btn_more = QPushButton("改下班时间 / 午休 / 休息日…", self)
        self._btn_more.setFont(self._qfont(7))
        self._btn_more.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._place(self._btn_more, 14, 102, 174, 15)
        self._btn_more.clicked.connect(self._goto_settings)

        btn_y = 124
        if self.ask_weather:
            # 同样一块透明按钮盖在自绘方块上。勾上才展开地点输入——
            # 不想要真实天气的人，这一行勾选框都不必碰。
            self._chk_w = QPushButton("", self)
            self._chk_w.setCheckable(True)
            self._chk_w.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._chk_w.setStyleSheet("QPushButton{background:transparent;border:none;}"
                                      "QPushButton:hover{background:rgba(255,255,255,26);}")
            self._place(self._chk_w, 12, 120, 178, 16)
            self._chk_w.toggled.connect(self._on_weather_toggle)

            self._place_edit = QLineEdit(self)
            self._place_edit.setFont(self._qfont(8))
            self._place_edit.setMaxLength(24)
            self._place_edit.setPlaceholderText("比如 杭州")
            self._place_edit.setStyleSheet(
                f"QLineEdit{{background:{pal['panel_shade'][0]};color:{pal['text']};"
                f"border:2px solid {pal['bevel_dark']};padding:2px 4px;}}")
            self._place(self._place_edit, 40, 140, 148, 18)
            self._place_edit.hide()
            btn_y = 178

        self._cancel = QPushButton("取消", self)
        self._cancel.setFont(self._qfont(7))
        self._place(self._cancel, 74, btn_y, 50, 15)
        self._cancel.clicked.connect(self.reject)

        self._ok = QPushButton("确定", self)
        self._ok.setObjectName("primary")
        self._ok.setFont(self._qfont(7, bold=True))
        self._ok.setDefault(True)
        self._place(self._ok, 130, btn_y, 56, 15)
        self._ok.clicked.connect(self._accept)

    def _on_weather_toggle(self, on: bool) -> None:
        self._place_edit.setVisible(bool(on))
        if on:
            self._place_edit.setFocus()
        self.update()

    def weather_choice(self):
        """(要不要真实天气, 地点)。没问过天气的窗返回 (False, "")。"""
        if not self.ask_weather:
            return False, ""
        return bool(self.use_real), self.place

    @property
    def remember(self) -> bool:
        return bool(self._chk.isChecked())

    def _apply_preset(self, t) -> None:
        self._input.set_value(datetime.now().time().replace(second=0, microsecond=0)
                              if t is None else t)

    def _goto_settings(self) -> None:
        host = self._host
        self.reject()
        if host is not None and hasattr(host, "open_settings_dialog"):
            host.open_settings_dialog()

    def _accept(self) -> None:
        self.result_time = self._input.value
        if self.ask_weather:
            self.place = self._place_edit.text().strip()
            # 勾了却没填地点，等于没勾——不拦人，直接当没选
            self.use_real = bool(self._chk_w.isChecked()) and bool(self.place)
        self.accept()

    def render_body(self, p: QPainter, w: int, h: int) -> None:
        pal = self.pal
        S = self.S
        pixel_font.draw_cjk(p, self.u(14), self.u(34) - self.u(12), "今天几点开始上班？",
                            self.u(12), QColor(pal["text"]), self.family)
        hint = sub = ""
        try:
            rule = engine.build_rule(self.cfg)
            off = engine.offwork_at(datetime.now().date(), self._input.value, rule)
            hint = f"下班 {off.strftime('%H:%M')}"
            lunch = int(rule.lunch_minutes)
            sub = f"扣 {lunch} 分钟午休" if lunch else "不扣午休"
        except Exception:
            pass
        if hint:
            pixel_font.draw_cjk(p, self.u(98), self.u(50) - self.u(8), hint, self.u(8),
                                QColor(pal["text_dim"]), self.family)
            pixel_font.draw_cjk(p, self.u(98), self.u(62) - self.u(8), sub,
                                self.u(8), QColor(pal["text_dim"]), self.family)

        # 复选方框（自绘）：勾上之后每天自动登记，不再弹这个窗
        bx, by, bs = self.u(14), self.u(86), self.u(10)
        # 没勾的时候不能是一块纯黑——那看着像色斑，不像能点的格子。
        # 做成"浅底 + 一圈深边"，勾上再整块变绿。
        theme.fill(p, bx, by, bs, bs, QColor("#3a3a3a"))
        theme.fill(p, bx + S, by + S, bs - 2 * S, bs - 2 * S, QColor("#e2e2e2"))
        if self.remember:
            # 整块填草绿再压一道深色勾：只画一个小绿勾的话，1:1 屏幕上看不出来勾没勾
            theme.fill(p, bx + S, by + S, bs - 2 * S, bs - 2 * S, QColor(pal["accent"]))
            ink = QColor("#1b2f10")
            for i in range(3):
                theme.fill(p, bx + (2 + i) * S, by + (5 + i) * S, S, S, ink)
            for i in range(5):
                theme.fill(p, bx + (4 + i) * S, by + (7 - i) * S, S, S, ink)
        pixel_font.draw_cjk(p, self.u(28), self.u(86), self.REMEMBER_TEXT, self.u(8),
                            QColor(pal["text"]), self.family)

        if not self.ask_weather:
            return
        # 真实天气：和上面「记住」同一套方块画法，只是位置下一行
        wx, wy, ws = self.u(14), self.u(124), self.u(10)
        theme.fill(p, wx, wy, ws, ws, QColor("#3a3a3a"))
        theme.fill(p, wx + S, wy + S, ws - 2 * S, ws - 2 * S, QColor("#e2e2e2"))
        if self._chk_w.isChecked():
            theme.fill(p, wx + S, wy + S, ws - 2 * S, ws - 2 * S, QColor(pal["accent"]))
            ink = QColor("#1b2f10")
            for i in range(3):
                theme.fill(p, wx + (2 + i) * S, wy + (5 + i) * S, S, S, ink)
            for i in range(5):
                theme.fill(p, wx + (4 + i) * S, wy + (7 - i) * S, S, S, ink)
        pixel_font.draw_cjk(p, self.u(28), self.u(124), "真实天气", self.u(8),
                            QColor(pal["text"]), self.family)
        if not self._chk_w.isChecked():
            return
        pixel_font.draw_cjk(p, self.u(14), self.u(148), "地点", self.u(8),
                            QColor(pal["text"]), self.family)
        pixel_font.draw_cjk(p, self.u(40), self.u(166),
                            "填到市就行。软件会按你填的地址改变天气。", self.u(7),
                            QColor(pal["text_dim"]), self.family)


class ConfirmDialog(MCDialog):
    W_UNITS = 212
    H_UNITS = 94
    TITLE = "确认操作"
    SHOW_ICON = False

    def __init__(self, parent, cfg, pal, S, dpr, title, message):
        self.message = message
        self._title = title
        super().__init__(parent, cfg, pal, S, dpr)
        b1 = QPushButton("取消", self)
        b1.setFont(self._qfont(7))
        self._place(b1, 90, 66, 52, 15)
        b1.clicked.connect(self.reject)
        b2 = QPushButton("确定", self)
        b2.setObjectName("primary")
        b2.setFont(self._qfont(7, bold=True))
        self._place(b2, 148, 66, 52, 15)
        b2.clicked.connect(self.accept)

    def title_text(self) -> str:
        return self._title

    def render_body(self, p: QPainter, w: int, h: int) -> None:
        pixel_font.draw_cjk(p, 0, self.u(42), self.message, self.u(12),
                            QColor(self.pal["text"]), self.family,
                            align="center", max_w=w)


class AboutDialog(MCDialog):
    """关于：告诉对方自己在用哪一版、跑了多久。

    挂件没有标题栏，发给别人之后对方认不出自己拿的是哪一版，
    所以这一项是给"会传给别人"准备的。检查更新以后也长在这里。
    """

    W_UNITS = 216
    H_UNITS = 146
    TITLE = "关于"

    def __init__(self, parent, cfg, pal, S, dpr, cumulative, known=None):
        self.cumulative = int(cumulative)
        self._copied = False
        self._status = ""
        self._remote_url = ""
        self._checker = None
        self._cn = ("", "")
        # 后台查到的更新信息：{version, url, cn_url, cn_pwd, asset, size}
        info = dict(known) if isinstance(known, dict) else (
            {"version": known[0], "url": known[1]} if known else {})
        self._info = info
        self._remote_url = str(info.get("url") or "")
        self._asset = str(info.get("asset") or "")
        self._size = int(info.get("size") or 0)
        self._v_remote = str(info.get("version") or "")
        self._fetcher = None
        self._mode = "idle"              # idle / downloading / saved / failed
        self._hint = ""
        self._folder = ""
        self._pct = -1
        super().__init__(parent, cfg, pal, S, dpr)
        if info:
            from .update import short_label

            self._status = f"有新版本 {short_label(self._v_remote)}"

        b_copy = QPushButton("复制版本号", self)
        b_copy.setFont(self._qfont(7))
        self._place(b_copy, 12, 124, 62, 15)
        b_copy.clicked.connect(self._copy)

        self._b_check = QPushButton(
            "下载更新" if self._asset else ("去下载" if self._info else "检查更新"), self)
        self._b_check.setFont(self._qfont(7))
        self._place(self._b_check, 78, 124, 62, 15)
        self._b_check.clicked.connect(self._on_check_clicked)

        b = QPushButton("关闭", self)
        b.setFont(self._qfont(7))
        b.setDefault(True)
        self._place(b, 144, 124, 58, 15)
        b.clicked.connect(self.accept)

    # ------------------------------------------------------------------ 检查更新
    def _on_check_clicked(self) -> None:
        if self._mode == "downloading":
            self._fetcher and self._fetcher.cancel()
            return
        if self._mode == "saved":
            self._open_folder()
            return
        if self._mode == "idle" and self._asset:
            self._start_download()
            return
        if self._remote_url:
            QDesktopServices.openUrl(QUrl(self._remote_url))
            return
        from .update import UpdateChecker

        self._status = "检查中…"
        self._b_check.setEnabled(False)
        self.update()
        self._checker = UpdateChecker(self)
        self._checker.found.connect(self._on_found)
        self._checker.uptodate.connect(self._on_uptodate)
        self._checker.failed.connect(self._on_failed)
        self._checker.start()

    # ------------------------------------------------------------------ 一键下载
    def _start_download(self) -> None:
        """把新 exe 下到旧 exe 旁边，不碰任何数据文件。

        不做自我替换：本程序正开着，Windows 不允许删/覆盖它自己。所以退一步——
        文件放到位，用户关掉它、双击新的，两步。
        """
        from .update import UpdateFetcher

        self._mode = "downloading"
        self._pct = -1
        self._hint = ""
        self._status = "下载中…"
        self._b_check.setText("取消")
        self.update()

        f = UpdateFetcher(self, self._asset, self._size, self._v_remote)
        f.progress.connect(self._on_progress)
        f.done.connect(self._on_download_done)
        f.failed.connect(self._on_download_failed)
        self._fetcher = f
        f.start()

    def _on_progress(self, got: int, total: int) -> None:
        # 百分比变了才重绘：下载进度一来就是几百次，每次重画整窗不划算
        pct = int(got * 100 / total) if total > 0 else -1
        if pct == self._pct:
            return
        self._pct = pct
        mb = got / (1024 * 1024)
        self._status = f"下载中 {pct}%（{mb:.1f} MB）" if pct >= 0 else f"下载中 {mb:.1f} MB"
        self.update()

    def _on_download_done(self, path: str) -> None:
        import os

        self._fetcher = None
        self._mode = "saved"
        self._folder = os.path.dirname(path)
        self._status = f"已下好 {os.path.basename(path)}"
        self._hint = "关掉我，双击新的那个；设置和台账都还在"
        self._b_check.setText("打开文件夹")
        self._b_check.setEnabled(True)
        self.update()

    def _on_download_failed(self, why: str) -> None:
        self._fetcher = None
        self._mode = "failed"
        self._status = why
        self._hint = "也可以点右边，去网页手动下"
        self._b_check.setText("去下载")
        self._b_check.setEnabled(True)
        self.update()

    def _open_folder(self) -> None:
        if self._folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._folder))

    def closeEvent(self, event):  # noqa: N802
        # 下载中关窗 = 放弃：取消会顺手把半截文件删掉，不留个坏 exe 在文件夹里
        if self._mode == "downloading" and self._fetcher is not None:
            self._fetcher.cancel()
        super().closeEvent(event)

    def reject(self) -> None:
        if self._mode == "downloading" and self._fetcher is not None:
            self._fetcher.cancel()
        super().reject()

    def _on_found(self, version: str, url: str, cn_url: str = "", cn_pwd: str = "") -> None:
        # 默认走 GitHub（正式、无密码）；蓝奏云留在连不上时兜底
        from .update import short_label

        self._status = f"有新版本 {short_label(version)}"
        self._remote_url = url
        self._cn = (cn_url, cn_pwd)
        self._v_remote = version
        self._asset = getattr(self._checker, "asset_url", "") or ""
        self._size = int(getattr(self._checker, "asset_size", 0) or 0)
        self._mode = "idle"
        self._b_check.setText("下载更新" if self._asset else "去下载")
        self._b_check.setEnabled(True)
        self.update()

    def _on_uptodate(self, version: str) -> None:
        self._status = f"已是最新 v{version}"
        self._b_check.setEnabled(True)
        self.update()

    def _on_failed(self) -> None:
        # 连不上多半是 GitHub 在国内被墙。程序下不了，就交给浏览器 + 蓝奏云：
        # 蓝奏云国内秒开，但要输提取码，所以提取码直接写在状态里。
        from .update import FALLBACK_CN_PWD, FALLBACK_CN_URL

        cn_url, cn_pwd = getattr(self, "_cn", ("", ""))
        self._remote_url = cn_url or FALLBACK_CN_URL
        pwd = cn_pwd or FALLBACK_CN_PWD
        self._status = f"连不上，蓝奏云下载（密码 {pwd}）"
        self._b_check.setText("去蓝奏云")
        self._b_check.setEnabled(True)
        self.update()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(f"MC 工时牌 {__version_label__}（{__version__}）")
        self._copied = True
        self.update()

    def render_body(self, p: QPainter, w: int, h: int) -> None:
        pal = self.pal
        family = self.family

        pixel_font.draw_cjk(p, 0, self.u(30), "MC 工时牌", self.u(13),
                            QColor(pal["text"]), family, bold=True,
                            align="center", max_w=w)
        # 版本号给足字号：这一行就是"我在用哪一版"的答案
        # 像素字体里小写 v 会渲染成倒三角，这里用大写
        pixel_font.draw_cjk(p, 0, self.u(50), __version_label__.upper(), self.u(11),
                            QColor(pal["accent"]), family, bold=True,
                            align="center", max_w=w)

        # 只有源码版才有这一行：正式版用户不需要知道自己是"exe 版"，
        # 那是打包方式，不是他该关心的事。
        if not getattr(sys, "frozen", False):
            pixel_font.draw_cjk(p, 0, self.u(70), "开发预览版", self.u(7),
                                QColor(pal["text_dim"]), family, align="center", max_w=w)

        hh, mm = divmod(self.cumulative, 60)
        total = f"累计加班 {hh} 小时 {mm} 分" if hh else f"累计加班 {mm} 分钟"
        pixel_font.draw_cjk(p, 0, self.u(84), total, self.u(8),
                            QColor(pal["text"]), family, align="center", max_w=w)

        if self._hint:
            # 下载相关的说明占掉"陪你数完今天"那一行：两行字刚好说清"下一步做什么"
            pixel_font.draw_cjk(p, 0, self.u(98), self._hint, self.u(7),
                                QColor(pal["text_dim"]), family, align="center", max_w=w)
        else:
            tip = "已复制到剪贴板" if self._copied else "陪你数完今天，就下班。"
            pixel_font.draw_cjk(p, 0, self.u(98), tip, self.u(7),
                                QColor(pal["accent"] if self._copied else pal["text_dim"]),
                                family, align="center", max_w=w)

        if self._status:
            hit = self._status.startswith(("有新版本", "已下好"))
            pixel_font.draw_cjk(p, 0, self.u(110), self._status, self.u(7),
                                QColor(pal["accent"] if hit else pal["text_dim"]),
                                family, align="center", max_w=w)


class StatsDialog(MCDialog):
    W_UNITS = 208
    H_UNITS = 124
    TITLE = "累计加班"

    def __init__(self, parent, cfg, pal, S, dpr, cumulative, store, today_ot):
        self.cumulative = cumulative
        self.store = store
        self.today_ot = today_ot
        super().__init__(parent, cfg, pal, S, dpr)
        b_clear = QPushButton("清空累计", self)
        b_clear.setFont(self._qfont(7))
        self._place(b_clear, 14, 102, 62, 15)
        b_clear.clicked.connect(self._clear)
        b = QPushButton("关闭", self)
        b.setFont(self._qfont(7))
        self._place(b, 136, 102, 58, 15)
        b.clicked.connect(self.accept)

    def _clear(self) -> None:
        if confirm(self, self.cfg, self.pal, self.S, self._dpr, "清空累计加班",
                   "确定清空全部累计加班记录？"):
            self.store.reset_cumulative()
            self.cumulative = 0
            self.today_ot = 0
            self.update()

    def render_body(self, p: QPainter, w: int, h: int) -> None:
        pal = self.pal
        S = self.S
        family = self.family
        pixel_font.draw_cjk(p, self.u(14), self.u(28), "累计加班总时长",
                            self.u(8), QColor(pal["text_dim"]), family)

        k = max(2, S * 2)
        h_, m_ = divmod(int(self.cumulative), 60)
        items = []
        if h_:
            items += [("b", f"{h_:02d}", k), ("g", self.u(5)), ("c", "小时", self.u(12)),
                      ("g", self.u(4))]
        items += [("b", f"{m_:02d}", k), ("g", self.u(5)), ("c", "分钟", self.u(12))]
        pixel_font.draw_items(p, self.u(self.W_UNITS // 2), self.u(56), items,
                              QColor(pal["accent"]), family)

        # 分隔线
        theme.fill(p, self.u(14), self.u(64), w - self.u(28), S,
                   QColor(pal["bevel_dark"]))

        days = int(self.store.data.get("days_counted", 0))
        best = int(self.store.data.get("max_single_day", 0))
        rows = [
            ("累计记录", f"{days} 天"),
            ("单日最高", engine.humanize(best)),
            ("今日加班", engine.humanize(self.today_ot)),
        ]
        y = 72
        right = self.u(self.W_UNITS - 14)
        for label, value in rows:
            pixel_font.draw_cjk(p, self.u(14), self.u(y), label, self.u(8),
                                QColor(pal["text_dim"]), family)
            pixel_font.draw_cjk(p, 0, self.u(y), value, self.u(8),
                                QColor(pal["text"]), family,
                                align="right", max_w=right)
            y += 10


class DayDialog(MCDialog):
    """今日结算：只讲工作本身，不写花草。

    顶上那行是「累计」——用「一共干了多少天、多少小时」代替「连续准点几天」：
    弹性制没有标准上班时刻，说准点没意义；累计是真实发生过的，谁也赖不掉。
    累计工时按「标准在岗时长 × 登记天数 + 累计加班」推算，因为不加班的日子
    根本不落 ledger，没法逐日累加。这是估算，但方向永远单调向上。

    底下三件才是「记事」：我常几点到、今天怎么样、今天想说什么。
    高度按内容算，没有内容就不留空行。
    """

    W_UNITS = 208
    TITLE = "今日结算"

    def __init__(self, parent, cfg, pal, S, dpr, store, rule, now, live_ot):
        self.store = store
        self.rule = rule
        self.now = now
        self.live_ot = max(0, int(live_ot))
        self._st = self._stat()
        self._rows_cache = self._rows()
        self._verdict = self._make_verdict()
        self._note = self.store.note(self.now.date())
        self.H_UNITS = (82 + 12 * len(self._rows_cache)
                        + (14 if self._verdict else 0)
                        + (12 if self._note else 0) + 28)
        super().__init__(parent, cfg, pal, S, dpr)
        b = QPushButton("关闭", self)
        b.setFont(self._qfont(7))
        self._place(b, 74, self.H_UNITS - 24, 60, 15)
        b.clicked.connect(self.accept)

    # ------------------------------------------------------------------
    def _stat(self) -> dict:
        today = self.now.date()
        start = self.store.work_start(today)
        st = {"start": start, "off": None, "effective": 0, "diff": None}
        if start is None:
            return st
        off = engine.offwork_at(today, start, self.rule)
        st["off"] = off
        seated = max(0, int((self.now - datetime.combine(today, start)).total_seconds() // 60))
        lunch = int(self.rule.lunch_overlap_minutes(start, self.now.time()))
        st["effective"] = max(0, seated - lunch)
        # 只有过了下班点，和昨天比才公平：否则拿半天比人家一整天，永远显示负数
        yday = self.store.day_minutes(today - timedelta(days=1), self.rule)
        if yday is not None and self.now >= off:
            st["diff"] = st["effective"] - yday
        return st

    def _rows(self) -> list[tuple[str, str]]:
        """今天的三四行就够了。数据不全的不出现，不留 0 和 —。

        不列「本周累计」：一周面板里有合计，这里再写一遍只是把面板塞满。
        不列「对比昨天」：短评已经说了"比昨天早走/晚走"，同一件事说两遍。
        """
        st = self._st
        start = st["start"]
        if start is None:
            return [("到岗", "还没登记")]
        off = st["off"]
        rows = [
            ("在岗时段", f"{start.strftime('%H:%M')} → {off.strftime('%H:%M')}"),
            ("有效工时", engine.humanize(st["effective"])),
        ]
        if self.live_ot:
            rows.append(("今日加班", engine.humanize(self.live_ot)))
        typical = self.store.typical_start(self.now.date())
        if typical is not None:
            rows.append(("常在", f"{typical.strftime('%H:%M')} 前后到岗"))
        return rows

    def _make_verdict(self) -> str:
        """一句实话。上班中间不评价——那时候说什么都像催促。"""
        st = self._st
        if st["start"] is None:
            return ""
        if self.now < st["off"]:
            return ""
        if self.live_ot >= 60:
            return "今天多干了不少，早点睡"
        if self.live_ot > 0:
            return "加了会儿，不算多"
        diff = st["diff"]
        if diff is not None and diff <= -30:
            return "比昨天早走，挺好"
        if diff is not None and diff >= 30:
            return "比昨天晚走，明天早点"
        return "今天没吃亏"

    def render_body(self, p: QPainter, w: int, h: int) -> None:
        pal = self.pal
        S = self.S
        family = self.family

        days = self.store.worked_days()
        total = self.store.worked_minutes(self.rule, self.live_ot)
        th, tm = divmod(int(total), 60)

        pixel_font.draw_cjk(p, self.u(14), self.u(28), "累计", self.u(8),
                            QColor(pal["text_dim"]), family)

        k = max(2, S * 2)
        pixel_font.draw_items(p, self.u(self.W_UNITS // 2), self.u(54),
                              [("b", f"{days}", k), ("g", self.u(5)),
                               ("c", "天", self.u(12))],
                              QColor(pal["accent"]), family)
        pixel_font.draw_cjk(p, self.u(14), self.u(60),
                            f"共 {th} 小时 {tm} 分", self.u(8),
                            QColor(pal["text"]), family, align="center",
                            max_w=w - self.u(28))

        theme.fill(p, self.u(14), self.u(72), w - self.u(28), S, QColor(pal["bevel_dark"]))

        right = self.u(self.W_UNITS - 14)
        y = 82
        for label, value in self._rows_cache:
            pixel_font.draw_cjk(p, self.u(14), self.u(y), label, self.u(8),
                                QColor(pal["text_dim"]), family)
            pixel_font.draw_cjk(p, 0, self.u(y), value, self.u(8),
                                QColor(pal["text"]), family,
                                align="right", max_w=right)
            y += 12

        y = 82 + 12 * len(self._rows_cache)
        if self._verdict:
            theme.fill(p, self.u(14), self.u(y), w - self.u(28), S,
                       QColor(pal["bevel_dark"]))
            pixel_font.draw_cjk(p, self.u(14), self.u(y + 6), self._verdict, self.u(8),
                                QColor(pal["accent"]), family)
            y += 14
        if self._note:
            text = self._note if len(self._note) <= 22 else self._note[:21] + "…"
            pixel_font.draw_cjk(p, self.u(14), self.u(y + 3), f"吐槽：{text}", self.u(7),
                                QColor(pal["text_dim"]), family, max_w=w - self.u(28))


class WeekDialog(MCDialog):
    """一周：七天各一根柱子，柱高就是当天的有效工时。

    比七行数字好读——哪几天长、哪几天短，一眼分得出来。
    超出标准工时的天用亮色，不加文字标注：这个尺度下字最容易读错。
    """

    W_UNITS = 208
    H_UNITS = 172
    TITLE = "一周"

    def __init__(self, parent, cfg, pal, S, dpr, store, rule, now, live_ot):
        self.store = store
        self.rule = rule
        self.now = now
        self.live_ot = max(0, int(live_ot))
        super().__init__(parent, cfg, pal, S, dpr)
        b = QPushButton("关闭", self)
        b.setFont(self._qfont(7))
        self._place(b, 74, 150, 60, 15)
        b.clicked.connect(self.accept)

    def render_body(self, p: QPainter, w: int, h: int) -> None:
        pal = self.pal
        S = self.S
        family = self.family
        today = self.now.date()
        week = self.store.week_minutes(today, self.rule, self.live_ot)
        base = max(1, int(round(self.rule.onsite_hours * 60)))
        total = sum(v for _, v in week if v)
        th, tm = divmod(int(total), 60)

        pixel_font.draw_cjk(p, self.u(14), self.u(28), "本周", self.u(8),
                            QColor(pal["text_dim"]), family)
        pixel_font.draw_cjk(p, self.u(14), self.u(38), f"共 {th} 小时 {tm} 分",
                            self.u(9), QColor(pal["text"]), family)

        # 和上周比：让人看见趋势，而不只是本周的形状
        last = self.store.week_total(today - timedelta(days=today.weekday() + 7),
                                     self.rule, today, self.live_ot)
        if last:
            diff = total - last
            if abs(diff) < 5:
                trend = "和上周差不多"
            else:
                trend = f"比上周{'多' if diff > 0 else '少'} {engine.humanize(abs(diff))}"
            pixel_font.draw_cjk(p, self.u(14), self.u(52), trend, self.u(8),
                                QColor(pal["text_dim"]), family)

        bottom = self.u(124)
        top = self.u(78)
        max_h = bottom - top
        bw = self.u(20)
        gap = self.u(5)
        x0 = self.u(16)
        for i, (d, mins) in enumerate(week):
            x = x0 + i * (bw + gap)
            if mins is None:
                theme.fill(p, x, bottom - S, bw, S, QColor(pal["track"][1]))
            else:
                bar = max(S, int(max_h * min(1.0, mins / base * 0.9)))
                color = pal["fill_light"] if mins > base else pal["fill"][1]
                theme.fill(p, x, bottom - bar, bw, bar, QColor(color))
                if d == today:
                    theme.fill(p, x, bottom - bar, bw, max(2, S), QColor(pal["bevel_light"]))
            pixel_font.draw_cjk(p, x, self.u(128), _DAY_CH[i], self.u(8),
                                QColor(pal["accent"] if d == today else pal["text_dim"]),
                                family, align="center", max_w=bw)

        pixel_font.draw_cjk(p, self.u(14), self.u(140), "亮色 = 超出标准工时",
                            self.u(7), QColor(pal["text_dim"]), family)


# 输入框里的那行提示：一天换一句，不重复。都是让人敢写的话——
# 写下来这一步本身有门槛，提示语太正式，就更不想写了。
NOTE_HINTS = (
    "烦心事都写在这里，本宝宝帮你记住！",
    "今天谁惹你了？写两句，别憋着。",
    "骂吧，写完就放下。",
    "不写名字也行，反正它不会告状。",
    "今天有什么想吐槽的？",
    "写下来就存住了，明天再看也不迟。",
)


class NoteDialog(MCDialog):
    """吐槽两句：今天想说的，不必是工作。

    存进 data.json 的 notes，按天一条，跟着 schedule 一起被修剪。
    「今日结算」底部会显示今天那句——它和工作数据不是一类东西，所以另起一行。

    按钮用「取消 / 确定」而不是「清空 / 记住」：清空看着像"要把我写的删掉"，
    实际上它以前是"清空并保存"，取消才是人真正想表达的那个意思。
    真想删掉这句，把内容删干净再按确定就行。
    """

    W_UNITS = 208
    H_UNITS = 104
    TITLE = "吐槽两句"
    SHOW_ICON = False

    def __init__(self, parent, cfg, pal, S, dpr, text: str = "", day=None):
        super().__init__(parent, cfg, pal, S, dpr)
        self.edit = QLineEdit(self)
        self.edit.setFont(self._qfont(8))
        self.edit.setMaxLength(60)
        seed = (day or getattr(parent, "_day", None))
        hint = NOTE_HINTS[(seed.toordinal() if seed else 0) % len(NOTE_HINTS)]
        self.edit.setPlaceholderText(hint)
        self.edit.setText(text or "")
        self.edit.setStyleSheet(
            f"QLineEdit{{background:{pal['panel_shade'][0]};color:{pal['text']};"
            f"border:2px solid {pal['bevel_dark']};padding:2px 4px;}}"
        )
        self._place(self.edit, 14, 30, self.W_UNITS - 28, 18)

        b_cancel = QPushButton("取消", self)
        b_cancel.setFont(self._qfont(7))
        self._place(b_cancel, 14, 76, 60, 15)
        b_cancel.clicked.connect(self.reject)
        b_ok = QPushButton("确定", self)
        b_ok.setFont(self._qfont(7))
        self._place(b_ok, 134, 76, 60, 15)
        b_ok.clicked.connect(self.accept)
        self.edit.setFocus()

    def text(self) -> str:
        return self.edit.text().strip()


def confirm(parent, cfg, pal, S, dpr, title, message) -> bool:
    dlg = ConfirmDialog(parent, cfg, pal, S, dpr, title, message)
    return bool(dlg.exec())


class SettingsDialog(MCDialog):
    """设置：上班时间 / 下班时间 / 午休开始 / 午休时长 / 哪几天上班。

    下班时间是直接选的，不是"上班加八小时"算出来的——公司几点下班是定死的。
    只有第一次打开（还没选过）时，才按 9 小时在岗、扣掉午休推一个默认值垫在框里，
    用户改一次，以后就一直用他选的那个。

    休息日给了七个可点的小格，因为它真的不是"双休/单休"两档：有人单休，
    有人周六休但周日上班。点亮 = 那天上班，灰 = 那天休息。
    """

    W_UNITS = 212
    H_UNITS = 236
    TITLE = "设置"

    # 七个格子在这一行里的位置（布局单位）：点亮=上班，灰=休息
    CELL_X = 52
    CELL_Y = 116
    CELL_W = 19
    CELL_H = 13
    CELL_GAP = 2

    def __init__(self, parent, cfg, pal, S, dpr, current):
        self._start = current or engine.parse_hhmm(
            cfg.get("schedule.default_work_start", "09:00"), dt_time(9, 0))
        self._lunch_start = engine.parse_hhmm(cfg.get("schedule.lunch_start", "12:00"),
                                              dt_time(12, 0))
        self._lunch_min = int(cfg.get("schedule.lunch_minutes", 60) or 0)
        self._days = {int(x) for x in (cfg.get("schedule.workdays") or [1, 2, 3, 4, 5])}
        text = str(cfg.get("schedule.offwork_time") or "").strip()
        if ":" in text:
            self._offwork = engine.parse_hhmm(text, dt_time(18, 0))
        else:
            # 还没选过：按 9 小时在岗（扣午休）算一个，垫在输入框里等下改
            self._offwork = engine.suggested_offwork(self._start,
                                                     engine.build_rule(cfg))
        super().__init__(parent, cfg, pal, S, dpr)

        self._t_start = TimeInput(self, pal, self.S, self._dpr, self.family, self._start)
        self._place(self._t_start, 96, 24, TimeInput.W_UNITS, TimeInput.H_UNITS)

        self._t_off = TimeInput(self, pal, self.S, self._dpr, self.family,
                                self._offwork)
        self._place(self._t_off, 96, 48, TimeInput.W_UNITS, TimeInput.H_UNITS)

        self._t_lunch = TimeInput(self, pal, self.S, self._dpr, self.family,
                                  self._lunch_start)
        self._place(self._t_lunch, 96, 72, TimeInput.W_UNITS, TimeInput.H_UNITS)

        # 午休时长：两边各一个 15 分钟的加减键
        self._mk_step(96, 98, "-", lambda: self._bump("lunch", -15))
        self._mk_step(168, 98, "+", lambda: self._bump("lunch", 15))

        # 真实天气：勾上才展开地点。并进这里之后，设过也能随时改，
        # 不像原来只有首次那个窗能设。
        self.use_real = str(cfg.get("weather.mode", "random")) == "real"
        self.place = str(cfg.get("weather.place", "") or "")
        self._chk_w = QPushButton("", self)
        self._chk_w.setCheckable(True)
        self._chk_w.setChecked(self.use_real)
        self._chk_w.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._chk_w.setStyleSheet("QPushButton{background:transparent;border:none;}"
                                  "QPushButton:hover{background:rgba(255,255,255,26);}")
        self._place(self._chk_w, 12, 166, 188, 16)
        self._chk_w.toggled.connect(self._on_weather_toggle)

        self._place_edit = QLineEdit(self)
        self._place_edit.setFont(self._qfont(8))
        self._place_edit.setMaxLength(24)
        self._place_edit.setPlaceholderText("比如 杭州")
        self._place_edit.setText(self.place)
        self._place_edit.setStyleSheet(
            f"QLineEdit{{background:{pal['panel_shade'][0]};color:{pal['text']};"
            f"border:2px solid {pal['bevel_dark']};padding:2px 4px;}}")
        self._place(self._place_edit, 40, 184, 156, 18)
        self._place_edit.setVisible(self.use_real)

        b_cancel = QPushButton("取消", self)
        b_cancel.setFont(self._qfont(7))
        self._place(b_cancel, 76, 214, 54, 15)
        b_cancel.clicked.connect(self.reject)

        b_ok = QPushButton("保存", self)
        b_ok.setObjectName("primary")
        b_ok.setFont(self._qfont(7, bold=True))
        b_ok.setDefault(True)
        self._place(b_ok, 134, 214, 58, 15)
        b_ok.clicked.connect(self.accept)

    def _on_weather_toggle(self, on: bool) -> None:
        self._place_edit.setVisible(bool(on))
        if on:
            self._place_edit.setFocus()
        self.update()

    def weather_choice(self):
        """(要不要真实天气, 地点)。以控件当前状态为准，不看 __init__ 时的快照。"""
        return (bool(self._chk_w.isChecked()),
                self._place_edit.text().strip())

    # ------------------------------------------------------------------
    def _mk_step(self, x: float, y: float, text: str, cb) -> None:
        b = QPushButton(text, self)
        b.setFont(self._qfont(9, bold=True))
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # 对话框 qss 给按钮留了 10px 横向内边距，14 单位宽的按钮会被挤没，这里单独清掉
        b.setStyleSheet("padding: 0px;")
        # 午休两小时要按 4 次 +，太琐碎：按住不放连续加
        b.setAutoRepeat(True)
        b.setAutoRepeatDelay(400)
        b.setAutoRepeatInterval(90)
        self._place(b, x, y, 14, 14)
        b.clicked.connect(lambda _=False: cb())

    def _bump(self, _kind: str, delta) -> None:
        self._lunch_min = max(0, min(240, self._lunch_min + int(delta)))
        self.update()

    # ------------------------------------------------------------------ 休息日
    def _day_at(self, pos) -> int:
        """点在哪个格子上？返回 1~7，点空返回 0。"""
        dpr = self._dpr or 1.0
        ux = pos.x() * dpr / max(1, self.S)
        uy = pos.y() * dpr / max(1, self.S)
        if not (self.CELL_Y - 1 <= uy <= self.CELL_Y + self.CELL_H + 1):
            return 0
        for i in range(7):
            x0 = self.CELL_X + i * (self.CELL_W + self.CELL_GAP)
            if x0 <= ux <= x0 + self.CELL_W:
                return i + 1
        return 0

    def _toggle_day(self, day: int) -> None:
        if day in self._days:
            if len(self._days) <= 1:       # 一个星期一天班都不上，不成立
                return
            self._days.discard(day)
        else:
            self._days.add(day)
        self.update()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            day = self._day_at(event.position().toPoint())
            if day:
                self._toggle_day(day)
                return
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    def result(self):
        """(上班时间, 下班时间, 午休开始, 午休分钟, 上班日列表)"""
        return (self._t_start.value, self._t_off.value,
                self._t_lunch.value, int(self._lunch_min), sorted(self._days))

    def _preview_span(self) -> str:
        """按当前四项算出来的有效工时（扣掉午休），填错时给个提醒。"""
        try:
            rule = engine.Rule(offwork=self._t_off.value,
                               lunch_start=self._t_lunch.value,
                               lunch_end=engine.shift_time(self._t_lunch.value,
                                                           self._lunch_min))
            if self._t_off.value <= self._t_start.value:
                return "下班时间早于上班时间，请检查"
            total = int(rule.target_minutes(self._t_start.value))
            return f"有效工时 {engine.humanize(total)}"
        except Exception:
            return ""

    def _draw_day_cell(self, p: QPainter, i: int, on: bool) -> None:
        """一格：点亮=上班（草绿底），灰=休息（凹陷暗底）。"""
        pal = self.pal
        S = self.S
        x = self.u(self.CELL_X + i * (self.CELL_W + self.CELL_GAP))
        y = self.u(self.CELL_Y)
        w = self.u(self.CELL_W)
        h = self.u(self.CELL_H)
        if on:
            theme.fill(p, x, y, w, h, QColor(pal["grass"][1]))
            theme.fill(p, x, y, w, S, QColor(pal["bevel_light"]))
            theme.fill(p, x, y, S, h, QColor(pal["bevel_light"]))
            theme.fill(p, x, y + h - S, w, S, QColor(pal["grass"][4]))
            theme.fill(p, x + w - S, y, S, h, QColor(pal["grass"][4]))
            ink = QColor(pal["text_on_grass"])
        else:
            theme.fill(p, x, y, w, h, QColor(pal["panel_shade"][0]).darker(112))
            theme.fill(p, x, y, w, S, QColor(pal["bevel_dark"]))
            theme.fill(p, x, y, S, h, QColor(pal["bevel_dark"]))
            ink = QColor(pal["text_dim"]).darker(118)
        theme.fill(p, x, y, w, S, QColor(pal["outline"]))
        theme.fill(p, x, y + h - S, w, S, QColor(pal["outline"]))
        theme.fill(p, x, y, S, h, QColor(pal["outline"]))
        theme.fill(p, x + w - S, y, S, h, QColor(pal["outline"]))
        pixel_font.draw_cjk_vcenter(p, x, y, h, _DAY_CH[i], self.u(8), ink,
                                    self.family, bold=True, align="center", max_w=w)

    def render_body(self, p: QPainter, w: int, h: int) -> None:
        pal = self.pal
        fam = self.family
        dim = QColor(pal["text_dim"])
        ink = QColor(pal["text"])

        rows = ((26, "上班时间"), (50, "下班时间"), (74, "午休开始"), (98, "午休多长"))
        for y, text in rows:
            pixel_font.draw_cjk(p, self.u(14), self.u(y + 4), text, self.u(9), ink, fam)

        label = f"{self._lunch_min} 分钟"
        tw, _th = pixel_font.measure_cjk(label, self.u(9), fam, bold=True)
        pixel_font.draw_cjk(p, self.u(139) - tw // 2, self.u(96), label, self.u(9),
                            QColor(pal["accent"]), fam, bold=True)

        # 休息日：一共七天，点亮的那几天算上班
        pixel_font.draw_cjk(p, self.u(14), self.u(120), "上班日", self.u(9), ink, fam)
        for i in range(7):
            self._draw_day_cell(p, i, (i + 1) in self._days)

        theme.fill(p, self.u(14), self.u(136), w - self.u(28), self.S,
                   QColor(pal["bevel_dark"]))
        hint = self._preview_span()
        if hint:
            pixel_font.draw_cjk(p, 0, self.u(142), hint, self.u(8), dim, fam,
                                align="center", max_w=w)
        # 点了最后一格会点不动，这里说明一句，免得以为坏了
        if len(self._days) <= 1:
            pixel_font.draw_cjk(p, 0, self.u(153), "至少留一天上班", self.u(7),
                                QColor(pal["warn"]), fam, align="center", max_w=w)
        else:
            pixel_font.draw_cjk(p, 0, self.u(153), "点亮=上班，灰=休息（点一下切换）",
                                self.u(7), dim, fam, align="center", max_w=w)

        # 真实天气：同一套方块勾选，勾上才展开地点
        wx, wy, ws = self.u(14), self.u(166), self.u(10)
        theme.fill(p, wx, wy, ws, ws, QColor("#3a3a3a"))
        theme.fill(p, wx + self.S, wy + self.S, ws - 2 * self.S, ws - 2 * self.S,
                   QColor("#e2e2e2"))
        if self._chk_w.isChecked():
            theme.fill(p, wx + self.S, wy + self.S, ws - 2 * self.S, ws - 2 * self.S,
                       QColor(pal["accent"]))
            tick = QColor("#1b2f10")
            for i in range(3):
                theme.fill(p, wx + (2 + i) * self.S, wy + (5 + i) * self.S,
                           self.S, self.S, tick)
            for i in range(5):
                theme.fill(p, wx + (4 + i) * self.S, wy + (7 - i) * self.S,
                           self.S, self.S, tick)
        pixel_font.draw_cjk(p, self.u(28), self.u(166), "真实天气", self.u(9), ink, fam)
        if not self._chk_w.isChecked():
            return
        pixel_font.draw_cjk(p, self.u(14), self.u(190), "地点", self.u(9), ink, fam)
        pixel_font.draw_cjk(p, self.u(40), self.u(204),
                            "填到市就行。软件会按你填的地址改变天气。", self.u(7),
                            dim, fam)
