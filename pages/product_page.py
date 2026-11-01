"""商品管理 - 商品信息页面对象（Page Object）。

页面实测结构（Ant Design，2026-10-31 采集）：
    地址 /material/material，标题「商品信息 · 管伊佳ERP」
    查询区：类别下拉「请选择类别」+ 关键词 input[placeholder="请输入条码、名称、助记码等查询"]
            + 规格 input[placeholder="请输入规格查询"] + 查询/重置 + 「展开」
            展开后追加：型号、颜色、品牌、制造商、扩展1/2/3、仓位货架、基础重量、保质期、备注
            输入框 + 状态/序列号/批号下拉
    工具栏：新增、删除、启用、禁用、导入、导出、批量编辑、修正库存、修正成本、列设置
    表头：勾选 | 操作 | 条码 | 名称 | 规格 | 型号 | 颜色 | 类别 | 单位 | 库存 |
          采购价 | 零售价 | 销售价 | 最低售价 | 状态
          行内操作只有「编辑」「复制」两个链接（无行内删除，删除走工具栏）
    新增/编辑弹窗：.ant-modal，标题「新增」/「编辑」；三个 Tab：基本信息、库存数量、图片信息
        必填：名称 #name（「请输入名称」）、单位 #unit（「输入单位」），
              均带红色 * 号；空表单保存红字「请输入名称!」「请输入单位!」
        单位字段旁有「多单位」勾选框，勾选后 #unit 消失，变成「选择多单位」下拉
        条码表格是自定义 div 表格（.tbody > .tr > .td），行内 input id 形如
            barCode_<uuid>、commodityUnit_<uuid>、purchaseDecimal_<uuid>、
            commodityDecimal_<uuid>（零售价）、wholesaleDecimal_<uuid>（销售价）、
            lowDecimal_<uuid>（最低售价）
        表头：条码、单位、采购价、零售价、销售价、最低售价
        底部按钮：插入行、采购价-批量、零售价-批量、销售价-批量、最低售价-批量、保存（Ctrl+S）
    复制弹窗：标题「复制新增」，回显源 name/unit，条码自动生成新值（getMaxBarCode +1）
    库存数量 Tab：表头 仓库、期初库存数量、最低安全库存数量、最高安全库存数量，初始「暂无数据」
    图片信息 Tab：上传提示「图片最多4张，且单张大小不超过1M」
    批量编辑弹窗：标题「批量编辑」，字段 颜色/品牌/基础重量/保质期/类别/仓位货架/制造商/序列号/批号/备注
    列设置：.ant-popover（右侧弹出），列出所有可显隐列 + 「恢复默认」
    删除/启用/禁用：勾选后工具栏操作 → .ant-modal-confirm（标题「确认删除」/「确认操作」）
    保存按钮注意：新增弹窗里有**两个** ant-btn-primary（「插入行」「保存（Ctrl+S）」），
        必须用 filter(has_text='保存') 定位，否则点到「插入行」不会保存。

定位一律基于实测到的 id / placeholder / 可见文案；列表行匹配按「名称」列整格比较。
"""

import time

from pages.base_page import CONFIRM, BasePage, spaced

# 表格列索引（td 从 1 开始；第 1 列勾选框，第 2 列操作，第 3 列起业务字段）
COL_OP = 2       # 操作（编辑/复制）
COL_BARCODE = 3  # 条码
COL_NAME = 4     # 名称
COL_SPEC = 5     # 规格
COL_MODEL = 6    # 型号
COL_COLOR = 7    # 颜色
COL_CATEGORY = 8 # 类别
COL_UNIT = 9     # 单位
COL_STOCK = 10   # 库存
COL_PURCHASE = 11  # 采购价
COL_RETAIL = 12    # 零售价
COL_SALE = 13      # 销售价
COL_LOWEST = 14    # 最低售价
COL_STATUS = 15    # 状态

# 保存后若出现这些字样，说明接口/校验拦下了这次写入（弹窗仍会关闭，不能只看弹窗）
SAVE_FAILURE_HINTS = ("异常", "失败", "错误", "不能为空", "已存在", "重复")

ROWS_JS = """() => Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
    .map(tr => {
        const cells = Array.from(tr.children).map(td => (td.innerText || '').trim());
        return {
            ops: cells[1], barcode: cells[2], name: cells[3], spec: cells[4],
            model: cells[5], color: cells[6], category: cells[7], unit: cells[8],
            stock: cells[9], purchase: cells[10], retail: cells[11],
            sale: cells[12], lowest: cells[13], status: cells[14],
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


class ProductPage(BasePage):
    PATH = "/material/material"
    KEYWORD_INPUT = 'input[placeholder="请输入条码、名称、助记码等查询"]'
    SPEC_INPUT = 'input[placeholder="请输入规格查询"]'
    ROWS = ".ant-table-tbody tr.ant-table-row"
    EMPTY = ".ant-empty-description, .ant-empty"

    def __init__(self, page):
        super().__init__(page)
        # 商品信息页的查询区/工具栏也在「含表格的卡片」里
        self.BUTTON_SCOPE = ".ant-card:has(.ant-table) button"

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
        assert len(hits) > nth, f"表格中找不到第 {nth + 1} 条名称「{name}」，当前：{self.names()}"
        return hits[nth]

    def row_locator(self, name, nth=0):
        return self.page.locator(self.ROWS).nth(self.row_index(name, nth))

    def read_row(self, name, nth=0):
        row = self.rows_data()[self.row_index(name, nth)]
        return {key: row[key] for key in (
            "ops", "barcode", "name", "spec", "model", "color", "category",
            "unit", "stock", "purchase", "retail", "sale", "lowest", "status")}

    def statuses(self):
        return {row["name"]: row["status"] for row in self.rows_data()}

    # ================= 查询 =================
    def search(self, keyword):
        """按关键词（条码/名称/助记码）模糊查询。"""
        self.ensure_alive()
        self.fill(self.KEYWORD_INPUT, keyword)
        self.click_button("查询")
        self._wait_table_loaded()
        return self

    def search_spec(self, spec):
        self.fill(self.SPEC_INPUT, spec)
        self.click_button("查询")
        self._wait_table_loaded()
        return self

    def reset(self):
        """清空查询条件，回到全量列表第一页。"""
        if self.page.locator(self.KEYWORD_INPUT).count():
            self.fill(self.KEYWORD_INPUT, "")
        if self.page.locator(self.SPEC_INPUT).count():
            self.fill(self.SPEC_INPUT, "")
        self.click_button("重置")
        self._wait_table_loaded()
        return self

    def expand_query(self):
        """展开高级查询区（若尚未展开）。"""
        btn = self.page.locator(".ant-card:has(.ant-table) a, .ant-card:has(.ant-table) button").filter(has_text="展开")
        if btn.count():
            btn.first.click()
            self.pause()
        return self

    # ================= 新增 / 编辑 / 复制弹窗 =================
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

    def open_copy_modal(self, name, nth=0):
        self.ensure_alive()
        self.close_overlays()
        self.row_locator(name, nth).locator("a", has_text="复制").click()
        self.modal().wait_for(state="visible", timeout=10000)
        self.pause()
        return self

    def form_state(self):
        """读取当前弹窗（新增/编辑/复制）的名称、单位、条码与标题。"""
        return self.modal().evaluate("""(m) => {
            const name = m.querySelector('#name');
            const unit = m.querySelector('#unit');
            const barCode = m.querySelector('[id^=barCode_]');
            const multi = Array.from(m.querySelectorAll('.ant-checkbox-wrapper'))
                .filter(w => (w.innerText || '').trim() === '多单位')[0];
            return {
                title: ((m.querySelector('.ant-modal-title') || {}).innerText || '').trim(),
                name: name ? name.value : null,
                unit: unit ? unit.value : null,
                barCode: barCode ? barCode.value : null,
                multiChecked: multi ? multi.querySelector('.ant-checkbox-checked') !== null : false,
            };
        }""")

    def fill_name(self, name):
        self.fill(self.modal().locator("#name"), name)
        return self

    def fill_unit(self, unit):
        """填单位（自由输入模式；多单位勾选时 #unit 不存在）。"""
        self.fill(self.modal().locator("#unit"), unit)
        return self

    def fill_basic(self, name, unit):
        """填名称 + 单位（最小必填项）。"""
        self.fill_name(name)
        if self.modal().locator("#unit").count():
            self.fill_unit(unit)
        return self

    def save_button(self):
        """保存按钮：必须用文案「保存」定位，避免误点「插入行」（同为 primary）。

        文案有两种：新增/编辑弹窗是「保存（Ctrl+S）」，批量编辑弹窗是「保 存」，
        所以用 spaced() 宽松匹配，别写死字符串。
        """
        return self.modal().locator("button").filter(has_text=spaced("保存")).first

    def click_save(self):
        self.save_button().click()
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

    def save_batch(self):
        """批量编辑保存：点「保存」会先弹「确认操作 / 是否操作选中的N条数据?」。

        注意这个确认框是 .ant-modal-confirm，会叠在批量编辑弹窗之上；
        不点确定就不会发 /material/batchUpdate 请求（表现为「保存没反应」）。
        返回 (确认框标题, 正文)。
        """
        self.drain_toasts()
        self.click_save()
        dialog = self.confirm_dialog()
        dialog.wait_for(state="visible", timeout=8000)
        title, content = self.confirm_texts()
        self.click_confirm("确定")
        try:
            self.modal().wait_for(state="hidden", timeout=12000)
        except Exception as exc:  # noqa: BLE001
            self._expired_or_raise("批量保存", exc)
            raise AssertionError(f"批量编辑保存后弹窗未关闭，页面提示：{self.toasts()}") from exc
        self._wait_table_loaded()
        return title, content

    def create(self, name, unit="个", others=None):
        """新增一条商品；others 保留兼容（暂不填扩展字段）。"""
        self.open_create_modal()
        self.fill_basic(name, unit)
        self.save_success()
        self.wait_row(name, present=True)
        return self

    def cancel(self):
        return self.cancel_modal()

    # ================= 多单位 =================
    def multi_unit_checkbox(self):
        return self.modal().locator(".ant-checkbox-wrapper").filter(has_text="多单位").first

    def multi_unit_checked(self):
        box = self.multi_unit_checkbox()
        if not box.count():
            return False
        return box.locator(".ant-checkbox-checked").count() > 0

    def enable_multi_unit(self):
        """勾选「多单位」，并等到「选择多单位」下拉出现。"""
        if not self.multi_unit_checked():
            self.multi_unit_checkbox().click()
            self.pause()
        self.multi_unit_select().wait_for(state="visible", timeout=10000)
        return self

    def disable_multi_unit(self):
        """取消勾选「多单位」，恢复自由输入。"""
        if self.multi_unit_checked():
            self.multi_unit_checkbox().click()
            self.pause()
        return self

    def multi_unit_select(self):
        return self.modal().locator(".ant-select").filter(has_text="选择多单位").first

    def multi_unit_options(self, max_scroll=8):
        """展开「选择多单位」下拉并读取全部选项。"""
        select = self.multi_unit_select()
        select.click()
        self.page.wait_for_timeout(600)
        self.page.locator(".ant-select-dropdown:visible .ant-select-dropdown-menu-item").first.wait_for(timeout=10000)
        collected = []
        for _ in range(max_scroll):
            items = self.page.locator(".ant-select-dropdown:visible .ant-select-dropdown-menu-item").all_inner_texts()
            items = [text.strip() for text in items if text.strip()]
            if items == collected:
                break
            collected = items
            self._safe_evaluate(
                "() => { const d = Array.from(document.querySelectorAll('.ant-select-dropdown'))"
                ".find(x => x.offsetWidth || x.offsetHeight);"
                " if (d) { const menu = d.querySelector('.ant-select-dropdown-menu');"
                " if (menu) menu.scrollTop = menu.scrollHeight; } }")
            self.page.wait_for_timeout(400)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)
        return collected

    # ================= 三个 Tab =================
    def switch_tab(self, tab_name):
        self.modal().locator(".ant-tabs-tab").filter(has_text=tab_name).first.click()
        self.pause()
        return self

    def barcode_table_headers(self):
        """条码表格（div 表格）的表头文字。"""
        return self.modal().evaluate("""(m) => {
            const pane = m.querySelector('.ant-tabs-tabpane-active') || m;
            const ths = Array.from(pane.querySelectorAll('[class*=header], [class*=thead] th, th'))
                .map(t => (t.innerText || '').trim()).filter(Boolean);
            return ths;
        }""")

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
        """工具栏操作（启用/禁用/删除/批量编辑等）：返回确认框 (标题, 正文)。"""
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

    # ================= 等待 / 清理 =================
    def wait_row(self, name, present=True, timeout=15.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.has_row(name) == present:
                return True
            self.page.wait_for_timeout(250)
        state = "出现" if present else "消失"
        raise AssertionError(f"等待「{name}」{state}超时（{timeout}s）")

    def cleanup_contains(self, token, limit=60):
        """按运行前缀回收测试商品：只删「名称含 token」的行。"""
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

    def delete(self, name, nth=0):
        """删除一条商品：勾选 + 工具栏「删除」→ 确认框确定。"""
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
        return self

    def wait_row_count(self, name, expected, timeout=15.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.count_row(name) == expected:
                return True
            self.page.wait_for_timeout(250)
        raise AssertionError(
            f"等待「{name}」行数为 {expected} 超时，当前 {self.count_row(name)}")
