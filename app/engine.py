"""工时计算核心（纯逻辑，不依赖 Qt，方便单元测试）。

规则
----
* 下班时刻由用户**直接指定**（rule.offwork，例如 18:00）。这是最贴近现实的一条：
  公司几点下班是定死的，不是"上班时间加八小时"算出来的。
* 没指定下班时刻时，退回旧口径：下班 = 上班 + (onsite_hours − 午休)。
  首次启动就是这条路径——按 9 小时在岗、扣 1 小时午休，得到一个默认下班时间。
* 有效工时目标 = 上班→下班 的跨度 − 落在午休里的那一段。所以午休改长了，
  有效工时自动变短，进度条不会因为改了设置就跳。
* 下班时刻早于上班时刻（跨天或笔误）时，自动退回按在岗时长推算，不会算出负数。
* 周六周日直接休息，不计时；不做节假日识别。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

# 状态
ST_WEEKEND = "weekend"      # 休息日
ST_UNSET = "unset"          # 今天还没设置上班时间
ST_BEFORE = "before"        # 还没到上班时间
ST_WORKING = "working"      # 正常计时
ST_LUNCH = "lunch"          # 午休中（暂停）
ST_OVERTIME = "overtime"    # 已过下班时间，加班中


def parse_hhmm(text: str, fallback: time) -> time:
    try:
        h, m = str(text).strip().split(":")
        return time(int(h) % 24, int(m) % 60)
    except Exception:
        return fallback


def fmt_hhmm(t: time | None) -> str:
    return "--:--" if t is None else f"{t.hour:02d}:{t.minute:02d}"


def overlap_minutes(a1: datetime, a2: datetime, b1: datetime, b2: datetime) -> float:
    lo = max(a1, b1)
    hi = min(a2, b2)
    return max(0.0, (hi - lo).total_seconds() / 60.0)


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


@dataclass
class Rule:
    onsite_hours: float = 9.0
    offwork: time | None = None     # 直接指定的下班时刻；None = 按在岗时长推算
    lunch_start: time = time(12, 0)
    lunch_end: time = time(13, 0)
    workdays: tuple = (1, 2, 3, 4, 5)

    @property
    def lunch_minutes(self) -> float:
        d = datetime.combine(date(2000, 1, 1), self.lunch_end) - datetime.combine(date(2000, 1, 1), self.lunch_start)
        return max(0.0, d.total_seconds() / 60.0)

    def lunch_overlap_minutes(self, begin: time, end: time) -> float:
        """[begin, end) 里撞上午休的那一段。只处理同一天，跨天由调用方兜底。"""
        lo = max(_minutes(begin), _minutes(self.lunch_start))
        hi = min(_minutes(end), _minutes(self.lunch_end))
        return max(0.0, float(hi - lo))

    def target_minutes(self, start: time) -> float:
        """有效工时目标（已扣午休）。

        指定了下班时刻就按它反推——这一天从几点干到几点是明摆着的；
        没指定（或时刻不成立）才退回"在岗时长 − 午休"。
        """
        if self.offwork is not None:
            span = _minutes(self.offwork) - _minutes(start)
            if span >= 60:
                return max(30.0, span - self.lunch_overlap_minutes(start, self.offwork))
        return max(60.0, self.onsite_hours * 60.0 - self.lunch_minutes)

    def is_workday(self, d: date) -> bool:
        return d.isoweekday() in self.workdays


def shift_time(t: time, minutes: float) -> time:
    total = (t.hour * 60 + t.minute + int(round(minutes))) % (24 * 60)
    return time(total // 60, total % 60)


def build_rule(cfg) -> Rule:
    sc = cfg.get("schedule", {})
    lunch_start = parse_hhmm(sc.get("lunch_start", "12:00"), time(12, 0))
    # 午休时长优先（设置界面写的是"开始 + 时长"），没有时长才退回旧的 lunch_end
    if sc.get("lunch_minutes") is not None:
        lunch_end = shift_time(lunch_start, float(sc.get("lunch_minutes", 60) or 0))
    else:
        lunch_end = parse_hhmm(sc.get("lunch_end", "13:00"), time(13, 0))
    # 下班时刻：设置里选过就用它；空字符串表示"还没选过"，交给在岗时长推算
    offwork = None
    text = str(sc.get("offwork_time") or "").strip()
    if ":" in text:
        hh, _, mm = text.partition(":")
        try:
            offwork = time(int(hh) % 24, int(mm) % 60)
        except ValueError:
            offwork = None
    return Rule(
        onsite_hours=float(sc.get("onsite_hours", 9.0)),
        offwork=offwork,
        lunch_start=lunch_start,
        lunch_end=lunch_end,
        workdays=tuple(sc.get("workdays", [1, 2, 3, 4, 5])),
    )


def _lunch_window(day: date, rule: Rule) -> tuple[datetime, datetime]:
    return (
        datetime.combine(day, rule.lunch_start),
        datetime.combine(day, rule.lunch_end),
    )


def offwork_at(day: date, start: time, rule: Rule) -> datetime:
    """下班时刻。直接指定的优先，否则按有效工时往后推（自动跳过午休）。"""
    begin = datetime.combine(day, start)
    if rule.offwork is not None:
        end = datetime.combine(day, rule.offwork)
        if end > begin:          # 下班早于上班 = 跨天或填错了，退回按工时推
            return end
    target = timedelta(minutes=rule.target_minutes(start))
    l1, l2 = _lunch_window(day, rule)
    end = begin + target
    for _ in range(6):  # 不动点迭代，通常 1~2 轮收敛
        paused = overlap_minutes(begin, end, l1, l2)
        new_end = begin + target + timedelta(minutes=paused)
        if abs((new_end - end).total_seconds()) < 30:
            end = new_end
            break
        end = new_end
    return end


def suggested_offwork(start: time, rule: Rule) -> time:
    """按"在岗时长 − 午休"推一个下班时刻。

    只用来给设置界面垫一个初始值：用户还没选过下班时间时，按 9 小时在岗
    （扣午休）先算一个出来，他直接改那个数字就行。
    """
    naive = Rule(onsite_hours=rule.onsite_hours, offwork=None,
                 lunch_start=rule.lunch_start, lunch_end=rule.lunch_end,
                 workdays=rule.workdays)
    return offwork_at(date.today(), start, naive).time()


def worked_minutes(start_dt: datetime, until: datetime, rule: Rule) -> int:
    """已计有效工时（不含午休）。"""
    if until <= start_dt:
        return 0
    total = (until - start_dt).total_seconds() / 60.0
    l1, l2 = _lunch_window(start_dt.date(), rule)
    total -= overlap_minutes(start_dt, until, l1, l2)
    return max(0, int(total))


@dataclass
class Snapshot:
    state: str = ST_UNSET
    now: datetime | None = None
    work_start: time | None = None
    offwork: datetime | None = None
    remaining_minutes: int = 0      # 距离下班
    overtime_minutes: int = 0       # 今日已加班
    worked_minutes: int = 0         # 已计有效工时
    target_minutes: int = 480
    progress: float = 0.0
    to_work_minutes: int = 0        # 距离上班（before 状态用）
    lunch_left_minutes: int = 0     # 午休还剩多久

    @property
    def is_workday_state(self) -> bool:
        return self.state not in (ST_WEEKEND,)


def snapshot(now: datetime, day_start: time | None, rule: Rule) -> Snapshot:
    day = now.date()
    s = Snapshot(now=now, work_start=day_start)

    if not rule.is_workday(day):
        s.state = ST_WEEKEND
        return s

    if day_start is None:
        s.state = ST_UNSET
        return s

    target = rule.target_minutes(day_start)
    s.target_minutes = int(target)
    start_dt = datetime.combine(day, day_start)
    off = offwork_at(day, day_start, rule)
    s.offwork = off

    if now >= off:
        s.state = ST_OVERTIME
        s.worked_minutes = int(target)
        s.progress = 1.0
        s.overtime_minutes = max(0, int((now - off).total_seconds() // 60))
        s.remaining_minutes = 0
        return s

    s.worked_minutes = worked_minutes(start_dt, now, rule)
    s.progress = min(1.0, s.worked_minutes / target) if target else 0.0
    s.remaining_minutes = max(0, int((off - now).total_seconds() // 60))

    l1, l2 = _lunch_window(day, rule)
    in_lunch = l1 <= now < l2
    if now < start_dt:
        s.state = ST_BEFORE
        s.to_work_minutes = max(0, int((start_dt - now).total_seconds() // 60))
        s.worked_minutes = 0
        s.progress = 0.0
    elif in_lunch:
        s.state = ST_LUNCH
        s.lunch_left_minutes = max(0, int((l2 - now).total_seconds() // 60))
        # 午休开始时已工作的时间（进度条冻结在这里）
        s.worked_minutes = worked_minutes(start_dt, l1, rule) if start_dt < l1 else 0
        s.progress = min(1.0, s.worked_minutes / target)
    else:
        s.state = ST_WORKING
    return s


def day_overtime(day: date, start: time | None, until: datetime, rule: Rule) -> int:
    """某一天的加班分钟数（用于跨天结算与历史记录）。"""
    if start is None or not rule.is_workday(day):
        return 0
    off = offwork_at(day, start, rule)
    if until <= off:
        return 0
    day_end = datetime.combine(day, time(23, 59, 59))
    return max(0, int((min(until, day_end) - off).total_seconds() // 60))


def humanize(minutes: int) -> str:
    minutes = max(0, int(minutes))
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} 小时 {m} 分钟"
    if h:
        return f"{h} 小时"
    return f"{m} 分钟"
