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

通用交互在 TablePage；这里只留商品特有：高级查询、复制弹窗、多单位勾选框、三个 Tab、
条码表格与批量编辑保存。定位一律基于实测到的 id / placeholder / 可见文案；
列表行匹配按「名称」列整格比较。
"""

from pages.table_page import TablePage

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

# AntD 下拉展开后渲染在 body 上，:visible 用来排除已关闭但仍留在 DOM 里的那几个
SELECT_DROPDOWN_OPTION = ".ant-select-dropdown:visible .ant-select-dropdown-menu-item"
COLUMN_SETTINGS_POPOVER = ".ant-popover:visible"

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


class ProductPage(TablePage):
    PATH = "/material/material"
    KEYWORD_INPUT = 'input[placeholder="请输入条码、名称、助记码等查询"]'
    SPEC_INPUT = 'input[placeholder="请输入规格查询"]'
    ROWS_JS = ROWS_JS
    READ_KEYS = ("ops", "barcode", "name", "spec", "model", "color", "category",
                 "unit", "stock", "purchase", "retail", "sale", "lowest", "status")
    NAME_KEY = "name"
    NAME_LABEL = "名称"
    MENU_GROUP = "商品管理"      # 左侧一级菜单

    # 主查询框 + 重置时要一并清空的其它查询框
    SEARCH_INPUT = KEYWORD_INPUT
    SEARCH_EXTRA_INPUTS = (SPEC_INPUT,)

    # 新增/编辑弹窗内的表单字段：id 由 AntD Form 依字段名生成，前端改字段名就失效，
    # 所以只在这里写一次。用例侧统一用 field("standard") 取定位器，不要写裸 id。
    FORM_FIELDS = {
        "name": "#name",
        "unit": "#unit",
        "standard": "#standard",     # 规格
        "model": "#model",
        "color": "#color",
        "brand": "#brand",
        "remark": "#remark",
        "manufacturer": "#manufacturer",   # 制造商
    }

    def field(self, key):
        """弹窗内某个表单字段的定位器，key 见 FORM_FIELDS。"""
        return self.modal().locator(self.FORM_FIELDS[key])

    # ================= 查询 =================
    def search_spec(self, spec):
        self.fill(self.SPEC_INPUT, spec)
        self.click_button("查询")
        self._wait_table_loaded()
        return self

    def expand_query(self):
        """展开高级查询区（若尚未展开）。"""
        btn = self.page.locator(".ant-card:has(.ant-table) a, .ant-card:has(.ant-table) button").filter(has_text="展开")
        if btn.count():
            btn.first.click()
            self.pause()
        return self

    def collapse_query(self):
        """收起高级查询区（若当前是展开状态）。"""
        btn = self.page.locator(".ant-card:has(.ant-table) a, .ant-card:has(.ant-table) button").filter(has_text="收起")
        if btn.count():
            btn.first.click()
            self.pause()
        return self

    def category_select(self):
        """查询区「请选择类别」下拉（不是表单里的类别字段）。"""
        return self.page.locator(".ant-card:has(.ant-table) .ant-select").filter(
            has_text="请选择类别").first

    def category_options(self):
        """点开类别下拉并返回选项文字；不改动查询条件。"""
        self.category_select().click()
        self.page.wait_for_timeout(600)
        return [t.strip() for t in
                self.page.locator(SELECT_DROPDOWN_OPTION).all_inner_texts() if t.strip()]

    def pick_category(self):
        """选中类别下拉里第一项并查询，返回被选中的类别名。"""
        option = self.page.locator(SELECT_DROPDOWN_OPTION).first
        picked = (option.inner_text() or "").strip()
        option.click()
        self.page.wait_for_timeout(300)
        self.click_button("查询")
        self._wait_table_loaded()
        return picked

    # ================= 新增 / 编辑 / 复制弹窗 =================
    def open_copy_modal(self, name, nth=0):
        self.click_row_link("复制", name, nth)
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

    def insert_row_button(self):
        """弹窗内的「插入行」按钮（新增弹窗里两个 primary，只能按文案区分）。"""
        return self.modal().locator("button").filter(has_text="插入行")

    def active_tab_text(self):
        """当前 Tab 面板的可见文字。"""
        return self.modal().locator(".ant-tabs-tabpane-active").first.inner_text()

    # ================= 列设置 =================
    def open_column_settings(self):
        """点工具栏「列设置」，返回弹出的配置浮层。"""
        self.click_toolbar("列设置")
        self.page.wait_for_timeout(800)
        return self.page.locator(COLUMN_SETTINGS_POPOVER)
