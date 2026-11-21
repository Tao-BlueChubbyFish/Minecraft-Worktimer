"""基础画笔：方块填充、斜面、程序化材质、面板/按钮/纯色进度条

从 app/theme.py 拆出（2026-11-20）。函数体逐字未改，只是挪了位置。
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QPolygonF

from .. import pixel_font

_tex_cache: dict[tuple, QImage] = {}


def _noise_block(w: int, h: int, colors: list[str], seed: int,
                 speck: float = 0.32, speck_colors: list[str] | None = None) -> QImage:
    """在 1 单位 = 1 像素的画布上生成方块噪声。"""
    rng = random.Random(seed)
    img = QImage(max(1, w), max(1, h), QImage.Format.Format_ARGB32_Premultiplied)
    base = [QColor(x) for x in colors]
    spk = [QColor(x) for x in (speck_colors or colors)]
    for y in range(h):
        for x in range(w):
            pool = spk if rng.random() < speck else base
            img.setPixelColor(x, y, pool[rng.randrange(len(pool))])
    return img


def grass_block(w: int, h: int, pal: dict, seed: int = 7) -> QImage:
    """草方块正面（16x16 上下缩放）：上部草皮 + 锯齿交界 + 泥土。"""
    rng = random.Random(seed)
    img = QImage(max(1, w), max(1, h), QImage.Format.Format_ARGB32_Premultiplied)
    grass = [QColor(x) for x in pal["grass"]]
    dirt = [QColor(x) for x in pal["dirt"]]
    edge = max(1, int(round(h * 0.44)))
    for x in range(w):
        jag = rng.choice((0, 0, 0, 1, -1, 2))
        for y in range(h):
            if y < edge + jag:
                img.setPixelColor(x, y, grass[rng.randrange(len(grass))])
            else:
                img.setPixelColor(x, y, dirt[rng.randrange(len(dirt))])
    # 草与泥土交界处压一条暗线，像素画的关键细节
    for x in range(w):
        for y in range(h):
            if img.pixelColor(x, y) in grass:
                if y + 1 < h and img.pixelColor(x, y + 1) in dirt:
                    img.setPixelColor(x, y, grass[-1])
    return img


def _scaled(img: QImage, s: int) -> QImage:
    if s <= 1:
        return img
    return img.scaled(img.width() * s, img.height() * s,
                      Qt.AspectRatioMode.IgnoreAspectRatio,
                      Qt.TransformationMode.FastTransformation)


def _grass_tones(pal: dict) -> list[str]:
    """草皮噪声用的绿：只留 4 档、彼此相差 4% 明度。

    以前是直接把调色板里 5 个绿（最亮 #98be62、最暗 #5e7a36）随机铺满，对比太大：
    远看不是"一条绿带"，而是一条发脏的灰绿。噪声该读成"质地"，不该读成"脏点"，
    所以取中间那档做基准，上下各差一点点，冷灰和暗灰的像素就没了。
    """
    cols = sorted((QColor(x) for x in pal["grass"]), key=lambda q: q.lightness())
    mid = cols[len(cols) // 2]
    return [mid.lighter(104).name(), mid.name(),
            mid.darker(104).name(), mid.darker(108).name()]


def texture(kind: str, w: int, h: int, s: int, pal: dict, seed: int = 0) -> QImage:
    key = (kind, w, h, s, pal.get("panel", ["#fff"])[0], pal.get("grass", ["#fff"])[0], pal.get("dirt", ["#fff"])[0], seed)
    hit = _tex_cache.get(key)
    if hit is not None:
        return hit
    if kind == "panel":
        img = _noise_block(w, h, pal["panel"], 11 + seed, 0.20,
                           [pal["panel"][0], pal["panel"][-1], pal["panel"][2]])
    elif kind == "shade":
        img = _noise_block(w, h, pal["panel_shade"], 23 + seed, 0.34)
    elif kind == "track":
        img = _noise_block(w, h, pal["track"], 31 + seed, 0.25)
    elif kind == "fill":
        img = _noise_block(w, h, pal["fill"], 41 + seed, 0.26, [pal["fill_light"]] * 1 + pal["fill"])
    elif kind == "grass":
        # 杂色（speck）比例从 0.38 降到 0.20，配色也收成 4 档近色：干净但仍有颗粒
        img = _noise_block(w, h, _grass_tones(pal), 53 + seed, 0.20)
    elif kind == "dirt":
        img = _noise_block(w, h, pal["dirt"], 61 + seed, 0.38)
    elif kind == "stone":
        # 未开垦的岩层：比面板更暗，接近石头 GUI 的内凹色
        img = _noise_block(w, h, pal["track"], 83 + seed, 0.34,
                           [pal["bevel_dark"], pal["track"][0], pal["track"][-1]])
    else:
        img = _noise_block(w, h, pal["panel"], 71, 0.3)
    img = _scaled(img, s)
    if len(_tex_cache) > 160:
        _tex_cache.clear()
    _tex_cache[key] = img
    return img


def clear_cache() -> None:
    _tex_cache.clear()


# ---------------------------------------------------------------- 绘制助手


def fill(p: QPainter, x: int, y: int, w: int, h: int, color: QColor) -> None:
    p.fillRect(QRect(int(x), int(y), int(w), int(h)), color)


def bevel(p: QPainter, x: int, y: int, w: int, h: int, s: int,
          light: QColor, dark: QColor) -> None:
    """MC GUI 经典 1 像素立体边框。"""
    fill(p, x, y, w, s, light)
    fill(p, x, y, s, h, light)
    fill(p, x, y + h - s, w, s, dark)
    fill(p, x + w - s, y, s, h, dark)


def draw_panel(p: QPainter, x: int, y: int, w: int, h: int, s: int, pal: dict,
               kind: str = "panel", outline: bool = True) -> None:
    """石头面板：噪声底 + 立体边框 + 1 单位描边。"""
    if kind == "grass":
        p.drawImage(QPoint(x, y), texture("grass", w // s, h // s, s, pal))
    elif kind == "shade":
        p.drawImage(QPoint(x, y), texture("shade", w // s, h // s, s, pal))
    else:
        p.drawImage(QPoint(x, y), texture("panel", w // s, h // s, s, pal))
    bevel(p, x, y, w, h, s, QColor(pal["bevel_light"]), QColor(pal["bevel_dark"]))
    if outline:
        o = QColor(pal["outline"])
        fill(p, x, y, w, s, o)
        fill(p, x, y, s, h, o)
        fill(p, x, y + h - s, w, s, o)
        fill(p, x + w - s, y, s, h, o)


def draw_sunken(p: QPainter, x: int, y: int, w: int, h: int, s: int, pal: dict,
                kind: str = "shade") -> None:
    """凹陷区域（进度条底槽之类）。"""
    p.drawImage(QPoint(x, y), texture(kind, max(1, w // s), max(1, h // s), s, pal))
    fill(p, x, y, w, s, QColor(pal["bevel_dark"]))
    fill(p, x, y, s, h, QColor(pal["bevel_dark"]))
    fill(p, x, y + h - s, w, s, QColor(pal["bevel_light"]))
    fill(p, x + w - s, y, s, h, QColor(pal["bevel_light"]))


def draw_bar(p: QPainter, x: int, y: int, w: int, h: int, s: int, pal: dict,
             ratio: float, paused: bool = False) -> None:
    """MC 风格进度条：凹槽 + 噪点填充 + 顶部高光。"""
    draw_sunken(p, x, y, w, h, s, pal, "track")
    inner_x, inner_y = x + s, y + s
    inner_w, inner_h = w - 2 * s, h - 2 * s
    if inner_w <= 0 or inner_h <= 0:
        return
    ratio = max(0.0, min(1.0, ratio))
    fill_w = int(round(inner_w * ratio))
    if fill_w <= 0:
        return
    tex_w = max(1, fill_w // s)
    img = texture("fill", tex_w, max(1, inner_h // s), s, pal)
    p.drawImage(QPoint(inner_x, inner_y), img)
    if fill_w >= 3 * s:
        fill(p, inner_x, inner_y, fill_w, s, QColor(pal["fill_light"]))
        fill(p, inner_x, inner_y + inner_h - s, fill_w, s, QColor(pal["fill_dark"]))
    if paused:
        # 暂停时打上斜条纹，明确"计时已停"
        stripe = QColor(0, 0, 0, 92)
        for i in range(0, fill_w + inner_h, 4 * s):
            for yy in range(inner_h // s):
                px = i - yy * s
                if 0 <= px < fill_w:
                    fill(p, inner_x + px, inner_y + yy * s, s, s, stripe)


# ---------------------------------------------------------------- 草地进度条
# 一天里的天空：黎明粉紫 → 上午通透蓝 → 正午最亮 → 黄昏橙红 → 夜里深蓝带星。
# 每帧按小时线性插值，天色连续渐变，不会整点跳一下。


def draw_button(p: QPainter, x: int, y: int, w: int, h: int, s: int, pal: dict,
                pressed: bool = False, hover: bool = False, face: str = "shade",
                outline: bool = True) -> None:
    """MC 按钮：底噪 + 立体边框，可选 1 单位描边。"""
    p.drawImage(QPoint(x, y), texture(face, max(1, w // s), max(1, h // s), s, pal, 3))
    ox = oy = 0
    if outline:
        o = QColor(pal["outline"])
        fill(p, x, y, w, s, o)
        fill(p, x, y, s, h, o)
        fill(p, x, y + h - s, w, s, o)
        fill(p, x + w - s, y, s, h, o)
        ox = oy = s
    iw, ih = w - 2 * ox, h - 2 * oy
    if pressed:
        bevel(p, x + ox, y + oy, iw, ih, s, QColor(pal["bevel_dark"]), QColor(pal["bevel_light"]))
    else:
        bevel(p, x + ox, y + oy, iw, ih, s, QColor(pal["bevel_light"]), QColor(pal["bevel_dark"]))
    if hover and not pressed:
        fill(p, x + ox + s, y + oy + s, iw - 2 * s, ih - 2 * s, QColor(255, 255, 255, 40))


def draw_slot(p: QPainter, x: int, y: int, size: int, s: int, pal: dict) -> None:
    """内凹格子：深色底 + 左上暗边 + 右下高光，用来衬托方块图标。"""
    fill(p, x, y, size, size, QColor(0, 0, 0, 110))
    o = QColor(pal["outline"])
    hi = QColor(pal["bevel_light"])
    hi.setAlpha(110)
    fill(p, x, y, size, s, o)
    fill(p, x, y, s, size, o)
    fill(p, x, y + size - s, size, s, hi)
    fill(p, x + size - s, y, s, size, hi)
