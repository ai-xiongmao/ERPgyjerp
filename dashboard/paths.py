"""控制台用到的磁盘位置与解释器。

单独成文件的原因：这些值原先散落在 `dashboard_server.py` 各处，一旦代码
挪进子目录，`Path(__file__).parent` 就会静默指错地方（还不报错，只是找不到
页面/缓存）。集中一处，只在这里出现一次 `parent`。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # 项目根
DASHBOARD_DIR = ROOT / "dashboard"
PAGE_FILE = DASHBOARD_DIR / "index.html"
CACHE_DIR = DASHBOARD_DIR / ".cache"
CASES_CACHE = CACHE_DIR / "cases.json"
SERVER_LOG = CACHE_DIR / "server.log"
REPORTS_DIR = ROOT / "reports"


def _python_exe():
    """优先用项目 venv 的解释器跑子进程，避免系统 Python 缺 playwright。"""
    for candidate in (ROOT / ".venv" / "Scripts" / "python.exe",
                      ROOT / ".venv" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


PYTHON = _python_exe()
