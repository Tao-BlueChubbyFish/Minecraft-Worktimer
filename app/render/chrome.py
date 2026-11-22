"""边框上的装饰件：图标、菜单按钮、草皮条、描边图

从 app/theme.py 拆出（2026-11-20）。函数体逐字未改，只是挪了位置。
"""
from __future__ import annotations

import math
import os
import random

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QPolygonF

from .. import pixel_font

from .common import _scaled, fill, texture  # noqa: E402

# 草方块图标是纯函数的产物（pal + size + seed 定死），却要逐像素做多边形点测试，
# 一帧就吃掉一半绘制时间。调色板每小时才换一次，存下来直接复用。
_iso_cache: dict = {"key": None, "img": None}
_NO_CACHE = os.environ.get("MCW_NO_CACHE") == "1"


def iso_block(pal: dict, size: int = 16, seed: int = 5) -> QImage:
    """等距投影的草方块（和 MC 物品栏里拿在手上的那个一样），size 建议 16。

    顶面草绿、左侧泥土偏暗、右侧泥土偏亮，四面自动描黑边；噪声只用同一色系
    的微调，避免纹理把立方体的体块感打散。
    """
    key = (size, seed, pal.get("_rev"), tuple(pal.get("grass") or ()),
           tuple(pal.get("dirt") or ()), tuple(pal.get("outline") or ()))
    if not _NO_CACHE and _iso_cache["key"] == key and _iso_cache["img"] is not None:
        return _iso_cache["img"]
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    u = size / 16.0
    top = QPolygonF([QPointF(8 * u, 0), QPointF(16 * u, 4 * u),
                     QPointF(8 * u, 8 * u), QPointF(0, 4 * u)])
    left = QPolygonF([QPointF(0, 4 * u), QPointF(8 * u, 8 * u),
                      QPointF(8 * u, 16 * u), QPointF(0, 12 * u)])
    right = QPolygonF([QPointF(8 * u, 8 * u), QPointF(16 * u, 4 * u),
                       QPointF(16 * u, 12 * u), QPointF(8 * u, 16 * u)])

    rng = random.Random(seed)
    g_base = QColor(pal["grass"][1])
    d_base = QColor(pal["dirt"][0])

    def tone(base: QColor, spread: int = 8) -> QColor:
        k = rng.randint(-spread, spread)
        return base.lighter(100 + k) if k >= 0 else base.darker(100 - k)

    g_top = g_base
    g_side_l = g_base.darker(118)
    g_side_r = g_base.lighter(104)
    d_l = d_base.darker(122)
    d_r = d_base.lighter(104)

    grid: list[list[QColor | None]] = [[None] * size for _ in range(size)]
    for y in range(size):
        for x in range(size):
            px = QPointF(x + 0.5, y + 0.5)
            if top.containsPoint(px, Qt.FillRule.WindingFill):
                grid[y][x] = tone(g_top, 7)
            elif left.containsPoint(px, Qt.FillRule.WindingFill):
                depth = (y + 0.5) - (4 * u + 0.5 * (x + 0.5))
                grid[y][x] = tone(g_side_l if depth < 2.5 * u else d_l, 7)
            elif right.containsPoint(px, Qt.FillRule.WindingFill):
                depth = (y + 0.5) - (4 * u + 0.5 * ((16 * u) - (x + 0.5)))
                grid[y][x] = tone(g_side_r if depth < 2.5 * u else d_r, 7)

    outline = QColor(pal["outline"])
    seam = d_base.darker(160)
    p = QPainter(img)
    for y in range(size):
        for x in range(size):
            col = grid[y][x]
            if col is None:
                continue
            border = (x == 0 or y == 0 or x == size - 1 or y == size - 1
                      or grid[y][x - 1] is None or grid[y][x + 1] is None
                      or grid[y - 1][x] is None or grid[y + 1][x] is None)
            if border:
                p.fillRect(x, y, 1, 1, outline)
            elif abs(x + 0.5 - 8 * u) < 0.6 and y > 8 * u:
                p.fillRect(x, y, 1, 1, seam)
            else:
                p.fillRect(x, y, 1, 1, col)
    p.end()
    if not _NO_CACHE:
        _iso_cache["key"], _iso_cache["img"] = key, img
    return img


def _snow_cap(p: QPainter, x: int, y: int, w: int, h: int, s: int,
              keep_clear: tuple[int, int] | None = None,
              clear_max: int = 3, cap: int = 7,
              skip: tuple[int, int] | None = None,
              pal: dict | None = None) -> None:
    """草尖积雪。

    1. **雪层薄、边沿平**——结冰的雪面是平的。厚雪加锯齿边只会糊成一片毛边。
    2. **轮廓走低频起伏**——每 3~5 列一个节点、中间斜着插值。整列随机会成毛刺，
       按块切长台又读成"白砖"，只有低频噪声两头都不占。
    3. **明度真拉开**——最上面纯白受光，往下三档一路压暗到 `snow_edge`；
       五档全挤在近白里等于没有层次。

    `keep_clear` 是标题文字的横坐标范围，那一带雪压到 `clear_max`，
    两侧各铺一段斜坡接回去。
    `skip` 是左上角草方块那一段：整段不积雪——方块是斜的，
    雪从它四个角露出来，看着就像方块被冻在冰里。
    """
    # 五档冷暖拉开的雪：纯白受光面 → 雪体 → 逼近底沿越来越冷。
    # 原来五档都挤在近白里，等于没层次；层次要读得出来，明度必须真拉开。
    white = QColor("#ffffff")
    snow_hi = QColor("#eaf4ff")
    snow = QColor("#d3e5f7")
    snow_deep = QColor("#b6cee6")
    snow_edge = QColor("#97b3d0")
    rows = max(1, h // s)
    n = max(1, w // s)
    # 三道上限：别压到泥土、别超过档位给的天数、也别把草皮条吃光。
    # 最后一道是给紧凑档的——它的草皮条只有 12 行，厚度照搬标准档就成了"一片白"。
    max_h = max(2, min(rows - 3, cap, max(2, int(rows * 0.72))))
    rng = random.Random(n * 131 + 7)

    # 1) 雪层：一块一块的长台，不是逐列锯齿——雪堆本来就是块状的
    # 厚度走低频起伏：一列一列地斜着变，不出现垂直断口——方块台面的竖直边
    # 在这个尺寸下读成"一块块白砖"，这是最难看的形态。
    # 用"每 3~5 列取一个随机高度、中间按比例插值"的噪声：轮廓不规则，
    # 但过渡是斜的——既不是整列随机的毛刺，也不是等周期的波纹。
    block = rng.randint(3, 5)
    knots = [rng.randint(max(2, max_h - 3), max_h)
             for _ in range(n // block + 3)]
    for i in range(n):
        pos = i / block
        k0 = int(pos)
        frac = pos - k0
        t = int(round(knots[k0] + (knots[min(k0 + 1, len(knots) - 1)] - knots[k0]) * frac))
        px = x + i * s
        t = max(2, min(t, max_h))
        if skip is not None and skip[0] - s <= px < skip[1] + s:
            t = 0                            # 草方块连同左右各一格：一点雪都不留
        elif keep_clear is not None:
            a, b = keep_clear
            ramp = 14 * s                    # 往标题两边各铺 14 格的坡：坡短了就是断崖
            if a <= px < b:
                t = min(t, clear_max)
            elif a - ramp <= px < a:
                k = (a - px) / ramp
                t = min(t, int(round(clear_max + (max_h - clear_max) * k)))
            elif b <= px < b + ramp:
                k = (px - b) / ramp
                t = min(t, int(round(clear_max + (max_h - clear_max) * k)))
        # 五档按"占这一列雪厚的比例"分，不按固定行数分：
        # 雪薄时上下几档挨着，雪厚时每档各自铺开——不然加厚以后中间一长条
        # 全是同一个色，看着就是一块白板。
        last = max(1, t - 1)
        for k in range(t):
            f = k / last
            if k == 0:
                col = white
            elif f < 0.35:
                col = snow_hi
            elif f < 0.70:
                col = snow
            elif f < 0.92:
                col = snow_deep
            else:
                col = snow_edge
            fill(p, px, y + k * s, s, s, col)


def draw_grass_strip(p: QPainter, w: int, h_px: int, s: int, pal: dict,
                     keep_clear: tuple[int, int] | None = None,
                     clear_max: int = 0, snow_cap: int | None = None,
                     skip: tuple[int, int] | None = None) -> None:
    """顶部草皮条：草地 + 1 单位泥土 + 交界暗线。

    冬天在草尖上压一层厚雪（见 `_snow_cap`）。位置用固定种子，不随帧变——
    否则每刷新一次雪层就重新洗牌，看着像屏幕在抖。
    """
    inner_w = w - 2 * s
    grass_h = h_px - 3 * s
    if grass_h > 0 and inner_w > 2:
        p.drawImage(QPoint(s, s), texture("grass", max(1, inner_w // s), max(1, grass_h // s), s, pal))
        p.drawImage(QPoint(s, h_px - 2 * s), texture("dirt", max(1, inner_w // s), 2, s, pal))
        fill(p, s, h_px - 2 * s, inner_w, s, QColor(pal["grass"][-1]).darker(125))
        if (pal.get("_season") or "") == "winter":
            # 0 = 这一天气温高，不积雪（见 paint.py 里的气温判断）
            cap = 7 if snow_cap is None else snow_cap
            if cap > 0:
                _snow_cap(p, s, s, inner_w, max(s, grass_h), s, keep_clear, clear_max,
                          cap, skip, pal)


def draw_image_outlined(p: QPainter, x: int, y: int, size_px: int, img: QImage, s: int,
                        pal: dict, outline: bool = True) -> None:
    img = img.scaled(size_px, size_px, Qt.AspectRatioMode.IgnoreAspectRatio,
                     Qt.TransformationMode.FastTransformation)
    p.drawImage(QPoint(x, y), img)
    if not outline:
        return
    o = QColor(pal["outline"])
    fill(p, x, y, size_px, s, o)
    fill(p, x, y + size_px - s, size_px, s, o)
    fill(p, x, y, s, size_px, o)
    fill(p, x + size_px - s, y, s, size_px, o)


def draw_menu_icon(p: QPainter, x: int, y: int, s: int, color: QColor) -> None:
    """三横线菜单图标（9x9 点阵，1 单位粗）。"""
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    for row in (1, 4, 7):
        p.drawRect(QRect(x, y + row * s, 9 * s, s))


def pixmap_icon(pal: dict, size: int = 64) -> QPixmap:
    """托盘 / 窗口图标：16x16 等距草方块整数倍放大。"""
    img = iso_block(pal, 16, 5)
    img = _scaled(img, max(1, size // 16))
    return QPixmap.fromImage(img)


# ---------------------------------------------------------------- 情绪化动效
# 这一组都是"纯函数 + 单位坐标"：只负责画，不持有状态，调用方给时间参数。
# 之所以要有，是因为 1 单位 = 2px 的尺度下，粒子类效果只能靠"形状"和"颜色
# 跳变"成立，靠数量堆是堆不出来的（花瓣、圆环烟花都试过，读不出来）。
