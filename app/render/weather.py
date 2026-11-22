"""天气的画法：阴天压色、雨天压色 + 雨丝。

两条设计约束，都是从之前踩过的坑里来的：

1. **只做成片的重复，不做单个像素点。** 蝴蝶、蜜蜂、萤火虫都试过，在「1 单位 = 2px」
   这个尺寸上全是噪点。雨是竖线、而且成片，属于「重复成片」那一类，才读得出来。
2. **不加整体泛白 / 闪光。** 收工庆祝曾经整窗提亮一帧，被当成闪屏。天气也一样，
   只用低透明度的冷色压一层，让画面"暗下来、脏一点"，不制造明暗跳变。
"""
from __future__ import annotations

import math
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

    # 位置按**屏幕像素**算，不按单位。雨速 7~11 单位/秒，一格要走六帧以上，
    # 按单位取整就变成"一秒只动十来下"，看着一顿一顿。方块仍是 s×s，
    # 只是纵向不再死对齐格子——雨本来就在动，这点错位看不出来。
    span_px = (rows + 5) * s
    for _ in range(count):
        x = rng.randrange(cols)
        speed = rng.uniform(*_SPEED) * s
        offset = rng.uniform(0.0, span_px)
        length = rng.choice(_LEN)
        y = int((offset + secs * speed) % span_px) - 5 * s
        for k in range(length):
            yy = y + k * s
            if 0 <= yy < rows * s:
                col = _HEAD if k == length - 1 else _TAIL
                fill(p, ix + x * s, iy + yy, s, s, col)


_SNOW = "#eaf2fb"
_SNOW_HI = "#ffffff"


def draw_snow(p: QPainter, ix: int, iy: int, iw: int, ih: int, s: int,
              secs: float, seed_day: int, heavy: bool = False) -> None:
    """雪花：慢、飘、小。和雨正相反。

    雨是又直又快的线，雪是慢慢晃下来的点——所以这里不画线段，只落方格，
    横向叠一条正弦让它左右飘。位置同样只由（日期 + 秒数）算出来，不存状态。
    随机数一律在判边界**之前**取完，否则越界的雪花会打乱后面所有雪花的位置。
    """
    cols = max(1, iw // s)
    rows = max(1, ih // s)
    count = max(5, int(cols * (0.62 if heavy else 0.34)))
    rng = random.Random((seed_day * 211 + 67) & 0x7FFFFFFF)
    span = rows + 4
    for _ in range(count):
        x0 = rng.randrange(cols)
        speed = rng.uniform(2.4, 4.0) if heavy else rng.uniform(1.3, 2.2)
        offset = rng.uniform(0.0, span)
        swing = rng.uniform(0.7, 2.0)
        phase = rng.uniform(0.0, 6.283)
        bright = rng.random() < 0.30
        # 和落叶同理：位置按**屏幕像素**取整。按"单位"取整的话，
        # 慢雪要三十多帧才挪一格，看着像钉在屏幕上。
        fy = (offset + secs * speed) % span - 4
        fx = (x0 + math.sin(secs * 0.8 + phase) * swing) % cols
        py = iy + int(round(fy * s))
        px = ix + int(round(fx * s))
        if not iy <= py < iy + ih - s:
            continue
        fill(p, px, py, s, s, _SNOW_HI if bright else _SNOW)


# 秋叶的四种颜色：枫红、银杏黄、枯褐、浅金。放在一起才像落叶堆，
# 只用一种会像下"橙色雨"。
_LEAF_COLORS = ("#c4692c", "#d39a3e", "#a2532a", "#d9ae55")


def draw_leaves(p: QPainter, ix: int, iy: int, iw: int, ih: int, s: int,
                secs: float, seed_day: int, count: int | None = None) -> None:
    """秋天的落叶：比雪还慢，而且不打旋不行——直着掉就成雪了。

    每片画成横着的两个像素：一个像素太碎，看起来像屏上落的灰；
    两个像素连起来才读得出"一片东西"。其中一块稍暗，像叶子翻了个面。
    位置只由（日期 + 秒数）算出来，不存状态——重启、切档都是同一场落叶。
    """
    n = count if count is not None else max(6, int(max(1, iw // s) * 0.10))
    rng = random.Random((seed_day * 373 + 29) & 0x7FFFFFFF)
    span = ih // s + 4
    for _ in range(n):
        x0 = rng.randrange(max(1, iw // s))
        # 速度差拉大：快的急着落地，慢的几乎悬着。混在一起，任何时刻都有人"正在动"，
        # 眼睛就不会盯住某一片看它卡。
        speed = rng.uniform(1.5, 5.5)
        offset = rng.uniform(0.0, span)
        swing = rng.uniform(1.4, 3.4)
        phase = rng.uniform(0.0, 6.283)
        color = QColor(_LEAF_COLORS[rng.randrange(len(_LEAF_COLORS))])
        flip = math.sin(secs * 2.2 + phase) > 0
        # 位置按**屏幕像素**取整，不按"单位"取整。
        # 一个单位是 s 个屏幕像素，按单位取整等于把精度砍掉 s 倍——
        # 慢速叶子就会连着十几帧停在同一个格子上。MC 的雪花能丝滑，
        # 靠的正是坐标连续、由光栅器落到半像素上，而不是"像素风所以该卡"。
        fy = (offset + secs * speed) % span - 4
        px = int(round((x0 + math.sin(secs * 1.3 + phase) * swing) * s))
        py = iy + int(round(fy * s))
        if not iy <= py < iy + ih - s:
            continue
        bx = ix + px
        if not ix <= bx <= ix + iw - 3 * s:      # 飘出画面的就不画，别在空中突然消失
            continue
        if flip:
            fill(p, bx, py, 3 * s, s, color)
            fill(p, bx + s, py + s, s, s, color.darker(118))
        else:
            fill(p, bx, py, s, 2 * s, color)
            fill(p, bx + s, py + s, s, s, color.darker(118))


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

    # 和小雨同样的道理：纵向按屏幕像素走，才不会被单位取整切成"一顿一顿"
    span_px = (rows + 8) * s
    for _ in range(count):
        cx = rng.randrange(cols)
        speed = rng.uniform(*_DP_SPEED) * s
        offset = rng.uniform(0.0, span_px)
        length = rng.choice(_DP_LEN)
        head_y = int((offset + secs * speed) % span_px) - 6 * s   # 雨丝的头（最下端）
        for k in range(length):
            yy = head_y - k * s                                   # k 越大越往上
            if not (0 <= yy < rows * s):
                continue
            xx = cx + k // 2                                      # 往上同时往右，才读成"斜"
            if 0 <= xx < cols:
                fill(p, ix + xx * s, iy + yy, s, s,
                     _DP_HEAD if k == 0 else _DP_TAIL)
