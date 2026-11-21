"""像素字体渲染。

* 数字 / 拉丁字母：手写 5x7 点阵，与 MC 原版 ascii 字体同一套网格，任意整数倍放大都绝对锐利。
* 中文：以 12/16px 无抗锯齿渲染后整数倍最近邻放大，得到 MC 那种「12px 点阵中文字」的观感
  （MC 中文就是 12px unifont 点阵）。
* 若 assets/fonts 下放了真正的像素字体（如 Zpix、缝合像素字体），会自动优先使用。
"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QImage, QPainter

# ---------------------------------------------------------------- 5x7 点阵
_G = {
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    ":": (".....", "..#..", "..#..", ".....", "..#..", "..#..", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", "..#..", "..#.."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    "/": ("....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."),
    "%": ("##..#", "##.#.", "...#.", "..#..", ".#...", "#.##.", "..##."),
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("###..", "#..#.", "#...#", "#...#", "#...#", "#..#.", "###.."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
}

GLYPH_W = 5
GLYPH_H = 7
GLYPH_GAP = 1

# 中文/拉丁字体族优先级（真正装了像素字体的机器自动升级质感）
_PIXEL_FAMILY_CANDIDATES = (
    "Zpix",
    "Fusion Pixel 12px monospaced zh_hans",
    "Fusion Pixel 12px",
    "缝合像素字体",
    "unifont",
    "SimSun",
    "NSimSun",
    "Microsoft YaHei",
)


def pixel_family() -> str:
    available = set(QFontDatabase.families())
    for fam in _PIXEL_FAMILY_CANDIDATES:
        if fam in available:
            return fam
    return "Microsoft YaHei"


def text_width(text: str, k: int) -> int:
    """5x7 点阵字符串宽度（含字符间距，末尾不留空隙）。"""
    n = len(text)
    if n <= 0:
        return 0
    return n * GLYPH_W * k + (n - 1) * GLYPH_GAP * k


def text_height(k: int) -> int:
    return GLYPH_H * k


def draw_bits(p: QPainter, x: int, y: int, text: str, k: int, color: QColor,
              shadow: QColor | None = None) -> int:
    """画点阵字符串，(x, y) 为左上角，返回占用宽度。"""
    if shadow is not None:
        draw_bits(p, x + k, y + k, text, k, shadow, None)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    cx = x
    for ch in text.upper():
        rows = _G.get(ch)
        if rows is None:
            rows = _G[" "] if ch != " " else _G[" "]
        for ry, row in enumerate(rows):
            run_start = -1
            for rx in range(GLYPH_W + 1):
                on = rx < GLYPH_W and row[rx] == "#"
                if on and run_start < 0:
                    run_start = rx
                elif not on and run_start >= 0:
                    p.drawRect(QRect(cx + run_start * k, y + ry * k,
                                     (rx - run_start) * k, k))
                    run_start = -1
        cx += (GLYPH_W + GLYPH_GAP) * k
    return text_width(text, k)


# ---------------------------------------------------------------- 中文像素化
_cjk_cache: dict[tuple, QImage] = {}
_CJK_CACHE_MAX = 400


def _cjk_image(text: str, base: int, scale: int, color: QColor, family: str, bold: bool) -> QImage:
    key = (text, base, scale, color.rgba(), family, bold)
    hit = _cjk_cache.get(key)
    if hit is not None:
        return hit
    font = QFont(family)
    font.setPixelSize(max(8, base))
    font.setBold(bold)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    fm = QFontMetrics(font)
    w = max(1, fm.horizontalAdvance(text) + 2)
    h = max(1, fm.height() + 1)
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    ip = QPainter(img)
    ip.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
    ip.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    ip.setFont(font)
    ip.setPen(color)
    ip.drawText(1, fm.ascent(), text)
    ip.end()
    if scale > 1:
        img = img.scaled(w * scale, h * scale, Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.FastTransformation)
    if len(_cjk_cache) > _CJK_CACHE_MAX:
        _cjk_cache.clear()
    _cjk_cache[key] = img
    return img


def cjk_size(target_h: int) -> tuple[int, int]:
    """返回 (base, scale)：目标像素高度 → 12/16px 点阵的整数倍。"""
    target_h = max(8, int(target_h))
    if target_h >= 22:
        return 12, max(2, int(round(target_h / 12.0)))
    return target_h, 1


def draw_cjk(p: QPainter, x: int, y: int, text: str, h: int, color: QColor,
             family: str, shadow: QColor | None = None, bold: bool = False,
             align: str = "left", max_w: int | None = None) -> int:
    """画中文/混排文字，(x, y) 为左上角，h 为目标高度，返回宽度。"""
    base, scale = cjk_size(h)
    img = _cjk_image(text, base, scale, color, family, bold)
    if shadow is not None:
        sh = _cjk_image(text, base, scale, shadow, family, bold)
        p.drawImage(x + scale, y + scale, sh)
    if align == "center" and max_w is not None:
        x = x + (max_w - img.width()) // 2
    elif align == "right" and max_w is not None:
        x = x + max_w - img.width()
    p.drawImage(x, y, img)
    return img.width()


def measure_cjk(text: str, h: int, family: str, bold: bool = False) -> tuple[int, int]:
    base, scale = cjk_size(h)
    img = _cjk_image(text, base, scale, QColor(255, 255, 255), family, bold)
    return img.width(), img.height()


_ink_cache: dict[tuple, tuple[int, int]] = {}


def ink_pads(text: str, h: int, family: str, bold: bool = False) -> tuple[int, int]:
    """字形墨迹在图像内的上 / 下留白（像素）。

    中文字模自带上下空白，按图像高度居中会让墨迹偏上；要"看着正"得按墨迹居中。
    """
    key = (text, h, family, bold)
    hit = _ink_cache.get(key)
    if hit is not None:
        return hit
    base, scale = cjk_size(h)
    img = _cjk_image(text, base, scale, QColor(255, 255, 255), family, bold)
    top, bot = 0, img.height() - 1
    for y in range(img.height()):
        row = False
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 0:
                row = True
                break
        if row:
            top = y
            break
    for y in range(img.height() - 1, -1, -1):
        col = False
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 0:
                col = True
                break
        if col:
            bot = y
            break
    pads = (top, img.height() - 1 - bot)
    if len(_ink_cache) > _CJK_CACHE_MAX:
        _ink_cache.clear()
    _ink_cache[key] = pads
    return pads


def draw_cjk_vcenter(p: QPainter, x: int, band_top: int, band_h: int, text: str, h: int,
                     color: QColor, family: str, shadow: QColor | None = None,
                     bold: bool = False, align: str = "left",
                     max_w: int | None = None) -> int:
    """在 [band_top, band_top+band_h) 这条带子里按墨迹垂直居中地画文字。"""
    _, ih = measure_cjk(text, h, family, bold)
    top_pad, bot_pad = ink_pads(text, h, family, bold)
    y = band_top + (band_h - ih) // 2 + (bot_pad - top_pad + 1) // 2
    return draw_cjk(p, x, y, text, h, color, family, shadow=shadow, bold=bold,
                    align=align, max_w=max_w)


def draw_items(p: QPainter, center_x: int, bottom: int, items: list, color: QColor,
               family: str, shadow: QColor | None = None) -> int:
    """水平居中绘制混排片段。

    items 元素（全部使用物理像素）：
      ("b", text, k)      5x7 点阵，k = 放大倍数
      ("c", text, h_px)   中文，目标高度
      ("g", gap_px)       空隙
    返回总宽度。
    """
    widths: list[int] = []
    for it in items:
        if it[0] == "b":
            widths.append(text_width(it[1], it[2]))
        elif it[0] == "c":
            widths.append(measure_cjk(it[1], it[2], family)[0])
        else:
            widths.append(int(it[1]))
    total = sum(widths)
    x = center_x - total // 2
    for it, wd in zip(items, widths):
        if it[0] == "b":
            draw_bits(p, x, bottom - text_height(it[2]), it[1], it[2], color, shadow)
        elif it[0] == "c":
            base, sc = cjk_size(it[2])
            draw_cjk(p, x, bottom - base * sc, it[1], it[2], color, family, shadow=shadow)
        x += wd
    return total


def mixed_width(text: str, h: int, family: str) -> int:
    """估算混排宽度：ASCII 用点阵、中文用像素字。"""
    k = max(1, int(round(h / GLYPH_H)))
    w = 0
    for ch in text:
        if ch.isascii() and ch.upper() in _G:
            w += (GLYPH_W + GLYPH_GAP) * k
        else:
            base, scale = cjk_size(h)
            w += int(base * scale * 1.0)
    return w
