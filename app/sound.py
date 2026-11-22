"""两声音效：下班一声、里程碑一声。

不打包 wav。声音是当场算出来的三角波，写进内存里的 wav 头，交给 Windows 播——
省了素材文件，也省了打包时"资源漏拷"这一类错误。

为什么是三角波：方波太刺耳，正弦太"电子琴"，三角波介于两者之间，
衰减给快一点（像敲一下木牌），短促、不打扰。默认是关的，见 `ui.fx.sound`。
"""
from __future__ import annotations

import io
import math
import struct
import threading
import wave

RATE = 22050
_cache: dict[str, bytes] = {}

# 每声 = (频率 Hz, 时长 ms)。下行 = 收工，上行 = 达成。
_TUNES = {
    "end": ((392.0, 150), (523.25, 300)),      # G4 → C5，像收工的一句"好了"
    "milestone": ((523.25, 90), (659.25, 90), (783.99, 220)),  # C5 E5 G5
}


def _tone(freq: float, ms: int, vol: float = 0.62) -> bytes:
    n = int(RATE * ms / 1000)
    out = bytearray()
    for i in range(n):
        t = i / RATE
        env = math.exp(-3.6 * t / (ms / 1000))          # 快衰减：敲一下，不是拉长音
        tri = 4.0 * abs((t * freq) % 1.0 - 0.5) - 1.0   # 三角波
        s = int(max(-1.0, min(1.0, tri * env * vol)) * 32767)
        out += struct.pack("<h", s)
    return bytes(out)


def _build(name: str) -> bytes:
    frames = b"".join(_tone(f, ms) for f, ms in _TUNES[name])
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)
    return buf.getvalue()


def play(name: str) -> None:
    """播一声。缺东西、没声卡、非 Windows——一律静默跳过，绝不让它影响画面。

    **放在线程里用同步方式播**，不用 `SND_ASYNC`：内存播放 + 异步在 Windows 上
    有静音的已知情况（调用返回、什么都不响），而同步播放是可靠的，代价是它会阻塞
    到放完——所以不能放在主线程里，否则里程碑那一刻界面会卡 0.4 秒。
    """
    try:
        import winsound
    except ImportError:
        return
    data = _cache.get(name)
    if data is None:
        data = _build(name)
        _cache[name] = data

    def _run() -> None:
        try:
            winsound.PlaySound(data, winsound.SND_MEMORY)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
