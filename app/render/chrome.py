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
              clear_max: int = 3, cap: int = 6) -> None:
    """草尖积雪：有厚度的雪层，不是一条白边。

    四条规则：
    1. **厚度要有量**——1~2 单位像贴了一条白胶带，会被当成画错的边框；压到 3~6 单位才读得出是雪。
    2. **顶上亮、中间白**——最上面 1 单位用纯白，受光的一面朝上，雪才有圆头的感觉。
    3. **下沿压 1 单位冷灰影**——没有影子，雪就只是白块；有影子，雪才是压在草上的东西。
    4. **标题那一带压薄**——`keep_clear` 是标题文字的横坐标范围，那里雪只留 2 单位，
       否则白字压在白雪上读不出来。两端照常堆厚，看起来正好是"雪被窗户中间挡住"的自然样子。

    厚度按列跳变（0.45 的概率重新抽），于是起伏是成片的，不是逐列抖动的锯齿。
    """
    snow = QColor("#dbe8f8")
    snow_top = QColor("#ffffff")
    shade = QColor("#7d93a7")
    rows = max(1, h // s)
    n = max(1, w // s)
    max_h = max(2, min(rows - 1, cap))
    rng = random.Random(n * 131 + 7)
    thick = min(max_h, 4)
    i = 0
    while i < n:
        if rng.random() < 0.45:
            thick = rng.randint(min(3, max_h), max_h)
        px = x + i * s
        lim = max_h
        if keep_clear is not None and keep_clear[0] <= px < keep_clear[1]:
            lim = min(max_h, clear_max)
        t = min(thick, lim)
        for k in range(t):
            fill(p, px, y + k * s, s, s, snow_top if k == 0 else snow)
        if t < rows:
            fill(p, px, y + t * s, s, s, shade)
        i += 1


def draw_grass_strip(p: QPainter, w: int, h_px: int, s: int, pal: dict,
                     keep_clear: tuple[int, int] | None = None,
                     clear_max: int = 3, snow_cap: int | None = None) -> None:
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
            _snow_cap(p, s, s, inner_w, max(s, grass_h), s, keep_clear, clear_max,
                      snow_cap or 6)


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
