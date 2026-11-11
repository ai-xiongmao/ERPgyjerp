"""执行器：按用例编号顺序跑脚本、收尾、出报告、可选写回 Excel。

用法见 run_cases.py。这里只做四件事：
1. 跑之前确保登录态（掉登录 → 该条记「阻塞」，不污染后续用例）；
2. 跑完必做收尾（关浮层 / 清勾选 / 清查询 / 删掉本次造的数据）；
3. 把异常翻译成用例表口径：断言不符=失败、环境不具备=阻塞、脚本报错=异常；
4. 输出 Markdown 报告（Allure 由 allure_report 单独生成），可用 --update-xlsx 回填「执行结果」列。
"""

import time
from dataclasses import dataclass, field
from pathlib import Path

from framework import registry
from framework.allure_report import writer as allure_writer
from framework.asserts import CaseBlocked, CaseFailed
from framework.browser import SessionExpiredError, ensure_login

REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"

# 写回 Excel「执行结果」时的口径映射
XLSX_STATUS = {
    registry.PASS: "通过",
    registry.FAIL: "失败",
    registry.BLOCKED: "阻塞",
    registry.ERROR: "阻塞",   # 脚本/环境异常无法定性为缺陷，按阻塞处理，细节看报告
}


@dataclass
class Result:
    cid: str
    title: str
    tag: str
    priority: str
    status: str
    seconds: float = 0.0
    detail: str = ""
    notes: list = field(default_factory=list)


class Runner:
    def __init__(self, ctx, relogin_wait=None, cleanup=True, log=print, allure=None, layer="ui"):
        self.ctx = ctx
        self.relogin_wait = relogin_wait
        self.cleanup = cleanup
        self.log = log
        self.layer = layer
        self.results = []
        # 未启用 Allure 时是空对象，下面所有 allure.* 调用都变成空操作
        self.allure = allure if allure is not None else allure_writer()

    # ---------------- 单条 ----------------
    def run_one(self, case):
        blocked = case.blocked_for(self.layer)
        if blocked:
            self.log(f"        跳过：{blocked}")
            result = Result(case.cid, case.title, case.tag, case.priority,
                            registry.BLOCKED, 0.0, blocked)
            with self.allure.test(case):
                self.allure.finish(result)
            return result

        func = case.func_for(self.layer)
        if func is None:
            detail = "该用例没有接口版实现（仅 UI）" if self.layer == "api" else "该用例没有 UI 版实现"
            self.log(f"        跳过：{detail}")
            return Result(case.cid, case.title, case.tag, case.priority,
                          registry.NOT_COVERED, 0.0, detail)

        self.ctx.notes = []
        started = time.time()
        status, detail = registry.PASS, ""
        with self.allure.test(case):
            try:
                with self.allure.step("前置：登录态检查"):
                    self._ensure_auth()
                with self.allure.step(f"执行用例：{case.title}"):
                    func(self.ctx)
            except SessionExpiredError as exc:
                status, detail = registry.BLOCKED, f"登录已失效：{exc}"
            except CaseBlocked as exc:
                status, detail = registry.BLOCKED, f"前置不具备：{exc}"
            except CaseFailed as exc:
                status, detail = registry.FAIL, str(exc)
                self._screenshot(case)
            except AssertionError as exc:
                status, detail = registry.FAIL, str(exc) or "断言失败"
                self._screenshot(case)
            except Exception as exc:  # noqa: BLE001 - 顶层兜底，转成报告里可读的一行
                status, detail = registry.ERROR, f"{type(exc).__name__}: {exc}".strip()
                self._screenshot(case)
            finally:
                elapsed = time.time() - started
                with self.allure.step("收尾：页面复位"):
                    try:
                        self.ctx.reset()
                    except SessionExpiredError:
                        status = registry.BLOCKED if status == registry.PASS else status
                        detail = detail or "收尾时发现登录已失效"
                    except Exception as exc:  # noqa: BLE001
                        self.log(f"        收尾告警：{type(exc).__name__}: {exc}")
                if self.cleanup and status != registry.BLOCKED:
                    with self.allure.step("收尾：数据回收"):
                        try:
                            removed = self.ctx.cleanup()
                            if removed:
                                self.log(f"        已回收 {removed} 条测试数据")
                        except Exception as exc:  # noqa: BLE001
                            self.log(f"        回收告警：{type(exc).__name__}: {exc}")
            result = Result(case.cid, case.title, case.tag, case.priority,
                            status, elapsed, detail, list(self.ctx.notes))
            self.allure.finish(result)
        return result

    def _ensure_auth(self):
        """按层做前置：UI 看页面登录态，接口看 token 能不能用。"""
        if self.layer == "api":
            client = getattr(self.ctx, "client", None)
            if client is None:
                raise CaseBlocked("接口层没有 ApiClient，无法发起请求")
            try:
                client.token
            except Exception as exc:  # noqa: BLE001
                raise CaseBlocked(f"接口认证不可用：{exc}") from exc
            return
        ensure_login(self.ctx.page, wait_seconds=self.relogin_wait, log=self.log)

    def _screenshot(self, case):
        """失败瞬间立刻截图（复位之前），PS：抓不到不影响用例结果。"""
        if self.layer != "ui":
            return
        try:
            self.allure.attach_screenshot(self.ctx.page, f"{case.cid} 失败截图")
        except Exception:  # noqa: BLE001
            pass

    # ---------------- 全部 ----------------
    def run(self, cases):
        total = len(cases)
        started = time.time()
        self.log(f"运行前缀 {self.ctx.data.token}，共 {total} 条用例\n")
        for index, case in enumerate(cases, start=1):
            self.log(f"[{index:>2}/{total}] {case.cid} {case.title}")
            result = self.run_one(case)
            self.results.append(result)
            mark = {registry.PASS: "OK  ", registry.FAIL: "FAIL", registry.BLOCKED: "SKIP",
                    registry.ERROR: "ERR ", registry.NOT_COVERED: "N/A "}.get(result.status, "?   ")
            self.log(f"        {mark} {result.status}（{result.seconds:.1f}s）"
                     + (f"｜{result.detail}" if result.detail else ""))
            self.log("")
        self.elapsed = time.time() - started
        return self.results

    # ---------------- 汇总 ----------------
    def counts(self):
        counts = {registry.PASS: 0, registry.FAIL: 0, registry.BLOCKED: 0,
                  registry.ERROR: 0, registry.NOT_COVERED: 0}
        for item in self.results:
            counts[item.status] = counts.get(item.status, 0) + 1
        return counts

    def summary_line(self):
        counts = self.counts()
        line = (f"通过 {counts[registry.PASS]} / 失败 {counts[registry.FAIL]} / "
                f"阻塞 {counts[registry.BLOCKED]} / 异常 {counts[registry.ERROR]}")
        if counts[registry.NOT_COVERED]:
            line += f" / 未覆盖 {counts[registry.NOT_COVERED]}"
        return line + f"　总计 {len(self.results)}　用时 {getattr(self, 'elapsed', 0):.0f}s"

    def print_failures(self):
        bad = [r for r in self.results if r.status in (registry.FAIL, registry.ERROR)]
        if not bad:
            return
        self.log("\n需要关注：")
        for r in bad:
            self.log(f"  {r.cid} {r.title}\n      {r.status}：{r.detail}")

    def print_blocked(self):
        blocked = [r for r in self.results if r.status == registry.BLOCKED]
        if not blocked:
            return
        self.log("\n阻塞/人工用例：")
        for r in blocked:
            self.log(f"  {r.cid} {r.title}\n      {r.detail}")

    # ---------------- 报告 ----------------
    def write_report(self, directory=REPORT_DIR, tag=None):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        stem = f"run_{stamp}" + (f"_{tag}" if tag else "")
        md_path = directory / f"{stem}.md"

        layer_name = "接口" if self.layer == "api" else "UI"
        lines = [
            f"# 管伊佳ERP {layer_name} 自动化执行报告",
            "",
            f"- 运行时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 执行层：{layer_name}（另有一层实现时，请分别执行）",
            f"- 数据前缀：{self.ctx.data.token}",
            f"- 汇总：{self.summary_line()}",
            "",
            "| 用例编号 | 标签 | 用例标题 | 结果 | 耗时(s) | 说明 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in self.results:
            detail = (r.detail or "").replace("|", "\\|").replace("\n", " ")
            if r.notes:
                detail = (detail + "；" if detail else "") + "；".join(r.notes)
            lines.append(f"| {r.cid} | {r.tag} | {r.title} | {r.status} | "
                         f"{r.seconds:.1f} | {detail} |")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return md_path

    # ---------------- 写回 Excel ----------------
    def update_xlsx(self, path):
        """把结果写回用例表「执行结果」列（只动这一列，备注不动）。"""
        import shutil

        import openpyxl

        path = Path(path)
        backup = path.with_name(f"{path.stem}.bak_{time.strftime('%Y%m%d_%H%M%S')}{path.suffix}")
        shutil.copy2(path, backup)

        workbook = openpyxl.load_workbook(path)
        sheet = workbook["测试用例"] if "测试用例" in workbook.sheetnames else workbook.worksheets[0]
        header = [cell.value for cell in sheet[1]]
        col_id = header.index("用例编号") + 1
        col_result = header.index("执行结果") + 1

        by_id = {r.cid: r for r in self.results}
        written = 0
        for row in range(2, sheet.max_row + 1):
            cid = sheet.cell(row, col_id).value
            result = by_id.get((cid or "").strip())
            if not result:
                continue
            # 「未覆盖」表示本层没写这条，不该覆盖用例表里已有的执行结果
            if result.status == registry.NOT_COVERED:
                continue
            sheet.cell(row, col_result).value = XLSX_STATUS.get(result.status, "未执行")
            written += 1
        workbook.save(path)
        return backup, written
