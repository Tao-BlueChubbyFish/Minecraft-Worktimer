"""MC 工时牌 —— 应用入口。"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths, Qt, qInstallMessageHandler
from PySide6.QtGui import QFontDatabase, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from app import __version__, engine, theme, util, win32
from app.config import Config
from app.store import Store
from app.tray import Tray
from app.widget import TimerWidget


def _log_file(name: str):
    from pathlib import Path
    return Path(util.app_dir()) / name


def _silence_qt_noise(mode, context, message: str) -> None:
    """pythonw 没有 stderr，只把真正的错误写进 qt.log，避免无控制台时静默丢失。"""
    low = message.lower()
    if "font" in low or "propagatesizehints" in low:
        return
    if "error" not in low and "fatal" not in low and "traceback" not in low:
        return
    try:
        with open(_log_file("qt.log"), "a", encoding="utf-8") as f:
            f.write(message.rstrip() + "\n")
    except Exception:
        pass


def _install_crash_hook() -> None:
    import traceback

    def hook(exc_type, exc, tb):
        try:
            with open(_log_file("crash.log"), "a", encoding="utf-8") as f:
                f.write("=" * 60 + "\n")
                traceback.print_exception(exc_type, exc, tb, file=f)
        except Exception:
            pass

    sys.excepthook = hook


def _load_bundled_fonts() -> None:
    folder = util.fonts_dir()
    if not folder.exists():
        return
    for f in list(folder.glob("*.ttf")) + list(folder.glob("*.otf")) + list(folder.glob("*.ttc")):
        QFontDatabase.addApplicationFont(str(f))


def _acquire_single_instance():
    tmp = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)
    lock = QLockFile(str(Path(tmp) / "mc-worktimer.lock"))
    lock.setStaleLockTime(0)
    if lock.tryLock(120):
        return lock
    return None


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qInstallMessageHandler(_silence_qt_noise)
    _install_crash_hook()

    app = QApplication(sys.argv)
    app.setApplicationName("MCWorkTimer")
    app.setApplicationVersion(__version__)
    app.setApplicationDisplayName("MC 工时牌")
    app.setQuitOnLastWindowClosed(False)

    lock = _acquire_single_instance()
    if lock is None:
        QMessageBox.information(None, "MC 工时牌", "程序已经在运行了，看右下角托盘。")
        return 0

    _load_bundled_fonts()

    cfg = Config()
    if not cfg.path.exists():
        try:
            cfg.save()
        except Exception:
            pass
    store = Store()
    rule = engine.build_rule(cfg)

    # 让注册表与配置保持一致（包括「换过启动方式后命令要跟着改」）
    try:
        if cfg.get("autostart", False):
            if not win32.autostart_matches_current():
                win32.set_autostart(True)
        elif win32.autostart_enabled():
            win32.set_autostart(False)
    except Exception:
        pass

    icon_file = util.resource_dir() / "assets" / "icon.ico"
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    widget = TimerWidget(cfg, store, rule)
    pal = theme.resolve_palette(cfg)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = Tray(widget, pal)
        widget.tray = tray
        tray.show()
        tray.refresh(widget.snap)

    widget.show()
    widget.request_quit.connect(app.quit)

    code = app.exec()
    store.save()
    win32.set_click_through(0, False)
    return code


if __name__ == "__main__":
    sys.exit(main())
