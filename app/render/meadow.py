"""草地：花海、草皮卷、道具，以及整条天空进度条的组装

从 app/theme.py 拆出（2026-11-20）。函数体逐字未改，只是挪了位置。
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QPolygonF

from .. import pixel_font

from .palette import _curve_at, c  # noqa: E402
from .common import _grass_tones, fill, texture  # noqa: E402
from .sky import _draw_flock, _draw_sky  # noqa: E402
from .weather import draw_downpour, draw_rain, draw_tint  # noqa: E402
from ..weather import CLEAR, CLOUDY, DOWNPOUR, RAIN, RAINY  # noqa: E402

_SPECIES: dict[str, dict] = {
    # 花冠统一 4 行高，宽 4~5 格：同一条花带里花冠顶是对齐的，不会高高低低连成彩边。
    # 每朵都三件套：a 花瓣 / c 高光（左上，让花冠鼓起来）/ b 花心与底影（让花冠有边）。
    # 只用单色方块的话，1 单位 = 2px 的尺度下就是一块色斑，读不出"花"。
    "poppy": {"colors": {"a": "#c4433c", "b": "#7d2a25", "c": "#e8907f"},
              "head": (".a.a.",
                       "aacaa",
                       "aabaa",
                       ".bbb.")},
    "dandelion": {"colors": {"a": "#e5c63c", "b": "#a8891a", "c": "#f8ec9a"},
                  "head": (".aa.",
                           "acaa",
                           "abba",
                           ".bb.")},
    "oxeye": {"colors": {"a": "#eef0e4", "b": "#dfbf3c", "c": "#ffffff"},
              "head": (".aa.",
                       "abba",
                       "abba",
                       ".aa.")},
    "cornflower": {"colors": {"a": "#5a7fd0", "b": "#33509b", "c": "#93b2e6"},
                   "head": (".a.a",
                            "acaa",
                            "abba",
                            ".bb.")},
    "allium": {"colors": {"a": "#a978c2", "b": "#6d4080", "c": "#cda9e0"},
               "head": (".aaa.",
                        "aacaa",
                        "aabba",
                        ".bbb.")},
    "tulip": {"colors": {"a": "#d9782f", "b": "#8f4a19", "c": "#f2a865"},
              "head": (".a.a",
                       "acaa",
                       "aaba",
                       ".bb.")},
    "bluet": {"colors": {"a": "#8fb6ee", "b": "#5a7fbf", "c": "#c4dbf9"},
              "head": ("ab",
                       "ba")},
    # 向日葵：比别的花冠宽一格，花瓣带缺口，在一堆小花里最容易被认成"花"
    "sunflower": {"colors": {"a": "#f0b429", "b": "#7a5210", "c": "#fbe08a"},
                  "head": (".a.a.",
                           "aacaa",
                           "acbca",
                           ".bbb.")},
    # 兰花：品红偏粉，和绒球葱的冷紫拉开色相，不会看成一朵
    "orchid": {"colors": {"a": "#cf6fae", "b": "#8a3f72", "c": "#eaa9d1"},
               "head": (".aa.",
                        "acca",
                        "abba",
                        ".bb.")},
}


_SPECIES_ORDER = ("poppy", "dandelion", "oxeye", "cornflower", "allium", "tulip",
                   "bluet", "sunflower", "orchid")


_PETAL_COLORS = ("#c4433c", "#e5c63c", "#eef0e4", "#5a7fd0", "#a978c2", "#d9782f",
                  "#8fb6ee", "#f0b429", "#cf6fae")


_day_picks_cache: dict[int, tuple[int, ...]] = {}


def _day_picks(seed_day: int) -> tuple[int, ...]:
    """每天固定五种花：主色 / 副色 / 点缀 / 两种稀少。

    只有三种时，天天看都是那三色，跟 MC 的花田比太单调；但七种平均撒下去又会
    变成"彩纸"。折中是**五种、权重很陡**（4 : 3 : 2 : 1.5 : 1）——主色仍占大头，
    稀有的那两种一天只露几朵，负责"今天好像不一样"。
    """
    hit = _day_picks_cache.get(seed_day)
    if hit is None:
        r = random.Random(seed_day * 977 + 3)
        hit = tuple(r.sample(range(len(_PETAL_COLORS)), 5))
        if len(_day_picks_cache) > 64:
            _day_picks_cache.clear()
        _day_picks_cache[seed_day] = hit
    return hit


def _shade(col: QColor, f: float) -> QColor:
    """按明度倍数压暗/提亮，用于让花色跟着天色走。"""
    if abs(f - 1.0) < 0.01:
        return col
    h, s, v, a = col.getHsvF()
    return QColor.fromHsvF(h if h >= 0 else 0.0, s, max(0.0, min(1.0, v * f)), a)


def _draw_head(p: QPainter, left: int, top: int, s: int, head, colors: dict,
               dim: float = 1.0) -> None:
    for ry, row in enumerate(head):
        for rx, ch in enumerate(row):
            if ch == ".":
                continue
            col = colors.get(ch)
            if col is not None:
                fill(p, left + rx * s, top + ry * s, s, s, _shade(QColor(col), dim))


def _draw_flower(p: QPainter, cx: int, gy: int, s: int, key: str, height_u: int,
                 paused: bool, pal: dict, dim: float = 1.0,
                 stem: bool = True) -> None:
    """一枝花：茎 + 花冠。高度由调用方保证不出框。

    stem=False 就是"不带茎"——只落一个花冠，靠底下那层草叶接着。这是主力的画法：
    一条带子里 200 根竖茎就是"竖线森林"，而只给花冠、不给支撑，读起来才是
    "花自己开在花海里"。真茎只留给最高的那一层（它们高到必须撑一下）。
    """
    sp = _SPECIES[key]
    stem_col = QColor(pal["grass"][2]).darker(114)
    stem_hi = QColor(pal["grass"][1]).darker(102)
    h = max(0, height_u) * s
    if stem and h > 0:
        # 不画叶子：2 单位宽的一横在这个尺度下读成"手臂"，不如只留一根细茎
        fill(p, cx, gy - h, s, h, stem_col)
        if h >= 6 * s:
            fill(p, cx, gy - h + s, s, s, stem_hi)
    if paused:
        # 午休：花收成花苞
        fill(p, cx - s, gy - h - s, 2 * s, s, stem_col.darker(112))
        fill(p, cx, gy - h - 2 * s, s, s, _shade(QColor(sp["colors"]["b"]), dim))
        return
    head = sp["head"]
    hw = len(head[0])
    left = cx - ((hw - 1) // 2) * s
    _draw_head(p, left, gy - h - (len(head) - 1) * s, s, head, sp["colors"], dim)


def _draw_tuft(p: QPainter, cx: int, gy: int, s: int, pal: dict, rng: random.Random) -> None:
    """纯草叶：填在高枝之间，给花丛补体积。"""
    tones = [QColor(v) for v in pal["grass"]]
    blades = rng.randint(2, 4)
    for i in range(blades):
        bh = rng.randint(2, 6) * s
        fill(p, cx + (i - blades // 2) * s, gy - bh, s, bh,
             tones[rng.randrange(len(tones))].darker(105))


# 贴地小花的几种像素花冠（a=花瓣，b=暗部，'.'=透明）


_BLOSSOM_HEADS = (
    ("aa", "aa"),
    (".a.", "aaa"),
    ("aa", "ab"),
    ("a.a", ".a."),
    (".a", "aa", "a."),
    ("a",),
    ("aa",),
)


def _draw_blossom(p: QPainter, x: int, gy: int, s: int, rng: random.Random,
                  pal: dict, seed_day: int, dim: float = 1.0) -> None:
    """贴地小花：低矮花冠压在草皮上，成丛连片才有花海感。"""
    base = QColor(_PETAL_COLORS[rng.choices(_day_picks(seed_day),
                                            weights=(7, 5, 2, 1, 0.6))[0]])
    k = rng.randint(-8, 8)
    col = base.lighter(100 + k) if k >= 0 else base.darker(100 - k)
    col = _shade(col, dim)
    stem = QColor(pal["grass"][2]).darker(126)
    head = _BLOSSOM_HEADS[rng.randrange(len(_BLOSSOM_HEADS))]
    hw, hh = len(head[0]), len(head)
    sh = rng.choice((0, 0, 0, 1, 1, 2))
    if sh:
        fill(p, x, gy - sh * s, s, sh * s, stem)
    dm = QColor(col).darker(118)
    left = x - ((hw - 1) // 2) * s
    top = gy - (sh + hh) * s
    for ry, row in enumerate(head):
        for rx, ch in enumerate(row):
            if ch == ".":
                continue
            fill(p, left + rx * s, top + ry * s, s, s, col if ch == "a" else dm)


def _draw_flower_field(p: QPainter, ix: int, gy: int, cols: int, s: int, pal: dict,
                       seed_day: int, paused: bool, sky_u: int, dim: float = 1.0) -> None:
    """已开垦的草地，按高度分成四条带，各自横向排，互不挤在同一行。

    这套画法解决的是"铺满就糊"的问题。糊的原因有两个，且是叠加的：
      1. 花茎是 1 单位宽的深色竖线，一根看不出来，两百根就是"竖线森林"；
      2. 花冠如果都落在同一高度，连起来就成"一条彩色边"，一朵都分不出。
    所以这里：
      * 茎只给最高的那一带（5 单位以上），中低两带的花冠直接坐在草上，
        **不带茎**——花就一朵是一朵，不再被竖线串起来；
      * 四带各占一段高度，横向起始点错开，铺满时读起来是层层叠叠的花坡，
        不是一片色斑；
      * 同层内下一朵至少让出"花冠宽 + 3 格"，两朵花冠永远不会并成一坨。
    """
    if cols <= 1:
        return
    rng = random.Random(seed_day * 131 + 5)
    top_u = max(4, sky_u - 1)          # 花冠顶端最高到哪儿（单位，从草地线数起）

    # 当天只开三种花（主色 / 副色 / 点缀），和贴地花毯同一套配色。
    # 七种颜色全上，画面是"花"；三种成片，才是"一片花田"。
    picked = _day_picks(seed_day)

    def pick(weights=(4, 3, 2, 1.5, 1)) -> str:
        # 蓝亚麻只有 2×2，做花冠太碎、密了像噪点，只让它留在下面的贴地花毯里
        pairs = [(w, _SPECIES_ORDER[p]) for w, p in zip(weights, picked)
                 if _SPECIES_ORDER[p] != "bluet"]
        if not pairs:
            pairs = [(1, _SPECIES_ORDER[picked[0]])]
        return rng.choices([k for _, k in pairs], weights=[w for w, _ in pairs])[0]

    def hw_of(key: str) -> int:
        return len(_SPECIES[key]["head"][0])

    # 1) 草叶垫底：矮草铺一层，花才有落脚的东西，草地也不至于露出大片纯绿
    x = 0
    while x < cols - 1:
        if rng.random() < 0.55:
            _draw_tuft(p, ix + x * s, gy, s, pal, rng)
        x += rng.randint(2, 4)

    # 2) 三层花带，高度带**首尾相接**而不是互相穿插——一旦穿插，两朵花冠就会
    #    半叠在一起，那就又回到"糊成一片"。所以每层的花高固定，层间距 ≥ 花冠高。
    #    绝大部分的视觉重量压在主层上，高枝只负责把上沿打散。
    #    (起始列, 花高, 额外间距, 出现率, 是否带茎)
    #    花冠现在统一 4 行高，所以每层的高度差要留够 4：层与层之间只在横向错开，
    #    纵向不叠，一朵就是一朵。
    layers = (
        (2, 9, 7, 0.38, True),      # 高枝：稀，带茎，花冠落在 9~12
        (6, 5, 4, 0.52, False),     # 次高：花冠落在 5~8
        (1, 2, 2, 0.86, False),     # 主层：最密，不带茎，花冠落在 2~5
        (12, 0, 5, 0.62, False),    # 贴地：花冠落在 0~3
    )
    for lx, h, gap, rate, st in layers:
        x = lx
        while x < cols - 4:
            if rng.random() < rate:
                key = pick()
                if h == 0 or top_u - len(_SPECIES[key]["head"]) - 1 >= h:
                    _draw_flower(p, ix + x * s, gy, s, key, h, paused, pal, dim,
                                 stem=st)
                    x += hw_of(key) + gap + rng.randint(0, 2)
                    continue
            x += rng.randint(3, 6)

    # 3) 贴地花毯：最底一条线上的小碎花，负责"花海"的颗粒感
    if paused:
        return
    x = 0
    while x < cols - 2:
        if rng.random() < 0.55:
            for k in range(rng.randint(2, 3)):
                bx = x + k * 2
                if bx < cols - 1:
                    _draw_blossom(p, ix + bx * s, gy, s, rng, pal, seed_day, dim)
            x += rng.randint(3, 6)
        else:
            x += rng.randint(2, 4)


_SOD_ROLL_TURN_PER_UNIT = 0.25   # 滚过 1 单位转多少圈（略作夸张，否则一天也转不了几圈）


def _roll_radius(grass_u: int, ratio: float = 0.5) -> int:
    """卷的半径（单位）：跟真的一卷草皮一样，是越铺越少的。

    起手是完整的一卷（3，7×7），铺开一段就瘦成薄薄一卷（2，5×5）——一卷草皮
    摊开多少就少多少，从大变小才是现实里的样子。上限压到 3（原来是 4），因为
    再大一档就成了"草地上一颗绿球"，反而看不出是卷。
    """
    cap = 3 if grass_u >= 3 else 2
    r = 3 if ratio < 0.35 else 2
    return min(r, cap)


def _roll_cells(r: int) -> set[tuple[int, int]]:
    R = float(r)
    return {(ux, uy) for uy in range(-r, r + 1) for ux in range(-r, r + 1)
            if math.hypot(ux, uy) <= R + 0.5}


def _sod_roll(p: QPainter, cx: int, gy: int, s: int, pal: dict, grass_u: int,
              phase: float = 0.0, lift: int = 0, dust: int = 0,
              ratio: float = 0.5) -> None:
    """推进前沿的那卷草皮：端面朝着我们，一圈圈卷到偏在右下的小卷芯。

    不是"一颗绿球"，区别就在断面：草皮是一层压一层卷起来的，切开的端面必然
    是"草 + 一条土"交替的螺旋。所以端面只做两件事——平涂绿身（柱面光，上亮
    下暗，不要球面中心高光），再沿参数曲线逐格描一条土色螺旋，从外缘一直卷到
    偏右下的卷芯。卷底沾一层土、压进草皮压住，就落在地上了。
    """
    tones = sorted((QColor(v) for v in pal["grass"]), key=lambda c: c.lightness())
    out = tones[1].darker(126)
    dcol = QColor(pal["dirt"][0])

    r = _roll_radius(grass_u, ratio)
    n = 2 * r + 1
    cells = _roll_cells(r)
    bury = 2 if r == 3 else 1
    base_y = gy + bury * s - lift * s
    cy = base_y - r * s
    gtex = texture("grass", n, n, s, pal)
    R = float(r)

    def put(ux: int, uy: int, col: QColor) -> None:
        fill(p, cx + ux * s, cy + uy * s, s, s, col)

    def base_at(ux: int, uy: int) -> QColor:
        c = gtex.pixelColor((ux + r) * s + s // 2, (uy + r) * s + s // 2)
        avg = tones[2]
        return QColor((c.red() + avg.red() * 2) // 3,
                      (c.green() + avg.green() * 2) // 3,
                      (c.blue() + avg.blue() * 2) // 3)

    # 卷芯偏右下：真实的卷，芯一定不在几何中心——这一条就把"球"排除掉了
    corex, corey = 0.90, 0.62
    turns = 1.2
    mouth = -0.45 * math.pi + phase * 2 * math.pi

    # 1) 卷身：平涂绿，上亮下暗（柱面光，不是球面那种中心高光）
    for (ux, uy) in cells:
        h = (uy + r) / max(1, 2 * r)
        f = 1.20 - 0.15 * h - 0.05 * (math.hypot(ux, uy) / (R + 0.5))
        put(ux, uy, _shade(base_at(ux, uy), f))

    # 2) 断面上的土线：沿参数曲线逐格描，连成一条螺旋。
    #    草皮是一圈圈卷起来的，切开的端面必然是"草 + 一条土"交替的螺旋，
    #    这是卷和球最根本的区别，比任何打光都管用。
    steps = 240
    drawn: set[tuple[int, int]] = set()
    for k in range(steps + 1):
        t = k / steps
        th = mouth + 2 * math.pi * turns * t
        rad = (R - 0.1) * (1.0 - 0.90 * t ** 1.1)
        drift = t ** 0.9
        px = int(round(rad * math.cos(th) + corex * drift))
        py = int(round(rad * math.sin(th) + corey * drift))
        if (px, py) in cells and (px, py) not in drawn:
            drawn.add((px, py))
            put(px, py, _shade(dcol, 0.98 - 0.06 * t))

    # 3) 卷芯那格：卷到最后剩的一小截草皮，颜色最鲜
    put(int(round(corex)), int(round(corey)), _shade(tones[-1], 1.08))

    # 4) 卷口：螺旋起点那一格换成薄土，草皮就是在这儿断的
    hx = int(round((R - 0.1) * math.cos(mouth)))
    hy = int(round((R - 0.1) * math.sin(mouth)))
    if (hx, hy) in cells:
        put(hx, hy, _shade(dcol, 1.00))

    # 5) 卷底沾着的土：只压最底一行中间三格
    bot = max(uy for _, uy in cells)
    for ux in range(-1, 2):
        if (ux, bot) in cells:
            put(ux, bot, _shade(dcol, 0.92))

    # 6) 描边：一圈深草绿，闭口才不会像贴纸
    for (ux, uy) in cells:
        if any((ux + dx, uy + dy) not in cells
               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            put(ux, uy, out)

    # 7) 压在地上的影 + 右前方扬起的土粒
    fill(p, cx - r * s, base_y, n * s, s, QColor(0, 0, 0, 58))
    if dust:
        dcol2 = QColor(pal["dirt"][-1]).lighter(126)
        for i in range(dust):
            fill(p, cx + (r + 1 + (i % 2)) * s, base_y - (1 + i % 2) * s, s, s, dcol2)


# 天空里飞过的鸟群。为什么是"群"而不是"一只"：1 单位 = 2px 的尺度下，
# 单只 10px 的小鸟在 400px 宽的条子里就是个污点（蝴蝶、蜜蜂、单鸟都画过放大图，全读不出来）。
# 六只排成 V 字一起移动，队形本身就成了信号——跟花海靠"重复"成片是同一个道理。
# 领头的在最前，两条胳膊往后张开。三种队形按日期轮换，天天一个样容易看腻。


_PROP_FRACS = (0.19, 0.53, 0.84)


def _prop_fence(p: QPainter, cx: int, gy: int, s: int, pal: dict) -> None:
    """三柱两横的木栅栏，12×8 单位——比花高一头，才不会被花海埋掉。"""
    wood = QColor(pal["dirt"][0]).darker(96)
    dark = QColor(pal["dirt"][0]).darker(132)
    for dx in (-5, 0, 5):
        fill(p, cx + dx * s, gy - 10 * s, s, 10 * s, wood)
        fill(p, cx + dx * s, gy - 10 * s, s, s, wood.lighter(126))
    fill(p, cx - 5 * s, gy - 9 * s, 11 * s, s, dark)
    fill(p, cx - 5 * s, gy - 5 * s, 11 * s, s, dark)


def _prop_hay(p: QPainter, cx: int, gy: int, s: int, pal: dict) -> None:
    """一捆干草，9×6 单位：上沿收一格 + 中间一道捆绳，不然就是块黄砖。"""
    hay = QColor("#d9b45c")
    dark = QColor("#a8842f")
    fill(p, cx - 4 * s, gy - 5 * s, 9 * s, 5 * s, hay)
    fill(p, cx - 3 * s, gy - 6 * s, 7 * s, s, hay.lighter(108))
    fill(p, cx - 4 * s, gy - 5 * s, 9 * s, s, hay.lighter(116))
    fill(p, cx - 4 * s, gy - s, 9 * s, s, dark)
    fill(p, cx - s, gy - 4 * s, s, 4 * s, dark)
    fill(p, cx - 4 * s, gy - 3 * s, s, s, dark)


def _prop_stones(p: QPainter, cx: int, gy: int, s: int, pal: dict) -> None:
    """石头堆，7×5 单位：大石压小石，轮廓不齐才像堆的。"""
    light = QColor("#9a9a94")
    dark = QColor("#6f6f6a")
    fill(p, cx - 3 * s, gy - 3 * s, 5 * s, 3 * s, light)
    fill(p, cx - 3 * s, gy - 3 * s, 2 * s, s, light.lighter(118))
    fill(p, cx + 2 * s, gy - 2 * s, 3 * s, 2 * s, dark)
    fill(p, cx - s, gy - 5 * s, 3 * s, 2 * s, dark.lighter(112))
    fill(p, cx + 3 * s, gy - 4 * s, 2 * s, 2 * s, light.darker(108))


def _draw_props(p: QPainter, ix: int, gy: int, iw: int, s: int, pal: dict,
                seed_day: int, ratio: float) -> None:
    for i, fr in enumerate(_PROP_FRACS):
        if ratio < fr + 0.02:          # 还没铺到那儿
            continue
        cx = ix + int(iw * fr) // s * s
        kind = (seed_day + i * 2) % 3
        if kind == 0:
            _prop_fence(p, cx, gy, s, pal)
        elif kind == 1:
            _prop_hay(p, cx, gy, s, pal)
        else:
            _prop_stones(p, cx, gy, s, pal)


def draw_meadow_bar(p: QPainter, x: int, y: int, w: int, h: int, s: int, pal: dict,
                    ratio: float, paused: bool = False, seed_day: int = 0,
                    hour: float = 12.0, secs: float = 0.0,
                    roll_phase: float = 0.0, roll_lift: int = 0,
                    roll_on: bool = True, landmark: float | None = None,
                    landmark_passed: bool = False,
                    flock: tuple[float, float] | None = None,
                    moon: bool = True, props: bool = True,
                    weather: str | None = "clear") -> None:
    """草地进度条：一整条花海剖面，天空在上一路铺满。

    分层自下而上：泥土剖面 → 锯齿草皮 → 草叶与花 → 天空（云会飘、天色随钟点变）。
    已开垦区是开满花的草地，未开垦区是压实的暗色泥地，中间留一道断口。
    """
    if w <= 4 * s or h <= 4 * s:
        return

    ix, iy = x + s, y + s
    iw, ih = w - 2 * s, h - 2 * s
    uh = max(5, ih // s)

    if uh >= 16:
        # 草地带加高到 6 格：花冠现在有 4 格高，绿带还压成 4 格的话花就只能挤在
        # 一条线上，看着像彩边。多出来的 2 格从天空里让，天空照样够高。
        grass_u, dirt_u = 6, 4
    elif uh >= 12:
        grass_u, dirt_u = 3, 4
    else:
        grass_u, dirt_u = 2, max(2, uh - 7)
    ground_u = min(uh - 2, grass_u + dirt_u)
    sky_u = uh - ground_u
    grass_u = min(grass_u, ground_u - 1)
    ground_h = ground_u * s
    grass_h = grass_u * s
    gy = iy + sky_u * s                       # 草地顶面
    dirt_y = gy + grass_h

    # 边框先画，植物最后画，才能"越过"边框
    o = QColor(pal["outline"])
    fill(p, x, y, w, s, o)
    fill(p, x, y + h - s, w, s, o)
    fill(p, x, y, s, h, o)
    fill(p, x + w - s, y, s, h, o)

    # 内容一律裁在内框里：飘到边上的云、贴边的草皮卷都不许画到框外
    p.save()
    p.setClipRect(QRect(ix, iy, iw, ih))

    # 1) 天空：整条通铺，云按秒横移，天色随钟点连续渐变
    mul = float(pal.get("sky_mul", 1.0) or 1.0)
    if weather == DOWNPOUR:        # 大雨：天压得最暗，云几乎看不出层次
        mul *= 0.58
    elif weather == RAIN:          # 阴雨天：天色压暗且降饱和，云也跟着发灰
        mul *= 0.70
    elif weather == CLOUDY:
        mul *= 0.86
    bands = _draw_sky(p, ix, iy, iw, sky_u, s, hour, secs, seed_day, mul,
                      moon and weather not in RAINY,
                      clouds=weather is not None)
    fill(p, ix, gy - s, iw, s, bands[-1].lighter(104))     # 地平线亮线

    ratio = max(0.0, min(1.0, ratio))
    fill_w = int(round(iw * ratio))
    cols = fill_w // s
    fx = ix + cols * s

    # 2) 未开垦区：压实的暗色泥地，天空照样在它上面
    if fx < ix + iw:
        ncols = max(1, (ix + iw - fx) // s)
        p.drawImage(QPoint(fx, gy), texture("dirt", ncols, ground_u, s, pal))
        # 压暗分几档渐入：前沿不留一条笔直的硬边，卷才像"压过去"而不是"切过去"
        x0 = fx
        for band, alpha in ((1, 38), (2, 76), (3, 102), (None, 118)):
            if x0 >= ix + iw:
                break
            bw = (ix + iw - x0) if band is None else band * s
            fill(p, x0, gy, min(bw, ix + iw - x0), ground_h, QColor(26, 21, 16, alpha))
            x0 += bw
        fill(p, fx, gy, ix + iw - fx, s, QColor(pal["track"][0]).darker(150))

    # 3) 已开垦区：泥土剖面 + 草皮 + 花海
    if cols >= 1:
        p.drawImage(QPoint(ix, dirt_y), texture("dirt", cols, ground_u - grass_u, s, pal))
        rng = random.Random((seed_day * 31 + 7) & 0x7FFFFFFF)
        for _ in range(max(1, cols // 6)):
            bx = ix + rng.randrange(max(1, cols)) * s
            by = dirt_y + (1 + rng.randrange(max(1, max(1, ground_u - grass_u - 2)))) * s
            col = QColor(pal["dirt"][-1]).darker(126)
            fill(p, bx, by, s, s, col)
            if rng.random() < 0.5:
                fill(p, bx + s, by, s, s, col.lighter(112))

        p.drawImage(QPoint(ix, gy), texture("grass", cols, grass_u, s, pal))
        rng = random.Random((seed_day * 53 + 11) & 0x7FFFFFFF)
        # 草叶也用收敛后的四档近色：单根草叶不该比整条绿带还显眼
        tones = [QColor(x) for x in _grass_tones(pal)]
        for cidx in range(cols):
            cx = ix + cidx * s
            jag = rng.choice((0, 0, 0, 1, 1, 2))
            fill(p, cx, dirt_y + jag * s, s, s, tones[-1].darker(130))
            if rng.random() < 0.30:
                bh = s if rng.random() < 0.7 else 2 * s
                fill(p, cx, gy - bh, s, bh, tones[rng.randrange(len(tones))])

        # 草皮卷脚下留 2 单位新铺的裸草：刚铺开的草皮本来就还没长花，
        # 顺带让卷的轮廓不糊在花丛里
        flower_cols = max(0, cols - 2)
        _draw_flower_field(p, ix, gy, flower_cols, s, pal, seed_day, paused, sky_u,
                           dim=max(0.55, min(1.0, _curve_at(hour)[2])))

    # 3.4) 草地上的道具：画在花之后，不然全被花挡住
    if props:
        _draw_props(p, ix, gy, iw, s, pal, seed_day, ratio)

    # 3.5) 午休地标：插在"午休开始"那一刻的位置，过了就点亮
    if landmark is not None and 0.02 < landmark < 0.99:
        draw_lunch_marker(p, ix + int(round(iw * landmark)), gy, s, pal,
                          landmark_passed)

    # 4) 推进前沿：一卷草皮横躺在那儿，正往右滚
    if roll_on and 0.0 < ratio < 1.0 and cols >= 2:
        roll_x = ix + int(round(iw * ratio))          # 用像素位，滚动不跳格
        rr = _roll_radius(grass_u, ratio) * s          # 卷的半径：贴边时整圆留在框内
        roll_x = max(ix + rr, min(ix + iw - rr, roll_x))
        _sod_roll(p, roll_x, gy, s, pal, grass_u, roll_phase, roll_lift,
                  dust=3 if roll_lift else 0, ratio=ratio)

    # 4.5) 路过的鸟群：在天上，跟草地那一堆细节不打架
    if flock is not None:
        _draw_flock(p, flock[0], flock[1], ix, iy, iw, sky_u, s, seed_day)

    # 4.6) 天气：先压一层冷色（盖住天与地），再把雨丝落到最上面
    if weather != CLEAR:
        draw_tint(p, ix, iy, iw, sky_u * s, ground_u * s, weather)
        if weather in RAINY:
            # 雨只落在天空那一段：落到花海上会变成一片噪点，花海才是主角
            if weather == DOWNPOUR:
                draw_downpour(p, ix, iy, iw, sky_u * s, s, secs, seed_day)
            else:
                draw_rain(p, ix, iy, iw, sky_u * s, s, secs, seed_day)

    # 4.7) 午休：花已经收成花苞了（见 _draw_flower），再从草地上飘三个 z
    if paused:
        _draw_sleep_z(p, ix + iw - 18 * s, gy - 3 * s, s, secs)

    p.restore()

    # 底部一条极淡的亮线，暗示整条是"挖进去"的
    hi = QColor(pal["bevel_light"])
    hi.setAlpha(45)
    fill(p, x + s, y + h - s, w - 2 * s, s, hi)


# 三个 z 的像素字形：4 宽 4 高。跟 5×7 点阵不同，这里只有 4×4，才塞得进天空
_Z_GLYPH = ("1111", "..1.", ".1..", "1111")


def _draw_sleep_z(p: QPainter, bx: int, by: int, s: int, secs: float) -> None:
    """午休时从草地上飘起三个 z。

    午休时人基本不在屏幕前，所以这里不做"剧场"，只留一个不用读字的提示：
    花已经合上了，再加上缓缓上飘的 z，"在睡觉"这件事一眼就成立。
    白色配一点深色投影，白天和夜里的天空上都读得出来。
    """
    for i in range(3):
        phase = (secs * 0.55 + i * 0.34) % 1.0     # 三个 z 错开相位，一个接一个往上飘
        rise = int(round(phase * 5))               # 0~5 单位
        alpha = int(235 * (1.0 - phase) ** 0.7)
        if alpha <= 10:
            continue
        x = bx + i * 2 * s - int(round(phase * 2)) * s
        y = by - (rise + i * 2) * s
        for ry, row in enumerate(_Z_GLYPH):
            for rx, ch in enumerate(row):
                if ch != "1":
                    continue
                fill(p, x + rx * s + s, y + ry * s + s, s, s, QColor(20, 24, 30, alpha // 3))
                fill(p, x + rx * s, y + ry * s, s, s, QColor(255, 255, 255, alpha))


def draw_lunch_marker(p: QPainter, x: int, gy: int, s: int, pal: dict,
                      passed: bool) -> None:
    """午休开始的地标：一根小木桩挑一面三角旗，插在草地上。

    中午那一段没人盯着屏幕，做成"庆祝"也没人看；改成常驻地标更划算——
    一眼就知道今天几点开始午休，以及自己已经铺到旗子的哪一边。
    """
    post = QColor(pal["dirt"][1]).darker(120)
    flag = QColor("#f0c04a") if passed else QColor("#e6e6e6")
    edge = QColor(pal["outline"])
    fill(p, x, gy - 7 * s, s, 8 * s, post)          # 杆子挑高，越过花冠才看得见
    fill(p, x + s, gy - 7 * s, 4 * s, 3 * s, flag)  # 旗面 3 行，收窄成三角
    fill(p, x + s, gy - 6 * s, 3 * s, s, flag)
    fill(p, x + s, gy - 5 * s, 2 * s, s, flag)
    fill(p, x + 4 * s, gy - 7 * s, s, 3 * s, edge)  # 旗尾一点描边，免得糊进天空
