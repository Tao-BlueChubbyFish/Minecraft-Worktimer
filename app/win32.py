"""Win32 相关：鼠标穿透、置顶、开机自启、Alt+Tab 隐藏。

用 SetWindowLong 直接改扩展样式，而不是 Qt 的 setWindowFlag：
后者会重建原生窗口，导致置顶丢失、闪烁、坐标抖动。BongoCat Mover 这类
悬浮窗也是这么做的。
"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from . import util

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008

HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

_user32 = None
if sys.platform == "win32":
    try:
        _user32 = ctypes.windll.user32
    except Exception:
        _user32 = None


def _style_funcs():
    if _user32 is None:
        return None, None
    try:
        getter = _user32.GetWindowLongPtrW
        setter = _user32.SetWindowLongPtrW
        getter.restype = ctypes.c_ssize_t
        getter.argtypes = (ctypes.c_void_p, ctypes.c_int)
        setter.restype = ctypes.c_ssize_t
        setter.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t)
    except AttributeError:
        getter = _user32.GetWindowLongW
        setter = _user32.SetWindowLongW
        getter.restype = ctypes.c_long
        getter.argtypes = (ctypes.c_void_p, ctypes.c_int)
        setter.restype = ctypes.c_long
        setter.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_long)
    return getter, setter


def _topmost(hwnd: int, enable: bool) -> None:
    try:
        _user32.SetWindowPos(ctypes.c_void_p(int(hwnd)), ctypes.c_void_p(-1 if enable else -2),
                             0, 0, 0, 0,
                             SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    except Exception:
        pass


def set_click_through(hwnd: int, enable: bool) -> bool:
    """开启/关闭鼠标穿透。只改扩展样式，不动置顶与位置。"""
    getter, setter = _style_funcs()
    if not getter or not hwnd:
        return False
    try:
        style = getter(ctypes.c_void_p(int(hwnd)), GWL_EXSTYLE)
        if enable:
            style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        setter(ctypes.c_void_p(int(hwnd)), GWL_EXSTYLE, style)
        if enable:
            # 保证置顶不因样式变更而失效
            _topmost(hwnd, True)
        return True
    except Exception:
        return False


def set_topmost(hwnd: int, enable: bool) -> None:
    if _user32 is None or not hwnd:
        return
    _topmost(hwnd, enable)


def hide_from_alt_tab(hwnd: int) -> None:
    """加 TOOLWINDOW 扩展样式，Alt+Tab / 任务栏里不出现这个小挂件。"""
    getter, setter = _style_funcs()
    if not getter or not hwnd:
        return
    try:
        style = getter(hwnd, GWL_EXSTYLE)
        setter(hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW)
    except Exception:
        pass


# ---------------------------------------------------------------- 开机自启
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "MCWorkTimer"


def _launch_command() -> str:
    if util.is_frozen():
        return f'"{Path(sys.executable).resolve()}"'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    main_py = util.app_dir() / "main.py"
    return f'"{exe.resolve()}" "{main_py.resolve()}"'


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            value, _ = winreg.QueryValueEx(k, APP_NAME)
            return bool(value)
    except OSError:
        return False
    except Exception:
        return False


def autostart_command() -> str:
    """读注册表里记着的启动命令；没开自启就返回空串。"""
    if sys.platform != "win32":
        return ""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            value, _ = winreg.QueryValueEx(k, APP_NAME)
            return str(value)
    except Exception:
        return ""


def autostart_matches_current() -> bool:
    """注册表里的命令是不是「当前正在跑的这个版本」。换过版本（源码/exe）就会是 False。"""
    stored = autostart_command()
    if not stored:
        return False
    norm = lambda s: s.replace("/", "\\").strip().lower()
    return norm(stored) == norm(_launch_command())


def set_autostart(enable: bool) -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enable:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False
