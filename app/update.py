"""检查更新：读仓库里的 latest.json，比版本号。

网络不可靠——GitHub raw 在部分网络下会被重置，所以规矩是：

* 自动检查（后台悄悄跑）失败一律**静默**：不弹窗、不报错、不写日志。
* 只有用户自己点「检查更新」才告诉他失败。
* raw 不通时自动改走 jsDelivr 镜像，两个都不行才算失败。

用 Qt 的网络模块而不是 urllib：Qt 默认按系统代理配置走（Steam++、系统 VPN 这类
只给浏览器生效的加速工具，靠的就是这个系统代理，urllib 是不认的）。
"""
from __future__ import annotations

import json

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import (QNetworkAccessManager, QNetworkProxyFactory,
                               QNetworkReply, QNetworkRequest)

from . import __version__

# 仓库里的版本文件。改仓库名/分支时只改这两行。
RAW = "https://raw.githubusercontent.com/Tao-BlueChubbyFish/Minecraft-Worktimer/main/latest.json"
CDN = "https://cdn.jsdelivr.net/gh/Tao-BlueChubbyFish/Minecraft-Worktimer@main/latest.json"

TIMEOUT_MS = 8000

# 国内下载兜底。读不到 latest.json 时也能用（所以必须写死在代码里）。
# 发新版换了蓝奏云链接，除了改这里，也可以在 latest.json 里加 url_cn / cn_password 覆盖。
FALLBACK_CN_URL = "https://wwbpm.lanzoue.com/i7VMs4gztl5g"
FALLBACK_CN_PWD = "1wne"


def parse_version(text: str) -> tuple[int, ...]:
    """"1.2.0" → (1, 2, 0)；认不出来的返回空元组（调用方当失败处理）。"""
    parts = []
    for chunk in str(text or "").strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def is_newer(remote: str, local: str = __version__) -> bool:
    r, l = parse_version(remote), parse_version(local)
    return bool(r) and bool(l) and r > l


def short_label(version: str) -> str:
    """"1.4.0" → "v1.4"：界面上只说大版本，跟 exe 名、菜单里的写法一致。"""
    parts = parse_version(version)
    if len(parts) >= 2:
        return "v" + ".".join(str(x) for x in parts[:2])
    return "v" + str(version or "").strip().lstrip("vV")


class UpdateChecker(QObject):
    """拉一次 latest.json。found / uptodate / failed 三个信号里只会来一个。"""

    found = Signal(str, str, str, str)   # (远端版本, 下载页, 国内下载页, 提取码)
    uptodate = Signal(str)          # (当前版本)
    failed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = None
        self._tried = 0
        self._done = False
        # 一键下载用：latest.json 里的 asset（exe 直链）与字节数，供调用方读
        self.asset_url = ""
        self.asset_size = 0

    def start(self) -> None:
        if self._nam is None:
            # 显式打开系统代理：加速工具改的是系统代理，Qt 默认用它更稳
            QNetworkProxyFactory.setUseSystemConfiguration(True)
            self._nam = QNetworkAccessManager(self)
        self._tried = 0
        self._done = False
        self._fetch()

    # ------------------------------------------------------------------
    def _fetch(self) -> None:
        url = RAW if self._tried == 0 else CDN
        req = QNetworkRequest(QUrl(url))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        req.setTransferTimeout(TIMEOUT_MS)
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply: self._on_reply(r))

    def _on_reply(self, reply: QNetworkReply) -> None:
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        body = bytes(reply.readAll()).decode("utf-8", "replace") if ok else ""
        reply.deleteLater()

        if not ok or not body.strip():
            if self._tried == 0:
                self._tried = 1
                self._fetch()           # raw 不通，换镜像再试一次
                return
            self._finish_failed()
            return

        try:
            data = json.loads(body)
            remote = str(data.get("version") or "").strip()
            url = str(data.get("url") or "").strip() or \
                "https://github.com/Tao-BlueChubbyFish/Minecraft-Worktimer/releases/latest"
            cn_url = str(data.get("url_cn") or "").strip() or FALLBACK_CN_URL
            cn_pwd = str(data.get("cn_password") or "").strip() or FALLBACK_CN_PWD
            self.asset_url = str(data.get("asset") or "").strip()
            self.asset_size = int(data.get("size") or 0)
        except Exception:
            if self._tried == 0:
                self._tried = 1
                self._fetch()
                return
            self._finish_failed()
            return

        if not remote:
            self._finish_failed()
            return

        self._done = True
        if is_newer(remote):
            self.found.emit(remote, url, cn_url, cn_pwd)
        else:
            self.uptodate.emit(__version__)

    def _finish_failed(self) -> None:
        if not self._done:
            self._done = True
            self.failed.emit()


class UpdateFetcher(QObject):
    """把新版 exe 下到旧 exe 旁边。

    这里**不做自我替换**。exe 正在跑，Windows 不允许删它或覆盖它；想一步到位只能
    写个临时批处理，等进程退出后再动手——那套东西碰上只读目录、杀软拦截，
    给用户的是一串看不懂的错误。所以只做最稳的那半截：

    文件送到旧版同一个文件夹里，用户关掉本程序、双击新的就行。
    config.json 和 data.json 全程不碰，台账一个字节都不会丢。
    """

    progress = Signal(int, int)      # (已下载, 总量)；总量未知时给 0
    done = Signal(str)               # 保存路径
    failed = Signal(str)             # 一句人话

    def __init__(self, parent, url: str, size: int, version: str):
        super().__init__(parent)
        self._url = str(url or "")
        self._size = int(size or 0)
        self._version = str(version or "").strip().lstrip("vV")
        self._nam = None
        self._reply = None
        self._fh = None
        self._path = ""
        self._got = 0
        self._dead = False

    # ------------------------------------------------------------------
    def start(self) -> None:
        self._path = self._target()
        try:
            self._fh = open(self._path, "wb")
        except OSError:
            self._dead = True
            self.failed.emit("这个文件夹写不进去，请手动下载")
            return
        if self._nam is None:
            QNetworkProxyFactory.setUseSystemConfiguration(True)
            self._nam = QNetworkAccessManager(self)
        req = QNetworkRequest(QUrl(self._url))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        req.setTransferTimeout(180000)        # 35MB 慢网也要给足三分钟
        self._reply = self._nam.get(req)
        self._reply.readyRead.connect(self._on_data)
        self._reply.downloadProgress.connect(self._on_progress)
        self._reply.finished.connect(self._on_finished)

    def cancel(self) -> None:
        if self._reply is not None and not self._dead:
            self._dead = True
            self._reply.abort()

    # ------------------------------------------------------------------
    def _target(self) -> str:
        """存到 exe 旁边，名字带版本号；同名已存在就加序号，绝不覆盖任何东西。"""
        import sys
        from pathlib import Path

        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
        tag = f"MCWorkTimer_v{self._version}.exe" if self._version else "MCWorkTimer_new.exe"
        path = base / tag
        n = 2
        while path.exists():
            path = base / (tag[:-4] + f"_{n}.exe")
            n += 1
        return str(path)

    def _on_data(self) -> None:
        if self._fh is None or self._reply is None:
            return
        chunk = bytes(self._reply.readAll())
        if not chunk:
            return
        try:
            self._fh.write(chunk)
        except OSError:
            self._dead = True
            self.failed.emit("写文件失败，看看磁盘还剩多少")
            self._reply.abort()
            return
        self._got += len(chunk)

    def _on_progress(self, got: int, total: int) -> None:
        if not self._dead:
            self.progress.emit(int(got), int(total or self._size))

    def _on_finished(self) -> None:
        reply, self._reply = self._reply, None
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None
        if self._dead:
            self._drop()
            return
        ok = reply is not None and reply.error() == QNetworkReply.NetworkError.NoError
        if reply is not None:
            reply.deleteLater()
        if not ok:
            self._drop()
            self.failed.emit("下载中断了，网络不太稳")
            return
        want = self._size
        if want and self._got != want:
            self._drop()
            self.failed.emit("文件不完整，没下全")
            return
        self.done.emit(self._path)

    def _drop(self) -> None:
        """失败时把半截文件删掉，别留个坏 exe 在桌面上骗人。"""
        try:
            if self._path:
                import os
                os.remove(self._path)
        except OSError:
            pass
