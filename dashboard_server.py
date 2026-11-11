"""自动化控制台：本地 Web 面板，监控执行环境 + 勾选用例一键执行。

用法：
    .venv\\Scripts\\python.exe dashboard_server.py              # 默认 http://127.0.0.1:8760
    .venv\\Scripts\\python.exe dashboard_server.py --port 8800
    .venv\\Scripts\\python.exe dashboard_server.py --no-browser  # 不自动开浏览器

服务起来后用浏览器访问 http://127.0.0.1:8760/ 即可；页面是服务端实时读取的，
改 HTML 不用重启服务。注意不要直接双击 dashboard/index.html——file:// 下取不到 /api。

设计要点：
1. 不引入任何新依赖，只用标准库——面板本身也要「零安装」才能开箱可用；
2. 监控与执行彻底分离：环境探测在后台线程按 5s 一轮刷新并缓存，
   页面读缓存，不会因为探测卡住界面；执行则交给子进程，
   子进程就是平时手敲的 `run_cases.py run ...`，行为与命令行完全一致，便于对照排查；
3. 只监听 127.0.0.1，不把「执行用例」的能力暴露到局域网；
4. 用例清单由子进程导出并缓存 5 分钟，避免面板进程直接 import 业务代码
   （那样用例脚本一旦写错，连面板都起不来）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import BASE_URL, CDP_ENDPOINT  # noqa: E402  只读配置，不触发浏览器

PAGE_FILE = ROOT / "dashboard" / "index.html"
CACHE_DIR = ROOT / "dashboard" / ".cache"
CASES_CACHE = CACHE_DIR / "cases.json"
SERVER_LOG = CACHE_DIR / "server.log"
CASE_TTL = 300          # 用例清单缓存（秒）
HEALTH_TTL = 5          # 环境探测周期（秒）
MAX_LOG_LINES = 6000    # 单个任务保留的日志上限，防止长跑把内存吃掉

LOGIN_PATH_HINT = "login"


# ==================== 环境相关 ====================

def _python_exe():
    """优先用项目 venv 的解释器跑子进程，避免系统 Python 缺 playwright。"""
    for candidate in (ROOT / ".venv" / "Scripts" / "python.exe",
                      ROOT / ".venv" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


PYTHON = _python_exe()


def _probe_json(url, timeout=2.5):
    """GET 一个 JSON 接口，返回 (数据, 耗时ms)；失败抛异常。"""
    started = time.time()
    request = urllib.request.Request(url, headers={"User-Agent": "ERPDash/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8", "replace")), (time.time() - started) * 1000


_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _probe_http(url, timeout=6.0):
    started = time.time()
    request = urllib.request.Request(url, headers={"User-Agent": "ERPDash/1.0"})
    host = (urlparse(url).hostname or "").lower()
    # 本机地址不走系统代理：开了 Clash 之类的全局代理时，回环请求会被劫持成 502
    opener = _LOCAL_OPENER if host in ("127.0.0.1", "localhost", "::1") else urllib.request.build_opener()
    with opener.open(request, timeout=timeout) as response:
        response.read(1024)
        return response.status, (time.time() - started) * 1000


# 子进程导出用例清单：与 registry 同源，保证面板看到的和实际能跑的一致
_DUMP_SCRIPT = r"""
import json, sys
sys.path.insert(0, r"%s")
from framework import registry
from run_cases import MODULE_LABELS, MODULE_PATHS
import cases  # noqa: F401  导入即注册
rows = []
for case in registry.all_cases():
    rows.append({
        "cid": case.cid,
        "title": case.title,
        "tag": case.tag,
        "priority": case.priority,
        "module": registry.prefix_of(case.cid),
        "ui": case.func is not None,
        "uiBlocked": case.blocked or "",
        "api": case.api is not None,
        "apiBlocked": case.blocked_for("api") or "",
    })
payload = {
    "cases": rows,
    "modules": [{"prefix": key, "label": name,
                 "path": MODULE_PATHS.get(key, "")} for key, name in MODULE_LABELS.items()],
}
print("@@DATA@@" + json.dumps(payload, ensure_ascii=False))
"""

_CASES_LOCK = threading.Lock()
_CASES_MEM = {"ts": 0, "data": None, "failAt": 0, "failMsg": ""}


def load_cases(force=False):
    """取用例清单：内存 → 磁盘缓存 → 子进程现导。返回 dict。"""
    with _CASES_LOCK:
        now = time.time()
        if not force and _CASES_MEM["data"] and now - _CASES_MEM["ts"] < CASE_TTL:
            return _CASES_MEM["data"]
        # 导出失败后 30s 内不再重试：health 每 5s 探一轮，否则会连续起子进程
        if not force and _CASES_MEM["failAt"] and now - _CASES_MEM["failAt"] < 30:
            raise RuntimeError(_CASES_MEM["failMsg"])
        if not force and CASES_CACHE.exists() and now - CASES_CACHE.stat().st_mtime < CASE_TTL:
            try:
                data = json.loads(CASES_CACHE.read_text("utf-8"))
                _CASES_MEM.update(ts=CASES_CACHE.stat().st_mtime, data=data)
                return data
            except Exception:  # noqa: BLE001 - 缓存坏了就重导
                pass

        try:
            completed = subprocess.run(
                [PYTHON, "-c", _DUMP_SCRIPT % str(ROOT)],
                cwd=str(ROOT), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=180,
            )
        except Exception as exc:  # noqa: BLE001
            _CASES_MEM.update(failAt=time.time(), failMsg=f"执行导出脚本失败：{_short(exc)}")
            raise

        data = None
        for line in completed.stdout.splitlines():
            if line.startswith("@@DATA@@"):
                data = json.loads(line[len("@@DATA@@"):])
                break
        if data is None:
            detail = (completed.stderr or completed.stdout or "无输出").strip().splitlines()
            message = "用例清单导出失败：" + (detail[-1] if detail else "未知原因")
            _CASES_MEM.update(failAt=time.time(), failMsg=message)
            raise RuntimeError(message)

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CASES_CACHE.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        _CASES_MEM.update(ts=time.time(), data=data, failAt=0, failMsg="")
        return data


_PROBE_CACHE = {}


def _cached(key, ttl, producer):
    """探测结果短缓存：目标站点/浏览器这类慢探测不必每 5s 打一次。"""
    now = time.time()
    hit = _PROBE_CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = producer()
    _PROBE_CACHE[key] = (now, value)
    return value


def check_panel():
    return {
        "key": "panel", "name": "控制台服务", "status": "ok",
        "value": f"127.0.0.1:{PORT}",
        "detail": f"PID {os.getpid()} · 已运行 {_uptime()} · Python "
                  f"{sys.version_info.major}.{sys.version_info.minor}",
    }


def _uptime():
    seconds = int(time.time() - STARTED_AT)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m"


def check_browser():
    try:
        info, cost = _probe_json(f"{CDP_ENDPOINT}/json/version", timeout=2.0)
    except Exception as exc:  # noqa: BLE001 - 连不上就是没启动
        return {
            "key": "browser", "name": "MyTest 浏览器", "status": "fail",
            "value": "未启动",
            "detail": f"CDP {CDP_ENDPOINT} 无响应（{_short(exc)}）",
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
        targets, _ = _probe_json(f"{CDP_ENDPOINT}/json/list", timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        return {
            "key": "page", "name": "业务页面", "status": "unknown",
            "value": "无法判断", "detail": f"浏览器未连接（{_short(exc)}）",
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
    if LOGIN_PATH_HINT in url.lower():
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
            status, cost = _cached("site", 15, lambda: _probe_http(BASE_URL, timeout=5.0))
        except Exception as exc:  # noqa: BLE001
            _PROBE_CACHE.pop("site", None)
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
                      f"本次 {_short(error, 60)}",
        }
    return {
        "key": "site", "name": "目标系统", "status": "fail",
        "value": "不可达", "detail": f"{BASE_URL}（{_short(error)}）",
    }


def check_cases():
    try:
        data = load_cases()
    except Exception as exc:  # noqa: BLE001 - 用例导出失败要摆到明面上
        return {
            "key": "cases", "name": "用例库", "status": "fail",
            "value": "读取失败", "detail": _short(exc, 160),
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
            "value": "playwright 缺失", "detail": _short(exc, 160),
            "hint": "在 .venv 里执行 pip install -r requirements.txt",
        }
    version = getattr(playwright, "__version__", "")
    return {
        "key": "deps", "name": "执行依赖", "status": "ok",
        "value": "playwright 就绪",
        "detail": (f"v{version} · " if version else "") + f"解释器 {Path(PYTHON).name}",
    }


def _short(exc, limit=90):
    text = f"{type(exc).__name__}: {exc}".replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")


_CHECKS = [check_panel, check_browser, check_page, check_site, check_cases, check_deps]
_HEALTH = {"checks": [], "ts": 0}
_HEALTH_LOCK = threading.Lock()


def refresh_health():
    checks = []
    for probe in _CHECKS:
        try:
            checks.append(probe())
        except Exception as exc:  # noqa: BLE001 - 单项探测崩了不能拖垮整轮
            checks.append({"key": probe.__name__, "name": "探测异常", "status": "unknown",
                           "value": "—", "detail": _short(exc)})
    with _HEALTH_LOCK:
        _HEALTH["checks"] = checks
        _HEALTH["ts"] = time.time()
    return checks


def health_loop():
    while True:
        refresh_health()
        time.sleep(HEALTH_TTL)


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


# ==================== 任务执行 ====================

_LINE_TOTAL = re.compile(r"^\s*\[\s*(\d+)/(\d+)\]\s+(\S+)")
_LINE_RESULT = re.compile(r"^\s+(OK|FAIL|SKIP|ERR|N/A)\s+(通过|失败|阻塞|异常|未覆盖)")
_MARK_COUNT = {"OK": "pass", "FAIL": "fail", "SKIP": "blocked", "ERR": "error", "N/A": "skipped"}


class RunSession:
    """一次执行 = 一个 run_cases.py 子进程 + 它的日志与统计。"""

    def __init__(self, ids, layer, options):
        self.id = time.strftime("%Y%m%d_%H%M%S")
        self.ids = ids
        self.layer = layer
        self.options = options
        self.started = time.time()
        self.finished = None
        self.state = "running"
        self.returncode = None
        self.stopped = False
        self.report = ""
        self.allure = ""
        self.logs = []
        self.lock = threading.Lock()
        self.progress = {"done": 0, "total": len(ids)}
        self.counts = {"pass": 0, "fail": 0, "blocked": 0, "error": 0, "skipped": 0}
        self.current = ""

        self.cmd = self._build_cmd()
        env = dict(os.environ)
        env.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            self.cmd, cwd=str(ROOT), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            env=env, creationflags=flags,
        )
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _build_cmd(self):
        cmd = [PYTHON, "run_cases.py", "run", "--only", ",".join(self.ids)]
        if self.layer == "api":
            cmd += ["--layer", "api"]
        if self.options.get("update_xlsx"):
            cmd += ["--update-xlsx"]
        if self.options.get("keep_data"):
            cmd += ["--keep-data"]
        if not self.options.get("allure", True):
            cmd += ["--allure", "off"]
        return cmd

    def _pump(self):
        try:
            for line in self.proc.stdout:
                self._ingest(line.rstrip("\r\n"))
        except Exception as exc:  # noqa: BLE001 - 读日志失败也要把任务收尾
            self._ingest(f"[面板] 读取输出失败：{_short(exc)}")
        finally:
            self.proc.wait()
            self.returncode = self.proc.returncode
            self.finished = time.time()
            if self.stopped:
                self.state = "stopped"
            elif self.returncode in (0, 1) and self.report:
                # run_cases 用 1 表示「有失败用例」，所以返回码不能当判据；
                # 正常跑完一定会写 Markdown 报告，拿它判断这一轮是否真的跑起来了
                self.state = "done"
            else:
                self.state = "failed"
            self._ingest(f"[面板] 进程结束，返回码 {self.returncode}，"
                         f"耗时 {self.elapsed:.0f}s")
            if self.state == "failed":
                self._ingest("[面板] 没有生成报告，说明执行在启动阶段就中断了 —— "
                             "先看上面的报错，多半是 MyTest 浏览器没开或没登录。")

    def _ingest(self, line):
        with self.lock:
            self.logs.append(line)
            if len(self.logs) > MAX_LOG_LINES:
                del self.logs[: len(self.logs) - MAX_LOG_LINES]

            match = _LINE_TOTAL.match(line)
            if match:
                self.progress["done"] = int(match.group(1)) - 1
                self.progress["total"] = int(match.group(2))
                self.current = match.group(3)
                return

            match = _LINE_RESULT.match(line)
            if match:
                key = _MARK_COUNT.get(match.group(1))
                if key:
                    self.counts[key] += 1
                self.progress["done"] = min(self.progress["done"] + 1, self.progress["total"])
                self.current = ""
                return

            if line.startswith("报告："):
                self.report = line.split("报告：", 1)[1].strip()
            elif line.startswith("Allure："):
                self.allure = line.split("Allure：", 1)[1].strip()

    @property
    def elapsed(self):
        return (self.finished or time.time()) - self.started

    def snapshot(self, offset=0):
        with self.lock:
            logs = self.logs[offset:]
            total = len(self.logs)
            data = {
                "id": self.id,
                "state": self.state,
                "layer": self.layer,
                "ids": self.ids,
                "started": self.started,
                "elapsed": round(self.elapsed, 1),
                "returncode": self.returncode,
                "report": self.report,
                "allure": self.allure,
                "progress": dict(self.progress),
                "counts": dict(self.counts),
                "current": self.current,
                "options": self.options,
                "command": " ".join(self.cmd[1:]),
                "log": logs,
                "nextOffset": total,
            }
        return data

    def stop(self):
        if self.state != "running":
            return False
        self.stopped = True
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                               capture_output=True, timeout=15)
            else:
                self.proc.terminate()
        except Exception:  # noqa: BLE001 - 兜底强杀
            try:
                self.proc.kill()
            except Exception:  # noqa: BLE001
                return False
        return True


class RunManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.current = None
        self.history = []

    def start(self, ids, layer, options):
        if not ids:
            raise ValueError("没有选中任何用例")
        with self.lock:
            if self.current and self.current.state == "running":
                raise ValueError("已有任务在运行，先等它结束或点「停止」")
            session = RunSession(ids, layer, options)
            self.current = session
            self.history.insert(0, session)
            del self.history[12:]
            return session.id

    def stop(self):
        with self.lock:
            session = self.current
        if not session:
            return False
        return session.stop()

    def snapshot(self, run_id=None, offset=0):
        with self.lock:
            session = self.current
        if session is None:
            return {"state": "idle", "log": [], "nextOffset": 0}
        if run_id and session.id != run_id:
            return {"state": "idle", "stale": True, "log": [], "nextOffset": 0}
        return session.snapshot(offset)

    def history_brief(self):
        with self.lock:
            sessions = list(self.history)
        return [{"id": s.id, "layer": s.layer, "state": s.state, "count": len(s.ids),
                 "started": s.started, "elapsed": round(s.elapsed, 1),
                 "counts": dict(s.counts), "report": s.report} for s in sessions]


RUNS = RunManager()


# ==================== HTTP 层 ====================

def _open_path(target):
    """用系统默认程序打开文件（报告），但只允许 reports/ 下的产物。"""
    path = Path(target).resolve()
    reports = (ROOT / "reports").resolve()
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


def _launch_browser():
    lnk = _desktop_lnk()
    if lnk is None:
        raise ValueError("桌面上没找到 MyTest.exe.lnk，请手动打开浏览器")
    if os.name == "nt":
        os.startfile(str(lnk))  # noqa: S606 - 本地固定路径
    else:
        subprocess.Popen(["xdg-open", str(lnk)])
    return lnk.name


def _open_business_page():
    """让 MyTest 开一个管伊佳标签页（CDP 的 /json/new 需要用 PUT）。"""
    target = f"{CDP_ENDPOINT}/json/new?{urllib.parse.quote(BASE_URL, safe=':/?=&')}"
    request = urllib.request.Request(target, method="PUT")
    with _LOCAL_OPENER.open(request, timeout=6.0) as response:
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
            actions.append({"key": "browser", "ok": True, "msg": f"已启动 {_launch_browser()}，等待 CDP 就绪"})
        except Exception as exc:  # noqa: BLE001
            actions.append({"key": "browser", "ok": False, "msg": f"启动浏览器失败：{_short(exc)}"})
        return actions  # 浏览器没起来，开业务页也没意义

    page = check_page()
    if page["status"] != "ok":
        try:
            actions.append({"key": "page", "ok": True, "msg": f"已在浏览器打开 {_open_business_page()}"})
        except Exception as exc:  # noqa: BLE001
            actions.append({"key": "page", "ok": False, "msg": f"打开业务页失败：{_short(exc)}"})
    else:
        actions.append({"key": "page", "ok": True, "msg": "业务页面已就绪"})

    return actions


class Handler(BaseHTTPRequestHandler):
    server_version = "ERPDash/1.0"
    protocol_version = "HTTP/1.1"

    # --- 基础设施 ---
    def log_message(self, fmt, *args):  # 面板请求太多，不刷控制台
        pass

    def _send(self, body, content_type, status=200):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=200):
        self._send(json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8", status)

    def _error(self, message, status=400):
        self._json({"ok": False, "error": message}, status)

    def _body_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"请求体不是合法 JSON：{exc}") from exc

    def _same_origin(self):
        """只接受本机页面发来的写操作，挡住别的站点偷偷调接口。"""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return any(host in origin for host in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"))

    # --- 路由 ---
    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path

        try:
            if path in ("/", "/index.html"):
                if not PAGE_FILE.exists():
                    return self._send("<h1>缺少 dashboard/index.html</h1>", "text/html; charset=utf-8", 500)
                return self._send(PAGE_FILE.read_text("utf-8"), "text/html; charset=utf-8")

            if path == "/api/health":
                payload = health_snapshot()
                payload["run"] = RUNS.snapshot(offset=10 ** 9)
                payload["run"]["log"] = []
                return self._json(payload)

            if path == "/api/cases":
                data = load_cases(force=query.get("refresh", ["0"])[0] == "1")
                return self._json({"ok": True, **data})

            if path == "/api/run":
                offset = int(query.get("offset", ["0"])[0] or 0)
                run_id = query.get("id", [None])[0]
                return self._json(RUNS.snapshot(run_id=run_id, offset=offset))

            if path == "/api/history":
                return self._json({"runs": RUNS.history_brief()})

            if path == "/api/report":
                name = query.get("name", [""])[0]
                target = (ROOT / "reports" / name).resolve()
                if target.parent != (ROOT / "reports").resolve() or not target.exists():
                    return self._error("报告不存在", 404)
                return self._send(target.read_text("utf-8", "replace"), "text/plain; charset=utf-8")

            if path == "/favicon.ico":
                return self._send(b"", "image/x-icon", 200)

            return self._error("未知接口", 404)
        except Exception as exc:  # noqa: BLE001
            return self._error(_short(exc, 300), 500)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._same_origin():
            return self._error("拒绝跨站请求", 403)
        try:
            if path == "/api/run":
                body = self._body_json()
                ids = [str(i).strip().upper() for i in (body.get("ids") or []) if str(i).strip()]
                layer = "api" if body.get("layer") == "api" else "ui"
                options = {
                    "update_xlsx": bool(body.get("update_xlsx")),
                    "keep_data": bool(body.get("keep_data")),
                    "allure": bool(body.get("allure", True)),
                }
                run_id = RUNS.start(ids, layer, options)
                return self._json({"ok": True, "id": run_id})

            if path == "/api/stop":
                stopped = RUNS.stop()
                return self._json({"ok": stopped, "message": "已请求停止" if stopped else "当前没有运行中的任务"})

            if path == "/api/refresh":
                load_cases(force=True)
                refresh_health()
                return self._json({"ok": True})

            if path == "/api/open":
                body = self._body_json()
                _open_path(body.get("path") or "")
                return self._json({"ok": True})

            if path == "/api/open-browser":
                return self._json({"ok": True, "launched": _launch_browser()})

            if path == "/api/prepare":
                actions = prepare_env()
                refresh_health()
                return self._json({"ok": True, "actions": actions})

            return self._error("未知接口", 404)
        except ValueError as exc:
            return self._error(str(exc), 400)
        except Exception as exc:  # noqa: BLE001
            return self._error(_short(exc, 300), 500)


STARTED_AT = time.time()
PORT = int(os.environ.get("ERP_DASH_PORT", "8760"))
HOST = "127.0.0.1"


class _AppServer(ThreadingHTTPServer):
    """控制台 HTTP 服务。

    Windows 的 SO_REUSEADDR 语义与 Linux 不同：它允许两个进程绑同一端口，
    导致重复双击启动时第二个实例静默抢占，行为很难排查。这里改成独占绑定。
    """

    daemon_threads = True
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt":
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                pass
        super().server_bind()


class _LoopbackV6Server(_AppServer):
    """额外监听 IPv6 回环。

    Windows 上 localhost 常优先解析到 ::1，只绑 127.0.0.1 时浏览器用
    http://localhost:8760 会直接 ERR_CONNECTION_REFUSED——看起来就像页面失效。
    """

    address_family = socket.AF_INET6

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        except OSError:
            pass
        super().server_bind()


def _ensure_std_streams():
    """无控制台启动（pythonw）时 sys.stdout/stderr 是 None，print 会直接抛异常。

    这里兜住并把输出落到日志文件，否则服务闪退且没有任何痕迹可查。
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        stream = open(SERVER_LOG, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - 进程级常驻
    except Exception:  # noqa: BLE001
        stream = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def main(argv=None):
    global PORT
    _ensure_std_streams()
    parser = argparse.ArgumentParser(description="管伊佳ERP 自动化控制台")
    parser.add_argument("--port", type=int, default=PORT, help=f"监听端口（默认 {PORT}）")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    PORT = args.port

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        except Exception:  # noqa: BLE001 - pythonw 下是文件对象，失败无妨
            pass

    url = f"http://{HOST}:{PORT}/"

    try:
        server = _AppServer((HOST, PORT), Handler)
    except OSError as exc:
        # 端口被占：很可能已经有一个控制台在跑了，别再报一堆错让人以为坏了
        alive = False
        try:
            status, _ = _probe_http(url + "api/health", timeout=2.0)
            alive = status == 200
        except Exception:  # noqa: BLE001
            alive = False
        if alive:
            print(f"[提示] {PORT} 端口上已经有一个控制台在运行：{url}")
            print("       不重复启动，直接打开已有实例。")
            if not args.no_browser:
                webbrowser.open(url)
            return 0
        print(f"[错误] 端口 {PORT} 启动失败：{exc}")
        print(f"       端口被其它程序占用，换一个：--port 8800")
        return 1

    # 先探一轮，别让页面首屏空着；用例清单也顺手预热
    try:
        load_cases()
    except Exception as exc:  # noqa: BLE001 - 面板要能起来，把错误显示在页面上
        print(f"[警告] 用例清单导出失败：{exc}")
    refresh_health()
    threading.Thread(target=health_loop, daemon=True).start()

    # 再补一个 IPv6 回环，让 localhost 两种解析都能连上
    try:
        v6 = _LoopbackV6Server(("::1", PORT), Handler)
        threading.Thread(target=v6.serve_forever, daemon=True).start()
    except OSError:
        v6 = None  # 没有 IPv6 或端口已被占，IPv4 已够用

    print("=" * 58)
    print(" 管伊佳ERP 自动化控制台")
    print(f" 地址：{url}")
    print(f"       或 http://localhost:{PORT}/ （IPv6 回环{'已启用' if v6 else '未启用'}）")
    print(" 注意：请访问上面的 http 地址；直接双击 dashboard/index.html")
    print("       会以 file:// 打开，接口全部连不上。")
    print(f" 解释器：{PYTHON}")
    print(" Ctrl+C 结束（只关面板，不影响已跑完的用例与报告）")
    print("=" * 58)

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n面板已停止")
    finally:
        server.server_close()
        if v6 is not None:
            v6.shutdown()
            v6.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
