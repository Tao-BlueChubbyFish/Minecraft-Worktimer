"""鼠标与菜单：拖动、点击命中、右键菜单、设置与登记弹窗、托盘、穿透锁定。"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu
from .. import __version_label__, engine, style, weather, win32
from .consts import TIERS, TIER_ORDER, WEEK_CN  # noqa: F401


class InteractMixin:

    def _hit_plank(self, pos_logical: QPoint) -> bool:
        dpr = self._dpr or 1.0
        px = QPoint(int(pos_logical.x() * dpr), int(pos_logical.y() * dpr))
        if self.snap.state != engine.ST_OVERTIME or self._evening_choice:
            return False
        if self._offer_open:
            return False
        return self._plank_rect_px().contains(px)


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
            moved = self.end_drag(event.globalPosition().toPoint())
            self.unsetCursor()
            if moved:
                self._persist_position()
            elif self._press_on_quote:
                # 点一下那句 = 换下一句；手指挪过（拖窗口）就不算
                self.next_quote()
        self._press_on_quote = False
        super().mouseReleaseEvent(event)


    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if self._pt_active:
            return
        pos = event.position().toPoint()
        if self._in_quote(pos):
            return                      # 双击那句话只翻句，不弹登记窗
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
        m = QMenu(self)
        m.setFont(self.font())
        m.setStyleSheet(style.menu_qss(pal, font_px, self.family))

        cumulative = self.store.cumulative_minutes(self._day, self._live_overtime())
        a_time = m.addAction("修改今日上班时间…")
        a_cfg = m.addAction("设置…")
        a_home = m.addAction("今天就到这（收工）")
        a_home.setEnabled(self.snap.state == engine.ST_OVERTIME
                          and self._evening_choice != "home")
        a_reset = m.addAction("重置当日计时")
        a_stats = m.addAction(f"查看累计加班时长（{engine.humanize(cumulative)}）")
        m.addSeparator()

        # 窗口尺寸：三档单选，切换后立即重排（整数倍像素，不拉伸）
        m_size = m.addMenu("窗口尺寸")
        for key in TIER_ORDER:
            a = m_size.addAction(TIERS[key]["label"])
            a.setCheckable(True)
            a.setChecked(key == self._tier)
            a.triggered.connect(lambda _=False, k=key: self.set_tier(k))

        # 每日一句（小档不显示，标准 / 大档生效）
        a_quote = m.addAction("每日一句")
        a_quote.setCheckable(True)
        a_quote.setChecked(bool(self.cfg.get("ui.quote", True)))
        a_quote.setEnabled(not self._compact)
        a_quote.triggered.connect(self.toggle_quote)

        # 天气只占一条：文字报"今天什么天"，勾选本身就是开关。
        # 勾掉 = 这片天空什么天气都不要（连云一起收），所以晴天勾也有变化。
        today_w = weather.weather_of(self._day)
        on = bool(self.cfg.get("ui.fx.weather", True))
        a_weather = m.addAction(f"天气：{weather.LABELS[today_w]}" + ("" if on else "（已关）"))
        a_weather.setCheckable(True)
        a_weather.setChecked(on)
        a_weather.triggered.connect(self.toggle_weather)

        m.addSeparator()
        secs = self.cfg.get("passthrough_seconds", 3)
        a_pt = m.addAction(f"临时穿透（{secs:g} 秒）")
        auto_on = win32.autostart_enabled()
        a_auto = m.addAction(f"开机自启：{'开' if auto_on else '关'}")
        m.addSeparator()
        a_hide = m.addAction("最小化到托盘")
        a_about = m.addAction(f"关于 MC 工时牌 {__version_label__}…")
        a_about.triggered.connect(self.open_about_dialog)
        a_quit = m.addAction("退出")

        a_time.triggered.connect(self.open_time_dialog)
        a_cfg.triggered.connect(self.open_settings_dialog)
        a_home.triggered.connect(lambda: self._choose("home"))
        a_reset.triggered.connect(self.reset_today)
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
            try:
                self.cfg.save()
            except Exception:
                pass
            self._tick()
            self.update()


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
