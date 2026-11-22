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
_scaled_cache: dict[tuple, QImage] = {}   # 放大到屏幕像素的副本，每帧只 blit


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


# 每季的日出 / 入夜锚点（曲线小时）。数字越大 = 曲线越晚 = 天色越暗。
# 夏天日照长，下班时天还亮着，所以入夜锚点要**小**；冬天反过来，18:00 已经黑了。
# 第一版写反了（夏天给了 21.9），结果同一时刻夏天比冬天还黑。
_DAWN_BY_SEASON = {"spring": 6.2, "summer": 5.6, "autumn": 6.5, "winter": 6.9}
_NIGHT_BY_SEASON = {"spring": 20.4, "summer": 18.8, "autumn": 20.2, "winter": 22.4}


def work_sky_hour(real_hour: float, start_hour: float, span_hours: float,
                  season: str | None = None) -> float:
    """把真实钟点换算成"进度条里的天色小时"。

    曲线本身是按 24 小时做的：04:30 日出、12:00 正午、19:00 日落、20:30 入夜。
    但多数人只在 8:00~21:00 看着这个挂件，照真实钟点走的话，最好看的那几段
    全落在看不见的时间里（凌晨的日出、深夜的星空）。

    所以把 [上班, 上班 + span] 整段线性映射到曲线的 [日出, 入夜]：
    开工那一刻天刚亮，下午转暖，快下班时日落，加班时天彻底黑。
    上班之前 = 天刚亮；下班之后夜色继续慢慢加深（斜率减半），不会到点卡死。

    季节只挪两端的锚点：冬天日出晚、入夜早，夏天反过来。中间那段映射不变，
    所以同一段工作时间里感受到的"天黑速度"变了——这才是换季最直接的体感。
    """
    dawn = _DAWN_BY_SEASON.get(season or "", _SKY_DAWN_H)
    night = _NIGHT_BY_SEASON.get(season or "", _SKY_NIGHT_H)
    span = max(1.0, span_hours)
    t = (real_hour - start_hour) / span
    if t <= 0.0:
        return dawn
    if t <= 1.0:
        return dawn + t * (night - dawn)
    return min(23.9, night + (real_hour - start_hour - span) * 0.5)


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


# 云速：**一个屏幕像素 / 3 秒**（用户要的"几秒钟才挪一下"）。
#
# 这里按"像素/秒"定义，不按"单位/秒"——单位的大小随窗口档位变（大档一个单位=3像素），
# 按单位定义的话，小档窗口里云会明显更快。按像素定义，三档看到的云一样慢。
#
# 附带的好处：云这么慢，晴天就不必为它开 60 帧的马达了（见 clock._sync_rain_timer），
# 靠每秒一次的例行重绘就够——每 3 秒自然挪一格，晴天 CPU 回到接近 0。
_CLOUD_PX_PER_SEC = 1.0 / 3.0

# 每朵云各挑一档快慢：慢的六秒多才挪一格，快的不到两秒一格，中间差五倍。
# 整片天一起平移最假，几朵云各飘各的才像空中真有东西在走。
# 步长始终锁在 1 像素，所以差的是"多久挪一下"，不是"一下跳多远"——不会出现某朵云在飞。
_CLOUD_SPEEDS = (0.4, 0.75, 1.3, 2.2)


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
    # 先洗一遍快慢档：保证同一天里必定有快的也有慢的，不靠运气
    tiers = list(_CLOUD_SPEEDS)
    rng.shuffle(tiers)
    for i in range(max(1, int(total // (32 if tall else 45)))):
        cw = rng.randint(9, 14) if tall else rng.randint(7, 11)
        ch = 3 if sky_u < 6 else (6 if tall else 4)
        if ch + 2 > sky_u:
            ch = max(2, sky_u - 2)
        base = rng.uniform(0, total + cw)
        # 这朵云自己那一档快慢，再抖 ±8%：两朵同档的云也不会像被同一根绳拖着走。
        # 速度先由"像素/秒"折算回单位（画的时候按单位算、按像素落）。
        speed = (_CLOUD_PX_PER_SEC / s) * tiers[i % len(tiers)] * rng.uniform(0.92, 1.08)
        cx = (base + secs * speed) % (total + cw) - cw
        y = iy + (1 + rng.randint(0, max(0, sky_u - ch - 3))) * s
        key = (cw, ch, cloud.name(), shade.name(), seed_day * 31 + i, s)
        img = _scaled_cache.get(key)
        if img is None:
            img = _cloud_img(cw, ch, cloud.name(), shade.name(),
                             seed_day * 31 + i).scaled(
                cw * s, ch * s, Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation)
            if len(_scaled_cache) > 64:
                _scaled_cache.clear()
            _scaled_cache[key] = img
        p.setOpacity(0.95 if star < 0.3 else 0.8)
        p.drawImage(QPoint(ix + int(round(cx * s)), y), img)
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
