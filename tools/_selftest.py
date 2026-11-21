"""无界面自检：跑一遍状态机与绘制，抓异常。"""
from __future__ import annotations

import sys
import tempfile
from datetime import date, datetime, time, timedelta
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

    # 10) v1.1 累计与周视图：只读推算，不加班的天不能漏、休息日必须留空
    st6 = Store(tmp / "data6.json")
    rule6 = engine.build_rule(cfg)
    st6.set_work_start(date(2026, 11, 16), time(9, 0))
    st6.set_work_start(date(2026, 11, 17), time(9, 0))
    st6.set_work_start(date(2026, 11, 18), time(9, 30))
    st6.data["ledger"]["2026-11-17"] = 45
    st6.data["cumulative_overtime_minutes"] = 45  # 与 ledger 同步，模拟真实结算
    base6 = int(round(rule6.onsite_hours * 60))
    assert st6.worked_days() == 3, st6.worked_days()
    assert st6.worked_minutes(rule6) == 3 * base6 + 45
    assert st6.day_minutes(date(2026, 11, 19), rule6) is None, "没登记的天不该有工时"
    assert st6.day_minutes(date(2026, 11, 17), rule6) == base6 + 45
    # 今天有实时加班时，不能把 ledger 里那笔再加一遍（ledger 只存已结算的）
    assert st6.day_minutes(date(2026, 11, 17), rule6, 30) == base6 + 75
    week = st6.week_minutes(date(2026, 11, 18), rule6)
    assert len(week) == 7 and week[0][0] == date(2026, 11, 16), "周视图没从周一起头"
    assert week[3][1] is None, "周四没登记，应留空"
    st6.data["days_archived"] = 10
    assert st6.worked_days() == 13, "修剪归档的天数丢了"
    st6.data["days_archived"] = 0

    # 上周合计 / 到岗规律 / 随手小记
    assert st6.week_total(date(2026, 11, 16), rule6, date(2026, 11, 18)) == 3 * base6 + 45
    assert st6.week_total(date(2026, 11, 9), rule6, date(2026, 11, 18)) == 0
    # 到岗规律：样本不足 5 天不叫"常说"
    assert st6.typical_start(date(2026, 11, 21)) is None, "3 天样本不该说「常在」"
    st6.set_work_start(date(2026, 11, 19), time(9, 0))
    st6.set_work_start(date(2026, 11, 20), time(9, 0))
    assert st6.typical_start(date(2026, 11, 21)) == time(9, 0), st6.typical_start(date(2026, 11, 21))
    st6.set_note(date(2026, 11, 21), "今天开会开了两小时")
    assert st6.note(date(2026, 11, 21)) == "今天开会开了两小时"
    st6.set_note(date(2026, 11, 21), "   ")
    assert st6.note(date(2026, 11, 21)) == "", "清空小记没生效"
    print("totals ok")

    # 11) v1.1 两个新面板：菜单项在、弹窗能画出来（不 show，直接渲染）
    m6 = w6 = None
    w6 = TimerWidget(cfg, Store(tmp / "data7.json"), engine.build_rule(cfg))
    m6 = w6.build_menu()
    labels = [a.text() for a in m6.actions()]
    assert "今日结算…" in labels, labels
    assert "一周…" in labels, labels
    assert "记一句…" in labels, labels

    from app.dialogs import DayDialog, NoteDialog, WeekDialog  # noqa: E402

    now6 = datetime.now()
    for cls in (DayDialog, WeekDialog):
        dlg = cls(w6, cfg, w6.pal, w6._base_s, w6._dpr, w6.store, w6.rule, now6, 0)
        img = QImage(dlg.width(), dlg.height(), QImage.Format.Format_ARGB32)
        img.fill(0)
        dlg.render(img)
        assert not img.isNull(), f"{cls.__name__} 渲染失败"
        dlg.close()

    nd = NoteDialog(w6, cfg, w6.pal, w6._base_s, w6._dpr, "写点啥")
    assert nd.text() == "写点啥"
    nd.close()

    # 12) 累计里程碑：第一次静默播种（过去的事不补庆祝），之后只在刚达成时响一次
    w6.store = st6
    st6.data["schedule"].clear()
    for i in range(10):
        st6.data["schedule"][(date(2026, 10, 1) + timedelta(days=i)).isoformat()] = "09:00"
    st6.data["milestones"] = []
    w6._tot_seeded = False
    w6._tot_day = None
    w6._check_total_milestone(datetime.now())
    assert "d10" in st6.data["milestones"], "首次运行没把已达成的静默记为已响"
    st6.data["milestones"].remove("d10")
    w6._tot_day = None
    w6._check_total_milestone(datetime.now())
    assert "d10" in st6.data["milestones"], "满 10 天没有响"
    w6._tot_day = None
    said = list(st6.data["milestones"])
    w6._check_total_milestone(datetime.now())
    assert st6.data["milestones"] == said, "同一个里程碑响了两次"
    print("milestone ok")

    print("panels ok")

    print("ALL OK")


if __name__ == "__main__":
    main()
