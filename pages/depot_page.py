"""基础资料 - 仓库信息页面对象（Page Object）。

页面实测结构（Ant Design，2026-11-02 采集）：
    地址 /system/depot，标题「仓库信息 · 管伊佳ERP」
    查询区：仓库名称 input[placeholder="请输入仓库名称查询"]
            + 备注 input[placeholder="请输入备注查询"] + 「查 询」「重 置」
    工具栏：「新增」「删除」「启用」「禁用」（无空格）
    表头：# | 操作 | 仓库名称 | 仓库地址 | 仓储费 | 搬运费 | 排序 | 负责人 | 备注 | 状态 | 是否默认
          （最左侧还有一列勾选框；操作列含「编辑」「设为默认」两个链接）
    新增/编辑弹窗：.ant-modal，标题「新增」/「编辑」
        字段 #name（必填，占位/校验「请输入仓库名称!」）、#address（仓库地址）、
             #warehousing（仓储费，单位「元/天/KG」）、#truckage（搬运费，单位「元」）、
             #sort（排序）、#remark（备注）、负责人下拉（账号管理数据）
        按钮「取 消」「保 存」
    批量操作：勾选后点删除 → .ant-modal-confirm（标题「确认删除」/「是否删除选中数据?」）
             勾选后点启用/禁用 → .ant-modal-confirm（标题「确认操作」/「是否操作选中数据?」）
    设为默认：行内「设为默认」链接 → .ant-popover「确定设为默认吗?」（取 消/确 定）
    未勾选点工具栏 → toast「请选择一条记录！」

已知偏差（在用例里记 note，不判红）：
    - 空表单保存校验文案为「请输入仓库名称! 未知异常」（多了「未知异常」后缀）；
    - 仓储费/搬运费无前端数字校验，负数/小数可保存，非数字导致后端静默失败；
    - 排序字段自由文本无校验。

定位一律基于实测到的 id / placeholder / 可见文案；行匹配按「仓库名称」列整格比较。
"""

import time

from pages.base_page import CONFIRM, POPOVER, BasePage, spaced

# 表格列索引（td 从 1 开始；第 1 列勾选框，第 2 列 # 序号，第 3 列操作）
# 实测表头：# | 操作 | 仓库名称 | 仓库地址 | 仓储费 | 搬运费 | 负责人 | 备注 | 排序 | 状态 | 是否默认
COL_OP = 3        # 操作（编辑/设为默认）
COL_NAME = 4      # 仓库名称
COL_ADDRESS = 5   # 仓库地址
COL_WAREHOUSING = 6  # 仓储费
COL_TRUCKAGE = 7  # 搬运费
COL_MANAGER = 8   # 负责人
COL_REMARK = 9    # 备注
COL_SORT = 10     # 排序
COL_STATUS = 11   # 状态
COL_DEFAULT = 12  # 是否默认

# 保存后若出现这些字样，说明接口/校验拦下了这次写入（弹窗仍会关闭，不能只看弹窗）
SAVE_FAILURE_HINTS = ("异常", "失败", "错误", "不能为空", "已存在", "重复", "只能为数字")

ROWS_JS = """() => Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
    .map(tr => {
        const cells = Array.from(tr.children).map(td => (td.innerText || '').trim());
        return {
            seq: cells[1], ops: cells[2], name: cells[3], address: cells[4],
            warehousing: cells[5], truckage: cells[6], manager: cells[7],
            remark: cells[8], sort: cells[9], status: cells[10], isDefault: cells[11],
        };
    })"""

PAGINATION_JS = """() => {
    const rows = document.querySelectorAll('.ant-table-tbody tr.ant-table-row').length;
    const pager = document.querySelector('.ant-pagination');
    if (!pager) return {exists: false, total: rows, pageSize: null, current: 1,
                        pages: 1, range: '', pageNumbers: []};
    const totalText = ((pager.querySelector('.ant-pagination-total-text') || {}).innerText || '').trim();
    const matched = totalText.match(/共\\s*(\\d+)\\s*条/);
    const numbers = Array.from(pager.querySelectorAll('.ant-pagination-item'))
        .map(li => parseInt(li.innerText.trim(), 10)).filter(n => !isNaN(n));
    const active = pager.querySelector('.ant-pagination-item-active');
    const sizeValue = pager.querySelector('.ant-select-selection-selected-value');
    return {
        exists: true,
        totalText: totalText,
        total: matched ? parseInt(matched[1], 10) : rows,
        range: totalText,
        pageSize: sizeValue ? parseInt(sizeValue.innerText, 10) : null,
        current: active ? parseInt(active.innerText.trim(), 10) : 1,
        pages: numbers.length ? Math.max.apply(null, numbers) : 1,
        pageNumbers: numbers,
    };
}"""

SELECTED_JS = """() => ({
    rows: document.querySelectorAll('.ant-table-tbody .ant-checkbox-checked').length,
    header: (() => {
        const box = document.querySelector('.ant-table-thead .ant-checkbox');
        if (!box) return 'none';
        if (box.className.indexOf('ant-checkbox-checked') >= 0) return 'checked';
        if (box.className.indexOf('ant-checkbox-indeterminate') >= 0) return 'indeterminate';
        return 'none';
    })(),
})"""

FORM_JS = """() => {
    const modal = Array.from(document.querySelectorAll('.ant-modal'))
        .filter(m => m.offsetWidth || m.offsetHeight)
        .filter(m => m.className.indexOf('ant-modal-confirm') < 0).pop();
    if (!modal) return null;
    const value = id => {
        const el = modal.querySelector('#' + id);
        return el ? el.value : null;
    };
    const manager = modal.querySelector('.ant-select-selection-selected-value');
    return {
        title: ((modal.querySelector('.ant-modal-title') || {}).innerText || '').trim(),
        name: value('name'), address: value('address'),
        warehousing: value('warehousing'), truckage: value('truckage'),
        sort: value('sort'), remark: value('remark'),
        manager: manager ? (manager.innerText || '').trim() : '',
        required: Array.from(modal.querySelectorAll('.ant-form-item-label')).map(label => ({
            text: (label.innerText || '').trim(),
            star: !!label.querySelector('.ant-form-item-required'),
        })),
        bodyText: (modal.innerText || '').replace(/\\s+/g, ' ').trim(),
    };
}"""


class DepotPage(BasePage):
    PATH = "/system/depot"
    NAME_INPUT = 'input[placeholder="请输入仓库名称查询"]'
    REMARK_INPUT = 'input[placeholder="请输入备注查询"]'
    ROWS = ".ant-table-tbody tr.ant-table-row"
    EMPTY = ".ant-empty-description, .ant-empty"

    # ================= 导航 =================
    def open(self):
        from config import BASE_URL

        recovered = self.ensure_alive()
        if recovered:
            self.page.reload(wait_until="domcontentloaded")
            self.page.wait_for_timeout(1000)
            self.ensure_alive()
        if not (self.page.url or "").rstrip("/").endswith(self.PATH):
            self.goto(BASE_URL + self.PATH)
            self.ensure_alive()
        try:
            self.page.locator(self.BUTTON_SCOPE).first.wait_for(timeout=15000)
        except Exception:
            self.ensure_alive()
            raise
        self._wait_table_loaded()
        self.ensure_alive()
        return self

    def _wait_table_loaded(self, timeout=20.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            spinning = self.page.locator(".ant-spin-spinning").count()
            has_body = self.page.locator(".ant-table-tbody").count()
            if spinning == 0 and has_body:
                break
            self.page.wait_for_timeout(200)
        self.page.wait_for_timeout(400)

    # ================= 列表读取 =================
    def rows_data(self):
        return self._safe_evaluate(ROWS_JS, default=[]) or []

    def names(self):
        return [row["name"] for row in self.rows_data()]

    def row_count(self):
        return len(self.rows_data())

    def total_count(self):
        return self.pagination_info()["total"]

    def pagination_info(self):
        return self._safe_evaluate(PAGINATION_JS, default={
            "exists": False, "total": 0, "pageSize": None,
            "current": 1, "pages": 1, "range": "", "pageNumbers": []})

    def empty_text(self):
        locator = self.page.locator(self.EMPTY).first
        if not locator.count():
            return ""
        return (locator.inner_text() or "").strip()

    def has_row(self, name):
        return name in self.names()

    def count_row(self, name):
        return self.names().count(name)

    def row_index(self, name, nth=0):
        hits = [i for i, n in enumerate(self.names()) if n == name]
        assert len(hits) > nth, f"表格中找不到第 {nth + 1} 条仓库「{name}」，当前：{self.names()}"
        return hits[nth]

    def row_locator(self, name, nth=0):
        return self.page.locator(self.ROWS).nth(self.row_index(name, nth))

    def read_row(self, name, nth=0):
        row = self.rows_data()[self.row_index(name, nth)]
        return {key: row[key] for key in (
            "seq", "ops", "name", "address", "warehousing", "truckage",
            "manager", "remark", "sort", "status", "isDefault")}

    def statuses(self):
        return {row["name"]: row["status"] for row in self.rows_data()}

    def defaults(self):
        """返回 {仓库名: 是否默认('是'/'否')}。"""
        return {row["name"]: row["isDefault"] for row in self.rows_data()}

    def default_name(self):
        """当前默认仓库名（有且仅一个时返回，否则 None）。"""
        hits = [n for n, d in self.defaults().items() if d == "是"]
        return hits[0] if len(hits) == 1 else None

    # ================= 查询 =================
    def search(self, keyword):
        """按仓库名称模糊查询。"""
        self.ensure_alive()
        self.fill(self.NAME_INPUT, keyword)
        self.click_button("查询")
        self._wait_table_loaded()
        return self

    def search_remark(self, keyword):
        """按备注查询。"""
        self.ensure_alive()
        self.fill(self.REMARK_INPUT, keyword)
        self.click_button("查询")
        self._wait_table_loaded()
        return self

    def reset(self):
        """清空查询条件，回到全量列表第一页。"""
        if self.page.locator(self.NAME_INPUT).count():
            self.fill(self.NAME_INPUT, "")
        if self.page.locator(self.REMARK_INPUT).count():
            self.fill(self.REMARK_INPUT, "")
        self.click_button("重置")
        self._wait_table_loaded()
        return self

    # ================= 新增 / 编辑弹窗 =================
    def open_create_modal(self):
        self.ensure_alive()
        self.close_overlays()
        self.click_button("新增")
        self.modal().wait_for(state="visible", timeout=10000)
        self.pause()
        return self

    def open_edit_modal(self, name, nth=0):
        self.ensure_alive()
        self.close_overlays()
        self.row_locator(name, nth).locator("a", has_text="编辑").click()
        self.modal().wait_for(state="visible", timeout=10000)
        self.pause()
        return self

    def form_state(self):
        return self._safe_evaluate(FORM_JS)

    def fill_name(self, name):
        self.fill(self.modal().locator("#name"), name)
        return self

    def fill_form(self, name=None, address=None, warehousing=None,
                  truckage=None, sort=None, remark=None):
        """填仓库弹窗字段；None 表示该字段保持不动（用于编辑回显后局部修改）。"""
        modal = self.modal()
        if name is not None:
            self.fill(modal.locator("#name"), name)
        if address is not None:
            self.fill(modal.locator("#address"), address)
        if warehousing is not None:
            self.fill(modal.locator("#warehousing"), warehousing)
        if truckage is not None:
            self.fill(modal.locator("#truckage"), truckage)
        if sort is not None:
            self.fill(modal.locator("#sort"), sort)
        if remark is not None:
            self.fill(modal.locator("#remark"), remark)
        return self

    def click_save(self):
        self.modal().locator("button").filter(has_text=spaced("保存")).first.click()
        self.pause()
        return self

    def save_success(self):
        """点保存并等弹窗关闭；接口报错时弹窗也会关，必须再查失败 toast。"""
        modal = self.modal()
        self.drain_toasts(timeout=3000)
        self.click_save()
        try:
            modal.wait_for(state="hidden", timeout=12000)
        except Exception as exc:  # noqa: BLE001
            self._expired_or_raise("保存", exc)
            hints = self.toasts() + self.inline_errors()
            raise AssertionError(f"保存后弹窗未关闭，页面提示：{hints}") from exc
        self._wait_table_loaded()
        for message in self.toasts():
            if any(hint in message for hint in SAVE_FAILURE_HINTS):
                raise AssertionError(f"保存未成功，接口提示「{message}」")
        return self

    def save_blocked(self, expect=None):
        """点保存但预期被校验拦截：返回 {toast, inline, matched}。"""
        self.drain_toasts()
        self.click_save()
        matched = self.wait_message(expect) if expect else None
        return {"toast": self.toasts(), "inline": self.inline_errors(), "matched": matched}

    def create(self, name, address=None, warehousing=None, truckage=None,
               sort=None, remark=None):
        """新增一条仓库记录（最少只需 name）。"""
        self.open_create_modal()
        self.fill_form(name, address, warehousing, truckage, sort, remark)
        self.save_success()
        self.wait_row(name, present=True)
        return self

    def cancel(self):
        return self.cancel_modal()

    # ================= 负责人下拉 =================
    def manager_select(self):
        return self.modal().locator(".ant-select").first

    def open_manager_options(self):
        """点开负责人下拉，返回可见选项文案列表。"""
        self._click_manager_select()
        options = [t.strip() for t in self.page.locator(
            ".ant-select-dropdown:visible .ant-select-dropdown-menu-item").all_inner_texts()
            if t.strip()]
        return options

    def _click_manager_select(self):
        """点开负责人下拉（容忍关闭动画：点一次若没展开则再点一次）。"""
        select = self.manager_select()
        select.click()
        self.page.wait_for_timeout(700)
        # 若下拉没展开（可能被上一次的关闭动画吞掉这次点击），再点一次
        if not self.page.locator(".ant-select-dropdown:visible").count():
            select.click()
            self.page.wait_for_timeout(700)
        return self

    def choose_manager(self, text):
        """在负责人下拉里点选指定文案的选项。"""
        self._click_manager_select()
        option = self.page.locator(
            ".ant-select-dropdown:visible .ant-select-dropdown-menu-item").filter(
            has_text=text).first
        option.wait_for(state="visible", timeout=8000)
        option.click()
        self.pause()
        return self

    # ================= 勾选 =================
    def selection(self):
        return self._safe_evaluate(SELECTED_JS, default={"rows": 0, "header": "none"})

    def selected_count(self):
        return self.selection()["rows"]

    def header_state(self):
        return self.selection()["header"]

    def _wait_selected(self, expected, timeout=8.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.selected_count() == expected:
                return True
            self.page.wait_for_timeout(150)
        return False

    def select_row(self, name, nth=0):
        before = self.selected_count()
        self.row_locator(name, nth).locator(".ant-checkbox").click()
        self.pause(300)
        assert self._wait_selected(before + 1), (
            f"勾选「{name}」失败：勾选数仍为 {self.selected_count()}")
        return self

    def select_rows(self, names):
        for name in names:
            self.select_row(name)
        return self

    def select_all(self, checked=True, timeout=8.0):
        self.drain_toasts(timeout=3000)
        expected = self.row_count() if checked else 0
        for selector in (".ant-table-thead .ant-checkbox-input", ".ant-table-thead .ant-checkbox"):
            locator = self.page.locator(selector)
            if not locator.count():
                continue
            try:
                locator.first.click(force=True, timeout=5000)
            except Exception:  # noqa: BLE001
                continue
            self.pause(300)
            if self._wait_selected(expected, timeout=timeout / 2):
                return self
        raise AssertionError(
            f"{'全选' if checked else '取消全选'}失败：勾选数 {self.selected_count()}，期望 {expected}")

    def clear_selection(self, limit=60):
        for _ in range(limit):
            checked = self.page.locator(".ant-table-tbody .ant-checkbox-checked")
            if not checked.count():
                break
            try:
                checked.first.click()
            except Exception:  # noqa: BLE001
                self.close_overlays()
                try:
                    checked.first.click()
                except Exception:
                    break
            self.page.wait_for_timeout(120)
        return self

    # ================= 工具栏 / 批量操作 =================
    def click_toolbar(self, action):
        return self.click_button(action)

    def batch_action(self, action, expect_confirm=True):
        """工具栏操作（启用/禁用/删除）：返回确认框 (标题, 正文)。"""
        self.drain_toasts()
        self.click_toolbar(action)
        if not expect_confirm:
            return "", ""
        dialog = self.page.locator(CONFIRM)
        dialog.wait_for(state="visible", timeout=8000)
        title, content = self.confirm_texts()
        self.click_confirm("确定")
        self._wait_table_loaded()
        return title, content

    def set_status(self, name, status):
        """勾选单条 → 启用/禁用 → 确认 → 等状态生效。"""
        self.clear_selection()
        self.select_row(name)
        title, content = self.batch_action(status)
        self.wait_status(name, status)
        return title, content

    def wait_status(self, name, status, timeout=12.0):
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            last = self.statuses().get(name, "")
            if last == status:
                return True
            self.page.wait_for_timeout(250)
        raise AssertionError(f"等待「{name}」状态变为「{status}」超时，当前状态：{last!r}")

    # ================= 删除（勾选 + 工具栏确认框） =================
    def delete(self, name, nth=0):
        """删除一条仓库：勾选 + 工具栏「删除」→ 确认框确定。"""
        self.ensure_alive()
        before = self.count_row(name)
        self.clear_selection()
        self.select_row(name, nth)
        title, content = self.batch_action("删除")
        try:
            self.wait_row_count(name, before - 1)
        except AssertionError:
            self._raise_if_session_dead()
            raise
        return title, content

    # ================= 设为默认（行内 Popover） =================
    def open_set_default_popconfirm(self, name, nth=0):
        """点行内「设为默认」链接，返回 Popover。"""
        self.ensure_alive()
        self.close_overlays()
        self.row_locator(name, nth).locator("a", has_text="设为默认").click()
        popover = self.page.locator(POPOVER)
        popover.wait_for(state="visible", timeout=8000)
        return popover

    def click_popconfirm_ok(self, popover=None):
        popover = popover or self.page.locator(POPOVER)
        popover.locator("button").filter(has_text=spaced("确定")).first.click()
        self.pause()
        try:
            popover.wait_for(state="hidden", timeout=10000)
        except Exception:  # noqa: BLE001
            pass
        self._wait_table_loaded()
        return self

    def click_popconfirm_cancel(self, popover=None):
        popover = popover or self.page.locator(POPOVER)
        popover.locator("button").filter(has_text=spaced("取消")).first.click()
        self.pause()
        try:
            popover.wait_for(state="hidden", timeout=6000)
        except Exception:  # noqa: BLE001
            pass
        return self

    def set_default(self, name, nth=0):
        """设为默认：点链接 → Popover「确定设为默认吗?」→ 确定，等 isDefault 生效。"""
        popover = self.open_set_default_popconfirm(name, nth)
        text = popover.inner_text()
        assert "确定设为默认吗" in text, f"设为默认确认气泡文案不符：{text!r}"
        self.click_popconfirm_ok(popover)
        self.wait_default(name)
        return self

    def wait_default(self, name, timeout=12.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.defaults().get(name) == "是":
                return True
            self.page.wait_for_timeout(250)
        raise AssertionError(f"等待「{name}」变为默认仓库超时")

    # ================= 等待 / 清理 =================
    def wait_row(self, name, present=True, timeout=15.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.has_row(name) == present:
                return True
            self.page.wait_for_timeout(250)
        state = "出现" if present else "消失"
        raise AssertionError(f"等待「{name}」{state}超时（{timeout}s）")

    def wait_row_count(self, name, expected, timeout=15.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.count_row(name) == expected:
                return True
            self.page.wait_for_timeout(250)
        raise AssertionError(
            f"等待「{name}」行数为 {expected} 超时，当前 {self.count_row(name)}")

    def cleanup_contains(self, token, limit=60):
        """按运行前缀回收测试仓库：只删「仓库名称含 token」的行。"""
        if not token:
            return 0
        removed = 0
        self.close_overlays()
        self.clear_selection()
        self.search(token)
        try:
            while removed < limit:
                rows = self.rows_data()
                target = None
                for index, row in enumerate(rows):
                    if token in (row["name"] or ""):
                        target = (row["name"], index)
                        break
                if target is None:
                    break
                nth = sum(1 for r in rows[:target[1]] if r["name"] == target[0])
                self.delete(target[0], nth=nth)
                removed += 1
        finally:
            self.reset()
        return removed
