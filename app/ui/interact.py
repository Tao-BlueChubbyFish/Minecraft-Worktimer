"""鼠标与菜单：拖动、点击命中、右键菜单、设置与登记弹窗、托盘、穿透锁定。"""
from __future__ import annotations

import sys
import time as _time

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu
from .. import engine, season, style, weather, win32
from .consts import TIERS, TIER_ORDER, WEEK_CN  # noqa: F401


class StayOpenMenu(QMenu):
    """勾选项点了不关的菜单。

    QMenu 默认点任何一项就收起。这个菜单里一半是勾选开关（云朵、下落物、
    每日一句、帧率档位），想连着调两个，就得反复右键、反复找位置。
    所以这里拦下"点了勾选项"的那一下：状态改了，菜单留着，点别处再收。
    普通命令项（设置、收工、退出）照旧一点就关——那些是"执行一次"的动作，
    留着菜单反而碍事。
    """

    def _stay(self, event) -> bool:
        """这一下是不是点在勾选开关上（是 = 不关菜单）。"""
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        act = self.actionAt(event.position().toPoint())
        return (act is not None and act.isCheckable() and act.isEnabled()
                and act.menu() is None)

    def mousePressEvent(self, event):  # noqa: N802
        # QMenu 在"按下"这一步就把自己藏了，所以拦截必须放在 press；
        # 放到 release 里已经晚了——菜单早没了，用户看到的是闪一下。
        if self._stay(event):
            act = self.actionAt(event.position().toPoint())
            act.trigger()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self._stay(event):
            event.accept()
            return
        super().mouseReleaseEvent(event)


class InteractMixin:

    def _hit_plank(self, pos_logical: QPoint) -> bool:
        dpr = self._dpr or 1.0
        px = QPoint(int(pos_logical.x() * dpr), int(pos_logical.y() * dpr))
        if self.snap.state != engine.ST_OVERTIME or self._evening_choice:
            return False
        if self._offer_open:
            return False
        return self._plank_rect_px().contains(px)


    def _in_meadow(self, pos_logical: QPoint) -> bool:
        """点在不在那条草地上。草地在正文里，上下都是字，命中区只取进度条那一块。"""
        dpr = self._dpr or 1.0
        x = int(pos_logical.x() * dpr)
        y = int(pos_logical.y() * dpr)
        L = self._layout()
        pad = self.u(L.get("bar_pad", L["pad"]))
        top = self.u(L["bar_y"])
        hh = self.u(L["bar_h"])
        return pad <= x < self.u(self.W_UNITS) - pad and top <= y < top + hh

    def _hit_choice(self, pos_logical: QPoint) -> int:
        if not self._offer_open:
            return -1
        dpr = self._dpr or 1.0
        px = QPoint(int(pos_logical.x() * dpr), int(pos_logical.y() * dpr))
        for i, r in enumerate(self._choice_rects_px()):
            if r.contains(px):
                return i
        return -1

    # ---------------------------------------------------------------- 绘制：收工牌


    def _btn_rect_units(self) -> QRect:
        # 菜单键在草皮带里垂直居中（跟标题、图标同一条中线），命中区一起跟着走
        y = max(1, int(round((self._layout()["header"] - 12) / 2)))
        return QRect(self.W_UNITS - 4 - 12, y, 12, 12)


    def _btn_rect_px(self) -> QRect:
        r = self._btn_rect_units()
        return QRect(self.u(r.x()), self.u(r.y()), self.u(r.width()), self.u(r.height()))


    def _quote_rect_px(self) -> QRect:
        """底部"每日一句"的可点区域：整行宽，纵向放宽一点好点。"""
        L = self._layout()
        qb = int(L.get("quote_bottom", 0) or 0)
        if not qb:
            return QRect()                  # 小档没有这一行
        h = 16
        return QRect(self.u(2), self.u(max(0, qb - h + 2)),
                     self.u(max(1, self.W_UNITS - 4)), self.u(h))

    def _in_quote(self, pos_logical: QPoint) -> bool:
        dpr = self._dpr or 1.0
        px = QPoint(int(pos_logical.x() * dpr), int(pos_logical.y() * dpr))
        return self._quote_rect_px().contains(px)

    def next_quote(self) -> None:
        """点一下"每日一句"：往后翻一句（同一天内循环，跨天自动归零）。"""
        self._quote_salt = int(getattr(self, "_quote_salt", 0)) + 1
        self.update()

    def _in_btn(self, pos_logical: QPoint) -> bool:
        dpr = self._dpr or 1.0
        px = QPoint(int(pos_logical.x() * dpr), int(pos_logical.y() * dpr))
        return self._btn_rect_px().contains(px)

    # ---------------------------------------------------------------- 交互


    def mousePressEvent(self, event):  # noqa: N802
        if self._pt_active:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            idx = self._hit_choice(pos)
            if idx >= 0:                       # 选「回家」/「再干会儿」
                self._choose("home" if idx == 0 else "overtime")
                return
            if self._hit_plank(pos):           # 点收工牌：展开两个选项
                self._open_offer()
                return
            if self._in_btn(pos):
                self.open_menu(event.globalPosition().toPoint())
                return
            self._press_on_quote = self._in_quote(pos)
            self._press_on_meadow = self._in_meadow(pos)
            self.begin_drag(event.globalPosition().toPoint())
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        elif event.button() == Qt.MouseButton.RightButton:
            if self.cfg.get("ui.right_click_action", "passthrough") == "menu":
                self.open_menu(event.globalPosition().toPoint())
            else:
                self.enter_passthrough()
        super().mousePressEvent(event)


    def mouseMoveEvent(self, event):  # noqa: N802
        if self._pt_active:
            return
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self.update_drag(event.globalPosition().toPoint())
        else:
            pos = event.position().toPoint()
            hover_btn = self._in_btn(pos)
            hover_plank = self._hit_plank(pos)
            hover_choice = self._hit_choice(pos)
            changed = (hover_btn != self._hover_btn
                       or hover_plank != self._plank_hover
                       or hover_choice != self._choice_hover)
            self._hover_btn = hover_btn
            self._plank_hover = hover_plank
            self._choice_hover = hover_choice
            if hover_plank and not self._plank_hover_armed:
                self._plank_hover_armed = True
                QTimer.singleShot(700, self._open_on_hover)
            elif not hover_plank:
                self._plank_hover_armed = False
            if changed:
                clickable = hover_btn or hover_plank or hover_choice >= 0
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor) if clickable
                               else Qt.CursorShape.OpenHandCursor)
                self.update()
        super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            pos = event.position().toPoint()
            moved = self.end_drag(event.globalPosition().toPoint())
            self.unsetCursor()
            if moved:
                self._persist_position()
            elif self._press_on_quote:
                # 点一下那句 = 换下一句；手指挪过（拖窗口）就不算
                self.next_quote()
            elif self._press_on_meadow:
                self.poke_meadow(pos)
        self._press_on_quote = False
        self._press_on_meadow = False
        super().mouseReleaseEvent(event)


    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if self._pt_active:
            return
        pos = event.position().toPoint()
        if self._in_quote(pos):
            return                      # 双击那句话只翻句，不弹登记窗
        # 草地上双击 = 连推两下，不是"打开登记窗"。
        # 连点是这个互动里最上瘾的部分，被一个弹窗打断就全毁了；
        # 登记窗在「设置」里，只补今天的话双击别处也行，不缺这一条路。
        if event.button() == Qt.MouseButton.LeftButton and self._in_meadow(pos):
            self.poke_meadow(pos)
            return
        if event.button() == Qt.MouseButton.LeftButton and not self._in_btn(pos) \
                and not self._hit_plank(pos) and self._hit_choice(pos) < 0:
            self.open_time_dialog()


    def leaveEvent(self, event):  # noqa: N802
        self._plank_hover_armed = False
        if self._hover_btn or self._plank_hover or self._choice_hover >= 0:
            self._hover_btn = False
            self._plank_hover = False
            self._choice_hover = -1
            self.unsetCursor()
            self.update()

    # ---------------------------------------------------------------- 穿透


    def enter_passthrough(self) -> None:
        if self._pt_active:
            return
        secs = float(self.cfg.get("passthrough_seconds", 3))
        self._pt_active = True
        self._pt_remaining = secs
        self._drag_offset = None
        self._hover_btn = False
        self.unsetCursor()
        self.setWindowOpacity(max(0.1, min(1.0, float(self.cfg.get("ui.passthrough_opacity", 0.45)))))
        win32.set_click_through(int(self.winId()), True)
        self._pt_timer.start(int(max(0.5, secs) * 1000))
        self.update()


    def exit_passthrough(self) -> None:
        if not self._pt_active:
            return
        self._pt_active = False
        win32.set_click_through(int(self.winId()), False)
        if self.cfg.get("ui.always_on_top", True):
            win32.set_topmost(int(self.winId()), True)
        self._apply_opacity()
        self.update()


    def toggle_passthrough(self) -> None:
        if self._pt_active:
            self.exit_passthrough()
        else:
            self.enter_passthrough()

    # ---------------------------------------------------------------- 菜单


    def build_menu(self) -> QMenu:
        pal = self.pal
        font_px = max(11, int(round(9 * self.S * self._dpr / (self._dpr or 1.0))))
        m = StayOpenMenu(self)
        m.setFont(self.font())
        m.setStyleSheet(style.menu_qss(pal, font_px, self.family))

        cumulative = self.store.cumulative_minutes(self._day, self._live_overtime())
        # 只有这一个入口。以前「今天几点到的」和「作息设置」分成两项，两处都能改
        # 上班时间，站在用户角度根本分不清该点哪个。
        a_cfg = m.addAction("设置…")
        a_home = m.addAction("今天就到这（收工）")
        a_home.setEnabled(self.snap.state == engine.ST_OVERTIME
                          and self._evening_choice != "home")
        a_reset = m.addAction("重置当日计时")
        # 牛马记录：工时记在左、废话记在右，都是给老板打工这件事的存档。
        # 不用"账本"——太像财务软件；牛马是自嘲，点开之前就已经笑了一下。
        m.addSeparator()
        m_rec = StayOpenMenu("牛马日常", m)
        m.addMenu(m_rec)
        a_day = m_rec.addAction("今日结算…")
        a_week = m_rec.addAction("一周…")
        a_note = m_rec.addAction("吐槽两句…")
        a_stats = m_rec.addAction(f"累计加班（{engine.humanize(cumulative)}）")

        # 外观与声音：画面长什么样、有没有声。同属"这个挂件看起来如何"，合在一处。
        m_show = StayOpenMenu("外观", m)
        m.addMenu(m_show)

        # 窗口尺寸：三档单选，切换后立即重排（整数倍像素，不拉伸）
        m_size = StayOpenMenu("窗口尺寸", m_show)
        m_show.addMenu(m_size)
        # 菜单点完不关，所以"单选"要自己维护：勾一个，把别的取消。
        self._tier_actions = {}
        for key in TIER_ORDER:
            a = m_size.addAction(TIERS[key]["label"])
            a.setCheckable(True)
            a.setChecked(key == self._tier)
            a.triggered.connect(lambda _=False, k=key: self.set_tier(k))
            self._tier_actions[key] = a
        m_show.addSeparator()

        # 每日一句（小档不显示，标准 / 大档生效）
        a_quote = m_show.addAction("每日一句")
        a_quote.setCheckable(True)
        a_quote.setChecked(bool(self.cfg.get("ui.quote", True)))
        a_quote.setEnabled(not self._compact)
        a_quote.triggered.connect(self.toggle_quote)

        # 拆成两个开关：天上飘的云、往下落的东西。不再用"晴/阴"这类气象词——
        # 用户看得见的是画面元素，术语反而隔了一层。
        clouds_on = bool(self.cfg.get("ui.fx.clouds",
                                      self.cfg.get("ui.fx.weather", True)))
        a_clouds = m_show.addAction("云朵")
        a_clouds.setCheckable(True)
        a_clouds.setChecked(clouds_on)
        a_clouds.triggered.connect(self.toggle_clouds)

        fall_on = bool(self.cfg.get("ui.fx.fall",
                                    self.cfg.get("ui.fx.weather", True)))
        a_fall = m_show.addAction(f"下落物：{self._fall_label()}" if fall_on
                                  else "下落物：关")
        a_fall.setCheckable(True)
        a_fall.setChecked(fall_on)
        a_fall.triggered.connect(self.toggle_fall)
        self._act_fall = a_fall

        # 动画流畅度：三档都在，默认那档由机器自己判断（见 _probe_fps）。
        # 菜单里只摆三个具体档位，不摆"自动"——用户要的是"我现在跑哪一档"，
        # 不是"程序是怎么决定的"。
        m_fps = StayOpenMenu("帧率", m_show)
        m_show.addMenu(m_fps)
        fps_now = self._fps_mode()
        self._fps_actions = {}
        for key, label in (("high", "高"),
                           ("mid", "中"),
                           ("low", "低（省电）")):
            a_fps = m_fps.addAction(label)
            a_fps.setCheckable(True)
            a_fps.setChecked(fps_now == key)
            a_fps.triggered.connect(lambda _=False, k=key: self.set_fps(k))
            self._fps_actions[key] = a_fps

        # 音效默认关：有人开着它工作，突然一声会吓一跳。想听的人自己打开。
        snd_on = bool(self.cfg.get("ui.fx.sound", False))
        a_snd = m_show.addAction("音效（下班、里程碑各一声）")
        a_snd.setCheckable(True)
        a_snd.setChecked(bool(self.cfg.get("ui.fx.sound", False)))
        a_snd.triggered.connect(self.toggle_sound)
        # 「试听」只给源码版：打包成 exe 以后 `sys.frozen` 为真，这一行自动消失。
        # 正式版不需要它——音效是装饰，不该在菜单里多占一格。
        if not getattr(sys, "frozen", False):
            a_snd_try = m_show.addAction("　试听一下")
            a_snd_try.triggered.connect(self.preview_sound)

        m.addSeparator()
        secs = self.cfg.get("passthrough_seconds", 3)
        # "穿透"是行话，用户不懂；他真正要的是"这几秒别挡我鼠标"
        a_pt = m.addAction(f"暂时不挡鼠标（{secs:g} 秒）")
        auto_on = win32.autostart_enabled()
        a_auto = m.addAction(f"开机自启：{'开' if auto_on else '关'}")
        m.addSeparator()
        a_hide = m.addAction("最小化到托盘")
        # 版本号不摆在菜单里：菜单窄，长版本号会被截成"v1.1…"，
        # 想看版本的人点进去，那里有整行大字还能一键复制。
        a_about = m.addAction("关于…")
        a_about.triggered.connect(self.open_about_dialog)
        a_quit = m.addAction("退出")

        a_cfg.triggered.connect(self.open_settings_dialog)
        a_home.triggered.connect(lambda: self._choose("home"))
        a_reset.triggered.connect(self.reset_today)
        a_day.triggered.connect(self.show_day)
        a_week.triggered.connect(self.show_week)
        a_note.triggered.connect(self.show_note)
        a_stats.triggered.connect(self.show_stats)
        a_pt.triggered.connect(self.toggle_passthrough)
        a_auto.triggered.connect(self.toggle_autostart)
        a_hide.triggered.connect(self.hide_to_tray)
        a_quit.triggered.connect(self.quit_app)
        return m


    def open_menu(self, global_pos: QPoint) -> None:
        m = self.build_menu()
        m.exec(global_pos)

    # ---------------------------------------------------------------- 动作


    def open_time_dialog(self) -> None:
        from ..dialogs import TimeDialog

        current = self.store.work_start(self._day)
        dlg = TimeDialog(self, self.cfg, self.pal, self._base_s, self._dpr, current)
        if dlg.exec():
            value = dlg.result_time
            self.store.set_work_start(self._day, value)
            self.store.save()
            # 勾了「以后每天用这个时间」：默认时间跟着改，第二天自动登记；
            # 取消勾选就回到每天问一遍
            remember = bool(dlg.remember)
            self.cfg.set("schedule.remember_start", remember)
            if remember:
                self.cfg.set("schedule.default_work_start",
                             f"{value.hour:02d}:{value.minute:02d}")
            self._apply_weather_choice(dlg)
            try:
                self.cfg.save()
            except Exception:
                pass
            self._tick()
            self.update()


    # ---------------------------------------------------------------- 真实天气

    # 多久跟天气服务对一次表。天气是"当下"的东西：早上取到晴，下午真下起雨来，
    # 牌子上还挂着太阳就不对了。三小时一次，一个请求而已。
    _WX_TTL = 3 * 3600
    # 没网时下一回隔多久再试——别每秒都撞一次墙。
    _WX_RETRY = 15 * 60

    def _apply_weather_choice(self, dlg) -> None:
        """把对话框里「真实天气」的选择落到配置。没有这一项的窗就跳过。"""
        if not hasattr(dlg, "weather_choice"):
            return
        use_real, place = dlg.weather_choice()
        self.cfg.set("weather.asked", True)
        self.cfg.set("weather.fetched_day", "")
        self.cfg.set("weather.fetched_ts", 0.0)   # 换了地方就一定重取，不吃旧缓存
        self.cfg.set("weather.shown", "")
        if use_real and place:
            self.cfg.set("weather.mode", "real")
            self.cfg.set("weather.place", place)
            self.start_real_weather(place)
        else:
            self.cfg.set("weather.mode", "random")
            self.cfg.set("weather.place", "")
            weather.clear_real()

    def start_real_weather(self, place: str) -> None:
        """问一次真实天气。异步跑，界面不等它。"""
        if getattr(self, "_wx", None) is not None:
            return                       # 一次只查一个，别每秒 tick 都发请求
        from ..realtime_weather import WeatherFetcher

        self._wx = WeatherFetcher(self)
        self._wx.done.connect(self._on_weather_done)
        self._wx.failed.connect(self._on_weather_failed)
        self._wx.start(place)

    def _apply_cached_weather(self) -> None:
        """启动瞬间就把上次取到的真实天气接上，别先闪一帧随机天气。

        第一帧在 _tick 之前就画出来了，而 _tick 一秒后才跑，
        所以这里得在构造末尾手动接一次。

        **跨天也照接**：早上开机时缓存是昨天的，但昨天的天比随机抽一个更接近窗外，
        先顶几秒，等真正的请求回来再换。没网时它就是最后的已知值。
        """
        if str(self.cfg.get("weather.mode", "random")) != "real":
            return
        code = str(self.cfg.get("weather.code", "") or "")
        if code:
            weather.set_real(self._day, code, self.cfg.get("weather.temp"))

    def _maybe_fetch_weather(self) -> None:
        """启动时、跨天时、以及每过三小时，跟天气服务对一次表。

        缓存不是"当天取一次就够"：天气会在一天里变。所以缓存只认三小时，
        过期就在后台重取一次（界面照旧显示旧的，拿到新的再换，不闪）。
        """
        if str(self.cfg.get("weather.mode", "random")) != "real":
            return
        place = str(self.cfg.get("weather.place", "") or "").strip()
        if not place:
            return
        same_day = (str(self.cfg.get("weather.fetched_day", "") or "")
                    == self._day.isoformat())
        code = str(self.cfg.get("weather.code", "") or "")
        if code:
            # 每秒对一次表：跨天、或被别处清掉之后，画面能自己回到真实天气
            weather.set_real(self._day, code, self.cfg.get("weather.temp"))
        if getattr(self, "_wx", None) is not None:      # 上一发还没回来，别叠着发
            return
        try:
            ts = float(self.cfg.get("weather.fetched_ts", 0) or 0)
        except (TypeError, ValueError):
            ts = 0.0
        if same_day and code and (_time.time() - ts) < self._WX_TTL:
            return
        self.start_real_weather(place)

    def _on_weather_done(self, code: str, temp: float, shown: str) -> None:
        self._wx = None
        weather.set_real(self._day, code, temp)
        self.cfg.set("weather.code", code)
        self.cfg.set("weather.temp", float(temp))
        self.cfg.set("weather.fetched_day", self._day.isoformat())
        self.cfg.set("weather.fetched_ts", _time.time())
        if shown:
            self.cfg.set("weather.shown", shown)
        try:
            self.cfg.save()
        except Exception:
            pass
        self._tick()
        self.update()

    def _on_weather_failed(self, reason: str) -> None:
        """查不到就退回随机。不弹窗拦人——天气是氛围，不该挡住干活。

        但要把两种失败分开：
        - **地名不对**（"没找到「xx」"）：用户填错了。清掉设置、下次启动再问一次。
        - **网络不通**：设置本身是好的，只是这会儿连不上。上一次的天气接着用，
          过一刻钟再试——不能因为一次断网就把人家填好的地方抹掉。
        """
        self._wx = None
        place = str(self.cfg.get("weather.place", "") or "").strip()
        keep_old = (
            place
            and not str(reason).startswith("没找到")
            and bool(str(self.cfg.get("weather.code", "") or ""))
        )
        if keep_old:
            self.cfg.set("weather.fetched_ts",
                         _time.time() - self._WX_TTL + self._WX_RETRY)
            try:
                self.cfg.save()
            except Exception:
                pass
            return

        weather.clear_real()
        self.cfg.set("weather.mode", "random")
        self.cfg.set("weather.place", "")
        self.cfg.set("weather.code", "")
        self.cfg.set("weather.fetched_day", "")
        self.cfg.set("weather.fetched_ts", 0.0)
        self.cfg.set("weather.asked", False)   # 没设成，下次启动再给一次机会
        try:
            self.cfg.save()
        except Exception:
            pass
        self._toast("真实天气没设上：%s" % reason)

    def _toast(self, text: str) -> None:
        tray = getattr(self, "tray", None)
        if tray is not None:
            try:
                tray.showMessage("MC 工时牌", text)
            except Exception:
                pass

    def reset_today(self) -> None:
        from ..dialogs import confirm

        if not confirm(self, self.cfg, self.pal, self._base_s, self._dpr,
                       "重置当日计时", "清空今天的上班时间与加班记录？"):
            return
        self.store.reset_today(self._day)
        self._tick()
        self.update()


    def open_about_dialog(self) -> None:
        from ..dialogs import AboutDialog

        cumulative = self.store.cumulative_minutes(self._day, self._live_overtime())
        AboutDialog(self, self.cfg, self.pal, self._base_s, self._dpr, cumulative,
                    known=getattr(self, "_update_ready", None)).exec()

    def check_update_silent(self) -> None:
        """开机后悄悄问一次有没有新版。失败什么都不做——对方没装加速工具也不该被打扰。"""
        from ..update import UpdateChecker

        self._updater = UpdateChecker(self)
        self._updater.found.connect(self._remember_update)
        self._updater.start()

    def _remember_update(self, version: str, url: str) -> None:
        self._update_ready = (version, url)

    def show_stats(self) -> None:
        from ..dialogs import StatsDialog

        cumulative = self.store.cumulative_minutes(self._day, self._live_overtime())
        dlg = StatsDialog(self, self.cfg, self.pal, self._base_s, self._dpr,
                          cumulative, self.store, self.snap.overtime_minutes)
        dlg.exec()

    def show_day(self) -> None:
        from datetime import datetime
        from ..dialogs import DayDialog

        dlg = DayDialog(self, self.cfg, self.pal, self._base_s, self._dpr, self.store,
                        self.rule, datetime.now(), self._live_overtime())
        dlg.exec()

    def show_week(self) -> None:
        from datetime import datetime
        from ..dialogs import WeekDialog

        dlg = WeekDialog(self, self.cfg, self.pal, self._base_s, self._dpr, self.store,
                         self.rule, datetime.now(), self._live_overtime())
        dlg.exec()

    def show_note(self) -> None:
        from ..dialogs import NoteDialog

        dlg = NoteDialog(self, self.cfg, self.pal, self._base_s, self._dpr,
                         self.store.note(self._day), day=self._day)
        if dlg.exec():
            self.store.set_note(self._day, dlg.text())
            self.store.save()


    def toggle_autostart(self) -> None:
        target = not win32.autostart_enabled()
        if win32.set_autostart(target):
            self.cfg.set("autostart", target)
            try:
                self.cfg.save()
            except Exception:
                pass


    def open_settings_dialog(self) -> None:
        """设置：上班时间 / 下班时间 / 午休 / 哪几天上班，全部落到 config.json。"""
        from ..dialogs import SettingsDialog

        dlg = SettingsDialog(self, self.cfg, self.pal, self._base_s, self._dpr,
                             self.store.work_start(self._day))
        if not dlg.exec():
            return
        start, offwork, lunch_start, lunch_min, workdays = dlg.result()
        self.cfg.set("schedule.offwork_time", f"{offwork.hour:02d}:{offwork.minute:02d}")
        self.cfg.set("schedule.lunch_start", f"{lunch_start.hour:02d}:{lunch_start.minute:02d}")
        self.cfg.set("schedule.lunch_minutes", int(lunch_min))
        self.cfg.set("schedule.workdays", [int(d) for d in workdays])
        self._apply_weather_choice(dlg)
        try:
            self.cfg.save()
        except Exception:
            pass
        # 上下班规则重建：改完休息日，今天可能从「休息」变成「待登记」（或反过来）
        self.rule = engine.build_rule(self.cfg)
        if start is not None:
            self.store.set_work_start(self._day, start)
            self.store.save()
        self._apply_remembered_start(self._day)
        self._ms_hit.clear()
        self._tick()
        self.update()


    def toggle_quote(self) -> None:
        on = not bool(self.cfg.get("ui.quote", True))
        self.cfg.set("ui.quote", on)
        try:
            self.cfg.save()
        except Exception:
            pass
        self.update()


    POKE_DUR = 0.42      # 冲击到完全复位的时间

    def poke_meadow(self, pos_logical: QPoint | None = None) -> None:
        """点一下草地：以落点为圆心，中间的花被顶开，四周的往外倒。

        主窗口一秒才重绘一次，只设一个"按下"状态的话，这 0.4 秒只会显示一帧——
        看着就是"花突然没了又突然回来"。所以冲击要自己开一条 16ms 的短定时器，
        一帧一帧画出去：开头位移最大，随后按平方衰减收回，才像被一股力推开。
        """
        if pos_logical is not None:
            dpr = self._dpr or 1.0
            self._poke_x = int(pos_logical.x() * dpr)
        self._poke_t0 = _time.perf_counter()
        if getattr(self, "_poke_timer", None) is None:
            t = QTimer(self)
            t.setInterval(16)
            t.timeout.connect(self._poke_frame)
            self._poke_timer = t
        self._poke_timer.start()
        self.update()

    def _poke_frame(self) -> None:
        t0 = getattr(self, "_poke_t0", None)
        if t0 is None or _time.perf_counter() - t0 >= self.POKE_DUR:
            self._poke_timer.stop()
        self.update()

    def preview_sound(self) -> None:
        """试听：不受开关限制，点了就响——用来确认"到底有没有声音"。"""
        from .. import sound
        sound.play("milestone")

    def _fall_label(self) -> str:
        """今天会往下掉什么：雨、雪、落叶，或者什么都不掉。"""
        w = weather.weather_of(self._day)
        if w in weather.PRECIP:
            return "雪" if w in weather.SNOWY else "雨"
        if season.season_of(self._day) == season.AUTUMN:
            return "落叶"
        return "无"

    def toggle_clouds(self) -> None:
        on = not bool(self.cfg.get("ui.fx.clouds",
                                   self.cfg.get("ui.fx.weather", True)))
        self.cfg.set("ui.fx.clouds", on)
        try:
            self.cfg.save()
        except Exception:
            pass
        self.update()

    def toggle_fall(self) -> None:
        on = not bool(self.cfg.get("ui.fx.fall",
                                   self.cfg.get("ui.fx.weather", True)))
        self.cfg.set("ui.fx.fall", on)
        act = getattr(self, "_act_fall", None)
        if act is not None:
            act.setText(f"下落物：{self._fall_label()}" if on else "下落物：关")
        try:
            self.cfg.save()
        except Exception:
            pass
        self._sync_rain_timer()
        self.update()

    def set_fps(self, key: str) -> None:
        """切换流畅度。切换后立刻按新档位重启定时器，不用等下一次 tick。"""
        for k, act in getattr(self, "_fps_actions", {}).items():
            act.setChecked(k == key)
        self.cfg.set("ui.fx.fps", key)
        try:
            self.cfg.save()
        except Exception:
            pass
        self._sync_rain_timer()
        self.update()

    def toggle_sound(self) -> None:
        on = not bool(self.cfg.get("ui.fx.sound", False))
        self.cfg.set("ui.fx.sound", on)
        try:
            self.cfg.save()
        except Exception:
            pass
        if on:
            from .. import sound
            sound.play("milestone")     # 打开时自己听一声，算试听

    def toggle_weather(self) -> None:
        on = not bool(self.cfg.get("ui.fx.weather", True))
        self.cfg.set("ui.fx.weather", on)
        try:
            self.cfg.save()
        except Exception:
            pass
        self._sync_rain_timer()
        self.update()

    def hide_to_tray(self) -> None:
        if self.tray is None:      # 没有托盘就保持可见，避免"消失"再也找不回来
            self.show()
            return
        self.hide()
        self.tray.notify_hidden()


    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hit_hide()
        else:
            self.show()
            self.raise_()
            if self.cfg.get("ui.always_on_top", True):
                win32.set_topmost(int(self.winId()), True)


    def hit_hide(self) -> None:
        self.hide()
        if self.tray is not None:
            self.tray.notify_hidden()


    def quit_app(self) -> None:
        self.store.save()
        self.request_quit.emit()
