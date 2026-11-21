# -*- coding: utf-8 -*-
"""生成《更新文档-v1.1.docx》（开发自检 / 重出文档用，不进打包）。

    python tools/_make_doc.py

配图来自 D:\\小房间\\_改造备份\\对照图-v1.1-正式（重拍底片后重跑一次即可刷新文档配图）。
"""
from __future__ import annotations

import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = r"D:/小房间/备份/对照图-v1.1-正式"
OUT = r"D:/小房间/更新文档-v1.1.docx"

doc = Document()
sec = doc.sections[0]
sec.left_margin = Cm(2.6)
sec.right_margin = Cm(2.6)
sec.top_margin = Cm(2.2)
sec.bottom_margin = Cm(2.2)

st = doc.styles["Normal"]
st.font.name = "微软雅黑"
st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
st.paragraph_format.line_spacing = 1.45
st.paragraph_format.space_after = Pt(6)

GREEN = RGBColor(0x3F, 0x6B, 0x24)
GREY = RGBColor(0x66, 0x66, 0x66)


def title(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    r.font.size = Pt(22)
    r.font.bold = True
    r.font.color.rgb = GREEN


def sub(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(16)
    r = p.add_run(text)
    r.font.size = Pt(9.5)
    r.font.color.rgb = GREY


def h1(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    r.font.size = Pt(15)
    r.font.bold = True
    r.font.color.rgb = GREEN


def h2(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    r.font.size = Pt(11.5)
    r.font.bold = True


def para(text):
    doc.add_paragraph().add_run(text)


def bullet(text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.9)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.4
    p.add_run(text)


def pic(name, caption, width=14.5):
    path = os.path.join(BASE, name)
    if not os.path.exists(path):
        para("（缺图：%s）" % name)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(path, width=Cm(width))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(14)
    r = c.add_run(caption)
    r.font.size = Pt(9)
    r.font.color.rgb = GREY


title("MC 工时牌 v1.1 更新说明")
sub("一个放在桌面角落的像素风工时小牌子　·　2026-11-20")

# ---------------------------------------------------------------- v1.0
h1("一、v1.0：第一版，能用了")
para("先说第一版解决的事——它本来只是一个“今天还剩多久下班”的小牌子。")
bullet("永远置顶的一小块地方：上班点一下时间，之后它自己走，不用管。")
bullet("进度条是一条草地：上班时草皮一格格往右铺过去，铺满就是下班。看着草长出来，比看数字舒服。")
bullet("午休自动暂停：默认 12:00–13:00，这段时间不算工时，进度条停在那儿。")
bullet("到点会提醒，加班继续计时，累计加班时长单独记着，可以清空。")
bullet("三种大小（小 / 标准 / 大）、三套配色；右键可以临时“穿透”，不挡鼠标。")
bullet("会缩到右下角托盘里；可以设成开机自启；所有参数都在 config.json 里，改完重启就生效。")

# ---------------------------------------------------------------- v1.1
h1("二、v1.1：这次加了什么")

h2("1. 到点了会有块木牌，给你两个选择")
para("以前到点只是弹个提示。现在会出来一块小木牌，点一下（或者鼠标停一会儿）展开两个按钮："
     "“回家”和“再干会儿”。选“回家”就收工、记下今天的成绩；选“再干会儿”就接着往上计加班时间。"
     "这个选择会记下来，重启不会再问一遍。")

h2("2. 选“回家”会放一场烟花")
para("五秒钟的庆祝：六簇烟花错峰炸开，彩纸从上往下飘，木牌上换一句祝贺的话。"
     "不闪白屏——闪一下像故障，不像庆祝。")
pic("14_celebrate_42.png", "图 1　选“回家”那一刻：烟花 + 彩纸 + 木牌换成祝贺语", 13.6)

h2("3. 走到 25% / 75% / 90% 的时候有个小反馈")
para("右下角的百分比会变成金色，草皮卷往上颠一下，顶上冒一句短语。一天里就这三次，不打扰，但你知道自己走到哪了。")

h2("4. 顶上的字会说话")
para("顶部那行标题不再固定写“工作计时”，而是按状态和时段换：刚开机、上午、午休前、快到点、加班中……"
     "每个人一天大概能看到十几种不同的句子。")

h2("5. 天上偶尔有东西路过")
bullet("鸟群：一天两三次，一队鸟排成 V 字从天上飞过去，每次路线略有不同。")
bullet("月亮：入夜之后天上会挂一个月亮，位置跟着钟点走。")
bullet("道具：草地上有三样东西——木栅栏、干草捆、石头堆。进度条铺到那个位置它们才出现，"
       "像是“开垦到哪儿，哪儿就有东西”。")

h2("6. 天气：晴 / 阴 / 小雨 / 大雨")
para("按日期自动决定，同一天里不会变来变去，也不会重启就换了天。大致比例是：晴六成多、阴两成多、"
     "小雨一成不到、大雨更少。")
bullet("阴天：天色压暗一点，云发灰。")
bullet("小雨：竖直的短雨丝，只落在天空那一段。")
bullet("大雨：雨丝又长又斜（从右上往左下浇），落得更快，天压得最暗。")
para("右键菜单里有两条：一条“今天：晴 / 阴 / 小雨 / 大雨”只告诉你今天什么天，另一条“天气效果”才是开关。"
     "拆成两条是因为晴天本来就没有任何叠加，光看开关勾没勾是看不出变化的——"
     "以前那条“天气：晴”就容易被误会成坏了。")
pic("_天气预览/downpour_morning.png", "图 2　大雨：斜着浇下来的长雨丝，天色明显压暗", 13.6)

h2("7. 午休有个小剧场")
para("午休那一个小时花会收成花苞，草地上缓缓飘起三个 z，一高一低往上走。"
     "中午没人看屏幕，所以不写字，只留一个不用读的提示。")
pic("03_lunch.png", "图 3　午休：花收成花苞，草地上飘三个 z", 13.6)

h2("8. 加班的时候，天会自己黑下去")
para("过了下班时间还不走，进度条里的天色会继续往深夜走一点。不用弹窗催你，天黑了本身就说明问题。")

h2("9. 休息日可以自己勾了（这次新加）")
para("以前只有“双休 / 单休”两个选项，但真实情况不是这样：有人单休，有人周六休但周日上班。"
     "现在设置里多了一行“上班日”，周一到周日七个格子，点亮 = 那天上班，灰 = 那天休息，点一下就能切换。")
bullet("默认是周一到周五点亮，跟以前一样。")
bullet("至少会留一天上班：把最后一个也点掉是不生效的，底下会提示“至少留一天上班”。")
bullet("改完点保存，今天的状态立刻重算——本来显示“休息日”的，可能马上变成“待登记”。")

h2("10. 上班时间可以记住（这次新加）")
para("每天早上弹窗问“今天几点开始上班”，对固定作息的人来说是多余的一步。"
     "现在那个弹窗底下多了一个勾选框：“以后每天用这个时间，不再问我”。")
bullet("勾上：以后每个工作日自动按这个时间开始计时，不再弹窗。今天手动改过的那天也不会被覆盖。")
bullet("想恢复每天问一遍：再打开弹窗，把勾去掉就行。")

h2("11. 下班时间直接选，午休也能改")
para("公司几点下班是定死的，不该按“上班加八小时”算。现在设置里下班时间是直接选的；"
     "午休也能改——几点开始、休多久（加减 15 分钟），有效工时实时跟着算，填错了会提醒。")

h2("12. 花海和进度条都升级了（这次新加）")
para("有反馈说“花要仔细看才分得出是花还是色块”，所以这次专门改了这三件事：")
bullet("进度条加高：从 22 格加到 28 格，窗口跟着高 6 格。条子占的地方更大了。")
bullet("草地加高：草地从 4 格加到 6 格，花才有地方长，不再挤成一条线。")
bullet("花更大更清楚：花冠放大一档（4 格高，宽的 5 格），每朵都加了高光和暗边，"
       "看到的是“有花心的花”，不是一块颜色。同一层里的花高度一致、间隔留够，不会连成一条彩边。")
bullet("草皮噪声收敛：顶部那条绿带以前杂色太多，远看发脏。现在只用四档很接近的绿，"
       "远看是一条干净的绿带，近看还有细微颗粒。")
pic("02_morning.png", "图 4　上午：进度条更高、草地更宽，花是一朵一朵的", 13.6)

h2("13. 每日一句：500 多条")
para("进度条下面那行小字，按日期换，同一天不会变来变去。内置 500 多条（含一些游戏台词），"
     "也可以把自己喜欢的句子写进 config.json 的 ui.quotes 里，写进去就优先用你的。")

# ---------------------------------------------------------------- 怎么用
h1("三、两个新功能，怎么用")
h2("休息日怎么勾")
para("右键 →“设置…” → 看最下面那一行“上班日”。七个格子，点亮的是上班的日子。"
     "比如“周六休息、周日上班”，就把“六”点灰、“日”点亮，然后点“保存”。")
h2("记住上班时间怎么用")
para("右键 →“修改今日上班时间…” → 选好时间，把最下面那行“以后每天用这个时间，不再问我”勾上 → 点“确定”。"
     "以后工作日就不用再点了。想改回每天询问，同一个地方把勾去掉。")

# ---------------------------------------------------------------- 文件
h1("四、文件都在哪")
bullet("exe 启动版：双击就能用，不需要装 Python。里面有 config.json（设置）和 data.json（台账），别删。")
bullet("Python 版：源码目录，改代码、跑自检都在这里。")
bullet("打包工程：打 exe 用的配置，双击“一键打包exe.bat”就会重新生成一个 exe。")
bullet("备份：历次改动前后的截图对照，出问题可以回头比。")
para("注意：如果开了“开机自启”，换过文件夹之后要在右键菜单里把“开机自启”关一次、再开一次，让它记住新位置。")

doc.save(OUT)
print("saved", OUT, os.path.getsize(OUT))
