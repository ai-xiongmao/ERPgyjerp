"""环境补齐：起浏览器、开业务页、打开报告。

这一层是「有副作用的动作」，和 health.py 的「只读探测」严格分开：
探测每 5s 跑一次，绝不能顺手打开一个浏览器；动作只在用户点按钮时执行。
"""

from __future__ import annotations

import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from config import BASE_URL, CDP_ENDPOINT

from .health import LOCAL_OPENER, check_browser, check_page
from .paths import REPORTS_DIR
from .util import short_exc


def open_path(target):
    """用系统默认程序打开文件（报告），但只允许 reports/ 下的产物。"""
    path = Path(target).resolve()
    reports = REPORTS_DIR.resolve()
    if reports not in path.parents and path != reports:
        raise ValueError("只允许打开 reports 目录下的报告")
    if not path.exists():
        raise ValueError(f"文件不存在：{path.name}")
    if os.name == "nt":
        os.startfile(str(path))  # noqa: S606 - 本地固定路径
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _desktop_lnk():
    for name in ("MyTest.exe.lnk", "MyTest.lnk"):
        candidate = Path(os.path.expanduser("~")) / "Desktop" / name
        if candidate.exists():
            return candidate
    return None


def launch_browser():
    lnk = _desktop_lnk()
    if lnk is None:
        raise ValueError("桌面上没找到 MyTest.exe.lnk，请手动打开浏览器")
    if os.name == "nt":
        os.startfile(str(lnk))  # noqa: S606 - 本地固定路径
    else:
        subprocess.Popen(["xdg-open", str(lnk)])
    return lnk.name


def open_business_page():
    """让 MyTest 开一个管伊佳标签页（CDP 的 /json/new 需要用 PUT）。"""
    target = f"{CDP_ENDPOINT}/json/new?{urllib.parse.quote(BASE_URL, safe=':/?=&')}"
    request = urllib.request.Request(target, method="PUT")
    with LOCAL_OPENER.open(request, timeout=6.0) as response:
        response.read(1024)
    return BASE_URL


def prepare_env():
    """按当前探测结果补齐环境：缺浏览器就拉浏览器，缺业务页就开业务页。

    只负责「触发」，不等 CDP 就绪——浏览器启动要几秒，等在这里会把页面卡住，
    前端拿到结果后会自己盯着环境卡片变色。
    """
    actions = []

    browser = check_browser()
    if browser["status"] != "ok":
        try:
            actions.append({"key": "browser", "ok": True, "msg": f"已启动 {launch_browser()}，等待 CDP 就绪"})
        except Exception as exc:  # noqa: BLE001
            actions.append({"key": "browser", "ok": False, "msg": f"启动浏览器失败：{short_exc(exc)}"})
        return actions  # 浏览器没起来，开业务页也没意义

    page = check_page()
    if page["status"] != "ok":
        try:
            actions.append({"key": "page", "ok": True, "msg": f"已在浏览器打开 {open_business_page()}"})
        except Exception as exc:  # noqa: BLE001
            actions.append({"key": "page", "ok": False, "msg": f"打开业务页失败：{short_exc(exc)}"})
    else:
        actions.append({"key": "page", "ok": True, "msg": "业务页面已就绪"})

    return actions
