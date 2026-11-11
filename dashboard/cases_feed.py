"""用例清单：由子进程导出，面板进程不 import 业务代码。

这样做的理由：用例脚本一旦写错（语法错、import 环），面板仍然能起来并
把「用例库读取失败」显示在卡片上。若在面板进程里直接 `import cases`，
一行用例写坏就连面板都打不开，等于把排查工具和待排查的对象绑在一起。
"""

from __future__ import annotations

import json
import subprocess
import threading
import time

from . import runtime
from .paths import CACHE_DIR, CASES_CACHE, PYTHON, ROOT
from .util import short_exc

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

_LOCK = threading.Lock()
_MEM = {"ts": 0, "data": None, "failAt": 0, "failMsg": ""}


def load_cases(force=False):
    """取用例清单：内存 → 磁盘缓存 → 子进程现导。返回 dict。"""
    with _LOCK:
        now = time.time()
        if not force and _MEM["data"] and now - _MEM["ts"] < runtime.CASE_TTL:
            return _MEM["data"]
        # 导出失败后 30s 内不再重试：health 每 5s 探一轮，否则会连续起子进程
        if not force and _MEM["failAt"] and now - _MEM["failAt"] < 30:
            raise RuntimeError(_MEM["failMsg"])
        if not force and CASES_CACHE.exists() and now - CASES_CACHE.stat().st_mtime < runtime.CASE_TTL:
            try:
                data = json.loads(CASES_CACHE.read_text("utf-8"))
                _MEM.update(ts=CASES_CACHE.stat().st_mtime, data=data)
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
            _MEM.update(failAt=time.time(), failMsg=f"执行导出脚本失败：{short_exc(exc)}")
            raise

        data = None
        for line in completed.stdout.splitlines():
            if line.startswith("@@DATA@@"):
                data = json.loads(line[len("@@DATA@@"):])
                break
        if data is None:
            detail = (completed.stderr or completed.stdout or "无输出").strip().splitlines()
            message = "用例清单导出失败：" + (detail[-1] if detail else "未知原因")
            _MEM.update(failAt=time.time(), failMsg=message)
            raise RuntimeError(message)

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CASES_CACHE.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        _MEM.update(ts=time.time(), data=data, failAt=0, failMsg="")
        return data
