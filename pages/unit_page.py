"""商品管理 - 多单位页面对象（Page Object）。

页面实测结构（Ant Design）：
    表头：# | 操作 | 单位名称 | 基本单位 | 副单位 | 副单位2 | 副单位3 | 状态
    行内操作：「编辑」「删除」
    新增/编辑：居中弹窗 .ant-modal
        字段 #basicUnit（基本单位，必填）、#otherUnit + #ratio、
             #otherUnitTwo + #ratioTwo、#otherUnitThree + #ratioThree
    删除确认：.ant-popover 气泡，文案「确定删除吗?」+「取 消」「确 定」
    单位名称由系统自动拼接：基本单位/(副单位=比例基本单位)

定位一律基于实测到的 id / placeholder / 可见文案；行匹配按「基本单位」列做
**整格精确比较**，避免「测试瓶」误命中「测试瓶改」这类子串歧义。
"""

import re
import time

from browser import SessionExpiredError, ensure_login, expired_modal_text, session_alive
from config import ACTION_DELAY_MS, BASE_URL

# 表格列索引（td 从 1 开始，与表头顺序一一对应）
COL_NAME = 4    # 单位名称
COL_BASIC = 5   # 基本单位
COL_OTHER = 6   # 副单位（形如「箱=10瓶」）
COL_STATUS = 9  # 状态


def _btn(text):
    """匹配 Ant Design 按钮文案——它会把两个汉字拆成「查 询」。"""
    return re.compile(r"\s*".join(text))


class UnitPage:
    PATH = "/system/unit"
    SEARCH_INPUT = 'input[placeholder="请输入单位名称查询"]'
    MODAL = ".ant-modal:visible"
    POPOVER = ".ant-popover:visible"
    ROWS = ".ant-table-tbody tr.ant-table-row"

    # (单位输入框, 比例输入框)；第 1 组是基本单位，没有比例
    UNIT_FIELDS = (
        ("#basicUnit", None),
        ("#otherUnit", "#ratio"),
        ("#otherUnitTwo", "#ratioTwo"),
        ("#otherUnitThree", "#ratioThree"),
    )

    def __init__(self, page):
        self.page = page
        # 每个动作之间的间隔，避免操作快过页面渲染 / 服务端校验
        self.action_delay = ACTION_DELAY_MS

    def _pause(self):
        if self.action_delay:
            self.page.wait_for_timeout(self.action_delay)

    # ================= 导航 =================
    def open(self):
        """确保登录态可用、停在多单位页面，且表格首屏数据已经加载完。"""
        recovered = ensure_login(self.page)
        if recovered:
            # 登录可能是在 SPA 路由跳转中完成的（页面内存仍是旧 token），必须重载
            self.page.reload(wait_until="domcontentloaded")
            self.page.wait_for_timeout(1000)
            ensure_login(self.page)
        if not self.page.url.rstrip("/").endswith(self.PATH):
            self.page.goto(BASE_URL + self.PATH, wait_until="domcontentloaded")
            self.page.wait_for_timeout(500)
            ensure_login(self.page)  # 未登录时会被重定向回登录页
        try:
            self.page.locator("button", has_text=_btn("新增")).first.wait_for(timeout=8000)
        except Exception:
            ensure_login(self.page)  # 若是登录态问题，这里会抛出可读错误
            raise
        # 表格数据是接口异步拉取的：只等按钮会导致清理逻辑读到空表
        self._wait_table_loaded()
        ensure_login(self.page)  # 首屏接口返回后才可能暴露会话失效
        return self

    def _wait_table_loaded(self, timeout=10.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.page.locator(".ant-spin-spinning").count() == 0:
                break
            self.page.wait_for_timeout(200)
        # 再给首屏渲染留一点余量，避免读到「暂无数据」的中间态
        self.page.wait_for_timeout(600)

    # ================= 查询 =================
    def rows(self):
        return self.page.locator(self.ROWS)

    def basic_units(self):
        """当前表格里所有「基本单位」列的值。"""
        return [text.strip() for text in self.rows().locator(f"td:nth-child({COL_BASIC})").all_inner_texts()]

    def row_count(self):
        return len(self.basic_units())

    def has_row(self, basic_unit):
        return basic_unit in self.basic_units()

    def row(self, basic_unit):
        """按基本单位取到那一行的 locator。"""
        basics = self.basic_units()
        assert basic_unit in basics, f"表格中找不到基本单位「{basic_unit}」，当前：{basics}"
        return self.rows().nth(basics.index(basic_unit))

    def read_row(self, basic_unit):
        """读出该行的关键列，用于断言。"""
        cells = [text.strip() for text in self.row(basic_unit).locator("td").all_inner_texts()]
        return {
            "name": cells[COL_NAME - 1],
            "basic": cells[COL_BASIC - 1],
            "other": cells[COL_OTHER - 1],
            "status": cells[COL_STATUS - 1],
        }

    def search(self, keyword):
        """按单位名称模糊查询。"""
        self.page.fill(self.SEARCH_INPUT, keyword)
        self._click_button("查询")
        self.page.wait_for_timeout(500)
        return self

    def reset(self):
        """清空查询条件，回到全量列表。"""
        self.page.fill(self.SEARCH_INPUT, "")
        self._click_button("重置")
        self.page.wait_for_timeout(500)
        return self

    # ================= 新增 =================
    def create(self, basic_unit, others=()):
        """新增一条多单位记录。

        others: [(副单位, 比例), ...]，最多 3 组，例如 [("箱", 10)]。
        """
        ensure_login(self.page)
        self._click_button("新增")
        modal = self.page.locator(self.MODAL)
        modal.wait_for(state="visible")
        self._fill_form(basic_unit, others)
        self._save_and_wait(modal)
        self.wait_row(basic_unit, present=True)
        return self

    # ================= 修改 =================
    def update(self, current_basic, new_basic=None, others=()):
        """编辑一条记录。

        others 为该记录的**完整**目标副单位列表（省略即清空所有副单位）。
        """
        ensure_login(self.page)
        row = self.row(current_basic)
        row.locator("a", has_text="编辑").click()

        modal = self.page.locator(self.MODAL)
        modal.wait_for(state="visible")
        # 断言弹窗回填的正是目标行，防止点到别的记录
        assert self.page.input_value("#basicUnit") == current_basic, "编辑弹窗回填的基本单位与目标行不一致"

        target = new_basic or current_basic
        self._fill_form(target, others)
        self._save_and_wait(modal)

        self.wait_row(target, present=True)
        if target != current_basic:
            self.wait_row(current_basic, present=False)
        return self

    # ================= 删除 =================
    def delete(self, basic_unit):
        """删除单行：行内「删除」→ 气泡里「确 定」。"""
        ensure_login(self.page)
        row = self.row(basic_unit)
        row.locator("a", has_text="删除").click()

        popover = self.page.locator(self.POPOVER)
        popover.wait_for(state="visible")
        text = popover.inner_text()
        assert "确定删除吗" in text, f"删除确认气泡文案不符：{text!r}"
        popover.locator("button", has_text=_btn("确定")).first.click()

        try:
            self.wait_row(basic_unit, present=False)
        except AssertionError:
            self._raise_if_session_dead()
            raise
        return self

    def _raise_if_session_dead(self):
        """接口静默失败时（例如返回 loginOut 但前端不弹框）补一次服务端探活。"""
        probe = session_alive(self.page)
        if not probe.get("ok") and probe.get("reason") in ("loginOut", "no-token"):
            raise SessionExpiredError(
                "操作失败：服务端会话已失效（loginOut）。请在 MyTest 浏览器重新登录后重跑脚本。"
            )

    # ================= 内部工具 =================
    def _save_and_wait(self, modal):
        """点保存并等弹窗关闭；失败时区分「登录过期」与「表单校验不过」。"""
        modal.locator("button.ant-btn-primary").first.click()
        self._pause()
        try:
            modal.wait_for(state="hidden", timeout=8000)
        except Exception as exc:
            expired = expired_modal_text(self.page)
            if expired:
                first_line = expired.splitlines()[0].strip()
                raise SessionExpiredError(f"保存失败：{first_line}。请在 MyTest 浏览器重新登录后重跑脚本。") from exc
            self._raise_if_session_dead()
            hints = self.page.locator(
                ".ant-form-explain, .ant-message-notice, .ant-notification-notice").all_inner_texts()
            raise AssertionError(
                f"保存后弹窗未关闭，页面提示：{[h.strip() for h in hints if h.strip()]}") from exc

    def _click_button(self, text):
        self.page.locator("button").filter(has_text=_btn(text)).first.click()
        self._pause()

    def _fill_form(self, basic_unit, others):
        self.page.fill("#basicUnit", basic_unit)
        self._pause()
        for index, (unit_sel, ratio_sel) in enumerate(self.UNIT_FIELDS[1:]):
            if index < len(others):
                name, ratio = others[index]
                self.page.fill(unit_sel, str(name))
                self.page.fill(ratio_sel, str(ratio))
            else:
                # 编辑场景要清掉上一轮的残留值，避免把旧副单位一起提交
                self.page.fill(unit_sel, "")
                self.page.fill(ratio_sel, "")
            self._pause()

    def wait_row(self, basic_unit, present=True, timeout=10.0):
        """轮询等待某行出现 / 消失（表格刷新是异步的）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.has_row(basic_unit) == present:
                return True
            self.page.wait_for_timeout(250)
        state = "出现" if present else "消失"
        raise AssertionError(f"等待「{basic_unit}」{state}超时（{timeout}s）")

    def cleanup_prefix(self, prefixes, limit=50):
        """清理历史测试数据：删除基本单位以给定前缀开头的所有行。

        prefixes 可以是单个字符串，也可以是前缀元组（脚本会造多种角色名）。
        """
        if isinstance(prefixes, str):
            prefixes = (prefixes,)
        self.reset()
        removed = 0
        while removed < limit:
            target = next((b for b in self.basic_units() if b.startswith(prefixes)), None)
            if target is None:
                break
            self.delete(target)
            removed += 1
        return removed
