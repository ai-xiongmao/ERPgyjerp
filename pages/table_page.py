"""列表页公共基类：本项目三个页面（多单位 / 商品 / 仓库）都是同一个模子。

它们都是「查询区 + 表格 + 勾选列 + 工具栏 + 分页 + 新增/编辑弹窗」，
差异只在**字段**（列映射、表单字段、状态文案），不在**交互**。
所以交互全部收在这里，子类用类属性声明字段差异：

    class UnitPage(TablePage):
        PATH = "/system/unit"
        SEARCH_INPUT = 'input[placeholder="请输入单位名称查询"]'
        ROWS_JS = ...            # 行数据 → dict 的列映射
        READ_KEYS = ("seq", "name", "basic", ...)   # read_row 返回哪些键
        NAME_KEY = "basic"       # 用哪个字段标识一行（行匹配、状态表、回收都以它为准）
        NAME_LABEL = "基本单位"   # 断言文案里的称呼

删除有两种形态，都遇到过，所以基类只提供一种、另一种由子类覆盖：
    - 工具栏删除（默认实现）：勾选 → 工具栏「删除」→ .ant-modal-confirm
    - 行内删除（子类覆盖）：行内「删除」链接 → .ant-popover Popconfirm

实测要点（改前端后请重新核对）：
- 分页总数文案形如「1-10 共26条」，每页默认 10 条；切每页条数后当前页可能保留；
- 表头勾选框的点击常绑在 input 上，点 span 会静默失败，所以两种选择器都要试；
- 保存后接口报错时弹窗**也会关闭**，因此关闭后必须再查 toast，否则会误判成功；
- 行匹配一律按 NAME_KEY 那一列做整格比较，同名多行用 nth 区分。
"""

import time

from config import BASE_URL
from pages.base_page import CONFIRM, POPOVER, BasePage, spaced

# 保存后若出现这些字样，说明接口/校验拦下了这次写入（弹窗仍会关闭，不能只看弹窗）
# 三个页面历史上各写一份、各自漏词，这里取并集：宁可多拦，也不要静默放过一次失败写入。
SAVE_FAILURE_HINTS = (
    "异常", "失败", "错误", "不能为空", "只能为数字", "长度在", "已存在", "重复",
)

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


class TablePage(BasePage):
    # ---- 子类必须声明 ----
    PATH = ""                        # 页面路径，open() 用
    SEARCH_INPUT = ""                # 主查询框选择器，search() 用
    ROWS_JS = ""                     # 行数据列映射（每个页面表头不同）
    READ_KEYS = ()                   # read_row() 返回的键
    NAME_KEY = "name"                # 标识一行的字段
    NAME_LABEL = "记录"              # 断言文案里的称呼

    # ---- 可选覆盖 ----
    SEARCH_EXTRA_INPUTS = ()         # reset() 还要一并清空的其它查询框
    ROWS = ".ant-table-tbody tr.ant-table-row"
    EMPTY = ".ant-empty-description, .ant-empty"
    SAVE_FAILURE_HINTS = SAVE_FAILURE_HINTS

    # 左侧一级菜单文案（enter_via_menu 用），如「商品管理」「基础资料」
    MENU_GROUP = ""

    # ---- 页面骨架选择器（结构校验类用例共用的断言对象）----
    DASHBOARD_PATH = "/dashboard/analysis"
    MENU_SUBMENU = ".ant-menu-submenu"
    MENU_SUBMENU_TITLE = ".ant-menu-submenu-title"
    MENU_SELECTED = ".ant-menu-item-selected"
    TABLE_HEADERS = ".ant-table-thead th"
    TABLE = ".ant-table"

    # ================= 导航 =================
    def open(self):
        """确保登录态可用、停在目标页面，且表格首屏数据已经加载完。"""
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

    def enter_via_menu(self, href=None):
        """模拟真实用户路径：工作台 → 展开左侧一级菜单 → 点子菜单进入本页。

        与 open() 的区别是**不改地址栏**，走 SPA 路由跳转——这是「从菜单能否正常进入」
        这类用例要验证的东西，直接 goto 会绕过路由与菜单渲染。

        不在这里做登录态探活：目标页是否渲染出来，由随后的表格等待与断言暴露。
        """
        href = href or self.PATH
        self.goto(BASE_URL + self.DASHBOARD_PATH, wait_after=2000)

        group = self.page.locator(self.MENU_SUBMENU).filter(has_text=self.MENU_GROUP).first
        group.wait_for(state="visible", timeout=15000)
        # 一级菜单可能已展开（上一条用例留下的状态），已展开再点会收起
        if "ant-menu-submenu-open" not in (group.get_attribute("class") or ""):
            group.locator(self.MENU_SUBMENU_TITLE).first.click()
            self.pause()

        link = self.page.locator(f'.ant-menu-item a[href="{href}"]').first
        link.wait_for(state="visible", timeout=10000)
        link.click()
        self.page.wait_for_timeout(1200)
        self._wait_table_loaded()
        return self

    def wait_title(self, expected, timeout=10.0):
        """等 document.title 变成 expected，返回实际值。

        SPA 路由切换后标题是异步更新的；已知该系统经菜单跳转时**不更新** title，
        所以这里只返回实际值、由用例决定是判红还是记偏差。
        """
        deadline = time.time() + timeout
        title = self.page.title().strip()
        while time.time() < deadline and title != expected:
            self.page.wait_for_timeout(300)
            title = self.page.title().strip()
        return title

    # ================= 页面骨架（结构校验用）=================
    def active_menu_items(self):
        """左侧菜单当前高亮项的文字列表。"""
        return [t.strip() for t in self.page.locator(self.MENU_SELECTED).all_inner_texts()]

    def table_headers(self):
        """表头单元格文字列表（按列序）。"""
        return [h.strip() for h in self.page.locator(self.TABLE_HEADERS).all_inner_texts()]

    def has_table(self):
        return self.page.locator(self.TABLE).count() >= 1

    def toolbar_labels(self):
        """工具栏按钮文字，去掉 AntD 两个汉字的自动空格（「新 增」→「新增」）。"""
        return [t.replace(" ", "") for t in self.page.locator(self.BUTTON_SCOPE).all_inner_texts()]

    # ================= 列表读取 =================
    def rows_data(self):
        return self._safe_evaluate(self.ROWS_JS, default=[]) or []

    def row_key(self, row):
        """取一行的标识值（行匹配 / 状态表 / 数据回收都用它）。"""
        return row.get(self.NAME_KEY)

    def names(self):
        return [self.row_key(row) for row in self.rows_data()]

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
        """第 nth 个「NAME_KEY = name」的行在当前页的序号。"""
        hits = [i for i, current in enumerate(self.names()) if current == name]
        assert len(hits) > nth, (
            f"表格中找不到第 {nth + 1} 条{self.NAME_LABEL}「{name}」，当前：{self.names()}")
        return hits[nth]

    def row_locator(self, name, nth=0):
        return self.page.locator(self.ROWS).nth(self.row_index(name, nth))

    def read_row(self, name, nth=0):
        row = self.rows_data()[self.row_index(name, nth)]
        return {key: row[key] for key in self.READ_KEYS}

    def statuses(self):
        return {self.row_key(row): row["status"] for row in self.rows_data()}

    # ================= 查询 =================
    def search(self, keyword):
        self.ensure_alive()
        self.fill(self.SEARCH_INPUT, keyword)
        self.click_button("查询")
        self._wait_table_loaded()
        return self

    def reset(self):
        """清空查询条件，回到全量列表第一页。"""
        inputs = [self.SEARCH_INPUT, *self.SEARCH_EXTRA_INPUTS]
        present = [sel for sel in inputs if sel and self.page.locator(sel).count()]
        if not present:
            return self
        for selector in present:
            self.fill(selector, "")
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

    def click_row_link(self, text, name, nth=0):
        """点行内操作链接（编辑 / 删除 / 复制 / 设为默认）。"""
        self.ensure_alive()
        self.close_overlays()
        self.row_locator(name, nth).locator("a", has_text=text).click()
        return self

    def open_edit_modal(self, name, nth=0):
        self.click_row_link("编辑", name, nth)
        self.modal().wait_for(state="visible", timeout=10000)
        self.pause()
        return self

    def save_button(self):
        """保存按钮：必须用文案定位，避免误点同为 primary 的「插入行」。

        文案有两种：「保存（Ctrl+S）」「保 存」，用 spaced() 宽松匹配，别写死字符串。
        """
        return self.modal().locator("button").filter(has_text=spaced("保存")).first

    def click_save(self):
        self.save_button().click()
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
            if any(hint in message for hint in self.SAVE_FAILURE_HINTS):
                raise AssertionError(f"保存未成功，接口提示「{message}」")
        return self

    def save_blocked(self, expect=None):
        """点保存但预期被拦截：返回 {toast, inline, matched}，弹窗应保持打开。"""
        self.drain_toasts()
        self.click_save()
        matched = self.wait_message(expect) if expect else None
        return {"toast": self.toasts(), "inline": self.inline_errors(), "matched": matched}

    def cancel(self):
        return self.cancel_modal()

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

    def set_status(self, name, status):
        """勾选单条 → 启用/禁用 → 确认 → 等状态生效。"""
        self.clear_selection()
        self.select_row(name)
        title, content = self.batch_action(status)
        self.wait_status(name, status)
        return title, content

    def delete_selected(self):
        return self.batch_action("删除")

    def wait_status(self, name, status, timeout=12.0):
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            last = self.statuses().get(name, "")
            if last == status:
                return True
            self.page.wait_for_timeout(250)
        raise AssertionError(f"等待「{name}」状态变为「{status}」超时，当前状态：{last!r}")

    # ================= 删除（工具栏 + 确认框） =================
    def delete(self, name, nth=0):
        """删除一条记录：勾选 + 工具栏「删除」→ 确认框确定。返回 (标题, 正文)。

        行内删除的页面（如多单位）覆盖本方法，走 Popconfirm。
        同名多行时不能用「该名称是否还在列表」判断成功，必须以「这一行的条数减 1」为准。
        """
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

    # ================= Popconfirm（行内确认气泡） =================
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

    # ================= 等待 =================
    def wait_row(self, name, present=True, timeout=15.0):
        """轮询等待某行出现 / 消失（表格刷新是异步的）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.has_row(name) == present:
                return True
            self.page.wait_for_timeout(250)
        state = "出现" if present else "消失"
        raise AssertionError(f"等待「{name}」{state}超时（{timeout}s）")

    def wait_row_count(self, name, expected, timeout=15.0):
        """等某一行标识值的行数变成期望值（同名多行场景用）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.count_row(name) == expected:
                return True
            self.page.wait_for_timeout(250)
        raise AssertionError(
            f"等待「{name}」行数为 {expected} 超时，当前 {self.count_row(name)}")

    def wait_rows_rendered(self, expected, timeout=12.0):
        """等当前页渲染出指定行数（切每页条数、翻页后不能立刻读）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.row_count() == expected:
                return True
            self.page.wait_for_timeout(200)
        raise AssertionError(f"等待渲染 {expected} 行超时，当前 {self.row_count()} 行")

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

    # ================= 数据回收 =================
    def _matches_token(self, row, token):
        """该行是否属于本次运行造的数据。默认看标识列，子类可加判据。"""
        return token in (self.row_key(row) or "")

    def cleanup_contains(self, token, limit=60):
        """按运行前缀回收测试数据。

        模糊查询会连既有业务数据一起返回（例如名称里恰好含同名子串），
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
                    if self._matches_token(row, token):
                        target = (self.row_key(row), index)
                        break
                if target is None:
                    break
                # 同名多行时，nth 是「同一标识值里的第几条」
                nth = sum(1 for r in rows[:target[1]] if self.row_key(r) == target[0])
                self.delete(target[0], nth=nth)
                removed += 1
        finally:
            self.reset()
        return removed

    def cleanup_names(self, names, limit=20):
        """按「标识列整格相等」精确回收，用于名字里不含运行前缀的极少数记录。"""
        removed = 0
        for name in names:
            if not name:
                continue
            self.search(name)
            while removed < limit:
                rows = self.rows_data()
                if not any(self.row_key(row) == name for row in rows):
                    break
                self.delete(name, nth=0)
                removed += 1
        self.reset()
        return removed
