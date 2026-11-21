"""天空：天色曲线、云、月亮、鸟群

从 app/theme.py 拆出（2026-11-20）。函数体逐字未改，只是挪了位置。
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QPolygonF

from .. import pixel_font

from .palette import c  # noqa: E402
from .common import fill  # noqa: E402

_cloud_cache: dict[tuple, QImage] = {}


_SKY_CURVE = (
    # (小时, 天顶, 天中, 地平线, 云, 云影, 星空浓度)
    (0.0, "#111c30", "#17243c", "#1e2d47", "#3d4a60", "#333e51", 1.0),
    (4.6, "#1a2440", "#2b3054", "#5c4a63", "#4e4657", "#3f3948", 0.9),
    (6.2, "#5d6fa6", "#a2819a", "#e8a97f", "#f6d9c8", "#d9bda9", 0.15),
    (7.6, "#6a9bd4", "#8fb8e4", "#bcd6ee", "#f4f8ff", "#dbe6f7", 0.0),
    (11.0, "#4d8ad0", "#6ba4e0", "#9cc6ee", "#ffffff", "#e6eefa", 0.0),
    (14.5, "#5290d2", "#72a9e2", "#a2c8ec", "#fdfeff", "#e3ecf8", 0.0),
    (17.6, "#5f7fb8", "#a88b9a", "#ecac83", "#fbe0cc", "#e0c6b2", 0.0),
    (18.6, "#5b5fa2", "#b0708c", "#f0955f", "#ffd0ae", "#dcae91", 0.02),
    (19.6, "#3a3560", "#7d4f6e", "#c46a55", "#d99e86", "#b58270", 0.12),
    (20.8, "#1d2740", "#2a3450", "#4a3f57", "#575070", "#474159", 0.55),
    (22.0, "#111c30", "#17243c", "#1e2d47", "#3d4a60", "#333e51", 1.0),
    (24.0, "#111c30", "#17243c", "#1e2d47", "#3d4a60", "#333e51", 1.0),
)


_SKY_DAWN_H = 6.2            # 曲线里"日出"的锚点小时


_SKY_NIGHT_H = 20.8          # 曲线里"入夜"的锚点小时


def work_sky_hour(real_hour: float, start_hour: float, span_hours: float) -> float:
    """把真实钟点换算成"进度条里的天色小时"。

    曲线本身是按 24 小时做的：04:30 日出、12:00 正午、19:00 日落、20:30 入夜。
    但多数人只在 8:00~21:00 看着这个挂件，照真实钟点走的话，最好看的那几段
    全落在看不见的时间里（凌晨的日出、深夜的星空）。

    所以把 [上班, 上班 + span] 整段线性映射到曲线的 [日出, 入夜]：
    开工那一刻天刚亮，下午转暖，快下班时日落，加班时天彻底黑。
    上班之前 = 天刚亮；下班之后夜色继续慢慢加深（斜率减半），不会到点卡死。
    """
    span = max(1.0, span_hours)
    t = (real_hour - start_hour) / span
    if t <= 0.0:
        return _SKY_DAWN_H
    if t <= 1.0:
        return _SKY_DAWN_H + t * (_SKY_NIGHT_H - _SKY_DAWN_H)
    return min(23.9, _SKY_NIGHT_H + (real_hour - start_hour - span) * 0.5)


def _mix(a: str, b: str, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    return QColor(
        int(ca.red() + (cb.red() - ca.red()) * t),
        int(ca.green() + (cb.green() - ca.green()) * t),
        int(ca.blue() + (cb.blue() - ca.blue()) * t),
    )


def sky_at(hour: float, mul: float = 1.0) -> tuple[list[QColor], QColor, QColor, float]:
    """返回 (三段天色, 云色, 云影, 星空浓度)。mul 用来整体压暗（深色配色用）。"""
    h = hour % 24.0
    h0, h1 = _SKY_CURVE[0][0], _SKY_CURVE[1][0]
    t = 0.0
    for i in range(len(_SKY_CURVE) - 1):
        a, b = _SKY_CURVE[i], _SKY_CURVE[i + 1]
        if a[0] <= h <= b[0]:
            h0, h1 = a[0], b[0]
            t = 0.0 if h1 == h0 else (h - h0) / (h1 - h0)
            bands = [_mix(a[k], b[k], t) for k in (1, 2, 3)]
            cloud = _mix(a[4], b[4], t)
            shade = _mix(a[5], b[5], t)
            star = a[6] + (b[6] - a[6]) * t
            if mul != 1.0:
                def dim(c: QColor) -> QColor:
                    hh, ss, vv, aa = c.getHsvF()
                    return QColor.fromHsvF(hh if hh >= 0 else 0.0, min(1.0, ss * 0.85),
                                           min(1.0, vv * mul), aa)
                bands = [dim(c) for c in bands]
                cloud, shade = dim(cloud), dim(shade)
            return bands, cloud, shade, max(0.0, min(1.0, star))
    # 兜底：正午天色
    return [_mix(_SKY_CURVE[4][k], _SKY_CURVE[4][k], 0) for k in (1, 2, 3)], \
        _mix(_SKY_CURVE[4][4], _SKY_CURVE[4][4], 0), \
        _mix(_SKY_CURVE[4][5], _SKY_CURVE[4][5], 0), 0.0


def _cloud_img(cw: int, ch: int, col: str, shade: str, seed: int) -> QImage:
    """像素云：底部两层满宽，往上逐层内收，顶上一两个凸起。"""
    key = (cw, ch, col, shade, seed)
    hit = _cloud_cache.get(key)
    if hit is not None:
        return hit
    rng = random.Random(seed)
    img = QImage(max(1, cw), max(1, ch), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    c0, cs = QColor(col), QColor(shade)
    hi = QColor(col).lighter(103)

    def put(x: int, y: int, c: QColor) -> None:
        if 0 <= x < cw and 0 <= y < ch:
            img.setPixelColor(x, y, c)

    bottom = ch - 1
    for x in range(cw):
        put(x, bottom, cs)
        put(x, bottom - 1, c0)
    # 往上逐层内收，左右收得不一样才像自然云
    li = ri = 0
    for i in range(2, ch):
        li = min(li + rng.randint(0, 1), max(0, cw // 2 - 1))
        ri = min(ri + rng.randint(0, 1), max(0, cw // 2 - 1))
        for x in range(li, cw - ri):
            put(x, bottom - i, hi if i >= 3 else c0)
    # 顶部凸起
    if ch >= 4:
        for x in range(li, cw - ri):
            img.setPixelColor(x, 0, Qt.GlobalColor.transparent)
        h1 = li
        for x in range(h1, min(cw - ri, h1 + rng.randint(4, 6))):
            put(x, 0, hi)
        h2 = h1 + rng.randint(4, 6)
        for x in range(h2, min(cw - ri, h2 + rng.randint(3, 5))):
            put(x, 0, hi)
    for x, y in ((0, bottom), (cw - 1, bottom)):
        img.setPixelColor(x, y, Qt.GlobalColor.transparent)
    if len(_cloud_cache) > 64:
        _cloud_cache.clear()
    _cloud_cache[key] = img
    return img


_CLOUD_SPEED = 0.45          # 单位/秒，约 7 分钟飘完一整条（"稍慢"，能看出来在动）


def _draw_sky(p: QPainter, ix: int, iy: int, iw: int, sky_u: int, s: int,
              hour: float, secs: float, seed_day: int, mul: float,
              moon: bool = True, clouds: bool = True) -> list[QColor]:
    bands, cloud, shade, star = sky_at(hour, mul)
    n = len(bands)
    for i, col in enumerate(bands):
        y0 = iy + (sky_u * i) // n * s
        y1 = iy + (sky_u * (i + 1)) // n * s
        fill(p, ix, y0, iw, max(1, y1 - y0), col)

    # 月亮：日落之后挂上，画在云之前，于是云会从它前面飘过去
    if moon and hour >= 18.2 and sky_u >= 6:
        _draw_moon(p, ix, iy, iw, sky_u, s)

    # 星星：只在夜里亮，位置按日期固定，亮度随秒数轻轻呼吸
    if star > 0.02 and sky_u >= 4:
        rng = random.Random(seed_day * 613 + 29)
        for i in range(max(1, int(iw / s / 16))):
            sx = ix + rng.randrange(max(1, iw // s)) * s
            sy = iy + (1 + rng.randrange(max(1, sky_u - 3))) * s
            tw = 0.7 + 0.3 * (1.0 - abs(((secs / 4.0 + i) % 2.0) - 1.0))
            col = QColor(255, 255, 236)
            col.setAlpha(int(235 * star * tw))
            fill(p, sx, sy, s, s, col)

    # 云：按秒横移，落点吸到单位网格上，保持像素感
    if not clouds:
        return bands
    total = iw / s
    rng = random.Random(seed_day * 97 + 13)
    tall = sky_u >= 14                      # 天空加高之后，云也得跟着长，否则一片空
    for i in range(max(1, int(total // (32 if tall else 45)))):
        cw = rng.randint(9, 14) if tall else rng.randint(7, 11)
        ch = 3 if sky_u < 6 else (6 if tall else 4)
        if ch + 2 > sky_u:
            ch = max(2, sky_u - 2)
        base = rng.uniform(0, total + cw)
        speed = _CLOUD_SPEED * (0.75 + 0.5 * rng.random())
        cx = (base + secs * speed) % (total + cw) - cw
        y = iy + (1 + rng.randint(0, max(0, sky_u - ch - 3))) * s
        img = _cloud_img(cw, ch, cloud.name(), shade.name(), seed_day * 31 + i)
        img = img.scaled(cw * s, ch * s, Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.FastTransformation)
        p.setOpacity(0.95 if star < 0.3 else 0.8)
        p.drawImage(QPoint(ix + int(cx) * s, y), img)
        p.setOpacity(1.0)
    return bands


# 花色：每种花一个像素花冠图案，a=花瓣 b=花心/暗部 '.'=透明。
# 花冠边长就是它的"体型"——宽度决定同层里下一朵要让出多远，高度决定它站哪一层。
# 所以这里不再单独记高度范围。


def _draw_moon(p: QPainter, ix: int, iy: int, iw: int, sky_u: int, s: int) -> None:
    """入夜后天上挂一枚满月（云从它前面飘过去）。

    本来这儿画的是萤火虫，但 2px 的光点和满地蒲公英糊在一起，怎么看都是杂点；
    月亮是"大形状 + 干净背景"，这个尺度下反而最稳。
    """
    if sky_u < 6:
        return
    r = max(2, sky_u // 7)                    # 半径随天空长，太高就压到边框
    cx = ix + int(iw * 0.78) // s * s
    cy = iy + (r + 2) * s
    halo = QColor("#f7f0c8")
    halo.setAlpha(38)
    hw = r + 1
    fill(p, cx - hw * s, cy - s, (2 * hw + 1) * s, 3 * s, halo)   # 一圈极淡的光晕
    fill(p, cx - s, cy - hw * s, 3 * s, (2 * hw + 1) * s, halo)
    face = QColor("#f4efc2")
    for uy in range(-r, r + 1):
        for ux in range(-r, r + 1):
            if ux * ux + uy * uy <= r * r + 1:
                fill(p, cx + ux * s, cy + uy * s, s, s, face)
    # 两处暗斑当环形山，不然就是一块纯色圆片
    fill(p, cx - s, cy - s, s, s, QColor("#d8d19a"))
    fill(p, cx + s, cy + s, s, s, QColor("#ded7a2"))


def _draw_bird(p: QPainter, cx: int, cy: int, s: int, up: bool) -> None:
    """单只鸟：3 单位宽的 V 字，两帧之间翻个面就算扇翅。"""
    ink = QColor("#24232c")
    if up:
        fill(p, cx - s, cy - s, s, s, ink)
        fill(p, cx + s, cy - s, s, s, ink)
        fill(p, cx, cy, s, s, ink)
    else:
        fill(p, cx - s, cy, s, s, ink)
        fill(p, cx + s, cy, s, s, ink)
        fill(p, cx, cy + s, s, s, ink)


def _draw_flock(p: QPainter, elapsed: float, dur: float, ix: int, iy: int,
                iw: int, sky_u: int, s: int, seed: int) -> None:
    """鸟群从左框外斜斜飞过去。elapsed/dur 是秒。

    队形按日期固定，扇翅各错半拍——一起飞的一群鸟本来就不会完全同步。
    """
    if sky_u < 5:          # 小档天空只有 3 行，六只鸟挤进去只会糊成一团墨点，干脆不画
        return
    t = 0.0 if dur <= 0 else max(0.0, min(1.0, elapsed / dur))
    rng = random.Random(seed * 977 + 53)
    shape = _FLOCK_SHAPES[seed % len(_FLOCK_SHAPES)]
    # 整队压在天空带的上沿：再往下就是花冠，画在花之后会像鸟在草里爬
    lo = 2 + (seed // 3) % max(1, sky_u - 6)
    drift = int(round(math.sin(t * 3.14) * s))
    lead = int(round(ix - 20 * s + t * (iw + 34 * s)))
    for i, (bx, by) in enumerate(shape):
        if rng.random() < 0.10:            # 每天有一两只飞得不太齐，位置偏一点
            bx += rng.randint(-1, 1)
            by += rng.randint(-1, 1)
        up = int(elapsed * 7 + i * 0.5) % 2 == 0
        row = max(1, min(sky_u - 2, lo + by))     # 别贴着上边框，会被裁
        _draw_bird(p, lead + bx * s, iy + row * s + drift, s, up)


# ---------------------------------------------------------------- 草地上的道具
# 不是生物，所以不用"像"某个具体东西：轮廓和颜色不糊成噪点就成立。
# 按进度条的固定比例摆，铺到那儿才出现——地是一路铺过去的，东西也是慢慢多起来的。


_FLOCK_SHAPES = (
    ((0, 0), (-4, -1), (-4, 1), (-8, -2), (-8, 2), (-12, 0)),    # V 字
    ((0, 0), (-3, 0), (-6, 0), (-9, 0), (-12, 0)),                # 一字长蛇
    ((0, 0), (-4, -2), (-7, 1), (-11, -1), (-14, 2)),             # 松散
)


_BIRD = _FLOCK_SHAPES[0]
