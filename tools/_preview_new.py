"""渲染新版界面各状态（开发自检用）。

python tools/_preview_new.py
输出 assets/new_<name>.png（2 倍放大）
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from app import engine, quotes, theme  # noqa: E402
from app.config import Config  # noqa: E402
from app.store import Store  # noqa: E402
from app.widget import TimerWidget  # noqa: E402

OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)


def build(cfg, store, tier="standard"):
    w = TimerWidget(cfg, store, engine.build_rule(cfg))
    w.set_tier(tier)
    return w


def shot(w, when, start, name, zoom=2):
    w._day = when.date()
    w.snap = engine.snapshot(when, start, w.rule)
    w.pal = theme.palette_at(w._pal_base, w._visual_hour(when))
    img = QImage(w.W_UNITS * w.S, w.H_UNITS * w.S,
                 QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
    w.render_canvas(p, img.width(), img.height())
    p.end()
    big = img.scaled(img.width() * zoom, img.height() * zoom,
                     Qt.AspectRatioMode.IgnoreAspectRatio,
                     Qt.TransformationMode.FastTransformation)
    big.save(str(OUT / f"new_{name}.png"))
    print("saved", name, big.width(), big.height())


def main():
    tmp = Path(tempfile.mkdtemp())
    cfg = Config(tmp / "config.json")
    cfg.set("ui.pixel_scale", 2)
    cfg.save()
    store = Store(tmp / "data.json")
    today = datetime(2026, 11, 19)
    store.set_work_start(today.date(), time(9, 0))
    w = build(cfg, store)

    shot(w, datetime(2026, 11, 19, 10, 20), time(9, 0), "morning")
    shot(w, datetime(2026, 11, 19, 16, 10), time(9, 0), "afternoon")

    # 里程碑：跨 75%
    w._ms_hit = {0.25, 0.75}
    w._fx_kind, w._fx_t, w._fx_dur = "ms", 0.12, 1.4
    w._roll_lift = 2
    w._greet_text = quotes.milestone_text(0.76, today.date())
    w._greet_until = 1e18
    shot(w, datetime(2026, 11, 19, 15, 30), time(9, 0), "milestone")
    w._fx_kind, w._roll_lift, w._greet_text, w._greet_until = "", 0, "", 0.0

    # 到点：木牌
    w._plank_text = quotes.plank_text(today.date())
    w._evening_choice = None
    shot(w, datetime(2026, 11, 19, 18, 1), time(9, 0), "plank")

    # 悬停（描边亮 + 箭头常亮）
    w._plank_hover = True
    shot(w, datetime(2026, 11, 19, 18, 3), time(9, 0), "plank_hover")
    w._plank_hover = False

    # 展开选项
    w._offer_open = True
    w._plank_text = "还干吗"
    w._choice_hover = 0
    shot(w, datetime(2026, 11, 19, 18, 12), time(9, 0), "offer")

    # 回家庆祝
    w._offer_open = False
    w._choice_hover = -1
    w._evening_choice = "home"
    w._plank_text = quotes.cheer_text(today.date())
    w._fx_kind, w._fx_dur = "home", 5.0
    for tt in (0.22, 0.5, 0.8):
        w._fx_t = tt
        shot(w, datetime(2026, 11, 19, 18, 3), time(9, 0), f"celebrate_{int(tt*100)}")

    # 选了回家，庆祝结束
    w._fx_kind, w._plank_text = "", ""
    shot(w, datetime(2026, 11, 19, 18, 30), time(9, 0), "home_done")

    # 选了加班
    w._evening_choice = "overtime"
    shot(w, datetime(2026, 11, 19, 19, 40), time(9, 0), "overtime")

    # 小档
    w._evening_choice = None
    w._plank_text = ""
    small = build(cfg, store, "small")
    shot(small, datetime(2026, 11, 19, 10, 20), time(9, 0), "small")
    small._plank_text = "下班了"
    small._evening_choice = None
    shot(small, datetime(2026, 11, 19, 18, 1), time(9, 0), "small_plank")


if __name__ == "__main__":
    main()
