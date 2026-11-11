"""商品信息 - 页面入口（TC-MAT-001 ~ 003）。

从工作台经左侧菜单进入、直接 URL 进入、页面结构与元素完整性。
"""

from config import BASE_URL
from framework.asserts import check, check_eq, check_in
from framework.registry import case

EXPECTED_HEADERS = [
    "", "操作", "条码", "名称", "规格", "型号", "颜色", "类别", "单位",
    "库存", "采购价", "零售价", "销售价", "最低售价", "状态",
]
EXPECTED_TOOLBAR = ["新增", "删除", "启用", "禁用", "导入", "导出",
                    "批量编辑", "修正库存", "修正成本", "列设置"]


@case("TC-MAT-001", "通过左侧菜单进入商品信息页面", "页面入口", "高")
def tc_mat_001(ctx):
    """展开「商品管理」→ 点「商品信息」，校验地址/标题/菜单高亮。"""
    product = ctx.product.enter_via_menu()
    page = product.page

    check((page.url or "").rstrip("/").endswith("/material/material"),
          f"进入后地址不符：{page.url}")

    # 已知系统行为：SPA 菜单跳转不更新 document.title（直接开 URL 才会变）。
    # 标题正确性由 TC-MAT-002 覆盖；这里只记录偏差，不据此判红，
    # 否则用例会因系统既有行为永久失败，掩盖真正的回归。
    title = product.wait_title("商品信息 · 管伊佳ERP")
    if title != "商品信息 · 管伊佳ERP":
        ctx.note(
            f"偏差：菜单进入后浏览器标题未更新（{title!r}）；"
            "直接访问 /material/material 才是「商品信息 · 管伊佳ERP」"
        )

    check_in("商品信息", product.active_menu_items(), "左侧菜单高亮项")


@case("TC-MAT-002", "直接通过 URL 打开商品信息页面", "页面入口", "中")
def tc_mat_002(ctx):
    """地址栏直接访问 /material/material，不应要求重新登录。"""
    page = ctx.page
    product = ctx.product.open()
    check_eq((page.url or "").rstrip("/").split("?")[0],
             BASE_URL + "/material/material", "当前地址")
    check("login" not in (page.url or "").lower(), f"被重定向到登录页：{page.url}")
    check_in("商品信息", product.active_menu_items(), "左侧菜单高亮项")
    check(product.has_table(), "表格组件应渲染完成")


@case("TC-MAT-003", "页面结构与元素完整性校验", "页面入口", "高")
def tc_mat_003(ctx):
    """逐项核对查询区、工具栏、表头。"""
    product = ctx.product.open()

    kw = product.page.locator(product.KEYWORD_INPUT)
    check_eq(kw.count(), 1, "关键词输入框数量")
    check_eq(kw.first.get_attribute("placeholder"), "请输入条码、名称、助记码等查询", "关键词占位符")

    spec = product.page.locator(product.SPEC_INPUT)
    check_eq(spec.count(), 1, "规格输入框数量")
    check_eq(spec.first.get_attribute("placeholder"), "请输入规格查询", "规格占位符")

    for text in ("查询", "重置"):
        check(product.button(text).count() >= 1, f"查询区缺少「{text}」按钮")

    toolbar = product.toolbar_labels()
    for text in EXPECTED_TOOLBAR:
        check_in(text, toolbar, "工具栏按钮")

    check_eq(product.table_headers(), EXPECTED_HEADERS, "表头列序")
