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

通用交互（查询/勾选/工具栏/分页/等待/回收）在 TablePage 里；这里只留多单位特有的：
四个单位字段的表单、行身份取「基本单位」列、行内删除走 Popconfirm。
定位一律基于实测到的 id / placeholder / 可见文案；行匹配按「基本单位」列做整格比较，
同名多行用 index 区分（TC-UNIT-019 需要两条同名记录）。
"""

from pages.base_page import POPOVER
from pages.table_page import TablePage

# 表格列索引（td 从 1 开始，与表头顺序一一对应；第 1 列是勾选框）
COL_NAME = 4    # 单位名称
COL_BASIC = 5   # 基本单位
COL_OTHER = 6   # 副单位（形如「箱=10个」）
COL_OTHER2 = 7  # 副单位2
COL_OTHER3 = 8  # 副单位3
COL_STATUS = 9  # 状态

ROWS_JS = """() => Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
    .map(tr => {
        const cells = Array.from(tr.children).map(td => (td.innerText || '').trim());
        return {
            seq: cells[1], name: cells[3], basic: cells[4],
            other: cells[5], other2: cells[6], other3: cells[7], status: cells[8],
        };
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


class UnitPage(TablePage):
    PATH = "/system/unit"
    SEARCH_INPUT = 'input[placeholder="请输入单位名称查询"]'
    ROWS_JS = ROWS_JS
    READ_KEYS = ("seq", "name", "basic", "other", "other2", "other3", "status")
    NAME_KEY = "basic"          # 行身份是多单位自己的「基本单位」列
    NAME_LABEL = "基本单位"
    MENU_GROUP = "商品管理"      # 左侧一级菜单

    # (单位输入框, 比例输入框)；第 1 组是基本单位，没有比例
    UNIT_FIELDS = (
        ("#basicUnit", None),
        ("#otherUnit", "#ratio"),
        ("#otherUnitTwo", "#ratioTwo"),
        ("#otherUnitThree", "#ratioThree"),
    )

    # ================= 列表读取 =================
    def basic_units(self):
        """当前页所有「基本单位」值（历史命名，等价于 names()）。"""
        return self.names()

    # ================= 查询 =================
    def reset_search_only(self):
        """只清空输入框（不点重置），用于准备下一条查询。"""
        self.fill(self.SEARCH_INPUT, "")
        return self

    # ================= 新增 / 编辑弹窗 =================
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
        """多单位弹窗只有一个 primary 按钮，直接点它（历史实现，勿轻易改）。"""
        self.modal().locator("button.ant-btn-primary").first.click()
        self.pause()
        return self

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

    # ================= 删除（行内 Popconfirm，覆盖基类的工具栏删除） =================
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
        self.click_row_link("删除", basic_unit, nth)
        popover = self.page.locator(POPOVER)
        popover.wait_for(state="visible", timeout=8000)
        return popover

    # ================= 数据回收 =================
    def _matches_token(self, row, token):
        """单位名称或基本单位含 token 都算本次造的数据。"""
        return token in (row.get("name") or "") or token in (row.get("basic") or "")

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
