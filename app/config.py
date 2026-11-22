"""配置：所有可调参数集中在项目根目录的 config.json，改完重启即生效。"""
from __future__ import annotations

import copy
from pathlib import Path

from . import util

DEFAULT_CONFIG: dict = {
    "_readme": [
        "所有参数都可以直接改，保存后重启程序生效（不需要改代码）。",
        "passthrough_seconds: 右键触发临时穿透后，自动恢复的秒数（默认 3）",
        "font_scale: 文字与界面整体缩放，1.0 为标准，范围 0.7 ~ 2.0",
        "palette: 配色方案名，可选 grass_stone / stone_night / dirt_wood",
        "palette_override: 单独覆盖某个颜色，键见 docs/环境配置说明.md",
        "autostart: true = 开机自启（写入注册表 Run 项），保存后重启生效",
        "ui.pixel_scale: 像素块尺寸，0 = 按屏幕分辨率自动（2560x1440 → 2）",
        "ui.size_tier: 窗口尺寸档位，small（迷你窄条）/ standard（标准）/ large（大）",
        "ui.progress_style: 进度条样式，meadow（草地生长，默认）/ plain（纯色填充）",
        "ui.daylight_tint: true = 草皮/泥土/天空颜色随钟点变化，云会飘；false = 固定正午天色",
        "ui.sky_mode: work（默认）= 一天的天色压缩到你的上班时段里走完；clock = 按真实钟点",
        "ui.sky_span_hours: sky_mode=work 时，从上班算起多少小时走完日出到入夜（默认 13）",
        "ui.sod_roll: true = 进度前沿是一卷草皮，往前滚着铺（PvZ 那种）；false = 直边",
        "ui.sod_roll_idle: true = 不推进时草皮卷也慢慢转，看起来是活的",
        "ui.sod_roll_idle_speed: 待机时每秒转多少圈（默认 0.012 ≈ 80 秒一圈，大了就像原地打转）",
        "ui.quote: true = 标准/大档在进度条下面显示一行每日一句（小档不显示）",
        "ui.quote_shuffle: true = 先按固定种子洗牌再按日期取，看不出顺序；false = 按列表顺序轮",
        "ui.quotes: 自定义句子列表，留空 [] 用内置的 481 句（含米哈游台词），跨天自动换",
        "ui.right_click_action: 右键行为，passthrough（临时穿透）或 menu（右键菜单）",
        "ui.fx.*: 情绪化动效开关。greeting=顶部问候语；milestone=里程碑；celebrate=收工庆祝；",
        "         offer=到点询问加不加班；offer_idle_seconds=多久没反应就自动弹出（秒）；",
        "         life=一天两三次从天上飞过的鸟群；moon=入夜后的月亮；",
        "         fps=动效帧率。auto（默认）按机器性能自己挑；也可锁 high/mid/low = 60/30/15",
        "schedule: 上班时间/下班时间/午休，workdays 用 1=周一 ... 7=周日",
        "schedule.workdays: 哪几天上班，1=周一 ... 7=周日。单休、周六休周日上班都能配，至少留一天",
        "schedule.offwork_time: 下班时刻（HH:MM）。留空 = 还没选过，按 onsite_hours 推算；",
        "                     在设置里选过一次之后就一直用它",
        "schedule.lunch_minutes: 午休时长（分钟）。午休结束 = 午休开始 + 这个时长",
        "schedule.remember_start: true = 每天自动用 default_work_start 登记，不再弹窗问",
        "weather: mode=random 按日期播种（默认）/ real 用真实天气；place=用户填的城市名；",
        "         code/temp 是最近一次取到的缓存，跨天会重取；取不到就静默退回随机",
    ],
    "passthrough_seconds": 3,
    "font_scale": 1.0,
    "palette": "grass_stone",
    "palette_override": {},
    "autostart": False,
    "ui": {
        "always_on_top": True,
        "opacity": 1.0,
        "passthrough_opacity": 0.45,
        "right_click_action": "passthrough",
        "pixel_scale": 0,
        "corner_margin": 32,
        "size_tier": "standard",
        "progress_style": "meadow",
        "daylight_tint": True,
        "sky_mode": "work",
        "sky_span_hours": 13.0,
        "sod_roll": True,
        "sod_roll_idle": True,
        "sod_roll_idle_speed": 0.012,
        "quote": True,
        "quote_shuffle": True,
        "quotes": [],
        "fx": {
            "greeting": True,
            "milestone": True,
            "celebrate": True,
            "offer": True,
            "offer_idle_seconds": 25,
            "life": True,
            "moon": True,
            "props": True,
            "weather": True,
            "fps": "auto",
        },
    },
    "schedule": {
        "default_work_start": "09:00",
        "offwork_time": "",
        "onsite_hours": 9.0,
        "lunch_start": "12:00",
        "lunch_minutes": 60,
        "lunch_end": "13:00",
        "workdays": [1, 2, 3, 4, 5],
        "ask_start_on_launch": True,
        "remember_start": False,
        "setup_done": False,      # 第一次启动那套设置走完了没有
    },
    "weather": {
        "mode": "random",      # random = 按日期播种；real = 用真实天气
        "place": "",           # 用户填的城市名
        "shown": "",           # 天气服务返回的标准地名，显示用
        "asked": False,        # 是否已经问过「要不要真实天气」
        "fetched_day": "",     # 最近一次取到的是哪一天，跨天要重取
        "fetched_ts": 0.0,     # 最近一次取到的时间戳；超过 3 小时重取一次
        "code": "",            # 缓存下来的天气档
        "temp": None,          # 缓存下来的气温（℃）
    },
}


def _workdays(value) -> list[int]:
    """休息日（上班日）判定：1=周一 … 7=周日。

    去重、升序、至少留一天——一个都不留等于"整周休息"，那是配置写坏了，
    不是用户的意思，所以退回默认的周一到周五。
    """
    out: set[int] = set()
    if isinstance(value, (list, tuple, set)):
        for x in value:
            try:
                n = int(x)
            except (TypeError, ValueError):
                continue
            if 1 <= n <= 7:
                out.add(n)
    return sorted(out) or [1, 2, 3, 4, 5]


def _hhmm(value, default: str) -> str:
    """任何输入都收成一个合法的 "HH:MM" 字符串（手改配置写错了也不崩）。"""
    text = str(value or "").strip()
    try:
        h, m = text.split(":")
        return f"{int(h) % 24:02d}:{int(m) % 60:02d}"
    except Exception:
        return default


def _minutes_of(text: str) -> int | None:
    try:
        h, m = str(text).split(":")
        return (int(h) % 24) * 60 + int(m) % 60
    except Exception:
        return None


def _span_minutes(start, end, default: int) -> int:
    a, b = _minutes_of(_hhmm(start, "12:00")), _minutes_of(_hhmm(end, "13:00"))
    if a is None or b is None:
        return default
    span = (b - a) % (24 * 60)
    return span if 0 < span <= 240 else default


def _add_minutes(start: str, minutes: int) -> str:
    base = _minutes_of(start) or 0
    total = (base + int(minutes)) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _coerce_types(cfg: dict) -> dict:
    """容错：用户手改 json 时类型写错也不至于崩溃。"""
    def as_float(v, d):
        try:
            return float(v)
        except (TypeError, ValueError):
            return d

    def as_int(v, d):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return d

    cfg["passthrough_seconds"] = max(0.5, min(30.0, as_float(cfg.get("passthrough_seconds"), 3.0)))
    cfg["font_scale"] = max(0.6, min(2.5, as_float(cfg.get("font_scale"), 1.0)))
    cfg["autostart"] = bool(cfg.get("autostart", False))
    if not isinstance(cfg.get("palette"), str):
        cfg["palette"] = "grass_stone"
    if not isinstance(cfg.get("palette_override"), dict):
        cfg["palette_override"] = {}

    ui = cfg.get("ui") or {}
    ui["opacity"] = max(0.2, min(1.0, as_float(ui.get("opacity"), 1.0)))
    ui["passthrough_opacity"] = max(0.1, min(1.0, as_float(ui.get("passthrough_opacity"), 0.45)))
    ui["pixel_scale"] = max(0, min(6, as_int(ui.get("pixel_scale"), 0)))
    ui["corner_margin"] = max(0, min(400, as_int(ui.get("corner_margin"), 32)))
    ui["always_on_top"] = bool(ui.get("always_on_top", True))
    if ui.get("right_click_action") not in ("passthrough", "menu"):
        ui["right_click_action"] = "passthrough"
    if ui.get("size_tier") not in ("small", "standard", "large"):
        ui["size_tier"] = "standard"
    if ui.get("progress_style") not in ("meadow", "plain"):
        ui["progress_style"] = "meadow"
    ui["daylight_tint"] = bool(ui.get("daylight_tint", True))
    if ui.get("sky_mode") not in ("work", "clock"):
        ui["sky_mode"] = "work"
    try:
        ui["sky_span_hours"] = min(20.0, max(4.0, float(ui.get("sky_span_hours", 13.0))))
    except (TypeError, ValueError):
        ui["sky_span_hours"] = 13.0
    ui["sod_roll"] = bool(ui.get("sod_roll", True))
    ui["sod_roll_idle"] = bool(ui.get("sod_roll_idle", True))
    try:
        ui["sod_roll_idle_speed"] = min(0.5, max(0.0, float(ui.get("sod_roll_idle_speed", 0.012))))
    except (TypeError, ValueError):
        ui["sod_roll_idle_speed"] = 0.012
    ui["quote"] = bool(ui.get("quote", True))
    ui["quote_shuffle"] = bool(ui.get("quote_shuffle", True))
    qs = ui.get("quotes")
    if not isinstance(qs, list):
        qs = []
    ui["quotes"] = [str(s).strip() for s in qs if str(s).strip()]

    fx = ui.get("fx") or {}
    for key in ("greeting", "milestone", "celebrate", "offer", "life", "moon",
            "weather"):
        fx[key] = bool(fx.get(key, True))
    fx["offer_idle_seconds"] = max(5, min(600, as_int(fx.get("offer_idle_seconds"), 25)))
    # 帧率：auto = 启动时量几帧再定档。旧版默认就是 60，而且老校验会把手动档位
    # 也压回数字存起来（分不清选过没），所以数字一律按"没选过"处理：60→auto。
    fps = fx.get("fps", "auto")
    if isinstance(fps, (int, float)) or str(fps).strip().isdigit():
        n = as_int(fps, 0)
        fps = "auto" if n >= 45 else ("mid" if n >= 22 else "low")
    elif str(fps) not in ("auto", "high", "mid", "low"):
        fps = "auto"
    fx["fps"] = str(fps)
    fx["props"] = bool(fx.get("props", True))
    ui["fx"] = fx
    cfg["ui"] = ui

    sc = cfg.get("schedule") or {}
    sc["onsite_hours"] = max(1.0, min(24.0, as_float(sc.get("onsite_hours"), 9.0)))
    # 下班时刻：用户选过就是一个 HH:MM；空字符串 = 还没选过，按在岗时长推算
    off = str(sc.get("offwork_time") or "").strip()
    sc["offwork_time"] = _hhmm(off, "") if ":" in off else ""
    sc["lunch_start"] = _hhmm(sc.get("lunch_start"), "12:00")
    # 午休时长是主键；老配置里只有 lunch_end 的，用 start/end 反推时长
    if "lunch_minutes" in sc:
        sc["lunch_minutes"] = max(0, min(240, as_int(sc.get("lunch_minutes"), 60)))
    else:
        sc["lunch_minutes"] = _span_minutes(sc.get("lunch_start"), sc.get("lunch_end"), 60)
    sc["lunch_end"] = _add_minutes(sc["lunch_start"], sc["lunch_minutes"])
    sc["workdays"] = _workdays(sc.get("workdays"))
    sc["ask_start_on_launch"] = bool(sc.get("ask_start_on_launch", True))
    sc["remember_start"] = bool(sc.get("remember_start", False))
    sc["setup_done"] = bool(sc.get("setup_done", False))
    cfg["schedule"] = sc

    w = cfg.get("weather") or {}
    if not isinstance(w, dict):
        w = {}
    if w.get("mode") not in ("random", "real"):
        w["mode"] = "random"
    for key in ("place", "shown", "fetched_day", "code"):
        if not isinstance(w.get(key), str):
            w[key] = ""
    w["asked"] = bool(w.get("asked", False))
    w["temp"] = as_float(w.get("temp"), None)
    w["fetched_ts"] = as_float(w.get("fetched_ts"), 0.0) or 0.0
    # 选了真实天气却没填地点，等于没选：退回随机，免得每次启动都白失败一次
    if w["mode"] == "real" and not w["place"].strip():
        w["mode"] = "random"
    cfg["weather"] = w
    return cfg


class Config:
    def __init__(self, path: Path | None = None):
        self.path = path or util.config_path()
        self.raw: dict = {}
        self.data: dict = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        self.raw = util.read_json(self.path)
        merged = util.deep_merge(DEFAULT_CONFIG, self.raw)
        self.data = _coerce_types(merged)

    def save(self) -> None:
        # 保留用户自定义的其它键，同时把默认键补齐
        merged = util.deep_merge(self.raw, self.data)
        util.write_json(self.path, merged)
        self.raw = merged

    # -- 便捷访问 -------------------------------------------------------
    def get(self, dotted: str, default=None):
        cur = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        cur = self.data
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value
