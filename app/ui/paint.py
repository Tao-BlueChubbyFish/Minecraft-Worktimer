"""画面绘制：整窗画面、木牌、两个选项、庆祝动画的组装与坐标。"""
from __future__ import annotations

import time as _time
from datetime import datetime
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter
from .. import engine, life, pixel_font, quotes, theme, weather
from .consts import TIERS, TIER_ORDER, WEEK_CN  # noqa: F401


class PaintMixin:

    def _plank_metrics(self) -> tuple[str, int, int, int]:
        """(文案, 字号, 宽, 高)——绘制和命中区都从这里取，避免两处算不一致。"""
        text = self._plank_text or quotes.plank_text(self._day)
        if self._compact:
            th, pad_x, hu = 9, 12, 14
        else:
            th, pad_x, hu = 11, 17, 17
        tw, _ = pixel_font.measure_cjk(text, self.u(th), self.family, bold=True)
        return text, th, tw + self.u(pad_x), self.u(hu)


    def _plank_rect_px(self) -> QRect:
        _text, _th, w, h = self._plank_metrics()
        y = self.u(self._layout()["value_bottom"]) - h
        return QRect((self.u(self.W_UNITS) - w) // 2, y, w, h)


    def _choice_rects_px(self) -> tuple[QRect, QRect]:
        wpx = self.u(self.W_UNITS)
        if self._compact:                     # 小档没有底栏，两个按钮挤在数值行
            pad, gap, y, h = self.u(6), self.u(5), self.u(19), self.u(14)
        else:
            pad, gap, y, h = self.u(10), self.u(8), self.u(93), self.u(20)
        bw = (wpx - 2 * pad - gap) // 2
        return (QRect(pad, y, bw, h),
                QRect(pad + bw + gap, y, bw, h))


    def _draw_plank(self, p: QPainter, S: int, pal: dict) -> None:
        text, th, _w, _h = self._plank_metrics()
        r = self._plank_rect_px()
        gold = self._fx_kind == "home"
        theme.draw_plank(p, r.x(), r.y(), r.width(), r.height(), S, pal, text,
                         self.family, hot=self._plank_hover, gold=gold, text_h=th)
        # 可点的暗示：右端一颗慢慢闪的小箭头（不写字，靠动作提示）
        if not self._evening_choice and not self._offer_open:
            if self._plank_hover or int(_time.perf_counter() * 1.4) % 2 == 0:
                col = QColor(pal["accent"]).lighter(118)
                ax = r.right() + 3 * S
                ay = r.center().y()
                for i in range(3):
                    theme.fill(p, ax + i * S, ay - (2 - i) * S, S, S, col)
                    theme.fill(p, ax + i * S, ay + (2 - i) * S, S, S, col)


    def _draw_choices(self, p: QPainter, S: int, pal: dict, W: int) -> None:
        if not self._compact:
            pad = self.u(8)
            top = self.u(85)
            hgt = self.u(124) - top
            theme.draw_sunken(p, pad, top, W - 2 * pad, hgt, S, pal)
        for i, r in enumerate(self._choice_rects_px()):
            theme.draw_choice(p, r.x(), r.y(), r.width(), r.height(), S, pal,
                              "回家" if i == 0 else "再干会儿", self.family,
                              primary=(i == 0), hover=(self._choice_hover == i))


    def _draw_celebrate(self, p: QPainter, W: int, H: int, S: int) -> None:
        """回家那一刻的 5 秒：六簇烟花错峰炸开 + 彩纸一路飘落。

        起手不铺白闪：整窗提亮一下等于把界面洗掉一帧，看着像闪屏而不是庆祝。
        """
        t = self._fx_t
        theme.draw_confetti(p, W, H, S, t, self._day.toordinal(), top=0, count=44)
        bursts = ((0.16, 0.30, 0.00, "#ffd75e", 12.0), (0.84, 0.26, 0.10, "#f4a8c0", 10.0),
                  (0.50, 0.36, 0.20, "#9ec5ff", 13.0), (0.28, 0.22, 0.32, "#ffffff", 9.0),
                  (0.72, 0.20, 0.38, "#ffd75e", 11.0), (0.50, 0.56, 0.52, "#b6f0a0", 8.0))
        for fx, fy, delay, col, rad in bursts:
            tt = (t - delay) / 0.5
            if 0.0 <= tt <= 1.0:
                theme.draw_firework(p, int(W * fx), int(H * fy), S, tt, QColor(col),
                                    radius=rad)

    # ---------------------------------------------------------------- 绘制


    def render_canvas(self, p: QPainter, w: int, h: int) -> None:
        S = self.S
        pal = self.pal
        W = w
        H = h
        L = self._layout()
        content = self._content()

        # 像素投影（右下 2 单位的硬阴影，比模糊阴影更像原版）
        off = 2 * S
        p.fillRect(QRect(off, off, W, H), QColor(0, 0, 0, 48))

        theme.draw_panel(p, 0, 0, W, H, S, pal, kind="panel")

        # 顶部草皮：冬天的雪在标题这一带压薄，否则白字压在白雪上读不出来。
        # 标题要先算宽度，草皮才知道该让开哪一段，所以这段量字的逻辑提前到画草皮之前。
        hh = self.u(L["header"])
        btn = self._btn_rect_px()
        # 紧凑档没有标签行，标题位改放状态文案（省一行高度）；长文案自动降档字号
        if self._compact:
            title_text = content.get("label_short") or content["label"]
        else:
            title_text = content.get("title") or "工作计时"
        tx = self.u(L["title_x"])
        avail_t = max(1, btn.x() - tx - self.u(4))
        tsize = L["title"]
        tw, _th = pixel_font.measure_cjk(title_text, self.u(tsize), self.family, bold=True)
        while tsize > 8 and tw > avail_t:
            tsize -= 1
            tw, _th = pixel_font.measure_cjk(title_text, self.u(tsize), self.family,
                                             bold=True)
        # 雪厚跟着当天的天：大雪最厚、小雪次之、晴阴只留一层残雪。
        # 等 v1.3 接了真实天气，这里改看气温——暖冬不下雪，就不用画这一层。
        snow_cap = None
        if (pal.get("_season") or "") == "winter":
            snow_cap = {weather.BLIZZARD: 6, weather.SNOWY: 5,
                        weather.CLOUDY: 3}.get(weather.weather_of(self._day), 2)
        theme.draw_grass_strip(p, W, hh, S, pal, keep_clear=(tx - S, tx + tw + S),
                               snow_cap=snow_cap)
        theme.fill(p, 0, hh, W, S, QColor(pal["outline"]))

        # 图标 + 标题 / 状态文案 + 右上角菜单按钮：三者共用草皮带的一条中线
        icon_u = L["icon"]
        theme.draw_image_outlined(p, self.u(7 if not self._compact else 5),
                                  self.u((L["header"] - icon_u) // 2),
                                  self.u(icon_u), theme.iso_block(pal), S, pal,
                                  outline=False)

        theme.draw_button(p, btn.x(), btn.y(), btn.width(), btn.height(), S, pal,
                          pressed=False, hover=self._hover_btn)
        theme.draw_menu_icon(p, btn.x() + (btn.width() - 9 * S) // 2,
                             btn.y() + (btn.height() - 9 * S) // 2, S,
                             QColor(pal["outline"]))

        # 按墨迹居中：不同字号下墨迹上下留白一致，不会像以前那样顶到上边框
        p.save()
        p.setClipRect(QRect(tx, self.u(1), avail_t, max(1, hh - self.u(2))))
        pixel_font.draw_cjk_vcenter(p, tx, 0, hh, title_text, self.u(tsize),
                                    QColor(pal["text_on_grass"]), self.family,
                                    shadow=QColor(pal["text_shadow"]), bold=True)
        p.restore()

        # ---- 正文
        pad = self.u(L["pad"])
        center_x = W // 2
        cx_right = W - pad

        # 小标签（居中，仅完整布局）
        if L["label_size"]:
            label_size = L["label_size"]
            _, lh = pixel_font.measure_cjk(content["label"], self.u(label_size),
                                           self.family, bold=True)
            pixel_font.draw_cjk(p, 0, self.u(L["label_bottom"]) - lh,
                                content["label"], self.u(label_size),
                                QColor(content.get("label_color", pal["text_dim"])),
                                self.family, bold=True, align="center", max_w=W)

        # 主数值
        self._draw_items(p, center_x, self.u(L["value_bottom"]),
                         content["value"], QColor(content.get("value_color", pal["text"])))

        # 进度条（比正文宽 4 单位：左右各缩 4，天空和花海都多一点地方）
        bar_y = self.u(L["bar_y"])
        bar_h = self.u(L["bar_h"])
        bar_pad = self.u(L.get("bar_pad", L["pad"]))
        bar_w = W - 2 * bar_pad
        progress = content.get("progress", 0.0)
        paused = content.get("paused", False)
        if self.cfg.get("ui.progress_style", "meadow") == "plain":
            theme.draw_bar(p, bar_pad, bar_y, bar_w, bar_h, S, pal, progress, paused=paused)
        else:
            # 天色与云按真实时钟走；关掉 daylight_tint 就固定在正午、云不动
            now = self.snap.now or datetime.now()
            if self.cfg.get("ui.daylight_tint", True):
                hour = self._visual_hour(now)
                # 动画的秒必须取"此刻"，不能用 snap.now —— 那是上一次 tick 的时刻，
                # 一秒才更新一次；拿它算 secs 的话，哪怕 30fps 重绘，画面还是每秒动一格。
                # （底片脚本会把模块里的 _time 冻住，所以这里取 0，拍出来仍是静止的。）
                wall = _time.time()
                lt = datetime.fromtimestamp(wall)
                secs = (lt.hour * 3600 + lt.minute * 60 + lt.second
                        + lt.microsecond / 1_000_000.0)
            else:
                hour, secs = 12.0, 0.0
            lunch_ratio = self._lunch_ratio()
            flock_now = ((self._fx_t * self._fx_dur, self._fx_dur)
                         if self._fx_kind == "life" else None)
            # 天气按日期定：同一天里刷新多少次都一样，跨天才换。
            # 云和下落物是两个独立开关——用户想关的往往是"天上飘的东西"，
            # 而不是整个气象系统。两个都关 → None，天空留一大片干净底色。
            clouds_on = bool(self.cfg.get("ui.fx.clouds",
                                          self.cfg.get("ui.fx.weather", True)))
            fall_on = bool(self.cfg.get("ui.fx.fall",
                                        self.cfg.get("ui.fx.weather", True)))
            today_weather = (weather.weather_of(self._day)
                             if (clouds_on or fall_on) else None)
            theme.draw_meadow_bar(p, bar_pad, bar_y, bar_w, bar_h, S, pal,
                                  self._anim_ratio if self._animating else progress,
                                  paused=paused, seed_day=self._day.toordinal(),
                                  hour=hour, secs=secs,
                                  roll_phase=self._roll_phase, roll_lift=self._roll_lift,
                                  roll_on=bool(self.cfg.get("ui.sod_roll", True)),
                                  landmark=lunch_ratio,
                                  landmark_passed=(now.hour * 60 + now.minute
                                                   >= self.rule.lunch_start.hour * 60
                                                   + self.rule.lunch_start.minute),
                                  flock=flock_now,
                                  moon=bool(self.cfg.get("ui.fx.moon", True)),
                                  props=bool(self.cfg.get("ui.fx.props", True)),
                                  weather=today_weather,
                                  clouds=clouds_on, fall=fall_on,
                                  press=self._poke_power(),
                                  press_x=getattr(self, "_poke_x", None))

        # 底部一行（仅完整布局）
        if L["foot_bottom"]:
            foot_bottom = self.u(L["foot_bottom"])
            right = content.get("foot_right", "")
            rk = max(2, int(round(S * 1.6)))         # 右侧点阵跟左边中文差不多高
            rw = pixel_font.text_width(right, rk) if right else 0
            avail = cx_right - pad - (rw + 3 * S if right else 2 * S)
            fsize = L.get("foot_size", 10)
            fh = self.u(fsize)
            while fsize > 8:                         # 放不下就降一档字号，绝不挤到框外
                fw, fh = pixel_font.measure_cjk(content["foot_left"], self.u(fsize),
                                                self.family, bold=True)
                if fw <= avail:
                    break
                fsize -= 1
            fw, fh = pixel_font.measure_cjk(content["foot_left"], self.u(fsize),
                                            self.family, bold=True)
            pixel_font.draw_cjk(p, pad, foot_bottom - fh, content["foot_left"],
                                self.u(fsize), QColor(pal["text_dim"]), self.family,
                                bold=True)
            if right:
                gold = bool(content.get("foot_right_gold"))
                ty = foot_bottom - pixel_font.text_height(rk)
                if gold:      # 里程碑：先描一层深金影，再压亮金，灰底上也跳得出来
                    pixel_font.draw_bits(p, cx_right - rw + S // 2, ty + S // 2,
                                         right, rk, QColor("#8a6b1f"))
                pixel_font.draw_bits(p, cx_right - rw, ty, right, rk,
                                     QColor("#ffd75e") if gold else QColor(pal["text_dim"]))

        # 每日一句：固定占一行（进度条与底栏之间），跨天自动换；小档不显示
        qb = L.get("quote_bottom", 0)
        if qb:
            qtext = self._quote_text()
            if qtext:
                # 引用行左右只留 4 单位（正文是 12）：名句原文普遍偏长，多出的
                # 32px 让 15~16 字的原句仍能用 22px 点阵，长句也能少降一档字号
                avail_q = W - 2 * self.u(4)
                qsize = L.get("quote_size", 11)
                qw, qh = pixel_font.measure_cjk(qtext, self.u(qsize), self.family, bold=True)
                while qsize > 8 and qw > avail_q:      # 自定义长句也不越框
                    qsize -= 1
                    qw, qh = pixel_font.measure_cjk(qtext, self.u(qsize), self.family,
                                                    bold=True)
                pixel_font.draw_cjk(p, 0, self.u(qb) - qh, qtext, self.u(qsize),
                                    theme.quote_color(pal), self.family, bold=True,
                                    align="center", max_w=W)

        # ---- 收工流程的覆盖层：不参与布局，只在到点之后叠上来
        if self.snap.state == engine.ST_OVERTIME:
            if not self._compact and (not self._evening_choice
                                      or self._fx_kind == "home"):
                self._draw_plank(p, S, pal)
            if self._offer_open:
                self._draw_choices(p, S, pal, W)
            elif self._compact and (not self._evening_choice
                                    or self._fx_kind == "home"):
                self._draw_plank(p, S, pal)
        if self._fx_kind == "home":
            self._draw_celebrate(p, W, H, S)

        if self._pt_active:
            accent = QColor(pal["accent"])
            theme.fill(p, 0, 0, W, 2 * S, accent)
            theme.fill(p, 0, H - 2 * S, W, 2 * S, accent)
            theme.fill(p, 0, 0, 2 * S, H, accent)
            theme.fill(p, W - 2 * S, 0, 2 * S, H, accent)


    def _draw_items(self, p: QPainter, center_x: int, bottom: int, items, color: QColor) -> None:
        px_items = []
        for it in items:
            if it[0] == "c":
                px_items.append(("c", it[1], self.u(it[2])))
            elif it[0] == "g":
                px_items.append(("g", self.u(it[1])))
            else:
                px_items.append(it)
        pixel_font.draw_items(p, center_x, bottom, px_items, color, self.family)

    # ---------------------------------------------------------------- 文案
