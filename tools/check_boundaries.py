"""分层边界守卫：把「架构约定」变成一条能自动跑的检查。

守三条约定（都是本项目的真实痛点，见 docs/重构规划.md）：

  1. 用例层不碰页面细节——`cases/` 里出现 locator / wait_for_timeout / query_selector / goto
     说明 POM 被绕过，前端一改就整片失效；
  2. 页面对象不重复——三个页面对象的同名方法越多，改选择器要改的地方就越多；
  3. 单文件不超过 500 行——超了基本意味着一个文件干了多件事。

指标只允许变好。重构到一半时指标不动是正常的，一旦变差就拦下来（exit 1），
避免「一边清理一边又堆新的」。

用法：
    python tools/check_boundaries.py            # 对比基线，变差则退出码 1
    python tools/check_boundaries.py --detail   # 附带逐文件明细
    python tools/check_boundaries.py --update   # 指标已下降时重写基线

基线文件：docs/boundary_baseline.json（跟着代码一起提交，改基线要能说出理由）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "boundary_baseline.json"

SKIP_DIRS = {".venv", "__pycache__", ".git", "reports", "node_modules", ".cache", "api_dump"}
BIG_FILE_LIMIT = 500

# P2 会把 cases/ 重命名为 tests/ 并按模块分目录，届时这里同步改一处即可
CASE_DIR = ROOT / "cases"
PAGE_DIR = ROOT / "pages"

# 用例层一旦出现这些调用，说明它在直接操作 DOM，绕过了页面对象
PAGE_LEAK = re.compile(r"\blocator\s*\(|\bwait_for_timeout\s*\(|\bquery_selector\s*\(|\.goto\s*\(")
METHOD_DEF = re.compile(r"^    def ([a-zA-Z_]\w*)\s*\(", re.MULTILINE)


def _iter_py(directory: Path):
    for path in sorted(directory.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def measure():
    """算出三项指标及明细。"""
    leak_by_file = {}
    for path in _iter_py(CASE_DIR):
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = len(PAGE_LEAK.findall(text))
        if hits:
            leak_by_file[_rel(path)] = hits

    page_files = sorted(PAGE_DIR.glob("*_page.py"))
    owners = {}
    for path in page_files:
        for name in METHOD_DEF.findall(path.read_text(encoding="utf-8", errors="replace")):
            if name.startswith("__"):
                continue
            owners.setdefault(name, []).append(path.name)
    dup_methods = {name: files for name, files in owners.items() if len(files) > 1}

    big_files = {}
    for path in _iter_py(ROOT):
        count = _lines(path)
        if count > BIG_FILE_LIMIT:
            big_files[_rel(path)] = count

    return {
        "cases_page_leak": sum(leak_by_file.values()),
        "page_dup_methods": sum(len(files) - 1 for files in dup_methods.values()),
        "big_files": len(big_files),
        "_leak_by_file": dict(sorted(leak_by_file.items(), key=lambda kv: -kv[1])),
        "_dup_detail": dict(sorted(dup_methods.items())),
        "_big_files": dict(sorted(big_files.items(), key=lambda kv: -kv[1])),
    }


ROWS = [
    ("cases_page_leak", "用例层越界操作页面（次）"),
    ("page_dup_methods", "页面对象重复方法（个）"),
    ("big_files", f"超过 {BIG_FILE_LIMIT} 行的文件（个）"),
]


def _stable(metrics):
    return {key: metrics[key] for key, _ in ROWS}


def load_baseline():
    if not BASELINE.exists():
        return None
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[警告] 基线文件损坏，按无基线处理：{exc}", file=sys.stderr)
        return None


def save_baseline(metrics):
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    payload = {**_stable(metrics), "_note": "指标只允许下降；--update 重写本文件时请说明原因"}
    BASELINE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_report(metrics, baseline, detail=False):
    print(f"{'指标':<32}{'当前':>6}{'基线':>6}  状态")
    print("-" * 62)
    worse = []
    for key, label in ROWS:
        now = metrics[key]
        was = None if baseline is None else baseline.get(key)
        if was is None:
            state = "新建基线"
        elif now > was:
            state = f"变差 +{now - was}"
            worse.append((label, was, now))
        elif now < was:
            state = f"改善 -{was - now}"
        else:
            state = "保持"
        print(f"{label:<32}{now:>6}{'-' if was is None else was:>6}  {state}")

    if detail and metrics["_leak_by_file"]:
        print("\n越界明细（用例文件 → 次数）：")
        for name, hits in metrics["_leak_by_file"].items():
            print(f"  {hits:>3}  {name}")
    if detail and metrics["_big_files"]:
        print("\n超限文件：")
        for name, count in metrics["_big_files"].items():
            print(f"  {count:>4} 行  {name}")
    return worse


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="分层边界守卫：用例层 / 页面对象 / 文件体积")
    parser.add_argument("--update", action="store_true", help="把当前指标写为基线")
    parser.add_argument("--detail", action="store_true", help="打印逐文件明细")
    args = parser.parse_args(argv)

    metrics = measure()
    if args.update:
        save_baseline(metrics)
        print(f"基线已更新：{_rel(BASELINE)}")
        print_report(metrics, metrics, detail=args.detail)
        return 0

    baseline = load_baseline()
    worse = print_report(metrics, baseline, detail=args.detail)
    if baseline is None:
        print(f"\n提示：没有基线文件，先跑一次 --update 建立基线（{_rel(BASELINE)}）")
        return 0
    if worse:
        print("\n以下指标比基线更差，请先修掉再提交：")
        for label, was, now in worse:
            print(f"  - {label}：{was} → {now}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
