"""跨模块的小工具：异常摘要 + 探测结果短缓存。

放这里而不是 health.py，是因为 `short_exc` 被探测层、用例导出层、路由层都要用，
任何一层独占都会制造反向依赖。
"""

from __future__ import annotations

import time


def short_exc(exc, limit=90):
    """把异常压成一行短文本：面板上只有一行位置，堆栈会把它撑爆。"""
    text = f"{type(exc).__name__}: {exc}".replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")


_CACHE = {}


def cached(key, ttl, producer):
    """探测结果短缓存：目标站点这类慢探测不必每 5s 打一次。"""
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = producer()
    _CACHE[key] = (now, value)
    return value


def cache_drop(key):
    _CACHE.pop(key, None)
