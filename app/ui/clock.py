"""计时与状态推进：把「现在几点」翻译成进度、草皮卷、里程碑、鸟群、到点询问。"""
from __future__ import annotations

import time as _time
from datetime import datetime, time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPainter
from .. import engine, life, quotes, season, sound, theme, weather
from .consts import TIERS, TIER_ORDER, WEEK_CN  # noqa: F401


class ClockMixin:

    def _poke_power(self) -> float:
        """冲击的当前强度：0 = 没动，1 = 最强。

        点下去那一刻就是最大位移，之后按平方衰减收回——
        先"啪"地推开、再慢慢归位，比匀速淡出更像冲击波。
        """
        t0 = getattr(self, "_poke_t0", None)
        if t0 is None:
            return 0.0
        t = (_time.perf_counter() - t0) / self.POKE_DUR
        if t >= 1.0:
            return 0.0
        return (1.0 - t) ** 2

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
        ssn = season.season_of(day) if day is not None else None
        # 冬天的天光"走得更快"：同样 13 小时的刻度压到 10 小时，下班时天已经黑了
        span *= season.span_mul(ssn)
        h = theme.work_sky_hour(hour, start.hour + start.minute / 60.0, span, ssn)
        # 加班入夜：过了下班时间，天色继续往深夜多走一点。
        # 不用写字催人回家，让天自己暗下去——人对自己看着黑下来的天更敏感。
        if snap is not None and snap.state == engine.ST_OVERTIME:
            h += 0.8
        return h


    def _refresh_palette(self, now: datetime, force: bool = False) -> None:
        """按钟点刷新草皮 / 泥土色温，每小时只算一次。季节在这里一起叠上去。"""
        key = int(now.hour + now.minute / 60.0)
        if not force and key == self._pal_hour:
            return
        self._pal_hour = key
        # 构造时 _day 可能还没赋值，退回用 now 的日期（同一个真相）
        day = getattr(self, "_day", None) or now.date()
        self.pal = theme.palette_at(self._pal_base, self._visual_hour(now),
                                    season.season_of(day))

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
        self._check_total_milestone(now)
        self._check_sound_end()
        self._check_life(now)
        self._update_evening()
        # 启动后头一秒就把这台机器量一遍，别拖到草皮卷要动的那一刻才卡一下
        if getattr(self, "_auto_fps", None) is None:
            self._fps_mode()
        self._maybe_fetch_weather()
        self._sync_rain_timer()
        if self.tray is not None:
            self.tray.refresh(self.snap, self._evening_choice)
        self.update()

    # ---------------------------------------------------------------- 帧率
    _FPS_OF = {"high": 60, "mid": 30, "low": 15}

    def _fps_mode(self) -> str:
        """当前档位。auto 时按机器性能挑一次，之后一直沿用。"""
        mode = str(self.cfg.get("ui.fx.fps", "auto") or "auto")
        if mode in self._FPS_OF:
            return mode
        if getattr(self, "_auto_fps", None) is None:
            self._auto_fps = self._probe_fps()
        return self._auto_fps

    def _probe_fps(self) -> str:
        """离屏量几帧，按余量挑档。

        取最快的一帧而不是平均：第一帧要现建草地缓存，慢是正常的，不该为它降档。
        阈值留足一倍余量——窗口合成、系统负载还要从同一个核里分走时间。
        """
        dpr = getattr(self, "_dpr", 1.0) or 1.0
        w = max(1, int(round(self.width() * dpr)))
        h = max(1, int(round(self.height() * dpr)))
        if w < 16 or h < 16:
            return "high"                      # 尺寸还没定，别急着下结论
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        best = 99.0
        for _ in range(4):
            img.fill(Qt.GlobalColor.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
            t0 = _time.perf_counter()
            try:
                self.render_canvas(p, w, h)
            except Exception:
                p.end()
                return "high"
            p.end()
            best = min(best, _time.perf_counter() - t0)
        if best <= 0.009:
            return "high"
        if best <= 0.018:
            return "mid"
        return "low"

    def _sync_rain_timer(self) -> None:
        """只有"必须逐帧动"的东西在时才开的马达：雨、雪、落叶。

        以前按天气分了 83 / 125 / 150 / 200ms 四档，理由是"雨快雪慢"。
        但低帧率下慢速下落是一格一格跳的——看着像卡了，不像在飘。
        现在按档位统一 16 / 33 / 66ms：动作的快慢由每秒移动多少单位决定，
        不该由帧率决定。

        **云不算**：它已经慢到一个像素走三秒，每秒一次的例行重绘（_tick）就够了。
        晴天的云要是也挂在这条 60 帧马达上，等于为了三秒挪一格的东西一直烧一个核。
        收进托盘、雨雪落叶都没有，立刻停——不留一条空转的定时器。
        """
        today = weather.weather_of(self._day)
        fall_on = bool(self.cfg.get("ui.fx.fall",
                                    self.cfg.get("ui.fx.weather", True)))
        # 秋天晴天也要动：落叶是季节的常态，不是降水
        leaves = (fall_on and season.season_of(self._day) == season.AUTUMN
                  and today not in weather.PRECIP)
        want = (fall_on and (today in weather.PRECIP or leaves)
                and self.isVisible())
        if want:
            # auto 由 _fps_mode 现场拍板（见 _probe_fps），也可以手动锁档。
            mode = self._fps_mode()
            interval = {"low": 66, "mid": 33}.get(mode, 16)
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
        # 这一段只有 0.8 秒，但也要按档位走：低档机器上别为了它硬拉满
        self._anim_timer.setInterval({"low": 66, "mid": 33}.get(self._fps_mode(), 16))
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
        self._snd_seeded = False
        self._snd_day = None
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
        # 第一次启动把该问的一次问完（上下班、午休、真实天气），之后不再主动弹。
        if not self.cfg.get("schedule.setup_done", False):
            self.cfg.set("schedule.setup_done", True)
            self.cfg.set("schedule.ask_start_on_launch", False)
            self.cfg.set("schedule.remember_start", True)
            try:
                self.cfg.save()
            except Exception:
                pass
            self.open_settings_dialog()
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


    def _play_sound(self, name: str) -> None:
        """音效默认关：只有明确打开了 `ui.fx.sound` 才响。"""
        if bool(self.cfg.get("ui.fx.sound", False)):
            sound.play(name)

    def _check_sound_end(self) -> None:
        """下班那一声，一天只响一次。

        `_snd_seeded` 记的是"打开软件时是什么状态"：如果一开就已经过了下班点，
        那这一声属于过去，不补响；只有亲眼看着它跨过下班时刻，才响。
        """
        if not getattr(self, "_snd_seeded", False):
            self._snd_seeded = True
            self._snd_day = self._day if self.snap.state == engine.ST_OVERTIME else None
            return
        if self.snap.state != engine.ST_OVERTIME or getattr(self, "_snd_day", None) == self._day:
            return
        self._snd_day = self._day
        self._play_sound("end")

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
                self._play_sound("milestone")
                self._greet_text = quotes.milestone_text(prog, self._day)
                self._greet_until = _time.perf_counter() + 8.0
                break


    TOTAL_DAYS = (10, 50, 100, 365)
    TOTAL_HOURS = (100, 300, 500, 1000)

    def _check_total_milestone(self, now: datetime) -> None:
        """累计里程碑：记满 N 天 / 累计 N 小时，只响一次。

        和进度条里程碑不同，这个跟「今天」无关，只跟「一共」有关。
        按天节流；第一次运行就把已达成的记为已响——过去的事不该补庆祝一次。
        """
        if getattr(self, "_tot_day", None) == self._day:
            return
        self._tot_day = self._day
        if not self.cfg.get("ui.fx.milestone", True):
            return
        done = self.store.data.setdefault("milestones", [])
        days = self.store.worked_days()
        hours = self.store.worked_minutes(self.rule, self._live_overtime()) // 60

        if not getattr(self, "_tot_seeded", False):
            self._tot_seeded = True
            done.extend([f"d{n}" for n in self.TOTAL_DAYS if days >= n])
            done.extend([f"h{n}" for n in self.TOTAL_HOURS if hours >= n])
            self.store.save()
            return

        say = ""
        for n in self.TOTAL_DAYS:
            if days >= n and f"d{n}" not in done:
                done.append(f"d{n}")
                say = f"已经记了 {n} 天"
                break
        if not say:
            for n in self.TOTAL_HOURS:
                if hours >= n and f"h{n}" not in done:
                    done.append(f"h{n}")
                    say = f"累计 {n} 小时了"
                    break
        if not say:
            return
        self._start_fx("ms", 1.4)
        self._play_sound("milestone")
        self._greet_text = say
        self._greet_until = _time.perf_counter() + 8.0
        self.store.save()
        self.update()

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
