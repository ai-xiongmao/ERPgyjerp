"""环境探测：六项检查 + 后台轮询。

设计要点：探测在后台线程按 5s 一轮跑并存快照，页面读快照。所以任何一项探测
卡住（比如目标站点连不上、要等 5s 超时）都不会把界面卡住，也不会拖慢另一项。
单项抛异常只降级成一张「探测异常」卡片，不中断整轮。
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from config import BASE_URL, CDP_ENDPOINT

from . import runtime
from .cases_feed import load_cases
from .paths import PYTHON
from .util import cache_drop, cached, short_exc


def probe_json(url, timeout=2.5):
    """GET 一个 JSON 接口，返回 (数据, 耗时ms)；失败抛异常。"""
    started = time.time()
    request = urllib.request.Request(url, headers={"User-Agent": "ERPDash/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8", "replace")), (time.time() - started) * 1000


LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def probe_http(url, timeout=6.0):
    started = time.time()
    request = urllib.request.Request(url, headers={"User-Agent": "ERPDash/1.0"})
    host = (urlparse(url).hostname or "").lower()
    # 本机地址不走系统代理：开了 Clash 之类的全局代理时，回环请求会被劫持成 502
    opener = LOCAL_OPENER if host in ("127.0.0.1", "localhost", "::1") else urllib.request.build_opener()
    with opener.open(request, timeout=timeout) as response:
        response.read(1024)
        return response.status, (time.time() - started) * 1000


def _uptime():
    seconds = int(time.time() - runtime.STARTED_AT)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m"


def check_panel():
    return {
        "key": "panel", "name": "控制台服务", "status": "ok",
        "value": f"127.0.0.1:{runtime.PORT}",
        "detail": f"PID {os.getpid()} · 已运行 {_uptime()} · Python "
                  f"{sys.version_info.major}.{sys.version_info.minor}",
    }


def check_browser():
    try:
        info, cost = probe_json(f"{CDP_ENDPOINT}/json/version", timeout=2.0)
    except Exception as exc:  # noqa: BLE001 - 连不上就是没启动
        return {
            "key": "browser", "name": "MyTest 浏览器", "status": "fail",
            "value": "未启动",
            "detail": f"CDP {CDP_ENDPOINT} 无响应（{short_exc(exc)}）",
            "hint": "双击桌面 MyTest.exe 启动",
            "action": "open-browser",
            "actionText": "启动浏览器",
        }
    return {
        "key": "browser", "name": "MyTest 浏览器", "status": "ok",
        "value": "已连接",
        "detail": f"{info.get('Browser', 'Chromium')} · CDP 9231 · {cost:.0f}ms",
    }


def check_page():
    """业务页面 / 登录态：看浏览器里有没有打开管伊佳的标签页。"""
    try:
        targets, _ = probe_json(f"{CDP_ENDPOINT}/json/list", timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        return {
            "key": "page", "name": "业务页面", "status": "unknown",
            "value": "无法判断", "detail": f"浏览器未连接（{short_exc(exc)}）",
        }

    pages = [t for t in targets if t.get("type") == "page" and "gyjerp" in (t.get("url") or "")]
    if not pages:
        return {
            "key": "page", "name": "业务页面", "status": "fail",
            "value": "未打开",
            "detail": f"浏览器里没有 {BASE_URL} 页面",
            "hint": "在 MyTest 中打开并登录管伊佳 ERP",
        }

    page = pages[0]
    url = page.get("url") or ""
    title = (page.get("title") or "管伊佳ERP").strip()
    if runtime.LOGIN_PATH_HINT in url.lower():
        return {
            "key": "page", "name": "业务页面", "status": "warn",
            "value": "停在登录页",
            "detail": f"{title} · 需要登录后才能跑 UI 用例",
            "hint": "在浏览器里完成登录",
        }
    return {
        "key": "page", "name": "业务页面", "status": "ok",
        "value": "已打开",
        "detail": title,
    }


SITE_LAST_OK = {"ts": 0, "cost": 0.0, "status": 200}


def check_site():
    """目标站点可达性。

    失败再试一次；两次都失败但 2 分钟内成功过，就报「响应波动」而不是「不可达」——
    这台机器到 cloud.gyjerp.com 偶发慢连接，一次抖动不该把整块面板刷成红色。
    """
    error = None
    for attempt in range(2):
        try:
            status, cost = cached("site", 15, lambda: probe_http(BASE_URL, timeout=5.0))
        except Exception as exc:  # noqa: BLE001
            cache_drop("site")
            error = exc
            if attempt == 0:
                time.sleep(0.25)
            continue
        SITE_LAST_OK.update(ts=time.time(), cost=cost, status=status)
        return {
            "key": "site", "name": "目标系统", "status": "ok" if status < 400 else "warn",
            "value": f"HTTP {status}", "detail": f"{BASE_URL} · {cost:.0f}ms",
        }

    last = SITE_LAST_OK
    if last["ts"] and time.time() - last["ts"] < 120:
        ago = int(time.time() - last["ts"])
        return {
            "key": "site", "name": "目标系统", "status": "warn",
            "value": "响应波动",
            "detail": f"{BASE_URL} · 上次成功 {ago}s 前（{last['cost']:.0f}ms），"
                      f"本次 {short_exc(error, 60)}",
        }
    return {
        "key": "site", "name": "目标系统", "status": "fail",
        "value": "不可达", "detail": f"{BASE_URL}（{short_exc(error)}）",
    }


def check_cases():
    try:
        data = load_cases()
    except Exception as exc:  # noqa: BLE001 - 用例导出失败要摆到明面上
        return {
            "key": "cases", "name": "用例库", "status": "fail",
            "value": "读取失败", "detail": short_exc(exc, 160),
        }
    rows = data.get("cases") or []
    ui_ok = sum(1 for c in rows if c["ui"] and not c["uiBlocked"])
    api_ok = sum(1 for c in rows if c["api"] and not c["apiBlocked"])
    return {
        "key": "cases", "name": "用例库", "status": "ok" if rows else "warn",
        "value": f"{len(rows)} 条",
        "detail": f"UI 可自动 {ui_ok} · 接口可自动 {api_ok}",
    }


def check_deps():
    try:
        import playwright  # noqa: F401  只验证可导入，不启动浏览器
    except Exception as exc:  # noqa: BLE001
        return {
            "key": "deps", "name": "执行依赖", "status": "fail",
            "value": "playwright 缺失", "detail": short_exc(exc, 160),
            "hint": "在 .venv 里执行 pip install -r requirements.txt",
        }
    version = getattr(playwright, "__version__", "")
    return {
        "key": "deps", "name": "执行依赖", "status": "ok",
        "value": "playwright 就绪",
        "detail": (f"v{version} · " if version else "") + f"解释器 {Path(PYTHON).name}",
    }


CHECKS = [check_panel, check_browser, check_page, check_site, check_cases, check_deps]

_HEALTH = {"checks": [], "ts": 0}
_HEALTH_LOCK = threading.Lock()


def refresh_health():
    checks = []
    for probe in CHECKS:
        try:
            checks.append(probe())
        except Exception as exc:  # noqa: BLE001 - 单项探测崩了不能拖垮整轮
            checks.append({"key": probe.__name__, "name": "探测异常", "status": "unknown",
                           "value": "—", "detail": short_exc(exc)})
    with _HEALTH_LOCK:
        _HEALTH["checks"] = checks
        _HEALTH["ts"] = time.time()
    return checks


def health_loop():
    while True:
        refresh_health()
        time.sleep(runtime.HEALTH_TTL)


def health_snapshot():
    with _HEALTH_LOCK:
        checks = list(_HEALTH["checks"])
        ts = _HEALTH["ts"]
    if not checks:
        checks = refresh_health()
        ts = time.time()
    return {"checks": checks, "ts": ts,
            "overall": "fail" if any(c["status"] == "fail" for c in checks) else
                       ("warn" if any(c["status"] in ("warn", "unknown") for c in checks) else "ok")}
