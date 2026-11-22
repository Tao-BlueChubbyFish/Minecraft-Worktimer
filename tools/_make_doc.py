# -*- coding: utf-8 -*-
"""生成《更新文档-v1.2.docx》（开发自检 / 重出文档用，不进打包）。

    python tools/_make_doc.py

配图来自 D:\\小房间\\备份\\对照图-四季（四季各 31 张底片）。
"""

from __future__ import annotations

import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = r"D:/小房间/备份/对照图-四季"
OUT = r"D:/小房间/更新文档-v1.2.docx"
GRID = r"D:/小房间/备份/_四季对比.png"

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


def season_grid() -> str:
    """四季的上午并成一张 2×2：一张图就说清"同一时刻，四季不一样"。"""
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtCore import Qt

    _app = QGuiApplication.instance() or QGuiApplication([])
    order = ("spring", "summer", "autumn", "winter")
    imgs = []
    for s in order:
        p = os.path.join(BASE, s, "02_morning.png")
        if not os.path.exists(p):
            return ""
        imgs.append(QImage(p))
    w, h, gap = imgs[0].width(), imgs[0].height(), 8
    canvas = QImage(w * 2 + gap, h * 2 + gap, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.white)
    pt = QPainter(canvas)
    for i, im in enumerate(imgs):
        pt.drawImage((i % 2) * (w + gap), (i // 2) * (h + gap), im)
    pt.end()
    canvas.save(GRID)
    return GRID


title("MC 工时牌 v1.2 更新说明：光织四季")
sub("一个放在桌面角落的像素风工时小牌子　·　2026-11-21")
lead("四季会换，光不再跳。")

para("这一版没加新功能。加的是「看起来」：一年四季会换，天上的东西会动，而且动得比原来顺。")

h1("一、一年四季")
para("草地和天色跟着月份走。不是加滤镜，是每个季节换一套配色：")
bullet("春（2–4 月）：嫩绿配红花，天最清。")
bullet("夏（5–7 月）：草色最饱和，花色转暖，白天也最长。")
bullet("秋（8–11 月）：草往黄走，天上开始飘落叶。")
bullet("冬（12–1 月）：天光压到十小时，草转冷青；下雪，顶栏那层草皮会积雪。")
pic(season_grid(), "图 1　同一时刻的四季：左上春、右上夏、左下秋、右下冬"
                   "（底片各落在不同的天上：晴、阴、晴、大雪）")

h1("二、天上和地上")
bullet("雪：冬天下雪，分小雪和大雪两档，按当天的天。大雪那天，顶栏积雪也厚一层。")
bullet("落叶：秋天晴天、阴天都飘，一次三四片，橙的黄的；雨雪天不飘——天上已经够满。")
bullet("云：按真实钟点横着走，傍晚散得慢一点。")

h1("三、碰它一下")
para("鼠标点在草地上，脚边那几朵花会被推开、留一个空洞，过一会儿自己长回来；"
     "外一圈的花被推得矮一点。像往水里丢了一颗石子。")

h1("四、变流畅了")
para("画面动效从原来的一秒一格，升级到了 60 帧：云、雨雪、落叶都是连成一条线走的，"
     "不再一顿一顿。第一次启动会按这台机器的情况挑好档位；想省电，在「外观 → 流畅度」里调低就行。")
para("底下的画法也重做了一遍：同样的画面不再反复重算，CPU 占用大幅下降，"
     "笔记本的风扇会安静不少。")

h1("五、菜单瘦了")
bullet("一级菜单从 18 项压到 11 项：结算类收进「牛马日常」，显示开关收进「外观」。")
bullet("点勾选项不再关菜单，可以连着开好几个。")
bullet("天气那条拆开了：「云朵」和「下落物：雨 / 雪 / 落叶 / 无」是两个开关，想关哪个关哪个。")

h1("六、音效（默认关）")
para("下班、里程碑各响一声，是程序合成的短音，不吵。想听在「外观 → 音效」里打开。")

h1("七、升级怎么升")
bullet("用 exe 的：新 exe 覆盖旧的就行。config.json（设置）和 data.json（台账）千万别删。")
bullet("用源码的：替换 app 文件夹和 main.py，配置照旧能用。")

doc.save(OUT)
print("saved", OUT, os.path.getsize(OUT))
