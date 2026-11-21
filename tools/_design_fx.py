"""设计预览：F1 下班瞬间 / F2 里程碑花瓣 / F3 时段问候（只渲染，不改 app 逻辑）。

用法：python tools/_design_fx.py
输出：assets/design/fx_*.png（窗口 2 倍放大）
"""
from __future__ import annotations

import math
import sys
import tempfile
from datetime import datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from app import engine, pixel_font, theme  # noqa: E402
from app.config import Config  # noqa: E402
from app.store import Store  # noqa: E402
from app.widget import TimerWidget  # noqa: E402

OUT = ROOT / "assets" / "design"
OUT.mkdir(parents=True, exist_ok=True)
FAMILY = "Microsoft YaHei"

WHITE = QColor("#ffffff")
GOLD = QColor("#ffd75e")
AMBER = QColor("#e89a3c")


def bar_geom(x, y, w, h, s):
    ix, iy = x + s, y + s
    iw, ih = w - 2 * s, h - 2 * s
    uh = max(5, ih // s)
    if uh >= 16:
        grass_u, dirt_u = 4, 6
    elif uh >= 12:
        grass_u, dirt_u = 3, 4
    else:
        grass_u, dirt_u = 2, max(2, uh - 7)
    ground_u = min(uh - 2, grass_u + dirt_u)
    sky_u = uh - ground_u
    return ix, iy, iw, ih, sky_u, ground_u, grass_u


# ------------------------------------------------------------------ F2 花瓣
def draw_petals(p, cx, gy, s, seed_day, t):
    """达成瞬间：卷顶闪一下白光，几片花瓣贴着卷冒出来再落回去。

    不能飞进"天空"——那片天被花冠占满了，点进去就糊成花海的一部分。卷脚
    特意留了 2 列裸草，花瓣只有落在这个十字范围内才读得出来。
    """
    picks = theme._day_picks(seed_day)
    cols = [QColor(theme._PETAL_COLORS[i]) for i in picks]
    if t < 0.12:
        theme.fill(p, cx - s, gy - 2 * s, 2 * s, s, WHITE)
        theme.fill(p, cx, gy - 4 * s, s, s, WHITE)
        return
    tt = (t - 0.12) / 0.88
    n = 9
    for i in range(n):
        vx = (i - (n - 1) / 2) * 0.86
        peak = 2.2 + (i % 3) * 0.7
        px = cx + vx * tt * s
        py = gy - s - 4 * peak * tt * (1 - tt) * s
        if tt > 0.72 and i % 2:
            continue
        col = WHITE if tt < 0.14 else cols[i % len(cols)]
        theme.fill(p, int(round(px)), int(round(py)), s, s, col)


# ------------------------------------------------------------------ F1 烟花
def draw_sparkle(p, cx, cy, s, arm, col, core=WHITE):
    """像素十字星芒：中心 + 四向伸出的手臂。

    圆环烟花在灰面板上太淡、太碎，读起来像脏点；十字星只有 5~9 个像素，
    轮廓本身就认得出来，是像素游戏里通用的"闪一下"。
    """
    theme.fill(p, cx, cy, s, s, core)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for k in range(1, arm + 1):
            theme.fill(p, cx + dx * k * s, cy + dy * k * s, s, s,
                       core if k == 1 else col)


# ------------------------------------------------------------------ F1 木牌
def draw_sign(p, cx, bottom, s, pal, text, rise, hidden_bottom):
    """一块木牌从进度条里升上来，停在大号数字那一行。"""
    tw, _ = pixel_font.measure_cjk(text, 11 * s, FAMILY, bold=True)
    wu = max(30, tw // s + 17)
    hu = 17
    r = max(0.0, min(1.0, rise))
    ease = 1.0 - (1.0 - r) ** 2
    bot = hidden_bottom + (bottom - hidden_bottom) * ease
    x = cx - wu * s // 2
    y = int(round(bot)) - hu * s
    o = 2 * s

    theme.fill(p, x, y, wu * s, hu * s, QColor(pal["dirt"][2]))
    theme.fill(p, x, y, wu * s, s, QColor(pal["dirt"][4]))
    theme.fill(p, x, y + hu * s - s, wu * s, s, QColor(pal["dirt"][1]))
    theme.fill(p, x, y, wu * s, o, QColor(pal["outline"]))
    theme.fill(p, x, y + hu * s - o, wu * s, o, QColor(pal["outline"]))
    theme.fill(p, x, y, o, hu * s, QColor(pal["outline"]))
    theme.fill(p, x + wu * s - o, y, o, hu * s, QColor(pal["outline"]))
    nail = QColor(pal["bevel_light"])
    for nx in (x + 3 * s, x + wu * s - 4 * s):
        for ny in (y + 3 * s, y + hu * s - 4 * s):
            theme.fill(p, nx, ny, s, s, nail)
    pixel_font.draw_cjk_vcenter(p, x + (wu * s - tw) // 2, y + o, hu * s - 2 * o,
                                text, 11 * s, QColor(pal["text_on_grass"]),
                                FAMILY, shadow=QColor(pal["text_shadow"]), bold=True)


FANCY = {"petals": None, "sign": None, "fw": None, "exit": False,
         "sign_bottom": 0, "sign_clip": None, "fw_pos": (),
         "lift": 0, "gold": False}
GREETING = {"text": ""}


def patch():
    """把三处新东西挂到现有绘制路径上（仅预览用）。"""
    orig_v = pixel_font.draw_cjk_vcenter

    def v(p, x, top, bh, text, *a, **kw):
        if GREETING["text"] and text == "工作计时":
            text = GREETING["text"]
        return orig_v(p, x, top, bh, text, *a, **kw)

    pixel_font.draw_cjk_vcenter = v

    orig_bits = pixel_font.draw_bits

    def bits(p, x, y, text, k, color, *a, **kw):
        if FANCY["gold"] and text.endswith("%"):
            sh = QColor("#8a6b1f")
            orig_bits(p, x + max(1, k // 4), y + max(1, k // 4), text, k, sh, *a, **kw)
            return orig_bits(p, x, y, text, k, GOLD, *a, **kw)
        return orig_bits(p, x, y, text, k, color, *a, **kw)

    pixel_font.draw_bits = bits

    orig_content = TimerWidget._content

    def content(self):
        c = dict(orig_content(self))
        if FANCY["sign"] is not None:      # 庆祝期间数字行让位给木牌
            c["value"] = []
            c["label"] = ""
        return c

    TimerWidget._content = content

    orig_mb = theme.draw_meadow_bar

    def mb(p, x, y, w_, h_, s, pal, ratio, **kw):
        if FANCY["lift"]:
            kw = dict(kw, roll_lift=FANCY["lift"], roll_phase=0.0)
        orig_mb(p, x, y, w_, h_, s, pal, ratio, **kw)
        ix, iy, iw, ih, sky_u, ground_u, grass_u = bar_geom(x, y, w_, h_, s)
        gy = iy + sky_u * s
        if not (FANCY["exit"] or FANCY["petals"] is not None):
            return
        p.save()
        p.setClipRect(QRect(ix, iy, iw, ih))
        if FANCY["exit"]:                  # 卷正滚出右边缘
            theme._sod_roll(p, ix + iw + s, gy, s, pal, grass_u, 0.0, 0, 0, 1.0)
        if FANCY["petals"] is not None:
            draw_petals(p, ix + int(round(iw * ratio)), gy, s,
                        kw.get("seed_day", 0), FANCY["petals"])
        p.restore()

    theme.draw_meadow_bar = mb


def build():
    tmp = Path(tempfile.mkdtemp())
    cfg = Config(tmp / "config.json")
    cfg.set("ui.pixel_scale", 2)
    cfg.save()
    w = TimerWidget(cfg, Store(tmp / "data.json"), engine.build_rule(cfg))
    w.set_tier("standard")
    return w


def render(w, when, start, greeting, petals=None, sign=None, fw=None, exit_=False,
           lift=0, gold=False):
    GREETING["text"] = greeting
    L = w._layout()
    top = w.u(L["label_bottom"])
    FANCY.update(petals=petals, sign=sign, fw=fw, exit=exit_, lift=lift, gold=gold,
                 sign_bottom=w.u(L["value_bottom"]),
                 sign_clip=QRect(0, top, w.W_UNITS * w.S,
                                 w.u(L["bar_y"]) + w.u(L["bar_h"]) - top),
                 fw_pos=((int(w.W_UNITS * w.S * 0.30), w.u(43), 2, 0.2),
                         (int(w.W_UNITS * w.S * 0.70), w.u(43), 2, 0.2),
                         (int(w.W_UNITS * w.S * 0.22), w.u(50), 1, 0.6),
                         (int(w.W_UNITS * w.S * 0.79), w.u(49), 1, 0.6)))
    w._day = when.date()
    w.snap = engine.snapshot(when, start, engine.build_rule(w.cfg))
    w.pal = theme.palette_at(w._pal_base, w._visual_hour(when))
    img = QImage(w.W_UNITS * w.S, w.H_UNITS * w.S,
                 QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
    w.render_canvas(p, img.width(), img.height())
    # ---- 覆盖层（在整窗之上画，才能盖住数字、伸到面板空白处）
    if FANCY["sign"] is not None:
        p.save()
        p.setClipRect(FANCY["sign_clip"])
        draw_sign(p, img.width() // 2, FANCY["sign_bottom"], w.S, w.pal, "收工",
                  FANCY["sign"], FANCY["sign_bottom"] + 20 * w.S)
        p.restore()
    if FANCY["fw"] is not None:
        for i, (fx, fy, arm, t) in enumerate(FANCY["fw_pos"]):
            draw_sparkle(p, fx, fy, w.S, arm, GOLD if t > 0.35 else WHITE)
    p.end()
    return img


def main():
    patch()
    w = build()
    frames = [
        ("fx_1_greeting", datetime(2026, 11, 19, 9, 24), time(9, 0), "开工了",
         None, None, None, False),
        ("fx_2_milestone", datetime(2026, 11, 19, 14, 2), time(9, 0), "走了一半",
         None, None, None, False, 2, True),
        ("fx_3_done", datetime(2026, 11, 19, 18, 1), time(9, 0), "该回家了",
         None, 1.0, 0.5, True),
    ]
    for f in frames:
        name, when, start, greet, petals, sign, fw, ex = f[:8]
        extra = f[8:]
        img = render(w, when, start, greet, petals, sign, fw, ex,
                     *(extra or (0, False)))
        big = img.scaled(img.width() * 2, img.height() * 2,
                         Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.FastTransformation)
        big.save(str(OUT / f"{name}.png"))
        print("saved", name, big.width(), big.height())


if __name__ == "__main__":
    main()
