"""文字内容：标题、大数字、两排小字、每日一句、问候语，以及「加班了多久」。"""
from __future__ import annotations

import time as _time
from datetime import datetime, time
from .. import engine, quotes
from .consts import TIERS, TIER_ORDER, WEEK_CN  # noqa: F401


class ContentMixin:

    def _content(self) -> dict:
        """在基础文案上补一句顶部问候（F3），其余逻辑不变。"""
        c = self._content_base()
        c["title"] = self._greeting()
        c["foot_right_gold"] = self._fx_kind == "ms"
        return c


    def _content_base(self) -> dict:
        snap = self.snap
        pal = self.pal
        S = self.S
        k = max(2, S * 2)
        cjk_u = 12
        st = snap.state

        if st == engine.ST_WEEKEND:
            wd = WEEK_CN[snap.now.weekday()] if snap.now else ""
            return {
                "label": "今天不用上班",
                "value": [("c", "休息日", 14)],
                "foot_left": f"{wd} · 周末愉快",
                "foot_right": "",
                "progress": 0.0,
                "value_color": pal["text"],
            }

        if st == engine.ST_UNSET:
            return {
                "label": "还没登记今天的上班时间",
                "label_short": "还没设置上班时间",
                "value": [("c", "未设置", 14)],
                "foot_left": "点右上角按钮 或 右键菜单设置",
                "foot_right": "",
                "progress": 0.0,
                "value_color": pal["warn"],
            }

        if st == engine.ST_LUNCH:
            left = f"午休 {engine.fmt_hhmm(self.rule.lunch_start)}-{engine.fmt_hhmm(self.rule.lunch_end)}"
            return {
                "label": "先把饭吃了",
                "value": [("c", "休息中", 14)],
                "foot_left": f"{left} · 还有 {engine.humanize(snap.lunch_left_minutes)}",
                "foot_right": f"{int(round(snap.progress * 100))}%",
                "progress": snap.progress,
                "paused": True,
                "label_color": pal["warn"],
                "value_color": pal["warn"],
            }

        if st == engine.ST_OVERTIME:
            off = engine.fmt_hhmm(self.offwork_time())
            choice = self._evening_choice

            # 庆祝那 5 秒：数字行让位给木牌，别和祝贺语叠在一起
            if choice == "home" and self._fx_kind == "home":
                return {"label": "", "label_short": "收工", "value": [],
                        "foot_left": f"下班 {off}", "foot_right": "",
                        "progress": 1.0}

            # 选了「回家」：不再计加班，改成一句收尾——今天干了多久、几点下的班
            if choice == "home":
                total = int(snap.worked_minutes or snap.target_minutes)
                h, m = divmod(total, 60)
                value = []
                if h:
                    value += [("b", f"{h:02d}", k), ("g", 5), ("c", "小时", cjk_u), ("g", 4)]
                value += [("b", f"{m:02d}", k), ("g", 5), ("c", "分钟", cjk_u)]
                return {
                    "label": "今天干了",
                    "value": value,
                    "foot_left": f"下班 {off} · 明天见",
                    "foot_right": "OK",
                    "progress": 1.0,
                    "label_color": pal["accent"],
                    "value_color": pal["text"],
                }

            # 还没决定：数字行让位给木牌（牌上写字、可点）
            if choice is None:
                return {
                    "label": "",
                    "label_short": "到点了",
                    "value": [],
                    "foot_left": f"下班 {off}",
                    "foot_right": "OT",
                    "progress": 1.0,
                }

            ot = snap.overtime_minutes
            h, m = divmod(ot, 60)
            value = []
            if h:
                value += [("b", f"{h:02d}", k), ("g", 5), ("c", "小时", cjk_u), ("g", 4)]
            value += [("b", f"{m:02d}", k), ("g", 5), ("c", "分钟", cjk_u)]
            return {
                "label": "加班中",
                "value": value,
                "foot_left": f"下班 {off} · 早点回家",
                "foot_right": "OT",
                "progress": 1.0,
                "label_color": pal["warn"],
                "value_color": pal["warn"],
            }

        if st == engine.ST_BEFORE:
            m = snap.to_work_minutes
            h, mm = divmod(m, 60)
            value = []
            if h:
                value += [("b", f"{h:02d}", k), ("g", 5), ("c", "小时", cjk_u), ("g", 4)]
            value += [("b", f"{mm:02d}", k), ("g", 5), ("c", "分钟", cjk_u)]
            return {
                "label": "距离上班",
                "value": value,
                "foot_left": f"上班 {engine.fmt_hhmm(snap.work_start)} · "
                             f"下班 {engine.fmt_hhmm(self.offwork_time())}",
                "foot_right": f"{int(round(snap.progress * 100))}%",
                "progress": snap.progress,
                "value_color": pal["text_dim"],
            }

        # 正常计时
        m = snap.remaining_minutes
        h, mm = divmod(m, 60)
        value = []
        if h:
            value += [("b", f"{h:02d}", k), ("g", 5), ("c", "小时", cjk_u), ("g", 4)]
        value += [("b", f"{mm:02d}", k), ("g", 5), ("c", "分钟", cjk_u)]
        return {
            "label": "距离下班",
            "value": value,
            "foot_left": f"上班 {engine.fmt_hhmm(snap.work_start)} · "
                         f"下班 {engine.fmt_hhmm(self.offwork_time())}",
            "foot_right": f"{int(round(snap.progress * 100))}%",
            "progress": snap.progress,
            "value_color": pal["text"],
        }


    def _live_overtime(self) -> int:
        """实时加班分钟：已经选过「回家」就不该再往累计里记。"""
        if self.snap.state == engine.ST_OVERTIME and self._evening_choice == "home":
            return 0
        return int(self.snap.overtime_minutes)


    def _greeting(self) -> str:
        if not self.cfg.get("ui.fx.greeting", True):
            return "工作计时"
        if self._greet_text and _time.perf_counter() < self._greet_until:
            return self._greet_text
        return quotes.greeting(self.snap.state, self.snap.now or datetime.now(),
                               self.rule.lunch_start, self._evening_choice)


    def _quote_text(self) -> str:
        """当天那句：同一天恒定，跨天自动换；关掉 ui.quote 就整行不画。"""
        if not self.cfg.get("ui.quote", True):
            return ""
        salt = int(getattr(self, "_quote_salt", 0))
        if self._quote_day == (self._day, salt):
            return self._quote
        shuffle = bool(self.cfg.get("ui.quote_shuffle", True))
        self._quote = quotes.for_day(self._day, self.cfg.get("ui.quotes"), shuffle, salt)
        self._quote_day = (self._day, salt)
        return self._quote


    def offwork_time(self) -> time | None:
        if self.snap and self.snap.offwork:
            return self.snap.offwork.time()
        start = self.store.work_start(self._day)
        if start is None:
            return None
        return engine.offwork_at(self._day, start, self.rule).time()

    # ---------------------------------------------------------------- 命中区
