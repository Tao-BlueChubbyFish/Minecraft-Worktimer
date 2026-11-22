"""季节：按月份把一年切成四段，每段给一组色偏。

两个刻意的决定：

* **冬天只占 12 月和 1 月**。按自然月算冬天占四分之一，雪就不值钱了；
  缩到两个月，每年入冬才像个事件。
* **硬切，不做渐变**。3 月 1 号一觉醒来世界变绿——这个"变"本身就是事件；
  渐变要多写一倍代码，而且这个尺寸下未必看得出来。

色偏幅度压在 ±20% 以内，和 `palette._TIME_CURVE` 里"不破坏低饱和方块质感"的
原则一致：季节要能一眼看出，但不能变成另一种画风。
"""
from __future__ import annotations

from datetime import date

SPRING, SUMMER, AUTUMN, WINTER = "spring", "summer", "autumn", "winter"
ORDER = (SPRING, SUMMER, AUTUMN, WINTER)
LABELS = {SPRING: "春", SUMMER: "夏", AUTUMN: "秋", WINTER: "冬"}


def season_of(day: date) -> str:
    """2–4 春、5–7 夏、8–11 秋、12–1 冬。"""
    m = day.month
    if m in (12, 1):
        return WINTER
    if 2 <= m <= 4:
        return SPRING
    if 5 <= m <= 7:
        return SUMMER
    return AUTUMN


# (色相偏移°, 饱和度倍数, 明度倍数)
# 参考点：草色 #7da04b 的色相约 85°（黄绿偏绿），红0 / 黄60 / 绿120。
# 所以「往黄走」是**减**色相、不是加——第一版加到 +20 结果还是绿的。
TINTS: dict[str, tuple[float, float, float]] = {
    SPRING: (-4.0, 0.98, 1.08),    # 嫩黄绿、略亮
    SUMMER: (10.0, 1.15, 1.00),    # 正绿、最浓
    AUTUMN: (-22.0, 0.93, 1.05),   # 转到黄，但别真的枯掉：饱和度留 0.93
    WINTER: (22.0, 0.62, 0.86),    # 冷青、压暗：不抽干（会变黑白屏），也要够冷够沉
}


def tint(season: str) -> tuple[float, float, float]:
    return TINTS.get(season, (0.0, 1.0, 1.0))


def is_winter(season: str) -> bool:
    return season == WINTER


# 天色跨度倍数：把「上班 → 入夜」这段拉长或压短。
# 这是"天黑得早晚"真正的开关——只挪锚点不够，因为工作时段跨度固定 13 小时，
# 18:00 只走到 69% 的位置，天色永远停在大白天。
# 冬天压到 0.8，同一时刻走得更远，下班前后天就黑了；夏天拉到 1.15，反着来。
SPAN_MUL: dict[str, float] = {
    SPRING: 1.00,
    SUMMER: 1.15,
    AUTUMN: 0.98,
    WINTER: 0.80,
}


def span_mul(season: str | None) -> float:
    return SPAN_MUL.get(season or "", 1.0)
