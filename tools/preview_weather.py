"""渲染各种天气，看看效果（开发自检用，不进打包）。

    python tools/preview_weather.py [输出目录]

输出：clear / cloudy / rain / downpour 四种天气、上午与傍晚两个时段，各自标准档与小档。
雨天还会连出 4 帧，用来确认雨丝真的在动、而且动得够碎；大雨单独出 4 帧。
"""
from __future__ import annotations

import sys
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt                          # noqa: E402
from PySide6.QtGui import QImage, QPainter             # noqa: E402
from PySide6.QtWidgets import QApplication             # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app import engine, theme, weather                  # noqa: E402
from app.config import Config                           # noqa: E402
from app.store import Store                             # noqa: E402
from app.widget import TimerWidget                      # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "assets" / "weather")
OUT.mkdir(parents=True, exist_ok=True)

# 每种天气找一天出来：日期散列决定了哪天是什么天，这里不写死，免得改了权重就断
def _day_for(kind: str, start: date = date(2026, 11, 1)) -> date:
    for i in range(400):
        d = start + timedelta(days=i)
        if weather.weather_of(d) == kind:
            return d
    raise SystemExit(f"400 天里找不到 {kind} 的天气")


DAYS = {k: _day_for(k) for k in ("clear", "cloudy", "rain", "downpour")}


class _Frozen:
    def perf_counter(self) -> float:
        return 0.0

    def time(self) -> float:
        return 0.0


for _name, _mod in list(sys.modules.items()):
    if _name == "app" or _name.startswith("app."):
        if hasattr(_mod, "_time"):
            _mod._time = _Frozen()


def build(tier: str = "standard") -> TimerWidget:
    tmp = Path(tempfile.mkdtemp(prefix="mcw_"))
    cfg = Config(tmp / "config.json")
    cfg.set("ui.pixel_scale", 2)
    cfg.save()
    store = Store(tmp / "data.json")
    w = TimerWidget(cfg, store, engine.build_rule(cfg))
    if tier != "standard":
        w.set_tier(tier)
    return w


def pose(w: TimerWidget, when: datetime) -> None:
    w._day = when.date()
    w.snap = engine.snapshot(when, time(9, 0), w.rule)
    w.store.set_work_start(when.date(), time(9, 0))
    w.snap = engine.snapshot(when, time(9, 0), w.rule)
    w._refresh_palette(when, force=True)


def shoot(w: TimerWidget, name: str, zoom: int = 2) -> None:
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
    big.save(str(OUT / f"{name}.png"))
    print(f"  {name}")


def main() -> None:
    w = build()
    for kind, day in DAYS.items():
        assert weather.weather_of(day) == kind, (day, weather.weather_of(day))
        pose(w, datetime.combine(day, time(10, 20)))
        shoot(w, f"{kind}_morning")
        pose(w, datetime.combine(day, time(17, 40)))
        shoot(w, f"{kind}_evening")

    # 雨丝是否在动：同一秒内取 4 个瞬间
    for kind in ("rain", "downpour"):
        day = DAYS[kind]
        for i in range(4):
            pose(w, datetime.combine(day, time(10, 20, 0, i * 110_000)))
            shoot(w, f"{kind}_frame_{i}")

    small = build("small")
    pose(small, datetime.combine(DAYS["downpour"], time(10, 20)))
    shoot(small, "downpour_small")

    print(f"\n输出目录：{OUT}")


if __name__ == "__main__":
    main()
