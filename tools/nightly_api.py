"""夜间接口层巡检：只跑接口层，不启动浏览器，不依赖 UI 登录态。

为什么不整体放进 GitHub Actions：接口层虽然不需要浏览器，但需要真实登录态
（token 由桌面 MyTest 浏览器换取，缓存进 `.api_token`）。CI 上没有这台机器、
也没有这个 token，跑出来全是「阻塞」，看着绿其实什么都没验。所以夜间任务留在
本机由任务计划程序触发，CI 只跑离线门禁。

退出码：
    0  全通过
    1  有用例失败（run_cases 的约定：失败返回 1）
    2  一条都没选中（--layer api 却 0 条，说明注册被改坏了）
    3  接口认证不可用（token 过期且浏览器没开）——最常见，要人工登录一次
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTH_HINT = "接口认证不可用"


def main():
    cmd = [sys.executable, "run_cases.py", "run", "--layer", "api"]
    print(f"$ {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    output = (proc.stdout or "") + (proc.stderr or "")
    print(output, flush=True)

    if AUTH_HINT in output:
        print("!" * 60)
        print("[夜间巡检] 接口认证不可用：token 已过期，且浏览器未打开无法换新。")
        print("           请在 MyTest 里登录管伊佳 ERP，手动跑一次 `run_cases.py run --layer api`，")
        print("           让它把 token 写回 .api_token，之后夜间任务可继续无人值守。")
        print("!" * 60)
        return 3

    if re.search(r"共\s*0\s*条", output) or "没有匹配的用例" in output:
        print("[夜间巡检] 一条接口用例都没选中，检查 cases/__init__.py 的注册是否被改坏")
        return 2

    if proc.returncode != 0:
        print(f"[夜间巡检] 有用例失败（run_cases 返回 {proc.returncode}），报告见上面的「报告：」行")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
