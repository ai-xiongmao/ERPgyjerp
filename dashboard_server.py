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

代码组织：本文件只负责「解析参数 → 起服务 → 打横幅」。
具体能力按职责放在 dashboard/ 包里，依赖方向见 dashboard/__init__.py。
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dashboard import runtime  # noqa: E402
from dashboard.cases_feed import load_cases  # noqa: E402
from dashboard.health import health_loop, probe_http, refresh_health  # noqa: E402
from dashboard.paths import CACHE_DIR, PYTHON, SERVER_LOG  # noqa: E402
from dashboard.web import AppServer, Handler, LoopbackV6Server  # noqa: E402


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
    _ensure_std_streams()
    parser = argparse.ArgumentParser(description="管伊佳ERP 自动化控制台")
    parser.add_argument("--port", type=int, default=runtime.PORT, help=f"监听端口（默认 {runtime.PORT}）")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    runtime.PORT = args.port          # 必须改模块属性：其它模块读的是 runtime.PORT

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        except Exception:  # noqa: BLE001 - pythonw 下是文件对象，失败无妨
            pass

    url = f"http://{runtime.HOST}:{runtime.PORT}/"

    try:
        server = AppServer((runtime.HOST, runtime.PORT), Handler)
    except OSError as exc:
        # 端口被占：很可能已经有一个控制台在跑了，别再报一堆错让人以为坏了
        alive = False
        try:
            status, _ = probe_http(url + "api/health", timeout=2.0)
            alive = status == 200
        except Exception:  # noqa: BLE001
            alive = False
        if alive:
            print(f"[提示] {runtime.PORT} 端口上已经有一个控制台在运行：{url}")
            print("       不重复启动，直接打开已有实例。")
            if not args.no_browser:
                webbrowser.open(url)
            return 0
        print(f"[错误] 端口 {runtime.PORT} 启动失败：{exc}")
        print("       端口被其它程序占用，换一个：--port 8800")
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
        v6 = LoopbackV6Server(("::1", runtime.PORT), Handler)
        threading.Thread(target=v6.serve_forever, daemon=True).start()
    except OSError:
        v6 = None  # 没有 IPv6 或端口已被占，IPv4 已够用

    print("=" * 58)
    print(" 管伊佳ERP 自动化控制台")
    print(f" 地址：{url}")
    print(f"       或 http://localhost:{runtime.PORT}/ （IPv6 回环{'已启用' if v6 else '未启用'}）")
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
