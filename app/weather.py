"""今天的天气（纯逻辑，不依赖 Qt）。

规矩只有一条：**按日期播种**。同一天里刷新多少次都是同一种天气，跨天才换。
所以它不会在你看的时候突然下雨，也不会因为重启就换了个天。

分布：晴 62% / 阴 24% / 小雨 9.5% / 大雨 4.5%。

冬季换一套：晴 45% / 阴 20% / 小雪 25% / 大雪 10%——雪是冬天里"雨"的样子，
不是另开的天气档，所以夏天永远不会下雪。

雨天刻意做稀——一周大概一天。天天淋雨就不叫氛围了，叫故障；
而正因为少，它出现的那天才会被注意到。大雨再稀一档，一个月见一两次，
所以它出现时值得一眼看出来（雨丝更长、更斜、更密，天压得更暗）。
"""
from __future__ import annotations

from datetime import date

from . import season

CLEAR = "clear"
CLOUDY = "cloudy"
RAIN = "rain"
DOWNPOUR = "downpour"
SNOW = "snow"
BLIZZARD = "blizzard"

LABELS = {CLEAR: "晴", CLOUDY: "阴", RAIN: "小雨", DOWNPOUR: "大雨",
          SNOW: "小雪", BLIZZARD: "大雪"}

# 累计权重：0~619 晴，620~859 阴，860~954 小雨，955~999 大雨
_BOUNDS = ((620, CLEAR), (860, CLOUDY), (955, RAIN), (1000, DOWNPOUR))

# 冬天换一套分布：晴天压到 45%，剩下的给阴和两档雪。
# 不这么做的话按原比例只有 13% 的日子下雪，一周一次——那不叫冬天。
_WINTER_BOUNDS = ((450, CLEAR), (650, CLOUDY), (900, SNOW), (1000, BLIZZARD))

# 会下雨的两种：画雨丝、停月亮、开小马达，都按这个判断
RAINY = (RAIN, DOWNPOUR)
# 会下雪的两种：同上，只是画法不同
SNOWY = (SNOW, BLIZZARD)
# 有降水的四种：天色压暗、不挂月亮、定时器要转
PRECIP = RAINY + SNOWY


# 真实天气取到之后，只覆盖今天这一天；其余日子照旧按日期播种。
# 用模块级变量而不是加参数，是因为 weather_of(day) 被十几处调用，
# 没必要为了一个可选功能把所有调用点都改一遍。
_overrides: dict[str, str] = {}
_temp: float | None = None


def set_real(day: date, code: str, temp: float | None = None) -> None:
    """把某一天换成真实天气。code 必须是本模块的六种之一。"""
    global _temp
    _overrides.clear()
    _overrides[day.isoformat()] = code
    _temp = temp


def clear_real() -> None:
    """关掉真实天气，回到按日期播种。"""
    global _temp
    _overrides.clear()
    _temp = None


def is_real(day: date) -> bool:
    return day.isoformat() in _overrides


def temperature() -> float | None:
    """真实气温（℃）。没开真实天气时是 None。"""
    return _temp


def weather_of(day: date) -> str:
    """这一天的天气。乘法散列取模，同一天恒定，相邻两天互不相关。

    冬季走另一套权重，把雨换成雪——雪不是外加的天气，是冬天里"雨"的样子。
    """
    hit = _overrides.get(day.isoformat())
    if hit:
        return hit
    v = (day.toordinal() * 2654435761 + 17) % 1000
    bounds = _WINTER_BOUNDS if season.season_of(day) == season.WINTER else _BOUNDS
    for edge, name in bounds:
        if v < edge:
            return name
    return bounds[-1][1]


def is_raining(day: date) -> bool:
    return weather_of(day) in RAINY


def is_snowing(day: date) -> bool:
    return weather_of(day) in SNOWY


def is_heavy(day: date) -> bool:
    """大雨 / 大雪：雨丝更长更斜、雪更大更密，天色更暗。"""
    return weather_of(day) in (DOWNPOUR, BLIZZARD)


def label_of(day: date) -> str:
    return LABELS[weather_of(day)]
