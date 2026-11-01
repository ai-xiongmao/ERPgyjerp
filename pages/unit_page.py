"""商品管理 - 多单位页面对象（Page Object）。

页面实测结构（Ant Design，2026-10-31 采集）：
    查询区：单位名称 input[placeholder="请输入单位名称查询"] + 「查 询」「重 置」
    工具栏：「新增」「删除」「启用」「禁用」（无空格）
    表头：# | 操作 | 单位名称 | 基本单位 | 副单位 | 副单位2 | 副单位3 | 状态
          （最左侧还有一列勾选框，无文字）
    行内操作：「编辑」「删除」两个链接；删除走 Popconfirm「确定删除吗?」
    新增/编辑：弹窗 .ant-modal，标题「新增」/「编辑」
        字段 #basicUnit、#otherUnit+#ratio、#otherUnitTwo+#ratioTwo、
             #otherUnitThree+#ratioThree
    批量操作：勾选后点启用/禁用/删除 → .ant-modal-confirm
        启用/禁用：标题「确认操作」，正文「是否操作选中数据?」
        删除：标题「确认删除」，正文「是否删除选中数据?」
    分页：.ant-pagination，总数文案形如「1-10 共26条」，每页默认 10 条
    校验提示：内联红字在 .ant-form-explain（如「请输入基本单位!」）；
              其余拦截提示走 toast .ant-message-notice（如「抱歉，副单位不能为空！」）

定位一律基于实测到的 id / placeholder / 可见文案；行匹配按「基本单位」列做整格比较，
同名多行用 index 区分（TC-UNIT-019 需要两条同名记录）。
"""

import time

from browser import SessionExpiredError

from pages.base_page import CONFIRM, POPOVER, BasePage, spaced

# 表格列索引（td 从 1 开始，与表头顺序一一对应；第 1 列是勾选框）
COL_NAME = 4    # 单位名称
COL_BASIC = 5   # 基本单位
COL_OTHER = 6   # 副单位（形如「箱=10个」）
COL_OTHER2 = 7  # 副单位2
COL_OTHER3 = 8  # 副单位3
COL_STATUS = 9  # 状态

# 保存后若出现这些字样，说明接口/校验拦下了这次写入（弹窗仍会关闭，不能只看弹窗）
SAVE_FAILURE_HINTS = ("异常", "失败", "错误", "不能为空", "只能为数字", "长度在", "已存在")

ROWS_JS = """() => Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
    .map(tr => {
        const cells = Array.from(tr.children).map(td => (td.innerText || '').trim());
        return {
            seq: cells[1], name: cells[3], basic: cells[4],
            other: cells[5], other2: cells[6], other3: cells[7], status: cells[8],
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
    return {
        title: ((modal.querySelector('.ant-modal-title') || {}).innerText || '').trim(),
        basic: value('basicUnit'),
        other: value('otherUnit'), ratio: value('ratio'),
        other2: value('otherUnitTwo'), ratio2: value('ratioTwo'),
        other3: value('otherUnitThree'), ratio3: value('ratioThree'),
        required: Array.from(modal.querySelectorAll('.ant-form-item-label')).map(label => ({
            text: (label.innerText || '').trim(),
            star: !!label.querySelector('.ant-form-item-required'),
        })),
        bodyText: (modal.innerText || '').replace(/\\s+/g, ' ').trim(),
    };
}"""


class UnitPage(BasePage):
    PATH = "/system/unit"
    SEARCH_INPUT = 'input[placeholder="请输入单位名称查询"]'
    ROWS = ".ant-table-tbody tr.ant-table-row"
    EMPTY = ".ant-empty-description, .ant-empty"

    # (单位输入框, 比例输入框)；第 1 组是基本单位，没有比例
    UNIT_FIELDS = (
        ("#basicUnit", None),
        ("#otherUnit", "#ratio"),
        ("#otherUnitTwo", "#ratioTwo"),
        ("#otherUnitThree", "#ratioThree"),
    )

    # ================= 导航 =================
    def open(self):
        """确保登录态可用、停在多单位页面，且表格首屏数据已经加载完。"""
        from config import BASE_URL

        recovered = self.ensure_alive()
        if recovered:
            # 登录可能是在 SPA 路由跳转中完成的（页面内存仍是旧 token），必须重载
            self.page.reload(wait_until="domcontentloaded")
            self.page.wait_for_timeout(1000)
            self.ensure_alive()
        if not (self.page.url or "").rstrip("/").endswith(self.PATH):
            self.goto(BASE_URL + self.PATH)
            self.ensure_alive()  # 未登录时会被重定向回登录页
        try:
            self.page.locator(self.BUTTON_SCOPE).first.wait_for(timeout=15000)
        except Exception:
            self.ensure_alive()
            raise
        self._wait_table_loaded()
        self.ensure_alive()  # 首屏接口返回后才可能暴露会话失效
        return self

    def _wait_table_loaded(self, timeout=20.0):
        """等 loading 转圈结束 + 表格体出现，再留一点渲染余量。"""
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

    def basic_units(self):
        return [row["basic"] for row in self.rows_data()]

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

    def has_row(self, basic_unit):
        return basic_unit in self.basic_units()

    def count_row(self, basic_unit):
        return self.basic_units().count(basic_unit)

    def row_index(self, basic_unit, nth=0):
        """第 nth 个「基本单位 = basic_unit」的行在当前页的序号。"""
        hits = [i for i, basic in enumerate(self.basic_units()) if basic == basic_unit]
        assert len(hits) > nth, f"表格中找不到第 {nth + 1} 条基本单位「{basic_unit}」，当前：{self.basic_units()}"
        return hits[nth]

    def row_locator(self, basic_unit, nth=0):
        return self.page.locator(self.ROWS).nth(self.row_index(basic_unit, nth))

    def read_row(self, basic_unit, nth=0):
        row = self.rows_data()[self.row_index(basic_unit, nth)]
        return {key: row[key] for key in ("seq", "name", "basic", "other", "other2", "other3", "status")}

    def statuses(self):
        return {row["basic"]: row["status"] for row in self.rows_data()}

    # ================= 查询 =================
    def search(self, keyword):
        """按单位名称模糊查询。"""
        self.ensure_alive()
        self.fill(self.SEARCH_INPUT, keyword)
        self.click_button("查询")
        self._wait_table_loaded()
        return self

    def reset(self):
        """清空查询条件，回到全量列表第一页。"""
        if not self.page.locator(self.SEARCH_INPUT).count():
            return self
        self.fill(self.SEARCH_INPUT, "")
        self.click_button("重置")
        self._wait_table_loaded()
        return self

    def reset_search_only(self):
        """只清空输入框（不点重置），用于准备下一条查询。"""
        self.fill(self.SEARCH_INPUT, "")
        return self

    # ================= 新增 / 编辑弹窗 =================
    def open_create_modal(self):
        self.ensure_alive()
        self.close_overlays()
        self.click_button("新增")
        self.modal().wait_for(state="visible", timeout=10000)
        self.pause()
        return self

    def open_edit_modal(self, basic_unit, nth=0):
        self.ensure_alive()
        self.close_overlays()
        self.row_locator(basic_unit, nth).locator("a", has_text="编辑").click()
        self.modal().wait_for(state="visible", timeout=10000)
        self.pause()
        return self

    def form_state(self):
        return self._safe_evaluate(FORM_JS)

    def fill_form(self, basic_unit, others=()):
        """others: [(副单位, 比例), ...]，最多 3 组。"""
        modal = self.modal()
        self.fill(modal.locator("#basicUnit"), basic_unit)
        for index, (unit_sel, ratio_sel) in enumerate(self.UNIT_FIELDS[1:]):
            if index < len(others):
                name, ratio = others[index]
                self.fill(modal.locator(unit_sel), name)
                self.fill(modal.locator(ratio_sel), ratio)
            else:
                # 编辑场景要清掉上一轮残留值，避免把旧副单位一起提交
                self.fill(modal.locator(unit_sel), "")
                self.fill(modal.locator(ratio_sel), "")
        return self

    def click_save(self):
        self.modal().locator("button.ant-btn-primary").first.click()
        self.pause()
        return self

    def save_success(self):
        """点保存并等弹窗关闭；失败时区分「登录过期」「接口报错」「校验不过」。

        注意：接口报错时弹窗**也会关闭**（实测填副单位3 返回 301「数据写入异常」，
        弹窗照关、列表无新数据），所以必须在关闭后检查 toast，否则只会看到
        「等待某行出现超时」这种没有信息量的失败。
        """
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
        """点保存但预期被拦截：返回 {toast, inline, matched}，弹窗应保持打开。"""
        self.drain_toasts()
        self.click_save()
        matched = self.wait_message(expect) if expect else None
        return {"toast": self.toasts(), "inline": self.inline_errors(), "matched": matched}

    def create(self, basic_unit, others=()):
        """新增一条多单位记录。"""
        self.open_create_modal()
        self.fill_form(basic_unit, others)
        self.save_success()
        self.wait_row(basic_unit, present=True)
        return self

    def update(self, current_basic, new_basic=None, others=(), nth=0):
        """编辑一条记录；others 为该记录的**完整**目标副单位列表。"""
        self.open_edit_modal(current_basic, nth)
        # 断言弹窗回填的正是目标行，防止点到别的记录
        state = self.form_state() or {}
        assert state.get("basic") == current_basic, (
            f"编辑弹窗回填的基本单位与目标行不一致：{state.get('basic')!r} != {current_basic!r}")

        target = new_basic or current_basic
        self.fill_form(target, others)
        self.save_success()

        self.wait_row(target, present=True)
        if target != current_basic:
            self.wait_row(current_basic, present=False)
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

    def select_row(self, basic_unit, nth=0):
        before = self.selected_count()
        self.row_locator(basic_unit, nth).locator(".ant-checkbox").click()
        self.pause(300)
        assert self._wait_selected(before + 1), (
            f"勾选「{basic_unit}」失败：勾选数仍为 {self.selected_count()}")
        return self

    def select_rows(self, basic_units):
        for basic in basic_units:
            self.select_row(basic)
        return self

    def select_all(self, checked=True, timeout=8.0):
        """表头勾选框：全选 / 取消全选。

        实测点 span 有时不触发（antd 的点击绑定在 input 上），所以优先点 input，
        并且必须校验勾选数达到期望值——否则「已经全选」的场景会误判为成功。
        """
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
            except Exception:  # noqa: BLE001 - 被浮层挡住时先关浮层再试
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

    def set_status(self, basic_unit, status):
        """勾选单条 → 启用/禁用 → 确认 → 等状态生效。"""
        self.clear_selection()
        self.select_row(basic_unit)
        title, content = self.batch_action(status)
        self.wait_status(basic_unit, status)
        return title, content

    def delete_selected(self):
        return self.batch_action("删除")

    def wait_status(self, basic_unit, status, timeout=12.0):
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            last = self.statuses().get(basic_unit, "")
            if last == status:
                return True
            self.page.wait_for_timeout(250)
        raise AssertionError(f"等待「{basic_unit}」状态变为「{status}」超时，当前状态：{last!r}")

    # ================= 删除（行内 Popconfirm） =================
    def delete(self, basic_unit, nth=0):
        """行内删除：删除链接 → Popconfirm「确定删除吗?」→ 确定。

        同名多行时不能用「该名称是否还在列表」判断成功，
        必须以「这一行的条数是否减 1」为准。
        """
        self.ensure_alive()
        before = self.count_row(basic_unit)
        self.row_locator(basic_unit, nth).locator("a", has_text="删除").click()
        popover = self.page.locator(POPOVER)
        popover.wait_for(state="visible", timeout=8000)
        text = popover.inner_text()
        assert "确定删除吗" in text, f"删除确认气泡文案不符：{text!r}"
        self.click_popconfirm_ok(popover)
        try:
            self.wait_row_count(basic_unit, before - 1)
        except AssertionError:
            self._raise_if_session_dead()
            raise
        return self

    def open_delete_popconfirm(self, basic_unit, nth=0):
        self.close_overlays()
        self.row_locator(basic_unit, nth).locator("a", has_text="删除").click()
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
        # Popconfirm 有 1~1.5s 的离场动画，不等它消失就断言会误判为「没关掉」
        try:
            popover.wait_for(state="hidden", timeout=6000)
        except Exception:  # noqa: BLE001
            pass
        return self

    # ================= 分页 =================
    def goto_page(self, number):
        self.page.locator(f".ant-pagination-item-{number}").first.click()
        self.pause()
        self._wait_table_loaded()
        deadline = time.time() + 10
        while time.time() < deadline and self.pagination_info()["current"] != number:
            self.page.wait_for_timeout(200)
        return self

    def next_page(self):
        self.page.locator(".ant-pagination-next a").first.click()
        self.pause()
        self._wait_table_loaded()
        return self

    def set_page_size(self, size):
        """切换每页条数。

        注意：切换后当前页码可能保留（例如在第 2 页切 20 条/页，只剩 5 行），
        所以这里只等到「每页条数生效 + 行数稳定」，具体条数由用例按当前页断言。
        """
        self.page.locator(".ant-pagination-options-size-changer").first.click()
        self.page.wait_for_timeout(400)
        option = self.page.locator(
            ".ant-select-dropdown:visible .ant-select-dropdown-menu-item").filter(
                has_text=f"{size} 条/页").first
        option.click()
        self.pause()
        self._wait_table_loaded()
        deadline = time.time() + 10
        while time.time() < deadline and self.pagination_info().get("pageSize") != size:
            self.page.wait_for_timeout(150)
        self.wait_rows_stable()
        return self

    def wait_rows_stable(self, times=2, interval=300, timeout=10.0):
        """连续两次读到相同行数，认为渲染稳定。"""
        deadline = time.time() + timeout
        last, same = -1, 0
        while time.time() < deadline:
            current = self.row_count()
            same = same + 1 if current == last else 1
            last = current
            if same >= times:
                return current
            self.page.wait_for_timeout(interval)
        return last

    def page_size_options(self):
        self.page.locator(".ant-pagination-options-size-changer").first.click()
        self.page.wait_for_timeout(400)
        options = self._safe_evaluate(
            "() => Array.from(document.querySelectorAll('.ant-select-dropdown'))"
            ".filter(d => d.offsetWidth || d.offsetHeight)"
            ".flatMap(d => Array.from(d.querySelectorAll('.ant-select-dropdown-menu-item'))"
            ".map(o => (o.innerText || '').trim()))", default=[]) or []
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(200)
        return options

    # ================= 等待 / 清理 =================
    def wait_row(self, basic_unit, present=True, timeout=15.0):
        """轮询等待某行出现 / 消失（表格刷新是异步的）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.has_row(basic_unit) == present:
                return True
            self.page.wait_for_timeout(250)
        state = "出现" if present else "消失"
        raise AssertionError(f"等待「{basic_unit}」{state}超时（{timeout}s）")

    def wait_row_count(self, basic_unit, expected, timeout=15.0):
        """等某个基本单位的行数变成期望值（同名多行场景用）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.count_row(basic_unit) == expected:
                return True
            self.page.wait_for_timeout(250)
        raise AssertionError(
            f"等待「{basic_unit}」行数为 {expected} 超时，当前 {self.count_row(basic_unit)}")

    def wait_rows_rendered(self, expected, timeout=12.0):
        """等当前页渲染出指定行数（切每页条数、翻页后不能立刻读）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.row_count() == expected:
                return True
            self.page.wait_for_timeout(200)
        raise AssertionError(f"等待渲染 {expected} 行超时，当前 {self.row_count()} 行")

    def cleanup_prefix(self, prefixes, limit=50):
        """清理基本单位以给定前缀开头的所有行（历史脚本用法）。"""
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

    def cleanup_contains(self, token, limit=60):
        """按运行前缀回收测试数据：只删「单位名称或基本单位含 token」的行。

        模糊查询会连既有业务数据一起返回（例如单位名称里恰好含同名子串），
        所以删之前再用 token 做一次校验，绝不动别人的数据。
        """
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
                    if token in (row["name"] or "") or token in (row["basic"] or ""):
                        target = (row["basic"], index)
                        break
                if target is None:
                    break
                # 同名多行时，tgt 是「同基本单位里的第几条」
                nth = sum(1 for r in rows[:target[1]] if r["basic"] == target[0])
                self.delete(target[0], nth=nth)
                removed += 1
        finally:
            self.reset()
        return removed

    def cleanup_names(self, names, limit=20):
        """按「基本单位整格相等」精确回收，用于名字里不含运行前缀的极少数记录。"""
        removed = 0
        for name in names:
            if not name:
                continue
            self.search(name)
            while removed < limit:
                rows = self.rows_data()
                if not any(row["basic"] == name for row in rows):
                    break
                self.delete(name, nth=0)
                removed += 1
        self.reset()
        return removed
