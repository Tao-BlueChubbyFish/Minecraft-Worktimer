"""叠在最上层的覆盖物：木牌、两个选项、烟花、彩纸

从 app/theme.py 拆出（2026-11-20）。函数体逐字未改，只是挪了位置。
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QPolygonF

from .. import pixel_font

from .common import fill  # noqa: E402
from .meadow import _shade  # noqa: E402

def draw_plank(p: QPainter, x: int, y: int, w: int, h: int, s: int, pal: dict,
               text: str, family: str, hot: bool = False, gold: bool = False,
               text_h: int = 11) -> None:
    """一块木牌：收工／询问都用它。厚度 2 单位的硬描边，四角一颗白钉。"""
    o = 2 * s
    edge = QColor("#ffd75e") if gold else QColor(pal["outline"])
    if hot and not gold:
        edge = QColor("#ffd75e")
    fill(p, x, y, w, h, QColor(pal["dirt"][2]))
    fill(p, x, y, w, s, QColor(pal["dirt"][4]))
    fill(p, x, y + h - s, w, s, QColor(pal["dirt"][1]))
    fill(p, x, y, w, o, edge)
    fill(p, x, y + h - o, w, o, edge)
    fill(p, x, y, o, h, edge)
    fill(p, x + w - o, y, o, h, edge)
    nail = QColor(pal["bevel_light"])
    for nx in (x + 3 * s, x + w - 4 * s):
        for ny in (y + 3 * s, y + h - 4 * s):
            fill(p, nx, ny, s, s, nail)
    tw, _ = pixel_font.measure_cjk(text, text_h * s, family, bold=True)
    pixel_font.draw_cjk_vcenter(p, x + (w - tw) // 2, y + o, h - 2 * o, text,
                                text_h * s, QColor(pal["text_on_grass"]), family,
                                shadow=QColor(pal["text_shadow"]), bold=True)


def draw_firework(p: QPainter, cx: int, cy: int, s: int, t: float,
                  color: QColor, hot: QColor | None = None,
                  radius: float = 11.0) -> None:
    """一簇像素烟花：2×2 亮核 + 12 向三段拖尾，随 t 扩散、由白转色。

    单点撒一圈在灰底上只能读成"脏点"，所以每一向都画 3 段拖尾——有长度才像炸开。
    """
    if not (0.0 <= t <= 1.0):
        return
    hot = hot or QColor("#fff6d0")
    r = (1.6 + radius * t ** 0.62) * s
    core = hot if t < 0.45 else color
    fill(p, int(round(cx - s)), int(round(cy - s)), 2 * s, 2 * s, core)
    for k in range(12):
        ang = k * (math.pi / 6) + 0.26
        reach = 1.0 if k % 2 == 0 else 0.78
        for j, frac in enumerate((0.45, 0.72, 1.0)):
            rr = r * reach * frac
            col = hot if (j < 2 and t < 0.62) else color
            if t > 0.82 and j == 2 and k % 3:
                continue
            fill(p, int(round(cx + math.cos(ang) * rr)),
                 int(round(cy + math.sin(ang) * rr)), s, s, col)


_CONFETTI = ("#f2f2f2", "#ffd75e", "#e8703a", "#7da04b", "#9ec5ff", "#f4a8c0")


def draw_confetti(p: QPainter, w: int, h: int, s: int, t: float, seed: int,
                  top: int = 0, count: int = 20) -> None:
    """彩色纸屑从上往下飘：每片 1 单位，左右摆一格，落到 t=1 就不画了。"""
    rng = random.Random(seed)
    for i in range(count):
        col = QColor(_CONFETTI[i % len(_CONFETTI)])
        x0 = rng.randrange(0, max(1, w // s)) * s
        delay = rng.random() * 0.35
        speed = 0.55 + rng.random() * 0.55
        sway = (i % 5) - 2
        tt = (t - delay) / max(0.05, speed)
        if tt < 0 or tt > 1.0:
            continue
        y = top + int((h - top) * tt) + (i % 3) * s
        x = x0 + int(math.sin(tt * 6.28 + i) * abs(sway) * s)
        if tt > 0.85:
            col = _shade(col, 0.88)
        fill(p, x, min(y, h - s), s, s, col)


def draw_choice(p: QPainter, x: int, y: int, w: int, h: int, s: int, pal: dict,
                 label: str, family: str, primary: bool, hover: bool = False) -> None:
    """收工时的两个选项按钮：主按钮绿底白字，次按钮灰底深字。"""
    if primary:
        face = QColor(pal["accent"])
        face_d = face.darker(126)
        text = QColor("#ffffff")
        sh = QColor(pal["text_shadow"])
    else:
        face = QColor(pal["panel"][1])
        face_d = QColor(pal["panel_shade"][1])
        text = QColor(pal["text"])
        sh = QColor(pal["bevel_light"])
    o = 2 * s
    fill(p, x, y, w, h, face)
    fill(p, x, y, w, s * 2, face.lighter(112))
    fill(p, x, y + h - s * 2, w, s * 2, face_d)
    fill(p, x, y, w, o, QColor(pal["outline"]))
    fill(p, x, y + h - o, w, o, QColor(pal["outline"]))
    fill(p, x, y, o, h, QColor(pal["outline"]))
    fill(p, x + w - o, y, o, h, QColor(pal["outline"]))
    if hover:
        fill(p, x + o, y + o, w - 2 * o, h - 2 * o, QColor(255, 255, 255, 34))
    tw, _ = pixel_font.measure_cjk(label, 9 * s, family, bold=True)
    pixel_font.draw_cjk_vcenter(p, x + (w - tw) // 2, y + o, h - 2 * o, label,
                                9 * s, text, family, shadow=sh, bold=True)
