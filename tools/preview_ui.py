"""渲染主窗各状态 / 各尺寸档的预览图（仅开发用，不参与打包）。

用法：python tools/preview_ui.py
输出：assets/preview_<tier>_<state>.png
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, time
from pathlib import Path

# 用真实平台渲染，offscreen 下拿不到中文字体会渲染成方框

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from app import engine, theme  # noqa: E402
from app.config import Config  # noqa: E402
from app.store import Store  # noqa: E402
from app.widget import TIER_ORDER, TimerWidget  # noqa: E402

OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)

STATES = {
    "working": datetime(2026, 11, 18, 15, 20),
    "morning": datetime(2026, 11, 18, 10, 5),
    "lunch": datetime(2026, 11, 18, 12, 30),
    "overtime": datetime(2026, 11, 18, 19, 10),
    "evening": datetime(2026, 11, 18, 21, 40),
    "weekend": datetime(2026, 11, 21, 10, 0),
    "unset": datetime(2026, 11, 18, 9, 40),
}


def build(cfg_dir: Path, cfg: Config, tier: str):
    store = Store(cfg_dir / "data.json")
    for d in (datetime(2026, 11, 18).date(), datetime(2026, 11, 21).date()):
        store.set_work_start(d, time(9, 0))
    rule = engine.build_rule(cfg)
    w = TimerWidget(cfg, store, rule)
    w.set_tier(tier)
    return w, rule


def render(w: TimerWidget, when: datetime, work_start: time | None) -> QImage:
    w._day = when.date()
    w.snap = engine.snapshot(when, work_start, engine.build_rule(w.cfg))
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
    return img


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    # 用独立配置目录 + 临时数据，避免污染项目的 config.json / data.json
    cfg = Config(tmp / "config.json")
    cfg.set("ui.passthrough_opacity", 0.45)
    cfg.set("ui.pixel_scale", 2)   # 与 2560x1440 实机一致
    cfg.save()

    # README 里引用的几张定名图：标准档三态 + 小/大档
    alias = {
        ("standard", "working"): "preview.png",
        ("standard", "lunch"): "preview_lunch.png",
        ("standard", "overtime"): "preview_overtime.png",
        ("small", "working"): "preview_small.png",
        ("large", "working"): "preview_large.png",
    }

    for tier in TIER_ORDER:
        w, rule = build(tmp, cfg, tier)
        for name, when in STATES.items():
            img = render(w, when, None if name == "unset" else time(9, 0))
            path = OUT / f"preview_{tier}_{name}.png"
            img.save(str(path))
            print("saved", path.name, img.width(), "x", img.height())
            target = alias.get((tier, name))
            if target:
                img.save(str(OUT / target))
        w.deleteLater()


if __name__ == "__main__":
    main()
