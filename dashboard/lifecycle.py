"""进程收尾：让页面上的「关闭服务」能真的把控制台停掉。

为什么单独一个模块：`web.py` 里的请求处理器只知道自己，拿不到
`dashboard_server.py` 里那个正在 `serve_forever()` 的实例；而把 server 对象
塞进 `runtime` 又会让「常量模块」持有活对象，谁都能被误改。这里只做三件事——
登记、查询、异步关停，谁起的服务谁登记。

关停必须**异步**：调用它的正是被关掉的那个服务里的一个请求线程，同步
`shutdown()` 会一直等 `serve_forever()` 退出，而此刻响应还没写回浏览器，
结果是页面转圈、服务也停不利索。所以先返回，再隔一小会儿真正关。
"""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_servers: list = []
_stopping = False


def register(*servers):
    """登记需要被关停的服务实例（IPv4 主服务 + IPv6 回环），返回已登记数量。"""
    with _lock:
        for srv in servers:
            if srv is not None and srv not in _servers:
                _servers.append(srv)
        return len(_servers)


def pending():
    with _lock:
        return len(_servers)


def stop_all(delay=0.25):
    """异步关停所有已登记的服务；重复调用只生效一次。

    返回 False 表示「没有可关的实例」或「已经在关了」，调用方据此给页面如实回话。
    """
    global _stopping
    with _lock:
        if _stopping or not _servers:
            return False
        _stopping = True
        servers = list(_servers)

    def _run():
        # 留出时间把 200 响应写回浏览器，否则页面只会看到「连不上」而不知道为什么
        time.sleep(delay)
        for srv in servers:
            try:
                srv.shutdown()  # 让 serve_forever() 立刻返回，主线程的 finally 负责 server_close
            except Exception:  # noqa: BLE001 - 关停路径上不该再抛出
                pass

    threading.Thread(target=_run, name="dash-shutdown", daemon=True).start()
    return True
