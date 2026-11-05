"""用例执行入口：把测试用例表里的操作步骤跑成自动化。

前置条件：
1. 双击桌面 MyTest.exe 打开浏览器（自带 --remote-debugging-port=9231）；
2. 在其中登录 https://cloud.gyjerp.com 。

常用命令：
    python run_cases.py                          # 交互式菜单：选全部 / 按模块 / 按标签 / 指定编号
    python run_cases.py run                       # 跳过菜单，直接跑全部
    python run_cases.py list                      # 只看清单
    python run_cases.py run --only TC-UNIT-012,TC-UNIT-013
    python run_cases.py run --module DEP          # 只跑仓库信息模块
    python run_cases.py run --tag 新增 查询
    python run_cases.py run --from TC-UNIT-020
    python run_cases.py run --update-xlsx         # 跑完回填「执行结果」列

产物：
    reports/run_<时间>.md              终端摘要（文本，便于 grep / CI 日志）
    reports/allure-report/index.html   Allure 报告（单文件，双击可看）
        --allure off    不生成 Allure
        --allure multi  生成多文件版（供 allure open）

环境变量：
    ERP_ACTION_DELAY_MS  每个 UI 动作后的间隔（默认 1000ms）
    ERP_RELOGIN_WAIT     掉登录时等待人工登录的秒数（默认 180，0=立即失败）
"""

import argparse
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

from browser import SessionExpiredError, connect
from config import BASE_URL
from framework import registry
from framework.allure_report import AllureWriter, generate_report, instrument
from framework.context import Context
from framework.data import TestData
from framework.runner import REPORT_DIR, Runner
from pages.base_page import BasePage
from pages.depot_page import DepotPage
from pages.product_page import ProductPage
from pages.unit_page import UnitPage

import cases  # noqa: F401 - 导入即注册用例

CASE_FILE = Path(__file__).resolve().parent / "管伊佳ERP-测试用例.xlsx"
ALLURE_RESULTS = REPORT_DIR / "allure-results"
ALLURE_REPORT = REPORT_DIR / "allure-report"

SUBCOMMANDS = ("run", "list")

# 模块前缀 → 展示名。菜单与 --module 共用，避免两处各写一份
MODULE_LABELS = {
    "UNIT": "多单位",
    "MAT": "商品信息",
    "DEP": "仓库信息",
}
MODULE_PATHS = {
    "UNIT": "/system/unit",
    "MAT": "/material/material",
    "DEP": "/system/depot",
}


def module_label(prefix):
    name = MODULE_LABELS.get(prefix, prefix)
    path = MODULE_PATHS.get(prefix)
    return f"{name}（{path}）" if path else name


def _add_select_options(parser):
    """run / list 共用的用例筛选参数。"""
    parser.add_argument("--only", help="只跑指定编号，逗号分隔，如 TC-UNIT-012,TC-UNIT-013")
    parser.add_argument("--tag", nargs="*", help="只跑指定标签，如 --tag 新增 查询")
    parser.add_argument("--module", nargs="*", choices=list(MODULE_LABELS),
                        help="只跑指定模块：UNIT=多单位 / MAT=商品信息 / DEP=仓库信息")
    parser.add_argument("--from", dest="start", help="从某条编号开始（含），如 TC-UNIT-020")
    parser.add_argument("--layer", choices=["ui", "api"], default="ui",
                        help="执行层：ui=浏览器页面（默认）/ api=后端接口")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="run_cases.py",
        description="管伊佳ERP UI 自动化：按测试用例编号执行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("不带任何参数时进入交互菜单选择执行范围；带了参数就直接按参数跑，"
                "例如 `run_cases.py --only TC-UNIT-012` 等同 `run_cases.py run --only ...`"))
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="执行用例")
    _add_select_options(p_run)
    p_run.add_argument("--keep-data", action="store_true", help="保留测试数据（默认跑完回收）")
    p_run.add_argument("--relogin-wait", type=int, default=None,
                       help="掉登录时等待人工登录的秒数（默认取环境变量 ERP_RELOGIN_WAIT）")
    p_run.add_argument("--data-prefix", help="指定数据前缀（排查问题时便于复现）")
    p_run.add_argument("--report-dir", default=str(REPORT_DIR), help="报告输出目录")
    p_run.add_argument("--allure", choices=["auto", "off", "multi"], default="auto",
                       help="Allure 报告：auto=单文件（默认）/ off=不生成 / multi=多文件版")
    p_run.add_argument("--update-xlsx", action="store_true", help="把结果回填用例表「执行结果」列")

    p_list = sub.add_parser("list", help="列出用例清单，不执行")
    _add_select_options(p_list)
    return parser


def parse_args(argv=None):
    """解析命令行；兼容旧写法（无子命令 / --list）。"""
    argv = list(sys.argv[1:] if argv is None else argv)
    raw_empty = not argv  # 完全没给参数：可能要走交互菜单

    if not argv or argv[0] not in SUBCOMMANDS:
        if "--list" in argv:
            argv = [a for a in argv if a != "--list"]
            argv.insert(0, "list")
        else:
            argv.insert(0, "run")
    args = build_parser().parse_args(argv)
    args.raw_empty = raw_empty
    return args


def select_cases(args):
    only = args.only.split(",") if getattr(args, "only", None) else None
    return registry.select(
        only=only,
        tags=getattr(args, "tag", None),
        prefixes=getattr(args, "module", None),
        start=getattr(args, "start", None),
        layer=getattr(args, "layer", "ui"),
    )


def scope_text(args):
    """把筛选条件说成人话，写进报告与 Allure 的 Environment 区。"""
    parts = []
    if getattr(args, "only", None):
        parts.append(f"编号 {args.only}")
    if getattr(args, "module", None):
        parts.append("模块 " + "/".join(args.module))
    if getattr(args, "tag", None):
        parts.append("标签 " + "/".join(args.tag))
    return "、".join(parts) or "全部用例"


def print_catalog(cases_, layer="ui"):
    print(f"{'编号':<14}{'标签':<8}{'优先级':<6}{'状态':<6}标题")
    for item in cases_:
        state = "阻塞" if item.blocked_for(layer) else "可自动"
        print(f"{item.cid:<14}{item.tag:<8}{item.priority:<6}{state:<6}{item.title}")
    total = len(cases_)
    runnable = sum(1 for item in cases_ if item.runnable_on(layer))
    layer_name = "接口" if layer == "api" else "UI"
    print(f"\n共 {total} 条，{layer_name}层可自动 {runnable} 条，阻塞/人工 {total - runnable} 条")


def cmd_list(args):
    selected = select_cases(args)
    if not selected:
        print("没有匹配的用例", file=sys.stderr)
        return 1
    print_catalog(selected, layer=getattr(args, "layer", "ui"))
    return 0


# ==================== 交互式菜单 ====================
#
# 只在「完全没给参数 + 标准输入是终端」时启用；CI、重定向、后台执行都直接跑全部，
# 不会因为等输入把流水线挂住。想跳过菜单又保留全量语义，用 `run_cases.py run`。

def _ask(prompt, default=""):
    """读一行；空输入取默认值。返回 None 表示用户退出（EOF / Ctrl-C）。"""
    try:
        raw = input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return raw.strip() or default


def _split_tokens(raw):
    return [t for t in re.split(r"[,，、\s]+", raw) if t]


def _display_width(text):
    """中文/全角按 2 列算，用于菜单对齐。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text, width):
    return text + " " * max(0, width - _display_width(text))


class _Back(Exception):
    """菜单内部信号：用户输入 b，返回上一级。"""


def _ask_multi(options, prompt):
    """多选：输入 1,3 或 1-3；返回选中的下标列表，None 表示退出。"""
    while True:
        raw = _ask(prompt)
        if raw is None:
            return None
        if raw.lower() == "b":
            raise _Back
        picks, bad = [], []
        for token in _split_tokens(raw):
            span = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
            if span:
                a, b = int(span.group(1)), int(span.group(2))
                if 1 <= a <= b <= len(options):
                    picks.extend(range(a - 1, b))
                else:
                    bad.append(token)
            elif token.isdigit() and 1 <= int(token) <= len(options):
                picks.append(int(token) - 1)
            else:
                bad.append(token)
        if bad or not picks:
            shown = "、".join(bad) if bad else "（空输入）"
            print(f"  输入无效：{shown}；请输入 1~{len(options)}，多个用逗号分隔，b 返回")
            continue
        return sorted(set(picks))


def _expand_ids(raw):
    """展开编号输入：`TC-DEP-001,TC-DEP-005` 或同前缀区间 `TC-DEP-001-010`。"""
    ids = []
    for token in _split_tokens(raw):
        token = token.upper()
        span = re.fullmatch(r"(TC-[A-Z]+)-(\d+)\s*-\s*(\d+)", token)
        if span:
            prefix, a, b = span.group(1), int(span.group(2)), int(span.group(3))
            width = len(span.group(2))
            ids.extend(f"{prefix}-{i:0{width}d}" for i in range(a, b + 1))
        else:
            ids.append(token)
    return ids


def _ask_ids(known):
    """输入编号，原地重试直到有效；b 返回上一级，空/EOF 退出。"""
    while True:
        raw = _ask("\n 请输入编号（如 TC-DEP-001,TC-DEP-005 或区间 TC-DEP-001-010；"
                   "b 返回）: ")
        if raw is None:
            return None
        if raw.lower() == "b":
            raise _Back
        ids = _expand_ids(raw)
        missing = [i for i in ids if i not in known]
        if missing:
            print(f"  以下编号不存在，已忽略：{', '.join(missing)}")
        valid = [i for i in ids if i in known]
        if not valid:
            print("  没有匹配的编号，请重新输入")
            continue
        return {"only": ",".join(valid)}


def _count_by(key_func):
    """按 key 统计 (总数, 可自动数)，保持首次出现顺序。"""
    counts = {}
    for item in registry.all_cases():
        total, run = counts.get(key_func(item), (0, 0))
        counts[key_func(item)] = (total + 1, run + (1 if item.runnable else 0))
    return counts


def _menu_modules():
    counts = _count_by(lambda item: registry.prefix_of(item.cid))
    ordered = [p for p in MODULE_LABELS if p in counts] + \
              [p for p in counts if p not in MODULE_LABELS]
    print("\n 选择模块（可多选）：")
    for i, prefix in enumerate(ordered, 1):
        total, run = counts[prefix]
        print(f"   {i}  {_pad(module_label(prefix), 32)}{total:>3} 条（可自动 {run}）")
    return ordered


def _menu_tags():
    counts = _count_by(lambda item: item.tag)
    ordered = sorted(counts, key=lambda t: (-counts[t][0], t))
    print("\n 选择标签（可多选）：")
    for i, tag in enumerate(ordered, 1):
        total, run = counts[tag]
        print(f"   {i}  {_pad(tag or '(无标签)', 12)}{total:>3} 条（可自动 {run}）")
    return ordered


def _confirm_plan(planned, state):
    """展示待执行范围求确认。True=开始 / False=重选 / None=退出。"""
    if not planned:
        print("\n 没有匹配的用例，请重新选择")
        return False

    total = len(planned)
    runnable = sum(1 for item in planned if item.runnable)
    print("\n" + "-" * 60)
    print(f" 待执行 {total} 条：可自动 {runnable} 条，阻塞/人工 {total - runnable} 条")
    if runnable == 0:
        print(" 这些用例都需要人工执行，脚本跑不了")
        print("-" * 60)
        return False
    if total <= 10:
        for item in planned:
            print(f"   {'·' if item.runnable else '×'} {item.cid}  {item.title}")
    else:
        print(f"   起 {planned[0].cid} … 止 {planned[-1].cid}")
    print("-" * 60)
    print("  回车 = 开始    u = 开始并回填用例表    n = 返回重选")

    while True:
        raw = _ask(" 请确认 [回车]: ", "")
        if raw is None:
            return None
        answer = raw.lower()
        if answer in ("", "y", "yes"):
            return True
        if answer == "u":
            state["update_xlsx"] = True
            return True
        if answer in ("n", "no", "b"):
            return False
        print("  请输入 回车 / u / n")


def interactive_menu():
    """无参数启动时的引导菜单。

    返回 ("list",) / ("run", 筛选条件 dict, 是否回填 xlsx) / None（用户退出）。
    """
    cases_all = registry.all_cases()
    runnable = sum(1 for item in cases_all if item.runnable)

    while True:
        print("\n" + "=" * 62)
        print(" 管伊佳ERP UI 自动化")
        print(f" 共 {len(cases_all)} 条：可自动 {runnable} 条，阻塞/人工 {len(cases_all) - runnable} 条")
        print("=" * 62)
        print("   1  全部执行")
        print("   2  按模块执行（多单位 / 商品信息 / 仓库信息）")
        print("   3  按标签执行（页面入口 / 查询 / 新增 …）")
        print("   4  输入用例编号")
        print("   5  只看清单，不执行")
        print("   q  退出")

        choice = _ask("\n 请选择 [1]: ", "1")
        if choice is None or choice.lower() == "q":
            return None
        if choice == "5":
            return ("list",)

        if choice == "1":
            filters = {}
        elif choice in ("2", "3"):
            options = _menu_modules() if choice == "2" else _menu_tags()
            key = "module" if choice == "2" else "tag"
            try:
                picks = _ask_multi(options, "\n 请输入序号（如 1 或 1,3；b 返回）: ")
            except _Back:
                continue
            if picks is None:
                return None
            filters = {key: [options[i] for i in picks]}
        elif choice == "4":
            try:
                filters = _ask_ids({item.cid for item in cases_all})
            except _Back:
                continue
            if filters is None:
                return None
        else:
            print(f"  没有「{choice}」这个选项，请输入 1~5 或 q")
            continue

        planned = registry.select(
            only=filters["only"].split(",") if filters.get("only") else None,
            tags=filters.get("tag"),
            prefixes=filters.get("module"),
        )
        state = {"update_xlsx": False}
        verdict = _confirm_plan(planned, state)
        if verdict is None:
            return None
        if verdict:
            return ("run", filters, state["update_xlsx"])
        # 否则回到菜单重选


def cmd_run(args):
    layer = getattr(args, "layer", "ui")
    selected = select_cases(args)
    if not selected:
        print(f"没有匹配的用例（执行层 {layer}），用 `run_cases.py list --layer {layer}` 查看清单",
              file=sys.stderr)
        return 1

    data = TestData(run_id=args.data_prefix)
    allure = None
    if args.allure != "off":
        if layer == "ui":
            # 给页面对象的动作方法套上「记步骤」，报告里才能看到点了什么、填了什么
            instrument(BasePage, UnitPage, ProductPage, DepotPage)
        allure = AllureWriter(
            ALLURE_RESULTS,
            run_meta={
                "base_url": BASE_URL,
                "layer": "接口" if layer == "api" else "UI",
                "data_prefix": data.token,
                "scope": scope_text(args),
            },
            clean=True,
        )

    if layer == "api":
        # 接口层不碰浏览器：只取一次登录 token，全程 HTTP
        from framework.api_context import ApiContext

        ctx = ApiContext(data=data)
        runner = Runner(ctx, cleanup=not args.keep_data, allure=allure, layer="api")
        return _execute(args, ctx, runner, expected_layer="api")

    with connect() as page:
        ctx = Context(page, data)
        runner = Runner(ctx, relogin_wait=args.relogin_wait,
                        cleanup=not args.keep_data, allure=allure, layer="ui")
        return _execute(args, ctx, runner, expected_layer="ui")


def _execute(args, ctx, runner, expected_layer):
    """执行 + 出报告 + 收尾回收（UI / 接口两层共用）。"""
    runner.run(select_cases(args))

    print("\n" + runner.summary_line())
    runner.print_failures()
    runner.print_blocked()

    md_path = runner.write_report(
        directory=args.report_dir, tag=(args.tag[0] if args.tag else None))
    print(f"\n报告：{md_path}")

    allure = runner.allure
    if getattr(args, "allure", "off") != "off" and not isinstance(allure, type(None)):
        # 报告名带时间戳，避免覆盖历史：
        #   单文件（默认）→ reports/allure-report/20261102_200531.html
        #   多文件（--allure multi）→ reports/allure-report/20261102_200531/index.html
        stamp = time.strftime("%Y%m%d_%H%M%S")
        layer_name = "接口" if expected_layer == "api" else "UI"
        report_name = f"管伊佳ERP {layer_name} 自动化 {time.strftime('%Y-%m-%d %H:%M')}"
        if args.allure == "multi":
            report_dir = ALLURE_REPORT / stamp
            index = generate_report(ALLURE_RESULTS, report_dir,
                                    single_file=False, name=report_name)
            if index:
                print(f"Allure：{index}")
                print("        查看：node tools/allure/node_modules/allure-commandline/bin/allure "
                      f"open {report_dir}")
        else:
            # Allure CLI 只会输出 index.html，所以先生成到临时目录再改名
            with tempfile.TemporaryDirectory() as tmp:
                index = generate_report(ALLURE_RESULTS, tmp,
                                        single_file=True, name=report_name)
                if index:
                    target = ALLURE_REPORT / f"{stamp}.html"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(index), str(target))
                    print(f"Allure：{target}")

    if not args.keep_data:
        try:
            leftover = ctx.cleanup()
            if leftover:
                print(f"收尾回收 {leftover} 条残留测试数据")
        except Exception as exc:  # noqa: BLE001
            print(f"收尾回收失败：{type(exc).__name__}: {exc}")

    if args.update_xlsx:
        backup, written = runner.update_xlsx(CASE_FILE)
        print(f"已回填 {written} 条「执行结果」，原表备份：{backup.name}")

    bad = runner.counts()[registry.FAIL] + runner.counts()[registry.ERROR]
    return 0 if bad == 0 else 1


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)

    # 完全无参数 + 交互终端 → 引导菜单；非交互环境（CI / 重定向 / 后台）直接跑全部
    if args.raw_empty:
        if sys.stdin.isatty():
            menu = interactive_menu()
            if menu is None:
                print("\n已退出")
                return 0
            if menu[0] == "list":
                return cmd_list(args)
            _, filters, update_xlsx = menu
            for key in ("only", "tag", "module"):
                if filters.get(key):
                    setattr(args, key, filters[key])
            if update_xlsx:
                args.update_xlsx = True
        else:
            print("[提示] 当前不是交互终端，直接执行全部用例；"
                  "要选范围请加 --module / --tag / --only，或运行 run_cases.py list 查看清单")

    if args.command == "list":
        return cmd_list(args)
    return cmd_run(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SessionExpiredError as exc:
        print(f"\n[需要重新登录] {exc}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        sys.exit(130)
