"""对照底片：把界面每个状态渲染成 PNG，用于改动前后逐像素比对。

这不是程序的一部分，只是"检查用的相机"。

用法：
    python tools/baseline_shots.py <输出目录> [--season=spring|summer|autumn|winter]

要点：
* 全部用固定日期（2026-11-19 周四 / 11-21 周六），文案与花海按日期取种子，
  所以同一状态下每次拍出来的图完全一样。
* 把"现在几点"冻住（见 _FrozenTime）：木牌右侧那颗闪烁的小箭头按秒数交替，
  不冻住就会出现"两张图差一个箭头"的假警报。
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

# 别用离屏(offscreen)模式：那种模式下系统字体一个都读不到，中文会变成方框。
# 这里只是构造窗口对象、不调用 show()，屏幕上不会弹出任何东西。
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt                       # noqa: E402
from PySide6.QtGui import QImage, QPainter          # noqa: E402
from PySide6.QtWidgets import QApplication          # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app import engine, quotes, theme, widget as widget_mod   # noqa: E402
from app.config import Config                                 # noqa: E402
from app.store import Store                                   # noqa: E402
from app.widget import TimerWidget                            # noqa: E402


class _FrozenTime:
    """冻住"现在几点"，让闪烁类装饰也变成固定画面。"""

    def perf_counter(self) -> float:
        return 0.0

    def time(self) -> float:
        return 0.0


def _freeze_time() -> None:
    """把所有 app 模块里引用的 time 都换成冻住的版本。

    木牌右侧那颗小箭头按系统秒数交替亮灭，不冻住就拍不出同一张图。
    代码拆成多个文件后，每个文件各自 import 过一次 time，所以这里挨个替换。
    """
    frozen = _FrozenTime()
    for name, mod in list(sys.modules.items()):
        if name == "app" or name.startswith("app."):
            if hasattr(mod, "_time"):
                mod._time = frozen


_freeze_time()

# 四个季节各用一组同星期几的固定日期：季节换色换雪以后，只靠一套秋天的底片
# 就没法验证"改夏天有没有碰坏冬天"。--season 决定拍哪一季。
SEASON_DAYS = {
    "spring": (date(2026, 4, 16), date(2026, 4, 18)),
    "summer": (date(2026, 7, 16), date(2026, 7, 18)),
    "autumn": (date(2026, 11, 19), date(2026, 11, 21)),
    "winter": (date(2026, 12, 17), date(2026, 12, 19)),
}
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
_season = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--season=")), "autumn")
if _season not in SEASON_DAYS:
    raise SystemExit(f"--season 只能是 {', '.join(SEASON_DAYS)}")

DAY, SAT = SEASON_DAYS[_season]     # 周四 / 周六
WORK_START = time(9, 0)

OUT = Path(_args[0] if _args else ROOT / "assets" / "baseline")
OUT.mkdir(parents=True, exist_ok=True)

_count = 0


def fresh(sub: str, with_start: bool = True, tune=None) -> TimerWidget:
    """干净的窗口：一份临时配置、一份临时使用记录。"""
    tmp = Path(tempfile.mkdtemp(prefix="mcb_", dir=None)) / sub
    tmp.mkdir(parents=True, exist_ok=True)
    cfg = Config(tmp / "config.json")
    cfg.set("ui.pixel_scale", 2)
    if tune is not None:
        tune(cfg)
    cfg.save()
    store = Store(tmp / "data.json")
    if with_start:
        store.set_work_start(DAY, WORK_START)
        store.set_work_start(SAT, WORK_START)
    return TimerWidget(cfg, store, engine.build_rule(cfg))


def pose(w: TimerWidget, when: datetime) -> None:
    """把窗口摆到某个时刻的状态。"""
    w._day = when.date()
    w.snap = engine.snapshot(when, w.store.work_start(when.date()), w.rule)
    w._refresh_palette(when, force=True)


def shoot(w: TimerWidget, name: str, zoom: int = 2) -> None:
    global _count
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
    _count += 1
    print(f"  {name:22s} {img.width():4d}x{img.height():4d}")


def DT(h: int, m: int) -> datetime:
    """这一天（DAY）的 h:m。底片要按季节换日期，所以时刻不能写死。"""
    return datetime.combine(DAY, time(h, m))


def time_at_ratio(rule, ratio: float) -> datetime:
    """找出进度条最接近某个百分比的时刻（用来拍 19% / 53% / 84% 的道具）。"""
    best = None
    base = datetime.combine(DAY, WORK_START)
    for m in range(0, 9 * 60 + 1):
        when = base + timedelta(minutes=m)
        snap = engine.snapshot(when, WORK_START, rule)
        d = abs(snap.progress - ratio)
        if best is None or d < best[0]:
            best = (d, when)
    return best[1]


def main() -> None:
    w = fresh("main")

    print("基本一天")
    for name, when in (("01_before", DT(8, 30)),
                       ("02_morning", DT(10, 20)),
                       ("03_lunch", DT(12, 30)),
                       ("04_afternoon", DT(16, 10))):
        pose(w, when)
        shoot(w, name)

    print("道具出现：19% / 53% / 84%")
    for label, r in (("19", 0.19), ("53", 0.53), ("84", 0.84)):
        pose(w, time_at_ratio(w.rule, r))
        shoot(w, f"05_props_{label}")

    print("草皮卷正在滚动的中间帧")
    w._animating = True
    w._anim_ratio = 0.55
    w._roll_lift = 1
    pose(w, DT(14, 0))
    shoot(w, "06_rolling")
    w._animating = False
    w._roll_lift = 0

    print("里程碑 / 开场问候")
    w._ms_hit = {0.25, 0.75}
    w._fx_kind, w._fx_t, w._fx_dur = "ms", 0.12, 1.4
    w._roll_lift = 2
    w._greet_text = quotes.milestone_text(0.76, DAY)
    w._greet_until = 1e18
    pose(w, DT(15, 30))
    shoot(w, "07_milestone")
    w._fx_kind, w._fx_t, w._roll_lift = "", 0.0, 0
    w._greet_text = quotes.greeting(engine.ST_WORKING, DT(9, 5),
                                    w.rule.lunch_start)
    w._greet_until = 1e18
    pose(w, DT(9, 6))
    shoot(w, "08_greeting")
    w._greet_text, w._greet_until = "", 0.0

    print("鸟群三种队形位置")
    for fl in (0.2, 0.5, 0.8):
        pose(w, DT(11, 0))
        w._fx_kind, w._fx_dur, w._fx_t = "life", 17.0, fl
        shoot(w, f"09_birds_{int(fl * 100)}")
    w._fx_kind, w._fx_t = "", 0.0

    print("到点：木牌 / 悬停 / 展开")
    pose(w, DT(18, 1))
    w._evening_choice = None
    w._offer_open = False
    w._plank_text = ""
    shoot(w, "10_plank")
    w._plank_hover = True
    shoot(w, "11_plank_hover")
    w._plank_hover = False
    w._open_offer()
    w._choice_hover = 0
    shoot(w, "12_offer_home")
    w._choice_hover = 1
    shoot(w, "13_offer_overtime")
    w._choice_hover = -1
    w._offer_open = False

    print("选回家：庆祝四帧")
    w._evening_choice = "home"
    w._plank_text = quotes.cheer_text(DAY)
    w._fx_kind, w._fx_dur = "home", 5.0
    for tt in (0.18, 0.42, 0.66, 0.90):
        w._fx_t = tt
        pose(w, DT(18, 3))
        shoot(w, f"14_celebrate_{int(tt * 100)}")
    w._fx_kind, w._fx_t, w._plank_text = "", 0.0, ""

    print("收工后 / 加班中 / 入夜")
    pose(w, DT(18, 30))
    shoot(w, "15_home_done")
    w._evening_choice = "overtime"
    pose(w, DT(19, 40))
    shoot(w, "16_overtime")
    pose(w, DT(20, 30))
    shoot(w, "17_night")

    print("休息日 / 未设置 / 穿透锁定")
    pose(w, datetime.combine(SAT, time(11, 0)))
    w._evening_choice = None
    w._plank_text = ""
    shoot(w, "18_weekend")

    unset = fresh("unset", with_start=False)
    pose(unset, DT(10, 20))
    shoot(unset, "19_unset")

    w._pt_active = True
    pose(w, DT(10, 20))
    shoot(w, "20_passthrough")
    w._pt_active = False

    print("进度条另一种样式（纯色）")
    plain = fresh("plain", tune=lambda c: c.set("ui.progress_style", "plain"))
    pose(plain, DT(10, 20))
    shoot(plain, "21_plain_bar")

    print("小档")
    sm = fresh("small")
    sm.set_tier("small")
    pose(sm, DT(10, 20))
    shoot(sm, "22_small")
    pose(sm, DT(18, 1))
    sm._evening_choice = None
    sm._plank_text = ""
    shoot(sm, "23_small_plank")
    sm._open_offer()
    sm._choice_hover = 0
    shoot(sm, "24_small_offer")

    print(f"\n共 {_count} 张 → {OUT}")


if __name__ == "__main__":
    main()
