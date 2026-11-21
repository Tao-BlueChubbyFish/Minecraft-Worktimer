"""渲染"一个工作日"的天空时间线（仅开发用，不参与打包）。

用法：python tools/preview_sky.py
输出：assets/sky_timeline.png —— 08:00~21:00 各时刻的进度条并排对比

注意这里走的是 ui.sky_mode=work 的映射：开工天亮、下班入夜。
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from app import engine, pixel_font, theme  # noqa: E402
from app.config import Config  # noqa: E402
from app.store import Store  # noqa: E402
from app.widget import TimerWidget  # noqa: E402

OUT = ROOT / "assets"
MOMENTS = ("08:00", "09:30", "11:00", "13:00", "15:00", "17:00",
           "18:30", "20:00", "21:00")


def render(w: TimerWidget, when: datetime) -> QImage:
    w._day = when.date()
    w.snap = engine.snapshot(when, time(8, 0), engine.build_rule(w.cfg))
    w.pal = theme.palette_at(w._pal_base, w._visual_hour(when))
    img = QImage(w.W_UNITS * w.S, w.H_UNITS * w.S, QImage.Format.Format_ARGB32_Premultiplied)
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
    cfg = Config(tmp / "config.json")
    cfg.set("ui.pixel_scale", 2)
    cfg.save()
    store = Store(tmp / "data.json")
    w = TimerWidget(cfg, store, engine.build_rule(cfg))
    w.set_tier("standard")
    w.snap = engine.snapshot(datetime(2026, 11, 18, 8, 0), time(8, 0),
                             engine.build_rule(cfg))

    # 只截进度条那一行，方便一眼看天色
    S = w.S
    L = w.FULL_LAYOUT
    top = (L["bar_y"] - 2) * S
    height = (L["bar_h"] + 8) * S
    left = (L["pad"] - 4) * S
    width = w.W_UNITS * S - 2 * left
    family = pixel_font.pixel_family()

    rows = []
    for hhmm in MOMENTS:
        h, m = (int(x) for x in hhmm.split(":"))
        img = render(w, datetime(2026, 11, 18, h, m))
        rows.append((hhmm, img.copy(left, top, width, height)))

    gut, gap = 70, 10
    W = gut + width + gap
    H = len(rows) * (height + gap) + gap
    sheet = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    sheet.fill(QColor("#cdd2d8"))
    p = QPainter(sheet)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    y = gap
    for hhmm, img in rows:
        pixel_font.draw_bits(p, 8, y + height // 2 - 3 * S // 2, hhmm, 2,
                            QColor("#33383f"))
        p.drawImage(QPoint(gut, y), img)
        y += height + gap
    p.end()
    sheet.save(str(OUT / "sky_timeline.png"))
    print("ok", sheet.width(), sheet.height())


if __name__ == "__main__":
    main()
