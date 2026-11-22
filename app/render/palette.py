"""配色与一天的光线

从 app/theme.py 拆出（2026-11-20）。函数体逐字未改，只是挪了位置。
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QPolygonF

from .. import pixel_font, season as _season

from .common import fill  # noqa: E402

PALETTES: dict[str, dict] = {
    # 原版草方块 + 石头 GUI：浅灰石头面板、深灰描边、草绿点缀
    "grass_stone": {
        "outline": "#1b1b1b",
        "panel": ["#c6c6c6", "#c9c9c9", "#c3c3c3", "#cbcbcb", "#c0c0c0"],
        "panel_shade": ["#b4b4b4", "#b9b9b9", "#afafaf"],
        "bevel_light": "#ffffff",
        "bevel_dark": "#8b8b8b",
        "text": "#2f2f2f",
        "text_dim": "#5c5c5c",
        "text_on_grass": "#ffffff",
        "text_shadow": "#1f3312",
        "accent": "#4f7d2f",
        "grass": ["#7da04b", "#8cb356", "#6c8c3f", "#98be62", "#5e7a36"],
        "dirt": ["#8b6444", "#7a5639", "#9c7250", "#6b4a31", "#a87c58"],
        "sky_mul": 1.0,
        "track": ["#8a8a8a", "#828282", "#919191"],
        "fill": ["#6e9a3a", "#7aa844", "#62892f"],
        "fill_light": "#93c258",
        "fill_dark": "#4d6f26",
        "warn": "#b8541f",
    },
    # 夜晚石头：低饱和深灰，适合深色桌面
    "stone_night": {
        "outline": "#0d0d0d",
        "panel": ["#3a3a3a", "#404040", "#343434", "#464646", "#2f2f2f"],
        "panel_shade": ["#262626", "#2b2b2b", "#222222"],
        "bevel_light": "#5c5c5c",
        "bevel_dark": "#1a1a1a",
        "text": "#e6e6e6",
        "text_dim": "#9a9a9a",
        "text_on_grass": "#f2f2f2",
        "text_shadow": "#000000",
        "accent": "#8cb356",
        "grass": ["#5d7a3a", "#688641", "#4e6830", "#74944a", "#415726"],
        "dirt": ["#5c4230", "#4d3728", "#6a4c37", "#3f2d20", "#75543c"],
        "sky_mul": 0.62,
        "track": ["#252525", "#202020", "#2a2a2a"],
        "fill": ["#6e9a3a", "#7aa844", "#62892f"],
        "fill_light": "#93c258",
        "fill_dark": "#41601f",
        "warn": "#d4703a",
    },
    # 泥土木屋：暖色泥土 + 木头色，草绿点缀
    "dirt_wood": {
        "outline": "#241708",
        "panel": ["#b08b62", "#b8926a", "#a8835b", "#c19b73", "#9e7a54"],
        "panel_shade": ["#8e6d4a", "#967450", "#86664a"],
        "bevel_light": "#e8cba6",
        "bevel_dark": "#6d5133",
        "text": "#2b1d0e",
        "text_dim": "#5a4327",
        "text_on_grass": "#fff8e6",
        "text_shadow": "#2a1a08",
        "accent": "#4f7d2f",
        "grass": ["#7da04b", "#8cb356", "#6c8c3f", "#98be62", "#5e7a36"],
        "dirt": ["#8b6444", "#7a5639", "#9c7250", "#6b4a31", "#a87c58"],
        "sky_mul": 0.96,
        "track": ["#7d5f40", "#755838", "#866647"],
        "fill": ["#6e9a3a", "#7aa844", "#62892f"],
        "fill_light": "#93c258",
        "fill_dark": "#4d6f26",
        "warn": "#a8461b",
    },
}


PALETTE_NAMES = tuple(PALETTES.keys())


def resolve_palette(cfg) -> dict:
    name = cfg.get("palette", "grass_stone")
    base = PALETTES.get(name) or PALETTES["grass_stone"]
    pal = {}
    for k, v in base.items():
        pal[k] = list(v) if isinstance(v, list) else v
    override = cfg.get("palette_override") or {}
    for k, v in override.items():
        if k in pal and v:
            pal[k] = list(v) if isinstance(v, list) else v
    return pal


def c(pal: dict, key: str) -> QColor:
    v = pal[key]
    if isinstance(v, list):
        v = v[0]
    return QColor(v)


def quote_color(pal: dict) -> QColor:
    """每日一句的颜色：草绿压低/提亮到面板上刚好读得清的那一档。"""
    col = QColor(pal["accent"])
    light_panel = QColor(c(pal, "panel")).lightnessF() > 0.55
    return col.darker(122) if light_panel else col.lighter(112)


# ---------------------------------------------------------------- 时间色温
# 一天里草皮 / 泥土的颜色走向：清晨偏冷、正午偏黄、黄昏转暖、夜里压暗。
# 幅度刻意压在 ±10% 以内，避免破坏低饱和的方块质感。


_TIME_CURVE = (
    # (小时, 色相偏移°, 饱和度倍数, 明度倍数)
    (0.0, -10, 0.70, 0.58),
    (5.0, -10, 0.70, 0.58),
    (6.8, 8, 0.92, 0.96),      # 清晨：冷绿
    (9.5, 3, 1.03, 1.02),
    (12.5, 0, 1.08, 1.06),     # 正午：最亮最饱和
    (15.5, 6, 1.05, 1.02),
    (17.8, 14, 1.06, 0.97),    # 傍晚：转暖
    (19.5, 22, 1.02, 0.86),    # 黄昏：暖橙
    (21.5, 10, 0.84, 0.72),
    (24.0, -10, 0.70, 0.58),
)


def _curve_at(hour: float) -> tuple[float, float, float]:
    h = hour % 24.0
    for i in range(len(_TIME_CURVE) - 1):
        h0, d0, s0, v0 = _TIME_CURVE[i]
        h1, d1, s1, v1 = _TIME_CURVE[i + 1]
        if h0 <= h <= h1:
            t = 0.0 if h1 == h0 else (h - h0) / (h1 - h0)
            return (d0 + (d1 - d0) * t, s0 + (s1 - s0) * t, v0 + (v1 - v0) * t)
    return (0.0, 1.0, 1.0)


def _tint(col: QColor, dh: float, sm: float, vm: float) -> QColor:
    h, s, v, a = col.getHsvF()
    if h < 0:
        h = 0.0
    h = (h + dh / 360.0) % 1.0
    return QColor.fromHsvF(h, max(0.0, min(1.0, s * sm)), max(0.0, min(1.0, v * vm)), a)


def palette_at(base: dict, hour: float, season: str | None = None) -> dict:
    """按钟点 + 季节给草皮 / 泥土 / 填充调色，返回调色板副本（不改原对象）。

    两层是叠加的：先季节（这一季的草是什么色），再钟点（这个点的光是什么色）。
    季节不传就是原来那套（工具脚本和旧调用不受影响）。
    """
    dh0, sm0, vm0 = _curve_at(hour)
    dh, sm, vm = dh0, sm0, vm0
    sh, ss, sv = 0.0, 1.0, 1.0
    if season:
        sh, ss, sv = _season.tint(season)
        dh += sh
        sm *= ss
        vm *= sv
    if not season and abs(dh) < 0.05 and abs(sm - 1.0) < 0.005 and abs(vm - 1.0) < 0.005:
        return base
    pal = dict(base)
    if season:
        # 画花的那一层要按季节调整密度，顺着调色板捎过去，免得整条调用链都加参数
        pal["_season"] = season
    for key in ("grass", "dirt"):
        seq = base.get(key)
        if isinstance(seq, list):
            if key == "dirt":
                # 泥土不吃季节的色相：一年四季都是同一块土，冬天只是冷一点、暗一点。
                # 原来照搬草的那套参数，冬天 +22° 把暖棕直接抽成灰黄，看着就像发霉。
                pal[key] = [_tint(QColor(x), dh0 + sh * 0.15,
                                  sm0 * ss ** 0.2, vm0 * sv ** 0.35).name() for x in seq]
            else:
                pal[key] = [_tint(QColor(x), dh, sm, vm).name() for x in seq]
    fill_seq = base.get("fill")
    if isinstance(fill_seq, list):
        pal["fill"] = [_tint(QColor(x), dh, sm, vm).name() for x in fill_seq]
    # 递增版本号：草地那层离屏缓存拿它当 key，比逐个比色值便宜得多
    global _REV
    _REV += 1
    pal["_rev"] = _REV
    return pal


_REV = 0


# ---------------------------------------------------------------- 材质生成
