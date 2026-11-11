"""任务执行：一次运行 = 一个 `run_cases.py run` 子进程。

用子进程而不是线程，是因为面板要展示的正是「命令行会怎样」，这样出问题时
可以直接把面板上显示的那条命令复制到终端复跑，行为完全一致。副作用是日志
只能靠解析 stdout：`_LINE_TOTAL` / `_LINE_RESULT` 就是为此写的，
两处正则和 run_cases 的打印格式是耦合的，改打印格式要同步改这里。
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time

from . import runtime
from .paths import PYTHON, ROOT
from .util import short_exc

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
            self._ingest(f"[面板] 读取输出失败：{short_exc(exc)}")
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
            if len(self.logs) > runtime.MAX_LOG_LINES:
                del self.logs[: len(self.logs) - runtime.MAX_LOG_LINES]

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
