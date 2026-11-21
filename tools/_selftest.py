"""无界面自检：跑一遍状态机与绘制，抓异常。"""
from __future__ import annotations

import sys
import tempfile
from datetime import date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from app import engine, theme  # noqa: E402
from app.config import Config  # noqa: E402
from app.store import Store  # noqa: E402
from app.widget import TimerWidget  # noqa: E402


def paint(w, when, start):
    w._day = when.date()
    w.snap = engine.snapshot(when, start, w.rule)
    w.pal = theme.palette_at(w._pal_base, w._visual_hour(when))
    img = QImage(w.W_UNITS * w.S, w.H_UNITS * w.S,
                 QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    w.render_canvas(p, img.width(), img.height())
    p.end()
    return img


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    cfg = Config(tmp / "config.json")
    cfg.set("ui.pixel_scale", 2)
    cfg.save()
    store = Store(tmp / "data.json")
    day = datetime(2026, 11, 19).date()
    store.set_work_start(day, time(9, 0))
    w = TimerWidget(cfg, store, engine.build_rule(cfg))

    # 1) 全天的每个状态都画一遍
    for when in (datetime(2026, 11, 19, 8, 30), datetime(2026, 11, 19, 10, 0),
                 datetime(2026, 11, 19, 12, 30), datetime(2026, 11, 19, 15, 20),
                 datetime(2026, 11, 19, 18, 5), datetime(2026, 11, 19, 20, 0),
                 datetime(2026, 11, 21, 10, 0)):
        paint(w, when, time(9, 0))
    print("paint ok")

    # 2) 里程碑：跨过才响；启动时已经过了的不补响
    w._ms_hit.clear()
    w._ms_seeded = False
    w._fx_kind = ""
    w.snap = engine.snapshot(datetime(2026, 11, 19, 15, 40), time(9, 0), w.rule)
    w._check_milestones()                    # 60% 才启动：25% 是过去的事，不该响
    assert w._fx_kind != "ms", "启动时补响了已过去的里程碑"
    assert 0.25 in w._ms_hit, w._ms_hit

    w._ms_hit.clear()
    w._ms_seeded = False
    w.snap = engine.snapshot(datetime(2026, 11, 19, 10, 50), time(9, 0), w.rule)
    w._check_milestones()                    # 23%：还没到
    assert w._fx_kind != "ms" and not w._ms_hit, (w._fx_kind, w._ms_hit)
    w.snap = engine.snapshot(datetime(2026, 11, 19, 11, 5), time(9, 0), w.rule)
    w._check_milestones()                    # 26%：跨过去了
    assert w._fx_kind == "ms", "里程碑没触发"
    w._check_milestones()
    assert len(w._ms_hit) == 1, w._ms_hit
    print("milestone ok", w._ms_hit)

    # 3) 到点：木牌 → 展开 → 回家
    w._day = day
    w.snap = engine.snapshot(datetime(2026, 11, 19, 18, 1), time(9, 0), w.rule)
    w._update_evening()
    assert w._plank_text, "木牌文案为空"
    w._open_offer()
    assert w._offer_open
    w._choose("home")
    assert store.evening_choice(day) == "home"
    assert w._fx_kind == "home"
    paint(w, datetime(2026, 11, 19, 18, 1), time(9, 0))   # 庆祝帧
    w._fx_kind = ""
    w._plank_text = ""
    paint(w, datetime(2026, 11, 19, 18, 30), time(9, 0))  # 收工帧
    print("home ok")

    # 4) 加班分支
    w._evening_choice = None
    w._choose("overtime")
    assert store.evening_choice(day) == "overtime"
    w.snap = engine.snapshot(datetime(2026, 11, 19, 19, 20), time(9, 0), w.rule)
    paint(w, datetime(2026, 11, 19, 19, 20), time(9, 0))
    print("overtime ok")

    # 5) 自动询问：超时后自动展开
    w2 = TimerWidget(cfg, Store(tmp / "data2.json"), engine.build_rule(cfg))
    w2._day = day
    w2.store.set_work_start(day, time(9, 0))
    w2.snap = engine.snapshot(datetime(2026, 11, 19, 18, 1), time(9, 0), w2.rule)
    w2._update_evening()
    assert w2._offer_t0 > 0
    w2._offer_t0 -= 999                     # 假装过了很久
    w2._update_evening()
    assert w2._offer_open, "超时没有自动展开"
    print("auto offer ok")

    # 6) 小档也要能画
    w.set_tier("small")
    w._evening_choice = None
    w._plank_text = "下班了"
    paint(w, datetime(2026, 11, 19, 18, 1), time(9, 0))
    w._open_offer()
    paint(w, datetime(2026, 11, 19, 18, 1), time(9, 0))
    print("small ok")

    # 7) 配置：午休时长推导结束时间
    cfg.set("schedule.lunch_start", "11:30")
    cfg.set("schedule.lunch_minutes", 90)
    from app.config import _coerce_types
    fixed = _coerce_types(cfg.data)
    assert fixed["schedule"]["lunch_end"] == "13:00", fixed["schedule"]["lunch_end"]
    rule = engine.build_rule(cfg)
    assert engine.fmt_hhmm(rule.lunch_end) == "13:00"
    print("lunch ok", fixed["schedule"]["lunch_start"], fixed["schedule"]["lunch_end"])

    # 8) 自定义休息日：不再是"双休 / 单休"两档，而是七个格子随便点
    from app.config import _workdays
    assert _workdays([1, 2, 3, 4, 5, 7]) == [1, 2, 3, 4, 5, 7]
    assert _workdays([]) == [1, 2, 3, 4, 5], "全空要退回周一到周五"
    assert _workdays([7, 7, 0, 9, "3"]) == [3, 7], "去重 / 越界 / 字符串都要收干净"

    def state_on(wd_list, d):
        r = engine.Rule(offwork=time(18, 0), lunch_start=time(12, 0),
                        lunch_end=time(13, 0), workdays=tuple(wd_list))
        return engine.snapshot(datetime.combine(d, time(10, 0)), time(9, 0), r).state

    sat, sun = date(2026, 11, 21), date(2026, 11, 22)
    # 周六休、周日上班
    assert state_on([1, 2, 3, 4, 5, 7], sat) == engine.ST_WEEKEND, "周六该休息"
    assert state_on([1, 2, 3, 4, 5, 7], sun) != engine.ST_WEEKEND, "周日该上班"
    # 双休
    assert state_on([1, 2, 3, 4, 5], sat) == engine.ST_WEEKEND
    assert state_on([1, 2, 3, 4, 5], sun) == engine.ST_WEEKEND
    # 只休周日
    assert state_on([1, 2, 3, 4, 5, 6], sun) == engine.ST_WEEKEND
    assert state_on([1, 2, 3, 4, 5, 6], sat) != engine.ST_WEEKEND
    print("workdays ok")

    # 9) 记住上班时间：勾上就自动登记、不弹窗；取消勾选回到每天问
    # 这段用"今天"做断言，周末跑会假失败（今天压根不是工作日）：临时把一周都算上班，完事还原
    _days_bak = list(cfg.get("schedule.workdays") or [1, 2, 3, 4, 5])
    cfg.set("schedule.workdays", [1, 2, 3, 4, 5, 6, 7])
    cfg.set("schedule.remember_start", True)
    cfg.set("schedule.default_work_start", "08:40")
    cfg.save()
    w4 = TimerWidget(cfg, Store(tmp / "data4.json"), engine.build_rule(cfg))
    called: list[str] = []
    w4.open_time_dialog = lambda: called.append("dialog")
    w4._maybe_prompt_start()
    assert not called, "勾了「记住」还弹窗"
    today_start = w4.store.work_start(datetime.now().date())
    assert today_start == time(8, 40), f"没按默认时间自动登记：{today_start}"
    # 手动登记过的天不覆盖
    w4.store.set_work_start(datetime.now().date(), time(10, 15))
    assert not w4._apply_remembered_start(datetime.now().date())
    assert w4.store.work_start(datetime.now().date()) == time(10, 15)

    cfg.set("schedule.remember_start", False)
    cfg.save()
    w5 = TimerWidget(cfg, Store(tmp / "data5.json"), engine.build_rule(cfg))
    called5: list[str] = []
    w5.open_time_dialog = lambda: called5.append("dialog")
    w5._maybe_prompt_start()
    assert called5, "没勾「记住」却不问了"
    cfg.set("schedule.workdays", _days_bak)
    cfg.save()
    print("remember ok")

    print("ALL OK")


if __name__ == "__main__":
    main()
