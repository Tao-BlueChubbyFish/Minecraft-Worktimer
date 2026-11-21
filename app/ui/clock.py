"""计时与状态推进：把「现在几点」翻译成进度、草皮卷、里程碑、鸟群、到点询问。"""
from __future__ import annotations

import time as _time
from datetime import datetime, time
from PySide6.QtCore import QTimer
from .. import engine, life, quotes, theme, weather
from .consts import TIERS, TIER_ORDER, WEEK_CN  # noqa: F401


class ClockMixin:

    def _visual_hour(self, now: datetime) -> float:
        """真实钟点 → 进度条里的"天色小时"。"""
        hour = now.hour + now.minute / 60.0 + now.second / 3600.0
        if not self.cfg.get("ui.daylight_tint", True):
            return 12.0
        if self.cfg.get("ui.sky_mode", "work") != "work":
            return hour
        snap = getattr(self, "snap", None)
        day = getattr(self, "_day", None)
        start = (snap.work_start if snap is not None else None)
        if start is None and day is not None:
            start = self.store.work_start(day)
        if start is None:                      # 还没设置上班时间：按真实钟点
            return hour
        span = float(self.cfg.get("ui.sky_span_hours", 13.0) or 13.0)
        h = theme.work_sky_hour(hour, start.hour + start.minute / 60.0, span)
        # 加班入夜：过了下班时间，天色继续往深夜多走一点。
        # 不用写字催人回家，让天自己暗下去——人对自己看着黑下来的天更敏感。
        if snap is not None and snap.state == engine.ST_OVERTIME:
            h += 0.8
        return h


    def _refresh_palette(self, now: datetime, force: bool = False) -> None:
        """按钟点刷新草皮 / 泥土色温，每小时只算一次。"""
        key = int(now.hour + now.minute / 60.0)
        if not force and key == self._pal_hour:
            return
        self._pal_hour = key
        self.pal = theme.palette_at(self._pal_base, self._visual_hour(now))

    # ---------------------------------------------------------------- 计时


    def _tick(self) -> None:
        now = datetime.now()
        self._refresh_palette(now)
        if now.date() != self._day:
            self._on_new_day(now)
        self.snap = engine.snapshot(now, self.store.work_start(self._day), self.rule)
        self.store.note_today(self._day, self._live_overtime(), now)
        if self._last_persist is None or (now - self._last_persist).total_seconds() >= 30:
            self.store.save()
            self._last_persist = now
        self._advance_roll(self.snap.progress)
        if not self._animating and self.cfg.get("ui.sod_roll_idle", True):
            self._roll_phase += float(self.cfg.get("ui.sod_roll_idle_speed", 0.012) or 0.012)
        self._check_milestones()
        self._check_life(now)
        self._update_evening()
        self._sync_rain_timer()
        if self.tray is not None:
            self.tray.refresh(self.snap, self._evening_choice)
        self.update()

    def _sync_rain_timer(self) -> None:
        """下雨天才开的那条小马达：雨丝要走，主计时器一秒一帧不够看。

        大雨 83ms（约 12fps，雨快而长，慢了会断成几截），小雨 125ms（8fps 刚好）。
        晴天 / 阴天 / 收进托盘 / 关了天气开关，都立刻停——不留一条空转的定时器。
        """
        today = weather.weather_of(self._day)
        want = (bool(self.cfg.get("ui.fx.weather", True))
                and today in weather.RAINY
                and self.isVisible())
        if want:
            interval = 83 if today == weather.DOWNPOUR else 125
            if self._rain_timer.interval() != interval:
                self._rain_timer.setInterval(interval)
            if not self._rain_timer.isActive():
                self._rain_timer.start()
        elif self._rain_timer.isActive():
            self._rain_timer.stop()

    def _rain_step(self) -> None:
        if not self.isVisible():
            self._rain_timer.stop()
            return
        self.update()

    # ---------------------------------------------------------------- 草皮卷


    def _roll_turns(self, d_ratio: float) -> float:
        """滚过的距离 → 卷转过的圈数（转一圈 ≈ 走过的周长，略作夸张）。"""
        pad = self.u(self._layout().get("bar_pad", self._layout()["pad"]))
        units = max(8.0, (self.u(self.W_UNITS) - 2 * pad) / max(1, self.S))
        return d_ratio * units * theme._SOD_ROLL_TURN_PER_UNIT


    def _advance_roll(self, progress: float) -> None:
        """进度前进时，让前沿"滚"过去，而不是跳一格。

        只有"攒够一个单位"才演一次：单位是进度条的最小像素格（标准档约 2.8 分钟
        一格），否则每秒都在起动画，卷会原地抖、原地转，看着像个打转的轮子。
        `_last_progress` 记的是"上一次滚动起点"，没攒够就不动它。
        """
        prev = self._last_progress
        if self._animating or progress <= prev + 1e-6:
            return
        pad = self.u(self._layout().get("bar_pad", self._layout()["pad"]))
        units = max(8.0, (self.u(self.W_UNITS) - 2 * pad) / max(1, self.S))
        step = 1.0 / units
        if progress - prev < step * 0.98:   # 还不到一格，攒着
            return
        self._last_progress = progress
        if progress - prev > step * 8:      # 一次跳太多（补算 / 重启）：不演动画
            self._roll_phase += self._roll_turns(progress - prev)
            return
        self._anim_from, self._anim_target = prev, progress
        self._roll_phase0 = self._roll_phase
        self._anim_t0 = _time.perf_counter()
        self._animating = True
        self._anim_timer.start()


    def _anim_step(self) -> None:
        if not self.cfg.get("ui.sod_roll", True):
            self._animating = False
            self._anim_timer.stop()
            return
        t = (_time.perf_counter() - self._anim_t0) / 0.8
        if t >= 1.0:
            self._anim_ratio = self._anim_target
            self._animating = False
            self._roll_lift = 0
            self._anim_timer.stop()
            self.update()
            return
        e = 1.0 - (1.0 - t) ** 3                       # 先快后慢：一口气铺到位
        self._anim_ratio = self._anim_from + (self._anim_target - self._anim_from) * e
        # 卷是"滚"过去的：转多少圈由走过的距离定，不是原地疯转
        self._roll_phase = self._roll_phase0 + self._roll_turns(
            self._anim_ratio - self._anim_from)
        self._roll_lift = 1 if int(t * 5) % 2 else 0   # 一路上颠两下
        self.update()


    def _on_new_day(self, now: datetime) -> None:
        self.store.note_today(self._day, self._live_overtime(), now)
        self.store.settle(self.rule, now.date())
        self.store.save()
        self._day = now.date()
        self._quote_salt = 0            # 新的一天从那句固定的开始
        self._first_prompt_done = False
        # 新的一天：里程碑、收工牌、晚间选择全部归零
        self._ms_hit.clear()
        self._ms_seeded = False
        self._plank_text = ""
        self._offer_open = False
        self._offer_t0 = 0.0
        self._life_fired.clear()
        self._life_cache = None
        self._evening_choice = None
        self._fx_kind = ""
        self._fx_timer.stop()
        # 勾了「以后每天用这个时间」就悄悄登记，不再弹窗
        if not self._apply_remembered_start(self._day):
            QTimer.singleShot(1200, self._maybe_prompt_start)


    def _apply_remembered_start(self, day) -> bool:
        """勾了「以后每天用这个时间」：工作日直接按默认时间登记，不弹窗。

        三条前提缺一不可：开关是开的、今天是上班日、今天还没登记过。
        手动登记过的天永远不覆盖——用户改过的意图比默认值重要。
        """
        if not self.cfg.get("schedule.remember_start", False):
            return False
        if not self.rule.is_workday(day):
            return False
        if self.store.work_start(day) is not None:
            return False
        default = engine.parse_hhmm(self.cfg.get("schedule.default_work_start", "09:00"),
                                    time(9, 0))
        self.store.set_work_start(day, default)
        self.store.save()
        return True


    def _maybe_prompt_start(self) -> None:
        now = datetime.now()
        if self._apply_remembered_start(now.date()):
            self._tick()
            return
        if not self.rule.is_workday(now.date()):
            return
        if self.store.work_start(now.date()) is not None:
            return
        if not self.cfg.get("schedule.ask_start_on_launch", True):
            return
        self.open_time_dialog()

    # ---------------------------------------------------------------- 情绪化动效
    MILESTONES = (0.25, 0.75, 0.90)


    def _lunch_ratio(self) -> float | None:
        """午休开始那一刻在进度条上的位置；没登记上班时间就返回 None。"""
        start = self.store.work_start(self._day)
        target = self.rule.target_minutes(start) if start else 0.0
        if start is None or target <= 0:
            return None
        begin = datetime.combine(self._day, start)
        lunch = datetime.combine(self._day, self.rule.lunch_start)
        if lunch <= begin:
            return None
        ratio = engine.worked_minutes(begin, lunch, self.rule) / target
        return ratio if 0.01 < ratio < 0.99 else None


    def _check_milestones(self) -> None:
        """跨过 25/75/90% 时给一次小反馈：卷子跳一下 + 百分比变金 + 短语顶一会儿。

        50% 那个点特意不设：默认 9 点上班时它正好落在午休里，没人看屏幕。
        """
        if not self.cfg.get("ui.fx.milestone", True):
            return
        if self.snap.state != engine.ST_WORKING:
            return
        prog = self.snap.progress
        if not self._ms_seeded:
            # 启动时已经过了的里程碑不该再"补响"一次：那是过去的事，不是刚发生的事
            self._ms_seeded = True
            self._ms_hit.update(m for m in self.MILESTONES if prog > m + 1e-6)
        for m in self.MILESTONES:
            if prog + 1e-9 >= m and m not in self._ms_hit:
                self._ms_hit.add(m)
                self._start_fx("ms", 1.4)
                self._greet_text = quotes.milestone_text(prog, self._day)
                self._greet_until = _time.perf_counter() + 8.0
                break


    def _life_events(self) -> list[int]:
        """今天的"路过"时刻表。按（日期, 上班时间）缓存，改上班时间会自动重算。"""
        key = (self._day, self.store.work_start(self._day))
        cache = self._life_cache
        if cache is not None and cache[0] == key:
            return cache[1]
        ev = life.events_for(self._day, key[1], self.rule)
        self._life_cache = (key, ev)
        return ev


    def _check_life(self, now: datetime) -> None:
        """到点放一只小生物过去。

        用"当前分钟落在一个 8 秒窗口里"来判定，不排队、不建定时器：_tick 每秒
        跑一次，窗口够宽不会漏；重启后只要还在窗口内，它还会从同一条路径飞一遍。
        """
        if not self.cfg.get("ui.fx.life", True):
            return
        if self.snap.state != engine.ST_WORKING or self._fx_kind:
            return
        if self._compact:      # 小档条太矮，鸟群挤进去只会糊成一团
            return
        minute = now.hour * 60 + now.minute + now.second / 60.0
        for at in self._life_events():
            key = (self._day.toordinal(), at)
            if key in self._life_fired or not (0.0 <= minute - at < 0.14):
                continue
            self._life_fired.add(key)
            # 每次速度略不同（17~25 秒），同一队形飞两次也不会一模一样
            self._start_fx("life", 17.0 + (self._day.toordinal() % 4) * 2.6)
            break


    def _start_fx(self, kind: str, dur: float) -> None:
        self._fx_kind = kind
        self._fx_t0 = _time.perf_counter()
        self._fx_dur = max(0.1, dur)
        self._fx_t = 0.0
        self._fx_timer.start()


    def _fx_step(self) -> None:
        if not self._fx_kind:
            self._fx_timer.stop()
            return
        t = (_time.perf_counter() - self._fx_t0) / self._fx_dur
        if t >= 1.0:
            kind = self._fx_kind
            self._fx_kind = ""
            self._fx_t = 0.0
            self._fx_timer.stop()
            if kind == "ms":
                self._roll_lift = 0
            elif kind == "home":
                self._plank_text = ""
            self.update()
            return
        self._fx_t = t
        if self._fx_kind == "ms":
            self._roll_lift = 2 if t < 0.3 else 0
        self.update()


    def _update_evening(self) -> None:
        """到点之后的流程：木牌 →（悬停/点击/超时）两个选项 → 回家 或 加班。"""
        if self.snap.state != engine.ST_OVERTIME:
            self._offer_open = False
            self._offer_t0 = 0.0
            self._plank_hover = False
            return
        if not self._plank_text:
            self._plank_text = quotes.plank_text(self._day)
        choice = self.store.evening_choice(self._day)
        self._evening_choice = choice
        if choice is not None:
            self._offer_open = False
            return
        if not self.cfg.get("ui.fx.offer", True):
            return
        if self._offer_t0 <= 0.0:
            self._offer_t0 = _time.perf_counter()
        if self._offer_open:
            return
        idle = float(self.cfg.get("ui.fx.offer_idle_seconds", 25) or 25)
        if _time.perf_counter() - self._offer_t0 >= idle:
            self._open_offer()


    def _open_on_hover(self) -> None:
        """悬停 0.7 秒展开：想点的人不用先点一下，路过的人也不会被突然弹窗。"""
        self._plank_hover_armed = False
        if self._plank_hover and not self._offer_open and not self._evening_choice:
            self._open_offer()


    def _open_offer(self) -> None:
        if self._offer_open or self._evening_choice:
            return
        self._offer_open = True
        self._plank_text = "还加班吗"
        self._plank_hover = False
        self.update()


    def _choose(self, choice: str) -> None:
        """回家 = 收工庆祝；加班 = 进入加班计时。选完就落盘，重启不再问。"""
        self.store.set_evening_choice(self._day, choice)
        self.store.save()
        self._evening_choice = choice
        self._offer_open = False
        self._choice_hover = -1
        self.unsetCursor()
        if choice == "home":
            self._plank_text = quotes.cheer_text(self._day)
            if self.cfg.get("ui.fx.celebrate", True):
                self._start_fx("home", 5.0)
            else:
                self._plank_text = ""
        else:
            self._plank_text = ""
        self.update()

    # ---------------------------------------------------------------- 命中区（收工牌）
