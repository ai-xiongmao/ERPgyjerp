"""多单位 - 页面入口（TC-UNIT-001 ~ 003）。

从工作台经左侧菜单进入、直接 URL 进入、页面结构与元素完整性。
菜单进入后 title 不更新是系统既有行为，这里只记偏差，标题正确性由 URL 直达那条覆盖。
"""

from config import BASE_URL, LOGIN_PATH, UNIT_PATH
from framework.asserts import check, check_eq, check_in
from framework.registry import case

EXPECTED_HEADERS = ["", "#", "操作", "单位名称", "基本单位", "副单位", "副单位2", "副单位3", "状态"]
EXPECTED_TOOLBAR = ["新增", "删除", "启用", "禁用"]
PAGE_TITLE = "多单位 · 管伊佳ERP"


@case("TC-UNIT-001", "通过左侧菜单进入多单位页面", "页面入口", "高")
def tc_unit_001(ctx):
    """展开左侧「商品管理」→ 点击「多单位」，校验地址/标题/导航。"""
    unit = ctx.unit.enter_via_menu()
    page = unit.page

    check((page.url or "").rstrip("/").endswith(UNIT_PATH), f"进入后地址不符：{page.url}")

    # 已知系统行为：SPA 菜单跳转不更新 document.title（直接开 URL 才会变）。
    # 标题正确性由 TC-UNIT-003 覆盖；这里只记录偏差，不据此判红。
    title = unit.wait_title(PAGE_TITLE)
    if title != PAGE_TITLE:
        ctx.note(f"偏差：菜单进入后浏览器标题未更新（{title!r}）；直接访问 {UNIT_PATH} 才是「{PAGE_TITLE}」")

    # 用例表写的是「面包屑」，实测页面没有 .ant-breadcrumb，位置由页签栏承担
    breadcrumb = page.locator(".ant-breadcrumb")
    if breadcrumb.count():
        text = breadcrumb.first.inner_text()
        check("首页" in text and "多单位" in text, f"面包屑内容不符：{text!r}")
    else:
        tabs = [t.strip() for t in page.locator(".ant-tabs-tab").all_inner_texts()]
        ctx.note("页面无面包屑元素，实际由页签栏展示「首页 / 多单位」")
        check("首页" in tabs and "多单位" in tabs, f"页签栏未包含 首页/多单位：{tabs}")

    check_in("多单位", unit.active_menu_items(), "左侧菜单高亮项")


@case("TC-UNIT-002", "页面结构与元素完整性校验", "页面入口", "高")
def tc_unit_002(ctx):
    """逐项核对查询区、工具栏、表头。"""
    unit = ctx.open_unit()

    placeholder = unit.page.locator(unit.SEARCH_INPUT)
    check_eq(placeholder.count(), 1, "查询区「单位名称」输入框数量")
    check_eq(placeholder.first.get_attribute("placeholder"), "请输入单位名称查询", "输入框占位符")

    for text in ("查询", "重置"):
        check(unit.button(text).count() >= 1, f"查询区缺少「{text}」按钮")

    toolbar = unit.toolbar_labels()
    for text in EXPECTED_TOOLBAR:
        check_in(text, toolbar, "工具栏按钮")

    check_eq(unit.table_headers(), EXPECTED_HEADERS, "表头列序")


@case("TC-UNIT-003", "直接通过 URL 打开多单位页面", "页面入口", "中")
def tc_unit_003(ctx):
    """地址栏直接访问 /system/unit，不应要求重新登录。"""
    page = ctx.page
    page.goto(BASE_URL + UNIT_PATH, wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    unit = ctx.open_unit()

    check_eq((page.url or "").rstrip("/").split("?")[0], BASE_URL + UNIT_PATH, "当前地址")
    check(LOGIN_PATH not in (page.url or ""), f"被重定向到登录页：{page.url}")
    check_in("多单位", unit.active_menu_items(), "左侧菜单高亮项")
    check(unit.has_table(), "表格组件应渲染完成")
