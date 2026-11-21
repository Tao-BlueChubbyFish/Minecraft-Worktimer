"""边框上的装饰件：图标、菜单按钮、草皮条、描边图

从 app/theme.py 拆出（2026-11-20）。函数体逐字未改，只是挪了位置。
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QPolygonF

from .. import pixel_font

from .common import _scaled, fill, texture  # noqa: E402

def iso_block(pal: dict, size: int = 16, seed: int = 5) -> QImage:
    """等距投影的草方块（和 MC 物品栏里拿在手上的那个一样），size 建议 16。

    顶面草绿、左侧泥土偏暗、右侧泥土偏亮，四面自动描黑边；噪声只用同一色系
    的微调，避免纹理把立方体的体块感打散。
    """
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
    return img


def draw_grass_strip(p: QPainter, w: int, h_px: int, s: int, pal: dict) -> None:
    """顶部草皮条：草地 + 1 单位泥土 + 交界暗线。"""
    inner_w = w - 2 * s
    grass_h = h_px - 3 * s
    if grass_h > 0 and inner_w > 2:
        p.drawImage(QPoint(s, s), texture("grass", max(1, inner_w // s), max(1, grass_h // s), s, pal))
        p.drawImage(QPoint(s, h_px - 2 * s), texture("dirt", max(1, inner_w // s), 2, s, pal))
        fill(p, s, h_px - 2 * s, inner_w, s, QColor(pal["grass"][-1]).darker(125))


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
