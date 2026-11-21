"""今天的天气（纯逻辑，不依赖 Qt）。

规矩只有一条：**按日期播种**。同一天里刷新多少次都是同一种天气，跨天才换。
所以它不会在你看的时候突然下雨，也不会因为重启就换了个天。

分布：晴 62% / 阴 24% / 小雨 9.5% / 大雨 4.5%。

雨天刻意做稀——一周大概一天。天天淋雨就不叫氛围了，叫故障；
而正因为少，它出现的那天才会被注意到。大雨再稀一档，一个月见一两次，
所以它出现时值得一眼看出来（雨丝更长、更斜、更密，天压得更暗）。
"""
from __future__ import annotations

from datetime import date

CLEAR = "clear"
CLOUDY = "cloudy"
RAIN = "rain"
DOWNPOUR = "downpour"

LABELS = {CLEAR: "晴", CLOUDY: "阴", RAIN: "小雨", DOWNPOUR: "大雨"}

# 累计权重：0~619 晴，620~859 阴，860~954 小雨，955~999 大雨
_BOUNDS = ((620, CLEAR), (860, CLOUDY), (955, RAIN), (1000, DOWNPOUR))

# 会下雨的两种：画雨丝、停月亮、开小马达，都按这个判断
RAINY = (RAIN, DOWNPOUR)


def weather_of(day: date) -> str:
    """这一天的天气。乘法散列取模，同一天恒定，相邻两天互不相关。"""
    v = (day.toordinal() * 2654435761 + 17) % 1000
    for edge, name in _BOUNDS:
        if v < edge:
            return name
    return DOWNPOUR


def is_raining(day: date) -> bool:
    return weather_of(day) in RAINY


def is_heavy(day: date) -> bool:
    """大雨：雨丝更长更斜，天色更暗。"""
    return weather_of(day) == DOWNPOUR


def label_of(day: date) -> str:
    return LABELS[weather_of(day)]
