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
FALLBACK_CN_URL = "https://wwbpm.lanzoue.com/iEezd4gyr26f"
FALLBACK_CN_PWD = "61kp"


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
