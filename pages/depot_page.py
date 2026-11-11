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

通用交互在 TablePage；这里只留仓库特有：双查询框、七个表单字段、负责人下拉、设为默认。
定位一律基于实测到的 id / placeholder / 可见文案；行匹配按「仓库名称」列整格比较。
"""

import time

from pages.base_page import POPOVER
from pages.table_page import TablePage

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

ROWS_JS = """() => Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'))
    .map(tr => {
        const cells = Array.from(tr.children).map(td => (td.innerText || '').trim());
        return {
            seq: cells[1], ops: cells[2], name: cells[3], address: cells[4],
            warehousing: cells[5], truckage: cells[6], manager: cells[7],
            remark: cells[8], sort: cells[9], status: cells[10], isDefault: cells[11],
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


class DepotPage(TablePage):
    PATH = "/system/depot"
    NAME_INPUT = 'input[placeholder="请输入仓库名称查询"]'
    REMARK_INPUT = 'input[placeholder="请输入备注查询"]'
    ROWS_JS = ROWS_JS
    READ_KEYS = ("seq", "ops", "name", "address", "warehousing", "truckage",
                 "manager", "remark", "sort", "status", "isDefault")
    NAME_KEY = "name"
    NAME_LABEL = "仓库"
    MENU_GROUP = "基础资料"      # 左侧一级菜单

    # 主查询框 + 重置时要一并清空的其它查询框
    SEARCH_INPUT = NAME_INPUT
    SEARCH_EXTRA_INPUTS = (REMARK_INPUT,)

    # ================= 查询 =================
    def search_remark(self, keyword):
        """按备注查询。"""
        self.ensure_alive()
        self.fill(self.REMARK_INPUT, keyword)
        self.click_button("查询")
        self._wait_table_loaded()
        return self

    # ================= 新增 / 编辑弹窗 =================
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

    def create(self, name, address=None, warehousing=None, truckage=None,
               sort=None, remark=None):
        """新增一条仓库记录（最少只需 name）。"""
        self.open_create_modal()
        self.fill_form(name, address, warehousing, truckage, sort, remark)
        self.save_success()
        self.wait_row(name, present=True)
        return self

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

    # ================= 是否默认 =================
    def defaults(self):
        """返回 {仓库名: 是否默认('是'/'否')}。"""
        return {row["name"]: row["isDefault"] for row in self.rows_data()}

    def default_name(self):
        """当前默认仓库名（有且仅一个时返回，否则 None）。"""
        hits = [n for n, d in self.defaults().items() if d == "是"]
        return hits[0] if len(hits) == 1 else None

    def open_set_default_popconfirm(self, name, nth=0):
        """点行内「设为默认」链接，返回 Popover。"""
        self.click_row_link("设为默认", name, nth)
        popover = self.page.locator(POPOVER)
        popover.wait_for(state="visible", timeout=8000)
        return popover

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
