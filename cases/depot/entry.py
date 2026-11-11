"""仓库信息 - 页面入口（TC-DEP-001 ~ 003）。

从工作台经左侧菜单进入、直接 URL 进入、页面结构与元素完整性。
"""

from config import BASE_URL
from framework.asserts import check, check_eq, check_in
from framework.registry import case

EXPECTED_HEADERS = [
    "", "#", "操作", "仓库名称", "仓库地址", "仓储费", "搬运费",
    "负责人", "备注", "排序", "状态", "是否默认",
]
EXPECTED_TOOLBAR = ["新增", "删除", "启用", "禁用"]


@case("TC-DEP-001", "通过左侧菜单进入仓库信息页面", "页面入口", "高")
def tc_dep_001(ctx):
    """展开「基础资料」→ 点「仓库信息」，校验地址/标题/菜单高亮。"""
    depot = ctx.depot.enter_via_menu()
    page = depot.page

    check((page.url or "").rstrip("/").endswith("/system/depot"), f"进入后地址不符：{page.url}")

    # 与多单位/商品页一致的已知行为：SPA 菜单跳转不更新 document.title
    title = depot.wait_title("仓库信息 · 管伊佳ERP")
    if title != "仓库信息 · 管伊佳ERP":
        ctx.note(
            f"偏差：菜单进入后浏览器标题未更新（{title!r}）；"
            "直接访问 /system/depot 才是「仓库信息 · 管伊佳ERP」"
        )

    check_in("仓库信息", depot.active_menu_items(), "左侧菜单高亮项")


@case("TC-DEP-002", "直接通过 URL 打开仓库信息页面", "页面入口", "中")
def tc_dep_002(ctx):
    """地址栏直接访问 /system/depot，不应要求重新登录。"""
    page = ctx.page
    depot = ctx.depot.open()
    check_eq((page.url or "").rstrip("/").split("?")[0],
             BASE_URL + "/system/depot", "当前地址")
    check("login" not in (page.url or "").lower(), f"被重定向到登录页：{page.url}")
    check_in("仓库信息", depot.active_menu_items(), "左侧菜单高亮项")
    check(depot.has_table(), "表格组件应渲染完成")


@case("TC-DEP-003", "页面结构与元素完整性校验", "页面入口", "高")
def tc_dep_003(ctx):
    """逐项核对查询区、工具栏、表头。"""
    depot = ctx.depot.open()

    name_input = depot.page.locator(depot.NAME_INPUT)
    check_eq(name_input.count(), 1, "仓库名称输入框数量")
    check_eq(name_input.first.get_attribute("placeholder"), "请输入仓库名称查询", "仓库名称占位符")

    remark_input = depot.page.locator(depot.REMARK_INPUT)
    check_eq(remark_input.count(), 1, "备注输入框数量")
    check_eq(remark_input.first.get_attribute("placeholder"), "请输入备注查询", "备注占位符")

    for text in ("查询", "重置"):
        check(depot.button(text).count() >= 1, f"查询区缺少「{text}」按钮")

    toolbar = depot.toolbar_labels()
    for text in EXPECTED_TOOLBAR:
        check_in(text, toolbar, "工具栏按钮")

    check_eq(depot.table_headers(), EXPECTED_HEADERS, "表头列序")
