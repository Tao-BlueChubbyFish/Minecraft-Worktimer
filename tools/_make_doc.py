# -*- coding: utf-8 -*-
"""生成《更新文档-v1.3.docx》（开发自检 / 重出文档用，不进打包）。

    python tools/_make_doc.py

配图来自 %TEMP% 下的两张截图（设置窗、雪天整窗），缺图会在文档里标出来。
"""

from __future__ import annotations

import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

TEMP = os.environ.get("TEMP") or r"C:\Users\24892\AppData\Local\Temp"
PIC_SETTINGS = os.path.join(TEMP, "settings_dlg_v13.png")
PIC_SNOW = os.path.join(TEMP, "snow_b.png")
OUT = r"D:/小房间/更新文档-v1.3.docx"

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


def para(text):
    doc.add_paragraph().add_run(text)


def bullet(text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.9)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.4
    p.add_run(text)


def lead(text):
    """题记：一句话说清这一版的魂，排在标题下面。"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(14)
    r = p.add_run(text)
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.color.rgb = GREEN


def pic(path, caption, width=15.2):
    if not path or not os.path.exists(path):
        para("（缺图：%s）" % path)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(path, width=Cm(width))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(14)
    r = c.add_run(caption)
    r.font.size = Pt(9)
    r.font.color.rgb = GREY


title("MC 工时牌 v1.3 更新说明：同一片天")
sub("一个放在桌面角落的像素风工时小牌子　·　2026-11-22")
lead("外面什么天，窗上就是什么天。")

para("这一版只做一件事：让窗上那片天变成真的。剩下几处，是你之前看着别扭、一直想改的地方。")

h1("一、接上真实天气")
para("以前的天是“掷骰子”定的——今天该晴该雨，日期一算就知道，可它跟窗外一点关系都没有。"
     "你在下雨，它可能在晒。")
para("现在不一样了。打开「设置」，勾上最下面那个「真实天气」，填一个地名（填到市就行，"
     "不知道写哪个就先填省会），保存。之后窗上就是你头顶那片天：晴、阴、小雨、大雨、小雪、大雪。")
para("几个你可能会问的事：")
bullet("不用注册、不用填账号，也不花钱。")
bullet("软件隔几个小时自己去问一次天气，问的时候才联网；平时不占网。")
bullet("没网、或者地名填错了，它不会把界面弄花：原来的天气先留着，过一会儿再试。"
       "地名真的找不到才会清掉那一栏，你改一下再保存就行。")
bullet("真实天气只改「窗上显示什么」，上班时间、工时统计这些一律不动。")
pic(PIC_SETTINGS, "图 1　设置窗：最下面一行勾上「真实天气」，填好地点就生效", width=8.4)

h1("二、冬天会真的积雪")
para("下雪天，顶栏那条草皮上会压一层雪，厚薄跟着当天的天走：大雪最厚，小雪次之，"
     "晴阴天只留薄薄一层残雪。温度也算进去了——零下照常积，零到四度只积一点，四度以上一点不留："
     "下雨的冬天，草皮就不该白。")
para("雪面是从最上面一路压下来的五层颜色，最上一层亮得发白，越往下越冷；"
     "边沿是缓坡，不是锯齿。左上角那个草方块不盖雪——它是斜的，雪从四个角露出来会像被冻在冰里。")
pic(PIC_SNOW, "图 2　大雪那天的样子：顶栏积雪，天上飘雪，地下还是那块暖棕色的土")

h1("三、帧率它自己挑，不用你管")
para("以前默认就往 60 帧上跑，机器弱一点就吃力。现在第一次启动时它先试着画几帧，"
     "这台机器跑得动就 60，跑不太动就 30，实在吃力就 15——按机器来，不硬撑。")
para("想自己定：右键菜单 →「帧率」→ 高 / 中 / 低（省电）。三个档里，勾着的是眼下真正在用的那档。"
     "调低以后画面照样在动，只是慢一点，风扇会安静不少。")

h1("四、两个设置窗合成一个")
para("原来「改上班时间」和「设置」点开是两个窗，内容是重复的。现在只剩一个「设置」，"
     "上班、下班、午休、哪几天上班、真实天气，全在一张里。")
para("第一次打开软件会弹它一次，之后就记住了，不再主动弹。想临时改今天几点到的，"
     "照旧点窗前的空白处，那个快速登记还在。")

h1("五、顺手的修正")
bullet("泥土颜色：以前它会跟着草一起换季，一到冬天就变成灰黄发绿，像长了霉。"
       "现在一年四季都是那块暖棕色的土，冬天只是稍微冷一点、暗一点。")
bullet("云走得慢了也匀了：原来按“格”跳，小窗口反而挪得更快；现在按像素慢慢挪，几秒才动一格，"
       "看着像云，也省电。")
bullet("雨不再“上一格下一格”地抖，落得连贯了。")

h1("六、升级怎么升")
bullet("用 exe 的：新 exe 覆盖旧的就行。config.json（设置）和 data.json（台账）千万别删——"
       "台账删了记录就没了。")
bullet("用源码的：替换 app 文件夹和 main.py，配置照旧能用。")

doc.save(OUT)
print("已生成：", OUT)
