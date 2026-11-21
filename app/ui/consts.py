"""窗口尺寸档位与星期名。

单独放一个文件，是为了让 app/ui 下的小模块能用到，而不用反过来依赖窗口本体
（那会形成互相导入）。app/widget.py 仍然把它们转发出去，老的 import 照旧有效。
"""
from __future__ import annotations

WEEK_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

# 三档窗口尺寸：单位数是"逻辑布局"，S 是整数倍像素，所以切档永远是重绘而不是拉伸。
# small 走紧凑布局（无标签、无底栏），standard / large 共用完整布局，large 多一档像素。
TIERS: dict[str, dict] = {
    "small":    {"label": "小", "w": 168, "h": 56, "compact": True,  "s_add": 0},
    "standard": {"label": "标准", "w": 216, "h": 127, "compact": False, "s_add": 0},
    "large":    {"label": "大", "w": 216, "h": 127, "compact": False, "s_add": 1},
}
TIER_ORDER = ("small", "standard", "large")
