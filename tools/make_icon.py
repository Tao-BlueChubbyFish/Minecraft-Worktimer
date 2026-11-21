"""生成 assets/icon.ico（草方块图标，多尺寸 PNG-in-ICO，无第三方依赖）。"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage  # noqa: E402

from app import theme  # noqa: E402

SIZES = (16, 32, 48, 64, 128, 256)


def build_ico(pal: dict, out: Path) -> None:
    base = theme.iso_block(pal, 16, 5)      # 16x16 像素画，整数倍放大保持锐利
    blobs: list[tuple[int, bytes]] = []
    for size in SIZES:
        k = max(1, size // 16)
        img = base.scaled(16 * k, 16 * k, Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.FastTransformation)
        tmp = out.with_suffix(f".{size}.png")
        img.save(str(tmp), "PNG")
        blobs.append((size, tmp.read_bytes()))
        tmp.unlink()

    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries = b""
    body = b""
    for size, data in blobs:
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset + len(body))
        body += data
    out.write_bytes(header + entries + body)
    print(f"已生成 {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    app = QGuiApplication.instance() or QGuiApplication([])
    target = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    build_ico(theme.PALETTES["grass_stone"], target)
