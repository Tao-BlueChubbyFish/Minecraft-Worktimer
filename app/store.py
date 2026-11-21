"""数据持久化：data.json 保存每日上班时间、加班记录、窗口坐标。

* 当日加班随零点结算进累计，累计写入 cumulative_overtime_minutes 永不自动清零。
* 只有「重置当日计时」会清掉当天；「清空累计加班」需要手动在菜单里确认。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from . import engine, util

KEEP_DAYS = 90


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or util.data_path()
        self.data: dict = {}
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        raw = util.read_json(self.path)
        self.data = {
            "version": 1,
            "cumulative_overtime_minutes": int(raw.get("cumulative_overtime_minutes", 0) or 0),
            "ledger": dict(raw.get("ledger") or {}),
            "schedule": dict(raw.get("schedule") or {}),
            "last_settled_date": raw.get("last_settled_date"),
            "last_seen": raw.get("last_seen"),
            "today_overtime": int(raw.get("today_overtime", 0) or 0),
            "today_date": raw.get("today_date"),
            "window": raw.get("window") or {},
            "first_run": raw.get("first_run") or date.today().isoformat(),
            "max_single_day": int(raw.get("max_single_day", 0) or 0),
            "days_counted": int(raw.get("days_counted", 0) or 0),
            "days_archived": int(raw.get("days_archived", 0) or 0),
            "evening": dict(raw.get("evening") or {}),
            "notes": dict(raw.get("notes") or {}),
            "milestones": list(raw.get("milestones") or []),
        }

    def save(self) -> None:
        try:
            util.write_json(self.path, self.data)
        except Exception:
            pass

    # ------------------------------------------------------------------
    @staticmethod
    def _key(d: date) -> str:
        return d.isoformat()

    def work_start(self, d: date) -> time | None:
        raw = self.data["schedule"].get(self._key(d))
        if not raw:
            return None
        return engine.parse_hhmm(raw, time(9, 0))

    def set_work_start(self, d: date, t: time | None) -> None:
        k = self._key(d)
        if t is None:
            self.data["schedule"].pop(k, None)
        else:
            self.data["schedule"][k] = engine.fmt_hhmm(t)
        self._prune()

    def has_any_start(self) -> bool:
        return bool(self.data["schedule"])

    # ------------------------------------------------------------------
    def note_today(self, day: date, overtime_minutes: int, now: datetime) -> None:
        """记录当天加班快照 + 最后在线时间（供跨天/关机后结算）。"""
        self.data["today_date"] = self._key(day)
        self.data["today_overtime"] = int(overtime_minutes)
        self.data["last_seen"] = now.isoformat(timespec="seconds")

    def settle(self, rule: engine.Rule, today: date) -> bool:
        """把今天之前的加班结算进累计。返回是否发生了结算。

        只在「确有记录」时才结算：优先用上次运行留下的当日快照
        （today_overtime，最贴近真实），其次用 last_seen 精确推算。
        没跑过的那几天不作数，不会凭空给加班。
        """
        changed = False
        seen_raw = self.data.get("last_seen")
        try:
            seen_dt = datetime.fromisoformat(seen_raw) if seen_raw else None
        except ValueError:
            seen_dt = None

        # 1) 上次运行结束时记下的当日加班快照
        cached_date = self.data.get("today_date")
        cached_ot = int(self.data.get("today_overtime") or 0)
        if cached_date and cached_date < today.isoformat() and cached_ot > 0:
            try:
                d = date.fromisoformat(cached_date)
                self._add_overtime(d, cached_ot)
                changed = True
            except ValueError:
                pass

        # 2) last_seen 落在更早的一天，且那天还没入账 → 用最后在线时刻精确算
        if seen_dt is not None and seen_dt.date() < today:
            d = seen_dt.date()
            if d.isoformat() not in self.data["ledger"]:
                st = self.work_start(d)
                ot = engine.day_overtime(d, st, seen_dt, rule)
                if ot > 0:
                    self._add_overtime(d, ot)
                    changed = True

        self.data["today_overtime"] = 0
        self.data["today_date"] = today.isoformat()
        if self.data.get("last_settled_date") != today.isoformat():
            self.data["last_settled_date"] = today.isoformat()
            changed = True
        return changed

    def _add_overtime(self, d: date, minutes: int) -> None:
        if minutes <= 0:
            return
        k = self._key(d)
        if k in self.data["ledger"]:
            return
        self.data["ledger"][k] = int(minutes)
        self.data["cumulative_overtime_minutes"] += int(minutes)
        self.data["days_counted"] = int(self.data.get("days_counted", 0)) + 1
        self.data["max_single_day"] = max(int(self.data.get("max_single_day", 0)), int(minutes))

    # ------------------------------------------------------------------
    def cumulative_minutes(self, today: date, live_today_overtime: int) -> int:
        """累计加班 = 已结算历史 + 今日实时（今天还没结算，避免重复计算）。"""
        base = int(self.data.get("cumulative_overtime_minutes", 0))
        return max(0, base + max(0, live_today_overtime))

    def reset_today(self, today: date) -> None:
        k = self._key(today)
        val = self.data["ledger"].pop(k, None)
        if val:
            self.data["cumulative_overtime_minutes"] = max(
                0, int(self.data["cumulative_overtime_minutes"]) - int(val)
            )
            self.data["days_counted"] = max(0, int(self.data.get("days_counted", 1)) - 1)
        self.data["schedule"].pop(k, None)
        self.data["evening"].pop(k, None)
        self.data["today_overtime"] = 0
        self.data["today_date"] = k
        self.save()

    def reset_cumulative(self) -> None:
        self.data["cumulative_overtime_minutes"] = 0
        self.data["ledger"] = {}
        self.data["max_single_day"] = 0
        self.data["days_counted"] = 0
        self.save()

    def recent_days(self, limit: int = 5) -> list[tuple[str, int]]:
        items = sorted(self.data["ledger"].items(), reverse=True)
        return [(k, int(v)) for k, v in items[:limit]]

    # ------------------------------------------------------------------
    # 累计与周视图（v1.1）：只读，不改任何落盘结构。
    # 累计工时按「标准在岗时长 × 登记天数 + 累计加班」推算：
    # 不加班的日子不写 ledger，没法逐日累加，只能这样算。
    def worked_days(self) -> int:
        """累计上班天数 = 保留期内的登记天数 + 已被修剪归档的天数。"""
        return len(self.data["schedule"]) + int(self.data.get("days_archived", 0) or 0)

    def worked_minutes(self, rule: engine.Rule, live_today_overtime: int = 0) -> int:
        """累计有效工时（分钟）。"""
        base = int(round(rule.onsite_hours * 60))
        return (
            self.worked_days() * base
            + int(self.data.get("cumulative_overtime_minutes", 0) or 0)
            + max(0, int(live_today_overtime))
        )

    def day_minutes(
        self, d: date, rule: engine.Rule, live_overtime: int = 0
    ) -> int | None:
        """某天的有效工时。那天没登记上班就返回 None（周视图里留空）。"""
        if self.work_start(d) is None:
            return None
        base = int(round(rule.onsite_hours * 60))
        ot = int(self.data["ledger"].get(self._key(d), 0) or 0) + max(0, int(live_overtime))
        return base + ot

    def week_minutes(
        self, today: date, rule: engine.Rule, live_today_overtime: int = 0
    ) -> list[tuple[date, int | None]]:
        """本周七天的有效工时，周一打头。"""
        monday = today - timedelta(days=today.weekday())
        out: list[tuple[date, int | None]] = []
        for i in range(7):
            d = monday + timedelta(days=i)
            live = live_today_overtime if d == today else 0
            out.append((d, self.day_minutes(d, rule, live)))
        return out

    def week_total(self, monday: date, rule: engine.Rule, today: date,
                   live_today_overtime: int = 0) -> int:
        """某一周的合计（周一起算七天）。"""
        total = 0
        for i in range(7):
            d = monday + timedelta(days=i)
            v = self.day_minutes(d, rule, live_today_overtime if d == today else 0)
            if v:
                total += v
        return total

    def typical_start(self, ref: date, days: int = 30) -> time | None:
        """最近 N 天到岗时间的中间值——「我通常几点到」。

        用中位数不用平均数：偶发的 06:00 或 10:30 会把平均值拽走，中位数不会。
        样本少于 5 天不叫"常说"——刚装上的头几天说「常在 09:00 到岗」是假话。
        """
        vals: list[int] = []
        for i in range(days):
            t = self.work_start(ref - timedelta(days=i))
            if t is not None:
                vals.append(t.hour * 60 + t.minute)
        if len(vals) < 5:
            return None
        vals.sort()
        mid = vals[len(vals) // 2]
        return time(mid // 60, mid % 60)

    # ------------------------------------------------------------------
    def note(self, d: date) -> str:
        """当天随手记的一句话。"""
        return str((self.data.get("notes") or {}).get(self._key(d)) or "")

    def set_note(self, d: date, text: str) -> None:
        notes = self.data.setdefault("notes", {})
        k = self._key(d)
        text = (text or "").strip()[:60]
        if text:
            notes[k] = text
        else:
            notes.pop(k, None)
        self._prune()

    # ------------------------------------------------------------------
    def evening_choice(self, d: date) -> str | None:
        """今天下班时选过什么：'home'（回家）/ 'overtime'（继续加班）/ None。"""
        rec = self.data["evening"].get(self._key(d)) or {}
        choice = rec.get("choice")
        return choice if choice in ("home", "overtime") else None

    def set_evening_choice(self, d: date, choice: str) -> None:
        self.data["evening"][self._key(d)] = {
            "choice": choice,
            "at": datetime.now().isoformat(timespec="minutes"),
        }
        self._prune()

    # ------------------------------------------------------------------
    def window(self) -> dict:
        return dict(self.data.get("window") or {})

    def set_window(self, x: int, y: int) -> None:
        self.data["window"] = {"x": int(x), "y": int(y)}

    def _prune(self) -> None:
        for bucket in ("schedule", "ledger", "evening", "notes"):
            keys = sorted(self.data[bucket].keys())
            for k in keys[:-KEEP_DAYS]:
                if self.data[bucket].pop(k, None) is None:
                    continue
                if bucket == "schedule":
                    # 修剪掉的登记日仍算在累计里，否则「用了多少天」会随时间倒退
                    self.data["days_archived"] = int(self.data.get("days_archived", 0) or 0) + 1
