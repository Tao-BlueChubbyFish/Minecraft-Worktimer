"""真实天气：地名 → 经纬度 → 当天天气与气温。

只做一件事：把「用户填的城市」换成本项目那六种天气之一，外加一个气温。
取不到就什么都不改，上层继续用 weather.py 那套按日期播种的随机天气——
天气是氛围，不是核心功能，不能因为它连不上网就把程序卡住。

用的是 Open-Meteo：免费、不用注册 key。代价是国内访问不算快，
所以整个流程必须是异步的，界面先出来，天气晚几秒换过去。
"""
from __future__ import annotations

import json

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtNetwork import (QNetworkAccessManager, QNetworkProxyFactory,
                               QNetworkReply, QNetworkRequest)

from . import weather

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO 天气代码 → 本项目的六档。
# 本项目只认「晴 / 阴 / 小雨 / 大雨 / 小雪 / 大雪」，所以要把几十个代码压成六档。
# 压的原则：看体感，不看术语——毛毛雨和阵雨对画面来说都是"在下雨"。
_CODE = {
    0: weather.CLEAR,
    1: weather.CLOUDY, 2: weather.CLOUDY, 3: weather.CLOUDY,
    45: weather.CLOUDY, 48: weather.CLOUDY,          # 雾：天色压着，当阴天
    51: weather.RAIN, 53: weather.RAIN, 55: weather.RAIN,
    56: weather.RAIN, 57: weather.RAIN,              # 冻雨也算雨
    61: weather.RAIN, 63: weather.RAIN, 65: weather.DOWNPOUR,
    66: weather.RAIN, 67: weather.DOWNPOUR,
    71: weather.SNOW, 73: weather.SNOW, 77: weather.SNOW,
    75: weather.BLIZZARD,
    80: weather.RAIN, 81: weather.RAIN, 82: weather.DOWNPOUR,
    85: weather.SNOW, 86: weather.BLIZZARD,
    95: weather.DOWNPOUR, 96: weather.DOWNPOUR, 99: weather.DOWNPOUR,
}


class WeatherFetcher(QObject):
    """查一次真实天气。用完就丢，不要复用同一个实例查两地。

    done(code, temp, place)  code 是 weather.py 里的那六种之一
    failed(reason)           reason 是给用户看的一句话，不是异常信息
    """

    done = Signal(str, float, str)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = None
        self._place = ""
        self._shown = ""

    def start(self, place: str) -> None:
        self._place = (place or "").strip()
        if not self._place:
            self.failed.emit("还没填地点")
            return
        if self._nam is None:
            # 用户机器上常有加速工具，它们改的是系统代理，Qt 跟着走更稳
            QNetworkProxyFactory.setUseSystemConfiguration(True)
            self._nam = QNetworkAccessManager(self)
        self._get(GEO_URL, {
            "name": self._place, "count": 1, "language": "zh", "format": "json",
        }, self._on_geo)

    # ------------------------------------------------------------------
    def _get(self, base: str, params: dict, handler) -> None:
        query = "&".join("%s=%s" % (k, QUrl.toPercentEncoding(str(v)).data().decode())
                         for k, v in params.items())
        req = QNetworkRequest(QUrl(base + "?" + query))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        req.setTransferTimeout(12000)
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply: handler(r))

    def _read(self, reply):
        """读走 body 并回收 reply；返回 (是否成功, 解析后的字典)。"""
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        body = bytes(reply.readAll()).decode("utf-8", "replace") if ok else ""
        reply.deleteLater()
        if not ok or not body.strip():
            return False, {}
        try:
            return True, json.loads(body)
        except Exception:
            return False, {}

    def _on_geo(self, reply) -> None:
        ok, data = self._read(reply)
        if not ok:
            self.failed.emit("连不上天气服务")
            return
        rows = data.get("results") or []
        if not rows:
            self.failed.emit("没找到「%s」这个地方" % self._place)
            return
        row = rows[0]
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except Exception:
            self.failed.emit("没找到「%s」这个地方" % self._place)
            return
        name = str(row.get("name") or self._place)
        admin = str(row.get("admin1") or "")
        self._shown = name if (not admin or admin == name) else "%s %s" % (admin, name)

        self._get(FORECAST_URL, {
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,weather_code",
            "timezone": "auto",
        }, self._on_forecast)

    def _on_forecast(self, reply) -> None:
        ok, data = self._read(reply)
        if not ok:
            self.failed.emit("连不上天气服务")
            return
        cur = data.get("current") or {}
        try:
            code = int(cur.get("weather_code"))
            temp = float(cur.get("temperature_2m"))
        except Exception:
            self.failed.emit("天气数据格式不对")
            return
        self.done.emit(_CODE.get(code, weather.CLOUDY), temp, self._shown)
