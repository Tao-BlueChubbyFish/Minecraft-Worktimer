"""真跑检查：开窗 → 点一遍菜单 → 四个弹窗各调一次 → 验状态。

为什么要有这个文件：`app/ui/interact.py` 里曾经把 `from ..dialogs` 写成
`from .dialogs`，编译能过、静态检查也不报，但**一点菜单就崩**。所以每次改完，
必须把"每个菜单项、每个弹窗各调用一次"跑一遍——这就是那条检查的自动化版本。

用法：
    python tools/_check_ui.py

退出码 0 = 全过。
"""
from __future__ import annotations

import sys
import tempfile
from datetime import date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QDialog, QMenu   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app import __version_label__, dialogs as dlgr, engine, weather, win32  # noqa: E402
from app.config import Config                                                # noqa: E402
from app.store import Store                                                  # noqa: E402
from app.widget import TimerWidget                                           # noqa: E402

seen_dialogs: list[str] = []
seen_menus: list[str] = []


def _stub_exec(self):
    """弹窗一律"点了确定"：这样 accept 分支里的代码也真的跑一遍。"""
    seen_dialogs.append(type(self).__name__)
    if isinstance(self, dlgr.TimeDialog):
        self.result_time = time(9, 30)
    return 1


def _stub_menu(self, *args, **kwargs):
    seen_menus.append("menu")
    return None


QDialog.exec = _stub_exec
QMenu.exec = _stub_menu
# 开机自启会动注册表，这里换成假的：只验通路，不真改系统
win32.autostart_enabled = lambda: False
win32.set_autostart = lambda *a, **k: True


def check_menu(w: TimerWidget) -> None:
    m = w.build_menu()
    titles = [a.text() for a in m.actions()]
    assert any(__version_label__ in t for t in titles), f"菜单里没有版本号：{titles}"
    assert any(t.startswith("今天：") for t in titles), f"菜单里没有「今天：xx」：{titles}"
    assert weather.LABELS[weather.weather_of(w._day)] in "".join(titles)

    fired = []
    for a in m.actions():
        sub = a.menu()
        if sub is not None:                      # 子菜单（窗口尺寸）
            for s in sub.actions():
                s.trigger()
                fired.append(s.text())
            continue
        if not a.isEnabled():                    # 灰显的信息项：只该有字，不该能点
            continue
        a.trigger()
        fired.append(a.text())
    print(f"菜单 {len(titles)} 项，触发 {len(fired)} 项：{' / '.join(fired)}")


def check_dialogs(w: TimerWidget) -> None:
    w.open_time_dialog()
    w.open_settings_dialog()
    w.show_stats()
    w.reset_today()
    for name in ("TimeDialog", "SettingsDialog", "StatsDialog", "ConfirmDialog"):
        assert name in seen_dialogs, f"{name} 没被调用到：{seen_dialogs}"
    print(f"弹窗都调到了：{seen_dialogs}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    cfg = Config(tmp / "config.json")
    cfg.set("ui.pixel_scale", 2)
    # 周六休、周日上班：这是用户实测出来的那种排班
    cfg.set("schedule.workdays", [1, 2, 3, 4, 5, 7])
    cfg.save()

    store = Store(tmp / "data.json")
    w = TimerWidget(cfg, store, engine.build_rule(cfg))
    w._day = datetime.now().date()

    # 1) 三档都能画
    for tier in ("small", "standard", "large"):
        w.set_tier(tier)
        w.update()
    w.set_tier("standard")
    print("三档 ok")

    # 2) 菜单与弹窗（先勾上「记住」：弹窗打开时该是勾着的）
    check_menu(w)
    cfg.set("schedule.remember_start", True)
    cfg.save()
    check_dialogs(w)

    # 3) 自定义休息日：写回配置 + 规则重建，周六 / 周日状态对得上
    assert cfg.get("schedule.workdays") == [1, 2, 3, 4, 5, 7], cfg.get("schedule.workdays")
    sat, sun = date(2026, 11, 21), date(2026, 11, 22)
    assert not w.rule.is_workday(sat), "周六该休息"
    assert w.rule.is_workday(sun), "周日该上班"
    w._day, w.snap = sat, engine.snapshot(datetime(2026, 11, 21, 10, 0),
                                          time(9, 0), w.rule)
    assert w.snap.state == engine.ST_WEEKEND
    w._day, w.snap = sun, engine.snapshot(datetime(2026, 11, 22, 10, 0),
                                          time(9, 0), w.rule)
    assert w.snap.state != engine.ST_WEEKEND
    print("自定义休息日 ok")

    # 4) 记住上班时间：勾上之后不再问
    assert cfg.get("schedule.remember_start") is True, "弹窗里没写回 remember_start"
    assert cfg.get("schedule.default_work_start") == "09:30", cfg.get("schedule.default_work_start")
    print("记住上班时间 ok")

    # 5) 下雨天才开小马达
    w._day = w._day
    print("天气：", weather.LABELS[weather.weather_of(datetime.now().date())])

    # 6) 到点流程 + 午休 + 入夜（各画一帧）
    for when in (datetime(2026, 11, 19, 12, 30), datetime(2026, 11, 19, 18, 5),
                 datetime(2026, 11, 19, 20, 0)):
        w._day = when.date()
        w.snap = engine.snapshot(when, time(9, 0), w.rule)
        w.update()
    print("状态帧 ok")
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
