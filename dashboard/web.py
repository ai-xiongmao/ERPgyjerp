"""HTTP 层：路由 + socket 服务。

这是控制台唯一对外的一层，所以「谁可以被调、能被谁调」的防线都放在这里：
- 只绑 127.0.0.1 / ::1，执行用例的能力不外泄到局域网；
- 写操作校验 Origin，防止别的网页偷偷 POST 一条「跑全部用例」；
- 打开报告的路径限定在 reports/ 下，不接受任意绝对路径；
- 「关闭服务」走同一套写操作校验，且只能关掉自己这个进程（没法关别人的）。
"""

from __future__ import annotations

import json
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import lifecycle, runtime
from .cases_feed import load_cases
from .env import launch_browser, open_path, prepare_env
from .health import health_snapshot, refresh_health
from .paths import PAGE_FILE, REPORTS_DIR
from .runs import RUNS
from .util import short_exc


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
        return any(host in origin for host in (f"127.0.0.1:{runtime.PORT}", f"localhost:{runtime.PORT}"))

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
                payload["server"] = {
                    "version": runtime.SERVER_VERSION,
                    "features": list(runtime.SERVER_FEATURES),
                }
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
                target = (REPORTS_DIR / name).resolve()
                if target.parent != REPORTS_DIR.resolve() or not target.exists():
                    return self._error("报告不存在", 404)
                return self._send(target.read_text("utf-8", "replace"), "text/plain; charset=utf-8")

            if path == "/favicon.ico":
                return self._send(b"", "image/x-icon", 200)

            return self._error("未知接口", 404)
        except Exception as exc:  # noqa: BLE001
            return self._error(short_exc(exc, 300), 500)

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

            if path == "/api/shutdown":
                # 先把跑着的子进程收掉：服务一退它就成孤儿进程，会在后台继续开浏览器、
                # 写报告，而端口已经没了——看起来像「关了但没关干净」。
                run_stopped = RUNS.stop()
                if not lifecycle.stop_all():
                    return self._error("当前进程没有可关闭的服务实例（可能已请求过关闭）", 409)
                return self._json({
                    "ok": True,
                    "run_stopped": run_stopped,
                    "message": "已中断执行中的任务，控制台正在关闭" if run_stopped else "控制台正在关闭",
                })

            if path == "/api/refresh":
                load_cases(force=True)
                refresh_health()
                return self._json({"ok": True})

            if path == "/api/open":
                body = self._body_json()
                open_path(body.get("path") or "")
                return self._json({"ok": True})

            if path == "/api/open-browser":
                return self._json({"ok": True, "launched": launch_browser()})

            if path == "/api/prepare":
                actions = prepare_env()
                refresh_health()
                return self._json({"ok": True, "actions": actions})

            return self._error("未知接口", 404)
        except ValueError as exc:
            return self._error(str(exc), 400)
        except Exception as exc:  # noqa: BLE001
            return self._error(short_exc(exc, 300), 500)


class AppServer(ThreadingHTTPServer):
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


class LoopbackV6Server(AppServer):
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
