"""用例执行入口：把测试用例表里的操作步骤跑成自动化。

前置条件：
1. 双击桌面 MyTest.exe 打开浏览器（自带 --remote-debugging-port=9231）；
2. 在其中登录 https://cloud.gyjerp.com 。

常用命令：
    python run_cases.py                          # 跑全部（默认 run）
    python run_cases.py list                     # 只看清单
    python run_cases.py run --only TC-UNIT-012,TC-UNIT-013
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
import sys
import time
from pathlib import Path

from browser import SessionExpiredError, connect
from config import BASE_URL
from framework import registry
from framework.allure_report import AllureWriter, generate_report, instrument
from framework.context import Context
from framework.data import TestData
from framework.runner import REPORT_DIR, Runner
from pages.base_page import BasePage
from pages.product_page import ProductPage
from pages.unit_page import UnitPage

import cases  # noqa: F401 - 导入即注册用例

CASE_FILE = Path(__file__).resolve().parent / "管伊佳ERP-测试用例.xlsx"
ALLURE_RESULTS = REPORT_DIR / "allure-results"
ALLURE_REPORT = REPORT_DIR / "allure-report"

SUBCOMMANDS = ("run", "list")


def _add_select_options(parser):
    """run / list 共用的用例筛选参数。"""
    parser.add_argument("--only", help="只跑指定编号，逗号分隔，如 TC-UNIT-012,TC-UNIT-013")
    parser.add_argument("--tag", nargs="*", help="只跑指定标签，如 --tag 新增 查询")
    parser.add_argument("--from", dest="start", help="从某条编号开始（含），如 TC-UNIT-020")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="run_cases.py",
        description="管伊佳ERP UI 自动化：按测试用例编号执行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="省略子命令时默认执行 run，例如 `run_cases.py --only TC-UNIT-012` 等同 `run_cases.py run --only ...`")
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

    if not argv or argv[0] not in SUBCOMMANDS:
        if "--list" in argv:
            argv = [a for a in argv if a != "--list"]
            argv.insert(0, "list")
        else:
            argv.insert(0, "run")
    return build_parser().parse_args(argv)


def select_cases(args):
    only = args.only.split(",") if getattr(args, "only", None) else None
    return registry.select(only=only, tags=getattr(args, "tag", None), start=getattr(args, "start", None))


def print_catalog(cases_):
    print(f"{'编号':<14}{'标签':<8}{'优先级':<6}{'状态':<6}标题")
    for item in cases_:
        state = "阻塞" if item.blocked else "可自动"
        print(f"{item.cid:<14}{item.tag:<8}{item.priority:<6}{state:<6}{item.title}")
    total = len(cases_)
    runnable = sum(1 for item in cases_ if item.runnable)
    print(f"\n共 {total} 条，可自动 {runnable} 条，阻塞/人工 {total - runnable} 条")


def cmd_list(args):
    selected = select_cases(args)
    if not selected:
        print("没有匹配的用例", file=sys.stderr)
        return 1
    print_catalog(selected)
    return 0


def cmd_run(args):
    selected = select_cases(args)
    if not selected:
        print("没有匹配的用例，用 `run_cases.py list` 查看清单", file=sys.stderr)
        return 1

    data = TestData(run_id=args.data_prefix)
    allure = None
    if args.allure != "off":
        # 给页面对象的动作方法套上「记步骤」，报告里才能看到点了什么、填了什么
        instrument(BasePage, UnitPage, ProductPage)
        allure = AllureWriter(
            ALLURE_RESULTS,
            run_meta={
                "base_url": BASE_URL,
                "data_prefix": data.token,
                "scope": args.only or (("标签 " + "/".join(args.tag)) if args.tag else "全部用例"),
            },
            clean=True,
        )

    with connect() as page:
        ctx = Context(page, data)
        runner = Runner(ctx, relogin_wait=args.relogin_wait,
                        cleanup=not args.keep_data, allure=allure)
        runner.run(selected)

        print("\n" + runner.summary_line())
        runner.print_failures()
        runner.print_blocked()

        md_path = runner.write_report(
            directory=args.report_dir, tag=(args.tag[0] if args.tag else None))
        print(f"\n报告：{md_path}")

        if allure is not None:
            index = generate_report(
                ALLURE_RESULTS, ALLURE_REPORT,
                single_file=args.allure != "multi",
                name=f"管伊佳ERP UI 自动化 {time.strftime('%Y-%m-%d %H:%M')}")
            if index:
                print(f"Allure：{index}")
                if args.allure == "multi":
                    print("        查看：node tools/allure/node_modules/allure-commandline/bin/allure "
                          f"open {ALLURE_REPORT}")

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
