"""主悬浮窗：MC 像素风格工时牌。

窗口本体只负责：构造、尺寸档、位置记忆、显示与隐藏。
其余职责按类型拆在 app/ui/ 下：
    clock     计时与状态推进
    content   文字内容
    paint     画面绘制
    interact  鼠标与菜单
"""
from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget
from . import engine, pixel_font, theme, win32
from .base_window import DragMixin, PixelCanvas

from . import __version_label__
from .ui.clock import ClockMixin
from .ui.consts import TIER_ORDER, TIERS, WEEK_CN  # noqa: F401
from .ui.content import ContentMixin
from .ui.interact import InteractMixin
from .ui.paint import PaintMixin


class TimerWidget(ClockMixin, ContentMixin, PaintMixin, InteractMixin,
                  PixelCanvas, DragMixin, QWidget):

    request_quit = Signal()

    W_UNITS = TIERS["standard"]["w"]
    H_UNITS = TIERS["standard"]["h"]

    # 完整布局：进度条 22→28 单位（天空与草地各高一大截，花才画得开）：
    # 上面从"两排小字"里挤，下面把窗口加高 6 单位——条子占比变大，字也没被压。
    FULL_LAYOUT = {
        "header": 20, "label_bottom": 37, "label_size": 11,
        "value_bottom": 58, "bar_y": 60, "bar_h": 28,
        "quote_bottom": 106, "quote_size": 10,
        "foot_bottom": 123, "foot_size": 9, "pad": 12, "bar_pad": 8,
        "icon": 16, "title": 12, "title_x": 28,
    }
    # 紧凑布局（小档）：只留大数字 + 草地条；标题 11→9，顶部那条草皮才不挤。
    COMPACT_LAYOUT = {
        "header": 15, "label_bottom": 0, "label_size": 0,
        "value_bottom": 34, "bar_y": 37, "bar_h": 16,
        "quote_bottom": 0, "quote_size": 0,
        "foot_bottom": 0, "foot_size": 0, "pad": 8, "bar_pad": 6,
        "icon": 10, "title": 8, "title_x": 19,
    }



    def __init__(self, cfg, store, rule: engine.Rule, tray=None):
        flags = (Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool)
        super().__init__(None, flags)
        self.cfg = cfg
        self.store = store
        self.rule = rule
        self.tray = tray

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setWindowTitle(f"MC 工时牌 {__version_label__}")

        self._compact = False
        self._tier = "standard"
        self.init_canvas(cfg)

        self._pal_base = theme.resolve_palette(cfg)
        self._pal_hour: int | None = None
        self.pal = self._pal_base

        self._apply_tier(str(cfg.get("ui.size_tier", "standard") or "standard"))
        self._refresh_palette(datetime.now(), force=True)
        self.family = pixel_font.pixel_family()

        self._pt_active = False
        self._pt_remaining = 0
        self._pt_timer = QTimer(self)
        self._pt_timer.setSingleShot(True)
        self._pt_timer.timeout.connect(self.exit_passthrough)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.store.save)

        self._hover_btn = False
        self._last_persist: datetime | None = None
        self._day = datetime.now().date()

        # 每日一句：按日期取，同一天恒定，跨天自动换
        self._quote_day = None
        self._quote = ""

        # 草皮卷：进度前进时用一小段动画把它"滚"过去，而不是跳一格
        self._roll_phase = 0.0
        self._roll_phase0 = 0.0
        self._roll_lift = 0
        self._anim_ratio = 0.0
        self._anim_from = 0.0
        self._anim_target = 0.0
        self._anim_t0 = 0.0
        self._animating = False
        self._last_progress = 0.0
        # 动效统一 60fps（可配）：草皮卷推进、里程碑、收工庆祝都用这条线
        fps = int(self.cfg.get("ui.fx.fps", 60) or 60)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(max(8, int(1000 / max(15, fps))))
        self._anim_timer.timeout.connect(self._anim_step)

        # ---- 情绪化动效（F1/F2/F3）的运行时状态
        self._fx_kind = ""              # "" / "ms"（里程碑）/ "home"（回家庆祝）
        self._fx_t0 = 0.0
        self._fx_t = 0.0
        self._fx_dur = 0.0
        self._fx_timer = QTimer(self)
        self._fx_timer.setInterval(self._anim_timer.interval())
        self._fx_timer.timeout.connect(self._fx_step)

        # 雨丝专用的小马达：10fps。只在真的下雨、且窗口可见时跑，其余时候停着。
        self._rain_timer = QTimer(self)
        self._rain_timer.setInterval(125)      # 8fps：雨是像素雨，一帧走一格正好
        self._rain_timer.timeout.connect(self._rain_step)
        self._ms_hit: set[float] = set()
        self._ms_seeded = False
        self._greet_until = 0.0
        self._greet_text = ""
        self._quote_salt = 0            # 点一下"每日一句"就 +1，往后翻一句
        self._press_on_quote = False    # 这次按下是不是按在那句上
        self._plank_text = ""
        self._plank_hover = False
        self._plank_hover_armed = False
        self._offer_open = False
        self._offer_t0 = 0.0
        # 路过的小生物：今天的时刻表按（日期 + 上班时间）算，内存里只记"已经来过"
        self._life_fired: set[tuple[int, int]] = set()
        self._life_cache: tuple[object, list[int]] | None = None
        self._choice_hover = -1
        self._evening_choice: str | None = None

        self.snap = engine.snapshot(datetime.now(), self.store.work_start(self._day), self.rule)
        self._evening_choice = self.store.evening_choice(self._day)
        self.store.settle(self.rule, self._day)
        self.store.save()

        self._apply_opacity()
        self._restore_position()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000)

        self._first_prompt_done = False

    # ---------------------------------------------------------------- 生命周期


    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        hwnd = int(self.winId())
        if self.cfg.get("ui.always_on_top", True):
            win32.set_topmost(hwnd, True)
        if not self._first_prompt_done:
            self._first_prompt_done = True
            QTimer.singleShot(500, self._maybe_prompt_start)
        self._sync_rain_timer()             # 刚显示出来就下雨，不用等到下一个整秒


    def _apply_opacity(self) -> None:
        if self._pt_active:
            op = float(self.cfg.get("ui.passthrough_opacity", 0.45))
        else:
            op = float(self.cfg.get("ui.opacity", 1.0))
        self.setWindowOpacity(max(0.1, min(1.0, op)))


    def _restore_position(self) -> None:
        geo = self.store.window()
        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 2560, 1440)
        w, h = self.width(), self.height()
        if isinstance(geo.get("x"), int) and isinstance(geo.get("y"), int):
            x, y = geo["x"], geo["y"]
            # 夹回可见区域，换显示器也不会跑丢
            x = max(avail.left() - w // 3, min(x, avail.right() - w // 3))
            y = max(avail.top(), min(y, avail.bottom() - h // 3))
            self.move(int(x), int(y))
        else:
            margin = int(self.cfg.get("ui.corner_margin", 32))
            self.move(avail.right() - w - margin, avail.bottom() - h - margin - 40)


    def _persist_position(self) -> None:
        self.store.set_window(self.x(), self.y())
        self._save_timer.start(400)

    # ---------------------------------------------------------------- 尺寸 / 配色


    def _layout(self) -> dict:
        return self.COMPACT_LAYOUT if self._compact else self.FULL_LAYOUT


    def _apply_tier(self, tier: str) -> None:
        """切尺寸档：只改布局单位数与整数倍 S，然后重新排版，不做任何位图拉伸。"""
        if tier not in TIERS:
            tier = "standard"
        t = TIERS[tier]
        self._tier = tier
        self._compact = bool(t["compact"])
        self.W_UNITS = int(t["w"])
        self.H_UNITS = int(t["h"])
        self.S = max(1, min(8, int(self._base_s) + int(t["s_add"])))
        self._hover_btn = False
        self._plank_hover = False
        self._choice_hover = -1
        self.apply_units_size()
        self.update()


    def set_tier(self, tier: str) -> None:
        if tier not in TIERS or tier == self._tier:
            return
        geo = self.frameGeometry()
        right, bottom = geo.right(), geo.bottom()
        self._apply_tier(tier)
        # 锚定右下角，切档时窗口不会跳
        self.move(right - self.width() + 1, bottom - self.height() + 1)
        self.cfg.set("ui.size_tier", tier)
        try:
            self.cfg.save()
        except Exception:
            pass
        self._persist_position()
        self.update()

