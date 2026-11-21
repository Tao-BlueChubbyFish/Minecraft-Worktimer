"""比对两组底片：逐像素找出差异，把不一样的地方标红存成图。

这不是程序的一部分，只是"对照片"用的放大镜。

用法：
    python tools/compare_shots.py <改造前目录> <改造后目录> [差异图存放目录]

退出码 0 = 全部一模一样；1 = 有差异或有缺失。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage   # noqa: E402

if len(sys.argv) < 3:
    print("用法: python tools/compare_shots.py <改造前目录> <改造后目录> [差异图目录]")
    raise SystemExit(2)

BEFORE = Path(sys.argv[1])
AFTER = Path(sys.argv[2])
DIFF = Path(sys.argv[3]) if len(sys.argv) > 3 else AFTER.parent / "差异图"
DIFF.mkdir(parents=True, exist_ok=True)


def compare(pa: Path, pb: Path):
    """返回 (差异像素数, 最大单通道差值, 差异图或 None, 说明)。"""
    ia = QImage(str(pa))
    ib = QImage(str(pb))
    if ia.isNull() or ib.isNull():
        return -1, 0, None, "图片读不出来"
    if ia.size() != ib.size():
        return -1, 0, None, f"尺寸不同 {ia.width()}x{ia.height()} vs {ib.width()}x{ib.height()}"

    a = ia.convertToFormat(QImage.Format.Format_RGBA8888)
    b = ib.convertToFormat(QImage.Format.Format_RGBA8888)
    ba = bytes(a.constBits())
    bb = bytes(b.constBits())
    if ba == bb:
        return 0, 0, None, "一致"

    w, h = a.width(), a.height()
    out = QImage(a)
    red = QColor(255, 0, 0, 255)
    count, worst = 0, 0
    for y in range(h):
        base = y * w * 4
        for x in range(w):
            i = base + x * 4
            if ba[i:i + 4] != bb[i:i + 4]:
                count += 1
                d = max(abs(ba[i + k] - bb[i + k]) for k in range(4))
                if d > worst:
                    worst = d
                out.setPixelColor(x, y, red)
    return count, worst, out, "不一致"


def main() -> int:
    names = sorted(p.name for p in BEFORE.glob("*.png"))
    if not names:
        print(f"改造前目录里没有图：{BEFORE}")
        return 1

    bad = 0
    print(f"{'图片':24s}{'结果'}")
    print("-" * 60)
    for name in names:
        pb = AFTER / name
        if not pb.exists():
            print(f"{name:24s}缺失（改造后没拍这张）")
            bad += 1
            continue
        count, worst, out, note = compare(BEFORE / name, pb)
        if count == 0:
            print(f"{name:24s}一致")
        else:
            if count > 0:
                print(f"{name:24s}不一致：{count} 个像素点，最大色差 {worst}/255")
                out.save(str(DIFF / f"{Path(name).stem}_diff.png"))
            else:
                print(f"{name:24s}{note}")
            bad += 1

    extra = sorted({p.name for p in AFTER.glob("*.png")} - set(names))
    for name in extra:
        print(f"{name:24s}多出来的图（改造前没有）")

    print("-" * 60)
    if bad:
        print(f"有 {bad} 张对不上，差异图已存到：{DIFF}")
        return 1
    print(f"全部 {len(names)} 张完全一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
