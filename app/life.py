"""一天里"路过"的几次小事件：蝴蝶、蜜蜂、小鸟。

为什么要有这个
--------------
这个挂件把"还有多久下班"做到了极致，但一天里除了里程碑和到点，中间八小时
什么都不会发生。人记住的从来不是渐变，是事件，所以每隔一两个小时让一点小
东西路过一次，比再加十个数字都管用。

为什么不是真随机
----------------
时间由日期算出来（同一天永远同一份表），所以重启、切档、换显示器，今天那只
蝴蝶还是在同一时刻飞过同一段花田。它像这片地自己的作息，而不是随机弹窗；
好处是也不用存任何状态。

对外只有 events_for()，返回"今天第几分钟会有东西路过"的列表。

只做鸟群一种。蝴蝶、蜜蜂、单只鸟、以及原版的猪牛羊鸡都在真机上试过：前几种是
2px 粒度下只剩十来个像素，读不出来；后几种要么小得看不清，要么放大到"像"的时候
已经很突兀、和这条 100 单位宽的带子不成比例。结论是这块画布上唯一还成立的
"活物"是**一群鸟**——单只认不出，队形和整体移动认得出来。
"""
from __future__ import annotations

import random
from datetime import date, time




def _clock_after(start_min: int, work_minutes: float,
                 lunch: tuple[int, int]) -> int:
    """从 start_min 起算，走过 work_minutes 个"有效分钟"后的钟点。

    和 engine.offwork_at 用同一套规则：落在午休里就跳过午休，不把午休算进工时。
    这里只需要正推，所以写成一次线性走位，比反解简单。
    """
    t = start_min
    left = float(work_minutes)
    ls, le = lunch
    while left > 1e-6:
        if ls <= t < le:                      # 正好卡在午休里：跳到结束
            t = le
            continue
        if t < ls and t + left > ls:          # 这一段会撞上午休：先走到午休口
            left -= ls - t
            t = le
            continue
        t += left
        left = 0.0
    return int(round(t)) % (24 * 60)


def events_for(day: date, start: time | None, rule) -> list[int]:
    """今天会有几次鸟群经过、各在第几分钟。

    完全由 (日期, 上班时间) 决定：同样的输入永远同样的输出。
    2~3 次，按有效工时均分，各自在自己那一段里随机偏一点，既不会挤在一起，
    也不会每次都掐着整点出现。
    """
    if start is None or not rule.is_workday(day):
        return []
    total = float(rule.target_minutes(start))
    if total < 60:
        return []

    rng = random.Random(day.toordinal() * 7919 + 31)
    n = 3 if rng.random() < 0.55 else 2
    lunch = (rule.lunch_start.hour * 60 + rule.lunch_start.minute,
             rule.lunch_end.hour * 60 + rule.lunch_end.minute)
    s0 = start.hour * 60 + start.minute

    out: list[int] = []
    for i in range(n):
        frac = (i + rng.uniform(0.28, 0.78)) / n
        out.append(_clock_after(s0, total * frac, lunch))
    return out
