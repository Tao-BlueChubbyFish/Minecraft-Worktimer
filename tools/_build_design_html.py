"""生成设计预览页（把三张渲染帧 + 规范 + 时序拼成一张可读的设计稿）。

用法：python tools/_build_design_html.py
输出：设计预览-F1F2F3.html（图片内嵌 base64，单文件可拷走）
"""
from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "design"


def b64(name: str) -> str:
    return base64.b64encode((ASSETS / name).read_bytes()).decode()


CSS = """
:root{
  --ink:#1c1b19; --dim:#6b665e; --line:#dcd7cd; --paper:#fbfaf7;
  --wood:#9c7250; --grass:#5e7a36; --gold:#b8860b; --amber:#b8541f;
}
*{box-sizing:border-box}
body{
  margin:0; padding:48px 24px 72px; background:#eeece6; color:var(--ink);
  font:15px/1.75 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased;
}
.page{max-width:1080px;margin:0 auto}
.eyebrow{
  font:600 12px/1 ui-monospace,Consolas,monospace;letter-spacing:.16em;
  text-transform:uppercase;color:var(--dim);margin-bottom:14px
}
h1{font-size:30px;line-height:1.35;margin:0 0 12px;letter-spacing:-.01em}
.lede{font-size:16px;color:#403c37;margin:0 0 8px;max-width:74ch}
.meta{font:12px/1.6 ui-monospace,Consolas,monospace;color:var(--dim);margin-top:18px}
hr{border:0;border-top:1px solid var(--line);margin:40px 0}
h2{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);
   margin:0 0 18px;font-family:ui-monospace,Consolas,monospace;font-weight:600}
.frame{
  background:var(--paper);border:1px solid var(--line);border-radius:4px;
  padding:22px 22px 18px;margin-bottom:22px
}
.frame-head{display:flex;align-items:baseline;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.tag{
  font:600 11px/1 ui-monospace,Consolas,monospace;padding:5px 8px;border-radius:3px;
  background:#1c1b19;color:#fff;letter-spacing:.08em
}
.tag.f2{background:var(--gold)}
.tag.f3{background:var(--grass)}
.frame-head b{font-size:16px}
.frame-head span{color:var(--dim);font-size:13px}
.shot{display:block;width:100%;height:auto;border-radius:3px;
      box-shadow:0 1px 0 #fff inset, 0 6px 18px rgba(0,0,0,.10)}
.calls{list-style:none;padding:0;margin:16px 0 0;
       display:grid;grid-template-columns:1fr 1fr;gap:6px 26px}
.calls li{font-size:13.5px;color:#3a3733;padding-left:22px;position:relative}
.calls li em{
  position:absolute;left:0;top:2px;font:600 11px/16px ui-monospace,Consolas,monospace;
  width:16px;height:16px;text-align:center;border-radius:50%;font-style:normal;
  background:#1c1b19;color:#fff
}
.tl{display:grid;grid-template-columns:78px 1fr;gap:10px 16px;align-items:center;
    font:12px/1 ui-monospace,Consolas,monospace;color:var(--dim)}
.bar{position:relative;height:26px;background:#f2f0ea;border-radius:3px;overflow:hidden;
     border:1px solid var(--line)}
.seg{position:absolute;top:0;bottom:0;display:flex;align-items:center;justify-content:center;
     font-size:10.5px;color:#fff;white-space:nowrap;overflow:hidden}
.s1{background:#3b3a37}.s2{background:var(--grass)}.s3{background:var(--wood)}
.s4{background:var(--gold)}.s5{background:var(--amber)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font:600 11px/1.4 ui-monospace,Consolas,monospace;letter-spacing:.1em;
   text-transform:uppercase;color:var(--dim)}
td code,code{font:12.5px ui-monospace,Consolas,monospace;background:#eeeae1;
  padding:1px 5px;border-radius:3px}
.sw{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:7px;
    vertical-align:-1px;border:1px solid rgba(0,0,0,.18)}
.note{background:#fff8e6;border:1px solid #ecd9a8;border-radius:4px;padding:16px 18px;
      font-size:14px;margin:6px 0 0}
.note b{color:#8a5b00}
.evidence{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:14px;
          align-items:start}
.evidence figure{margin:0}
.evidence img{width:100%;image-rendering:pixelated;border-radius:3px;display:block}
figcaption{font:11.5px/1.6 ui-monospace,Consolas,monospace;color:var(--dim);margin-top:7px}
.q{font-size:14px;margin:0;padding-left:2px}
.q li{margin-bottom:9px}
.foot{font:12px/1.8 ui-monospace,Consolas,monospace;color:var(--dim);margin-top:44px}
"""


def frame(tag: str, cls: str, title: str, when: str, img: str, calls: list[str]) -> str:
    items = "".join(f"<li><em>{i + 1}</em>{c}</li>" for i, c in enumerate(calls))
    return f"""
<section class="frame">
  <div class="frame-head">
    <span class="tag {cls}">{tag}</span><b>{title}</b><span>{when}</span>
  </div>
  <img class="shot" src="data:image/png;base64,{b64(img)}" alt="{title}">
  <ul class="calls">{items}</ul>
</section>"""


def seg(cls: str, left: float, width: float, label: str) -> str:
    return (f'<div class="seg {cls}" style="left:{left}%;width:{width}%">{label}</div>')


def main() -> None:
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>MC 工时牌 · 情绪化改造设计预览（F1/F2/F3）</title>
<style>{CSS}</style></head>
<body><div class="page">

<div class="eyebrow">MC 工时牌 · 设计预览 v1.1 · 已实现</div>
<h1>情绪化改造：F1 收工瞬间 / F2 里程碑 / F3 时段问候</h1>
<p class="lede">三张都是<strong>实机渲染帧</strong>（标准档 432×232，像素 2 倍放大），不是画稿——
你现在看到的排版、字号、配色就是实现后的样子。整个改造<b>不新增面板、不改布局常数</b>，
只挪用现有的三个位置：顶部标题、右下百分比、大号数字那一行。</p>
<div class="note" style="margin:16px 0 0">
<b>已按此稿实现。</b>最终版比这张稿多了三处（都是后来提的需求）：木牌文案改成每天随机、
悬停或点击会展开「回家 / 再干会儿」两个按钮、回家庆祝换成了 6 簇烟花 + 44 片彩纸；
另外进度条上多了一面午休小旗。以 <code>README.md</code> 和 <code>assets/preview_*.png</code> 为准。
</div>
<div class="meta">渲染：py tools/_design_fx.py ｜ 依赖 app/theme.py 现有绘制（仅叠加，未改逻辑）</div>

<hr>
<h2>一、三个瞬间</h2>

{frame("F3", "f3", "时段问候", "09:24 · 距离下班 08:36", "fx_1_greeting.png", [
    "标题位由固定「工作计时」改成按时段/状态的一句话，这里显示「开工了」。",
    "位置、字号、草皮带中线全部不动，所以不会挤到图标和右上角菜单。",
    "换句逻辑沿用每日一句的日期取模：同一天刷新不变，跨天不重样。",
    "小档（168×56）顶部本来显示状态短文案，同一套问候直接复用。",
])}

{frame("F2", "f2", "里程碑", "14:02 · 刚过 50%", "fx_2_milestone.png", [
    "草皮卷离地 2 单位跳一下（0.2 秒），底部扬 3 粒土——「过了一个坎」的动作。",
    "右下角百分比变金色，并加 1 单位深金描边，持续 1.2 秒后回灰。",
    "标题同时切到里程碑短语「走了一半」，8 秒后回到时段问候。",
    "三处一起响，但每处都很小：不用粒子，靠「数字变金」这个形状差异。",
])}

{frame("F1", "f1", "收工瞬间", "18:01 · 达成 9 小时", "fx_3_done.png", [
    "木牌从进度条里升起，停在大号数字那一行；数字行让位 2.6 秒后恢复。",
    "牌面 2 单位硬描边 + 上沿受光/下沿背光，四角各一颗 1 单位白钉。",
    "木牌两侧四颗十字星芒，白 → 金，错峰 0.2 秒亮起。",
    "草皮卷从右边缘滚出画面（0.3 秒），尾巴扬一串土——收尾交给它。",
])}

<hr>
<h2>二、动效时序</h2>
<div class="tl">
  <span>F3 问候</span>
  <div class="bar">{seg("s2", 0, 100, "全天常驻 · 只在跨状态 / 跨时段时换一句")}</div>

  <span>F2 卷跳 · 0.2s</span>
  <div class="bar">{seg("s1", 0, 2.5, "")}</div>

  <span>F2 金色%</span>
  <div class="bar">{seg("s4", 0, 15, "1.2s 后回灰")}</div>

  <span>F2 短语</span>
  <div class="bar">{seg("s2", 0, 100, "8s 后回到时段问候")}</div>

  <span>F1 卷滚出 · 0.3s</span>
  <div class="bar">{seg("s3", 0, 11.5, "")}</div>

  <span>F1 木牌</span>
  <div class="bar">
    {seg("s1", 9.6, 19.2, "升起")}{seg("s3", 28.8, 59.6, "停留 1.5s")}{seg("s1", 88.4, 11.6, "落下")}
  </div>

  <span>F1 星芒 · 各 0.4s</span>
  <div class="bar">
    {seg("s4", 7.7, 15.4, "")}{seg("s4", 17.3, 15.4, "")}
  </div>
</div>
<p class="meta" style="margin-top:12px">总时长 2.6 秒，结束后自动回到 1 帧/秒的常态刷新；
动效期间临时提到 25fps，复用现有 <code>_anim_step</code> 定时器，不新增常驻定时器。</p>

<hr>
<h2>三、规范</h2>
<table>
<tr><th>项</th><th>值</th><th>说明</th></tr>
<tr><td>网格</td><td><code>1 单位 = 2px</code></td><td>全部坐标落在整数单位上，放大用最近邻，不糊</td></tr>
<tr><td>问候字号</td><td>11 单位（22px）</td><td>与现在的标题一致，22px 是点阵字的粗细分界</td></tr>
<tr><td>问候长度</td><td>≤ 6 个汉字</td><td>超了会被右上角菜单按钮挤掉，实现里按长度自动降一档</td></tr>
<tr><td>木牌</td><td>17 单位高 · 约 44 单位宽</td><td>宽度按文案动态算：<code>字宽 + 17 单位</code>留白</td></tr>
<tr><td>木牌配色</td><td>
  <span class="sw" style="background:#9c7250"></span><code>#9c7250</code>
  <span class="sw" style="background:#a87c58"></span><code>#a87c58</code>
  <span class="sw" style="background:#7a5639"></span><code>#7a5639</code>
</td><td>牌面 / 上沿受光 / 下沿背光，全部取自现有 dirt 色阶</td></tr>
<tr><td>字与描边</td><td>
  <span class="sw" style="background:#ffffff"></span><code>#ffffff</code>
  <span class="sw" style="background:#1f3312"></span><code>#1f3312</code>
  <span class="sw" style="background:#1b1b1b"></span><code>#1b1b1b</code>
</td><td>牌面文字 / 文字阴影 / 2 单位硬描边</td></tr>
<tr><td>金色</td><td><span class="sw" style="background:#ffd75e"></span><code>#ffd75e</code></td>
    <td>里程碑百分比与星芒共用；不用 warn 橙，避免和「加班」语义撞色</td></tr>
<tr><td>节流</td><td>单次 ≤ 3 秒 · 一天 ≤ 5 次</td><td>里程碑 4 次 + 收工 1 次，正好用满，不再加</td></tr>
</table>

<hr>
<h2>四、两处与原计划不同的地方</h2>
<p class="lede">原计划里 F2 是「花瓣爆开」、F1 是「像素烟花」。实机渲染出来都<b>读不出来</b>，
所以换了表达方式——判断依据就是下面这张放大对照。</p>

<div class="evidence">
  <figure>
    <img src="data:image/png;base64,{b64("evidence_petals.png")}" alt="花瓣爆开在实机下的效果">
    <figcaption>花瓣爆开 · 6 倍放大：卷右边那簇紫黄点就是"花瓣"，
    但草地本身就长满同样的花，它只会被读成"旁边又开了一朵"。</figcaption>
  </figure>
  <figure>
    <img src="data:image/png;base64,{b64("fx_3_done.png")}" alt="收工瞬间">
    <figcaption>同样的位置改成「木牌 + 十字星芒 + 金色百分比」：
    形状是新的（方牌/十字），不依赖粒子密度，一瞥就成立。</figcaption>
  </figure>
</div>

<div class="note" style="margin-top:18px">
<b>为什么换：</b>进度条里几乎没有空地——花冠长到贴着上沿，任何 1 单位的粒子都会糊进花海；
面板灰底上小圆环又太淡，看着像脏点。结论是<b>这个尺寸下只认"形状变化"和"颜色跳变"，
不认"粒子数量"</b>。所以：<br>
· F2 从"花瓣"改成 <b>卷跳 + 百分比变金 + 短语</b>；<br>
· F1 从"圆环烟花"改成 <b>十字星芒</b>（5~9 个像素，形状本身自明）+ 木牌。
</div>

<hr>
<h2>五、开关与降级</h2>
<table>
<tr><th>配置</th><th>默认</th><th>关掉之后</th></tr>
<tr><td><code>fx.greeting</code></td><td>开</td><td>标题回到「工作计时」，其余不动</td></tr>
<tr><td><code>fx.milestone</code></td><td>开</td><td>没有卷跳、没有金色百分比、短语不切</td></tr>
<tr><td><code>fx.celebrate</code></td><td>开</td><td>18:00 只是数字变化，不弹木牌</td></tr>
</table>
<p class="meta">三个开关全关时，界面与现在<b>逐像素一致</b>——新东西都是叠加在绘制末尾的，
不参与主布局计算。</p>

<hr>
<h2>六、需要你拍板的 5 件事</h2>
<ol class="q">
<li><b>木牌文案</b>：现在是「收工」两字（比例最舒服）。备选「下班了」「今天到这」。</li>
<li><b>木牌位置</b>：现在盖住大号数字那一行 2.6 秒。若不想遮数字，可改到进度条内（会挡草地）。</li>
<li><b>金色百分比</b>：里程碑时右下角 50% 变金 1.2 秒。有人会觉得太抢眼，可只保留卷跳。</li>
<li><b>里程碑时刻</b>：25 / 50 / 75 / 90% 四个，还是只留 50% 与 90%（少即是多）。</li>
<li><b>问候基调</b>：现在是朴素的「开工了 / 走了一半 / 快熬到头 / 该回家了」。
   要不要掺一点自嘲梗（例：「今天也要好好活着」），还是保持干净不抖机灵。</li>
</ol>

<div class="foot">
帧源文件：assets/design/fx_1_greeting.png · fx_2_milestone.png · fx_3_done.png<br>
重新出图：python tools/_design_fx.py ｜ 重新生成本页：python tools/_build_design_html.py
</div>

</div></body></html>"""
    out = ROOT / "docs" / "设计预览-F1F2F3.html"
    out.write_text(html, encoding="utf-8")
    print(out, f"{out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
