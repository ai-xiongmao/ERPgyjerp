"""离线门禁：不用浏览器、不连 ERP 也能判断「这次改动有没有搞坏东西」。

为什么需要它：这套自动化真正跑起来要桌面 MyTest 浏览器 + 登录态 + 目标系统，
CI（以及别人的机器）都没有。但重构中绝大多数事故是**静态可查**的——
导入写坏导致几十条用例静默消失、端口/包路径改了导致面板起不来、
用例偷偷去操作 DOM。这些都能在 20 秒内查出来。

检查项：
  1. ruff        语法 / 未定义名 / 未用导入 / 导入排序 / 行宽
  2. compileall  全部模块可编译
  3. 边界守卫    用例层不碰 DOM、页面对象不重复、文件不超 500 行
  4. 注册基线    用例编号清单与上次提交逐条一致（防「静默丢用例」）
  5. 面板冒烟    真起一次服务，打关键接口，确认路由与用例清单都能通

用法：
    python tools/gate.py            # 全部检查
    python tools/gate.py --update   # 用例清单有意的增减后，刷新基线
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "docs" / "case_counts.json"
PY = sys.executable

# Windows 上「非控制台」输出（CI 的管道、重定向到文件）默认用系统 ANSI 码页：
# 中文机器是 cp936 能打中文，英文 runner 是 cp1252，第一句中文 print 就
# UnicodeEncodeError 直接崩，且只留下 exit code 1，看不出任何原因。
# 这里把本进程的输出流钉成 UTF-8，子进程靠 _run() 里的 PYTHONIOENCODING 传递。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - 老版本或已重定向的流，忽略即可
        pass

# 传给所有子进程：保证它们也不受宿主码页影响
CHILD_ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")

_DUMP = r"""
import json, sys
sys.path.insert(0, r"%s")
import cases  # noqa: F401  导入即注册
from framework import registry
all_cases = registry.all_cases()
api_layer = registry.select(layer="api")
print(json.dumps({
    "total": len(all_cases),
    "uiAuto": sum(1 for c in all_cases if c.func is not None and not c.blocked),
    "apiLayer": len(api_layer),
    "apiAuto": sum(1 for c in api_layer if c.api is not None
                   and not (c.blocked and not c.api_unblocked)),
    "cids": [c.cid for c in all_cases],
}, ensure_ascii=False))
"""


class Step:
    def __init__(self, name):
        self.name = name
        self.ok = False
        self.note = ""


def _run(cmd, timeout=600):
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout,
                          env=CHILD_ENV)


def step_ruff(s: Step):
    proc = _run([PY, "-m", "ruff", "check"])
    s.ok = proc.returncode == 0
    if not s.ok:
        s.note = (proc.stdout or proc.stderr).strip().splitlines()[-1] if (proc.stdout or proc.stderr) else "ruff 失败"
    else:
        s.note = "无告警"


def step_compile(s: Step):
    targets = ["framework", "pages", "apis", "cases", "config", "dashboard", "tools",
               "run_cases.py", "dashboard_server.py"]
    proc = _run([PY, "-m", "compileall", "-q", *targets])
    s.ok = proc.returncode == 0
    s.note = "全部模块可编译" if s.ok else (proc.stdout or proc.stderr).strip()[:200]


def step_boundaries(s: Step):
    proc = _run([PY, "tools/check_boundaries.py"])
    s.ok = proc.returncode == 0
    text = (proc.stdout or "") + (proc.stderr or "")
    bad = [ln.strip() for ln in text.splitlines() if "回退" in ln or "ERROR" in ln.upper()]
    s.note = bad[0][:120] if bad else ("未越界" if s.ok else text.strip()[-160:])


def _case_registry():
    proc = _run([PY, "-c", _DUMP % str(ROOT)])
    line = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
    if not line:
        raise RuntimeError((proc.stderr or "导出失败").strip().splitlines()[-1])
    return json.loads(line[-1])


def step_registry(s: Step, update=False):
    data = _case_registry()
    if update or not BASELINE.exists():
        BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", "utf-8")
        s.ok = True
        s.note = f"已写入基线（{data['total']} 条）"
        return data
    expected = json.loads(BASELINE.read_text("utf-8"))
    if data == expected:
        s.ok = True
        s.note = (f"{data['total']} 条 / UI 可自动 {data['uiAuto']} / "
                  f"接口层 {data['apiLayer']}（可自动 {data['apiAuto']}）")
        return data
    s.ok = False
    parts = []
    gone = sorted(set(expected["cids"]) - set(data["cids"]))
    added = sorted(set(data["cids"]) - set(expected["cids"]))
    if gone:
        parts.append(f"少了 {len(gone)} 条：{', '.join(gone[:5])}")
    if added:
        parts.append(f"多了 {len(added)} 条：{', '.join(added[:5])}")
    if not parts:
        parts.append(f"编号没变但计数变了（{expected['total']} → {data['total']}）")
    s.note = "；".join(parts) + "。确实是有意的增减就重跑 --update"
    return data


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def step_dashboard(s: Step, expected_total=None):
    port = _free_port()
    env = dict(CHILD_ENV)
    # 指向必然连不上的回环端口：让探测快速失败，不依赖外网，也不受代理影响
    env.update({"ERP_DASH_PORT": str(port),
                "ERP_BASE_URL": "http://127.0.0.1:1",
                "ERP_CDP_ENDPOINT": "http://127.0.0.1:1",
                "PYTHONIOENCODING": "utf-8"})
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    proc = subprocess.Popen([PY, "dashboard_server.py", "--port", str(port), "--no-browser"],
                            cwd=str(ROOT), env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", creationflags=flags)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f"http://127.0.0.1:{port}"
    problems, cases = [], None
    try:
        deadline = time.time() + 60
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                with opener.open(base + "/api/health", timeout=2) as resp:
                    ready = resp.status == 200
                    if ready:
                        break
            except Exception:  # noqa: BLE001 - 还没起来
                pass
            time.sleep(0.5)
        if not ready:
            tail = (proc.stdout.read() if proc.stdout else "")[-300:]
            s.note = f"服务未就绪（退出码 {proc.poll()}）：{tail.strip()}"
            return

        def get(path):
            # 404/500 是预期内的检查项，不是异常：按状态码返回而不是抛出
            try:
                with opener.open(base + path, timeout=60) as resp:
                    return resp.status, resp.read()
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read()

        status, body = get("/")
        if status != 200 or b"</html>" not in body.lower():
            problems.append(f"首页异常（HTTP {status}，{len(body)} 字节）")

        # refresh=1 强制重新导出：不加的话会读到 dashboard/.cache/cases.json
        # 里上一轮的旧清单，本机跑门禁时永远是绿的（CI 上没缓存所以才发现不了）
        status, body = get("/api/cases?refresh=1")
        payload = json.loads(body)
        cases = len(payload.get("cases") or [])
        if status != 200 or not cases:
            problems.append(f"/api/cases 异常（HTTP {status}，{cases} 条）")
        if expected_total is not None and cases != expected_total:
            problems.append(f"/api/cases 返回 {cases} 条，基线是 {expected_total} 条")

        for path, want in (("/favicon.ico", 200), ("/api/nope", 404)):
            status, _ = get(path)
            if status != want:
                problems.append(f"{path} 期望 HTTP {want}，实际 {status}")

        status, body = get("/api/health")
        health = json.loads(body)
        keys = [c["key"] for c in health.get("checks") or []]
        if keys != ["panel", "browser", "page", "site", "cases", "deps"]:
            problems.append(f"健康探针不完整：{keys}")
        s.ok = not problems
        s.note = "、".join(problems) if problems else f"首页/接口/{cases} 条用例清单均正常"
    except Exception as exc:  # noqa: BLE001
        s.note = f"冒烟失败：{type(exc).__name__}: {exc}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    update = "--update" in argv

    print("=" * 62)
    print(" 离线门禁（不启动浏览器、不连目标系统）")
    print("=" * 62)

    steps = []

    s = Step("ruff 静态检查")
    step_ruff(s)
    steps.append(s)

    s = Step("模块可编译")
    step_compile(s)
    steps.append(s)

    s = Step("分层边界守卫")
    step_boundaries(s)
    steps.append(s)

    s = Step("用例注册基线")
    data = step_registry(s, update=update)
    steps.append(s)

    s = Step("控制台冒烟")
    step_dashboard(s, expected_total=data["total"])
    steps.append(s)

    print()
    for item in steps:
        mark = "PASS" if item.ok else "FAIL"
        print(f" [{mark}] {item.name:<16} {item.note}")
    failed = [x for x in steps if not x.ok]
    print()
    if failed:
        print(f"门禁未通过：{len(failed)} 项失败")
        return 1
    print("门禁通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
