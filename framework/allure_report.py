"""Allure 报告：把自研执行器的结果写成 allure-results，再调 CLI 生成 HTML。

为什么不用 allure-pytest：
    本项目不是 pytest 工程（自研注册表 + 顺序执行 + 每用例数据回收），
    所以直接用 allure-python-commons 的底层 lifecycle API 拼 TestResult，
    生成环节交给随项目安装的 allure-commandline（tools/allure）。

结果口径映射（与用例表保持一致）：
    通过 → passed      失败 → failed
    阻塞 → skipped     异常 → broken

除了用例本身，还会：
1. 把每条用例拆成「登录态检查 / 执行步骤 / 页面复位 / 数据回收」几段；
2. 执行步骤里自动记录页面动作（打开页面、填表、保存…），见 instrument()；
3. 失败时附全页截图；
4. 把用例里 ctx.note() 的观察结论（偏差 / 缺陷候选）作为附件带上。
"""

from __future__ import annotations

import functools
import hashlib
import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from allure_commons._core import plugin_manager
from allure_commons.lifecycle import AllureLifecycle
from allure_commons.logger import AllureFileLogger
from allure_commons.model2 import Label, Status, StatusDetails
from allure_commons.types import AttachmentType, LabelType, Severity
from allure_commons.utils import now, uuid4

from framework import registry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLURE_CLI = PROJECT_ROOT / "tools" / "allure" / "node_modules" / "allure-commandline" / "bin" / "allure"

# 用例表口径 → Allure 状态
STATUS_MAP = {
    registry.PASS: Status.PASSED,
    registry.FAIL: Status.FAILED,
    registry.BLOCKED: Status.SKIPPED,
    registry.ERROR: Status.BROKEN,
}

SEVERITY_MAP = {
    "高": Severity.CRITICAL,
    "中": Severity.NORMAL,
    "低": Severity.MINOR,
    "最高": Severity.BLOCKER,
}

# 用例编号前缀 → (epic, feature)。用例表里两个模块都归在「商品管理」下
MODULE_MAP = {
    "TC-UNIT": ("商品管理", "多单位"),
    "TC-MAT": ("商品管理", "商品信息"),
}

MAX_STEP_DEPTH = 3  # 步骤最多嵌套三层，更深的不记，避免报告刷屏

_ACTIVE = None  # 当前生效的 writer；页面对象包装器从这里取


def writer():
    """返回当前生效的 AllureWriter（未启用时是空对象，所有方法都是空操作）。"""
    return _ACTIVE or _NullWriter()


# ---------------------------------------------------------------- 空对象
class _NullWriter:
    """未启用 Allure 时的占位，保证调用方不用写 if。"""

    enabled = False
    depth = 0

    @contextmanager
    def step(self, name):
        yield None

    @contextmanager
    def test(self, case):
        yield self

    def attach_text(self, name, body):
        return None

    def attach_screenshot(self, page=None, name="失败截图"):
        return None

    def finish(self, result):
        return None


# ---------------------------------------------------------------- 录制
class AllureWriter:
    """一条用例 = 一个 Allure test result。"""

    enabled = True

    def __init__(self, results_dir, run_meta=None, clean=False):
        self.results_dir = Path(results_dir)
        if clean and self.results_dir.exists():
            shutil.rmtree(self.results_dir, ignore_errors=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self._lifecycle = AllureLifecycle()
        plugin_manager.register(AllureFileLogger(str(self.results_dir)))
        self.test_uuid = None
        self.depth = 0
        self._run_meta = run_meta or {}
        self._write_environment()

    # ---------- 环境信息（报告首页 Overview 会展示） ----------
    def _write_environment(self):
        """allure 用 Java Properties 读这个文件，中文会乱码，所以只写 ASCII。"""
        meta = self._run_meta
        lines = [
            f"System={meta.get('system', 'GuanYiJia ERP')}",
            f"Base.URL={meta.get('base_url', '')}",
            f"Browser={meta.get('browser', 'MyTest (CDP 9231)')}",
            f"Python={sys.version.split()[0]}",
            f"Data.Prefix={meta.get('data_prefix', '')}",
            f"Scope={meta.get('scope', 'all cases')}",
            f"Run.At={time.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        path = self.results_dir / "environment.properties"
        path.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")

    # ---------- 用例开闭 ----------
    @contextmanager
    def test(self, case):
        global _ACTIVE
        previous = _ACTIVE
        _ACTIVE = self
        self.depth = 0
        self.test_uuid = uuid4()
        test_uuid = self.test_uuid
        with self._lifecycle.schedule_test_case(uuid=test_uuid) as result:
            self._fill_result(result, case)
            try:
                yield self
            finally:
                _ACTIVE = previous
                self.depth = 0
                # 兜底：调用方没走 finish 也要落盘，否则这条用例在报告里凭空消失
                if test_uuid in self._lifecycle._items:
                    self._lifecycle.write_test_case(uuid=test_uuid)
                self.test_uuid = None

    def _fill_result(self, result, case):
        result.uuid = self.test_uuid
        result.name = f"{case.cid} {case.title}"
        result.fullName = f"{case.cid}.{case.title}"
        result.stage = "finished"
        result.start = now()
        result.status = Status.UNKNOWN
        result.historyId = hashlib.md5(case.cid.encode("utf-8")).hexdigest()
        result.testCaseId = result.historyId
        result.labels = self._labels(case)
        # 用例函数的 docstring 就是这条用例在测什么，放进详情页当说明
        doc = (getattr(case.func, "__doc__", "") or "").strip()
        if doc:
            result.description = doc.split("\n\n")[0]

    def _labels(self, case):
        epic, feature = MODULE_MAP.get(case.cid.rsplit("-", 1)[0], ("商品管理", "其他"))
        labels = [
            Label(LabelType.EPIC, epic),
            Label(LabelType.FEATURE, feature),
            Label(LabelType.STORY, case.tag or "未分类"),
            Label(LabelType.SUITE, feature),
            Label(LabelType.SUB_SUITE, case.tag or "未分类"),
            Label(LabelType.FRAMEWORK, "自研 Playwright 用例框架"),
            Label(LabelType.LANGUAGE, "python"),
            Label(LabelType.TAG, case.cid),
        ]
        severity = SEVERITY_MAP.get(case.priority)
        if severity is not None:
            labels.append(Label(LabelType.SEVERITY, severity.value))
        return labels

    # ---------- 步骤 ----------
    @contextmanager
    def step(self, name):
        if self.test_uuid is None or self.depth >= MAX_STEP_DEPTH:
            yield None
            return
        step_uuid = uuid4()
        self.depth += 1
        try:
            # 不传 parent_uuid：lifecycle 默认挂到「最后一个未关闭的可执行项」上，天然支持嵌套
            with self._lifecycle.start_step(uuid=step_uuid) as step:
                step.name = str(name)[:300]
                try:
                    yield step
                    step.status = Status.PASSED
                except BaseException as exc:
                    step.status = Status.FAILED if isinstance(exc, AssertionError) else Status.BROKEN
                    step.statusDetails = StatusDetails(message=_short(exc))
                    raise
                finally:
                    self._lifecycle.stop_step(step_uuid)
        finally:
            self.depth -= 1

    # ---------- 附件 ----------
    def attach_text(self, name, body):
        if self.test_uuid is None or not body:
            return None
        try:
            self._lifecycle.attach_data(
                self.test_uuid, str(body), name=name,
                attachment_type=AttachmentType.TEXT, extension="txt")
        except Exception:  # noqa: BLE001 - 附件失败不能影响用例结果
            pass
        return None

    def attach_screenshot(self, page=None, name="失败截图"):
        """失败时抓全页 PNG；抓不到就算了，绝不因此改变用例结果。"""
        if page is None or self.test_uuid is None:
            return None
        path = self.results_dir / f"shot_{uuid4()[:8]}.png"
        try:
            page.screenshot(path=str(path), full_page=True, timeout=15000)
            self._lifecycle.attach_file(
                self.test_uuid, str(path), name=name, attachment_type=AttachmentType.PNG)
        except Exception:  # noqa: BLE001
            try:
                path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
        return None

    # ---------- 收尾 ----------
    def finish(self, result):
        """把执行层结果写进 Allure：状态、耗时、错误详情、观察记录。"""
        if self.test_uuid is None:
            return None
        test_uuid = self.test_uuid
        try:
            with self._lifecycle.update_test_case(uuid=test_uuid) as test:
                if test is None:
                    return None
                test.status = STATUS_MAP.get(result.status, Status.UNKNOWN)
                # stop 用真实墙钟时间：收尾步骤（复位/回收）也算在用例时长里，步骤不会超出用例区间
                test.stop = now()
                if result.detail:
                    test.statusDetails = StatusDetails(
                        message=_short(result.detail),
                        trace=(f"用例：{result.cid} {result.title}\n"
                               f"结果：{result.status}\n详情：{result.detail}"))
            for note in result.notes or []:
                self.attach_text("观察记录", note)
            self._lifecycle.write_test_case(uuid=test_uuid)
        except Exception:  # noqa: BLE001 - 报告写入失败不能影响执行
            pass
        return None


def _short(exc, limit=2000):
    text = str(exc) or type(exc).__name__
    return text if len(text) <= limit else text[:limit] + "…"


# ---------------------------------------------------------------- 页面动作 → 步骤
# 只记「有业务含义的动作」；纯读接口（row_count / toasts / form_state …）不记，避免噪声
ACTION_METHODS = {
    # BasePage
    "click_button", "goto", "fill", "wait_toast", "cancel_modal", "click_confirm", "close_overlays",
    # UnitPage
    "open", "search", "reset", "reset_search_only", "open_create_modal", "open_edit_modal",
    "fill_form", "click_save", "save_success", "save_blocked", "create", "update",
    "select_row", "select_rows", "select_all", "clear_selection", "click_toolbar",
    "batch_action", "set_status", "delete_selected", "wait_status", "delete",
    "open_delete_popconfirm", "click_popconfirm_ok", "click_popconfirm_cancel",
    "goto_page", "next_page", "set_page_size", "wait_row", "wait_row_count",
    "cleanup_contains", "cleanup_names", "cleanup_prefix",
    # ProductPage
    "search_spec", "expand_query", "open_copy_modal", "fill_name", "fill_unit", "fill_basic",
    "cancel", "enable_multi_unit", "disable_multi_unit", "multi_unit_select", "switch_tab",
}


def instrument(*classes):
    """给页面对象的动作方法套一层「记步骤」，行为完全透明（返回值/异常原样透传）。"""
    for cls in classes:
        for name, attr in list(vars(cls).items()):
            if name not in ACTION_METHODS or not callable(attr) or isinstance(attr, type):
                continue
            if getattr(attr, "_allure_wrapped", False):
                continue
            setattr(cls, name, _wrap(attr, name))


def _wrap(func, name):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        active = _ACTIVE
        if active is None or active.test_uuid is None or active.depth >= MAX_STEP_DEPTH:
            return func(self, *args, **kwargs)
        with active.step(f"{name}{_args(args, kwargs)}"):
            return func(self, *args, **kwargs)

    wrapper._allure_wrapped = True
    return wrapper


def _args(args, kwargs, limit=90):
    """拼一个简短签名，报告里一眼能看出「对哪个数据做了什么」。"""
    parts = [repr(a) for a in args[:2]]
    if len(args) > 2:
        parts.append("…")
    for key, value in list(kwargs.items())[:2]:
        parts.append(f"{key}={value!r}")
    text = ", ".join(parts)
    return f"({text[:limit]})" if text else "()"


# ---------------------------------------------------------------- 生成 HTML
def generate_report(results_dir, report_dir, single_file=True, name=None, log=print):
    """调 allure CLI 出报告；成功返回 index.html 路径，失败返回 None。"""
    results_dir = Path(results_dir)
    if not any(results_dir.glob("*-result.json")):
        log("[allure] 没有结果文件，跳过生成")
        return None

    if not ALLURE_CLI.exists():
        log(f"[allure] 未找到 CLI：{ALLURE_CLI}")
        log("         安装：npm install --prefix tools/allure allure-commandline")
        return None

    node = shutil.which("node")
    if node:
        args = [node, str(ALLURE_CLI)]
    elif os.name == "nt":
        args = [str(ALLURE_CLI.parent.parent / "dist" / "bin" / "allure.bat")]
    else:
        args = [str(ALLURE_CLI)]

    report_dir = Path(report_dir)
    args += ["generate", str(results_dir), "-o", str(report_dir), "--clean"]
    if single_file:
        args.append("--single-file")
    if name:
        args += ["--report-name", name]

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=600,
                              cwd=str(PROJECT_ROOT))
    except Exception as exc:  # noqa: BLE001
        log(f"[allure] 生成失败：{type(exc).__name__}: {exc}")
        return None

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        log(f"[allure] 生成失败（exit {proc.returncode}）：{detail[-1] if detail else ''}")
        return None

    index = report_dir / "index.html"
    return index if index.exists() else None
