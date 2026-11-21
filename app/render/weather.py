"""天气的画法：阴天压色、雨天压色 + 雨丝。

两条设计约束，都是从之前踩过的坑里来的：

1. **只做成片的重复，不做单个像素点。** 蝴蝶、蜜蜂、萤火虫都试过，在「1 单位 = 2px」
   这个尺寸上全是噪点。雨是竖线、而且成片，属于「重复成片」那一类，才读得出来。
2. **不加整体泛白 / 闪光。** 收工庆祝曾经整窗提亮一帧，被当成闪屏。天气也一样，
   只用低透明度的冷色压一层，让画面"暗下来、脏一点"，不制造明暗跳变。
"""
from __future__ import annotations

import random

from PySide6.QtGui import QColor, QPainter

from .common import fill

# 压色：天比地压得重一点，雨天的天空本来就比草地更灰
_SKY_TINT = {
    "cloudy": QColor(108, 120, 132, 26),
    "rain": QColor(46, 62, 80, 52),
    "downpour": QColor(32, 44, 60, 76),
}
_GROUND_TINT = {
    "cloudy": QColor(96, 104, 112, 20),
    "rain": QColor(22, 32, 42, 72),
    "downpour": QColor(12, 18, 26, 98),
}

_HEAD = QColor(216, 234, 246, 205)      # 雨丝的下端（头），亮一点
_TAIL = QColor(176, 200, 218, 120)      # 上端（尾），淡一点

_DENSITY = 0.20         # 每一列有多少条雨丝（0.14 ≈ 每 7 列一条）
_SPEED = (7.0, 11.0)    # 单位/秒：约 2~3 秒落完整条
_LEN = (2, 3, 3)        # 雨丝长度（单位）

# 大雨：雨丝长、速度快、密度高，而且是斜的（右上往左下，每落 2 单位左移 1 单位）。
# 小雨那套常量一个都不动——小雨是"下着"，大雨是"浇下来"，两者要一眼分得开。
_DP_HEAD = QColor(234, 246, 255, 225)     # #eaf6ff 的雨丝头（最下端）
_DP_TAIL = QColor(207, 224, 234, 150)     # #cfe0ea 的雨丝尾（上端，淡一点，拉出斜向的尾巴）
_DP_DENSITY = 0.28
_DP_SPEED = (14.0, 20.0)
_DP_LEN = (6, 7, 8, 9)


def draw_tint(p: QPainter, ix: int, iy: int, iw: int,
              sky_h: int, ground_h: int, weather: str) -> None:
    """给天空和地面各压一层冷色。晴天什么都不画。"""
    sky = _SKY_TINT.get(weather)
    if sky is not None:
        fill(p, ix, iy, iw, sky_h, sky)
    ground = _GROUND_TINT.get(weather)
    if ground is not None:
        fill(p, ix, iy + sky_h, iw, ground_h, ground)


def draw_rain(p: QPainter, ix: int, iy: int, iw: int, ih: int, s: int,
              secs: float, seed_day: int) -> None:
    """雨丝：一格格往下落。

    位置全部由（日期 + 秒数）算出来，不存状态——刷新、重启、切档都还是同一场雨，
    只是往下走了几格。
    """
    cols = max(1, iw // s)
    rows = max(1, ih // s)
    count = max(6, int(cols * _DENSITY))
    rng = random.Random((seed_day * 149 + 41) & 0x7FFFFFFF)

    span = rows + 5
    for _ in range(count):
        x = rng.randrange(cols)
        speed = rng.uniform(*_SPEED)
        offset = rng.uniform(0.0, span)
        length = rng.choice(_LEN)
        y = int((offset + secs * speed) % span) - 5
        for k in range(length):
            yy = y + k
            if 0 <= yy < rows:
                col = _HEAD if k == length - 1 else _TAIL
                fill(p, ix + x * s, iy + yy * s, s, s, col)


def draw_downpour(p: QPainter, ix: int, iy: int, iw: int, ih: int, s: int,
                  secs: float, seed_day: int) -> None:
    """大雨：斜雨丝，右上往左下浇下来。

    和小雨的区别全在形状上，不在"更多的小雨"上：
    * 长：一根 6~9 单元，是成段的线，不是几个点；
    * 斜：每下落 2 单元左移 1 单元，方向一致，整片看上去是同一个风向；
    * 快：14~20 单元/秒，约 1 秒就穿过天空。

    位置同样只由（日期 + 秒数）算出，不存状态——重启、切档都还是同一场雨。
    """
    cols = max(1, iw // s)
    rows = max(1, ih // s)
    count = max(8, int(cols * _DP_DENSITY))
    rng = random.Random((seed_day * 233 + 97) & 0x7FFFFFFF)

    span = rows + 8
    for _ in range(count):
        cx = rng.randrange(cols)
        speed = rng.uniform(*_DP_SPEED)
        offset = rng.uniform(0.0, span)
        length = rng.choice(_DP_LEN)
        head_y = int((offset + secs * speed) % span) - 6      # 雨丝的头（最下端）
        for k in range(length):
            yy = head_y - k                                    # k 越大越往上
            if not (0 <= yy < rows):
                continue
            xx = cx + k // 2                                   # 往上同时往右，才读成"斜"
            if 0 <= xx < cols:
                fill(p, ix + xx * s, iy + yy * s, s, s,
                     _DP_HEAD if k == 0 else _DP_TAIL)
